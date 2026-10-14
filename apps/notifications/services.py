"""WhatsApp debt notifications — consent, queuing and the send boundary.

Flow of a business-initiated message:

1. A ledger event commits (signals.py -> transaction.on_commit), or the
   reminder schedule / a manual action fires.
2. ``queue_*`` writes one OutboundMessage under a unique idempotency key — a
   repeated event finds the existing row instead of making a second one.
3. ``deliver`` claims the row (QUEUED -> SENDING, a conditional UPDATE only
   one worker can win), re-checks consent *under a row lock on the consent*,
   checks the shop's sending hours, builds the template from current data and
   calls the channel. A STOP processed concurrently waits for that lock, so it
   is either applied before the check (nothing is sent) or after the send.
4. Transient failures go back to QUEUED with exponential backoff (at most
   MAX_ATTEMPTS); permanent ones end as FAILED.

A send whose outcome is unknown — the request may have reached Meta but no
answer came back, or the worker died mid-call (row left in SENDING) — is never
sent again: a duplicate debt message is worse than a missing one. Such rows end
in the UNKNOWN status for an operator to check (whatsapp_stats, admin, the
customer card). The idempotency key only stops *us* from creating or claiming
a message twice; it cannot make a repeated Cloud API call safe.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from apps.debt.models import Customer, DebtEntry
from apps.debt.services import outstanding_debts
from apps.shops.models import User

from . import templates as tpl
from .channels import SEND_UNKNOWN, ChannelError, ListRow, StatusEvent, get_channel
from .models import (
    ConsentEvent,
    InboundMessage,
    OutboundMessage,
    ShopNotificationSettings,
    WhatsAppConsent,
)
from .phone import mask, to_e164

logger = logging.getLogger(__name__)

Kind = OutboundMessage.Kind
Status = OutboundMessage.Status

AGGREGATION_WINDOW = timedelta(minutes=10)
MAX_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 30
BACKOFF_MAX_SECONDS = 30 * 60
SENDING_STALE_AFTER = timedelta(minutes=10)
REENQUEUE_AFTER = timedelta(minutes=5)
SERVICE_WINDOW = timedelta(hours=24)

TEMPLATE_KINDS = {
    Kind.DEBT_ADDED,
    Kind.DEBT_REMINDER,
    Kind.DEBT_OVERDUE,
    Kind.PAYMENT_RECEIVED,
    Kind.DEBT_CLOSED,
    Kind.MANUAL_REMINDER,
}
REMINDER_KINDS = {Kind.DEBT_REMINDER, Kind.DEBT_OVERDUE}

# Status order for webhook updates: a lower one never replaces a higher one.
STATUS_RANK = {
    Status.QUEUED: 0,
    Status.SENDING: 0,
    Status.SENT: 1,
    Status.DELIVERED: 2,
    Status.READ: 3,
}


class NotificationRejected(Exception):
    """Why a staff action (consent, manual reminder) cannot go ahead.
    ``message`` is shown to the user as is."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def channel_ready() -> bool:
    return get_channel().is_configured()


# --------------------------------------------------------------------------
# Sending hours
# --------------------------------------------------------------------------


def next_send_time(nsettings: ShopNotificationSettings, at: datetime) -> datetime:
    """``at`` itself if it falls inside the shop's sending hours (local time,
    settings.TIME_ZONE), otherwise the next moment the window opens."""
    local = timezone.localtime(at)
    start, end = nsettings.send_window_start, nsettings.send_window_end
    if start <= local.time() < end:
        return at
    opens = local.date() if local.time() < start else local.date() + timedelta(days=1)
    return timezone.make_aware(datetime.combine(opens, start))


def in_send_window(nsettings: ShopNotificationSettings, at: datetime) -> bool:
    return next_send_time(nsettings, at) == at


# --------------------------------------------------------------------------
# Consent
# --------------------------------------------------------------------------


def current_consent(customer: Customer) -> WhatsAppConsent | None:
    """The consent that allows messaging this customer right now, if any."""
    consent = WhatsAppConsent.objects.filter(customer=customer, is_active=True).first()
    if consent and consent.phone == to_e164(customer.phone):
        return consent
    return None


