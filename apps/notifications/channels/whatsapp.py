"""WhatsApp Cloud API adapter.

Only the standard library is used for HTTP — one JSON POST per message does
not justify a new dependency. Nothing here logs a token, a message body or an
unmasked number.

The Graph API version is never assumed: it comes from WHATSAPP_API_VERSION,
which the operator sets to a version Meta currently supports (see
docs/WHATSAPP.md). Without it the channel reports itself unconfigured.
"""

import hashlib
import hmac
import http.client
import json
import logging
from datetime import UTC, datetime
from urllib.parse import urlsplit

from django.conf import settings

from ..phone import mask, to_e164
from .base import (
    SEND_UNKNOWN,
    ChannelError,
    InboundEvent,
    ListRow,
    NotificationChannel,
    SendResult,
    StatusEvent,
    WebhookBatch,
)

logger = logging.getLogger(__name__)

# Meta error codes that are worth retrying later (rate limits, outages).
# https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes
TRANSIENT_CODES = {
    "1",  # API unknown
    "2",  # API service
    "4",  # app rate limit
    "17",  # user rate limit
    "341",  # application limit
    "80007",  # WABA rate limit
    "130429",  # throughput limit
    "131000",  # something went wrong
    "131016",  # service unavailable
    "131048",  # spam rate limit
    "131056",  # pair rate limit
    "133004",  # server temporarily unavailable
}
# Ones that will fail the same way however often they are repeated. Anything
# not listed falls back to the HTTP status (5xx/429 transient, else permanent).
PERMANENT_CODES = {
    "100",  # invalid parameter
    "131008",  # required parameter missing
    "131009",  # parameter value invalid
    "131026",  # message undeliverable (not a WhatsApp user, old app...)
    "131030",  # recipient not in allowed list (test number)
    "131031",  # account locked
    "131045",  # phone number not registered
    "131047",  # re-engagement: outside the 24h window, use a template
    "131051",  # unsupported message type
    "132000",  # template parameter count mismatch
    "132001",  # template does not exist / not approved
    "132005",  # translated text too long
    "132007",  # template format policy violation
    "132012",  # template parameter format mismatch
    "132015",  # template paused
    "132016",  # template disabled
    "133010",  # phone number not registered
    "190",  # access token expired / invalid
    "368",  # temporarily blocked for policy violations
}

TIMEOUT_SECONDS = 15


