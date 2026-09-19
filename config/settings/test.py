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
    },
}

# The manifest storage insists on `collectstatic` having been run; tests render
# admin pages (login lockout) and must not depend on that.
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
