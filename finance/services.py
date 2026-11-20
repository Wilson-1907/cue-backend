"""Private finance helpers — automatic expenditure + reports (staff only)."""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import FinanceEntry, FinanceSettings

logger = logging.getLogger(__name__)


def _dec(v, default="0") -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(default)


def record_entry(
    *,
    entry_type: str,
    category: str,
    amount,
    title: str,
    notes: str = "",
    source: str = FinanceEntry.Source.MANUAL,
    unique_key: str = "",
    reference: str = "",
    occurred_at=None,
    user=None,
    currency: str | None = None,
) -> FinanceEntry | None:
    """Create a finance row. AUTO rows with unique_key are idempotent."""
    amt = _dec(amount)
    if amt < 0:
        amt = abs(amt)
    if amt == 0 and source == FinanceEntry.Source.AUTO:
        return None

    settings = FinanceSettings.load()
    cur = currency or settings.currency or "KES"
    when = occurred_at or timezone.now()
    key = (unique_key or "").strip()

    if key and source == FinanceEntry.Source.AUTO:
        existing = FinanceEntry.objects.filter(unique_key=key).first()
        if existing:
            return existing

    try:
        return FinanceEntry.objects.create(
            entry_type=entry_type,
            category=category,
            amount=amt,
            currency=cur,
            title=(title or "Entry")[:200],
            notes=notes or "",
            source=source,
            unique_key=key,
            reference=(reference or "")[:120],
            occurred_at=when,
            created_by=user,
        )
    except Exception:
        logger.exception("Failed to record finance entry key=%s", key)
        if key:
            return FinanceEntry.objects.filter(unique_key=key).first()
        return None


def record_sms_cost(*, mobile: str, leak_event_id: int | None = None, ok: bool = True) -> FinanceEntry | None:
    if not ok:
        return None
    settings = FinanceSettings.load()
    if not settings.auto_record_sms:
        return None
    ref = f"leak:{leak_event_id}" if leak_event_id else "sms"
    key = f"sms:{ref}:{mobile}"
    return record_entry(
        entry_type=FinanceEntry.EntryType.EXPENSE,
        category=FinanceEntry.Category.SMS_ALERT,
        amount=settings.sms_cost,
        title=f"SMS alert to {mobile}",
        notes="Auto-recorded from TextSMS delivery",
        source=FinanceEntry.Source.AUTO,
        unique_key=key,
        reference=ref,
    )


def record_leak_water_loss(event) -> FinanceEntry | None:
    """Estimate water lost from confirmed leak and record expense."""
    settings = FinanceSettings.load()
    if not settings.auto_record_leak_loss:
        return None
    try:
        diff = abs(float(event.flow_difference or 0))  # L/min
    except Exception:
        return None
    if diff <= 0:
        return None

    started = event.started_at or timezone.now()
    ended = event.resolved_at or timezone.now()
    minutes = max((ended - started).total_seconds() / 60.0, 1.0)
    # Cap runaway estimates at 24h of continuous loss for a single event row
    minutes = min(minutes, 24 * 60)
    liters = Decimal(str(round(diff * minutes, 2)))
    amount = (liters * settings.water_cost_per_liter).quantize(Decimal("0.01"))
    key = f"waterloss:leak:{event.id}"
    return record_entry(
        entry_type=FinanceEntry.EntryType.EXPENSE,
        category=FinanceEntry.Category.WATER_LOSS,
        amount=amount,
        title=f"Water loss — {getattr(event.pipeline, 'pipeline_name', 'pipeline')}",
        notes=(
            f"Auto estimate: ~{liters} L lost "
            f"(Δflow {diff:.2f} L/min × {minutes:.1f} min @ {settings.water_cost_per_liter} KES/L)"
        ),
        source=FinanceEntry.Source.AUTO,
        unique_key=key,
        reference=f"leak:{event.id}",
        occurred_at=ended,
    )


