"""Real concurrency on PostgreSQL: several threads, each with its own database
connection, hitting the same rows at once.

The regular suite runs on SQLite, where SELECT ... FOR UPDATE is a no-op, so it
cannot show that the row locks actually serialise anything. These tests are
skipped there and run only against PostgreSQL, e.g. with a settings module
that points DATABASES at a local throwaway server:

    DJANGO_SETTINGS_MODULE=<pg settings> python manage.py test apps.notifications.test_postgres_races

They never reach Meta: the channel is FakeWhatsApp.
"""

import threading
import unittest
from datetime import time, timedelta

from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from apps.debt.models import Customer, DebtEntry
from apps.debt.services import add_debt, add_payment
from apps.shops.models import Shop, User

from . import services
from .models import OutboundMessage, ShopNotificationSettings, WhatsAppConsent
from .testing import FakeWhatsApp

Kind = OutboundMessage.Kind
Status = OutboundMessage.Status


class SlowWhatsApp(FakeWhatsApp):
    """Records sends like FakeWhatsApp, but each call can be held open until
    the test releases it — the "request is in flight" moment."""

    def __init__(self):
        super().__init__()
        self.in_flight = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.lock = threading.Lock()
        self.finished_at = None

    def _post(self, to, message):
        self.in_flight.set()
        self.release.wait(10)
        with self.lock:
            result = super()._post(to, message)
            self.finished_at = timezone.now()
        return result


def run_threads(*targets, timeout=20):
    """Run each callable in its own thread (own DB connection); re-raise the
    first exception any of them hit."""
    errors = []

    def wrap(fn):
        def runner():
            try:
                fn()
            except BaseException as exc:  # noqa: BLE001 — reported below
                errors.append(exc)
            finally:
                connections.close_all()

        return runner

    threads = [threading.Thread(target=wrap(fn)) for fn in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout)
    if errors:
        raise errors[0]
    return threads


