"""Debt-added / payment / closure notifications and the send boundary."""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.db import transaction
from django.test import override_settings

from apps.catalog.models import Batch, Product
from apps.debt.models import DebtEntry
from apps.sales.models import Sale
from apps.sales.services import CartLine, cancel_sale, create_sale

from . import services
from .channels import ChannelError
from .models import OutboundMessage
from .testing import FakeWhatsApp, NotificationTestCase

Status = OutboundMessage.Status
Kind = OutboundMessage.Kind


class DebtAddedTests(NotificationTestCase):
    def test_committed_debt_sends_exactly_one_message_after_the_window(self):
        self.add_debt(50_000, due_date=date(2026, 10, 20))
        self.assertEqual(self.messages().count(), 1)
        self.assertEqual(self.channel.sent, [])  # still inside the 10-minute window

        self.advance(minutes=10)
        self.flush()
        self.flush()  # a second sweep must not resend

        self.assertEqual(self.channel.templates(), ["debt_added"])
        self.assertEqual(
            self.channel.template_params(), ["Aziz", "Baraka", "50 000", "50 000", "20.10.2026"]
        )
        self.assertEqual(self.channel.sent[0][0], "+998901234567")
        message = self.messages().get()
        self.assertEqual(message.status, Status.SENT)
        self.assertEqual(message.external_id, "wamid.1")

    def test_rolled_back_debt_sends_nothing(self):
        from apps.debt.services import add_debt

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            try:
                with transaction.atomic():
                    add_debt(customer=self.customer, user=self.owner, amount=10_000)
                    raise RuntimeError("boom")
            except RuntimeError:
                pass
        self.assertEqual(callbacks, [])
        self.assertFalse(DebtEntry.objects.exists())
        self.assertFalse(self.messages().exists())

    def test_debts_within_ten_minutes_are_combined(self):
        self.add_debt(10_000)
        self.advance(minutes=4)
        self.add_debt(15_000)
        self.advance(minutes=5)
        self.add_debt(5_000, due_date=date(2026, 10, 25))
        self.assertEqual(self.messages().count(), 1)

        self.advance(minutes=1)
        self.flush()
        self.assertEqual(
            self.channel.template_params(), ["Aziz", "Baraka", "30 000", "30 000", "25.10.2026"]
        )

        # After the window closed, a new debt opens a new batch.
        self.advance(minutes=1)
        self.add_debt(7_000)
        self.assertEqual(self.messages().count(), 2)
        self.advance(minutes=10)
        self.flush()
        self.assertEqual(
            self.channel.template_params(), ["Aziz", "Baraka", "7 000", "37 000", "belgilanmagan"]
        )

    def test_same_event_twice_and_duplicate_task_execution_send_once(self):
        entry = self.add_debt(20_000)
        services.on_ledger_entry(entry.pk)  # event delivered again
        services.on_ledger_entry(entry.pk)
        self.assertEqual(self.messages().count(), 1)

        self.advance(minutes=10)
        message = self.messages().get()
        self.assertEqual(services.deliver(message.pk), "sent")
        self.assertEqual(services.deliver(message.pk), "not_due_or_taken")
        self.flush()
        self.assertEqual(len(self.channel.sent), 1)

    def test_a_row_already_claimed_by_another_worker_is_not_sent(self):
        self.add_debt(20_000)
        self.advance(minutes=10)
        message = self.messages().get()
        OutboundMessage.objects.filter(pk=message.pk).update(status=Status.SENDING)
        self.assertEqual(services.deliver(message.pk), "not_due_or_taken")
        self.assertEqual(self.channel.sent, [])

    def test_stuck_sending_row_is_marked_unknown_not_resent(self):
        self.add_debt(20_000)
        self.advance(minutes=10)
        message = self.messages().get()
        OutboundMessage.objects.filter(pk=message.pk).update(
            status=Status.SENDING, claimed_at=self.now
        )
        self.advance(minutes=11)
        self.flush()
        message.refresh_from_db()
        self.assertEqual(message.status, Status.UNKNOWN)
        self.assertEqual(message.error_code, "send_unknown")
        self.advance(hours=1)
        self.flush()
        self.assertEqual(self.channel.sent, [])

    def test_debt_paid_inside_the_window_cancels_the_notification(self):
        self.add_debt(20_000)
        self.advance(minutes=2)
        self.add_payment(20_000)  # closure goes out on its own
        self.advance(minutes=10)
        self.flush()
        added = self.messages(kind=Kind.DEBT_ADDED).get()
        self.assertEqual(added.status, Status.CANCELLED)
        self.assertEqual(added.error_code, "debt_paid")
        self.assertEqual(self.channel.templates(), ["debt_closed"])

    def test_debt_sale_notifies_and_cancelled_receipt_does_not_thank(self):
        product = Product.objects.create(
            shop=self.shop,
            name="Non",
            unit=Product.Unit.PIECE,
            markup_amount=500,
            min_stock=Decimal("0"),
        )
        Batch.objects.create(
            shop=self.shop,
            product=product,
            qty_initial=Decimal("10"),
            qty_remaining=Decimal("10"),
            cost_price=2000,
            sale_price=2500,
        )
        with self.captureOnCommitCallbacks(execute=True):
            sale = create_sale(
                shop=self.shop,
                user=self.owner,
                client_id=uuid4(),
                payment_type=Sale.PaymentType.DEBT,
                customer=self.customer,
                cart=[CartLine(product=product, qty=Decimal("2"))],
            )
        self.assertEqual(self.messages(kind=Kind.DEBT_ADDED).count(), 1)
        with self.captureOnCommitCallbacks(execute=True):
            cancel_sale(sale, self.owner)
        self.assertFalse(self.messages(kind__in=[Kind.PAYMENT_RECEIVED, Kind.DEBT_CLOSED]).exists())

    def test_shop_with_notifications_off_queues_nothing(self):
        self.nsettings.enabled = False
        self.nsettings.save()
        self.add_debt(10_000)
        self.add_payment(5_000)
        self.assertFalse(self.messages().exists())

    def test_turning_notifications_off_stops_queued_messages(self):
        self.add_debt(10_000)
        self.nsettings.enabled = False
        self.nsettings.save()
        self.advance(minutes=10)
        self.flush()
        self.assertEqual(self.messages().get().status, Status.CANCELLED)
        self.assertEqual(self.channel.sent, [])

    def test_missing_whatsapp_configuration_keeps_the_feature_off(self):
        self.channel = FakeWhatsApp(configured=False)
        entry = self.add_debt(10_000)
        self.add_payment(1_000)
        services.on_ledger_entry(entry.pk)
        self.assertFalse(self.messages().exists())
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debt_balance, 9_000)  # the ledger is unaffected

    def test_queuing_failure_never_breaks_the_debt_write(self):
        with patch.object(services, "queue_debt_added", side_effect=RuntimeError("db down")):
            entry = self.add_debt(10_000)
        self.assertTrue(DebtEntry.objects.filter(pk=entry.pk).exists())


