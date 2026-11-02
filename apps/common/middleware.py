"""Request ID: one per request, in the X-Request-ID response header and in
every log line written while the request is handled."""

import re
import uuid

import sentry_sdk

from apps.common.logging import request_id_var

HEADER = "X-Request-ID"
# An ID from a proxy in front (Caddy, nginx) is kept so both logs line up — but
# only a plain token: anything else (a newline, a megabyte) would let a client
# write fake lines into the log.
_VALID = re.compile(r"[A-Za-z0-9-]{8,64}")


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get(HEADER, "")
        request_id = incoming if _VALID.fullmatch(incoming) else uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_var.set(request_id)
        sentry_sdk.set_tag("request_id", request_id)  # no-op while Sentry is off
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[HEADER] = request_id
        return response
