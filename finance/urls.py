from django.urls import path

from . import views

urlpatterns = [
    path("finance/summary/", views.FinanceSummaryView.as_view()),
    path("finance/report/", views.FinanceReportView.as_view()),
    path("finance/entries/", views.FinanceEntryListCreateView.as_view()),
    path("finance/entries/<int:pk>/", views.FinanceEntryDetailView.as_view()),
    path("finance/settings/", views.FinanceSettingsView.as_view()),
    path("finance/maintenance/", views.FinanceMaintenanceView.as_view()),
]
