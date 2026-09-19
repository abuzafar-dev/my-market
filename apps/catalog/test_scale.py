"""Guards for what the load test found: list screens must not run a query per
row, pages can be enlarged on request, and the quick-buttons ranking is cheap."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Batch, Category, Product
from apps.catalog.services import quick_products
from apps.sales.models import Sale
from apps.sales.services import CartLine, create_sale
from apps.shops.models import Shop, ShopSettings, User


class CatalogScaleTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        ShopSettings.objects.create(shop=self.shop)
        self.owner = User.objects.create_user(
            phone="+998901112233", password="pass1234", shop=self.shop, full_name="Egasi"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.category = Category.objects.create(shop=self.shop, name="Ichimlik")

    def make_products(self, count, prefix="Mahsulot"):
        products = []
        for i in range(count):
            product = Product.objects.create(
                shop=self.shop,
                category=self.category,
                name=f"{prefix} {i:03d}",
                unit=Product.Unit.PIECE,
                markup_pct=Decimal("20"),
                min_stock=Decimal("5"),
            )
            Batch.objects.create(
                shop=self.shop,
                product=product,
                qty_initial=Decimal("50"),
                qty_remaining=Decimal("50"),
                cost_price=1000,
                sale_price=1200,
            )
            products.append(product)
        return products

    def sell(self, product, qty="1", when=None):
        sale = create_sale(
            shop=self.shop,
            user=self.owner,
            client_id=uuid4(),
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=[CartLine(product=product, qty=Decimal(qty))],
        )
        if when:
            Sale.objects.filter(pk=sale.pk).update(sold_at=when)
        return sale

    def test_product_list_query_count_does_not_grow_with_the_page(self):
        self.make_products(5)
        with self.assertNumQueries(2):  # the page + the count
            self.client.get("/api/products/", {"page_size": 5})

        self.make_products(30, prefix="Boshqa")
        with self.assertNumQueries(2):  # still 2 for 35 products
            response = self.client.get("/api/products/", {"page_size": 35})
        self.assertEqual(len(response.json()["data"]["results"]), 35)

    def test_price_and_category_come_with_the_list(self):
        self.make_products(1)

        row = self.client.get("/api/products/").json()["data"]["results"][0]

        self.assertEqual(row["price"], 1200)
        self.assertEqual(row["category_name"], "Ichimlik")

    def test_page_size_is_honoured_and_capped(self):
        self.make_products(30)

        small = self.client.get("/api/products/", {"page_size": 10}).json()["data"]
        self.assertEqual((len(small["results"]), small["count"]), (10, 30))
        self.assertIsNotNone(small["next"])

        huge = self.client.get("/api/products/", {"page_size": 100000}).json()["data"]
        self.assertEqual(len(huge["results"]), 30)  # capped at 100, only 30 exist

    def test_quick_products_rank_recent_sales_then_pad_alphabetically(self):
        a, b, c = self.make_products(3, prefix="P")
        self.sell(b, "3")
        self.sell(a, "1")

        names = [p.name for p in quick_products(self.shop, limit=3)]

        self.assertEqual(names, ["P 001", "P 000", "P 002"])  # b (3), a (1), c padded in

    def test_quick_products_ignore_old_sales_and_archived_products(self):
        a, b, c = self.make_products(3, prefix="P")
        self.sell(c, "9", when=timezone.now() - timedelta(days=400))  # too old to count
        self.sell(b, "2")
        Product.objects.filter(pk=a.pk).update(is_active=False)

        names = [p.name for p in quick_products(self.shop, limit=5)]

        self.assertEqual(names, ["P 001", "P 002"])
        self.assertNotIn("P 000", names)

    def test_quick_products_carry_stock_and_price(self):
        (product,) = self.make_products(1)
        self.sell(product, "4")

        (top,) = quick_products(self.shop)

        self.assertEqual(top.stock, Decimal("46"))
        self.assertEqual(top.fifo_price, 1200)

    def test_purchase_list_is_not_n_plus_one(self):
        for product in self.make_products(12):
            Batch.objects.filter(product=product).update(qty_remaining=Decimal("2"))  # low

        with self.assertNumQueries(1):
            response = self.client.get("/api/purchase-list/")

        self.assertEqual(len(response.json()["data"]), 12)