@transaction.atomic
def grant_consent(customer: Customer, user: User) -> WhatsAppConsent:
    """Staff record that the customer agreed to WhatsApp messages."""
    phone = to_e164(customer.phone)
    if not phone:
        raise NotificationRejected(
            "invalid_phone",
            "Mijozning telefon raqami noto'g'ri. +998 XX XXX XX XX ko'rinishida kiriting.",
        )
    consent = WhatsAppConsent.objects.select_for_update().filter(customer=customer).first()
    if consent is None:
        # Nothing to lock yet: two staff taps at once would both insert. The
        # loser of the unique-customer race locks the winner's row instead.
        try:
            with transaction.atomic():
                WhatsAppConsent.objects.create(
                    customer=customer, shop_id=customer.shop_id, phone=phone
                )
        except IntegrityError:
            pass
        consent = WhatsAppConsent.objects.select_for_update().get(customer=customer)
    if consent.is_active and consent.phone == phone:
        return consent
    now = timezone.now()
    consent.phone = phone
    consent.is_active = True
    consent.granted_at = now
    consent.granted_by = user
    consent.revoked_at = None
    consent.revoke_reason = ""
    consent.save()
    ConsentEvent.objects.create(
        consent=consent,
        action=ConsentEvent.Action.GRANTED,
        source=ConsentEvent.Source.STAFF,
        phone=phone,
        actor=user,
    )
    return consent


def _revoke(consent: WhatsAppConsent, reason: str, source: str, actor: User | None = None):
    consent.is_active = False
    consent.revoked_at = timezone.now()
    consent.revoke_reason = reason
    consent.save(update_fields=["is_active", "revoked_at", "revoke_reason", "updated_at"])
    ConsentEvent.objects.create(
        consent=consent,
        action=ConsentEvent.Action.REVOKED,
        source=source,
        phone=consent.phone,
        reason=reason,
        actor=actor,
    )


@transaction.atomic
def revoke_consent(customer: Customer, user: User) -> WhatsAppConsent | None:
    consent = WhatsAppConsent.objects.select_for_update().filter(customer=customer).first()
    if consent and consent.is_active:
        _revoke(
            consent,
            WhatsAppConsent.RevokeReason.STAFF,
            ConsentEvent.Source.STAFF,
            actor=user,
        )
    return consent


def invalidate_consent_on_phone_change(customer: Customer) -> None:
    """A new number has not agreed to anything: the old consent stops here and
    the shop must record consent again for the new one."""
    with transaction.atomic():
        consent = (
            WhatsAppConsent.objects.select_for_update()
            .filter(customer=customer, is_active=True)
            .first()
        )
        if consent and consent.phone != to_e164(customer.phone):
            _revoke(
                consent,
                WhatsAppConsent.RevokeReason.PHONE_CHANGED,
                ConsentEvent.Source.SYSTEM,
            )
            logger.info("whatsapp consent %s invalidated: phone changed", consent.pk)


@transaction.atomic
def revoke_by_phone(phone: str) -> int:
    """STOP from the customer: every shop stops messaging this number."""
    # Locked in one fixed order, so two STOPs for a number known to several
    # shops cannot deadlock on each other.
    consents = list(
        WhatsAppConsent.objects.select_for_update()
        .filter(phone=phone, is_active=True)
        .order_by("pk")
    )
    for consent in consents:
        _revoke(
            consent,
            WhatsAppConsent.RevokeReason.CUSTOMER_STOP,
            ConsentEvent.Source.WHATSAPP,
        )
    # Nothing queued for this number may go out now; deliver() would refuse
    # anyway, this just makes the ledger UI honest straight away.
    OutboundMessage.objects.filter(
        to_phone=phone, status=Status.QUEUED, kind__in=TEMPLATE_KINDS
    ).update(status=Status.CANCELLED, error_code="no_consent", updated_at=timezone.now())
    return len(consents)


@transaction.atomic
def restore_by_phone(phone: str) -> tuple[int, int]:
    """START: re-enable only what the customer themselves switched off with
    STOP — never consent a shop never recorded, nor one dropped because the
    number changed or that staff removed. Returns (restored, already_active)."""
    consents = list(WhatsAppConsent.objects.select_for_update().filter(phone=phone).order_by("pk"))
    restored = already = 0
    for consent in consents:
        if consent.is_active:
            already += 1
            continue
        if consent.revoke_reason != WhatsAppConsent.RevokeReason.CUSTOMER_STOP:
            continue
        if to_e164(consent.customer.phone) != phone or not consent.customer.is_active:
            continue
        consent.is_active = True
        consent.revoked_at = None
        consent.revoke_reason = ""
        consent.save(update_fields=["is_active", "revoked_at", "revoke_reason", "updated_at"])
        ConsentEvent.objects.create(
            consent=consent,
            action=ConsentEvent.Action.RESTORED,
            source=ConsentEvent.Source.WHATSAPP,
            phone=phone,
        )
        restored += 1
    return restored, already


