from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    UserDetailView,
    UserListCreateView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/password/change/", ChangePasswordView.as_view(), name="auth-password-change"),
    path("auth/users/", UserListCreateView.as_view(), name="auth-users"),
    path("auth/users/<int:pk>/", UserDetailView.as_view(), name="auth-user-detail"),
]