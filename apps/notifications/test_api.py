"""Staff API: settings, consent, manual reminders, ledger status — and isolation."""

from datetime import date

from rest_framework.test import APIClient

from apps.shops.models import Shop, User

from . import services
from .models import OutboundMessage, ShopNotificationSettings
from .testing import FakeWhatsApp, NotificationTestCase

Status = OutboundMessage.Status


class ApiTestCase(NotificationTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        self.other_shop = Shop.objects.create(name="Nur", phone="+998900000001")
        self.other_owner = User.objects.create_user(
            phone="+998905556677",
            password="pass1234",  # pragma: allowlist secret
            shop=self.other_shop,
            full_name="Boshqa",
        )
        self.add_debt(30_000)

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client


class SettingsApiTests(ApiTestCase):
    def url(self, shop=None):
        return f"/api/shops/{(shop or self.shop).pk}/notification-settings/"

    def test_owner_reads_and_updates(self):
        data = self.api.get(self.url()).json()["data"]
        self.assertEqual(
            data,
            {
                "enabled": True,
                "reminder_days_before": 1,
                "send_window_start": "09:00",
                "send_window_end": "20:00",
                "max_reminders_per_debt": 3,
                "overdue_repeat_days": 0,  # TZ FT-3: one overdue reminder
                "whatsapp_configured": True,
            },
        )
        response = self.api.patch(
            self.url(),
            {
                "reminder_days_before": 0,
                "send_window_start": "10:30",
                "max_reminders_per_debt": 5,
                "overdue_repeat_days": 7,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.nsettings.refresh_from_db()
        self.assertEqual(self.nsettings.reminder_days_before, 0)
        self.assertEqual(self.nsettings.overdue_repeat_days, 7)
        bad = self.api.patch(self.url(), {"overdue_repeat_days": 31}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.nsettings.send_window_start.strftime("%H:%M"), "10:30")

    def test_defaults_for_a_new_shop_are_off(self):
        data = self.as_user(self.other_owner).get(self.url(self.other_shop)).json()["data"]
        self.assertFalse(data["enabled"])
        self.assertEqual(data["reminder_days_before"], 1)

    def test_validation(self):
        for payload in [
            {"reminder_days_before": 8},
            {"reminder_days_before": -1},
            {"max_reminders_per_debt": 0},
            {"send_window_start": "21:00"},
            {"send_window_start": "12:00", "send_window_end": "12:00"},
        ]:
            response = self.api.patch(self.url(), payload, format="json")
            self.assertEqual(response.status_code, 400, payload)
            self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_seller_and_anonymous_and_other_shop_are_refused(self):
        self.assertEqual(self.as_user(self.seller).get(self.url()).status_code, 403)
        self.assertEqual(APIClient().get(self.url()).status_code, 401)
        other = self.as_user(self.other_owner)
        self.assertEqual(other.get(self.url()).status_code, 404)
        self.assertEqual(
            other.patch(self.url(), {"enabled": False}, format="json").status_code, 404
        )
        self.nsettings.refresh_from_db()
        self.assertTrue(self.nsettings.enabled)


class ConsentApiTests(ApiTestCase):
    def url(self, customer=None, suffix="whatsapp-consent"):
        return f"/api/customers/{(customer or self.customer).pk}/{suffix}/"

    def test_seller_can_record_and_withdraw_consent(self):
        customer = self.make_customer(self.shop, "Vali", "+998 93 555 44 33")
        seller = self.as_user(self.seller)
        response = seller.post(self.url(customer), {"granted": True}, format="json")
        self.assertEqual(response.status_code, 200)
        state = response.json()["data"]
        self.assertTrue(state["consent"]["active"])
        self.assertEqual(state["consent"]["granted_by_name"], "Sotuvchi")
        self.assertEqual(state["consent"]["phone"], "+998935554433")

        state = seller.post(self.url(customer), {"granted": False}, format="json").json()["data"]
        self.assertFalse(state["consent"]["active"])
        self.assertEqual(state["consent"]["revoke_reason"], "staff")

    def test_invalid_phone_is_a_clear_400(self):
        customer = self.make_customer(self.shop, "Vali", "")
        response = self.api.post(self.url(customer), {"granted": True}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_phone")

    def test_another_shops_customer_is_not_found(self):
        other = self.as_user(self.other_owner)
        self.assertEqual(other.post(self.url(), {"granted": False}, format="json").status_code, 404)
        self.assertEqual(other.get(self.url(suffix="whatsapp")).status_code, 404)
        self.assertEqual(other.post(self.url(suffix="send-reminder")).status_code, 404)
        self.assertTrue(services.current_consent(self.customer))

    def test_state_maps_ledger_lines_to_their_latest_message_status(self):
        self.advance(minutes=10)
        self.flush()
        entry = self.customer.entries.get()
        state = self.api.get(self.url(suffix="whatsapp")).json()["data"]
        self.assertEqual(state["entry_status"][str(entry.pk)]["status"], "sent")
        self.assertEqual(state["entry_status"][str(entry.pk)]["kind"], "debt_added")
        self.assertEqual(state["last_message"]["status"], "sent")
        self.assertTrue(state["can_remind"])

    def test_state_endpoint_query_count_is_flat(self):
        for _ in range(5):
            self.advance(minutes=11)
            self.add_debt(1_000)
        with self.assertNumQueries(4):  # however many messages there are
            self.api.get(self.url(suffix="whatsapp"))


class ManualReminderApiTests(ApiTestCase):
    def url(self, customer=None):
        return f"/api/customers/{(customer or self.customer).pk}/send-reminder/"

    def post(self, client=None, url=None):
        with self.captureOnCommitCallbacks(execute=True):
            return (client or self.api).post(url or self.url())

    def test_sends_once_a_day(self):
        response = self.post()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.channel.templates(), ["debt_reminder"])
        self.assertEqual(
            self.channel.template_params(), ["Aziz", "Baraka", "30 000", "belgilanmagan"]
        )

        again = self.api.post(self.url())
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["error"]["code"], "already_sent_today")
        self.assertIn("bugun", again.json()["error"]["message"])

        self.at(2026, 10, 14, 10, 0)
        self.assertEqual(self.post().status_code, 202)
        self.assertEqual(len(self.channel.templates()), 2)

    def test_uses_the_overdue_wording_when_something_is_overdue(self):
        self.at(2026, 10, 1, 12, 0)
        self.add_debt(5_000, due_date=date(2026, 10, 5))
        self.at(2026, 10, 13, 12, 0)
        self.post()
        self.assertEqual(self.channel.templates(), ["debt_overdue"])
        self.assertEqual(self.channel.template_params(), ["Aziz", "Baraka", "5 000", "05.10.2026"])

    def test_outside_hours_it_is_scheduled_for_the_morning(self):
        self.at(2026, 10, 13, 22, 0)
        data = self.api.post(self.url()).json()["data"]
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["send_after"], "2026-10-14T09:00:00+05:00")
        self.assertEqual(self.channel.sent, [])

    def test_refusals_explain_why(self):
        cases = []
        no_consent = self.make_customer(self.shop, "Vali", "+998901110000")
        self.add_debt(1_000, customer=no_consent)
        cases.append((self.url(no_consent), "no_consent"))
        no_debt = self.make_customer(self.shop, "Sobir", "+998901110001")
        services.grant_consent(no_debt, self.owner)
        cases.append((self.url(no_debt), "no_debt"))
        for url, code in cases:
            response = self.api.post(url)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["error"]["code"], code)

        ShopNotificationSettings.objects.filter(shop=self.shop).update(enabled=False)
        response = self.api.post(self.url())
        self.assertEqual(response.json()["error"]["code"], "notifications_disabled")

        self.channel = FakeWhatsApp(configured=False)
        response = self.api.post(self.url())
        self.assertEqual(response.json()["error"]["code"], "whatsapp_not_configured")
        self.assertEqual(self.channel.sent, [])

    def test_anonymous_is_refused(self):
        self.assertEqual(APIClient().post(self.url()).status_code, 401)

    def test_presses_either_side_of_midnight_still_give_one_reminder_a_day(self):
        # 23:50 is outside sending hours: it goes out at 09:00 tomorrow. A
        # press at 00:10 must not add a second one for that same morning.
        self.at(2026, 10, 13, 23, 50)
        self.assertEqual(self.post().status_code, 202)
        state = self.api.get(f"/api/customers/{self.customer.pk}/whatsapp/").json()["data"]
        self.assertFalse(state["can_remind"])
        self.at(2026, 10, 14, 0, 10)
        again = self.post()
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["error"]["code"], "already_sent_today")
        self.at(2026, 10, 14, 9, 0)
        self.flush()
        self.assertEqual(self.channel.templates().count("debt_reminder"), 1)
        # The next calendar day is a new day again.
        self.at(2026, 10, 15, 10, 0)
        self.assertEqual(self.post().status_code, 202)

    def test_seller_cannot_send_a_reminder_but_sees_the_state(self):
        # TZ §3: sending a manual reminder is the owner's; sellers see statuses.
        seller = self.as_user(self.seller)
        self.assertEqual(self.post(seller).status_code, 403)
        self.assertEqual(self.channel.sent, [])
        state = seller.get(f"/api/customers/{self.customer.pk}/whatsapp/").json()["data"]
        self.assertFalse(state["can_remind"])
        owner_state = self.api.get(f"/api/customers/{self.customer.pk}/whatsapp/").json()["data"]
        self.assertTrue(owner_state["can_remind"])

    def test_rate_limited(self):
        from rest_framework.throttling import ScopedRateThrottle

        rates = {**ScopedRateThrottle.THROTTLE_RATES, "reminders": "2/min"}
        original = ScopedRateThrottle.THROTTLE_RATES
        ScopedRateThrottle.THROTTLE_RATES = rates
        try:
            codes = [self.api.post(self.url()).status_code for _ in range(3)]
        finally:
            ScopedRateThrottle.THROTTLE_RATES = original
        self.assertEqual(codes, [202, 409, 429])


