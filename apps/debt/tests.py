from django.test import TestCase

from apps.debt.models import Customer, DebtEntry
from apps.debt.services import add_debt, add_payment
from apps.shops.models import Shop, User


class DebtServicesTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        self.user = User.objects.create_user(
            phone="+998901112233", password="pass1234", shop=self.shop, full_name="Egasi"
        )
        self.customer = Customer.objects.create(shop=self.shop, full_name="Mijoz")

    def test_add_debt_increases_balance(self):
        add_debt(customer=self.customer, user=self.user, amount=50_000)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debt_balance, 50_000)

    def test_add_payment_decreases_balance(self):
        add_debt(customer=self.customer, user=self.user, amount=50_000)
        add_payment(customer=self.customer, user=self.user, amount=20_000)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debt_balance, 30_000)

    def test_add_debt_creates_debt_entry(self):
        add_debt(customer=self.customer, user=self.user, amount=10_000, note="Non olindi")
        entry = DebtEntry.objects.get(customer=self.customer)
        self.assertEqual(entry.entry_type, DebtEntry.EntryType.DEBT)
        self.assertEqual(entry.amount, 10_000)

    def test_add_payment_creates_negative_amount_entry(self):
        add_payment(customer=self.customer, user=self.user, amount=15_000)
        entry = DebtEntry.objects.get(customer=self.customer)
        self.assertEqual(entry.entry_type, DebtEntry.EntryType.PAYMENT)
        self.assertEqual(entry.amount, -15_000)

    def test_multiple_partial_payments_reconcile(self):
        add_debt(customer=self.customer, user=self.user, amount=100_000)
        add_payment(customer=self.customer, user=self.user, amount=30_000)
        add_payment(customer=self.customer, user=self.user, amount=40_000)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debt_balance, 30_000)
