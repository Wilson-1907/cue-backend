from django.contrib import admin
from .models import SystemSettings


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "id", "normal_flow_rate_threshold", "leak_trigger_flow_difference",
        "leak_trigger_percentage", "automatic_leak_detection",
        "automatic_valve_shutdown", "device_heartbeat_timeout",
    )

    def has_add_permission(self, request):
        # singleton — already created by .load()
        return not SystemSettings.objects.exists()