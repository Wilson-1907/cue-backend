from django.urls import path

from . import views

urlpatterns = [
    path("msingi/chat/", views.MsingiChatView.as_view()),
    path("msingi/speak/", views.MsingiSpeakView.as_view()),
    path("msingi/health/", views.MsingiHealthView.as_view()),
]
