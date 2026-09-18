"""Debt ledger operations (TZ v2 3.5)."""
from django.db import transaction
from django.db.models import F

from apps.shops.models import User

from .models import Customer, DebtEntry


@transaction.atomic
def add_debt(*, customer: Customer, user: User, amount: int, note: str = "") -> DebtEntry:
    entry = DebtEntry.objects.create(
        shop=customer.shop,
        customer=customer,
        amount=amount,
        entry_type=DebtEntry.EntryType.DEBT,
        note=note,
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
