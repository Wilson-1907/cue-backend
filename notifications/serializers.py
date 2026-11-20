from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True, default=""
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "severity",
            "audience",
            "is_read",
            "is_pinned",
            "is_active",
            "created_by",
            "created_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by", "created_by_username"]


class NotificationCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    message = serializers.CharField()
    severity = serializers.ChoiceField(
        choices=Notification.Severity.choices, default=Notification.Severity.INFO
    )
    audience = serializers.ChoiceField(
        choices=Notification.Audience.choices, default=Notification.Audience.INTERNAL
    )
    is_pinned = serializers.BooleanField(required=False, default=False)
    notification_type = serializers.ChoiceField(
        choices=Notification.Type.choices, required=False
    )


class PublicNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "severity",
            "is_pinned",
            "created_at",
        ]
