"""Local development settings."""

from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "10.183.211.58"]

# runserver_plus (django-extensions) — lets the dev server speak HTTPS via a
# self-signed cert, so secure-context-only browser APIs (camera, BarcodeDetector)
# work when opened from a phone over the LAN, not just at http://localhost.
INSTALLED_APPS = INSTALLED_APPS + ["django_extensions"]
