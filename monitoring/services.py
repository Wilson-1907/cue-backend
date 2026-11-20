from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Max
from .models import FlowReading, Consumption, Sensor, Pipeline

def latest_reading_for_sensor(sensor: Sensor):
    return FlowReading.objects.filter(sensor=sensor).order_by("-reading_timestamp").first()

def consumption_today(pipeline: Pipeline | None = None) -> Decimal:
    """Compute today's consumption.

    Uses the OUTLET sensor cumulative volume delta as the authoritative
    consumption for the pipeline. Falls back to INLET if no outlet sensor.
    """
    sensors_qs = Sensor.objects.all()
    if pipeline:
        sensors_qs = sensors_qs.filter(pipeline=pipeline)
    outlet = sensors_qs.filter(sensor_position=Sensor.Position.OUTLET).first()
    sensor = outlet or sensors_qs.filter(sensor_position=Sensor.Position.INLET).first()
    if not sensor:
        return Decimal("0")

    now = timezone.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last = latest_reading_for_sensor(sensor)
    first = (FlowReading.objects
             .filter(sensor=sensor, reading_timestamp__gte=start)
             .order_by("reading_timestamp")
             .first())
    if not first or not last:
        return Decimal("0")
    return max(Decimal("0"), (last.volume or Decimal("0")) - (first.volume or Decimal("0")))

def current_flow_rate(pipeline: Pipeline | None = None) -> Decimal:
    qs = FlowReading.objects.all()
    if pipeline:
        qs = qs.filter(sensor__pipeline=pipeline)
    latest = qs.order_by("-reading_timestamp").first()
    return latest.flow_rate if latest else Decimal("0")

def calculate_consumption_window(pipeline: Pipeline, start, end) -> Decimal:
    sensor = Sensor.objects.filter(pipeline=pipeline,
                                   sensor_position=Sensor.Position.OUTLET).first()
    if not sensor:
        sensor = Sensor.objects.filter(pipeline=pipeline).first()
    if not sensor:
        return Decimal("0")
    qs = FlowReading.objects.filter(sensor=sensor,
                                    reading_timestamp__gte=start,
                                    reading_timestamp__lte=end).order_by("reading_timestamp")
    first = qs.first()
    last = qs.last()
    if not first or not last or first.pk == last.pk:
        return Decimal("0")
    return max(Decimal("0"), last.volume - first.volume)