"""
Keep the free-tier DB small: only recent readings for live graphs, then delete.

Preserves users, devices, sensors, pipelines, valves, settings.
Prunes FlowReading, DeviceCommunicationLog, ActivityLog, old Consumption rows.
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
    """Skip near-duplicate quiet readings so we only store what graphs need."""
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
    # Always keep a sample at least every N seconds for a smooth live chart
    min_gap = int(getattr(settings, "TELEMETRY_MIN_SAMPLE_SECONDS", 5))
    if age < min_gap:
        return False

    flow = Decimal(str(flow_rate))
    vol = Decimal(str(volume))
    flow_delta = abs((last.flow_rate or Decimal("0")) - flow)
    vol_delta = abs((last.volume or Decimal("0")) - vol)

    # Quiet line (both ~0): keep at most one sample per 60s
    if flow < Decimal("0.05") and (last.flow_rate or Decimal("0")) < Decimal("0.05"):
        return age >= 60

    # Meaningful change → store
    if flow_delta >= Decimal("0.15") or vol_delta >= Decimal("0.05"):
        return True

    # Unchanged flow: sample every 15s max
    return age >= 15


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

        # Hard cap: keep newest N rows even inside the window
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
        # Keep at most 7 days of consumption summaries
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
