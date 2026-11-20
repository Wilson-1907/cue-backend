from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator

from core.models import TimeStampedModel


class FinanceSettings(TimeStampedModel):
    """Singleton cost rates used for automatic expenditure."""

    currency = models.CharField(max_length=8, default="KES")
    sms_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=1.00,
        validators=[MinValueValidator(0)],
        help_text="Cost per SMS alert (KES)",
    )
    water_cost_per_liter = models.DecimalField(
        max_digits=10, decimal_places=4, default=0.15,
        validators=[MinValueValidator(0)],
        help_text="Estimated water tariff used for leak loss (KES/L)",
    )
    maintenance_default_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=500.00,
        validators=[MinValueValidator(0)],
    )
    kit_unit_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=8180.00,
        validators=[MinValueValidator(0)],
        help_text="Default hardware kit cost (KES)",
    )
    auto_record_sms = models.BooleanField(default=True)
    auto_record_leak_loss = models.BooleanField(default=True)
    auto_record_maintenance_hint = models.BooleanField(default=True)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class FinanceEntry(TimeStampedModel):
    class EntryType(models.TextChoices):
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"

    class Category(models.TextChoices):
        SMS_ALERT = "SMS_ALERT", "SMS alerts"
        WATER_LOSS = "WATER_LOSS", "Water loss (leaks)"
        HARDWARE = "HARDWARE", "Hardware / kit"
        MAINTENANCE = "MAINTENANCE", "Maintenance & repairs"
        CLOUD = "CLOUD", "Cloud / connectivity"
        SERVICE = "SERVICE", "Service / installation"
        GRANT = "GRANT", "Grant / funding"
        OTHER = "OTHER", "Other"

    class Source(models.TextChoices):
        AUTO = "AUTO", "Automatic"
        MANUAL = "MANUAL", "Manual"

    entry_type = models.CharField(max_length=12, choices=EntryType.choices)
    category = models.CharField(max_length=24, choices=Category.choices, default=Category.OTHER)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=8, default="KES")
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True, default="")
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.MANUAL)
    # Idempotency for automatic rows (e.g. sms:leak:12:2547…)
    unique_key = models.CharField(max_length=120, blank=True, default="", db_index=True)
    reference = models.CharField(max_length=120, blank=True, default="")
    occurred_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="finance_entries",
    )

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["unique_key"],
                condition=~models.Q(unique_key=""),
                name="finance_entry_unique_key_nonempty",
            )
        ]

    def __str__(self):
        return f"{self.entry_type} {self.amount} {self.currency} — {self.title}"
