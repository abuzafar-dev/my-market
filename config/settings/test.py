"""Settings for running the test suite.

Swaps Postgres for an in-memory SQLite database so `manage.py test` works
without requiring CREATEDB rights on the dev Postgres role.
"""

import logging

from .dev import *  # noqa: F403

# Tests deliberately trigger 4xx/5xx and business events; keep output clean.
logging.disable(logging.CRITICAL)

# Rate limits are not what most tests are about, and every test shares one
# process-wide cache — keep them out of the way. Tests that check throttling
# patch the class attribute themselves (see apps/common/tests.py).
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        **REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        "anon": "100000/min",
        "user": "100000/min",
        "login": "100000/min",
        "exports": "100000/min",
        "reminders": "100000/min",
    },
}

# The manifest storage insists on `collectstatic` having been run; tests render
# admin pages (login lockout) and must not depend on that.
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Tasks run inline, in the calling process, so the suite needs no broker and
# no worker. The task writes the same job states either way, so tests still
# see the whole lifecycle.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "my-market-test",
    }
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# WhatsApp is always mocked in tests (see apps/notifications/testing.py);
# whatever is in the developer's .env must never reach Meta from a test run.
WHATSAPP_ACCESS_TOKEN = ""
WHATSAPP_PHONE_NUMBER_ID = ""
WHATSAPP_APP_SECRET = "test-app-secret"  # pragma: allowlist secret
WHATSAPP_VERIFY_TOKEN = "test-verify-token"
WHATSAPP_API_VERSION = ""
WHATSAPP_API_BASE = "http://whatsapp.invalid"
