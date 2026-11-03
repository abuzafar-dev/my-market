"""Scheduled upcoming/overdue reminders."""

from datetime import date

from django.core.cache import cache

from . import services
from .models import OutboundMessage
from .testing import NotificationTestCase

Kind = OutboundMessage.Kind
Status = OutboundMessage.Status


class ReminderTestBase(NotificationTestCase):
    def setUp(self):
        super().setUp()
        # A debt from two days ago, due tomorrow (14 Oct); its "debt added"
        # message is already out of the way.
        self.at(2026, 10, 11, 12, 0)
        self.debt = self.add_debt(40_000, due_date=date(2026, 10, 14))
        self.advance(minutes=10)
        self.flush()
        self.channel.sent.clear()

    def run_schedule(self):
        with self.captureOnCommitCallbacks(execute=True):
            queued = services.schedule_reminders()
        self.flush()
        return queued

    def reminders(self):
        return self.messages(kind__in=[Kind.DEBT_REMINDER, Kind.DEBT_OVERDUE])


class ReminderTests(ReminderTestBase):
    def test_upcoming_reminder_one_day_before_by_default(self):
        self.at(2026, 10, 12, 10, 0)  # two days before: too early
        self.assertEqual(self.run_schedule(), 0)
        self.at(2026, 10, 13, 10, 0)
        self.assertEqual(self.run_schedule(), 1)
        self.assertEqual(self.channel.templates(), ["debt_reminder"])
        self.assertEqual(self.channel.template_params(), ["Aziz", "Baraka", "40 000", "14.10.2026"])

    def test_repeated_runs_and_concurrent_workers_do_not_duplicate(self):
        self.at(2026, 10, 13, 10, 0)
        self.run_schedule()
        self.advance(minutes=15)
        self.run_schedule()
        services._schedule_reminders(self.now)  # bypassing the run lock
        self.assertEqual(self.reminders().count(), 1)
        self.assertEqual(len(self.channel.sent), 1)

    def test_a_run_already_in_progress_is_skipped(self):
        self.at(2026, 10, 13, 10, 0)
        cache.add("whatsapp:reminder-run", 1, 60)
        self.assertEqual(services.schedule_reminders(), 0)

    def test_days_before_setting(self):
        self.nsettings.reminder_days_before = 3
        self.nsettings.save()
        self.at(2026, 10, 11, 13, 0)
        self.assertEqual(self.run_schedule(), 1)

    def test_zero_days_before_reminds_on_the_due_date(self):
        self.nsettings.reminder_days_before = 0
        self.nsettings.save()
        self.at(2026, 10, 13, 10, 0)
        self.assertEqual(self.run_schedule(), 0)
        self.at(2026, 10, 14, 10, 0)
        self.assertEqual(self.run_schedule(), 1)

    def test_only_inside_sending_hours(self):
        self.at(2026, 10, 13, 20, 30)
        self.assertEqual(self.run_schedule(), 0)
        self.at(2026, 10, 14, 7, 0)
        self.assertEqual(self.run_schedule(), 0)
        self.at(2026, 10, 14, 9, 0)  # due date morning: upcoming still applies
        self.assertEqual(self.run_schedule(), 1)
        self.assertEqual(self.channel.templates(), ["debt_reminder"])

    def test_custom_sending_hours(self):
        from datetime import time

        self.nsettings.send_window_start = time(14, 0)
        self.nsettings.save()
        self.at(2026, 10, 13, 12, 0)
        self.assertEqual(self.run_schedule(), 0)
        self.at(2026, 10, 13, 14, 0)
        self.assertEqual(self.run_schedule(), 1)

    def test_by_default_exactly_one_overdue_reminder_as_in_the_tz(self):
        sent = []
        for day in range(13, 31):
            self.at(2026, 10, day, 10, 0)
            if self.run_schedule():
                sent.append((day, self.channel.templates()[-1]))
        self.assertEqual(sent, [(13, "debt_reminder"), (15, "debt_overdue")])
        self.assertEqual(self.nsettings.max_reminders_per_debt, 3)  # limit not the reason

    def test_overdue_transition_and_follow_ups_up_to_the_limit(self):
        self.nsettings.overdue_repeat_days = 7  # opt-in, beyond the TZ
        self.nsettings.save()
        self.at(2026, 10, 13, 10, 0)
        self.run_schedule()  # upcoming
        self.at(2026, 10, 14, 10, 0)
        self.assertEqual(self.run_schedule(), 0)  # stage already used
        self.at(2026, 10, 15, 10, 0)
        self.assertEqual(self.run_schedule(), 1)  # overdue transition
        self.assertEqual(self.channel.templates()[-1], "debt_overdue")
        self.assertEqual(self.channel.template_params(), ["Aziz", "Baraka", "40 000", "14.10.2026"])
        self.at(2026, 10, 18, 10, 0)
        self.assertEqual(self.run_schedule(), 0)  # follow-ups are weekly
        self.at(2026, 10, 22, 10, 0)
        self.assertEqual(self.run_schedule(), 1)  # third = default limit
        self.at(2026, 10, 29, 10, 0)
        self.assertEqual(self.run_schedule(), 0)
        self.at(2026, 11, 30, 10, 0)
        self.assertEqual(self.run_schedule(), 0)
        self.assertEqual(self.reminders().count(), 3)

    def test_reminder_limit_setting(self):
        self.nsettings.max_reminders_per_debt = 1
        self.nsettings.save()
        self.at(2026, 10, 13, 10, 0)
        self.run_schedule()
        self.at(2026, 10, 15, 10, 0)
        self.assertEqual(self.run_schedule(), 0)

    def test_paid_debt_gets_no_reminder(self):
        self.add_payment(40_000)
        self.at(2026, 10, 13, 10, 0)
        self.assertEqual(self.run_schedule(), 0)
        self.at(2026, 10, 15, 10, 0)
        self.assertEqual(self.run_schedule(), 0)

    def test_reminder_queued_then_paid_is_cancelled_at_send_time(self):
        self.at(2026, 10, 13, 10, 0)
        with self.captureOnCommitCallbacks(execute=False):
            services.schedule_reminders()  # queued, task not run yet
        self.nsettings.enabled = False  # hold the payment message back
        self.nsettings.save()
        self.add_payment(40_000)
        self.nsettings.enabled = True
        self.nsettings.save()
        self.flush()
        reminder = self.reminders().get()
        self.assertEqual((reminder.status, reminder.error_code), (Status.CANCELLED, "debt_paid"))
        self.assertEqual(self.channel.sent, [])

    def test_partial_payment_reminds_about_the_debt_still_open(self):
        self.at(2026, 10, 11, 12, 30)
        later = self.add_debt(25_000, due_date=date(2026, 10, 20))
        self.advance(minutes=1)
        self.add_payment(40_000)  # covers the first (older) debt only
        self.at(2026, 10, 13, 10, 0)
        self.assertEqual(self.run_schedule(), 0)  # first debt paid -> nothing due
        self.at(2026, 10, 19, 10, 0)
        self.assertEqual(self.run_schedule(), 1)
        self.assertEqual(self.reminders().get().debt_entry_id, later.pk)
        self.assertEqual(self.channel.template_params(), ["Aziz", "Baraka", "25 000", "20.10.2026"])

    def test_debt_without_due_date_is_never_auto_reminded(self):
        self.debt.due_date = None
        self.debt.save()
        self.at(2026, 10, 20, 10, 0)
        self.assertEqual(self.run_schedule(), 0)

    def test_one_automatic_reminder_per_customer_per_day(self):
        self.at(2026, 10, 11, 12, 30)
        self.add_debt(10_000, due_date=date(2026, 10, 14))
        self.at(2026, 10, 13, 10, 0)
        self.assertEqual(self.run_schedule(), 1)
        self.advance(hours=1)
        self.assertEqual(self.run_schedule(), 0)
        self.at(2026, 10, 14, 10, 0)
        self.assertEqual(self.run_schedule(), 1)  # the second debt, next day

    def test_no_consent_or_disabled_shop_gets_no_reminder(self):
        self.at(2026, 10, 13, 10, 0)
        self.nsettings.enabled = False
        self.nsettings.save()
        self.assertEqual(self.run_schedule(), 0)
        self.nsettings.enabled = True
        self.nsettings.save()
        services.revoke_consent(self.customer, self.owner)
        self.assertEqual(self.run_schedule(), 0)