class SendingHoursTests(NotificationTestCase):
    def test_debt_added_late_in_the_evening_waits_until_the_window_opens(self):
        self.at(2026, 10, 13, 21, 30)
        self.add_debt(10_000)
        message = self.messages().get()
        self.assertEqual(message.send_after.isoformat(), "2026-10-14T04:00:00+00:00")  # 09:00

        self.advance(minutes=30)
        self.flush()
        self.assertEqual(self.channel.sent, [])
        self.at(2026, 10, 14, 9, 0)
        self.flush()
        self.assertEqual(self.channel.templates(), ["debt_added"])

    def test_a_message_due_when_the_window_closed_is_deferred(self):
        self.at(2026, 10, 13, 19, 55)
        self.add_debt(10_000)  # due at 20:05, after closing
        message = self.messages().get()
        self.assertEqual(message.send_after.hour, 4)  # next day 09:00 Tashkent (UTC+5)

        # Even a row forced to "due now" is put back rather than sent at night.
        OutboundMessage.objects.filter(pk=message.pk).update(send_after=self.now)
        self.at(2026, 10, 13, 22, 0)
        self.assertEqual(services.deliver(message.pk), "deferred")
        message.refresh_from_db()
        self.assertEqual(message.status, Status.QUEUED)
        self.assertEqual(message.attempts, 0)
        self.assertEqual(self.channel.sent, [])

    def test_next_send_time(self):
        from .testing import TASHKENT

        opens_today = datetime(2026, 10, 13, 9, 0, tzinfo=TASHKENT)
        self.at(2026, 10, 13, 8, 59)
        self.assertEqual(services.next_send_time(self.nsettings, self.now), opens_today)
        self.at(2026, 10, 13, 20, 0)
        self.assertEqual(
            services.next_send_time(self.nsettings, self.now), opens_today + timedelta(days=1)
        )
        self.at(2026, 10, 13, 10, 0)
        self.assertEqual(services.next_send_time(self.nsettings, self.now), self.now)


