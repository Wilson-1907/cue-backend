from django.urls import path
from . import views

urlpatterns = [
    path("iot/readings/", views.ReadingIngestView.as_view()),
    path("iot/readings/bulk/", views.BulkReadingsView.as_view()),
    path("iot/sensors/<int:pk>/readings/", views.SensorReadingView.as_view()),
    path("iot/sensors/<int:pk>/configuration/", views.SensorConfigView.as_view()),
    path("iot/heartbeat/", views.HeartbeatView.as_view()),
    path("iot/devices/register/", views.DeviceRegisterView.as_view()),
    path("iot/devices/status/", views.DeviceStatusReportView.as_view()),
    path("iot/devices/warnings/", views.DeviceWarningView.as_view()),
    path("iot/devices/<int:pk>/configuration/", views.DeviceConfigView.as_view()),
    path("iot/commands/pending/", views.PendingCommandsView.as_view()),
    path("iot/commands/<int:pk>/acknowledge/", views.AcknowledgeCommandView.as_view()),
    path("iot/commands/<int:pk>/execute/", views.ExecuteCommandView.as_view()),
    path("iot/valves/<int:pk>/status/", views.ValveStatusReportView.as_view()),
]