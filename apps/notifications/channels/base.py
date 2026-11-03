"""What the notification logic needs from a messaging channel.

Business code (services, bot, tasks) talks only to this interface; the
WhatsApp Cloud API specifics live in whatsapp.py. Another channel (SMS,
Telegram) would be one more adapter implementing the same methods.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SendResult:
    external_id: str


# ChannelError.code for a send whose outcome is not known: the request may
# have reached the provider. Never retried automatically (see services.deliver).
SEND_UNKNOWN = "send_unknown"


class ChannelError(Exception):
    """A send the provider refused or that never reached it.

    ``retryable`` decides what happens next: transient problems (provider
    outage, rate limit, network) are retried with backoff; permanent ones
    (number not on WhatsApp, template missing, bad token) are not, because
    repeating the same request can only fail the same way."""

    def __init__(self, code: str, detail: str = "", *, retryable: bool):
        super().__init__(code)
        self.code = code
        self.detail = detail[:255]
        self.retryable = retryable


@dataclass(frozen=True)
class InboundEvent:
    message_id: str
    from_phone: str  # E.164
    message_type: str
    text: str = ""
    payload: str = ""  # id of the pressed quick-reply / list row
    timestamp: datetime | None = None


@dataclass(frozen=True)
class StatusEvent:
    message_id: str
    status: str  # sent | delivered | read | failed
    timestamp: datetime | None = None
    error_code: str = ""
    error_title: str = ""


@dataclass
class WebhookBatch:
    messages: list[InboundEvent] = field(default_factory=list)
    statuses: list[StatusEvent] = field(default_factory=list)


@dataclass(frozen=True)
class ListRow:
    id: str
    title: str
    description: str = ""


class NotificationChannel(ABC):
    name: str = ""
    # Can it show buttons / pick-lists? The bot falls back to numbered text
    # when it cannot (see bot.py).
    supports_interactive: bool = False

    @abstractmethod
    def is_configured(self) -> bool:
        """Every credential needed to send is present."""

    @abstractmethod
    def send_template(
        self, to: str, template: str, language: str, params: list[str], *, quick_reply: str = ""
    ) -> SendResult:
        """A pre-approved template — the only kind of message a business may
        start a conversation with."""

    @abstractmethod
    def send_text(self, to: str, body: str) -> SendResult:
        """Free text — only as a reply inside the customer-service window."""

    def send_buttons(self, to: str, body: str, buttons: list[ListRow]) -> SendResult:
        raise NotImplementedError

    def send_list(self, to: str, body: str, button: str, rows: list[ListRow]) -> SendResult:
        raise NotImplementedError

    @abstractmethod
    def parse_webhook(self, payload: dict) -> WebhookBatch:
        """Turn the provider's webhook body into channel-neutral events.
        Must never raise on odd or partial payloads — unknown parts are skipped."""
