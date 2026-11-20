import pytest
from decimal import Decimal
from devices.models import Device
from monitoring.models import Pipeline, Sensor, FlowReading
from monitoring.services import current_flow_rate, consumption_today


@pytest.mark.django_db
def test_current_flow_rate_returns_latest():
    d = Device.objects.create(device_name="D", device_identifier="D-1")
    p = Pipeline.objects.create(pipeline_name="P", pipeline_code="PC-1")
    s = Sensor.objects.create(sensor_name="S", sensor_identifier="S-1",
                              device=d, sensor_position="INLET", pipeline=p)
    from django.utils import timezone
    FlowReading.objects.create(sensor=s, device=d, flow_rate=Decimal("5"),
                               volume=Decimal("10"), pulse_count=1, reading_timestamp=timezone.now())
    assert current_flow_rate(p) == Decimal("5.0000")


@pytest.mark.django_db
def test_consumption_today_no_data_is_zero():
    p = Pipeline.objects.create(pipeline_name="P", pipeline_code="PC-1")
    assert consumption_today(p) == Decimal("0")