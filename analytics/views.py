from datetime import date, timedelta
from io import BytesIO
from django.http import FileResponse
from django.core.files.base import ContentFile
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from core.utils import success_response
from .models import Report
from .serializers import ReportSerializer
from .services import analytics_summary, consumption_trends, usage_breakdown
from leak_detection.models import LeakEvent
from leak_detection.serializers import LeakEventSerializer

def _range(request):
    end = request.query_params.get("end_date")
    start = request.query_params.get("start_date")
    end_d = date.fromisoformat(end) if end else date.today()
    start_d = date.fromisoformat(start) if start else end_d - timedelta(days=30)
    return start_d, end_d

class AnalyticsSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        s, e = _range(request)
        return success_response(analytics_summary(s, e))

class ConsumptionTrendsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        s, e = _range(request)
        return success_response(consumption_trends(s, e))

class UsageBreakdownView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        s, e = _range(request)
        return success_response(usage_breakdown(s, e))

class LeakEventStatsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        s, e = _range(request)
        qs = LeakEvent.objects.filter(started_at__date__gte=s, started_at__date__lte=e)
        return success_response({
            "total": qs.count(),
            "by_status": {st: qs.filter(detection_status=st).count()
                          for st, _ in LeakEvent.DetectionStatus.choices},
            "by_severity": {sv: qs.filter(severity=sv).count()
                            for sv, _ in LeakEvent.Severity.choices},
            "events": LeakEventSerializer(qs[:100], many=True).data,
        })

class ReportsListView(generics.ListAPIView):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

class GenerateReportView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        s = date.fromisoformat(request.data["start_date"])
        e = date.fromisoformat(request.data["end_date"])
        report_type = request.data.get("report_type", "CONSUMPTION")
        title = request.data.get("title", f"{report_type} report {s} to {e}")
        rep = Report.objects.create(title=title, report_type=report_type,
                                    start_date=s, end_date=e,
                                    generated_by=request.user)
        summary = analytics_summary(s, e) if report_type != "LEAK" else {"leaks": LeakEvent.objects.count()}
        rep.summary = summary
        # Simple text summary as file
        content = "\n".join(f"{k}: {v}" for k, v in summary.items())
        rep.file.save(f"report_{rep.id}.txt", ContentFile(content.encode()), save=True)
        rep.status = Report.Status.READY
        rep.save()
        return success_response(ReportSerializer(rep).data, "Report generated")

class ReportDetailView(generics.RetrieveAPIView):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

class DownloadReportView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        rep = Report.objects.get(pk=pk)
        if not rep.file:
            from core.utils import error_response
            from rest_framework import status
            return error_response("No file available", status_code=status.HTTP_404_NOT_FOUND)
        return FileResponse(rep.file.open("rb"), as_attachment=True,
                            filename=rep.file.name.split("/")[-1])