def linked_customers(phone: str) -> list[Customer]:
    """Customers the bot may talk about to this number: the shop linked the
    number to WhatsApp (a consent row, even if later STOPped), the customer
    card still carries that number, and the shop has the feature on."""
    consents = (
        WhatsAppConsent.objects.filter(phone=phone, customer__is_active=True)
        .exclude(revoke_reason=WhatsAppConsent.RevokeReason.PHONE_CHANGED)
        .exclude(revoke_reason=WhatsAppConsent.RevokeReason.STAFF)
        .select_related("customer__shop")
        .order_by("customer__shop__name")
    )
    enabled = set(
        ShopNotificationSettings.objects.filter(
            enabled=True, shop_id__in=[c.shop_id for c in consents]
        ).values_list("shop_id", flat=True)
    )
    return [
        c.customer for c in consents if c.shop_id in enabled and to_e164(c.customer.phone) == phone
    ]


# --------------------------------------------------------------------------
# Queuing
# --------------------------------------------------------------------------


def _eligible(customer: Customer, consent: WhatsAppConsent | None):
    """(settings) when this customer may get business messages now, else None."""
    if not channel_ready():
        return None
    if not consent or not consent.is_active or consent.phone != to_e164(customer.phone):
        return None
    nsettings = ShopNotificationSettings.for_shop(customer.shop_id)
    return nsettings if nsettings.enabled else None


def _create(**fields) -> tuple[OutboundMessage, bool]:
    try:
        with transaction.atomic():
            return OutboundMessage.objects.create(**fields), True
    except IntegrityError:
        return OutboundMessage.objects.get(idempotency_key=fields["idempotency_key"]), False


def _enqueue(message: OutboundMessage) -> None:
    """Hand the row to a worker once the surrounding transaction commits. If
    the broker is unreachable the row simply waits for the sweeper."""

    def send():
        from .tasks import send_message

        delay = max((message.send_after - timezone.now()).total_seconds(), 0)
        try:
            # Long waits (night-time deferral) are left to the sweeper: a Redis
            # ETA task longer than the visibility timeout gets redelivered.
            if delay <= 30 * 60:
                send_message.apply_async((str(message.pk),), countdown=delay)
                OutboundMessage.objects.filter(pk=message.pk).update(enqueued_at=timezone.now())
        except Exception:  # noqa: BLE001 — the sweeper picks it up
            logger.warning("whatsapp enqueue failed for message %s", message.pk, exc_info=True)

    transaction.on_commit(send)


def on_ledger_entry(entry_id) -> None:
    """Called after a DebtEntry has committed (signals.py)."""
    entry = DebtEntry.objects.select_related("customer").filter(pk=entry_id).first()
    if entry is None:
        return
    if entry.entry_type == DebtEntry.EntryType.DEBT:
        queue_debt_added(entry)
    elif entry.sale_id is None:
        # A payment credit with a sale is a cancelled receipt, not money the
        # customer paid — do not thank them for it.
        queue_payment(entry)


def queue_debt_added(entry: DebtEntry) -> OutboundMessage | None:
    """One message per customer for every debt added within
    AGGREGATION_WINDOW of the first: the first event opens a batch that is
    sent when the window closes; later ones join it."""
    now = timezone.now()
    with transaction.atomic():
        # Locking the consent row serialises concurrent debt events for the
        # same customer, so two of them cannot both open a batch.
        consent = (
            WhatsAppConsent.objects.select_for_update()
            .filter(customer_id=entry.customer_id)
            .first()
        )
        nsettings = _eligible(entry.customer, consent)
        if nsettings is None:
            return None
        entry_key = str(entry.pk)
        recent = list(
            OutboundMessage.objects.select_for_update().filter(
                customer_id=entry.customer_id,
                kind=Kind.DEBT_ADDED,
                created_at__gte=now - 2 * AGGREGATION_WINDOW,
            )
        )
        for message in recent:
            if entry_key in message.params.get("entry_ids", []):
                return message  # the same event delivered twice
        batch = next(
            (
                m
                for m in recent
                if m.status == Status.QUEUED and m.created_at > now - AGGREGATION_WINDOW
            ),
            None,
        )
        if batch:
            batch.params["entry_ids"].append(entry_key)
            batch.save(update_fields=["params", "updated_at"])
            return batch
        message, created = _create(
            shop_id=entry.shop_id,
            customer_id=entry.customer_id,
            debt_entry=entry,
            to_phone=consent.phone,
            kind=Kind.DEBT_ADDED,
            params={"entry_ids": [entry_key]},
            idempotency_key=f"debt_added:{entry.pk}",
            send_after=next_send_time(nsettings, now + AGGREGATION_WINDOW),
        )
        if created:
            _enqueue(message)
        return message


