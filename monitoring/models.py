from django.db import models
from core.models import TimeStampedModel
from devices.models import Device

class Pipeline(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        MAINTENANCE = "MAINTENANCE", "Maintenance"

    pipeline_name = models.CharField(max_length=120)
    pipeline_code = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True)
    length_meters = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pipe_diameter = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                        help_text="Diameter in mm")
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["pipeline_name"]

    def __str__(self):
        return f"{self.pipeline_name} ({self.pipeline_code})"

class Sensor(TimeStampedModel):
    class Type(models.TextChoices):
        FLOW = "FLOW", "Flow"
    class Position(models.TextChoices):
        INLET = "INLET", "Inlet"
        OUTLET = "OUTLET", "Outlet"
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        FAULTY = "FAULTY", "Faulty"

    sensor_name = models.CharField(max_length=120)
    sensor_identifier = models.CharField(max_length=64, unique=True)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="sensors")
    sensor_type = models.CharField(max_length=20, choices=Type.choices, default=Type.FLOW)
    sensor_position = models.CharField(max_length=10, choices=Position.choices)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="sensors")
    calibration_factor = models.DecimalField(max_digits=10, decimal_places=4, default=7.5,
                                             help_text="Pulses per litre factor")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    installation_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["sensor_name"]

    def __str__(self):
        return f"{self.sensor_name} [{self.sensor_identifier}]"

class PipelineSection(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name="sections")
    inlet_sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name="inlet_sections")
    outlet_sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name="outlet_sections")
    section_name = models.CharField(max_length=120)
    start_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    start_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    end_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    end_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    diagram_position = models.CharField(max_length=64, blank=True,
                                        help_text="Frontend SVG position identifier")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["pipeline", "section_name"]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.inlet_sensor_id == self.outlet_sensor_id:
            raise ValidationError("Inlet and outlet sensor must be different.")

class FlowReading(TimeStampedModel):
    sensor = models.ForeignKey(Sensor, on_delete=models.CASCADE, related_name="readings")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="readings")
    flow_rate = models.DecimalField(max_digits=12, decimal_places=4,
                                    help_text="Litres per minute")
    volume = models.DecimalField(max_digits=16, decimal_places=4,
                                 help_text="Cumulative volume in litres")
    pulse_count = models.BigIntegerField(default=0)
    reading_timestamp = models.DateTimeField(db_index=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-reading_timestamp"]
        indexes = [
            models.Index(fields=["sensor", "-reading_timestamp"]),
            models.Index(fields=["device", "-reading_timestamp"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["sensor", "reading_timestamp", "pulse_count"],
                name="uniq_sensor_reading_idempotency",
            ),
        ]

class Consumption(TimeStampedModel):
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name="consumption")
    consumption_volume = models.DecimalField(max_digits=16, decimal_places=4)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    source = models.CharField(max_length=40, default="CALCULATED")

    class Meta:
        ordering = ["-period_end"]
        indexes = [models.Index(fields=["pipeline", "-period_end"])]