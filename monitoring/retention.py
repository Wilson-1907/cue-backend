"""
Keep the free-tier DB small: recent readings for live graphs, then delete.

When water is flowing, store frequently so KPIs are never frozen.
When quiet (~0), store rarely to save space.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

log = logging.getLogger("cue.retention")

_last_prune_at = None


def retention_minutes() -> int:
    return max(1, int(getattr(settings, "TELEMETRY_RETENTION_MINUTES", 15)))


def max_readings() -> int:
    return max(100, int(getattr(settings, "TELEMETRY_MAX_READINGS", 2000)))


def should_store_reading(sensor, flow_rate, volume) -> bool:
    """Store often while flowing; throttle only when both samples are ~0."""
    from monitoring.models import FlowReading

    if not getattr(settings, "TELEMETRY_SKIP_DUPES", True):
        return True

    last = (
        FlowReading.objects.filter(sensor=sensor)
        .order_by("-reading_timestamp")
        .only("flow_rate", "volume", "reading_timestamp")
        .first()
    )
    if not last:
        return True

    age = (timezone.now() - last.reading_timestamp).total_seconds()
    flow = Decimal(str(flow_rate))
    last_flow = last.flow_rate or Decimal("0")

    # Flowing (now or previously): sample every ~2s so live KPIs move
    flowing_gap = int(getattr(settings, "TELEMETRY_FLOWING_SAMPLE_SECONDS", 2))
    if flow >= Decimal("0.05") or last_flow >= Decimal("0.05"):
        return age >= flowing_gap

    # Quiet line: at most one sample per 60s
    return age >= 60


def prune_telemetry(force: bool = False) -> dict:
    """Delete expired telemetry. Safe to call often; rate-limited unless force."""
    global _last_prune_at
    from monitoring.models import FlowReading, Consumption
    from devices.models import DeviceCommunicationLog
    from activity_logs.models import ActivityLog

    now = timezone.now()
    interval = int(getattr(settings, "TELEMETRY_PRUNE_EVERY_SECONDS", 60))
    if (
        not force
        and _last_prune_at is not None
        and (now - _last_prune_at).total_seconds() < interval
    ):
        return {"skipped": True}

    cutoff = now - timedelta(minutes=retention_minutes())
    deleted = {}

    with transaction.atomic():
        deleted["flow_readings_by_age"], _ = FlowReading.objects.filter(
            reading_timestamp__lt=cutoff
        ).delete()

        ids = list(
            FlowReading.objects.order_by("-reading_timestamp").values_list("id", flat=True)[
                : max_readings()
            ]
        )
        if ids:
            deleted["flow_readings_over_cap"], _ = FlowReading.objects.exclude(
                id__in=ids
            ).delete()
        else:
            deleted["flow_readings_over_cap"] = 0

        deleted["comm_logs"], _ = DeviceCommunicationLog.objects.filter(
            created_at__lt=cutoff
        ).delete()
        deleted["activity_logs"], _ = ActivityLog.objects.filter(
            created_at__lt=cutoff
        ).delete()
        cons_cutoff = now - timedelta(days=7)
        deleted["consumption"], _ = Consumption.objects.filter(
            period_end__lt=cons_cutoff
        ).delete()

    _last_prune_at = now
    log.info("prune_telemetry %s", deleted)
    return deleted


def wipe_telemetry() -> dict:
    """Delete all telemetry tables; keep accounts/devices/sensors/config."""
    from monitoring.models import FlowReading, Consumption
    from devices.models import DeviceCommunicationLog
    from activity_logs.models import ActivityLog

    out = {}
    with transaction.atomic():
        out["flow_readings"], _ = FlowReading.objects.all().delete()
        out["consumption"], _ = Consumption.objects.all().delete()
        out["comm_logs"], _ = DeviceCommunicationLog.objects.all().delete()
        out["activity_logs"], _ = ActivityLog.objects.all().delete()
    log.warning("wipe_telemetry %s", out)
    return out