def queue_payment(entry: DebtEntry) -> OutboundMessage | None:
    customer = entry.customer
    consent = WhatsAppConsent.objects.filter(customer=customer).first()
    nsettings = _eligible(customer, consent)
    if nsettings is None:
        return None
    paid = -entry.amount
    # The balance right after this payment, from the ledger itself — the
    # running total on Customer may already include later entries.
    balance_after = (
        DebtEntry.objects.filter(customer=customer)
        .filter(Q(created_at__lt=entry.created_at) | Q(pk=entry.pk))
        .aggregate(total=Sum("amount"))["total"]
        or 0
    )
    # The whole committed ledger now. Two payments can commit in the opposite
    # order to their created_at (one waited for the customer row lock); then
    # neither "as of" snapshot reaches zero, yet the debt is closed — the
    # payment whose callback sees the final state must still announce it.
    balance_now = (
        DebtEntry.objects.filter(customer=customer).aggregate(total=Sum("amount"))["total"] or 0
    )
    closes = balance_after <= 0 < balance_after + paid or balance_now <= 0 < balance_now + paid
    params = {"entry_id": str(entry.pk), "amount": paid, "balance": balance_after}
    common = {
        "shop_id": entry.shop_id,
        "customer_id": customer.pk,
        "debt_entry": entry,
        "to_phone": consent.phone,
        "send_after": next_send_time(nsettings, timezone.now()),
    }

    if closes:
        # One closure per debt "cycle": the key is the last debt that this
        # payment cleared, so two payments racing to close the same debts
        # cannot both announce it.
        last_debt = (
            DebtEntry.objects.filter(
                customer=customer,
                entry_type=DebtEntry.EntryType.DEBT,
                created_at__lte=entry.created_at,
            )
            .order_by("-created_at", "-id")
            .values_list("pk", flat=True)
            .first()
        )
        message, created = _create(
            **common,
            kind=Kind.DEBT_CLOSED,
            params=params,
            idempotency_key=f"debt_closed:{customer.pk}:{last_debt}",
        )
        if created:
            _enqueue(message)
            return message
        if message.params.get("entry_id") == str(entry.pk):
            return message  # same event again

    message, created = _create(
        **common,
        kind=Kind.PAYMENT_RECEIVED,
        params=params,
        idempotency_key=f"payment:{entry.pk}",
    )
    if created:
        _enqueue(message)
    return message


def manual_reminder_key(customer_id, day) -> str:
    return f"manual:{customer_id}:{day.isoformat()}"


def send_manual_reminder(customer: Customer, user: User) -> OutboundMessage:
    """Staff pressed "Eslatma yuborish". At most one per customer per day."""
    if not channel_ready():
        raise NotificationRejected(
            "whatsapp_not_configured", "WhatsApp hali ulanmagan. Administratorga murojaat qiling."
        )
    nsettings = ShopNotificationSettings.for_shop(customer.shop_id)
    if not nsettings.enabled:
        raise NotificationRejected(
            "notifications_disabled",
            "Do'konda WhatsApp xabarlari o'chirilgan. Sozlamalardan yoqing.",
        )
    consent = current_consent(customer)
    if consent is None:
        raise NotificationRejected("no_consent", "Mijoz WhatsApp xabarlariga rozilik bermagan.")
    customer.refresh_from_db(fields=["debt_balance"])
    if customer.debt_balance <= 0:
        raise NotificationRejected("no_debt", "Mijozning qarzi yo'q.")

    send_after = next_send_time(nsettings, timezone.now())
    message, created = _create(
        shop_id=customer.shop_id,
        customer_id=customer.pk,
        to_phone=consent.phone,
        kind=Kind.MANUAL_REMINDER,
        params={"requested_by": str(user.pk)},
        # Keyed by the day the customer *receives* it, not the day of the
        # press: 23:50 (deferred to 09:00) and 00:10 are the same morning.
        idempotency_key=manual_reminder_key(customer.pk, timezone.localdate(send_after)),
        send_after=send_after,
    )
    if not created:
        raise NotificationRejected(
            "already_sent_today",
            "Bu mijozga bugun eslatma yuborilgan. Ertaga qayta urinib ko'ring.",
        )
    _enqueue(message)
    return message


