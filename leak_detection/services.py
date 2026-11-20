from __future__ import annotations

import json
import logging
import threading
from datetime import timedelta
from decimal import Decimal

from django.db import close_old_connections, transaction
from django.utils import timezone

from monitoring.models import FlowReading, Pipeline, Sensor
from system_settings.models import SystemSettings

from .localize import estimate_break
from .models import LeakEvent
from .sms_format import format_leak_sms

logger = logging.getLogger(__name__)


def _latest_near(sensor: Sensor, at, window_seconds: int = 30):
    lo = at - timedelta(seconds=window_seconds)
    hi = at + timedelta(seconds=window_seconds)
    return (
        FlowReading.objects.filter(
            sensor=sensor, reading_timestamp__gte=lo, reading_timestamp__lte=hi
        )
        .order_by("-reading_timestamp")
        .first()
    )


def compare_pipeline(pipeline: Pipeline, window_seconds: int = 30) -> dict:
    settings = SystemSettings.load()
    inlet = Sensor.objects.filter(
        pipeline=pipeline, sensor_position=Sensor.Position.INLET
    ).first()
    outlet = Sensor.objects.filter(
        pipeline=pipeline, sensor_position=Sensor.Position.OUTLET
    ).first()
    if not inlet or not outlet:
        return {"error": "Pipeline requires inlet and outlet sensors"}

    ref = timezone.now()
    inlet_r = _latest_near(inlet, ref, window_seconds) or inlet.readings.order_by(
        "-reading_timestamp"
    ).first()
    outlet_r = _latest_near(outlet, ref, window_seconds) or outlet.readings.order_by(
        "-reading_timestamp"
    ).first()
    if not inlet_r or not outlet_r:
        return {"error": "Insufficient readings to compare"}

    inlet_flow = Decimal(inlet_r.flow_rate)
    outlet_flow = Decimal(outlet_r.flow_rate)
    difference = inlet_flow - outlet_flow
    pct = (difference / inlet_flow * Decimal("100")) if inlet_flow > 0 else Decimal("0")

    tolerance = Decimal(settings.sensor_difference_tolerance)
    flow_threshold = Decimal(settings.leak_trigger_flow_difference)
    pct_threshold = Decimal(settings.leak_trigger_percentage)

    # Arm only when there is meaningful inlet flow (avoid dry-pipe noise)
    armed = inlet_flow >= Decimal("2.0")
    is_leak = bool(
        armed
        and abs(difference) > tolerance
        and abs(difference) >= flow_threshold
        and abs(pct) >= pct_threshold
    )

    return {
        "inlet_sensor_id": inlet.id,
        "outlet_sensor_id": outlet.id,
        "inlet_flow_rate": inlet_flow,
        "outlet_flow_rate": outlet_flow,
        "flow_difference": difference,
        "difference_percentage": pct,
        "is_leak_candidate": is_leak,
        "settings": {
            "tolerance": tolerance,
            "flow_threshold": flow_threshold,
            "pct_threshold": pct_threshold,
            "duration": settings.leak_detection_duration,
        },
    }


def _severity_for(pct: Decimal) -> str:
    if pct >= Decimal("50"):
        return LeakEvent.Severity.CRITICAL
    if pct >= Decimal("30"):
        return LeakEvent.Severity.HIGH
    if pct >= Decimal("15"):
        return LeakEvent.Severity.MEDIUM
    return LeakEvent.Severity.LOW


def _dispatch_sms(event_id: int, message: str) -> None:
    def worker():
        close_old_connections()
        try:
            from django.conf import settings as dj_settings
            from notifications.sms import send_sms

            # Tag SMS sends so finance can attribute cost to this leak
            dj_settings._CUE_LEAK_EVENT_ID = event_id
            try:
                results = send_sms(message)
            finally:
                try:
                    delattr(dj_settings, "_CUE_LEAK_EVENT_ID")
                except Exception:
                    dj_settings._CUE_LEAK_EVENT_ID = None

            ok = any(r.get("ok") for r in results)
            LeakEvent.objects.filter(pk=event_id).update(
                sms_sent=ok,
                sms_response=json.dumps(results, default=str)[:4000],
                sms_sent_at=timezone.now() if ok else None,
            )
            if ok:
                try:
                    from finance.services import record_sms_cost

                    for r in results:
                        if r.get("ok") and r.get("mobile"):
                            record_sms_cost(
                                mobile=r["mobile"], leak_event_id=event_id, ok=True
                            )
                except Exception:
                    logger.exception("Finance SMS record failed event=%s", event_id)
            logger.info("Leak SMS event=%s ok=%s", event_id, ok)
        except Exception:
            logger.exception("Leak SMS failed for event=%s", event_id)
            LeakEvent.objects.filter(pk=event_id).update(
                sms_response="SMS worker exception — see server logs"
            )
        finally:
            close_old_connections()

    threading.Thread(target=worker, daemon=True).start()


