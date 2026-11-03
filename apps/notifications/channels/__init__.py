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


def get_channel() -> NotificationChannel:
    """The channel in use. Only WhatsApp exists today; tests patch this."""
    from .whatsapp import WhatsAppCloudChannel

    return WhatsAppCloudChannel.from_settings()


__all__ = [
    "SEND_UNKNOWN",
    "ChannelError",
    "InboundEvent",
    "ListRow",
    "NotificationChannel",
    "SendResult",
    "StatusEvent",
    "WebhookBatch",
    "get_channel",
]