def queue_reply(
    phone: str,
    key: str,
    *,
    text: str,
    rows: list[ListRow] | None = None,
    buttons: list[ListRow] | None = None,
    list_button: str = "",
    shop_id=None,
    customer_id=None,
) -> OutboundMessage:
    """A bot answer to something the customer just wrote — free text inside
    the 24-hour service window, so no template and no consent needed (the
    customer asked). Sent right away by the caller."""
    params = {"text": text}
    if rows:
        params["rows"] = [r.__dict__ for r in rows]
        params["list_button"] = list_button
    if buttons:
        params["buttons"] = [b.__dict__ for b in buttons]
    message, _ = _create(
        shop_id=shop_id,
        customer_id=customer_id,
        to_phone=phone,
        kind=Kind.REPLY,
        params=params,
        idempotency_key=f"reply:{key}"[:120],
        send_after=timezone.now(),
    )
    return message


# --------------------------------------------------------------------------
# Reminders (Celery Beat, see tasks.schedule_debt_reminders)
# --------------------------------------------------------------------------


def _reminder_stage(due, today, days_before: int, repeat_days: int = 0) -> tuple[str, str] | None:
    """(stage key, kind) a debt due on ``due`` is in today, or None.

    upcoming:   from ``days_before`` days ahead up to the due date itself
    overdue-0:  from the day after the due date (the overdue transition)
    overdue-N:  only if the shop opted in (``repeat_days`` > 0): every
                ``repeat_days`` after that, until max_reminders_per_debt"""
    if today < due - timedelta(days=days_before):
        return None
    if today <= due:
        return "upcoming", Kind.DEBT_REMINDER
    n = ((today - due).days - 1) // repeat_days if repeat_days else 0
    return f"overdue-{n}", Kind.DEBT_OVERDUE


def schedule_reminders(now: datetime | None = None) -> int:
    """Queue today's due/overdue reminders. Safe to run often and from
    several beat/worker processes: a cache lock keeps runs from overlapping,
    and the per-debt-per-stage idempotency key makes a duplicate impossible
    even without it."""
    if not channel_ready():
        return 0
    if not cache.add("whatsapp:reminder-run", 1, timeout=10 * 60):
        return 0
    try:
        return _schedule_reminders(now or timezone.now())
    finally:
        cache.delete("whatsapp:reminder-run")


def _schedule_reminders(now: datetime) -> int:
    today = timezone.localdate(now)
    day_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    queued = 0
    for nsettings in ShopNotificationSettings.objects.filter(enabled=True):
        if not in_send_window(nsettings, now):
            continue  # picked up on a later run, once the window opens
        consents = WhatsAppConsent.objects.filter(
            shop_id=nsettings.shop_id,
            is_active=True,
            customer__is_active=True,
            customer__debt_balance__gt=0,
        ).select_related("customer")
        for consent in consents:
            customer = consent.customer
            if consent.phone != to_e164(customer.phone):
                continue
            # One automatic reminder per customer per day at most, however
            # many of their debts are due.
            if OutboundMessage.objects.filter(
                customer=customer, kind__in=REMINDER_KINDS, created_at__gte=day_start
            ).exists():
                continue
            candidate = _pick_reminder(customer, nsettings, today)
            if candidate is None:
                continue
            entry, stage, kind = candidate
            message, created = _create(
                shop_id=customer.shop_id,
                customer_id=customer.pk,
                debt_entry=entry,
                to_phone=consent.phone,
                kind=kind,
                params={"stage": stage},
                idempotency_key=f"reminder:{entry.pk}:{stage}",
                send_after=now,
            )
            if created:
                _enqueue(message)
                queued += 1
    if queued:
        logger.info("whatsapp reminders queued=%s", queued)
    return queued


