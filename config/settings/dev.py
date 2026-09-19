"""Local development settings."""

from decouple import config

from .base import *  # noqa: F403

DEBUG = True
REFRESH_COOKIE_SECURE = False

# The current developer's LAN IP, for opening the app from a phone on the
# same Wi-Fi — goes stale on a different network or a different developer's
# machine, so it's an env var (see QOLLANMA.md's `hostname -I` note) rather
# than hardcoded, with today's value kept as the local default.
DEV_LAN_HOST = config("DEV_LAN_HOST", default="10.183.211.58")

ALLOWED_HOSTS = ["localhost", "127.0.0.1", DEV_LAN_HOST]

# runserver_plus (django-extensions) — lets the dev server speak HTTPS via a
# self-signed cert, so secure-context-only browser APIs (camera, BarcodeDetector)
# work when opened from a phone over the LAN, not just at http://localhost.
INSTALLED_APPS = INSTALLED_APPS + ["django_extensions"]
