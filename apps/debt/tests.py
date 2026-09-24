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


class CustomerListApiTests(TestCase):
    """The debt page's filter / phone search / summary endpoints."""

    def setUp(self):
        from rest_framework.test import APIClient

        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        self.user = User.objects.create_user(
            phone="+998901112233", password="pass1234", shop=self.shop, full_name="Egasi"
        )
        self.ali = Customer.objects.create(shop=self.shop, full_name="Ali", phone="+998907770011")
        self.vali = Customer.objects.create(shop=self.shop, full_name="Vali")
        add_debt(customer=self.ali, user=self.user, amount=50_000)
        add_debt(customer=self.vali, user=self.user, amount=20_000)
        add_payment(customer=self.vali, user=self.user, amount=20_000)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def get(self, path, **params):
        response = self.client.get(path, params)
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def names(self, **params):
        return [c["full_name"] for c in self.get("/api/customers/", **params)["results"]]

    def test_debtors_filter(self):
        self.assertEqual(self.names(filter="debtors"), ["Ali"])
        self.assertEqual(self.names(), ["Ali", "Vali"])

    def test_search_by_phone(self):
        self.assertEqual(self.names(q="7770011"), ["Ali"])

    def test_summary(self):
        self.assertEqual(self.get("/api/customers/summary/"), {"total_debt": 50_000, "debtors": 1})

    def test_entries_carry_author(self):
        entries = self.get(f"/api/customers/{self.ali.id}/")["entries"]
        self.assertEqual(entries[0]["created_by_name"], "Egasi")
        self.assertIsNone(entries[0]["sale"])
