from django.contrib import admin
from .models import LeakEvent


@admin.register(LeakEvent)
class LeakEventAdmin(admin.ModelAdmin):
    list_display = ("id", "pipeline", "detection_status", "severity",
                    "flow_difference", "started_at", "resolved_at")
    list_filter = ("detection_status", "severity")
    search_fields = ("pipeline__pipeline_name", "description")
    readonly_fields = ("created_at", "updated_at")