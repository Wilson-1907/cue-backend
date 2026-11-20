from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["id", "date_joined", "last_login", "is_staff"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role", "password"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        role = validated_data.get("role") or User.Role.VIEWER
        user = User(**validated_data)
        user.set_password(password)
        # Staff flag for ADMIN role so Django admin + operator APIs stay aligned
        if role == User.Role.ADMIN:
            user.is_staff = True
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, validators=[validate_password]
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "password",
        ]

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        role = validated_data.get("role", instance.role)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if role == User.Role.ADMIN:
            instance.is_staff = True
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value