from rest_framework import serializers
from .models import Pipeline, Sensor, PipelineSection, FlowReading, Consumption

class SensorBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = ["id", "sensor_name", "sensor_identifier", "sensor_position", "status"]

class SensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor
        fields = ["id", "sensor_name", "sensor_identifier", "device", "sensor_type",
                  "sensor_position", "pipeline", "calibration_factor", "status",
                  "installation_date", "created_at"]
        read_only_fields = ["id", "created_at"]

class PipelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pipeline
        fields = "__all__"

class PipelineSectionSerializer(serializers.ModelSerializer):
    inlet_sensor_detail = SensorBriefSerializer(source="inlet_sensor", read_only=True)
    outlet_sensor_detail = SensorBriefSerializer(source="outlet_sensor", read_only=True)

    class Meta:
        model = PipelineSection
        fields = "__all__"

class FlowReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowReading
        fields = "__all__"

class ConsumptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consumption
        fields = "__all__"