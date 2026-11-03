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
    "apps.notifications",
]

MIDDLEWARE = [
    # First, so every later middleware and view logs with the request ID.
    "apps.common.middleware.RequestIdMiddleware",
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
        # Manual WhatsApp reminders; the one-per-customer-per-day rule is
        # enforced separately in the database.
        "reminders": "20/min",
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
# Celery (background work) — see config/celery.py
# --------------------------------------------------------------------------
# Redis is the broker and the result store. The default points at the service
# in docker-compose.yml; outside Compose set REDIS_URL to a reachable Redis.
REDIS_URL = config("REDIS_URL", default="redis://redis:6379/0")

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=REDIS_URL)

# A worker that dies mid-task must not lose it: acknowledge only once the task
# has finished, and hand it to someone else if the worker goes away.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
# One task at a time per child process. Building a workbook is memory-heavy,
# and prefetching several would multiply that for no throughput gain.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# A report that has not finished in five minutes is not going to; fail it
# rather than hold a worker forever.
CELERY_TASK_SOFT_TIME_LIMIT = 300
CELERY_TASK_TIME_LIMIT = 360
CELERY_RESULT_EXPIRES = 60 * 60 * 24
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE

# How long a finished export file stays downloadable before the cleanup task
# removes it (hours).
EXPORT_RETENTION_HOURS = config("EXPORT_RETENTION_HOURS", cast=int, default=24)

CELERY_BEAT_SCHEDULE = {
    # Liveness of beat + broker + worker, read by GET /healthz/celery/.
    "beat-heartbeat": {
        "task": "apps.common.tasks.beat_heartbeat",
        "schedule": 60,
        # A heartbeat not run within its minute is dropped, so a backlog left
        # by a worker outage cannot keep the key fresh after beat has died.
        "options": {"expires": 60},
    },
    "purge-expired-exports": {
        "task": "apps.reports.tasks.purge_expired_exports",
        "schedule": 60 * 60,  # hourly
    },
    # WhatsApp: hand due/deferred/retrying messages to workers.
    "whatsapp-dispatch-due": {
        "task": "apps.notifications.tasks.dispatch_due_messages",
        "schedule": 60,
    },
    # WhatsApp: queue upcoming/overdue debt reminders (inside each shop's
    # sending hours; outside them a run simply queues nothing).
    "whatsapp-debt-reminders": {
        "task": "apps.notifications.tasks.schedule_debt_reminders",
        "schedule": 15 * 60,
    },
}

# --------------------------------------------------------------------------
# WhatsApp Cloud API (apps/notifications, docs/WHATSAPP.md)
# --------------------------------------------------------------------------
# Leave the token / number id empty and the whole feature stays off: nothing
# is queued, the debt flow is untouched. One business number serves every
# shop; each message names the shop it is from.
WHATSAPP_ACCESS_TOKEN = config("WHATSAPP_ACCESS_TOKEN", default="")
WHATSAPP_PHONE_NUMBER_ID = config("WHATSAPP_PHONE_NUMBER_ID", default="")
# Signs webhook POSTs (X-Hub-Signature-256); without it every POST is refused.
WHATSAPP_APP_SECRET = config("WHATSAPP_APP_SECRET", default="")
# Answers Meta's GET verification when the webhook URL is registered.
WHATSAPP_VERIFY_TOKEN = config("WHATSAPP_VERIFY_TOKEN", default="")
# Graph API version, e.g. "vXX.0" — deliberately no default: set one Meta
# currently supports (developers.facebook.com/docs/graph-api/changelog).
WHATSAPP_API_VERSION = config("WHATSAPP_API_VERSION", default="")
WHATSAPP_API_BASE = config("WHATSAPP_API_BASE", default="https://graph.facebook.com")
# Language code the templates were approved under in WhatsApp Manager.
WHATSAPP_TEMPLATE_LANGUAGE = config("WHATSAPP_TEMPLATE_LANGUAGE", default="uz")
# True only if the approved templates carry the "Qoldiqni ko'rish" quick-reply
# button; sending a button parameter to a template without one is an error.
WHATSAPP_TEMPLATE_QUICK_REPLY = config("WHATSAPP_TEMPLATE_QUICK_REPLY", cast=bool, default=True)
# Interactive lists/buttons in bot replies; False falls back to plain text.
WHATSAPP_INTERACTIVE = config("WHATSAPP_INTERACTIVE", cast=bool, default=True)

# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------
# Login-lockout counters and rate limits are shared state: every gunicorn
# worker must see the same numbers, or a guesser simply retries until they
# land on a worker that has not counted them yet. Redis is that shared store.
# dev.py falls back to a local-memory cache so `runserver` needs no Redis.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("CACHE_URL", default=REDIS_URL),
    }
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
    # [request_id] ties a line to one HTTP request (X-Request-ID header,
    # apps/common/middleware.py); "-" outside a request (Celery, commands).
    "filters": {"request_id": {"()": "apps.common.logging.RequestIdFilter"}},
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s]: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["request_id"],
        },
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
# The SPA may read the request ID, e.g. to show it next to an error message.
CORS_EXPOSE_HEADERS = ["X-Request-ID"]

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
