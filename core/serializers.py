from rest_framework import serializers


class MessageSerializer(serializers.Serializer):
    """Simple serializer used purely for drf-spectacular response schemas."""
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = serializers.JSONField(required=False)