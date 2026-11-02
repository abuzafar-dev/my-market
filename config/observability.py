"""Error reporting (Sentry) — optional, off unless SENTRY_DSN is set.

Called from config/settings/prod.py. Same switch as the WhatsApp feature: an
empty value leaves the feature off and nothing leaves the server.

Customers' phone numbers and names must not reach a third party (TZ NFR-04).
send_default_pii=False alone does not ensure that, so the SDK is also told:
  * max_request_body_size="never" — no POST bodies (a new customer, a debt sale);
  * include_local_variables=False — no stack-frame locals (``customer``,
    ``validated_data``);
  * before_send=scrub_event — no query string (``?search=+99890…``), cookies
    or parsed body, whatever an integration attached.
The stack trace, URL path, method, user id and request id are enough to act on.
"""

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

_REQUEST_KEYS_KEPT = {"url", "method", "headers", "env"}


def scrub_event(event: dict, hint: dict) -> dict:
    """Sentry before_send: keep only the non-personal parts of ``request``."""
    request = event.get("request")
    if isinstance(request, dict):
        event["request"] = {k: v for k, v in request.items() if k in _REQUEST_KEYS_KEPT}
    return event


def parse_sample_rate(value: str) -> float:
    """SENTRY_TRACES_SAMPLE_RATE; blank means 0 (a bare ``float("")`` would
    crash backend, worker and beat at start-up)."""
    value = value.strip()
    return float(value) if value else 0.0


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
        max_request_body_size="never",
        include_local_variables=False,
        before_send=scrub_event,
        traces_sample_rate=traces_sample_rate,
    )
    return True
