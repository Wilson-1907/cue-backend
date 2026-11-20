from rest_framework.permissions import BasePermission, SAFE_METHODS

def _role(user):
    return getattr(user, "role", None)

def _is_admin_or_operator(user):
    if not (user and user.is_authenticated):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return _role(user) in ("ADMIN", "OPERATOR")

class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated
            and (_role(u) == "ADMIN" or getattr(u, "is_superuser", False))
        )

class IsOperatorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return _is_admin_or_operator(request.user)

class RoleReadOnlyOrAdmin(BasePermission):
    """Viewers get read-only; operators/admin get write."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return _is_admin_or_operator(request.user)