from rest_framework import serializers
from devices.models import Device

class ReadingIngestSerializer(serializers.Serializer):
    device_id = serializers.CharField()
    sensor_id = serializers.CharField()
    flow_rate = serializers.DecimalField(max_digits=12, decimal_places=4)
    volume = serializers.DecimalField(max_digits=16, decimal_places=4)
    pulse_count = serializers.IntegerField(default=0)
    timestamp = serializers.DateTimeField()

class BulkReadingsSerializer(serializers.Serializer):
    readings = ReadingIngestSerializer(many=True)

class HeartbeatSerializer(serializers.Serializer):
    device_id = serializers.CharField()
    status = serializers.CharField(required=False, default="OK")
    firmware_version = serializers.CharField(required=False, allow_blank=True)

class DeviceRegisterSerializer(serializers.Serializer):
    device_name = serializers.CharField()
    device_identifier = serializers.CharField()
    device_type = serializers.CharField(default="ARDUINO_ESP")
    location = serializers.CharField(required=False, allow_blank=True)
    firmware_version = serializers.CharField(required=False, allow_blank=True)

class DeviceStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    note = serializers.CharField(required=False, allow_blank=True)

class DeviceWarningSerializer(serializers.Serializer):
    title = serializers.CharField()
    message = serializers.CharField()
    severity = serializers.CharField(default="WARNING")

class ValveStatusReportSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["OPEN", "CLOSED", "UNKNOWN"])
    message = serializers.CharField(required=False, allow_blank=True)