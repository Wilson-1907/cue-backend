from rest_framework import serializers
from .models import ActivityLog

class ActivityLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    device_name = serializers.CharField(source="device.device_name", read_only=True)

    class Meta:
        model = ActivityLog
        fields = ["id", "user", "username", "device", "device_name", "action",
                  "description", "category", "ip_address", "created_at"]