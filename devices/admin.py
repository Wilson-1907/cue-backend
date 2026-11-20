from django.contrib import admin
from .models import Device, DeviceCommunicationLog


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "device_name", "device_identifier", "device_type",
                    "connection_status", "is_active", "last_communication")
    list_filter = ("connection_status", "device_type", "is_active")
    search_fields = ("device_name", "device_identifier", "location")
    readonly_fields = ("api_key_hash", "api_key_prefix", "created_at", "updated_at")


@admin.register(DeviceCommunicationLog)
class DeviceCommunicationLogAdmin(admin.ModelAdmin):
    list_display = ("id", "device", "kind", "success", "created_at")
    list_filter = ("kind", "success")
    search_fields = ("device__device_identifier",)