class PaymentTests(NotificationTestCase):
    def test_partial_payment_reports_the_remaining_balance(self):
        self.add_debt(100_000)
        self.advance(minutes=11)
        self.flush()
        self.add_payment(30_000)
        self.flush()
        self.assertEqual(self.channel.templates(), ["debt_added", "payment_received"])
        self.assertEqual(self.channel.template_params(), ["Aziz", "Baraka", "30 000", "70 000"])

    def test_remaining_balance_is_as_of_the_payment_not_later_entries(self):
        self.add_debt(100_000)
        self.advance(minutes=11)
        self.flush()
        self.nsettings.enabled = False  # hold the payment message back
        self.nsettings.save()
        payment = self.add_payment(30_000)
        self.nsettings.enabled = True
        self.nsettings.save()
        self.advance(minutes=1)
        self.add_debt(5_000)
        services.on_ledger_entry(payment.pk)
        self.flush()
        self.assertEqual(self.channel.template_params(), ["Aziz", "Baraka", "30 000", "70 000"])

    def test_full_payment_sends_one_closure(self):
        self.add_debt(50_000)
        self.advance(minutes=11)
        self.flush()
        payment = self.add_payment(50_000)
        services.on_ledger_entry(payment.pk)  # duplicate event
        self.flush()
        self.flush()
        self.assertEqual(self.channel.templates(), ["debt_added", "debt_closed"])
        self.assertEqual(self.channel.template_params(), ["Aziz", "Baraka", "50 000"])
        self.assertEqual(self.messages(kind=Kind.DEBT_CLOSED).count(), 1)

    def test_final_payment_is_one_message_saying_paid_amount_and_zero_left(self):
        from . import templates as tpl

        self.add_debt(50_000)
        self.advance(minutes=11)
        self.flush()
        self.add_payment(20_000)
        self.flush()
        self.add_payment(30_000)  # the final one
        self.flush()
        self.assertEqual(
            self.channel.templates(), ["debt_added", "payment_received", "debt_closed"]
        )
        self.assertEqual(self.channel.template_params(), ["Aziz", "Baraka", "30 000"])
        self.assertIn("{{3}} so'm to'lovingizni qabul qildi", tpl.DEBT_CLOSED.body)
        self.assertIn("Qolgan qarz: 0 so'm", tpl.DEBT_CLOSED.body)
        final = self.messages(kind=Kind.DEBT_CLOSED).get()
        # No payment_received row for the final payment entry.
        self.assertFalse(
            self.messages(kind=Kind.PAYMENT_RECEIVED, debt_entry=final.debt_entry).exists()
        )

    def test_overpayment_closes_once_and_still_reports_the_full_amount_paid(self):
        self.add_debt(50_000)
        self.advance(minutes=11)
        self.flush()
        self.add_payment(60_000)
        self.flush()
        self.assertEqual(self.channel.templates(), ["debt_added", "debt_closed"])
        self.assertEqual(self.channel.template_params(), ["Aziz", "Baraka", "60 000"])
        self.assertEqual(self.messages().count(), 2)

    def test_two_payments_racing_to_close_announce_closure_once(self):
        self.add_debt(50_000)
        self.advance(minutes=11)
        self.flush()
        # Two payments committed at the same instant, each of whose ledger
        # snapshots sees the debt being closed by itself.
        payments = [
            DebtEntry.objects.create(
                shop=self.shop,
                customer=self.customer,
                amount=-50_000,
                entry_type=DebtEntry.EntryType.PAYMENT,
            )
            for _ in range(2)
        ]
        first, second = (services.queue_payment(p) for p in payments)
        self.assertEqual(first.kind, Kind.DEBT_CLOSED)
        self.assertEqual(second.kind, Kind.PAYMENT_RECEIVED)
        self.assertEqual(self.messages(kind=Kind.DEBT_CLOSED).count(), 1)

    def test_paying_again_after_a_new_debt_closes_again(self):
        self.add_debt(10_000)
        self.advance(seconds=5)
        self.add_payment(10_000)
        self.advance(minutes=30)
        self.add_debt(20_000)
        self.advance(seconds=5)
        self.add_payment(20_000)
        self.assertEqual(self.messages(kind=Kind.DEBT_CLOSED).count(), 2)


