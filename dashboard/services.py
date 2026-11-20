from datetime import timedelta

from django.db.models import Avg, Count
from django.db.models.functions import TruncDay, TruncHour, TruncMinute
from django.utils import timezone

from devices.models import Device
from leak_detection.models import LeakEvent
from monitoring.models import FlowReading, Pipeline, Sensor
from monitoring.services import calculate_consumption_window, consumption_today, current_flow_rate
from notifications.models import Notification

# range → (lookback, trunc_fn or None for raw, max raw points, bucket label)
_RANGE_CFG = {
    "live": (timedelta(minutes=30), None, 180, "raw"),
    "day": (timedelta(days=1), TruncMinute, None, "5min"),
    "week": (timedelta(days=7), TruncHour, None, "hour"),
    "month": (timedelta(days=30), TruncDay, None, "day"),
}


def overview() -> dict:
    active_alerts = LeakEvent.objects.exclude(
        detection_status=LeakEvent.DetectionStatus.RESOLVED
    ).count()
    unread = Notification.objects.filter(is_read=False).count()
    total_devices = Device.objects.count()
    connected_devices = Device.objects.filter(
        connection_status=Device.ConnectionStatus.CONNECTED
    ).count()
    system_health = (
        "HEALTHY"
        if connected_devices == total_devices and active_alerts == 0
        else "DEGRADED"
    )
    return {
        "current_water_flow": {"value": current_flow_rate(), "unit": "L/min"},
        "todays_consumption": {"value": consumption_today(), "unit": "L"},
        "system_health": system_health,
        "active_alerts": active_alerts,
        "unread_notifications": unread,
        "devices": {"total": total_devices, "connected": connected_devices},
    }


def _downsample_minutes(points: list, every: int = 5) -> list:
    """Average points into every-N-minute buckets (day view)."""
    if every <= 1 or len(points) <= 400:
        return points
    buckets: dict = {}
    for p in points:
        ts = p["timestamp"]
        try:
            minute = int(ts[14:16])
        except (TypeError, ValueError, IndexError):
            minute = 0
        key = ts[:14] + f"{(minute // every) * every:02d}"
        b = buckets.setdefault(key, {"sum": 0.0, "n": 0, "timestamp": ts})
        b["sum"] += p["flow_rate"]
        b["n"] += 1
        b["timestamp"] = ts
    return [
        {"timestamp": b["timestamp"], "flow_rate": round(b["sum"] / b["n"], 4)}
        for _, b in sorted(buckets.items())
    ]


def flow_trend(
    hours: int | None = None,
    range_key: str = "day",
    sensor_id=None,
    as_list: bool = False,
):
    """
    Sensor flow trend for dashboard charts.

    range_key: live | day | week | month
    hours: legacy lookback in hours (used when provided without an explicit range)
    sensor_id: optional Sensor pk
    as_list: if True, return flat list (legacy SummaryView)
    """
    now = timezone.now()
    key = (range_key or "day").lower().strip()
    if key not in _RANGE_CFG:
        key = "day"

    # Legacy ?hours=N without range → treat as custom hour window
    if hours is not None and range_key in (None, "", "day") and int(hours) != 24:
        h = max(1, min(int(hours), 24 * 31))
        since = now - timedelta(hours=h)
        trunc = TruncHour if h > 6 else TruncMinute
        raw_cap = None
        bucket = "hour" if h > 6 else "minute"
        label = f"{h}h"
        use_live_raw = False
    else:
        delta, trunc, raw_cap, bucket = _RANGE_CFG[key]
        since = now - delta
        label = key
        use_live_raw = key == "live" or trunc is None

    qs = FlowReading.objects.filter(reading_timestamp__gte=since)
    if sensor_id:
        qs = qs.filter(sensor_id=sensor_id)

    sensor_ids = list(qs.values_list("sensor_id", flat=True).distinct())
    sensors = {
        s.id: s
        for s in Sensor.objects.filter(id__in=sensor_ids)
    }
    if not sensors and sensor_id:
        s = Sensor.objects.filter(pk=sensor_id).first()
        if s:
            sensors = {s.id: s}

    series = []
    flat_compat = []

    for sid, sensor in sorted(
        sensors.items(),
        key=lambda kv: (kv[1].sensor_position, kv[1].sensor_name),
    ):
        sensor_qs = qs.filter(sensor_id=sid)

        if use_live_raw:
            rows = list(
                sensor_qs.order_by("-reading_timestamp")[: (raw_cap or 180)]
            )
            rows.reverse()
            points = [
                {
                    "timestamp": r.reading_timestamp.isoformat(),
                    "flow_rate": float(r.flow_rate),
                }
                for r in rows
            ]
        else:
            aggregated = (
                sensor_qs.annotate(bucket=trunc("reading_timestamp"))
                .values("bucket")
                .annotate(avg_flow=Avg("flow_rate"), n=Count("id"))
                .order_by("bucket")
            )
            points = [
                {
                    "timestamp": row["bucket"].isoformat(),
                    "flow_rate": float(row["avg_flow"] or 0),
                }
                for row in aggregated
                if row["bucket"] is not None
            ]
            if key == "day" and trunc is TruncMinute:
                points = _downsample_minutes(points, every=5)

        series.append(
            {
                "sensor_id": sid,
                "sensor": sensor.sensor_identifier,
                "name": f"{sensor.sensor_name} ({sensor.sensor_position})",
                "position": sensor.sensor_position,
                "data": points,
            }
        )
        for p in points:
            flat_compat.append(
                {
                    "timestamp": p["timestamp"],
                    "flow_rate": p["flow_rate"],
                    "sensor": sid,
                    "sensor_name": sensor.sensor_identifier,
                    "position": sensor.sensor_position,
                }
            )

    flat_compat.sort(key=lambda r: r["timestamp"])

    if as_list:
        return flat_compat

    return {
        "range": label,
        "bucket": bucket,
        "from": since.isoformat(),
        "to": now.isoformat(),
        "series": series,
        "data": flat_compat,
        "count": len(flat_compat),
    }


def consumption_overview(days: int = 7) -> list:
    result = []
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    zero = __import__("decimal").Decimal("0")
    for i in range(days, 0, -1):
        start = today - timedelta(days=i)
        end = start + timedelta(days=1)
        total = sum(
            (
                calculate_consumption_window(p, start, end)
                for p in Pipeline.objects.all()
            ),
            start=zero,
        )
        result.append({"date": start.date().isoformat(), "consumption": float(total)})
    return result
