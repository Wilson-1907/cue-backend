import pytest
from devices.models import Device


@pytest.mark.django_db
def test_device_api_key_roundtrip():
    d = Device.objects.create(device_name="D", device_identifier="DEV-1")
    raw = Device.generate_api_key()
    d.set_api_key(raw)
    d.refresh_from_db()
    from django.contrib.auth.hashers import check_password
    assert check_password(raw, d.api_key_hash)