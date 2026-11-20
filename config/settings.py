import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")
DEBUG = os.getenv("DEBUG", "True") == "True"

_raw_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]
# Render sets this automatically
_render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
if _render_host and _render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "channels",
    # Local
    "core",
    "accounts",
    "devices",
    "monitoring",
    "valves",
    "leak_detection",
    "notifications",
    "activity_logs",
    "system_settings",
    "dashboard",
    "analytics",
    "iot",
    "msingi",
    "finance",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Prefer self-contained templates/ (Render) then monorepo frontend/templates
_FRONTEND_CANDIDATES = [
    BASE_DIR / "templates",
    BASE_DIR.parent / "frontend" / "templates",
]
FRONTEND_DIR = next((p for p in _FRONTEND_CANDIDATES if p.is_dir()), BASE_DIR / "templates")

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [FRONTEND_DIR],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

_STATIC_CANDIDATES = [
    BASE_DIR / "static",
    BASE_DIR.parent / "frontend" / "static",
    FRONTEND_DIR,  # css/js/img next to HTML for same-origin hosting
]
STATICFILES_DIRS = [p for p in _STATIC_CANDIDATES if p.is_dir()]

# Database — DATABASE_URL on Render (Postgres); SQLite locally
_default_sqlite = f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}"
_db_url = os.getenv("DATABASE_URL", _default_sqlite)
try:
    import dj_database_url

    _is_postgres = _db_url.startswith(("postgres://", "postgresql://"))
    DATABASES = {
        "default": dj_database_url.config(
            default=_db_url,
            # Aiven free ~15 slots; don't hold idle connections for 10 minutes
            conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "60")),
            ssl_require=_is_postgres
            and (
                bool(os.getenv("RENDER"))
                or os.getenv("DATABASE_SSL", "False") == "True"
            ),
        )
    }
except Exception:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "iot.authentication.DeviceAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.exceptions.envelope_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "2000/hour",
        "iot": "10000/hour",
        "login": "8/minute",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", 30))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", 7))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
CORS_ALLOW_CREDENTIALS = False

# Behind Render's TLS proxy
if os.getenv("RENDER") or os.getenv("FORCE_SCRIPT_NAME") is not None:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

_csrf = os.getenv("CSRF_TRUSTED_ORIGINS", "").strip()
if _csrf:
    CSRF_TRUSTED_ORIGINS = [x.strip() for x in _csrf.split(",") if x.strip()]
elif _render_host:
    CSRF_TRUSTED_ORIGINS = [f"https://{_render_host}"]
else:
    CSRF_TRUSTED_ORIGINS = []

SPECTACULAR_SETTINGS = {
    "TITLE": "CUE Water Monitoring API",
    "DESCRIPTION": "IoT water monitoring, leak detection and valve control backend.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5500,http://127.0.0.1:5500,"
        "https://cue-pi-orpin.vercel.app",
    ).split(",")
    if o.strip()
]
if _render_host:
    _origin = f"https://{_render_host}"
    if _origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(_origin)
# Split static frontends on Render / Vercel
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://[\w-]+\.onrender\.com$",
    r"^https://[\w-]+\.vercel\.app$",
]

_REDIS_URL = os.getenv("REDIS_URL", "").strip()
if _REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [_REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

SERIAL_PORT = os.getenv("SERIAL_PORT", "COM10")
SERIAL_BAUD = int(os.getenv("SERIAL_BAUD", "9600"))

TEXTSMS_API_URL = os.getenv(
    "TEXTSMS_API_URL", "https://sms.textsms.co.ke/api/services/sendsms/"
)
TEXTSMS_API_KEY = os.getenv("TEXTSMS_API_KEY", "")
TEXTSMS_PARTNER_ID = os.getenv("TEXTSMS_PARTNER_ID", "")
TEXTSMS_SHORTCODE = os.getenv("TEXTSMS_SHORTCODE", "TEXTSms")
ALERT_PHONES = [
    p.strip()
    for p in os.getenv("ALERT_PHONES", "").split(",")
    if p.strip()
]

MSINGI_API_KEY = os.getenv("MSINGI_API_KEY", "")
MSINGI_BASE_URL = os.getenv("MSINGI_BASE_URL", "https://api.msingiai.com").rstrip("/")
MSINGI_VOICE_ID = os.getenv("MSINGI_VOICE_ID", "female3")

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_TIMEZONE = "UTC"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
