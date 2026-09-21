"""The permission matrix, as executable rules.

One table says, for every API endpoint, what an owner, a seller and an
anonymous caller get. If a view changes who may use it, this table fails —
that is the point: role logic is a rule written down here, not an accident
of which decorator a view happens to carry.

Owner-only: products create/edit/archive/delete, batches (kirim) and write-offs,
reports and exports, settings. Everything else is open to both roles, and a
seller additionally never sees cost data (see HiddenCostDataTests) and may
only cancel their own receipt from today (see CancelRuleTests).
"""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Batch, Product
from apps.debt.models import Customer
from apps.sales.models import Sale
from apps.sales.services import CartLine, cancel_sale, create_sale
from apps.shops.models import Shop, ShopSettings, User

OWNER, SELLER = "owner", "seller"


class RoleFixtureMixin:
    def setUp(self):
        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        ShopSettings.objects.create(shop=self.shop)
        self.owner = User.objects.create_user(
            phone="+998901000001", password="pass1234", shop=self.shop, full_name="Egasi"
        )
        self.seller = User.objects.create_user(
            phone="+998901000002",
            password="pass1234",
            shop=self.shop,
            full_name="Sotuvchi",
            role=User.Role.SELLER,
        )
        self.other_seller = User.objects.create_user(
            phone="+998901000003",
            password="pass1234",
            shop=self.shop,
            full_name="Boshqa sotuvchi",
            role=User.Role.SELLER,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name="Un",
            unit=Product.Unit.KG,
            barcode="4780000000012",
            markup_amount=3000,
            min_stock=Decimal("5"),
        )
        self.batch = Batch.objects.create(
            shop=self.shop,
            product=self.product,
            qty_initial=Decimal("100"),
            qty_remaining=Decimal("100"),
            cost_price=1000,
            sale_price=1300,
        )
        self.customer = Customer.objects.create(shop=self.shop, full_name="Aziz")

    def client_for(self, user):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def sell(self, user, qty="1", when=None):
        sale = create_sale(
            shop=self.shop,
            user=user,
            client_id=uuid4(),
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=[CartLine(product=self.product, qty=Decimal(qty))],
        )
        if when is not None:
            Sale.objects.filter(pk=sale.pk).update(sold_at=when)
            sale.refresh_from_db()
        return sale


class RoleMatrixTests(RoleFixtureMixin, TestCase):
    def matrix(self):
        """(method, url, payload, owner status, seller status)."""
        p, b, c = self.product, self.batch, self.customer
        # Never sold, so deleting it is allowed (p is sold by the sale row below).
        spare = Product.objects.create(
            shop=self.shop, name="Ortiqcha", unit=Product.Unit.PIECE, min_stock=Decimal("1")
        )
        sale = {
            "client_id": str(uuid4()),
            "payment_type": "cash",
            "items": [{"product_id": str(p.id), "qty": "1"}],
        }
        return [
            # ---- open to both roles
            ("GET", "/api/products/", None, 200, 200),
            ("GET", f"/api/products/{p.id}/", None, 200, 200),
            ("GET", f"/api/products/barcode/{p.barcode}/", None, 200, 200),
            ("GET", "/api/purchase-list/", None, 200, 200),
            ("GET", "/api/categories/", None, 200, 200),
            ("POST", "/api/categories/", {"name": "Yangi"}, 201, 201),
            ("GET", "/api/sales/", None, 200, 200),
            ("POST", "/api/sales/", sale, 201, 201),
            ("GET", "/api/customers/", None, 200, 200),
            ("POST", "/api/customers/", {"full_name": "Yangi mijoz"}, 201, 201),
            ("GET", f"/api/customers/{c.id}/", None, 200, 200),
            ("POST", f"/api/customers/{c.id}/debt/", {"amount": 100}, 200, 200),
            ("POST", f"/api/customers/{c.id}/payment/", {"amount": 50}, 200, 200),
            ("GET", "/api/dashboard/", None, 200, 200),
            # ---- owner only
            (
                "POST",
                "/api/products/",
                {"name": "Yangi", "unit": "kg", "markup_amount": "2000", "min_stock": "1"},
                201,
                403,
            ),
            ("PATCH", f"/api/products/{p.id}/", {"name": "Un 2"}, 200, 403),
            (
                "POST",
                "/api/batches/",
                {"product": str(p.id), "qty_initial": "5", "cost_price": 1000},
                201,
                403,
            ),
            (
                "POST",
                f"/api/batches/{b.id}/writeoff/",
                {"qty": "1", "reason": "lost"},
                201,
                403,
            ),
            ("GET", f"/api/products/{p.id}/batches/", None, 200, 403),
            ("PATCH", f"/api/batches/{b.id}/", {"expires_at": "2030-01-01"}, 200, 403),
            ("DELETE", f"/api/products/{spare.id}/", None, 204, 403),
            ("GET", "/api/reports/", None, 200, 403),
            ("GET", "/api/reports/export/", None, 200, 403),
            ("GET", "/api/reports/low-stock/export/", None, 200, 403),
            ("GET", "/api/reports/unsold/export/", None, 200, 403),
            ("GET", "/api/settings/", None, 200, 403),
            ("PATCH", "/api/settings/", {"expiry_warn_days": 5}, 200, 403),
            # last: archiving takes the product out of every other case
            ("POST", f"/api/products/{p.id}/archive/", None, 200, 403),
        ]

    def run_matrix(self, user, column):
        client = self.client_for(user)
        for method, url, payload, *expected in self.matrix():
            with self.subTest(f"{method} {url}"):
                response = client.generic(
                    method,
                    url,
                    data=None if payload is None else __import__("json").dumps(payload),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, expected[column], response.content[:200])

    def test_owner_gets_the_owner_column(self):
        self.run_matrix(self.owner, 0)

    def test_seller_gets_the_seller_column(self):
        self.run_matrix(self.seller, 1)

    def test_anonymous_is_rejected_everywhere_with_401(self):
        client = self.client_for(None)
        for method, url, payload, *_ in self.matrix():
            with self.subTest(f"{method} {url}"):
                response = client.generic(
                    method,
                    url,
                    data=None if payload is None else __import__("json").dumps(payload),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 401)

    def test_seller_is_told_why_on_owner_only_endpoints(self):
        response = self.client_for(self.seller).get("/api/reports/")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["message"], "Bu amal faqat do'kon egasi uchun.")

    def test_a_deactivated_user_cannot_use_the_api(self):
        User.objects.filter(pk=self.seller.pk).update(is_active=False)
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken.for_user(self.seller)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(client.get("/api/products/").status_code, 401)

    def test_role_is_read_from_the_database_on_every_request(self):
        # Demoting an owner takes effect immediately, not when their token expires.
        from rest_framework_simplejwt.tokens import AccessToken

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(self.owner)}")
        self.assertEqual(client.get("/api/reports/").status_code, 200)

        User.objects.filter(pk=self.owner.pk).update(role=User.Role.SELLER)

        self.assertEqual(client.get("/api/reports/").status_code, 403)


