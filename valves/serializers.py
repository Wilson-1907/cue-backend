from rest_framework import serializers

from .models import Valve, ValveCommand


class ValveSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.device_name", read_only=True, default="")
    device_identifier = serializers.CharField(
        source="device.device_identifier", read_only=True, default=""
    )
    connection_status = serializers.CharField(
        source="device.connection_status", read_only=True, default="UNKNOWN"
    )
    device_last_communication = serializers.DateTimeField(
        source="device.last_communication", read_only=True, default=None
    )
    device_is_active = serializers.BooleanField(source="device.is_active", read_only=True, default=False)
    device_location = serializers.CharField(source="device.location", read_only=True, default="")

    class Meta:
        model = Valve
        fields = [
            "id",
            "valve_name",
            "valve_identifier",
            "device",
            "device_name",
            "device_identifier",
            "connection_status",
            "device_last_communication",
            "device_is_active",
            "device_location",
            "pipeline",
            "current_status",
            "control_mode",
            "last_updated",
        ]
        read_only_fields = ["current_status", "last_updated"]

class ValveCommandSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)

    class Meta:
        model = ValveCommand
        fields = "__all__"