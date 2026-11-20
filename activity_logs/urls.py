from django.urls import path
from . import views

urlpatterns = [
    path("activity-logs/", views.ActivityLogListView.as_view()),
    path("activity-logs/users/", views.UserActivitiesView.as_view()),
    path("activity-logs/devices/", views.DeviceActivitiesView.as_view()),
    path("activity-logs/valves/", views.ValveActivitiesView.as_view()),
    path("activity-logs/<int:pk>/", views.ActivityLogDetailView.as_view()),
]