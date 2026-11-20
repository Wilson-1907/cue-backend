from django.contrib.auth.hashers import check_password
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from devices.models import Device

class DevicePrincipal:
    """Lightweight principal representing a device."""
    is_authenticated = True
    is_anonymous = False
    role = "DEVICE"

    def __init__(self, device: Device):
        self.device = device
        self.id = device.id
        self.username = device.device_identifier

class DeviceAuthentication(BaseAuthentication):
    """Header: X-Device-Id + X-Api-Key."""
    keyword = "X-Api-Key"

    def authenticate(self, request):
        device_id = request.META.get("HTTP_X_DEVICE_ID")
        api_key = request.META.get("HTTP_X_API_KEY")
        if not device_id or not api_key:
            return None
        try:
            device = Device.objects.get(device_identifier=device_id, is_active=True)
        except Device.DoesNotExist:
            raise AuthenticationFailed("Unknown device")
        if not device.api_key_hash or not check_password(api_key, device.api_key_hash):
            raise AuthenticationFailed("Invalid device key")
        return (DevicePrincipal(device), None)