def _send_leak_sms_once(event: LeakEvent, *, zone: str = "ZONE_1") -> None:
    if event.sms_sent:
        return
    length = float(getattr(event.pipeline, "length_meters", 50) or 50)
    locus = estimate_break(
        float(event.inlet_flow_rate),
        float(event.outlet_flow_rate),
        length_m=length,
    )
    if event.estimate_from_s1_m is not None:
        locus["distance_from_s1_m"] = event.estimate_from_s1_m
        locus["distance_from_s2_m"] = event.estimate_from_s2_m
        locus["severity_pct"] = event.estimate_severity_pct
        if event.estimate_summary:
            locus["summary"] = event.estimate_summary
        locus["available"] = True

    message = format_leak_sms(
        zone=zone,
        inlet=float(event.inlet_flow_rate),
        outlet=float(event.outlet_flow_rate),
        locus=locus,
        from_s1_m=event.estimate_from_s1_m,
        from_s2_m=event.estimate_from_s2_m,
        severity_pct=event.estimate_severity_pct,
        length_m=length,
    )
    # Mark pending so concurrent confirmations don't double-send
    LeakEvent.objects.filter(pk=event.id, sms_sent=False).update(
        sms_response="sending"
    )
    _dispatch_sms(event.id, message)


def _notify_confirmed(event: LeakEvent):
    from notifications.services import create_notification

    create_notification(
        title="Confirmed leak",
        message=f"Confirmed leak on pipeline {event.pipeline.pipeline_name}.",
        notification_type="LEAK_CONFIRMED",
        severity="CRITICAL",
    )
    try:
        from finance.services import record_leak_water_loss

        record_leak_water_loss(event)
    except Exception:
        logger.exception("Finance water-loss record failed for leak=%s", event.id)
    _send_leak_sms_once(event)


def _maybe_shutdown(event: LeakEvent, settings):
    if not settings.automatic_valve_shutdown:
        return
    from valves.models import Valve, ValveCommand
    from valves.services import request_command

    qs = Valve.objects.filter(pipeline=event.pipeline)
    # Prefer AUTOMATIC valves; fall back to any kit valve on this pipeline
    valves = list(qs.filter(control_mode=Valve.ControlMode.AUTOMATIC)) or list(qs)
    for valve in valves:
        try:
            request_command(valve, ValveCommand.CommandType.CLOSE, user=None)
        except Exception:
            logger.exception("Auto valve CLOSE failed for %s", valve.valve_identifier)


@transaction.atomic
def evaluate_pipeline(pipeline: Pipeline) -> LeakEvent | None:
    """Evaluate a pipeline and update/create a leak event; SMS on confirm."""
    settings = SystemSettings.load()
    if not settings.automatic_leak_detection:
        return None

    result = compare_pipeline(pipeline)
    if "error" in result:
        return None

    active = (
        LeakEvent.objects.filter(pipeline=pipeline)
        .exclude(detection_status=LeakEvent.DetectionStatus.RESOLVED)
        .order_by("-started_at")
        .first()
    )

    duration = int(settings.leak_detection_duration or 30)

    if result["is_leak_candidate"]:
        if active:
            active.inlet_flow_rate = result["inlet_flow_rate"]
            active.outlet_flow_rate = result["outlet_flow_rate"]
            active.flow_difference = result["flow_difference"]
            active.difference_percentage = result["difference_percentage"]
            active.severity = _severity_for(abs(result["difference_percentage"]))

            elapsed = (timezone.now() - active.started_at).total_seconds()
            if (
                active.detection_status == LeakEvent.DetectionStatus.SUSPECTED
                and elapsed >= duration
            ):
                active.detection_status = LeakEvent.DetectionStatus.CONFIRMED
                active.save()
                _notify_confirmed(active)
                _maybe_shutdown(active, settings)
            else:
                active.save()
            return active

        event = LeakEvent.objects.create(
            pipeline=pipeline,
            inlet_sensor_id=result["inlet_sensor_id"],
            outlet_sensor_id=result["outlet_sensor_id"],
            inlet_flow_rate=result["inlet_flow_rate"],
            outlet_flow_rate=result["outlet_flow_rate"],
            flow_difference=result["flow_difference"],
            difference_percentage=result["difference_percentage"],
            detection_status=LeakEvent.DetectionStatus.SUSPECTED,
            severity=_severity_for(abs(result["difference_percentage"])),
            started_at=timezone.now(),
            description="Flow difference exceeded threshold.",
        )
        from notifications.services import create_notification

        create_notification(
            title="Suspected leak detected",
            message=(
                f"Pipeline {pipeline.pipeline_name} flow difference "
                f"{result['flow_difference']} L/min."
            ),
            notification_type="LEAK_SUSPECTED",
            severity="WARNING",
        )
        # Instant confirm if duration is very short (<=5s) — useful for demos
        if duration <= 5:
            event.detection_status = LeakEvent.DetectionStatus.CONFIRMED
            event.save(update_fields=["detection_status", "updated_at"])
            _notify_confirmed(event)
            _maybe_shutdown(event, settings)
        return event

    # Normal — resolve active event if stable
    if active:
        active.detection_status = LeakEvent.DetectionStatus.RESOLVED
        active.resolved_at = timezone.now()
        active.save()
        from notifications.services import create_notification

        create_notification(
            title="Leak resolved",
            message=f"Pipeline {pipeline.pipeline_name} has returned to normal flow.",
            notification_type="LEAK_RESOLVED",
            severity="INFO",
        )
    return None


