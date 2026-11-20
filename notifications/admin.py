from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "title",
        "audience",
        "notification_type",
        "severity",
        "is_pinned",
        "is_active",
        "is_read",
    )
    list_filter = ("audience", "notification_type", "severity", "is_read", "is_active", "is_pinned")
    search_fields = ("title", "message")
    readonly_fields = ("created_at", "updated_at")
