"""Webhook security, inbound commands, multi-shop selection and status sync."""

import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, override_settings

from apps.shops.models import Shop

from . import services
from .models import InboundMessage, OutboundMessage, ShopNotificationSettings
from .testing import (
    FakeWhatsApp,
    NotificationTestCase,
    inbound_payload,
    status_payload,
)

Status = OutboundMessage.Status
URL = "/api/whatsapp/webhook/"


class VerificationTests(NotificationTestCase):
    def test_correct_token_returns_the_challenge(self):
        response = Client().get(
            URL,
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token",
                "hub.challenge": "42",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"42")

    def test_wrong_or_missing_token_is_refused(self):
        for params in [
            {"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"},
            {"hub.mode": "subscribe", "hub.challenge": "42"},
            {"hub.mode": "unsubscribe", "hub.verify_token": "test-verify-token"},
        ]:
            self.assertEqual(Client().get(URL, params).status_code, 403)

    @override_settings(WHATSAPP_VERIFY_TOKEN="")
    def test_unconfigured_verify_token_refuses_everything(self):
        response = Client().get(URL, {"hub.mode": "subscribe", "hub.verify_token": ""})
        self.assertEqual(response.status_code, 403)


class SignatureTests(NotificationTestCase):
    def test_invalid_signature_is_403_and_nothing_is_stored(self):
        payload = inbound_payload("998901234567", "wamid.x", text="qarz")
        for header in [None, "sha256=deadbeef", "md5=abc"]:
            extra = {"HTTP_X_HUB_SIGNATURE_256": header} if header else {}
            response = Client().post(
                URL, data=json.dumps(payload), content_type="application/json", **extra
            )
            self.assertEqual(response.status_code, 403)
        response = self.signed_post(Client(), payload, secret="other")  # pragma: allowlist secret
        self.assertEqual(response.status_code, 403)
        self.assertFalse(InboundMessage.objects.exists())

    def test_body_altered_after_signing_is_rejected(self):
        import hashlib
        import hmac

        body = json.dumps(inbound_payload("998901234567", "wamid.x", text="qarz")).encode()
        signature = hmac.new(b"test-app-secret", body, hashlib.sha256).hexdigest()
        response = Client().post(
            URL,
            data=body.replace(b"qarz", b"stop"),
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
        )
        self.assertEqual(response.status_code, 403)

    def test_repeated_bad_signatures_are_rate_limited(self):
        client = Client()
        for _ in range(30):
            client.post(URL, data="{}", content_type="application/json")
        response = client.post(URL, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 429)

    @override_settings(WHATSAPP_APP_SECRET="")
    def test_missing_app_secret_refuses_all_posts(self):
        self.channel = FakeWhatsApp()
        self.channel.app_secret = ""
        response = self.signed_post(Client(), inbound_payload("998901234567", "w", text="qarz"))
        self.assertEqual(response.status_code, 403)

    def test_malformed_but_signed_payloads_do_not_crash(self):
        for payload in [
            [],
            {},
            {"entry": "x"},
            {"entry": [{"changes": [{"field": "messages", "value": None}]}]},
            {"entry": [{"changes": [{"field": "messages", "value": {"messages": [1, None]}}]}]},
            {"entry": [{"changes": [{"field": "messages", "value": {"messages": [{"id": "a"}]}}]}]},
            {"entry": [{"changes": [{"field": "messages", "value": {"statuses": [{"id": 5}]}}]}]},
            {"entry": [{"changes": [{"field": "account_update", "value": {}}]}]},
        ]:
            self.assertEqual(self.signed_post(Client(), payload).status_code, 200, payload)
        self.assertFalse(InboundMessage.objects.exists())

    def test_invalid_json_with_valid_signature_is_400(self):
        import hashlib
        import hmac

        body = b"not json"
        signature = hmac.new(b"test-app-secret", body, hashlib.sha256).hexdigest()
        response = Client().post(
            URL,
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
        )
        self.assertEqual(response.status_code, 400)

    def test_events_for_another_business_number_are_ignored(self):
        payload = inbound_payload("998901234567", "wamid.x", text="qarz")
        payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "OTHER"
        self.assertEqual(self.signed_post(Client(), payload).status_code, 200)
        self.assertFalse(InboundMessage.objects.exists())