def _pick_reminder(customer, nsettings, today):
    for entry, _remaining in sorted(
        (pair for pair in outstanding_debts(customer) if pair[0].due_date),
        key=lambda pair: pair[0].due_date,
    ):
        stage = _reminder_stage(
            entry.due_date,
            today,
            nsettings.reminder_days_before,
            nsettings.overdue_repeat_days,
        )
        if stage is None:
            continue
        sent = (
            OutboundMessage.objects.filter(debt_entry=entry, kind__in=REMINDER_KINDS)
            .exclude(status=Status.CANCELLED)
            .count()
        )
        if sent >= nsettings.max_reminders_per_debt:
            continue
        if OutboundMessage.objects.filter(
            idempotency_key=f"reminder:{entry.pk}:{stage[0]}"
        ).exists():
            continue
        return entry, stage[0], stage[1]
    return None


# --------------------------------------------------------------------------
# The send boundary
# --------------------------------------------------------------------------


@dataclass
class _Built:
    template: str = ""
    params: list | None = None
    text: str = ""
    rows: list | None = None
    buttons: list | None = None
    list_button: str = ""
    cancel: str = ""  # reason not to send at all


def _build(message: OutboundMessage) -> _Built:
    """Message content from *current* data, so a debt paid in the meantime
    stops its reminder and totals are never stale."""
    if message.kind == Kind.REPLY:
        p = message.params
        return _Built(
            text=p.get("text", ""),
            rows=[ListRow(**r) for r in p.get("rows", [])] or None,
            buttons=[ListRow(**b) for b in p.get("buttons", [])] or None,
            list_button=p.get("list_button", ""),
        )

    customer = message.customer
    if customer is None or not customer.is_active:
        return _Built(cancel="customer_inactive")
    customer.refresh_from_db(fields=["debt_balance", "full_name", "phone"])
    name = tpl.param(customer.full_name)
    shop = tpl.param(message.shop.name)
    balance = customer.debt_balance
    today = timezone.localdate()

    if message.kind == Kind.DEBT_ADDED:
        entries = list(
            DebtEntry.objects.filter(customer=customer, pk__in=message.params.get("entry_ids", []))
        )
        added = sum(e.amount for e in entries)
        if not entries or balance <= 0:
            return _Built(cancel="debt_paid")
        dues = [e.due_date for e in entries if e.due_date]
        return _Built(
            template=tpl.DEBT_ADDED.name,
            params=[
                name,
                shop,
                tpl.money(added),
                tpl.money(balance),
                tpl.day(min(dues) if dues else None),
            ],
        )

    if message.kind == Kind.PAYMENT_RECEIVED:
        p = message.params
        return _Built(
            template=tpl.PAYMENT_RECEIVED.name,
            params=[name, shop, tpl.money(p["amount"]), tpl.money(max(p["balance"], 0))],
        )

    if message.kind == Kind.DEBT_CLOSED:
        return _Built(
            template=tpl.DEBT_CLOSED.name,
            params=[name, shop, tpl.money(message.params["amount"])],
        )

    open_debts = outstanding_debts(customer)
    if balance <= 0 or not open_debts:
        return _Built(cancel="debt_paid")
    overdue = [(e, r) for e, r in open_debts if e.due_date and e.due_date < today]

    if message.kind in REMINDER_KINDS:
        if message.debt_entry_id not in {e.pk for e, _ in open_debts}:
            return _Built(cancel="debt_paid")
        entry = message.debt_entry
        if message.kind == Kind.DEBT_OVERDUE:
            return _Built(
                template=tpl.DEBT_OVERDUE.name,
                params=[name, shop, tpl.money(sum(r for _, r in overdue)), tpl.day(entry.due_date)],
            )
        return _Built(
            template=tpl.DEBT_REMINDER.name,
            params=[name, shop, tpl.money(balance), tpl.day(entry.due_date)],
        )

    # Manual reminder: the overdue wording when something is overdue.
    if overdue:
        earliest = min(e.due_date for e, _ in overdue)
        return _Built(
            template=tpl.DEBT_OVERDUE.name,
            params=[name, shop, tpl.money(sum(r for _, r in overdue)), tpl.day(earliest)],
        )
    upcoming = [e.due_date for e, _ in open_debts if e.due_date]
    return _Built(
        template=tpl.DEBT_REMINDER.name,
        params=[name, shop, tpl.money(balance), tpl.day(min(upcoming) if upcoming else None)],
    )


