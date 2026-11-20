from django.urls import path
from . import views

urlpatterns = [
    path("devices/", views.DeviceListView.as_view()),
    path("devices/connected/", views.ConnectedDeviceListView.as_view()),
    path("devices/disconnected/", views.DisconnectedDeviceListView.as_view()),
    path("devices/<int:pk>/", views.DeviceDetailView.as_view()),
    path("devices/<int:pk>/status/", views.DeviceStatusView.as_view()),
    path("devices/<int:pk>/health/", views.DeviceHealthView.as_view()),
    path("devices/<int:pk>/communications/", views.DeviceCommunicationsView.as_view()),
]