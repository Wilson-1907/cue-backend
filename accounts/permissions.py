from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdministrator(BasePermission):
    """Only users with role == ADMIN."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == "ADMIN"
        )


class IsOperatorOrAdmin(BasePermission):
    """Users with role OPERATOR or ADMIN."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) in ("ADMIN", "OPERATOR")
        )


class RoleReadOnlyOrAdmin(BasePermission):
    """All authenticated users read; only OPERATOR/ADMIN write."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return getattr(request.user, "role", None) in ("ADMIN", "OPERATOR")