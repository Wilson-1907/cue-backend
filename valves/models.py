from django.db import models
from core.models import TimeStampedModel
from devices.models import Device
from monitoring.models import Pipeline
from django.conf import settings

class Valve(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"
        UNKNOWN = "UNKNOWN", "Unknown"

    class ControlMode(models.TextChoices):
        AUTOMATIC = "AUTOMATIC", "Automatic"
        MANUAL = "MANUAL", "Manual"

    valve_name = models.CharField(max_length=120)
    valve_identifier = models.CharField(max_length=64, unique=True)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="valves")
    pipeline = models.ForeignKey(Pipeline, on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="valves")
    current_status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNKNOWN)
    control_mode = models.CharField(max_length=20, choices=ControlMode.choices,
                                    default=ControlMode.MANUAL)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["valve_name"]

class ValveCommand(TimeStampedModel):
    class CommandType(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSE = "CLOSE", "Close"
        SET_MODE_AUTO = "AUTO", "Set Auto Mode"
        SET_MODE_MANUAL = "MANUAL", "Set Manual Mode"

    class ExecutionStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RECEIVED = "RECEIVED", "Received"
        EXECUTED = "EXECUTED", "Executed"
        FAILED = "FAILED", "Failed"
        EXPIRED = "EXPIRED", "Expired"

    valve = models.ForeignKey(Valve, on_delete=models.CASCADE, related_name="commands")
    command_type = models.CharField(max_length=10, choices=CommandType.choices)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True)
    execution_status = models.CharField(max_length=20, choices=ExecutionStatus.choices,
                                        default=ExecutionStatus.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    response_message = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        ordering = ["-requested_at"]