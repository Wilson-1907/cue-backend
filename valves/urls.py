from django.urls import path
from . import views

urlpatterns = [
    path("valves/", views.ValveListView.as_view()),
    path("valves/open/", views.ValveOpenListView.as_view()),
    path("valves/closed/", views.ValveClosedListView.as_view()),
    path("valves/activities/", views.ValveActivitiesView.as_view()),
    path("valves/<int:pk>/", views.ValveDetailView.as_view()),
    path("valves/<int:pk>/open/", views.ValveOpenView.as_view()),
    path("valves/<int:pk>/close/", views.ValveCloseView.as_view()),
    path("valves/<int:pk>/auto/", views.ValveAutoView.as_view()),
    path("valves/<int:pk>/manual/", views.ValveManualView.as_view()),
]