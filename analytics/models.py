from django.conf import settings
from django.db import models
from core.models import TimeStampedModel


class Report(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=40)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_reports",   # <-- explicit reverse name
    )
    file = models.FileField(upload_to="reports/", null=True, blank=True)
    summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title