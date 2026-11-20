from django.contrib import admin
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "user", "device", "action", "category")
    list_filter = ("category", "created_at")
    search_fields = ("action", "description", "user__username", "device__device_name")
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        return False  # audit logs are append-only via services

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser