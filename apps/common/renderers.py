"""Wraps every successful response as {"data": ..., "error": null} (TZ v2 8.1).

Error responses already come out of apps.common.exceptions.exception_handler
in that exact shape, so only status < 400 gets wrapped here — otherwise an
error would end up double-nested as {"data": {"data": null, "error": {...}}}.
"""
from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get("response")
        already_wrapped = isinstance(data, dict) and {"data", "error"} <= set(data)

        if response is not None and response.status_code < 400 and not already_wrapped:
            data = {"data": data, "error": None}

        return super().render(data, accepted_media_type, renderer_context)
