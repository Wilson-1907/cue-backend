from django.contrib import admin

from .models import FinanceEntry, FinanceSettings


@admin.register(FinanceSettings)
class FinanceSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "currency",
        "sms_cost",
        "water_cost_per_liter",
        "kit_unit_cost",
        "auto_record_sms",
        "auto_record_leak_loss",
    )


@admin.register(FinanceEntry)
class FinanceEntryAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_at",
        "entry_type",
        "category",
        "amount",
        "currency",
        "title",
        "source",
        "reference",
    )
    list_filter = ("entry_type", "category", "source")
    search_fields = ("title", "notes", "reference", "unique_key")
    readonly_fields = ("unique_key", "created_at", "updated_at")