class WhatsAppCloudChannel(NotificationChannel):
    name = "whatsapp"

    def __init__(
        self,
        *,
        access_token: str,
        phone_number_id: str,
        api_version: str,
        app_secret: str = "",
        api_base: str = "https://graph.facebook.com",
        interactive: bool = True,
    ):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.api_version = api_version
        self.app_secret = app_secret
        self.api_base = api_base.rstrip("/")
        self.supports_interactive = interactive

    @classmethod
    def from_settings(cls) -> WhatsAppCloudChannel:
        return cls(
            access_token=settings.WHATSAPP_ACCESS_TOKEN,
            phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID,
            api_version=settings.WHATSAPP_API_VERSION,
            app_secret=settings.WHATSAPP_APP_SECRET,
            api_base=settings.WHATSAPP_API_BASE,
            interactive=settings.WHATSAPP_INTERACTIVE,
        )

    def is_configured(self) -> bool:
        return bool(self.access_token and self.phone_number_id and self.api_version)

    # ------------------------------------------------------------------ send

    def send_template(self, to, template, language, params, *, quick_reply=""):
        components = []
        if params:
            components.append(
                {"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}
            )
        if quick_reply:
            # Only valid when the approved template really has a quick-reply
            # button at index 0; the payload comes back in the webhook.
            components.append(
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": "0",
                    "parameters": [{"type": "payload", "payload": quick_reply}],
                }
            )
        template_body = {"name": template, "language": {"code": language}}
        if components:
            template_body["components"] = components
        return self._post(to, {"type": "template", "template": template_body})

    def send_text(self, to, body):
        return self._post(to, {"type": "text", "text": {"body": body, "preview_url": False}})

    def send_buttons(self, to, body, buttons: list[ListRow]):
        return self._post(
            to,
            {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": body},
                    "action": {
                        "buttons": [
                            {"type": "reply", "reply": {"id": b.id, "title": b.title[:20]}}
                            for b in buttons[:3]
                        ]
                    },
                },
            },
        )

    def send_list(self, to, body, button, rows: list[ListRow]):
        return self._post(
            to,
            {
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "body": {"text": body},
                    "action": {
                        "button": button[:20],
                        "sections": [
                            {
                                "title": button[:24],
                                "rows": [
                                    {
                                        "id": r.id,
                                        "title": r.title[:24],
                                        **(
                                            {"description": r.description[:72]}
                                            if r.description
                                            else {}
                                        ),
                                    }
                                    for r in rows[:10]
                                ],
                            }
                        ],
                    },
                },
            },
        )

    def _post(self, to: str, message: dict) -> SendResult:
        """One POST to Meta, with every failure sorted by what it tells us.

        * Before a byte is sent (DNS, refused, TLS handshake, connect timeout)
          -> retryable "network": Meta cannot have seen it.
        * Meta answered with an error -> classified by its code/status.
        * After the request started going out (write error, read timeout,
          connection reset, unreadable answer, 2xx without a message id)
          -> "send_unknown", not retryable: Meta may already have delivered
          it, and the Cloud API has no idempotency key to make a retry safe.
          The message is kept in the UNKNOWN status for an operator to check.

        http.client is used rather than urllib because urllib folds connect
        and send errors into one URLError, which hides exactly that line.
        """
        if not self.is_configured():
            raise ChannelError(
                "not_configured", "WhatsApp credentials are not set", retryable=False
            )
        url = urlsplit(f"{self.api_base}/{self.api_version}/{self.phone_number_id}/messages")
        body = json.dumps(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to.lstrip("+"),
                **message,
            }
        ).encode()
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        connection_class = (
            http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
        )
        connection = connection_class(url.hostname, url.port, timeout=TIMEOUT_SECONDS)
        try:
            try:
                connection.connect()
            except OSError as exc:
                raise ChannelError("network", type(exc).__name__, retryable=True) from None
            try:
                connection.request("POST", url.path, body=body, headers=headers)
                response = connection.getresponse()
                status, raw = response.status, response.read()
            except (OSError, http.client.HTTPException) as exc:
                raise ChannelError(
                    SEND_UNKNOWN,
                    f"{type(exc).__name__} after the request was sent",
                    retryable=False,
                ) from None
        finally:
            connection.close()

        if status >= 300:
            raise self._error_from_response(status, raw)
        try:
            external_id = json.loads(raw or b"{}")["messages"][0]["id"]
            if not isinstance(external_id, str) or not external_id:
                raise TypeError
        except ValueError, KeyError, IndexError, TypeError:
            raise ChannelError(
                SEND_UNKNOWN, f"HTTP {status} without a readable message id", retryable=False
            ) from None
        logger.info("whatsapp send accepted type=%s to=%s", message.get("type"), mask(to))
        return SendResult(external_id=external_id)

    @staticmethod
    def _error_from_response(status: int, raw: bytes) -> ChannelError:
        try:
            error = json.loads(raw or b"{}").get("error", {})
            if not isinstance(error, dict):
                error = {}
        except ValueError, AttributeError:
            error = {}
        code = str(error.get("code", "") or "")
        details = error.get("error_data") if isinstance(error.get("error_data"), dict) else {}
        title = str(details.get("details") or error.get("message") or "")
        if code in TRANSIENT_CODES:
            retryable = True
        elif code in PERMANENT_CODES:
            retryable = False
        else:
            retryable = status >= 500 or status == 429
        return ChannelError(code or f"http_{status}", title, retryable=retryable)

    # --------------------------------------------------------------- webhook

    def verify_signature(self, raw_body: bytes, header: str | None) -> bool:
        """X-Hub-Signature-256: "sha256=" + hex HMAC-SHA256 of the raw body,
        keyed with the app secret. Compared in constant time."""
        if not self.app_secret or not header or not header.startswith("sha256="):
            return False
        expected = hmac.new(self.app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, header.removeprefix("sha256="))

    def parse_webhook(self, payload) -> WebhookBatch:
        batch = WebhookBatch()
        if not isinstance(payload, dict):
            return batch
        for entry in _as_list(payload.get("entry")):
            for change in _as_list(_get(entry, "changes")):
                if _get(change, "field") != "messages":
                    continue
                value = _get(change, "value")
                if not isinstance(value, dict):
                    continue
                # One Meta app can serve several numbers; act only on ours.
                metadata_id = str(_get(_get(value, "metadata"), "phone_number_id") or "")
                if self.phone_number_id and metadata_id and metadata_id != self.phone_number_id:
                    continue
                for raw in _as_list(value.get("messages")):
                    event = self._parse_message(raw)
                    if event:
                        batch.messages.append(event)
                for raw in _as_list(value.get("statuses")):
                    event = self._parse_status(raw)
                    if event:
                        batch.statuses.append(event)
        return batch

    @staticmethod
    def _parse_message(raw) -> InboundEvent | None:
        if not isinstance(raw, dict):
            return None
        message_id = raw.get("id")
        phone = to_e164(str(raw.get("from") or ""))
        if not isinstance(message_id, str) or not message_id or not phone:
            return None
        message_type = str(raw.get("type") or "unknown")[:20]
        text = payload = ""
        if message_type == "text":
            text = str(_get(_get(raw, "text"), "body") or "")
        elif message_type == "button":  # quick reply on a template
            button = _get(raw, "button")
            payload = str(_get(button, "payload") or "")
            text = str(_get(button, "text") or "")
        elif message_type == "interactive":
            interactive = _get(raw, "interactive")
            reply = _get(interactive, "button_reply") or _get(interactive, "list_reply")
            payload = str(_get(reply, "id") or "")
            text = str(_get(reply, "title") or "")
        return InboundEvent(
            message_id=message_id[:128],
            from_phone=phone,
            message_type=message_type,
            text=text[:512],
            payload=payload[:128],
            timestamp=_timestamp(raw.get("timestamp")),
        )

    @staticmethod
    def _parse_status(raw) -> StatusEvent | None:
        if not isinstance(raw, dict):
            return None
        message_id = raw.get("id")
        status = raw.get("status")
        if not isinstance(message_id, str) or status not in {"sent", "delivered", "read", "failed"}:
            return None
        errors = _as_list(raw.get("errors"))
        first_error = errors[0] if errors and isinstance(errors[0], dict) else {}
        return StatusEvent(
            message_id=message_id[:128],
            status=status,
            timestamp=_timestamp(raw.get("timestamp")),
            error_code=str(first_error.get("code") or "")[:40],
            error_title=str(first_error.get("title") or "")[:255],
        )


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _get(value, key):
    return value.get(key) if isinstance(value, dict) else None


def _timestamp(value) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except TypeError, ValueError, OverflowError, OSError:
        return None