@unittest.skipUnless(connection.vendor == "postgresql", "needs PostgreSQL row locks")
class PostgresRaceTests(TransactionTestCase):
    def setUp(self):
        from unittest.mock import patch

        self.channel = SlowWhatsApp()
        patcher = patch("apps.notifications.services.get_channel", side_effect=lambda: self.channel)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.shop = Shop.objects.create(name="Baraka", phone="+998900000000")
        # Open all day, so the real clock is always inside the window.
        ShopNotificationSettings.objects.create(
            shop=self.shop,
            enabled=True,
            send_window_start=time(0, 0),
            send_window_end=time(23, 59, 59),
        )
        self.owner = User.objects.create_user(
            phone="+998901112233",
            password="pass1234",  # pragma: allowlist secret
            shop=self.shop,
            full_name="Egasi",
        )
        self.customer = Customer.objects.create(
            shop=self.shop, full_name="Aziz", phone="+998901234567"
        )
        services.grant_consent(self.customer, self.owner)

    def due_now(self, message):
        OutboundMessage.objects.filter(pk=message.pk).update(
            send_after=timezone.now() - timedelta(seconds=1)
        )

    def queued_debt_message(self, amount=50_000):
        add_debt(customer=self.customer, user=self.owner, amount=amount)
        message = OutboundMessage.objects.get(kind=Kind.DEBT_ADDED)
        self.due_now(message)
        return message

    # ------------------------------------------------------------ sending

    def test_two_workers_delivering_the_same_row_send_it_once(self):
        message = self.queued_debt_message()
        self.channel.release.clear()
        start = threading.Barrier(4)
        outcomes = []

        def worker():
            start.wait()
            outcomes.append(services.deliver(message.pk))

        def releaser():
            start.wait()
            self.channel.in_flight.wait(5)
            self.channel.release.set()

        run_threads(worker, worker, worker, releaser)
        self.assertEqual(len(self.channel.sent), 1)
        self.assertEqual(sorted(outcomes), ["not_due_or_taken", "not_due_or_taken", "sent"])
        message.refresh_from_db()
        self.assertEqual((message.status, message.attempts), (Status.SENT, 1))

    def test_stop_arriving_while_a_send_is_in_flight_waits_for_it(self):
        message = self.queued_debt_message()
        self.channel.release.clear()
        stop_done = {}

        def sender():
            services.deliver(message.pk)

        def stopper():
            self.channel.in_flight.wait(5)
            services.revoke_by_phone("+998901234567")
            stop_done["at"] = timezone.now()

        threads = run_threads(sender, stopper, timeout=1)
        # The STOP is blocked on the consent row lock the sender holds.
        self.assertTrue(threads[1].is_alive())
        self.assertNotIn("at", stop_done)
        self.channel.release.set()
        for thread in threads:
            thread.join(10)

        self.assertEqual(len(self.channel.sent), 1)
        self.assertGreater(stop_done["at"], self.channel.finished_at)
        message.refresh_from_db()
        self.assertEqual(message.status, Status.SENT)
        self.assertFalse(WhatsAppConsent.objects.get(customer=self.customer).is_active)

    def test_stop_committed_first_means_nothing_is_sent(self):
        message = self.queued_debt_message()
        # The worker has claimed the row (SENDING) but not reached the consent
        # check when the STOP commits.
        OutboundMessage.objects.filter(pk=message.pk).update(status=Status.QUEUED)
        run_threads(lambda: services.revoke_by_phone("+998901234567"))
        message.refresh_from_db()
        self.assertEqual((message.status, message.error_code), (Status.CANCELLED, "no_consent"))
        self.assertEqual(services.deliver(message.pk), "not_due_or_taken")

        # Same, but the row was already SENDING (claimed) when STOP landed.
        other = OutboundMessage.objects.create(
            shop=self.shop,
            customer=self.customer,
            to_phone="+998901234567",
            kind=Kind.MANUAL_REMINDER,
            idempotency_key="manual:race",
            send_after=timezone.now(),
        )
        self.assertEqual(services.deliver(other.pk), "cancelled")
        self.assertEqual(self.channel.sent, [])

    def test_two_concurrent_stops_on_a_number_with_several_shops_do_not_deadlock(self):
        for i in range(4):
            shop = Shop.objects.create(name=f"Do'kon {i}", phone=f"+99890000010{i}")
            ShopNotificationSettings.objects.create(shop=shop, enabled=True)
            twin = Customer.objects.create(shop=shop, full_name="Aziz", phone="+998901234567")
            services.grant_consent(twin, self.owner)
        start = threading.Barrier(2)

        def stop():
            start.wait()
            services.revoke_by_phone("+998901234567")

        threads = run_threads(stop, stop)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertFalse(WhatsAppConsent.objects.filter(is_active=True).exists())

    # ------------------------------------------------------------ queuing

    def test_concurrent_debts_for_one_customer_share_one_message(self):
        start = threading.Barrier(3)

        def debt():
            start.wait()
            add_debt(customer=self.customer, user=self.owner, amount=10_000)

        run_threads(debt, debt, debt)
        messages = OutboundMessage.objects.filter(kind=Kind.DEBT_ADDED)
        self.assertEqual(messages.count(), 1)
        self.assertEqual(len(messages.get().params["entry_ids"]), 3)

    def test_two_payments_closing_the_debt_announce_the_closure_once(self):
        add_debt(customer=self.customer, user=self.owner, amount=100_000)
        start = threading.Barrier(2)

        def pay():
            start.wait()
            add_payment(customer=self.customer, user=self.owner, amount=50_000)

        run_threads(pay, pay)
        kinds = sorted(
            OutboundMessage.objects.filter(
                kind__in=[Kind.PAYMENT_RECEIVED, Kind.DEBT_CLOSED]
            ).values_list("kind", flat=True)
        )
        self.assertEqual(kinds, [Kind.DEBT_CLOSED, Kind.PAYMENT_RECEIVED])

    def test_payment_written_first_but_committed_last_still_announces_the_closure(self):
        """Payment A gets the earlier created_at but commits after B (it waited
        for the customer row). Judged only "as of" its own created_at, neither
        payment would look like the one that closed the debt."""
        add_debt(customer=self.customer, user=self.owner, amount=100_000)
        a_written = threading.Event()
        b_committed = threading.Event()

        def payment_a():
            with transaction.atomic():
                DebtEntry.objects.create(
                    shop=self.shop,
                    customer=self.customer,
                    amount=-50_000,
                    entry_type=DebtEntry.EntryType.PAYMENT,
                    created_by=self.owner,
                )
                a_written.set()
                b_committed.wait(10)
                Customer.objects.filter(pk=self.customer.pk).update(
                    debt_balance=Customer.objects.get(pk=self.customer.pk).debt_balance - 50_000
                )

        def payment_b():
            a_written.wait(10)
            add_payment(customer=self.customer, user=self.owner, amount=50_000)
            b_committed.set()

        run_threads(payment_a, payment_b)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debt_balance, 0)
        self.assertEqual(OutboundMessage.objects.filter(kind=Kind.DEBT_CLOSED).count(), 1)

    def test_concurrent_consent_grants_for_a_new_customer(self):
        fresh = Customer.objects.create(shop=self.shop, full_name="Vali", phone="+998901110000")
        start = threading.Barrier(3)

        def grant():
            start.wait()
            services.grant_consent(fresh, self.owner)

        run_threads(grant, grant, grant)
        self.assertTrue(WhatsAppConsent.objects.get(customer=fresh).is_active)

    def test_concurrent_reminder_runs_queue_one_reminder(self):
        from django.core.cache import cache

        entry = add_debt(
            customer=self.customer,
            user=self.owner,
            amount=10_000,
            due_date=timezone.localdate() + timedelta(days=1),
        )
        DebtEntry.objects.filter(pk=entry.pk).update(created_at=timezone.now() - timedelta(days=2))
        start = threading.Barrier(3)

        def run():
            start.wait()
            # Bypass the cache lock: the database alone must prevent doubles.
            cache.delete("whatsapp:reminder-run")
            services._schedule_reminders(timezone.now())

        run_threads(run, run, run)
        self.assertEqual(
            OutboundMessage.objects.filter(kind__in=services.REMINDER_KINDS).count(), 1
        )
