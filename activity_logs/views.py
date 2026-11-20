from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import ActivityLog
from .serializers import ActivityLogSerializer

class ActivityLogListView(generics.ListAPIView):
    queryset = ActivityLog.objects.select_related("user", "device")
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["category", "user", "device"]
    search_fields = ["action", "description"]

class ActivityLogDetailView(generics.RetrieveAPIView):
    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]

class UserActivitiesView(generics.ListAPIView):
    queryset = ActivityLog.objects.filter(user__isnull=False)
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]

class DeviceActivitiesView(generics.ListAPIView):
    queryset = ActivityLog.objects.filter(device__isnull=False)
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]

class ValveActivitiesView(generics.ListAPIView):
    queryset = ActivityLog.objects.filter(category=ActivityLog.Category.VALVE)
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]