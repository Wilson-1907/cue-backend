from rest_framework import serializers
from .models import Device, DeviceCommunicationLog

class DeviceSerializer(serializers.ModelSerializer):
    sensors = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = ["id", "device_name", "device_identifier", "device_type", "location",
                  "firmware_version", "connection_status", "last_communication",
                  "is_active", "created_at", "sensors"]
        read_only_fields = ["id", "created_at", "connection_status", "last_communication"]

    def get_sensors(self, obj):
        from monitoring.serializers import SensorBriefSerializer
        return SensorBriefSerializer(obj.sensors.all(), many=True).data

class DeviceCommunicationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceCommunicationLog
        fields = "__all__"

class DeviceRegisterResponseSerializer(serializers.Serializer):
    device_id = serializers.IntegerField()
    device_identifier = serializers.CharField()
    api_key = serializers.CharField()