from django.conf import settings
from django.db import models
from core.models import TimeStampedModel
from devices.models import Device

class ActivityLog(TimeStampedModel):
    class Category(models.TextChoices):
        AUTH = "AUTH", "Authentication"
        VALVE = "VALVE", "Valve"
        SETTINGS = "SETTINGS", "Settings"
        DEVICE = "DEVICE", "Device"
        SENSOR = "SENSOR", "Sensor"
        LEAK = "LEAK", "Leak"
        SYSTEM = "SYSTEM", "System"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="activity_logs")
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="activity_logs")
    action = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.SYSTEM)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]