def _in_service_window(phone: str, now: datetime) -> bool:
    last = (
        InboundMessage.objects.filter(from_phone=phone)
        .order_by("-received_at")
        .values_list("received_at", flat=True)
        .first()
    )
    return bool(last and now - last < SERVICE_WINDOW)


def _finish(message: OutboundMessage, **fields) -> None:
    for name, value in fields.items():
        setattr(message, name, value)
    message.save(update_fields=[*fields, "updated_at"])


def deliver(message_id) -> str:
    """Send one queued message if — and only if — it is still allowed."""
    now = timezone.now()
    claimed = OutboundMessage.objects.filter(
        pk=message_id, status=Status.QUEUED, send_after__lte=now
    ).update(status=Status.SENDING, claimed_at=now, attempts=F("attempts") + 1, updated_at=now)
    if not claimed:
        return "not_due_or_taken"

    message = OutboundMessage.objects.select_related("customer", "shop", "debt_entry").get(
        pk=message_id
    )
    channel = get_channel()
    with transaction.atomic():
        if message.kind in TEMPLATE_KINDS:
            # Held until the send is recorded: a STOP being processed right
            # now waits here, so the order of the two is never ambiguous.
            consent = (
                WhatsAppConsent.objects.select_for_update()
                .filter(customer_id=message.customer_id)
                .first()
            )
            customer_phone = to_e164(message.customer.phone) if message.customer else None
            if not (
                consent
                and consent.is_active
                and consent.phone == message.to_phone
                and customer_phone == message.to_phone
            ):
                _finish(message, status=Status.CANCELLED, error_code="no_consent")
                return "cancelled"
            nsettings = ShopNotificationSettings.for_shop(message.shop_id)
            if not nsettings.enabled:
                _finish(message, status=Status.CANCELLED, error_code="notifications_disabled")
                return "cancelled"
            if not in_send_window(nsettings, now):
                _finish(
                    message,
                    status=Status.QUEUED,
                    send_after=next_send_time(nsettings, now),
                    attempts=F("attempts") - 1,
                    enqueued_at=None,
                )
                return "deferred"
        elif not _in_service_window(message.to_phone, now):
            _finish(message, status=Status.CANCELLED, error_code="outside_service_window")
            return "cancelled"

        if not channel.is_configured():
            _finish(message, status=Status.FAILED, error_code="not_configured", failed_at=now)
            return "failed"

        built = _build(message)
        if built.cancel:
            _finish(message, status=Status.CANCELLED, error_code=built.cancel)
            return "cancelled"

        try:
            if built.template:
                result = channel.send_template(
                    message.to_phone,
                    built.template,
                    settings.WHATSAPP_TEMPLATE_LANGUAGE,
                    built.params,
                    quick_reply=tpl.BALANCE_PAYLOAD
                    if settings.WHATSAPP_TEMPLATE_QUICK_REPLY
                    else "",
                )
            elif built.rows and channel.supports_interactive:
                result = channel.send_list(
                    message.to_phone, built.text, built.list_button, built.rows
                )
            elif built.buttons and channel.supports_interactive:
                result = channel.send_buttons(message.to_phone, built.text, built.buttons)
            else:
                result = channel.send_text(message.to_phone, built.text)
        except ChannelError as exc:
            message.refresh_from_db(fields=["attempts"])
            return _record_failure(message, exc, now)

        params = dict(message.params)
        if built.template:
            params["template"] = built.template
            params["template_params"] = built.params
        _finish(
            message,
            status=Status.SENT,
            external_id=result.external_id,
            sent_at=now,
            params=params,
            error_code="",
            error_detail="",
        )
    logger.info(
        "whatsapp outbound sent kind=%s message=%s shop=%s to=%s",
        message.kind,
        message.pk,
        message.shop_id,
        mask(message.to_phone),
    )
    return "sent"


