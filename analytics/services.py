from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Avg
from monitoring.models import FlowReading, Pipeline
from monitoring.services import calculate_consumption_window
from leak_detection.models import LeakEvent
from datetime import datetime, time

def _as_range(start_date, end_date):
    start = datetime.combine(start_date, time.min)
    end = datetime.combine(end_date, time.max)
    return timezone.make_aware(start), timezone.make_aware(end)

def analytics_summary(start_date, end_date):
    start, end = _as_range(start_date, end_date)
    total = Decimal("0")
    for p in Pipeline.objects.all():
        total += calculate_consumption_window(p, start, end)
    days = (end - start).days or 1
    average = total / Decimal(days)
    leaks = LeakEvent.objects.filter(started_at__range=(start, end)).count()
    return {
        "total_consumption": float(total),
        "average_daily_usage": float(average),
        "leak_events": leaks,
        "period": {"start": start_date, "end": end_date},
    }

def consumption_trends(start_date, end_date):
    from datetime import timedelta
    rows = []
    d = start_date
    while d <= end_date:
        start, end = _as_range(d, d)
        total = Decimal("0")
        for p in Pipeline.objects.all():
            total += calculate_consumption_window(p, start, end)
        rows.append({"date": d.isoformat(), "consumption": float(total)})
        d = d + timedelta(days=1)
    return rows

def usage_breakdown(start_date, end_date):
    start, end = _as_range(start_date, end_date)
    rows = []
    for p in Pipeline.objects.all():
        vol = calculate_consumption_window(p, start, end)
        rows.append({"pipeline_id": p.id, "pipeline": p.pipeline_name,
                     "consumption": float(vol)})
    return rows