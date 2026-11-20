from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsAdministrator
from core.utils import success_response
from activity_logs.services import log_action
from .models import SystemSettings
from .serializers import SystemSettingsSerializer

class _SettingsBase(APIView):
    permission_classes = [IsAuthenticated]
    fields = None

    def get(self, request):
        s = SystemSettings.load()
        data = SystemSettingsSerializer(s).data
        if self.fields:
            data = {k: data[k] for k in self.fields}
        return success_response(data)

    def patch(self, request):
        from rest_framework.permissions import IsAuthenticated as _
        from core.permissions import IsAdministrator as _Admin
        self.permission_classes = [IsAuthenticated, IsAdministrator]
        self.check_permissions(request)
        s = SystemSettings.load()
        partial = {k: v for k, v in request.data.items()
                   if not self.fields or k in self.fields}
        serializer = SystemSettingsSerializer(s, data=partial, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_action(user=request.user, action="SETTINGS_UPDATED",
                   description=f"Updated settings: {list(partial.keys())}",
                   category="SETTINGS")
        return success_response(serializer.data, "Settings updated")

class SettingsView(_SettingsBase):
    fields = None

class ThresholdsView(_SettingsBase):
    fields = ["normal_flow_rate_threshold", "maximum_flow_rate",
              "sensor_difference_tolerance", "leak_trigger_flow_difference"]

class LeakDetectionView(_SettingsBase):
    fields = ["leak_trigger_flow_difference", "leak_trigger_percentage",
              "leak_detection_duration", "automatic_leak_detection"]

class AutomationView(_SettingsBase):
    fields = ["automatic_valve_shutdown", "automatic_leak_detection",
              "device_heartbeat_timeout"]