@transaction.atomic
def handle_firmware_leak_alert(
    pipeline: Pipeline,
    *,
    zone: str,
    inlet: float,
    outlet: float,
    estimate: dict | None = None,
) -> LeakEvent:
    """
    Firmware already confirmed LEAK_ALERT — create/confirm event, close valve, SMS.
    """
    settings = SystemSettings.load()
    inlet_s = Sensor.objects.filter(
        pipeline=pipeline, sensor_position=Sensor.Position.INLET
    ).first()
    outlet_s = Sensor.objects.filter(
        pipeline=pipeline, sensor_position=Sensor.Position.OUTLET
    ).first()

    difference = Decimal(str(round(inlet - outlet, 4)))
    pct = (
        (difference / Decimal(str(inlet)) * Decimal("100"))
        if inlet > 0
        else Decimal("0")
    )
    est = estimate or {}
    length = float(getattr(pipeline, "length_meters", 50) or 50)
    locus = estimate_break(inlet, outlet, length_m=length)
    s1 = est.get("from_s1_m", locus.get("distance_from_s1_m"))
    s2 = est.get("from_s2_m", locus.get("distance_from_s2_m"))
    sev = est.get("severity_pct", locus.get("severity_pct"))
    summary = est.get("summary") or locus.get("summary") or ""

    active = (
        LeakEvent.objects.filter(pipeline=pipeline)
        .exclude(detection_status=LeakEvent.DetectionStatus.RESOLVED)
        .order_by("-started_at")
        .first()
    )

    if active:
        event = active
        event.inlet_flow_rate = Decimal(str(inlet))
        event.outlet_flow_rate = Decimal(str(outlet))
        event.flow_difference = difference
        event.difference_percentage = pct
        event.severity = _severity_for(abs(pct))
        event.detection_status = LeakEvent.DetectionStatus.CONFIRMED
        event.estimate_from_s1_m = float(s1) if s1 is not None else None
        event.estimate_from_s2_m = float(s2) if s2 is not None else None
        event.estimate_severity_pct = float(sev) if sev is not None else None
        event.estimate_summary = (summary or "")[:255]
        event.raw_alert_line = f"LEAK_ALERT:{zone}:{inlet}:{outlet}"[:255]
        event.description = "Firmware LEAK_ALERT confirmed."
        event.save()
    else:
        event = LeakEvent.objects.create(
            pipeline=pipeline,
            inlet_sensor=inlet_s,
            outlet_sensor=outlet_s,
            inlet_flow_rate=Decimal(str(inlet)),
            outlet_flow_rate=Decimal(str(outlet)),
            flow_difference=difference,
            difference_percentage=pct,
            detection_status=LeakEvent.DetectionStatus.CONFIRMED,
            severity=_severity_for(abs(pct)),
            started_at=timezone.now(),
            description="Firmware LEAK_ALERT confirmed.",
            estimate_from_s1_m=float(s1) if s1 is not None else None,
            estimate_from_s2_m=float(s2) if s2 is not None else None,
            estimate_severity_pct=float(sev) if sev is not None else None,
            estimate_summary=(summary or "")[:255],
            raw_alert_line=f"LEAK_ALERT:{zone}:{inlet}:{outlet}"[:255],
        )

    from notifications.services import create_notification

    create_notification(
        title="Confirmed leak (firmware)",
        message=f"{zone}: inlet {inlet:.2f} / outlet {outlet:.2f} L/min. Valve closing.",
        notification_type="LEAK_CONFIRMED",
        severity="CRITICAL",
    )

    # Always attempt valve close on firmware alert
    from valves.models import Valve, ValveCommand
    from valves.services import request_command

    for valve in Valve.objects.filter(pipeline=pipeline):
        try:
            request_command(valve, ValveCommand.CommandType.CLOSE, user=None)
        except Exception:
            logger.exception("Firmware alert valve CLOSE failed")

    # Also honour settings flag for any extra AUTOMATIC valves
    _maybe_shutdown(event, settings)
    _send_leak_sms_once(event, zone=zone)
    return event