def _record_failure(message: OutboundMessage, exc: ChannelError, now: datetime) -> str:
    if exc.code == SEND_UNKNOWN:
        _finish(
            message,
            status=Status.UNKNOWN,
            failed_at=now,
            error_code=SEND_UNKNOWN,
            error_detail=exc.detail,
        )
        outcome = "unknown"
    elif exc.retryable and message.attempts < MAX_ATTEMPTS:
        delay = min(BACKOFF_BASE_SECONDS * 2 ** (message.attempts - 1), BACKOFF_MAX_SECONDS)
        _finish(
            message,
            status=Status.QUEUED,
            send_after=now + timedelta(seconds=delay),
            enqueued_at=None,
            error_code=exc.code[:40],
            error_detail=exc.detail,
        )
        outcome = "retry"
    else:
        _finish(
            message,
            status=Status.FAILED,
            failed_at=now,
            error_code=exc.code[:40],
            error_detail=exc.detail,
        )
        outcome = "failed"
    logger.warning(
        "whatsapp outbound %s kind=%s message=%s attempt=%s code=%s to=%s",
        outcome,
        message.kind,
        message.pk,
        message.attempts,
        exc.code,
        mask(message.to_phone),
    )
    return outcome


def dispatch_due(now: datetime | None = None) -> int:
    """Sweeper (every minute): hand due rows to workers, including ones whose
    original task was lost, deferred overnight, or waiting for a retry; and
    give up on rows stuck mid-send."""
    from .tasks import send_message

    now = now or timezone.now()
    stale = OutboundMessage.objects.filter(
        status=Status.SENDING, claimed_at__lt=now - SENDING_STALE_AFTER
    ).update(status=Status.UNKNOWN, error_code=SEND_UNKNOWN, failed_at=now, updated_at=now)
    if stale:
        logger.warning("whatsapp outbound stuck in sending, marked unknown count=%s", stale)

    due = list(
        OutboundMessage.objects.filter(status=Status.QUEUED, send_after__lte=now)
        .filter(Q(enqueued_at__isnull=True) | Q(enqueued_at__lt=now - REENQUEUE_AFTER))
        .order_by("send_after")
        .values_list("pk", flat=True)[:500]
    )
    if due:
        OutboundMessage.objects.filter(pk__in=due).update(enqueued_at=now)
    for pk in due:
        send_message.delay(str(pk))
    return len(due)


# --------------------------------------------------------------------------
# Status webhooks
# --------------------------------------------------------------------------


def apply_status(event: StatusEvent) -> bool:
    """Apply a sent/delivered/read/failed update. Duplicates and late arrivals
    are harmless: a status only ever moves forward, and FAILED/READ are final."""
    with transaction.atomic():
        message = (
            OutboundMessage.objects.select_for_update().filter(external_id=event.message_id).first()
        )
        if message is None:
            return False
        at = event.timestamp or timezone.now()
        fields = {}
        timestamp_field = {
            "sent": "sent_at",
            "delivered": "delivered_at",
            "read": "read_at",
            "failed": "failed_at",
        }[event.status]
        if getattr(message, timestamp_field) is None:
            fields[timestamp_field] = at

        if event.status == "failed":
            if message.status not in {Status.DELIVERED, Status.READ, Status.FAILED}:
                fields["status"] = Status.FAILED
                fields["error_code"] = (
                    f"wa_{event.error_code}"[:40] if event.error_code else "wa_failed"
                )
                fields["error_detail"] = event.error_title
        elif message.status != Status.FAILED and STATUS_RANK[event.status] > STATUS_RANK.get(
            message.status, 0
        ):
            fields["status"] = event.status

        if fields:
            _finish(message, **fields)
    if event.status == "failed":
        logger.warning(
            "whatsapp delivery failed message=%s code=%s", message.pk, event.error_code or "-"
        )
    return True


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def stats(since: datetime | None = None) -> dict:
    """Counts for monitoring — no customer data."""
    from django.db.models import Count

    since = since or timezone.now() - timedelta(hours=24)
    recent = OutboundMessage.objects.filter(created_at__gte=since)
    return {
        "queue_depth": OutboundMessage.objects.filter(status=Status.QUEUED).count(),
        "sending": OutboundMessage.objects.filter(status=Status.SENDING).count(),
        # Sends whose outcome is unknown — check these by hand (all time).
        "unknown_total": OutboundMessage.objects.filter(status=Status.UNKNOWN).count(),
        "by_status": dict(recent.values_list("status").annotate(n=Count("id"))),
        "by_kind": dict(recent.values_list("kind").annotate(n=Count("id"))),
        "failed_codes": dict(
            recent.filter(status=Status.FAILED).values_list("error_code").annotate(n=Count("id"))
        ),
        "inbound": InboundMessage.objects.filter(received_at__gte=since).count(),
    }
