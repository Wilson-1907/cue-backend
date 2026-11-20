from django.contrib import admin
from .models import Pipeline, Sensor, PipelineSection, FlowReading, Consumption


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ("id", "pipeline_name", "pipeline_code", "status", "length_meters")
    list_filter = ("status",)
    search_fields = ("pipeline_name", "pipeline_code")


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ("id", "sensor_name", "sensor_identifier", "device",
                    "sensor_position", "pipeline", "status")
    list_filter = ("sensor_position", "status", "sensor_type")
    search_fields = ("sensor_name", "sensor_identifier")


@admin.register(PipelineSection)
class PipelineSectionAdmin(admin.ModelAdmin):
    list_display = ("id", "pipeline", "section_name", "inlet_sensor", "outlet_sensor", "status")
    list_filter = ("status",)


@admin.register(FlowReading)
class FlowReadingAdmin(admin.ModelAdmin):
    list_display = ("id", "sensor", "device", "flow_rate", "volume",
                    "pulse_count", "reading_timestamp", "received_at")
    list_filter = ("sensor", "device")
    date_hierarchy = "reading_timestamp"


@admin.register(Consumption)
class ConsumptionAdmin(admin.ModelAdmin):
    list_display = ("id", "pipeline", "consumption_volume", "period_start", "period_end")
    list_filter = ("pipeline",)