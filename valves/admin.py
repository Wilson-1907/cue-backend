from django.contrib import admin
from .models import Valve, ValveCommand


@admin.register(Valve)
class ValveAdmin(admin.ModelAdmin):
    list_display = ("id", "valve_name", "valve_identifier", "device",
                    "current_status", "control_mode", "last_updated")
    list_filter = ("current_status", "control_mode")
    search_fields = ("valve_name", "valve_identifier")


@admin.register(ValveCommand)
class ValveCommandAdmin(admin.ModelAdmin):
    list_display = ("id", "valve", "command_type", "execution_status",
                    "requested_by", "requested_at", "executed_at")
    list_filter = ("command_type", "execution_status")
    readonly_fields = ("requested_at", "acknowledged_at", "executed_at", "created_at", "updated_at")