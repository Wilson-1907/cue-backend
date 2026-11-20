from pathlib import Path

from django.contrib import admin
from django.http import FileResponse, Http404, JsonResponse
from django.urls import path, include, re_path
from django.views.static import serve
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from django.conf import settings

api_patterns = [
    path("", include("accounts.urls")),
    path("", include("dashboard.urls")),
    path("", include("monitoring.urls")),
    path("", include("analytics.urls")),
    path("", include("devices.urls")),
    path("", include("valves.urls")),
    path("", include("leak_detection.urls")),
    path("", include("notifications.urls")),
    path("", include("activity_logs.urls")),
    path("", include("system_settings.urls")),
    path("", include("iot.urls")),
    path("", include("msingi.urls")),
    path("", include("finance.urls")),
]


def api_index(_request):
    return JsonResponse({
        "service": "CUE Water Monitoring API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "app": "/app/",
            "api_root": "/api/v1/",
            "docs_swagger": "/api/docs/",
            "docs_redoc": "/api/redoc/",
            "schema": "/api/schema/",
            "admin": "/admin/",
            "websocket": "/ws/stream/?token=<access_token>",
        },
    })


FRONTEND_ROOT = Path(getattr(settings, "FRONTEND_DIR", settings.BASE_DIR / "templates"))


def frontend_index(_request):
    index = FRONTEND_ROOT / "index.html"
    if not index.is_file():
        return api_index(_request)
    return FileResponse(index.open("rb"), content_type="text/html")


def frontend_file(_request, path: str):
    """Serve public UI files (html/css/js/img) from FRONTEND_DIR."""
    # Never shadow API / admin
    if path.startswith(("api/", "admin/", "ws/", "static/", "media/")):
        raise Http404()
    target = (FRONTEND_ROOT / path).resolve()
    try:
        target.relative_to(FRONTEND_ROOT.resolve())
    except ValueError as exc:
        raise Http404() from exc
    if target.is_dir():
        target = target / "index.html"
    if not target.is_file():
        raise Http404()
    return serve(_request, path=str(target.relative_to(FRONTEND_ROOT)), document_root=str(FRONTEND_ROOT))


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("app/", frontend_index, name="app-home"),
    path("", frontend_index, name="home"),
    re_path(r"^(?P<path>.+)$", frontend_file, name="frontend-file"),
]
