from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/overview/", views.OverviewView.as_view()),
    path("dashboard/flow-trend/", views.FlowTrendView.as_view()),
    path("dashboard/consumption-overview/", views.ConsumptionOverviewView.as_view()),
    path("dashboard/recent-activity/", views.RecentActivityView.as_view()),
    path("dashboard/summary/", views.SummaryView.as_view()),
]