from django.contrib import admin
from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "report_type", "status", "start_date", "end_date", "generated_by")
    list_filter = ("status", "report_type")
    search_fields = ("title",)
    readonly_fields = ("created_at", "updated_at")