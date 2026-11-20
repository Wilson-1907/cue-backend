import secrets
from django.db import models
from core.models import TimeStampedModel

class Device(TimeStampedModel):
    class DeviceType(models.TextChoices):
        ARDUINO_ESP = "ARDUINO_ESP", "Arduino + ESP8266"
        OTHER = "OTHER", "Other"

    class ConnectionStatus(models.TextChoices):
        CONNECTED = "CONNECTED", "Connected"
        DISCONNECTED = "DISCONNECTED", "Disconnected"
        UNKNOWN = "UNKNOWN", "Unknown"

    device_name = models.CharField(max_length=120)
    device_identifier = models.CharField(max_length=64, unique=True)
    device_type = models.CharField(max_length=32, choices=DeviceType.choices,
                                   default=DeviceType.ARDUINO_ESP)
    location = models.CharField(max_length=200, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    connection_status = models.CharField(max_length=20, choices=ConnectionStatus.choices,
                                         default=ConnectionStatus.UNKNOWN)
    last_communication = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    api_key_hash = models.CharField(max_length=128, blank=True)  # hashed device secret
    api_key_prefix = models.CharField(max_length=12, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.device_name} ({self.device_identifier})"

    def mark_connected(self):
        from django.utils import timezone
        self.connection_status = self.ConnectionStatus.CONNECTED
        self.last_communication = timezone.now()
        self.save(update_fields=["connection_status", "last_communication", "updated_at"])

    def set_api_key(self, raw_key: str):
        from django.contrib.auth.hashers import make_password
        self.api_key_hash = make_password(raw_key)
        self.api_key_prefix = raw_key[:8]
        self.save(update_fields=["api_key_hash", "api_key_prefix", "updated_at"])

    @staticmethod
    def generate_api_key():
        return secrets.token_urlsafe(32)

class DeviceCommunicationLog(TimeStampedModel):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="communications")
    kind = models.CharField(max_length=40)
    payload = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=True)
    note = models.TextField(blank=True)