class DebtApiTests(ApiTestCase):
    def test_debt_accepts_an_optional_due_date_and_the_ledger_shows_it(self):
        url = f"/api/customers/{self.customer.pk}/debt/"
        self.advance(minutes=1)
        response = self.api.post(url, {"amount": 1000, "due_date": "2026-10-20"}, format="json")
        self.assertEqual(response.status_code, 200)
        entries = response.json()["data"]["entries"]
        self.assertEqual(entries[0]["due_date"], "2026-10-20")
        self.assertIsNone(entries[1]["due_date"])

        past = self.api.post(url, {"amount": 1000, "due_date": "2026-10-01"}, format="json")
        self.assertEqual(past.status_code, 400)
        self.assertEqual(self.api.post(url, {"amount": 1000}, format="json").status_code, 200)

    def test_payment_endpoint_is_unchanged(self):
        url = f"/api/customers/{self.customer.pk}/payment/"
        response = self.api.post(url, {"amount": 1000, "due_date": "2026-10-20"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"]["entries"][0]["due_date"])


class CustomerStatusesApiTests(ApiTestCase):
    url = "/api/customers/whatsapp-statuses/"

    def test_latest_status_per_customer_for_the_debt_book(self):
        self.advance(minutes=10)
        self.flush()
        quiet = self.make_customer(self.shop, "Vali", "+998901110000")
        ShopNotificationSettings.objects.create(shop=self.other_shop, enabled=True)
        foreign = self.make_customer(self.other_shop, "Begona", "+998901234567")
        services.grant_consent(foreign, self.other_owner)
        self.add_debt(5_000, customer=foreign)

        ids = ",".join(str(c.pk) for c in (self.customer, quiet, foreign)) + ",not-a-uuid"
        data = self.as_user(self.seller).get(self.url, {"ids": ids}).json()["data"]
        self.assertEqual(data, {str(self.customer.pk): {"status": "sent", "kind": "debt_added"}})

        # The other shop sees its own customer, never this one.
        other = self.as_user(self.other_owner).get(self.url, {"ids": ids}).json()["data"]
        self.assertEqual(list(other), [str(foreign.pk)])

    def test_bot_replies_do_not_count_and_anonymous_is_refused(self):
        services.queue_reply("+998901234567", "x", text="hi", customer_id=self.customer.pk)
        data = self.api.get(self.url, {"ids": str(self.customer.pk)}).json()["data"]
        self.assertEqual(data[str(self.customer.pk)]["kind"], "debt_added")
        self.assertEqual(APIClient().get(self.url).status_code, 401)
