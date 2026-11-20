import pytest
from rest_framework.test import APIClient
from devices.models import Device
from monitoring.models import Pipeline, Sensor


@pytest.mark.django_db
def test_device_registration_and_reading_ingestion():
    client = APIClient()
    resp = client.post("/api/v1/iot/devices/register/", {
        "device_name": "Arduino",
        "device_identifier": "ARDUINO_TEST",
    }, format="json")
    assert resp.status_code == 201, resp.json()
    data = resp.json()["data"]
    api_key = data["api_key"]

    device = Device.objects.get(device_identifier="ARDUINO_TEST")
    pipeline = Pipeline.objects.create(pipeline_name="P", pipeline_code="PC")
    Sensor.objects.create(sensor_name="In", sensor_identifier="IN1",
                          device=device, sensor_position="INLET", pipeline=pipeline)

    resp = client.post(
        "/api/v1/iot/readings/",
        {
            "device_id": "ARDUINO_TEST",
            "sensor_id": "IN1",
            "flow_rate": "10.0",
            "volume": "100.0",
            "pulse_count": 1,
            "timestamp": "2026-01-01T00:00:00Z",
        },
        format="json",
        HTTP_X_DEVICE_ID="ARDUINO_TEST",
        HTTP_X_API_KEY=api_key,
    )
    assert resp.status_code == 201, resp.json()


@pytest.mark.django_db
def test_reading_without_device_key_is_401():
    client = APIClient()
    resp = client.post("/api/v1/iot/readings/", {}, format="json")
    assert resp.status_code == 401