class FailureHandlingTests(NotificationTestCase):
    def setUp(self):
        super().setUp()
        self.add_debt(10_000)
        self.advance(minutes=10)
        self.message = self.messages().get()

    def test_transient_errors_retry_with_backoff_then_give_up_after_five(self):
        self.channel.errors = [
            ChannelError("131016", "Service unavailable", retryable=True) for _ in range(5)
        ]
        delays = []
        for _ in range(5):
            self.flush()
            self.message.refresh_from_db()
            if self.message.status == Status.QUEUED:
                delays.append(int((self.message.send_after - self.now).total_seconds()))
                self.now = self.message.send_after
        self.assertEqual(delays, [30, 60, 120, 240])
        self.assertEqual(self.message.status, Status.FAILED)
        self.assertEqual(self.message.attempts, 5)
        self.assertEqual(self.message.error_code, "131016")
        self.assertEqual(self.channel.sent, [])

    def test_transient_error_then_success(self):
        self.channel.errors = [ChannelError("network", "URLError", retryable=True)]
        self.flush()
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, Status.QUEUED)
        self.advance(seconds=30)
        self.flush()
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, Status.SENT)
        self.assertEqual(self.message.attempts, 2)

    def test_invalid_recipient_is_not_retried(self):
        self.channel.errors = [ChannelError("131026", "Message undeliverable", retryable=False)]
        self.flush()
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, Status.FAILED)
        self.assertEqual(self.message.attempts, 1)
        self.advance(hours=1)
        self.flush()
        self.assertEqual(self.channel.sent, [])

    @override_settings(WHATSAPP_TEMPLATE_QUICK_REPLY=False)
    def test_quick_reply_button_parameter_is_optional(self):
        self.flush()
        components = self.channel.sent[0][1]["template"]["components"]
        self.assertEqual([c["type"] for c in components], ["body"])

    def test_quick_reply_button_parameter_is_sent_by_default(self):
        self.flush()
        components = self.channel.sent[0][1]["template"]["components"]
        self.assertEqual(components[1]["parameters"], [{"type": "payload", "payload": "BALANCE"}])
        self.assertEqual(self.channel.sent[0][1]["template"]["language"], {"code": "uz"})


