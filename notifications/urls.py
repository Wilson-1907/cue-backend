from django.urls import path

from . import views

urlpatterns = [
    path("notifications/", views.NotificationListView.as_view()),
    path("notifications/create/", views.NotificationCreateView.as_view()),
    path("notifications/public/", views.PublicNotificationListView.as_view()),
    path("notifications/unread/", views.UnreadListView.as_view()),
    path("notifications/mark-all-read/", views.MarkAllReadView.as_view()),
    path("notifications/preferences/", views.NotificationPreferencesView.as_view()),
    path("notifications/<int:pk>/", views.NotificationDetailView.as_view()),
    path("notifications/<int:pk>/read/", views.MarkReadView.as_view()),
    path("notifications/<int:pk>/deactivate/", views.NotificationDeactivateView.as_view()),
]
