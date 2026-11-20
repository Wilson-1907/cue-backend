from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from core.permissions import IsOperatorOrAdmin
from core.utils import error_response, success_response

from .models import Notification
from .serializers import (
    NotificationCreateSerializer,
    NotificationSerializer,
    PublicNotificationSerializer,
)
from . import services


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["is_read", "severity", "notification_type", "audience"]

    def get_queryset(self):
        return Notification.objects.all()


class NotificationCreateView(APIView):
    """Operators/admins publish internal or public notices."""

    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]

    def post(self, request):
        ser = NotificationCreateSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid notification", errors=ser.errors)
        d = ser.validated_data
        audience = d.get("audience") or Notification.Audience.INTERNAL
        ntype = d.get("notification_type")
        if not ntype:
            ntype = (
                Notification.Type.PUBLIC_ANNOUNCEMENT
                if audience == Notification.Audience.PUBLIC
                else Notification.Type.ADMIN_MESSAGE
            )
        notif = services.create_notification(
            title=d["title"],
            message=d["message"],
            notification_type=ntype,
            severity=d.get("severity") or Notification.Severity.INFO,
            audience=audience,
            is_pinned=d.get("is_pinned") or False,
            user=request.user,
        )
        return success_response(
            NotificationSerializer(notif).data,
            "Notification published",
            status_code=201,
        )


class PublicNotificationListView(APIView):
    """Public website feed — active PUBLIC announcements only."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        limit = min(int(request.query_params.get("limit") or 10), 30)
        qs = Notification.objects.filter(
            audience=Notification.Audience.PUBLIC,
            is_active=True,
        ).order_by("-is_pinned", "-created_at")[:limit]
        return success_response(PublicNotificationSerializer(qs, many=True).data)


class UnreadListView(generics.ListAPIView):
    queryset = Notification.objects.filter(is_read=False, audience=Notification.Audience.INTERNAL)
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]


class NotificationDetailView(generics.RetrieveAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        Notification.objects.filter(pk=pk).update(is_read=True)
        return success_response(message="Marked as read")


class MarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(is_read=False).update(is_read=True)
        return success_response(message="All notifications marked as read")


class NotificationDeactivateView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]

    def post(self, request, pk):
        n = Notification.objects.filter(pk=pk).first()
        if not n:
            return error_response("Not found", status_code=404)
        n.is_active = False
        n.save(update_fields=["is_active", "updated_at"])
        return success_response(NotificationSerializer(n).data, "Notification deactivated")


class NotificationPreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response({"email_notifications": True, "push_notifications": True})

    def patch(self, request):
        return success_response(request.data, "Preferences updated")