class OutstandingDebtsTests(NotificationTestCase):
    def test_payments_cover_the_oldest_debts_first(self):
        from apps.debt.services import outstanding_debts

        first = self.add_debt(10_000, due_date=date(2026, 10, 14))
        self.advance(minutes=1)
        second = self.add_debt(20_000, due_date=date(2026, 10, 20))
        self.add_payment(15_000)
        self.assertEqual(
            [(e.pk, r) for e, r in outstanding_debts(self.customer)], [(second.pk, 15_000)]
        )
        self.assertNotIn(first.pk, [e.pk for e, _ in outstanding_debts(self.customer)])
        self.add_payment(15_000)
        self.assertEqual(outstanding_debts(self.customer), [])


class SendOutcomeTests(NotificationTestCase):
    """The real adapter (HTTP mocked at http.client) behind deliver(): what
    each kind of failure does to the message row."""

    def setUp(self):
        super().setUp()
        from .channels.whatsapp import WhatsAppCloudChannel

        self.channel = WhatsAppCloudChannel(
            access_token="token",
            phone_number_id="PNID",
            api_version="v0.test",
            api_base="https://graph.example",
        )
        self.connections = []  # one FakeHTTP per attempt, in order
        patcher = patch("http.client.HTTPSConnection", side_effect=self._connect)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.add_debt(10_000)
        self.advance(minutes=10)
        self.message = self.messages().get()

    def _connect(self, host, port=None, timeout=None):
        return self.connections.pop(0)(host, port, timeout)

    def attempt(self, *fakes):
        self.connections.extend(fakes)
        self.flush()
        self.message.refresh_from_db()
        return self.message

    def test_failure_before_sending_is_retried_and_then_sent_once(self):
        from .test_channel import FakeHTTP

        first = FakeHTTP(fail_at="connect", error=ConnectionRefusedError())
        message = self.attempt(first)
        self.assertEqual((message.status, message.error_code), (Status.QUEUED, "network"))
        self.assertEqual(first.requests, [])
        self.advance(seconds=30)
        second = FakeHTTP()
        message = self.attempt(second)
        self.assertEqual((message.status, message.attempts), (Status.SENT, 2))
        self.assertEqual(len(second.requests), 1)

    def test_retryable_error_from_meta_is_retried(self):
        from .test_channel import FakeHTTP

        body = json.dumps({"error": {"code": 130429, "message": "Rate limit"}}).encode()
        message = self.attempt(FakeHTTP(status=429, body=body))
        self.assertEqual((message.status, message.error_code), (Status.QUEUED, "130429"))
        self.assertEqual(message.send_after, self.now + timedelta(seconds=30))

    def test_permanent_error_from_meta_fails_without_retry(self):
        from .test_channel import FakeHTTP

        body = json.dumps({"error": {"code": 131026, "message": "Undeliverable"}}).encode()
        message = self.attempt(FakeHTTP(status=400, body=body))
        self.assertEqual((message.status, message.error_code), (Status.FAILED, "131026"))
        self.advance(hours=2)
        self.flush()
        message.refresh_from_db()
        self.assertEqual((message.status, message.attempts), (Status.FAILED, 1))

    def test_timeout_after_sending_is_unknown_and_never_resent(self):
        from .test_channel import FakeHTTP

        sent = FakeHTTP(fail_at="response", error=TimeoutError())
        message = self.attempt(sent)
        self.assertEqual(len(sent.requests), 1)  # it did go out
        self.assertEqual(
            (message.status, message.error_code, message.attempts),
            (Status.UNKNOWN, "send_unknown", 1),
        )
        self.assertIsNotNone(message.failed_at)
        for _ in range(3):
            self.advance(hours=1)
            self.flush()
        message.refresh_from_db()
        self.assertEqual((message.status, message.attempts), (Status.UNKNOWN, 1))
        self.assertEqual(services.stats()["unknown_total"], 1)

    def test_unknown_rows_cannot_be_requeued_from_the_admin(self):
        from django.contrib import admin
        from django.test import RequestFactory

        from apps.shops.models import User

        model_admin = admin.site._registry[OutboundMessage]
        request = RequestFactory().get("/")
        request.user = User(is_superuser=True, is_staff=True)
        self.assertFalse(model_admin.has_change_permission(request, self.message))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request, self.message))
