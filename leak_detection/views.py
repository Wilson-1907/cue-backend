from datetime import timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from core.utils import success_response
from monitoring.models import Pipeline, Sensor
from .models import LeakEvent
from .serializers import LeakEventSerializer
from .services import compare_pipeline, evaluate_pipeline
from system_settings.models import SystemSettings

class LeakOverviewView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        active = LeakEvent.objects.exclude(detection_status=LeakEvent.DetectionStatus.RESOLVED)
        return success_response({
            "active_events": active.count(),
            "confirmed_events": active.filter(detection_status=LeakEvent.DetectionStatus.CONFIRMED).count(),
            "suspected_events": active.filter(detection_status=LeakEvent.DetectionStatus.SUSPECTED).count(),
            "system_status": "ALERT" if active.exists() else "NORMAL",
        })

class LeakStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        pipelines = []
        for p in Pipeline.objects.all():
            active = (LeakEvent.objects
                      .filter(pipeline=p)
                      .exclude(detection_status=LeakEvent.DetectionStatus.RESOLVED)
                      .order_by("-started_at").first())
            pipelines.append({
                "pipeline_id": p.id,
                "pipeline_name": p.pipeline_name,
                "status": active.detection_status if active else "NORMAL",
            })
        return success_response(pipelines)

class LeakEventsListView(generics.ListAPIView):
    queryset = LeakEvent.objects.select_related("pipeline", "inlet_sensor", "outlet_sensor")
    serializer_class = LeakEventSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["detection_status", "severity", "pipeline"]

class LeakEventDetailView(generics.RetrieveAPIView):
    queryset = LeakEvent.objects.all()
    serializer_class = LeakEventSerializer
    permission_classes = [IsAuthenticated]

class PipelineStructureView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        pipeline_id = request.query_params.get("pipeline")
        pipeline = Pipeline.objects.filter(pk=pipeline_id).first() if pipeline_id else Pipeline.objects.first()
        if not pipeline:
            return success_response({"pipelines": []})
        inlet = Sensor.objects.filter(pipeline=pipeline, sensor_position=Sensor.Position.INLET).first()
        outlet = Sensor.objects.filter(pipeline=pipeline, sensor_position=Sensor.Position.OUTLET).first()
        sections = list(pipeline.sections.values())
        return success_response({
            "pipeline": {
                "id": pipeline.id,
                "name": pipeline.pipeline_name,
                "code": pipeline.pipeline_code,
                "length_meters": pipeline.length_meters,
                "status": pipeline.status,
            },
            "inlet_sensor": {
                "id": inlet.id, "identifier": inlet.sensor_identifier,
                "name": inlet.sensor_name,
            } if inlet else None,
            "outlet_sensor": {
                "id": outlet.id, "identifier": outlet.sensor_identifier,
                "name": outlet.sensor_name,
            } if outlet else None,
            "sections": sections,
            "condition": pipeline.status,
        })

class PipelineLiveView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        pipeline_id = request.query_params.get("pipeline")
        pipeline = Pipeline.objects.filter(pk=pipeline_id).first() if pipeline_id else Pipeline.objects.first()
        if not pipeline:
            return success_response({})
        return success_response(compare_pipeline(pipeline))

class PipelineComparisonView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        pipeline_id = request.query_params.get("pipeline")
        pipeline = Pipeline.objects.filter(pk=pipeline_id).first() if pipeline_id else Pipeline.objects.first()
        if not pipeline:
            return success_response({})
        return success_response(compare_pipeline(pipeline))

class PipelineFlowDifferenceView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        pipeline_id = request.query_params.get("pipeline")
        pipeline = Pipeline.objects.filter(pk=pipeline_id).first() if pipeline_id else Pipeline.objects.first()
        if not pipeline:
            return success_response({})
        r = compare_pipeline(pipeline)
        return success_response({
            "flow_difference": r.get("flow_difference"),
            "difference_percentage": r.get("difference_percentage"),
        })

class LeakHistoryView(generics.ListAPIView):
    serializer_class = LeakEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LeakEvent.objects.all().order_by("-started_at")

class LeakSettingsPatchView(APIView):
    permission_classes = [IsAuthenticated]
    def patch(self, request):
        from core.permissions import IsAdministrator
        if not IsAdministrator().has_permission(request, self):
            return success_response(message="Forbidden", data=None)
        s = SystemSettings.load()
        for field in ["leak_trigger_flow_difference", "leak_trigger_percentage",
                      "leak_detection_duration", "automatic_leak_detection"]:
            if field in request.data:
                setattr(s, field, request.data[field])
        s.save()
        return success_response({"status": "updated"})