"""Settings for running the test suite.

Swaps Postgres for an in-memory SQLite database so `manage.py test` works
without requiring CREATEDB rights on the dev Postgres role.
"""

from .dev import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
