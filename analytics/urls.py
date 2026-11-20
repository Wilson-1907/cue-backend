from django.urls import path
from . import views

urlpatterns = [
    path("analytics/summary/", views.AnalyticsSummaryView.as_view()),
    path("analytics/consumption-trends/", views.ConsumptionTrendsView.as_view()),
    path("analytics/usage-breakdown/", views.UsageBreakdownView.as_view()),
    path("analytics/leak-events/", views.LeakEventStatsView.as_view()),
    path("analytics/reports/", views.ReportsListView.as_view()),
    path("analytics/reports/generate/", views.GenerateReportView.as_view()),
    path("analytics/reports/<int:pk>/", views.ReportDetailView.as_view()),
    path("analytics/reports/<int:pk>/download/", views.DownloadReportView.as_view()),
]