class ReminderEdgeCaseTests(ReminderTestBase):
    """Limits and payments around the reminder policy (docs/WHATSAPP.md §3a)."""

    def test_partial_payment_of_the_same_debt_reminds_about_the_rest(self):
        self.add_payment(15_000)
        self.at(2026, 10, 13, 10, 0)
        self.assertEqual(self.run_schedule(), 1)
        self.assertEqual(self.channel.template_params(), ["Aziz", "Baraka", "25 000", "14.10.2026"])

    def test_full_payment_after_overdue_stops_the_follow_ups(self):
        self.at(2026, 10, 15, 10, 0)
        self.assertEqual(self.run_schedule(), 1)  # overdue
        self.add_payment(40_000)
        self.at(2026, 10, 22, 10, 0)
        self.assertEqual(self.run_schedule(), 0)
        self.assertEqual(self.reminders().count(), 1)

    def test_cancelled_reminders_do_not_use_up_the_limit_but_failed_ones_do(self):
        from .channels import ChannelError

        self.nsettings.max_reminders_per_debt = 2
        self.nsettings.overdue_repeat_days = 7
        self.nsettings.save()
        self.at(2026, 10, 13, 10, 0)
        with self.captureOnCommitCallbacks(execute=False):
            services.schedule_reminders()
        services.revoke_consent(self.customer, self.owner)
        self.flush()  # cancelled: no consent at send time
        services.grant_consent(self.customer, self.owner)
        self.at(2026, 10, 15, 10, 0)
        self.channel.errors = [ChannelError("131026", "x", retryable=False)]
        self.assertEqual(self.run_schedule(), 1)  # overdue-0, fails permanently
        self.at(2026, 10, 22, 10, 0)
        self.assertEqual(self.run_schedule(), 1)  # overdue-1: 2nd counted attempt
        self.at(2026, 10, 29, 10, 0)
        self.assertEqual(self.run_schedule(), 0)  # limit 2 reached (cancelled not counted)
        self.assertEqual(
            list(self.reminders().values_list("status", flat=True)),
            [Status.CANCELLED, Status.FAILED, Status.SENT],
        )

    def test_with_repeats_on_limit_two_still_means_one_before_and_one_overdue(self):
        self.nsettings.max_reminders_per_debt = 2
        self.nsettings.overdue_repeat_days = 7
        self.nsettings.save()
        sent = []
        for day in range(13, 31):
            self.at(2026, 10, day, 10, 0)
            if self.run_schedule():
                sent.append(day)
        self.assertEqual(sent, [13, 15])

    def test_daily_limit_holds_across_debts_and_stages(self):
        self.at(2026, 10, 1, 12, 0)
        self.add_debt(5_000, due_date=date(2026, 10, 5))  # overdue by the 13th
        self.at(2026, 10, 13, 10, 0)
        self.assertEqual(self.run_schedule(), 1)
        self.advance(hours=2)
        self.assertEqual(self.run_schedule(), 0)
        self.at(2026, 10, 14, 10, 0)
        self.assertEqual(self.run_schedule(), 1)
        self.assertEqual(self.reminders().count(), 2)

    def test_a_manual_reminder_does_not_count_against_the_automatic_ones(self):
        self.at(2026, 10, 13, 9, 30)
        with self.captureOnCommitCallbacks(execute=True):
            services.send_manual_reminder(self.customer, self.owner)
        self.flush()
        self.assertEqual(self.run_schedule(), 1)
        kinds = list(self.messages().values_list("kind", flat=True))
        self.assertEqual(kinds.count(Kind.MANUAL_REMINDER), 1)
        self.assertEqual(kinds.count(Kind.DEBT_REMINDER), 1)
