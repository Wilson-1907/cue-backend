from django.db import models
from core.models import TimeStampedModel
from monitoring.models import Pipeline, Sensor

class LeakEvent(TimeStampedModel):
    class DetectionStatus(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        SUSPECTED = "SUSPECTED", "Suspected"
        CONFIRMED = "CONFIRMED", "Confirmed"
        RESOLVED = "RESOLVED", "Resolved"

    class Severity(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name="leak_events")
    inlet_sensor = models.ForeignKey(Sensor, on_delete=models.SET_NULL, null=True,
                                     related_name="inlet_leak_events")
    outlet_sensor = models.ForeignKey(Sensor, on_delete=models.SET_NULL, null=True,
                                      related_name="outlet_leak_events")
    inlet_flow_rate = models.DecimalField(max_digits=12, decimal_places=4)
    outlet_flow_rate = models.DecimalField(max_digits=12, decimal_places=4)
    flow_difference = models.DecimalField(max_digits=12, decimal_places=4)
    difference_percentage = models.DecimalField(max_digits=7, decimal_places=2)
    detection_status = models.CharField(max_length=20, choices=DetectionStatus.choices,
                                        default=DetectionStatus.SUSPECTED)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MEDIUM)
    started_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    # Firmware / locus pin
    estimate_from_s1_m = models.FloatField(null=True, blank=True)
    estimate_from_s2_m = models.FloatField(null=True, blank=True)
    estimate_severity_pct = models.FloatField(null=True, blank=True)
    estimate_summary = models.CharField(max_length=255, blank=True, default="")
    raw_alert_line = models.CharField(max_length=255, blank=True, default="")
    # TextSMS delivery
    sms_sent = models.BooleanField(default=False)
    sms_response = models.TextField(blank=True, default="")
    sms_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["pipeline", "-started_at"])]