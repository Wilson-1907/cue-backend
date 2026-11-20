from django.contrib.auth import authenticate, get_user_model
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from core.permissions import IsOperatorOrAdmin
from core.utils import error_response, success_response

from .serializers import (
    ChangePasswordSerializer,
    ProfileUpdateSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .throttles import LoginRateThrottle

User = get_user_model()

DASHBOARD_ROLES = {User.Role.ADMIN, User.Role.OPERATOR}


def user_can_access_dashboard(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if not user.is_active:
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return getattr(user, "role", None) in DASHBOARD_ROLES


class LoginView(TokenObtainPairView):
    """
    Secure operator login → JWT for the CUE dashboard.
    Rejects inactive accounts and users without operator/admin access.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        if not username or not password:
            return error_response("Username and password are required.", status_code=400)

        user = authenticate(username=username, password=password)
        if user is None:
            # Also try case-sensitive exact lookup for clearer inactive messaging
            existing = User.objects.filter(username=username).first()
            if existing and not existing.is_active:
                return error_response(
                    "This account is deactivated. Contact an administrator.",
                    status_code=403,
                )
            from activity_logs.services import log_action

            log_action(
                action="LOGIN_FAILED",
                description=f"Failed login attempt for '{username}'",
                category="AUTH",
                ip_address=self._client_ip(request),
            )
            return error_response("Invalid username or password.", status_code=401)

        if not user.is_active:
            return error_response(
                "This account is deactivated. Contact an administrator.",
                status_code=403,
            )

        if not user_can_access_dashboard(user):
            from activity_logs.services import log_action

            log_action(
                user=user,
                action="LOGIN_DENIED",
                description="Login denied — insufficient role for dashboard",
                category="AUTH",
                ip_address=self._client_ip(request),
            )
            return error_response(
                "Your account is not authorized for the operator dashboard.",
                status_code=403,
            )

        refresh = RefreshToken.for_user(user)
        from activity_logs.services import log_action

        log_action(
            user=user,
            action="LOGIN",
            description="User logged in to dashboard",
            category="AUTH",
            ip_address=self._client_ip(request),
        )
        return success_response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            "Login successful",
        )

    @staticmethod
    def _client_ip(request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except Exception:
                return error_response("Invalid refresh token.")
        from activity_logs.services import log_action

        log_action(
            user=request.user,
            action="LOGOUT",
            description="User logged out",
            category="AUTH",
        )
        return success_response(message="Logged out successfully")


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = UserSerializer(request.user).data
        data["can_access_dashboard"] = user_can_access_dashboard(request.user)
        return success_response(data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(UserSerializer(request.user).data, "Profile updated")


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return success_response(message="Password changed successfully")


class UserListCreateView(APIView):
    """In-app user management (operators/admins)."""

    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]

    def get(self, request):
        qs = User.objects.all().order_by("-date_joined")
        role = request.query_params.get("role")
        status = request.query_params.get("status")
        search = (request.query_params.get("search") or "").strip()
        if role:
            qs = qs.filter(role=role)
        if status == "ACTIVE":
            qs = qs.filter(is_active=True)
        elif status == "INACTIVE":
            qs = qs.filter(is_active=False)
        if search:
            from django.db.models import Q

            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        rows = UserSerializer(qs[:200], many=True).data
        summary = {
            "total": User.objects.count(),
            "active": User.objects.filter(is_active=True).count(),
            "admins": User.objects.filter(role=User.Role.ADMIN).count(),
            "inactive": User.objects.filter(is_active=False).count(),
        }
        return success_response({"users": rows, "summary": summary})

    def post(self, request):
        ser = UserCreateSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid user data", errors=ser.errors)
        user = ser.save()
        return success_response(UserSerializer(user).data, "User created", status_code=201)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]

    def get(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return error_response("User not found", status_code=404)
        return success_response(UserSerializer(user).data)

    def patch(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return error_response("User not found", status_code=404)
        if user.id == request.user.id and request.data.get("is_active") is False:
            return error_response("You cannot deactivate your own account.", status_code=400)
        ser = UserUpdateSerializer(user, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid user data", errors=ser.errors)
        ser.save()
        return success_response(UserSerializer(user).data, "User updated")

    def delete(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return error_response("User not found", status_code=404)
        if user.id == request.user.id:
            return error_response("You cannot delete your own account.", status_code=400)
        user.is_active = False
        user.save(update_fields=["is_active"])
        return success_response(UserSerializer(user).data, "User deactivated")
