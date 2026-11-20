"""Production device inventory helpers — heartbeat, live sensors, warnings."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from monitoring.models import FlowReading, Sensor
from system_settings.models import SystemSettings


def heartbeat_timeout_seconds() -> int:
    try:
        return int(SystemSettings.load().device_heartbeat_timeout or 120)
    except Exception:
        return 120


def seconds_since(dt) -> int | None:
    if not dt:
        return None
    return max(0, int((timezone.now() - dt).total_seconds()))


def effective_connection(device) -> str:
    """CONNECTED only if last_communication is within heartbeat timeout."""
    timeout = heartbeat_timeout_seconds()
    age = seconds_since(device.last_communication)
    if age is None:
        return "UNKNOWN"
    if age <= timeout and device.is_active:
        return "CONNECTED"
    return "DISCONNECTED"


def sync_stale_devices() -> int:
    """Mark devices DISCONNECTED when heartbeat is stale. Returns count updated."""
    from .models import Device

    timeout = heartbeat_timeout_seconds()
    cutoff = timezone.now() - timedelta(seconds=timeout)
    n = 0
    for d in Device.objects.filter(connection_status=Device.ConnectionStatus.CONNECTED):
        if not d.last_communication or d.last_communication < cutoff or not d.is_active:
            d.connection_status = Device.ConnectionStatus.DISCONNECTED
            d.save(update_fields=["connection_status", "updated_at"])
            n += 1
    return n


def latest_sensor_snapshot(sensor: Sensor) -> dict[str, Any]:
    last = (
        FlowReading.objects.filter(sensor=sensor)
        .order_by("-reading_timestamp")
        .first()
    )
    return {
        "id": sensor.id,
        "sensor_name": sensor.sensor_name,
        "sensor_identifier": sensor.sensor_identifier,
        "sensor_position": sensor.sensor_position,
        "status": sensor.status,
        "calibration_factor": float(sensor.calibration_factor),
        "flow_rate_lpm": float(last.flow_rate) if last else None,
        "volume_l": float(last.volume) if last and last.volume is not None else None,
        "last_reading_at": last.reading_timestamp.isoformat() if last else None,
        "reading_age_seconds": seconds_since(last.reading_timestamp) if last else None,
    }


def device_inventory_row(device) -> dict[str, Any]:
    from notifications.models import Notification

    conn = effective_connection(device)
    age = seconds_since(device.last_communication)
    timeout = heartbeat_timeout_seconds()
    sensors = [latest_sensor_snapshot(s) for s in device.sensors.all()]
    valves = [
        {
            "id": v.id,
            "valve_name": v.valve_name,
            "valve_identifier": v.valve_identifier,
            "current_status": v.current_status,
            "control_mode": v.control_mode,
            "last_updated": v.last_updated.isoformat() if v.last_updated else None,
        }
        for v in device.valves.all()
    ]

    sensor_faults = sum(1 for s in sensors if s["status"] == "FAULTY")
    stale_sensors = sum(
        1
        for s in sensors
        if s["reading_age_seconds"] is None or s["reading_age_seconds"] > timeout
    )
    warnings = Notification.objects.filter(
        notification_type__in=[
            Notification.Type.HARDWARE_WARNING,
            Notification.Type.DEVICE_DISCONNECTED,
            Notification.Type.SENSOR_ERROR,
        ],
        is_read=False,
    ).count()

    if conn != "CONNECTED":
        health = "OFFLINE"
        health_note = "No heartbeat within timeout"
    elif sensor_faults:
        health = "DEGRADED"
        health_note = f"{sensor_faults} faulty sensor(s)"
    elif stale_sensors and sensors:
        health = "DEGRADED"
        health_note = "Sensor readings stale"
    elif not device.is_active:
        health = "INACTIVE"
        health_note = "Device deactivated"
    else:
        health = "HEALTHY"
        health_note = "Online with recent telemetry"

    inlet = next((s for s in sensors if s["sensor_position"] == "INLET"), None)
    outlet = next((s for s in sensors if s["sensor_position"] == "OUTLET"), None)

    return {
        "id": device.id,
        "device_name": device.device_name,
        "device_identifier": device.device_identifier,
        "device_type": device.device_type,
        "location": device.location or "",
        "firmware_version": device.firmware_version or "",
        "is_active": device.is_active,
        "connection_status": conn,
        "stored_connection_status": device.connection_status,
        "last_communication": device.last_communication.isoformat()
        if device.last_communication
        else None,
        "heartbeat_age_seconds": age,
        "heartbeat_timeout_seconds": timeout,
        "health": health,
        "health_note": health_note,
        "sensors": sensors,
        "sensor_count": len(sensors),
        "inlet_flow_lpm": inlet["flow_rate_lpm"] if inlet else None,
        "outlet_flow_lpm": outlet["flow_rate_lpm"] if outlet else None,
        "valves": valves,
        "valve_state": valves[0]["current_status"] if valves else None,
        "hardware_warnings_open": warnings,
        "created_at": device.created_at.isoformat() if device.created_at else None,
    }


def inventory_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    connected = sum(1 for r in rows if r["connection_status"] == "CONNECTED")
    degraded = sum(1 for r in rows if r["health"] in ("DEGRADED", "OFFLINE", "INACTIVE"))
    latest = None
    for r in rows:
        ts = r.get("last_communication")
        if ts and (latest is None or ts > latest):
            latest = ts
    warn = rows[0]["hardware_warnings_open"] if rows else 0
    return {
        "total": len(rows),
        "connected": connected,
        "offline": len(rows) - connected,
        "degraded_or_offline": degraded,
        "last_communication": latest,
        "hardware_warnings": warn,
        "heartbeat_timeout_seconds": heartbeat_timeout_seconds(),
    }
