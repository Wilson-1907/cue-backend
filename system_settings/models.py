from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel

class SystemSettings(TimeStampedModel):
    """Singleton-style settings (use .load())."""
    normal_flow_rate_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=30,
        validators=[MinValueValidator(0)])
    leak_trigger_flow_difference = models.DecimalField(max_digits=10, decimal_places=2, default=1.5,
        validators=[MinValueValidator(0)])
    leak_trigger_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=15,
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    leak_detection_duration = models.IntegerField(default=30,
        help_text="Seconds abnormal condition must persist",
        validators=[MinValueValidator(5)])
    maximum_flow_rate = models.DecimalField(max_digits=10, decimal_places=2, default=100,
        validators=[MinValueValidator(0)])
    sensor_difference_tolerance = models.DecimalField(max_digits=10, decimal_places=2, default=0.5,
        validators=[MinValueValidator(0)])
    automatic_valve_shutdown = models.BooleanField(default=False)
    automatic_leak_detection = models.BooleanField(default=True)
    device_heartbeat_timeout = models.IntegerField(default=120,
        validators=[MinValueValidator(10)])

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj