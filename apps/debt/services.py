"""Debt ledger operations (TZ v2 3.5)."""

from datetime import date

from django.db import transaction
from django.db.models import F

from apps.shops.models import User

from .models import Customer, DebtEntry


@transaction.atomic
def add_debt(
    *, customer: Customer, user: User, amount: int, note: str = "", due_date: date | None = None
) -> DebtEntry:
    entry = DebtEntry.objects.create(
        shop=customer.shop,
        customer=customer,
        amount=amount,
        entry_type=DebtEntry.EntryType.DEBT,
        note=note,
        due_date=due_date,
        created_by=user,
    )
    Customer.objects.filter(pk=customer.pk).update(debt_balance=F("debt_balance") + amount)
    return entry


@transaction.atomic
def add_payment(*, customer: Customer, user: User, amount: int, note: str = "") -> DebtEntry:
    entry = DebtEntry.objects.create(
        shop=customer.shop,
        customer=customer,
        amount=-amount,
        entry_type=DebtEntry.EntryType.PAYMENT,
        note=note,
        created_by=user,
    )
    Customer.objects.filter(pk=customer.pk).update(debt_balance=F("debt_balance") - amount)
    return entry


def outstanding_debts(customer: Customer) -> list[tuple[DebtEntry, int]]:
    """Every debt entry of the customer that is not fully paid yet, oldest
    first, with how much of it is still owed.

    The ledger only keeps one running balance, so payments are not tied to a
    particular debt. They are applied first-in-first-out: everything the
    customer has paid (payments and cancelled-receipt credits alike) covers the
    oldest debts first. A debt is "paid" once that running total has reached
    past it — which is what the reminders need to stop on time."""
    entries = list(DebtEntry.objects.filter(customer=customer).order_by("created_at", "id"))
    paid = -sum(e.amount for e in entries if e.entry_type == DebtEntry.EntryType.PAYMENT)
    open_debts = []
    for entry in entries:
        if entry.entry_type != DebtEntry.EntryType.DEBT:
            continue
        covered = min(paid, entry.amount)
        paid -= covered
        if entry.amount - covered > 0:
            open_debts.append((entry, entry.amount - covered))
    return open_debts
