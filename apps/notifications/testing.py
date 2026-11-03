"""Test helpers: a WhatsApp channel that never touches the network, and a clock.

FakeWhatsApp subclasses the real adapter and replaces only the HTTP call, so
the payloads the tests inspect are exactly what would be posted to Meta.
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase

from apps.debt.models import Customer
from apps.shops.models import Shop, User

from . import services
from .channels import SendResult
from .channels.whatsapp import WhatsAppCloudChannel
from .models import OutboundMessage, ShopNotificationSettings

TASHKENT = ZoneInfo("Asia/Tashkent")
APP_SECRET = "test-app-secret"  # pragma: allowlist secret


class FakeWhatsApp(WhatsAppCloudChannel):
    def __init__(self, *, configured=True, interactive=True):
        super().__init__(
            access_token="token" if configured else "",
            phone_number_id="PNID",
            api_version="v0.test",
            app_secret=APP_SECRET,
            interactive=interactive,
        )
        self.sent: list[tuple[str, dict]] = []
        self.errors: list[Exception] = []

    def _post(self, to, message):
        if self.errors:
            raise self.errors.pop(0)
        self.sent.append((to, message))
        return SendResult(external_id=f"wamid.{len(self.sent)}")

    # Convenience views of what was sent
    def templates(self) -> list[str]:
        return [m["template"]["name"] for _, m in self.sent if m["type"] == "template"]

    def template_params(self, index=-1) -> list[str]:
        sent = [m for _, m in self.sent if m["type"] == "template"][index]
        body = next(c for c in sent["template"]["components"] if c["type"] == "body")
        return [p["text"] for p in body["parameters"]]

    def texts(self) -> list[str]:
        out = []
        for _, m in self.sent:
            if m["type"] == "text":
                out.append(m["text"]["body"])
            elif m["type"] == "interactive":
                out.append(m["interactive"]["body"]["text"])
        return out


class NotificationTestCase(TestCase):
    """Shop with notifications on, an owner, a seller, a consenting customer,
    a fake channel and a clock frozen at 2026-10-13 12:00 Tashkent time."""

    start = datetime(2026, 10, 13, 12, 0, tzinfo=TASHKENT)

    def setUp(self):
        cache.clear()
        self.channel = FakeWhatsApp()
        for target in (
            "apps.notifications.services.get_channel",
            "apps.notifications.views.get_channel",
        ):
            patcher = patch(target, side_effect=lambda: self.channel)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.now = self.start
        clock = patch("django.utils.timezone.now", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)

        self.shop = Shop.objects.create(name="Baraka", phone="+998900000000")
        self.nsettings = ShopNotificationSettings.objects.create(shop=self.shop, enabled=True)
        self.owner = User.objects.create_user(
            phone="+998901112233",
            password="pass1234",  # pragma: allowlist secret
            shop=self.shop,
            full_name="Egasi",
        )
        self.seller = User.objects.create_user(
            phone="+998907778899",
            password="pass1234",  # pragma: allowlist secret
            shop=self.shop,
            full_name="Sotuvchi",
            role=User.Role.SELLER,
        )
        self.customer = self.make_customer(self.shop, "Aziz", "+998 90 123 45 67")
        services.grant_consent(self.customer, self.owner)

    # ----------------------------------------------------------- helpers

    def make_customer(self, shop, name, phone):
        return Customer.objects.create(shop=shop, full_name=name, phone=phone)

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)

    def at(self, *args):
        """Move the clock to a Tashkent wall-clock time."""
        self.now = datetime(*args, tzinfo=TASHKENT)

    def add_debt(self, amount, customer=None, due_date=None, user=None):
        from apps.debt.services import add_debt

        with self.captureOnCommitCallbacks(execute=True):
            return add_debt(
                customer=customer or self.customer,
                user=user or self.owner,
                amount=amount,
                due_date=due_date,
            )

    def add_payment(self, amount, customer=None):
        from apps.debt.services import add_payment

        with self.captureOnCommitCallbacks(execute=True):
            return add_payment(customer=customer or self.customer, user=self.owner, amount=amount)

    def flush(self):
        """What the per-minute sweeper would do now."""
        with self.captureOnCommitCallbacks(execute=True):
            return services.dispatch_due()

    def messages(self, **filters):
        return OutboundMessage.objects.filter(**filters).order_by("created_at")

    # ----------------------------------------------------------- webhook

    def signed_post(self, client, payload, secret=APP_SECRET):
        body = json.dumps(payload).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return client.post(
            "/api/whatsapp/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
        )


def inbound_payload(
    phone_digits, message_id, *, text=None, payload=None, interactive=None, timestamp=None
):
    # No timestamp -> the server's receive time is used (the frozen clock).
    message = {"from": phone_digits, "id": message_id}
    if timestamp is not None:
        message["timestamp"] = str(timestamp)
    if text is not None:
        message.update(type="text", text={"body": text})
    elif payload is not None:
        message.update(type="button", button={"payload": payload, "text": "Qoldiqni ko'rish"})
    elif interactive is not None:
        message.update(type="interactive", interactive=interactive)
    return _envelope({"messages": [message]})


def status_payload(external_id, status, timestamp=1791900000, errors=None):
    event = {"id": external_id, "status": status, "timestamp": str(timestamp), "recipient_id": "x"}
    if errors:
        event["errors"] = errors
    return _envelope({"statuses": [event]})


def _envelope(value):
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "PNID"}, **value}
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": value}]}],
    }