class InboundTests(NotificationTestCase):
    def setUp(self):
        super().setUp()
        self.web = Client()
        self.n = 0

    def say(self, text=None, phone="998901234567", **kwargs):
        self.n += 1
        payload = inbound_payload(phone, f"wamid.in{self.n}", text=text, **kwargs)
        return self.signed_post(self.web, payload)

    def test_balance_shows_total_and_last_five_operations(self):
        for amount in [10_000, 20_000, 30_000, 40_000, 50_000]:
            self.add_debt(amount)
            self.advance(minutes=1)
        self.add_payment(15_000)
        self.say("  QARZ ")
        reply = self.channel.texts()[-1]
        self.assertIn("*Baraka* do'koni", reply)
        self.assertIn("135 000 so'm", reply)
        self.assertIn("To'lov −15 000 so'm", reply)
        self.assertNotIn("+10 000", reply)  # oldest of six: not in the last five
        self.assertEqual(reply.count(" — "), 5)
        self.assertIn("STOP", reply)

    def test_balance_button_and_qoldiq(self):
        self.add_debt(10_000)
        self.say(payload="BALANCE")
        self.say("Qoldiq")
        self.say(
            interactive={"type": "button_reply", "button_reply": {"id": "BALANCE", "title": "x"}}
        )
        self.assertEqual(sum("10 000 so'm" in t for t in self.channel.texts()), 3)

    def test_duplicate_webhook_delivery_is_processed_once(self):
        payload = inbound_payload("998901234567", "wamid.same", text="qarz")
        self.signed_post(self.web, payload)
        self.signed_post(self.web, payload)
        self.assertEqual(InboundMessage.objects.count(), 1)
        self.assertEqual(len(self.channel.sent), 1)
        self.assertEqual(InboundMessage.objects.get().status, InboundMessage.Status.PROCESSED)

    def test_queue_outage_returns_503_and_the_redelivery_is_processed(self):
        payload = inbound_payload("998901234567", "wamid.q", text="qarz")
        with patch(
            "apps.notifications.views.process_inbound_message.delay",
            side_effect=ConnectionError("redis down"),
        ):
            self.assertEqual(self.signed_post(self.web, payload).status_code, 503)
        self.assertEqual(InboundMessage.objects.get().status, InboundMessage.Status.RECEIVED)
        self.assertEqual(self.signed_post(self.web, payload).status_code, 200)
        self.assertEqual(len(self.channel.sent), 1)

    def test_unregistered_number(self):
        self.say("qarz", phone="998935550000")
        self.assertIn("ro'yxatdan o'tmagan", self.channel.texts()[-1])

    def test_unregistered_number_gets_not_registered_instead_of_the_menu(self):
        self.say("salom", phone="998935550000")
        self.assertIn("ro'yxatdan o'tmagan", self.channel.texts()[-1])
        self.assertEqual(self.channel.sent[-1][1]["type"], "text")

    def test_number_in_a_shop_that_has_notifications_off_is_not_shown(self):
        ShopNotificationSettings.objects.filter(shop=self.shop).update(enabled=False)
        self.say("qarz")
        self.assertIn("ro'yxatdan o'tmagan", self.channel.texts()[-1])

    def test_unknown_command_gets_the_help_menu_with_a_button(self):
        self.say("salom")
        _, message = self.channel.sent[-1]
        self.assertEqual(message["type"], "interactive")
        self.assertIn("qoldiq", message["interactive"]["body"]["text"])
        button = message["interactive"]["action"]["buttons"][0]["reply"]
        self.assertEqual(button, {"id": "BALANCE", "title": "Qoldiqni ko'rish"})

    def test_text_fallback_when_interactive_is_off(self):
        self.channel = FakeWhatsApp(interactive=False)
        self.say("salom")
        self.assertEqual(self.channel.sent[-1][1]["type"], "text")

    def test_media_message_gets_help(self):
        payload = inbound_payload("998901234567", "wamid.img")
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
        self.signed_post(self.web, payload)
        self.assertIn("qoldiq", self.channel.texts()[-1])
        self.assertEqual(InboundMessage.objects.get().text, "")


