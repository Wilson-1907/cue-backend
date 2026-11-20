"""
USB serial bridge: Arduino Uno (IOT/firmware) -> CUE backend models.

Minimal glue only — does not change firmware or product APIs.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone as dt_tz
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)

FLOW_RE = re.compile(
    r"Inlet \(S1\):\s*(?P<inlet>[-+]?\d*\.?\d+)\s*L/min\s*\|\s*"
    r"Outlet \(S2\):\s*(?P<outlet>[-+]?\d*\.?\d+)\s*L/min",
    re.I,
)
DV_RE = re.compile(
    r"dV_in:(?P<din>[-+]?\d*\.?\d+)mL\s+dV_out:(?P<dout>[-+]?\d*\.?\d+)mL",
    re.I,
)
LEAK_RE = re.compile(
    r"^LEAK_ALERT:(?P<zone>[A-Za-z0-9_]+):(?P<inlet>[-+]?\d*\.?\d+):(?P<outlet>[-+]?\d*\.?\d+)\s*$"
)
# ESTIMATE:s1_m:s2_m:sev:length:loss:qin:qout:band
ESTIMATE_RE = re.compile(
    r"^ESTIMATE:(?P<s1>[-+]?\d*\.?\d+):(?P<s2>[-+]?\d*\.?\d+):(?P<sev>[-+]?\d*\.?\d+)"
    r":(?P<length>[-+]?\d*\.?\d+):(?P<loss>[-+]?\d*\.?\d+)"
    r":(?P<qin>[-+]?\d*\.?\d+):(?P<qout>[-+]?\d*\.?\d+):(?P<band>\d+)\s*$"
)


def _ensure_kit():
    from devices.models import Device
    from monitoring.models import Pipeline, Sensor
    from valves.models import Valve

    device, _ = Device.objects.get_or_create(
        device_identifier="UNO-KIT-001",
        defaults={
            "device_name": "CUE Uno Kit",
            "device_type": Device.DeviceType.ARDUINO_ESP,
            "location": "Lab / COM serial",
            "is_active": True,
        },
    )
    pipe, _ = Pipeline.objects.get_or_create(
        pipeline_code="ZONE1",
        defaults={
            "pipeline_name": "Zone 1 S1-S2",
            "length_meters": Decimal("50.00"),
            "location": "S1 inlet to S2 outlet",
        },
    )
    s1, _ = Sensor.objects.get_or_create(
        sensor_identifier="S1",
        defaults={
            "sensor_name": "Inlet S1",
            "device": device,
            "sensor_position": Sensor.Position.INLET,
            "pipeline": pipe,
        },
    )
    if s1.device_id != device.id:
        s1.device = device
        s1.save(update_fields=["device"])
    s2, _ = Sensor.objects.get_or_create(
        sensor_identifier="S2",
        defaults={
            "sensor_name": "Outlet S2",
            "device": device,
            "sensor_position": Sensor.Position.OUTLET,
            "pipeline": pipe,
        },
    )
    if s2.device_id != device.id:
        s2.device = device
        s2.save(update_fields=["device"])
    valve, _ = Valve.objects.get_or_create(
        valve_identifier="UNO-KIT-001-VALVE",
        defaults={
            "valve_name": "CUE Kit Valve",
            "device": device,
            "pipeline": pipe,
            "current_status": Valve.Status.OPEN,
            "control_mode": Valve.ControlMode.MANUAL,
        },
    )
    changed = []
    if valve.device_id != device.id:
        valve.device = device
        changed.append("device")
    if valve.pipeline_id != pipe.id:
        valve.pipeline = pipe
        changed.append("pipeline")
    if changed:
        valve.save(update_fields=changed + ["updated_at"])
    return device, s1, s2, pipe


class Command(BaseCommand):
    help = "Bridge IOT/firmware Uno serial into CUE (devices/monitoring)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--port",
            default=getattr(settings, "SERIAL_PORT", None) or "",
            help="COM port (empty + --auto = discover any port)",
        )
        parser.add_argument(
            "--baud",
            type=int,
            default=int(getattr(settings, "SERIAL_BAUD", 9600) or 9600),
        )
        parser.add_argument(
            "--auto",
            action="store_true",
            help="Auto-detect Uno on any COM port and reconnect forever when replugged",
        )

    def handle(self, *args, **options):
        try:
            import serial
            from serial.tools import list_ports
        except ImportError as exc:
            raise SystemExit("pip install pyserial") from exc

        from monitoring.models import FlowReading
        from devices.models import DeviceCommunicationLog

        baud = options["baud"]
        auto = options["auto"] or not (options["port"] or "").strip()
        port = (options["port"] or "").strip() or "COM10"

        ARDUINO_VIDS = {0x2341, 0x2A03, 0x1A86, 0x0403, 0x10C4, 0x067B}

        def discover_port() -> str | None:
            ports = list(list_ports.comports())
            self.stdout.write("Ports:")
            for p in ports:
                self.stdout.write(f"  {p.device}: {p.description}")
            if not ports:
                return None
            ranked = []
            for p in ports:
                score = 0
                desc = f"{p.description or ''} {p.manufacturer or ''}".lower()
                if p.vid and int(p.vid) in ARDUINO_VIDS:
                    score += 100
                if any(k in desc for k in ("arduino", "ch340", "uno", "usb-serial", "cp210")):
                    score += 50
                ranked.append((score, p.device))
            ranked.sort(key=lambda x: (-x[0], x[1]))
            return ranked[0][1] if ranked else None

        device, s1, s2, pipe = _ensure_kit()
        # Ensure auto leak detect + valve shutdown are on for the kit
        try:
            from system_settings.models import SystemSettings

            ss = SystemSettings.load()
            changed = []
            if not ss.automatic_leak_detection:
                ss.automatic_leak_detection = True
                changed.append("automatic_leak_detection")
            if not ss.automatic_valve_shutdown:
                ss.automatic_valve_shutdown = True
                changed.append("automatic_valve_shutdown")
            if changed:
                ss.save(update_fields=changed + ["updated_at"])
                self.stdout.write(self.style.WARNING(f"Enabled settings: {', '.join(changed)}"))
        except Exception:
            logger.exception("settings bootstrap failed")

        vol_in = Decimal("0")
        vol_out = Decimal("0")
        pulse_tick = 0
        pending_estimate: dict | None = None
        pending_leak: dict | None = None

        def _flush_pending_leak():
            nonlocal pending_leak, pending_estimate
            if not pending_leak:
                return
            try:
                from leak_detection.services import handle_firmware_leak_alert

                event = handle_firmware_leak_alert(
                    pipe,
                    zone=pending_leak["zone"],
                    inlet=pending_leak["inlet"],
                    outlet=pending_leak["outlet"],
                    estimate=pending_estimate,
                )
                self.stdout.write(
                    self.style.ERROR(
                        f"LEAK handled id={event.id} status={event.detection_status} "
                        f"sms={'queued' if not event.sms_sent else 'sent'}"
                    )
                )
            except Exception:
                logger.exception("firmware leak alert handling failed")
            pending_leak = None
            pending_estimate = None

        while True:
            try:
                if auto:
                    found = discover_port()
                    if not found:
                        self.stdout.write(
                            self.style.WARNING("No serial device — plug Uno into any USB port…")
                        )
                        time.sleep(2)
                        continue
                    port = found
                self.stdout.write(self.style.SUCCESS(f"Listening {port} @ {baud}"))
                with serial.Serial(port, baud, timeout=0.2) as ser:
                    device.mark_connected()
                    self.stdout.write(self.style.SUCCESS(f"Connected {port}"))
                    while True:
                        close_old_connections()
                        # Pending valve close/open from product UI -> Uno
                        try:
                            from valves.models import ValveCommand

                            cmd = (
                                ValveCommand.objects.filter(
                                    execution_status=ValveCommand.ExecutionStatus.PENDING
                                )
                                .order_by("id")
                                .first()
                            )
                            if cmd:
                                action = (cmd.command_type or "").upper()
                                if action in {"CLOSE", "OPEN"}:
                                    # Firmware: CLOSE shuts valve; RESET/OPEN reopens
                                    line = "CLOSE" if action == "CLOSE" else "RESET"
                                    ser.write((line + "\r\n").encode())
                                    ser.flush()
                                    from valves.services import execute_command

                                    execute_command(
                                        cmd,
                                        success=True,
                                        message=f"Sent {line} to Uno",
                                    )
                                    self.stdout.write(self.style.WARNING(f"TX {line}"))
                        except Exception:
                            logger.exception("valve command poll failed")

                        raw = ser.readline()
                        if not raw:
                            continue
                        text = raw.decode("utf-8", errors="replace").strip()
                        if not text:
                            continue
                        safe = text.encode("ascii", errors="replace").decode("ascii")
                        self.stdout.write(f"SERIAL: {safe}")

                        est_m = ESTIMATE_RE.match(text)
                        if est_m:
                            band_i = int(est_m.group("band"))
                            band_name = {1: "near_S1", 2: "mid", 3: "near_S2"}.get(
                                band_i, str(band_i)
                            )
                            pending_estimate = {
                                "from_s1_m": float(est_m.group("s1")),
                                "from_s2_m": float(est_m.group("s2")),
                                "severity_pct": float(est_m.group("sev")),
                                "length_m": float(est_m.group("length")),
                                "summary": (
                                    f"PIN ~{float(est_m.group('s1')):.0f}m from S1 / "
                                    f"~{float(est_m.group('s2')):.0f}m from S2 "
                                    f"(band {band_name}, loss {float(est_m.group('loss')):.2f} L/min)"
                                ),
                            }
                            self.stdout.write(
                                self.style.WARNING(f"ESTIMATE: {pending_estimate['summary']}")
                            )
                            # Firmware sends ESTIMATE right after LEAK_ALERT
                            if pending_leak:
                                _flush_pending_leak()
                            continue

                        leak = LEAK_RE.match(text)
                        if leak:
                            pending_leak = {
                                "zone": leak.group("zone"),
                                "inlet": float(leak.group("inlet")),
                                "outlet": float(leak.group("outlet")),
                            }
                            self.stdout.write(
                                self.style.ERROR(
                                    f"LEAK_ALERT buffered {pending_leak['zone']} "
                                    f"{pending_leak['inlet']}/{pending_leak['outlet']} — waiting ESTIMATE"
                                )
                            )
                            continue

                        m = FLOW_RE.search(text)
                        if not m:
                            # If we got other lines after a leak without ESTIMATE, still flush
                            if pending_leak and text.startswith("REPAIR:"):
                                _flush_pending_leak()
                            continue

                        # New flow telemetry — flush any buffered leak first
                        if pending_leak:
                            _flush_pending_leak()
                        inlet = Decimal(m.group("inlet"))
                        outlet = Decimal(m.group("outlet"))
                        din = Decimal("0")
                        dout = Decimal("0")
                        dv = DV_RE.search(text)
                        if dv:
                            din = Decimal(dv.group("din"))
                            dout = Decimal(dv.group("dout"))
                            if din < 4:
                                din = Decimal("0")
                            if dout < 4:
                                dout = Decimal("0")
                        vol_in += din / Decimal("1000")
                        vol_out += dout / Decimal("1000")
                        pulse_tick += 1
                        now = timezone.now()
                        ts_in = now
                        ts_out = now

                        try:
                            r_in = FlowReading.objects.create(
                                sensor=s1,
                                device=device,
                                flow_rate=inlet,
                                volume=vol_in,
                                pulse_count=pulse_tick,
                                reading_timestamp=ts_in,
                            )
                            r_out = FlowReading.objects.create(
                                sensor=s2,
                                device=device,
                                flow_rate=outlet,
                                volume=vol_out,
                                pulse_count=pulse_tick,
                                reading_timestamp=ts_out,
                            )
                            device.mark_connected()
                            DeviceCommunicationLog.objects.create(
                                device=device,
                                kind="READING",
                                payload={
                                    "inlet_lpm": float(inlet),
                                    "outlet_lpm": float(outlet),
                                },
                            )
                            try:
                                from config.broadcast import broadcast_kit_flow

                                broadcast_kit_flow(r_in, r_out)
                            except Exception:
                                logger.exception("broadcast reading failed")
                            # Continuous backend leak evaluation (SMS on confirm)
                            try:
                                from leak_detection.services import evaluate_pipeline

                                evaluate_pipeline(pipe)
                            except Exception:
                                logger.exception("evaluate_pipeline failed")
                        except Exception:
                            logger.exception("persist reading failed")
            except serial.SerialException as exc:
                self.stderr.write(self.style.ERROR(f"{port}: {exc} — retry 2s"))
                time.sleep(2)
            except KeyboardInterrupt:
                break
