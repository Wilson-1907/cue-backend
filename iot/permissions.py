from rest_framework.permissions import BasePermission

class IsDevice(BasePermission):
    def has_permission(self, request, view):
        principal = getattr(request, "user", None)
        return principal is not None and getattr(principal, "role", None) == "DEVICE"