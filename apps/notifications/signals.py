"""Ledger and customer hooks.

The debt app knows nothing about notifications: these receivers watch its
models instead. Every ledger path (manual debt/payment, debt sale, cancelled
receipt) creates a DebtEntry, so they are all covered in one place, and the
work is deferred to transaction.on_commit — a rolled-back debt never notifies.
A failure here is logged and swallowed: it must never break a sale.
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.debt.models import Customer, DebtEntry

from . import services

logger = logging.getLogger(__name__)


@receiver(post_save, sender=DebtEntry, dispatch_uid="notifications.ledger_entry")
def ledger_entry_saved(sender, instance: DebtEntry, created: bool, raw: bool = False, **kwargs):
    if not created or raw or not services.channel_ready():
        return
    entry_id = instance.pk

    def notify():
        try:
            services.on_ledger_entry(entry_id)
        except Exception:  # noqa: BLE001 — the ledger write already succeeded
            logger.exception("whatsapp: could not queue notification for entry %s", entry_id)

    transaction.on_commit(notify)


@receiver(post_save, sender=Customer, dispatch_uid="notifications.customer_phone")
def customer_saved(sender, instance: Customer, created: bool, raw: bool = False, **kwargs):
    update_fields = kwargs.get("update_fields")
    if created or raw or (update_fields is not None and "phone" not in update_fields):
        return
    services.invalidate_consent_on_phone_change(instance)
