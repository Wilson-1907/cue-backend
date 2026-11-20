from decimal import Decimal

from rest_framework import serializers

from .models import FinanceEntry, FinanceSettings


class FinanceEntrySerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True, default="")

    class Meta:
        model = FinanceEntry
        fields = [
            "id",
            "entry_type",
            "category",
            "amount",
            "currency",
            "title",
            "notes",
            "source",
            "reference",
            "occurred_at",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "source", "created_by", "created_at", "updated_at"]


class FinanceEntryCreateSerializer(serializers.Serializer):
    entry_type = serializers.ChoiceField(choices=FinanceEntry.EntryType.choices)
    category = serializers.ChoiceField(choices=FinanceEntry.Category.choices, default=FinanceEntry.Category.OTHER)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"))
    title = serializers.CharField(max_length=200)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=120)
    occurred_at = serializers.DateTimeField(required=False)


class FinanceSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceSettings
        fields = [
            "currency",
            "sms_cost",
            "water_cost_per_liter",
            "maintenance_default_cost",
            "kit_unit_cost",
            "auto_record_sms",
            "auto_record_leak_loss",
            "auto_record_maintenance_hint",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]


class MaintenanceCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=120)
