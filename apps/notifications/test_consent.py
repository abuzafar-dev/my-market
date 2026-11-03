"""Consent: nothing without it, STOP/START, phone changes."""

from django.test import Client

from apps.debt.models import Customer
from apps.shops.models import Shop

from . import services
from .models import ConsentEvent, OutboundMessage, WhatsAppConsent
from .testing import NotificationTestCase, inbound_payload

Status = OutboundMessage.Status


class ConsentTests(NotificationTestCase):
    def setUp(self):
        super().setUp()
        self.web = Client()
        self.n = 0

    def say(self, text, phone="998901234567"):
        self.n += 1
        return self.signed_post(self.web, inbound_payload(phone, f"wamid.in{self.n}", text=text))

    def test_customer_without_consent_gets_nothing(self):
        stranger = self.make_customer(self.shop, "Vali", "+998901110000")
        self.add_debt(10_000, customer=stranger)
        self.add_payment(5_000, customer=stranger)
        self.advance(minutes=10)
        self.flush()
        self.assertFalse(OutboundMessage.objects.filter(customer=stranger).exists())
        self.assertEqual(self.channel.sent, [])

    def test_a_phone_number_alone_is_not_consent(self):
        stranger = self.make_customer(self.shop, "Vali", "+998901110000")
        self.assertIsNone(services.current_consent(stranger))
        with self.assertRaises(services.NotificationRejected):
            services.send_manual_reminder(stranger, self.owner)

    def test_grant_is_recorded_with_who_and_when(self):
        consent = WhatsAppConsent.objects.get(customer=self.customer)
        self.assertTrue(consent.is_active)
        self.assertEqual(consent.phone, "+998901234567")
        self.assertEqual(consent.granted_by, self.owner)
        self.assertEqual(consent.granted_at, self.start)
        event = consent.events.get()
        self.assertEqual(
            (event.action, event.source, event.actor),
            (ConsentEvent.Action.GRANTED, ConsentEvent.Source.STAFF, self.owner),
        )

    def test_invalid_phone_cannot_be_consented(self):
        for phone in ["", "12345", "+7 912 345 67 89", "+998 01 234 56 78"]:
            customer = self.make_customer(self.shop, "X", phone)
            with self.assertRaises(services.NotificationRejected) as ctx:
                services.grant_consent(customer, self.owner)
            self.assertEqual(ctx.exception.code, "invalid_phone")

    def test_phone_change_invalidates_consent_and_needs_a_fresh_one(self):
        self.add_debt(10_000)  # queued for the old number
        self.customer.phone = "+998935554433"
        self.customer.save()
        consent = WhatsAppConsent.objects.get(customer=self.customer)
        self.assertFalse(consent.is_active)
        self.assertEqual(consent.revoke_reason, WhatsAppConsent.RevokeReason.PHONE_CHANGED)

        self.advance(minutes=10)
        self.flush()
        self.assertEqual(self.channel.sent, [])  # never to the old number
        self.assertEqual(OutboundMessage.objects.get().error_code, "no_consent")

        self.add_debt(5_000)
        self.assertEqual(OutboundMessage.objects.count(), 1)  # nothing for the new one yet

        services.grant_consent(self.customer, self.seller)
        consent.refresh_from_db()
        self.assertEqual((consent.phone, consent.is_active), ("+998935554433", True))

    def test_reformatting_the_same_number_keeps_consent(self):
        self.customer.phone = "901234567"
        self.customer.save()
        self.assertTrue(WhatsAppConsent.objects.get(customer=self.customer).is_active)

    def test_sending_refuses_when_numbers_no_longer_match(self):
        # A change that bypassed save() (bulk update): the receiver never ran,
        # but the send-time check still compares the numbers.
        Customer.objects.filter(pk=self.customer.pk).update(phone="+998935554433")
        self.customer.refresh_from_db()
        self.assertIsNone(services.current_consent(self.customer))

    def test_stop_blocks_everything_after_it_and_confirms_once(self):
        self.add_debt(10_000)  # queued before STOP
        response = self.say("STOP")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.channel.texts()), 1)
        self.assertIn("obunadan chiqdingiz", self.channel.texts()[0])

        self.say("stop")  # duplicate: no second confirmation
        self.assertEqual(len(self.channel.texts()), 1)

        self.add_debt(20_000)
        self.add_payment(5_000)
        self.advance(minutes=10)
        self.flush()
        self.assertEqual(self.channel.templates(), [])
        queued = OutboundMessage.objects.exclude(kind=OutboundMessage.Kind.REPLY).get()
        self.assertEqual((queued.status, queued.error_code), (Status.CANCELLED, "no_consent"))
        consent = WhatsAppConsent.objects.get(customer=self.customer)
        self.assertEqual(consent.revoke_reason, WhatsAppConsent.RevokeReason.CUSTOMER_STOP)

    def test_stop_variants(self):
        for text in ["  To'xtat ", "TO‘XTAT", "toxtat", "Stop!"]:
            services.grant_consent(self.customer, self.owner)
            self.say(text)
            self.assertFalse(
                WhatsAppConsent.objects.get(customer=self.customer).is_active, msg=text
            )

    def test_stop_applies_to_every_shop_on_that_number(self):
        other = Shop.objects.create(name="Nur", phone="+998900000001")
        twin = self.make_customer(other, "Aziz", "+998901234567")
        services.grant_consent(twin, self.owner)
        self.say("stop")
        self.assertFalse(WhatsAppConsent.objects.filter(is_active=True).exists())
        self.assertEqual(len(self.channel.texts()), 1)

    def test_start_restores_consent_revoked_by_stop(self):
        self.say("STOP")
        self.say("START")
        consent = WhatsAppConsent.objects.get(customer=self.customer)
        self.assertTrue(consent.is_active)
        self.assertTrue(consent.events.filter(action=ConsentEvent.Action.RESTORED).exists())
        self.assertIn("qayta yoqildi", self.channel.texts()[-1])

        self.add_debt(10_000)
        self.advance(minutes=10)
        self.flush()
        self.assertEqual(self.channel.templates(), ["debt_added"])

        self.say("start")  # already on
        self.assertIn("allaqachon", self.channel.texts()[-1])

    def test_start_never_creates_consent_the_shop_did_not_record(self):
        self.make_customer(self.shop, "Vali", "+998901110000")
        self.say("START", phone="998901110000")
        self.assertFalse(WhatsAppConsent.objects.filter(phone="+998901110000").exists())
        self.assertIn("rozilik topilmadi", self.channel.texts()[-1])

    def test_start_does_not_undo_a_staff_revocation(self):
        services.revoke_consent(self.customer, self.owner)
        self.say("START")
        self.assertFalse(WhatsAppConsent.objects.get(customer=self.customer).is_active)

    def test_stop_cancels_already_queued_messages_at_once(self):
        self.add_debt(10_000)
        services.revoke_by_phone("+998901234567")
        self.assertEqual(OutboundMessage.objects.get().status, Status.CANCELLED)
