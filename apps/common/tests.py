"""Role-based access control tests (P1): owner-only endpoints must 403 a
seller, and cost-price data must not leak into a seller's view of a sale."""
from decimal import Decimal

from rest_framework.test import APITestCase

from apps.catalog.models import Batch, Product
from apps.sales.models import Sale
from apps.sales.services import CartLine, create_sale
from apps.shops.models import Shop, ShopSettings, User


class RoleTestCase(APITestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        ShopSettings.objects.create(shop=self.shop)
        self.owner = User.objects.create_user(
            phone="+998901112233",
            password="pass1234",
            shop=self.shop,
            full_name="Egasi",
            role=User.Role.OWNER,
        )
        self.seller = User.objects.create_user(
            phone="+998904445566",
            password="pass1234",
            shop=self.shop,
            full_name="Sotuvchi",
            role=User.Role.SELLER,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name="Non",
            unit=Product.Unit.PIECE,
            markup_pct=Decimal("10"),
            min_stock=Decimal("5"),
        )


class OwnerOnlyEndpointTests(RoleTestCase):
    def assert_owner_ok_seller_forbidden(self, method, url, data=None, expected_owner_status=200):
        self.client.force_authenticate(self.seller)
        response = getattr(self.client, method)(url, data, format="json")
        self.assertEqual(response.status_code, 403, response.data)

        self.client.force_authenticate(self.owner)
        response = getattr(self.client, method)(url, data, format="json")
        self.assertEqual(response.status_code, expected_owner_status, response.data)

    def test_settings_view(self):
        self.assert_owner_ok_seller_forbidden("get", "/api/settings/")

    def test_dashboard_view_open_to_both_but_hides_profit_from_seller(self):
        self.client.force_authenticate(self.seller)
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("today", response.data)
        self.assertIn("total_debt", response.data)

        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("today", response.data)

    def test_reports_view(self):
        self.assert_owner_ok_seller_forbidden("get", "/api/reports/")

    def test_reports_export_view(self):
        self.client.force_authenticate(self.seller)
        response = self.client.get("/api/reports/export/")
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.owner)
        response = self.client.get("/api/reports/export/")
        self.assertEqual(response.status_code, 200)

    def test_product_create(self):
        payload = {
            "name": "Sut",
            "unit": Product.Unit.PIECE,
            "markup_pct": "15",
            "min_stock": "3",
        }
        self.assert_owner_ok_seller_forbidden(
            "post", "/api/products/", payload, expected_owner_status=201
        )

    def test_product_patch(self):
        url = f"/api/products/{self.product.id}/"
        self.assert_owner_ok_seller_forbidden("patch", url, {"markup_pct": "20"})

    def test_product_archive(self):
        url = f"/api/products/{self.product.id}/archive/"
        self.assert_owner_ok_seller_forbidden("post", url, {})

    def test_batch_create(self):
        payload = {
            "product": str(self.product.id),
            "qty_initial": "10",
            "cost_price": 1000,
            "sale_price": 1500,
        }
        self.assert_owner_ok_seller_forbidden(
            "post", "/api/batches/", payload, expected_owner_status=201
        )

    def test_product_list_is_open_to_sellers(self):
        # Sanity check: the matrix keeps browsing open to both roles.
        self.client.force_authenticate(self.seller)
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, 200)


class SaleUnitCostVisibilityTests(RoleTestCase):
    def setUp(self):
        super().setUp()
        Batch.objects.create(
            shop=self.shop,
            product=self.product,
            qty_initial=Decimal("10"),
            qty_remaining=Decimal("10"),
            cost_price=1000,
            sale_price=1500,
        )
        self.sale = create_sale(
            shop=self.shop,
            user=self.seller,
            client_id="11111111-1111-1111-1111-111111111111",
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=[CartLine(product=self.product, qty=Decimal("2"))],
        )

    def test_seller_does_not_see_unit_cost(self):
        self.client.force_authenticate(self.seller)
        response = self.client.get(f"/api/sales/{self.sale.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("unit_cost", response.data["items"][0])

    def test_owner_sees_unit_cost(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(f"/api/sales/{self.sale.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("unit_cost", response.data["items"][0])