class HiddenCostDataTests(RoleFixtureMixin, TestCase):
    """Cost data is owner-only: unit_cost (already) and markup_amount (it is the
    cost in disguise: sale price = cost * (1 + markup))."""

    def test_markup_is_visible_to_owner_and_hidden_from_seller(self):
        url = f"/api/products/{self.product.id}/"

        owner_view = self.client_for(self.owner).get(url).json()["data"]
        seller_view = self.client_for(self.seller).get(url).json()["data"]

        self.assertIn("markup_amount", owner_view)
        self.assertNotIn("markup_amount", seller_view)

    def test_markup_is_hidden_from_seller_in_lists_too(self):
        # The purchase list only holds low-stock products, so make this one low.
        Batch.objects.filter(pk=self.batch.pk).update(qty_remaining=Decimal("1"))
        for url in ("/api/products/", "/api/products/?quick=true", "/api/purchase-list/"):
            with self.subTest(url):
                body = self.client_for(self.seller).get(url).json()["data"]
                rows = body["results"] if isinstance(body, dict) else body
                self.assertTrue(rows)
                self.assertNotIn("markup_amount", rows[0])

    def test_unit_cost_is_hidden_from_seller_on_receipts(self):
        sale = self.sell(self.owner)

        seller_item = (
            self.client_for(self.seller).get(f"/api/sales/{sale.id}/").json()["data"]["items"][0]
        )
        owner_item = (
            self.client_for(self.owner).get(f"/api/sales/{sale.id}/").json()["data"]["items"][0]
        )

        self.assertNotIn("unit_cost", seller_item)
        self.assertIn("unit_cost", owner_item)

    def test_seller_dashboard_has_no_revenue_or_profit(self):
        self.assertNotIn(
            "today", self.client_for(self.seller).get("/api/dashboard/").json()["data"]
        )
        self.assertIn("today", self.client_for(self.owner).get("/api/dashboard/").json()["data"])


class CancelRuleTests(RoleFixtureMixin, TestCase):
    """Owner cancels anything. A seller cancels only their own receipt, only today."""

    def cancel(self, user, sale):
        return self.client_for(user).post(f"/api/sales/{sale.id}/cancel/")

    def test_seller_can_cancel_their_own_receipt_from_today(self):
        sale = self.sell(self.seller)

        response = self.cancel(self.seller, sale)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], Sale.Status.CANCELLED)

    def test_seller_cannot_cancel_a_colleagues_receipt(self):
        sale = self.sell(self.other_seller)

        response = self.cancel(self.seller, sale)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"]["message"],
            "Sotuvchi faqat o'zining bugungi chekini bekor qila oladi.",
        )
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.COMPLETED)

    def test_seller_cannot_cancel_their_own_receipt_from_an_earlier_day(self):
        sale = self.sell(self.seller, when=timezone.now() - timedelta(days=1, hours=1))

        self.assertEqual(self.cancel(self.seller, sale).status_code, 403)

    def test_seller_cannot_cancel_an_owners_receipt(self):
        self.assertEqual(self.cancel(self.seller, self.sell(self.owner)).status_code, 403)

    def test_owner_can_cancel_any_receipt_even_an_old_one(self):
        sale = self.sell(self.seller, when=timezone.now() - timedelta(days=40))

        self.assertEqual(self.cancel(self.owner, sale).status_code, 200)

    def test_a_refused_cancel_leaves_stock_untouched(self):
        sale = self.sell(self.other_seller, qty="10")
        before = Batch.objects.get(pk=self.batch.pk).qty_remaining

        self.cancel(self.seller, sale)

        self.assertEqual(Batch.objects.get(pk=self.batch.pk).qty_remaining, before)

    def test_can_cancel_flag_tells_the_ui_when_to_show_the_button(self):
        mine = self.sell(self.seller)
        theirs = self.sell(self.other_seller)
        gone = cancel_sale(self.sell(self.seller), self.seller)

        def flag(user, sale):
            return self.client_for(user).get(f"/api/sales/{sale.id}/").json()["data"]["can_cancel"]

        self.assertTrue(flag(self.seller, mine))
        self.assertFalse(flag(self.seller, theirs))
        self.assertFalse(flag(self.seller, gone))  # already cancelled
        self.assertTrue(flag(self.owner, theirs))
