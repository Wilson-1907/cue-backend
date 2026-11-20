"""Create/ensure UNO-KIT-001 + S1/S2 and print a fresh API key for the Windows agent."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Provision UNO-KIT-001 API key + write scripts/uno_agent/config.json template"

    def add_arguments(self, parser):
        parser.add_argument(
            "--api-base",
            default="http://127.0.0.1:8000/api/v1",
            help="Public CUE API base (Contabo URL after hosting)",
        )
        parser.add_argument(
            "--write-config",
            action="store_true",
            help="Write scripts/uno_agent/config.json with the new key",
        )

    def handle(self, *args, **options):
        from devices.models import Device
        from monitoring.models import Pipeline, Sensor
        from valves.models import Valve

        device, _ = Device.objects.get_or_create(
            device_identifier="UNO-KIT-001",
            defaults={
                "device_name": "CUE Uno Kit",
                "device_type": Device.DeviceType.ARDUINO_ESP,
                "location": "USB serial (any port)",
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
        for sid, name, pos in (
            ("S1", "Inlet S1", Sensor.Position.INLET),
            ("S2", "Outlet S2", Sensor.Position.OUTLET),
        ):
            s, _ = Sensor.objects.get_or_create(
                sensor_identifier=sid,
                defaults={
                    "sensor_name": name,
                    "device": device,
                    "sensor_position": pos,
                    "pipeline": pipe,
                },
            )
            if s.device_id != device.id:
                s.device = device
                s.save(update_fields=["device"])
            if s.pipeline_id != pipe.id:
                s.pipeline = pipe
                s.save(update_fields=["pipeline"])

        Valve.objects.get_or_create(
            valve_identifier="UNO-KIT-001-VALVE",
            defaults={
                "valve_name": "CUE Kit Valve",
                "device": device,
                "pipeline": pipe,
                "current_status": Valve.Status.OPEN,
                "control_mode": Valve.ControlMode.MANUAL,
            },
        )

        raw = Device.generate_api_key()
        device.set_api_key(raw)
        device.is_active = True
        device.save()

        api_base = options["api_base"].rstrip("/")
        cfg = {
            "api_base": api_base,
            "device_id": "UNO-KIT-001",
            "api_key": raw,
            "baud": 9600,
            "sensor_inlet": "S1",
            "sensor_outlet": "S2",
            "scan_interval_sec": 2,
            "prefer_vid": True,
            "port": "",
        }

        self.stdout.write(self.style.SUCCESS("UNO-KIT-001 provisioned"))
        self.stdout.write(f"device_id: UNO-KIT-001")
        self.stdout.write(self.style.WARNING(f"api_key:  {raw}"))
        self.stdout.write(f"api_base:  {api_base}")
        self.stdout.write("Store the api_key now — it cannot be shown again.")

        if options["write_config"]:
            # .../backend/iot/management/commands/this.py → parents[3] = backend/
            root = Path(__file__).resolve().parents[3]
            out = root / "scripts" / "uno_agent" / "config.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Wrote {out}"))
