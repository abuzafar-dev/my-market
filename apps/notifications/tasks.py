"""Celery tasks for WhatsApp notifications.

All of them are safe to run more than once (acks_late + at-least-once
delivery): sending claims the row first, inbound handling claims the message
first, and scheduling relies on unique idempotency keys.
"""

from celery import shared_task

from . import bot, services
from .channels import StatusEvent


@shared_task(ignore_result=True)
def send_message(message_id: str) -> str:
    return services.deliver(message_id)


@shared_task(ignore_result=True)
def dispatch_due_messages() -> int:
    return services.dispatch_due()


@shared_task(ignore_result=True)
def schedule_debt_reminders() -> int:
    return services.schedule_reminders()


@shared_task(ignore_result=True)
def process_inbound_message(inbound_id: str) -> str:
    return bot.handle(inbound_id)


@shared_task(ignore_result=True, max_retries=1, default_retry_delay=60)
def apply_status_later(event: dict) -> bool:
    """A status that arrived before the send was recorded (Meta can be faster
    than our commit) gets one more try a minute later."""
    from datetime import datetime

    timestamp = event.get("timestamp")
    return services.apply_status(
        StatusEvent(
            message_id=event["message_id"],
            status=event["status"],
            timestamp=datetime.fromisoformat(timestamp) if timestamp else None,
            error_code=event.get("error_code", ""),
            error_title=event.get("error_title", ""),
        )
    )