def record_maintenance(
    *,
    title: str,
    amount=None,
    notes: str = "",
    user=None,
    reference: str = "",
) -> FinanceEntry | None:
    settings = FinanceSettings.load()
    amt = amount if amount is not None else settings.maintenance_default_cost
    return record_entry(
        entry_type=FinanceEntry.EntryType.EXPENSE,
        category=FinanceEntry.Category.MAINTENANCE,
        amount=amt,
        title=title or "Maintenance",
        notes=notes,
        source=FinanceEntry.Source.MANUAL,
        reference=reference,
        user=user,
    )


def ensure_kit_baseline() -> FinanceEntry | None:
    """One-time hardware kit cost so reports aren't empty on first use."""
    settings = FinanceSettings.load()
    return record_entry(
        entry_type=FinanceEntry.EntryType.EXPENSE,
        category=FinanceEntry.Category.HARDWARE,
        amount=settings.kit_unit_cost,
        title="CUE monitoring kit (baseline)",
        notes="Auto baseline hardware cost for single-pipeline kit",
        source=FinanceEntry.Source.AUTO,
        unique_key="hardware:kit:baseline",
        reference="kit",
    )


def summary(days: int = 30) -> dict[str, Any]:
    ensure_kit_baseline()
    settings = FinanceSettings.load()
    since = timezone.now() - timedelta(days=max(1, int(days)))
    qs = FinanceEntry.objects.filter(occurred_at__gte=since)

    income = qs.filter(entry_type=FinanceEntry.EntryType.INCOME).aggregate(t=Sum("amount"))["t"] or Decimal("0")
    expense = qs.filter(entry_type=FinanceEntry.EntryType.EXPENSE).aggregate(t=Sum("amount"))["t"] or Decimal("0")
    auto_exp = (
        qs.filter(entry_type=FinanceEntry.EntryType.EXPENSE, source=FinanceEntry.Source.AUTO).aggregate(
            t=Sum("amount")
        )["t"]
        or Decimal("0")
    )
    manual_exp = (
        qs.filter(entry_type=FinanceEntry.EntryType.EXPENSE, source=FinanceEntry.Source.MANUAL).aggregate(
            t=Sum("amount")
        )["t"]
        or Decimal("0")
    )

    by_cat = list(
        qs.filter(entry_type=FinanceEntry.EntryType.EXPENSE)
        .values("category")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    monthly = list(
        FinanceEntry.objects.filter(occurred_at__gte=timezone.now() - timedelta(days=365))
        .annotate(month=TruncMonth("occurred_at"))
        .values("month", "entry_type")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    recent = list(
        qs.order_by("-occurred_at")[:25].values(
            "id",
            "entry_type",
            "category",
            "amount",
            "currency",
            "title",
            "source",
            "reference",
            "occurred_at",
            "notes",
        )
    )

    return {
        "currency": settings.currency,
        "period_days": days,
        "income": float(income),
        "expense": float(expense),
        "net": float(income - expense),
        "auto_expense": float(auto_exp),
        "manual_expense": float(manual_exp),
        "by_category": [
            {"category": r["category"], "total": float(r["total"] or 0), "count": r["count"]}
            for r in by_cat
        ],
        "monthly": [
            {
                "month": r["month"].date().isoformat() if r["month"] else None,
                "entry_type": r["entry_type"],
                "total": float(r["total"] or 0),
            }
            for r in monthly
        ],
        "recent": [
            {
                **row,
                "amount": float(row["amount"]),
                "occurred_at": row["occurred_at"].isoformat() if row["occurred_at"] else None,
            }
            for row in recent
        ],
        "settings": {
            "sms_cost": float(settings.sms_cost),
            "water_cost_per_liter": float(settings.water_cost_per_liter),
            "maintenance_default_cost": float(settings.maintenance_default_cost),
            "kit_unit_cost": float(settings.kit_unit_cost),
            "auto_record_sms": settings.auto_record_sms,
            "auto_record_leak_loss": settings.auto_record_leak_loss,
        },
        "tips": [
            "SMS alerts and estimated leak water-loss are recorded automatically.",
            "Log maintenance after repairs so the report stays complete.",
            "Adjust unit costs in Finance settings — the system uses them for auto entries.",
        ],
    }
