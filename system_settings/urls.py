from django.urls import path
from . import views

urlpatterns = [
    path("settings/", views.SettingsView.as_view()),
    path("settings/thresholds/", views.ThresholdsView.as_view()),
    path("settings/leak-detection/", views.LeakDetectionView.as_view()),
    path("settings/automation/", views.AutomationView.as_view()),
]