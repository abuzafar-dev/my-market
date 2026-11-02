"""Production settings."""

from decouple import Csv, config

from config.observability import init_sentry

from .base import *  # noqa: F403

DEBUG = False

# Admin and the API docs are switched off on a real server by default.
ADMIN_ENABLED = config("ADMIN_ENABLED", cast=bool, default=False)

# The SPA is served from the same origin (nginx proxies /api), so no other
# origin needs CORS access. Leave empty unless a separate front-end host is used.
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", cast=Csv(), default="")

# The cache comes from base.py and is Redis: login-attempt counters and rate
# limits have to be shared by every gunicorn worker, which a per-process cache
# cannot do and a file cache only does slowly. Redis is already in the stack as
# the Celery broker, so this costs nothing extra.

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

# --------------------------------------------------------------------------
# Security hardening
# --------------------------------------------------------------------------
# Secure by default; SECURE_SSL_REDIRECT is the one knob a bare
# `docker compose up` smoke test (no TLS-terminating proxy in front) needs
# to flip off via .env — a real deployment behind a proxy/load balancer
# either leaves this on or sets SECURE_PROXY_SSL_HEADER too.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", cast=bool, default=True)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Cookies: never readable by scripts, never sent cross-site, admin sessions short.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 60 * 60 * 12

# --------------------------------------------------------------------------
# Behind a TLS-terminating reverse proxy (Caddy / nginx / a load balancer)
# --------------------------------------------------------------------------
# The proxy talks plain HTTP to gunicorn and says what the browser used in
# X-Forwarded-Proto. Without trusting that header Django thinks every request
# is insecure and SECURE_SSL_REDIRECT bounces it forever. Only enable it when a
# proxy that sets the header is really in front (never expose gunicorn directly).
if config("BEHIND_PROXY", cast=bool, default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# https origins allowed to POST to the Django admin, e.g. https://shop.example.uz
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", cast=Csv(), default="")

# The uptime check must answer over plain HTTP from inside the container.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$", r"^healthz/celery/$"]

# --------------------------------------------------------------------------
# TEMPORARY test mode: plain HTTP (no TLS) — e.g. reaching the server by IP
# before a domain / HTTPS exists. NEVER for real use: passwords and sessions
# travel unencrypted, and the camera barcode scanner does not work (browsers only
# allow the camera on HTTPS). Real deployments use HTTPS (see QOLLANMA.md).
# --------------------------------------------------------------------------
if config("ALLOW_INSECURE_HTTP", cast=bool, default=False):
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    REFRESH_COOKIE_SECURE = False

# --------------------------------------------------------------------------
# Error reporting — off unless SENTRY_DSN is set (config/observability.py)
# --------------------------------------------------------------------------
init_sentry(
    config("SENTRY_DSN", default=""),
    environment=config("SENTRY_ENVIRONMENT", default="production"),
    traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", cast=float, default=0.0),
)