class MultiShopTests(NotificationTestCase):
    def setUp(self):
        super().setUp()
        self.web = Client()
        self.n = 0
        self.other = Shop.objects.create(name="Nur", phone="+998900000001")
        ShopNotificationSettings.objects.create(shop=self.other, enabled=True)
        self.twin = self.make_customer(self.other, "Aziz N.", "998901234567")
        services.grant_consent(self.twin, self.owner)
        # A third shop knows the number but never linked it to WhatsApp.
        third = Shop.objects.create(name="Zamon", phone="+998900000002")
        ShopNotificationSettings.objects.create(shop=third, enabled=True)
        self.unlinked = self.make_customer(third, "Aziz Z.", "+998901234567")
        self.add_debt(11_000)
        self.add_debt(22_000, customer=self.twin)
        self.add_debt(33_000, customer=self.unlinked)

    def say(self, text=None, **kwargs):
        self.n += 1
        payload = inbound_payload("998901234567", f"wamid.m{self.n}", text=text, **kwargs)
        return self.signed_post(self.web, payload)

    def test_asks_which_shop_and_lists_only_linked_ones(self):
        self.say("qarz")
        _, message = self.channel.sent[-1]
        rows = message["interactive"]["action"]["sections"][0]["rows"]
        self.assertEqual([r["title"] for r in rows], ["Baraka", "Nur"])
        self.assertNotIn("Zamon", json.dumps(message))
        self.assertNotIn("so'm", message["interactive"]["body"]["text"])  # no amounts yet

    def test_choosing_a_shop_shows_only_that_shops_records(self):
        self.say("qarz")
        self.say(interactive={"type": "list_reply", "list_reply": {"id": "shop:2", "title": "Nur"}})
        reply = self.channel.texts()[-1]
        self.assertIn("*Nur* do'koni", reply)
        self.assertIn("22 000", reply)
        self.assertNotIn("11 000", reply)
        self.assertNotIn("33 000", reply)

        # The choice is used up.
        self.say("1")
        self.assertIn("qoldiq", self.channel.texts()[-1])

    def test_typed_number_works_as_a_text_fallback(self):
        self.channel = FakeWhatsApp(interactive=False)
        self.say("qarz")
        self.assertIn("1. Baraka\n2. Nur", self.channel.texts()[-1])
        self.say(" 1 ")
        self.assertIn("11 000", self.channel.texts()[-1])

    def test_invalid_choice(self):
        self.say("qarz")
        self.say("7")
        self.assertIn("Bunday tanlov yo'q", self.channel.texts()[-1])
        self.say("0")
        self.assertIn("Bunday tanlov yo'q", self.channel.texts()[-1])

    def test_choice_expires_after_ten_minutes(self):
        self.say("qarz")
        cache.clear()  # what the 10-minute TTL does
        self.say("2")
        self.assertIn("qoldiq", self.channel.texts()[-1])
        self.assertNotIn("22 000", self.channel.texts()[-1])

    def test_a_shop_unlinked_after_the_menu_is_refused(self):
        self.say("qarz")
        services.revoke_consent(self.twin, self.owner)  # staff removed the link
        self.say("2")
        self.assertNotIn("22 000", self.channel.texts()[-1])


class StatusTests(NotificationTestCase):
    def setUp(self):
        super().setUp()
        self.add_debt(10_000)
        self.advance(minutes=10)
        self.flush()
        self.message = OutboundMessage.objects.get()
        self.web = Client()

    def status(self, status, timestamp=1791900000, **kwargs):
        self.signed_post(self.web, status_payload("wamid.1", status, timestamp, **kwargs))
        self.message.refresh_from_db()
        return self.message.status

    def test_sent_delivered_read(self):
        self.assertEqual(self.status("delivered", 1791900010), Status.DELIVERED)
        self.assertIsNotNone(self.message.delivered_at)
        self.assertEqual(self.status("read", 1791900020), Status.READ)
        self.assertIsNotNone(self.message.read_at)

    def test_out_of_order_and_duplicate_events_never_go_backwards(self):
        self.assertEqual(self.status("read"), Status.READ)
        self.assertEqual(self.status("delivered"), Status.READ)
        self.assertIsNotNone(self.message.delivered_at)  # timestamp still recorded
        self.assertEqual(self.status("sent"), Status.READ)
        self.assertEqual(self.status("read"), Status.READ)
        self.assertEqual(self.status("failed", errors=[{"code": 131026}]), Status.READ)

    def test_failed_is_final(self):
        self.assertEqual(
            self.status("failed", errors=[{"code": 131026, "title": "Undeliverable"}]),
            Status.FAILED,
        )
        self.assertEqual(self.message.error_code, "wa_131026")
        self.assertEqual(self.status("delivered"), Status.FAILED)

    def test_unknown_message_id_is_retried_once_later_without_error(self):
        with patch("apps.notifications.views.apply_status_later.apply_async") as later:
            response = self.signed_post(self.web, status_payload("wamid.unknown", "delivered"))
        self.assertEqual(response.status_code, 200)
        later.assert_called_once()


