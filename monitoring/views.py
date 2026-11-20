from datetime import timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from core.permissions import RoleReadOnlyOrAdmin
from core.utils import success_response
from devices.models import Device
from .models import Sensor, Pipeline, PipelineSection, FlowReading, Consumption
from .serializers import (SensorSerializer, PipelineSerializer, PipelineSectionSerializer,
                          FlowReadingSerializer, ConsumptionSerializer)
from .services import latest_reading_for_sensor, consumption_today, current_flow_rate

# ---------- Devices & Sensors management endpoints ----------
class SensorListView(generics.ListAPIView):
    queryset = Sensor.objects.select_related("device", "pipeline")
    serializer_class = SensorSerializer
    permission_classes = [IsAuthenticated, RoleReadOnlyOrAdmin]
    filterset_fields = ["sensor_position", "status", "device", "pipeline"]
    search_fields = ["sensor_name", "sensor_identifier"]

class SensorDetailView(generics.RetrieveAPIView):
    queryset = Sensor.objects.select_related("device", "pipeline")
    serializer_class = SensorSerializer
    permission_classes = [IsAuthenticated]

class SensorReadingsView(generics.ListAPIView):
    serializer_class = FlowReadingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FlowReading.objects.filter(sensor_id=self.kwargs["pk"])

class SensorStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        s = Sensor.objects.get(pk=pk)
        last = latest_reading_for_sensor(s)
        return success_response({
            "sensor": s.sensor_identifier,
            "status": s.status,
            "sensor_position": s.sensor_position,
            "last_reading": FlowReadingSerializer(last).data if last else None,
        })

# ---------- Pipelines ----------
class PipelineListView(generics.ListAPIView):
    queryset = Pipeline.objects.all()
    serializer_class = PipelineSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status"]

class PipelineSectionListView(generics.ListAPIView):
    queryset = PipelineSection.objects.select_related("pipeline", "inlet_sensor", "outlet_sensor")
    serializer_class = PipelineSectionSerializer
    permission_classes = [IsAuthenticated]

# ---------- Live Monitoring ----------
class LiveMonitoringView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        pipeline_id = request.query_params.get("pipeline")
        pipeline = Pipeline.objects.filter(pk=pipeline_id).first() if pipeline_id else Pipeline.objects.first()
        data = {
            "pipeline_id": pipeline.id if pipeline else None,
            "current_flow_rate": current_flow_rate(pipeline),
            "unit": "L/min",
            "consumption_today": consumption_today(pipeline),
            "sensors": [],
        }
        if pipeline:
            for s in Sensor.objects.filter(pipeline=pipeline):
                last = latest_reading_for_sensor(s)
                data["sensors"].append({
                    "sensor": s.sensor_identifier,
                    "position": s.sensor_position,
                    "last_reading": FlowReadingSerializer(last).data if last else None,
                })
        return success_response(data)

class FlowRateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        pipeline_id = request.query_params.get("pipeline")
        pipeline = Pipeline.objects.filter(pk=pipeline_id).first() if pipeline_id else None
        return success_response({
            "flow_rate": current_flow_rate(pipeline),
            "unit": "L/min",
            "as_of": timezone.now(),
        })

class ConsumptionTodayView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        pipeline_id = request.query_params.get("pipeline")
        pipeline = Pipeline.objects.filter(pk=pipeline_id).first() if pipeline_id else None
        return success_response({
            "consumption_volume": consumption_today(pipeline),
            "unit": "L",
        })

class SensorStatusListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        data = []
        for s in Sensor.objects.select_related("device"):
            last = latest_reading_for_sensor(s)
            data.append({
                "sensor_id": s.id,
                "sensor": s.sensor_identifier,
                "name": s.sensor_name,
                "position": s.sensor_position,
                "device": s.device.device_identifier,
                "device_status": s.device.connection_status,
                "status": s.status,
                "last_reading_at": last.reading_timestamp if last else None,
            })
        return success_response(data)

class ConnectivityView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        devices = list(Device.objects.values(
            "id", "device_name", "device_identifier", "connection_status", "last_communication"))
        return success_response({"devices": devices})

class HistoryView(generics.ListAPIView):
    serializer_class = FlowReadingSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["sensor"]

    def get_queryset(self):
        qs = FlowReading.objects.all()
        start = self.request.query_params.get("start")
        end = self.request.query_params.get("end")
        if start:
            qs = qs.filter(reading_timestamp__gte=start)
        if end:
            qs = qs.filter(reading_timestamp__lte=end)
        return qs.order_by("-reading_timestamp")