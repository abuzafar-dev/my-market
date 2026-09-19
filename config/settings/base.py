"""Settings shared by every environment. Secrets and environment-specific
values are never hardcoded here — they are read from the .env file."""

from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from decouple import Csv, config

# --------------------------------------------------------------------------
# Paths & environment
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --------------------------------------------------------------------------
# Core security
# --------------------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY")

# --------------------------------------------------------------------------
# Application definition
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "apps.common",
    "apps.shops",
    "apps.catalog",
    "apps.sales",
    "apps.debt",
    "apps.reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# The only HTML this project still renders is the Django admin at
# /admin/ (see config/urls.py) — everything else is JSON (TZ v2 8.1).
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
_db_url = urlparse(config("DATABASE_URL"))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _db_url.path.lstrip("/"),
        "USER": _db_url.username,
        "PASSWORD": _db_url.password,
        "HOST": _db_url.hostname,
        "PORT": _db_url.port,
    },
}

# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "shops.User"

# Counts wrong passwords per address/phone and locks a guesser out (see
# apps/shops/security.py). Also guards the Django admin login.
AUTHENTICATION_BACKENDS = ["apps.shops.security.LockoutModelBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# --------------------------------------------------------------------------
# Internationalization
# --------------------------------------------------------------------------
LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static & media files
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# --------------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# REST API (Django REST Framework + JWT)
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "apps.common.renderers.EnvelopeJSONRenderer",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    # How many reverse proxies sit in front of the app (Caddy + nginx = 2 in the
    # provided deployment). 0 means "trust only the socket address". It MUST be
    # right: with the wrong value a client can put anything in X-Forwarded-For and
    # escape every rate limit, or all users end up sharing the proxy's address.
    "NUM_PROXIES": config("NUM_PROXIES", cast=int, default=0),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # anon / user: every request (per address / per logged-in user). "writes",
    # "login" and "exports" are applied per view on top: sale + debt writes,
    # the login form, and the heavy report files.
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/min",
        "user": "600/min",
        "writes": "120/min",
        "login": "10/min",
        "exports": "12/min",
    },
    "EXCEPTION_HANDLER": "apps.common.exceptions.exception_handler",
}

# Access token: short-lived, returned in the response body only (kept in
# memory by the frontend). Refresh token: long-lived, httpOnly cookie,
# rotated and blacklisted on every use (TZ v2 9.4).
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Mening Bozorim API",
    "DESCRIPTION": "Kichik do'konlar uchun boshqaruv tizimi — REST API",
    "VERSION": "2.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
# Django's default config only prints errors when DEBUG=True (its console
# handler is require_debug_true, and the fallback mail_admins needs ADMINS
# + SMTP) — so with DEBUG=False a 500 left no traceback anywhere. Everything
# here goes to stderr, which gunicorn/docker capture as the service log.
LOG_LEVEL = config("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        # Unhandled exceptions -> 5xx, with the traceback.
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        # Business events (sale cancelled, stock written off) from apps.*
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# --------------------------------------------------------------------------
# CORS — only the separately hosted Vue SPA is allowed to call this API
# --------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", cast=Csv(), default="http://localhost:5173")

# --------------------------------------------------------------------------
# Optional surfaces (off in production unless asked for)
# --------------------------------------------------------------------------
# The Django admin is a full back door to the data; the server keeps it switched
# off (ADMIN_ENABLED=False) and turns it on only while someone needs it.
ADMIN_ENABLED = config("ADMIN_ENABLED", cast=bool, default=True)

# The refresh-token cookie is only ever sent over HTTPS unless a settings module
# says otherwise (dev serves localhost; prod's ALLOW_INSECURE_HTTP test mode).
REFRESH_COOKIE_SECURE = True

CORS_ALLOW_CREDENTIALS = True