class WebhookLimitTests(NotificationTestCase):
    def setUp(self):
        super().setUp()
        self.web = Client()
        self.n = 0

    def say(self, text):
        self.n += 1
        return self.signed_post(
            self.web, inbound_payload("998901234567", f"wamid.l{self.n}", text=text)
        )

    def test_a_flood_of_bad_signatures_never_blocks_correctly_signed_deliveries(self):
        from .views import BAD_SIGNATURE_LIMIT

        body = json.dumps(inbound_payload("998901234567", "wamid.bad", text="qarz"))
        codes = [
            Client()
            .post(
                URL,
                data=body,
                content_type="application/json",
                HTTP_X_HUB_SIGNATURE_256="sha256=00",
            )
            .status_code
            for _ in range(BAD_SIGNATURE_LIMIT + 3)
        ]
        self.assertEqual(codes[:BAD_SIGNATURE_LIMIT], [403] * BAD_SIGNATURE_LIMIT)
        self.assertEqual(set(codes[BAD_SIGNATURE_LIMIT:]), {429})
        # Same client address (e.g. everything seen as the proxy): Meta still gets in.
        self.assertEqual(self.say("qarz").status_code, 200)
        self.assertEqual(InboundMessage.objects.count(), 1)

    def test_wrong_verify_tokens_count_towards_the_limit(self):
        from .views import BAD_SIGNATURE_LIMIT

        params = {"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "c"}
        codes = [Client().get(URL, params).status_code for _ in range(BAD_SIGNATURE_LIMIT + 1)]
        self.assertEqual(codes[-1], 429)
        self.assertEqual(codes[0], 403)

    def test_oversized_body_is_refused_before_reading(self):
        from .views import MAX_WEBHOOK_BODY

        response = Client().post(
            URL,
            data=b"x" * (MAX_WEBHOOK_BODY + 1),
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=00",
        )
        self.assertEqual(response.status_code, 413)

    def padded(self, size):
        """A real inbound payload padded (in a field the parser ignores) to
        exactly ``size`` bytes of JSON."""
        payload = inbound_payload("998901234567", "wamid.big", text="qarz")
        value = payload["entry"][0]["changes"][0]["value"]
        value["padding"] = ""
        base = len(json.dumps(payload).encode())
        value["padding"] = "x" * (size - base)
        self.assertEqual(len(json.dumps(payload).encode()), size)
        return payload

    def test_a_signed_payload_of_metas_documented_maximum_is_accepted(self):
        # Meta: "Webhook payloads can be up to 3 MB" — above Django's
        # app-wide 2.5 MB DATA_UPLOAD_MAX_MEMORY_SIZE.
        response = self.signed_post(self.web, self.padded(3 * 1024 * 1024))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(InboundMessage.objects.get().wa_message_id, "wamid.big")
        self.assertEqual(InboundMessage.objects.get().status, InboundMessage.Status.PROCESSED)
        self.assertIn("*Baraka* do'koni", self.channel.texts()[-1])  # balance reply sent

    def test_body_at_the_limit_is_read_and_checked_not_refused_for_size(self):
        from .views import MAX_WEBHOOK_BODY

        response = self.signed_post(self.web, self.padded(MAX_WEBHOOK_BODY))
        self.assertEqual(response.status_code, 200)

    def test_body_over_the_limit_is_413_even_when_signed(self):
        from .views import MAX_WEBHOOK_BODY

        response = self.signed_post(self.web, self.padded(MAX_WEBHOOK_BODY + 1))
        self.assertEqual(response.status_code, 413)
        self.assertFalse(InboundMessage.objects.exists())

    def test_replies_per_number_are_capped_but_stop_always_works(self):
        from .bot import REPLY_LIMIT

        for _ in range(REPLY_LIMIT + 5):
            self.assertEqual(self.say("qarz").status_code, 200)  # Meta always gets 200
        self.assertEqual(len(self.channel.texts()), REPLY_LIMIT)
        self.assertEqual(InboundMessage.objects.count(), REPLY_LIMIT + 5)
        self.assertFalse(
            InboundMessage.objects.exclude(status=InboundMessage.Status.PROCESSED).exists()
        )

        self.say("STOP")
        self.assertFalse(services.current_consent(self.customer))
        self.assertIn("obunadan chiqdingiz", self.channel.texts()[-1])

        cache.clear()  # the window has passed
        self.say("qarz")
        self.assertEqual(len(self.channel.texts()), REPLY_LIMIT + 2)
