from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from activity_logs.models import ActivityLog
from activity_logs.serializers import ActivityLogSerializer
from core.utils import success_response

from .services import consumption_overview, flow_trend, overview


class OverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(overview())


class FlowTrendView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        range_param = request.query_params.get("range")
        hours_raw = request.query_params.get("hours")
        sensor = request.query_params.get("sensor")

        sensor_id = None
        if sensor:
            try:
                sensor_id = int(sensor)
            except (TypeError, ValueError):
                sensor_id = None

        if range_param:
            payload = flow_trend(
                range_key=range_param.lower().strip(),
                sensor_id=sensor_id,
            )
        elif hours_raw is not None:
            try:
                hours = int(hours_raw)
            except (TypeError, ValueError):
                hours = 24
            payload = flow_trend(hours=hours, range_key="day", sensor_id=sensor_id)
        else:
            payload = flow_trend(range_key="day", sensor_id=sensor_id)

        return success_response(payload)


class ConsumptionOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("days", 7))
        return success_response(consumption_overview(days))


class RecentActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ActivityLog.objects.select_related("user", "device")[:20]
        return success_response(ActivityLogSerializer(qs, many=True).data)


class SummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(
            {
                "overview": overview(),
                "flow_trend_last_6h": flow_trend(hours=6, range_key="day", as_list=True),
                "consumption_last_7_days": consumption_overview(7),
            }
        )
