from django.urls import path
from . import views

urlpatterns = [
    path("leaks/overview/", views.LeakOverviewView.as_view()),
    path("leaks/status/", views.LeakStatusView.as_view()),
    path("leaks/events/", views.LeakEventsListView.as_view()),
    path("leaks/events/<int:pk>/", views.LeakEventDetailView.as_view()),
    path("leaks/pipeline/", views.PipelineStructureView.as_view()),
    path("leaks/pipeline/live/", views.PipelineLiveView.as_view()),
    path("leaks/pipeline/comparison/", views.PipelineComparisonView.as_view()),
    path("leaks/pipeline/flow-difference/", views.PipelineFlowDifferenceView.as_view()),
    path("leaks/history/", views.LeakHistoryView.as_view()),
    path("leaks/settings/", views.LeakSettingsPatchView.as_view()),
]