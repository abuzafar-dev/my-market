"""Production settings."""

from decouple import Csv, config

from .base import *  # noqa: F403

DEBUG = False

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
X_FRAME_OPTIONS = "DENY"
