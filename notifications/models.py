from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Notification(TimeStampedModel):
    class Type(models.TextChoices):
        LEAK_SUSPECTED = "LEAK_SUSPECTED", "Leak Suspected"
        LEAK_CONFIRMED = "LEAK_CONFIRMED", "Leak Confirmed"
        LEAK_RESOLVED = "LEAK_RESOLVED", "Leak Resolved"
        DEVICE_DISCONNECTED = "DEVICE_DISCONNECTED", "Device Disconnected"
        DEVICE_CONNECTED = "DEVICE_CONNECTED", "Device Connected"
        SENSOR_ERROR = "SENSOR_ERROR", "Sensor Error"
        ABNORMAL_FLOW = "ABNORMAL_FLOW", "Abnormal Flow"
        VALVE_STATUS_CHANGED = "VALVE_STATUS_CHANGED", "Valve Status Changed"
        HARDWARE_WARNING = "HARDWARE_WARNING", "Hardware Warning"
        SYSTEM = "SYSTEM", "System"
        PUBLIC_ANNOUNCEMENT = "PUBLIC_ANNOUNCEMENT", "Public Announcement"
        ADMIN_MESSAGE = "ADMIN_MESSAGE", "Admin Message"

    class Severity(models.TextChoices):
        INFO = "INFO", "Info"
        WARNING = "WARNING", "Warning"
        CRITICAL = "CRITICAL", "Critical"

    class Audience(models.TextChoices):
        INTERNAL = "INTERNAL", "Internal (operators)"
        PUBLIC = "PUBLIC", "Public website"

    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=40, choices=Type.choices)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)
    audience = models.CharField(
        max_length=12, choices=Audience.choices, default=Audience.INTERNAL, db_index=True
    )
    is_read = models.BooleanField(default=False, db_index=True)
    is_pinned = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications_created",
    )

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
