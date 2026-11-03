"""What the bot answers to a customer's message.

Commands (case- and whitespace-insensitive): qarz / qoldiq / the
"Qoldiqni ko'rish" button -> balance; STOP / to'xtat -> unsubscribe;
START -> resubscribe. Anything else gets the help menu.

A number linked to several shops is first asked which one; the pending
choice lives in the cache (Redis in production) for SHOP_CHOICE_TTL, holding
only the customer ids that number may see — a reply naming anything else is
rejected.
"""

import hashlib
import logging
import re

from django.core.cache import cache
from django.utils import timezone

from apps.debt.models import Customer, DebtEntry

from . import services
from . import templates as tpl
from .channels import ListRow
from .models import InboundMessage
from .phone import mask, to_e164

logger = logging.getLogger(__name__)

SHOP_CHOICE_TTL = 10 * 60
# At most this many bot replies to one number per REPLY_WINDOW. Beyond it
# messages are still stored (and Meta still got its 200) but not answered, so
# a stuck client or a prank cannot keep the bot (and the database) busy.
# STOP and START are never limited: consent always takes effect.
REPLY_LIMIT, REPLY_WINDOW = 10, 10 * 60
BALANCE_WORDS = {"qarz", "qoldiq", "qoldiqni ko'rish", "qoldiqni korish", "balans"}
STOP_WORDS = {"stop", "to'xtat", "toxtat", "to'xtatish"}
START_WORDS = {"start"}
CHOICE_PREFIX = "shop:"


def normalize(text: str) -> str:
    text = re.sub(r"[‘’ʻʼ`´]", "'", text or "")
    return re.sub(r"\s+", " ", text).strip().lower().strip(".!")


def _over_reply_limit(phone: str) -> bool:
    key = "whatsapp:replies:" + hashlib.sha256(phone.encode()).hexdigest()[:32]
    cache.add(key, 0, REPLY_WINDOW)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, REPLY_WINDOW)
        count = 1
    return count > REPLY_LIMIT


def _choice_key(phone: str) -> str:
    return "whatsapp:shop-choice:" + hashlib.sha256(phone.encode()).hexdigest()[:32]


def handle(inbound_id) -> str:
    """Process one stored inbound message exactly once."""
    claimed = InboundMessage.objects.filter(
        pk=inbound_id, status=InboundMessage.Status.RECEIVED
    ).update(status=InboundMessage.Status.PROCESSING, updated_at=timezone.now())
    if not claimed:
        return "already_handled"
    inbound = InboundMessage.objects.get(pk=inbound_id)
    try:
        outcome = _respond(inbound)
    except Exception:
        InboundMessage.objects.filter(pk=inbound.pk).update(status=InboundMessage.Status.FAILED)
        logger.exception("whatsapp inbound %s failed", inbound.pk)
        raise
    InboundMessage.objects.filter(pk=inbound.pk).update(
        status=InboundMessage.Status.PROCESSED, processed_at=timezone.now()
    )
    logger.info(
        "whatsapp inbound handled id=%s from=%s outcome=%s",
        inbound.pk,
        mask(inbound.from_phone),
        outcome,
    )
    return outcome


def _reply(inbound: InboundMessage, text: str, **kwargs) -> None:
    message = services.queue_reply(inbound.from_phone, inbound.wa_message_id, text=text, **kwargs)
    services.deliver(message.pk)


def _respond(inbound: InboundMessage) -> str:
    phone = inbound.from_phone
    payload = inbound.payload.strip()
    command = normalize(inbound.text)

    consent_command = command in STOP_WORDS or command in START_WORDS
    if not consent_command and _over_reply_limit(phone):
        return "rate_limited"

    if payload == tpl.BALANCE_PAYLOAD or command in BALANCE_WORDS:
        return _balance(inbound)
    if command in STOP_WORDS:
        revoked = services.revoke_by_phone(phone)
        cache.delete(_choice_key(phone))
        if revoked:
            _reply(inbound, tpl.UNSUBSCRIBED)
            return "stopped"
        return "stop_duplicate"  # already off: one confirmation is enough
    if command in START_WORDS:
        restored, already = services.restore_by_phone(phone)
        if restored:
            _reply(inbound, tpl.RESUBSCRIBED)
            return "restarted"
        if already:
            _reply(inbound, tpl.ALREADY_SUBSCRIBED)
            return "start_duplicate"
        _reply(inbound, tpl.CANNOT_RESUBSCRIBE)
        return "start_refused"

    choice = payload.removeprefix(CHOICE_PREFIX) if payload.startswith(CHOICE_PREFIX) else command
    if choice.isdigit():
        pending = cache.get(_choice_key(phone))
        if pending:
            return _chosen(inbound, pending, int(choice))

    if not services.linked_customers(phone):
        # TZ §6 step 3: a number no shop has linked learns only that.
        _reply(inbound, tpl.NOT_REGISTERED)
        return "not_registered"
    _reply(inbound, tpl.HELP_MENU, buttons=[ListRow(tpl.BALANCE_PAYLOAD, tpl.BALANCE_BUTTON)])
    return "help"


def _balance(inbound: InboundMessage) -> str:
    customers = services.linked_customers(inbound.from_phone)
    if not customers:
        _reply(inbound, tpl.NOT_REGISTERED)
        return "not_registered"
    if len(customers) == 1:
        _send_balance(inbound, customers[0])
        return "balance"

    customers = customers[:10]  # a WhatsApp list holds ten rows
    cache.set(_choice_key(inbound.from_phone), [str(c.pk) for c in customers], SHOP_CHOICE_TTL)
    names = [c.shop.name for c in customers]
    _reply(
        inbound,
        tpl.shop_menu_text(names),
        rows=[ListRow(f"{CHOICE_PREFIX}{i}", name) for i, name in enumerate(names, start=1)],
        list_button=tpl.CHOOSE_SHOP_BUTTON,
    )
    return "choose_shop"


def _chosen(inbound: InboundMessage, pending: list[str], number: int) -> str:
    if not 1 <= number <= len(pending):
        _reply(inbound, tpl.INVALID_CHOICE)
        return "invalid_choice"
    # Re-validate: the choice must still be one of this number's customers.
    allowed = {str(c.pk): c for c in services.linked_customers(inbound.from_phone)}
    customer = allowed.get(pending[number - 1])
    if customer is None:
        cache.delete(_choice_key(inbound.from_phone))
        _reply(inbound, tpl.NOT_REGISTERED)
        return "not_registered"
    cache.delete(_choice_key(inbound.from_phone))
    _send_balance(inbound, customer)
    return "balance"


def _send_balance(inbound: InboundMessage, customer: Customer) -> None:
    # Fresh from the database and strictly this customer's own ledger.
    customer = Customer.objects.select_related("shop").get(pk=customer.pk)
    if to_e164(customer.phone) != inbound.from_phone:
        _reply(inbound, tpl.NOT_REGISTERED)
        return
    operations = list(
        DebtEntry.objects.filter(customer=customer, shop=customer.shop)
        .order_by("-created_at")
        .values_list("created_at", "entry_type", "amount")[:5]
    )
    operations = [(timezone.localtime(at), kind, amount) for at, kind, amount in operations]
    _reply(
        inbound,
        tpl.balance_reply(customer.shop.name, customer.debt_balance, operations),
        shop_id=customer.shop_id,
        customer_id=customer.pk,
    )
