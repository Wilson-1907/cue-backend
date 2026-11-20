from django.urls import path
from . import views

urlpatterns = [
    # Sensors
    path("sensors/", views.SensorListView.as_view()),
    path("sensors/<int:pk>/", views.SensorDetailView.as_view()),
    path("sensors/<int:pk>/readings/", views.SensorReadingsView.as_view()),
    path("sensors/<int:pk>/status/", views.SensorStatusView.as_view()),
    # Pipelines
    path("pipelines/", views.PipelineListView.as_view()),
    path("pipelines/sections/", views.PipelineSectionListView.as_view()),
    # Live monitoring
    path("monitoring/live/", views.LiveMonitoringView.as_view()),
    path("monitoring/flow-rate/", views.FlowRateView.as_view()),
    path("monitoring/consumption/today/", views.ConsumptionTodayView.as_view()),
    path("monitoring/sensors/status/", views.SensorStatusListView.as_view()),
    path("monitoring/connectivity/", views.ConnectivityView.as_view()),
    path("monitoring/history/", views.HistoryView.as_view()),
]