"""Error reporting (Sentry) — optional, off unless SENTRY_DSN is set.

Called from config/settings/prod.py. Same switch as the WhatsApp feature: an
empty value leaves the feature off and nothing leaves the server.
send_default_pii stays False — request bodies with customers' phone numbers
and names, and the user's IP, are not sent to a third party (TZ NFR-04/06).
"""

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration


def init_sentry(dsn: str, *, environment: str, traces_sample_rate: float = 0.0) -> bool:
    """Start Sentry for Django and Celery; return whether it was started."""
    dsn = dsn.strip()
    if not dsn:
        return False
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        send_default_pii=False,
        traces_sample_rate=traces_sample_rate,
    )
    return True
