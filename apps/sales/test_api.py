"""Checkout / sales-list API: validation and filtering edge cases."""

from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Batch, Product
from apps.debt.models import Customer
from apps.sales.models import Sale
from apps.shops.models import Shop, ShopSettings, User


class SaleApiTestCase(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        ShopSettings.objects.create(shop=self.shop)
        self.user = User.objects.create_user(
            phone="+998901112233",
            password="pass1234",  # pragma: allowlist secret
            shop=self.shop,
            full_name="Sotuvchi",
        )
        self.piece = self.make_product("Non", Product.Unit.PIECE)
        self.weighed = self.make_product("Un", Product.Unit.KG)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def make_product(self, name, unit):
        product = Product.objects.create(
            shop=self.shop, name=name, unit=unit, min_stock=Decimal("1")
        )
        Batch.objects.create(
            shop=self.shop,
            product=product,
            qty_initial=Decimal("10"),
            qty_remaining=Decimal("10"),
            cost_price=1000,
            sale_price=1500,
        )
        return product

    def checkout(self, product=None, qty="1", payment_type="cash", **extra):
        product = product or self.piece
        payload = {
            "client_id": str(uuid4()),
            "payment_type": payment_type,
            "items": [{"product_id": str(product.id), "qty": qty}],
            **extra,
        }
        return self.api.post("/api/sales/", payload, format="json")


class CheckoutValidationTests(SaleApiTestCase):
    def test_a_cash_sale_is_created(self):
        response = self.checkout(qty="2")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Sale.objects.get().total, 3000)

    def test_a_debt_sale_needs_a_customer(self):
        response = self.checkout(payment_type="debt")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertFalse(Sale.objects.exists())

    def test_a_debt_sale_raises_the_customers_balance(self):
        customer = Customer.objects.create(shop=self.shop, full_name="Mijoz")

        response = self.checkout(payment_type="debt", customer_id=str(customer.id))

        self.assertEqual(response.status_code, 201)
        customer.refresh_from_db()
        self.assertEqual(customer.debt_balance, 1500)

    def test_another_shops_customer_is_not_found(self):
        other = Shop.objects.create(name="Boshqa", phone="+998900000009")
        stranger = Customer.objects.create(shop=other, full_name="Begona")

        response = self.checkout(payment_type="debt", customer_id=str(stranger.id))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Sale.objects.exists())

    def test_an_archived_product_cannot_be_sold(self):
        self.piece.is_active = False
        self.piece.save()

        response = self.checkout()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "product_inactive")

    def test_pieces_must_be_whole(self):
        response = self.checkout(qty="1.5")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_quantity")
        self.assertFalse(Sale.objects.exists())

    def test_a_weighed_product_may_be_fractional(self):
        self.assertEqual(self.checkout(self.weighed, qty="1.5").status_code, 201)

    def test_selling_more_than_is_in_stock_is_refused(self):
        response = self.checkout(qty="11")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Sale.objects.exists())

    def test_an_empty_cart_is_refused(self):
        response = self.api.post(
            "/api/sales/",
            {"client_id": str(uuid4()), "payment_type": "cash", "items": []},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_zero_quantity_is_refused(self):
        self.assertEqual(self.checkout(qty="0").status_code, 400)

    def test_an_unknown_product_is_refused(self):
        response = self.api.post(
            "/api/sales/",
            {
                "client_id": str(uuid4()),
                "payment_type": "cash",
                "items": [{"product_id": str(uuid4()), "qty": "1"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_anonymous_cannot_check_out(self):
        response = APIClient().post("/api/sales/", {}, format="json")

        self.assertEqual(response.status_code, 401)


class SaleListFilterTests(SaleApiTestCase):
    def test_a_malformed_date_is_a_validation_error(self):
        response = self.api.get("/api/sales/?date=21.09.2026")

        self.assertEqual(response.status_code, 400)
        self.assertIn("date", response.json()["error"]["fields"])

    def test_filtering_by_todays_date_finds_todays_sale(self):
        from datetime import date

        self.checkout()

        response = self.api.get(f"/api/sales/?date={date.today().isoformat()}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]["results"]), 1)

    def test_filtering_by_another_date_finds_nothing(self):
        self.checkout()

        response = self.api.get("/api/sales/?date=2000-01-01")

        self.assertEqual(response.json()["data"]["results"], [])

    def test_filtering_by_status(self):
        self.checkout()

        completed = self.api.get("/api/sales/?status=completed").json()["data"]["results"]
        cancelled = self.api.get("/api/sales/?status=cancelled").json()["data"]["results"]

        self.assertEqual((len(completed), len(cancelled)), (1, 0))

    def test_only_this_shops_sales_are_listed(self):
        self.checkout()
        other = Shop.objects.create(name="Boshqa", phone="+998900000009")
        stranger = User.objects.create_user(
            phone="+998901119999",
            password="pass1234",  # pragma: allowlist secret
            shop=other,
            full_name="Begona",
        )
        client = APIClient()
        client.force_authenticate(stranger)

        self.assertEqual(client.get("/api/sales/").json()["data"]["results"], [])
