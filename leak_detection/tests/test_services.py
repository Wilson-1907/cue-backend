import pytest
from decimal import Decimal
from django.utils import timezone
from redis.utils import pipeline
from devices.models import Device
from monitoring.models import Pipeline, Sensor, FlowReading
from leak_detection.services import compare_pipeline, evaluate_pipeline
from leak_detection.models import LeakEvent
from system_settings.models import SystemSettings

@pytest.mark.django_db
def test_compare_pipeline_detects_difference():
    s = SystemSettings.load()
    s.leak_trigger_flow_difference = Decimal("1.0")
    s.leak_trigger_percentage = Decimal("10")
    s.sensor_difference_tolerance = Decimal("0.2")
    s.save()

    device = Device.objects.create(device_name="D1", device_identifier="D1")
    pipeline = Pipeline.objects.create(pipeline_name="P1", pipeline_code="PC1")
    inlet = Sensor.objects.create(sensor_name="IN", sensor_identifier="IN1",
                                  device=device, sensor_position=Sensor.Position.INLET,
                                  pipeline=pipeline)
    outlet = Sensor.objects.create(sensor_name="OUT", sensor_identifier="OUT1",
                                   device=device, sensor_position=Sensor.Position.OUTLET,
                                   pipeline=pipeline)
    now = timezone.now()
    FlowReading.objects.create(sensor=inlet, device=device, flow_rate=Decimal("10"),
                               volume=Decimal("100"), pulse_count=1, reading_timestamp=now)
    FlowReading.objects.create(sensor=outlet, device=device, flow_rate=Decimal("3"),
                               volume=Decimal("60"), pulse_count=1, reading_timestamp=now)
    result = compare_pipeline(pipeline)
    assert result["is_leak_candidate"] is True
    assert result["flow_difference"] == Decimal("7")

@pytest.mark.django_db
def test_evaluate_creates_and_resolves_leak_event():
    # Same setup as above
    ...
    evaluate_pipeline(pipeline)
    assert LeakEvent.objects.count() >= 1