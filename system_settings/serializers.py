from rest_framework import serializers
from .models import SystemSettings

class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        exclude = ["created_at", "updated_at"]