import pytest
from decimal import Decimal
from django.utils import timezone
from devices.models import Device
from monitoring.models import Pipeline, Sensor, FlowReading
from leak_detection.services import compare_pipeline


@pytest.mark.django_db
def test_compare_pipeline_computes_difference():
    d = Device.objects.create(device_name="D", device_identifier="D-1")
    p = Pipeline.objects.create(pipeline_name="P", pipeline_code="PC-1")
    inlet = Sensor.objects.create(sensor_name="IN", sensor_identifier="IN-1",
                                  device=d, sensor_position="INLET", pipeline=p)
    outlet = Sensor.objects.create(sensor_name="OUT", sensor_identifier="OUT-1",
                                   device=d, sensor_position="OUTLET", pipeline=p)
    now = timezone.now()
    FlowReading.objects.create(sensor=inlet, device=d, flow_rate=Decimal("10"),
                               volume=Decimal("100"), pulse_count=1, reading_timestamp=now)
    FlowReading.objects.create(sensor=outlet, device=d, flow_rate=Decimal("3"),
                               volume=Decimal("60"), pulse_count=1, reading_timestamp=now)
    result = compare_pipeline(p)
    assert result["flow_difference"] == Decimal("7")
    assert result["is_leak_candidate"] is True