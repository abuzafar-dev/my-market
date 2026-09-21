"""Fixing mistakes: editing a batch and deleting a product (owner only)."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Batch, Category, Product, WriteOff
from apps.sales.models import Sale
from apps.sales.services import CartLine, create_sale
from apps.shops.models import Shop, ShopSettings, User


class ManageTestCase(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        ShopSettings.objects.create(shop=self.shop)
        self.owner = User.objects.create_user(
            phone="+998901000001",
            password="pass1234",  # pragma: allowlist secret
            shop=self.shop,
            full_name="Egasi",
        )
        self.category = Category.objects.create(shop=self.shop, name="Ichimliklar")
        self.product = Product.objects.create(
            shop=self.shop, name="Suv", unit=Product.Unit.PIECE, min_stock=Decimal("1")
        )
        self.batch = Batch.objects.create(
            shop=self.shop,
            product=self.product,
            qty_initial=Decimal("10"),
            qty_remaining=Decimal("10"),
            cost_price=1000,
            sale_price=1500,
        )
        self.api = APIClient()
        self.api.force_authenticate(self.owner)

    def sell(self, qty):
        return create_sale(
            shop=self.shop,
            user=self.owner,
            client_id=uuid4(),
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=[CartLine(product=self.product, qty=Decimal(qty))],
        )


class EditProductTests(ManageTestCase):
    def test_name_and_category_can_be_corrected(self):
        response = self.api.patch(
            f"/api/products/{self.product.id}/",
            {"name": "Mineral suv", "category": str(self.category.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Mineral suv")
        self.assertEqual(self.product.category, self.category)


class EditBatchTests(ManageTestCase):
    def patch(self, payload, batch=None):
        return self.api.patch(f"/api/batches/{(batch or self.batch).id}/", payload, format="json")

    def test_expiry_and_prices_can_be_corrected(self):
        response = self.patch({"expires_at": "2030-05-01", "cost_price": 1100, "sale_price": 1700})

        self.assertEqual(response.status_code, 200)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.expires_at, date(2030, 5, 1))
        self.assertEqual((self.batch.cost_price, self.batch.sale_price), (1100, 1700))

    def test_expiry_can_be_cleared(self):
        self.batch.expires_at = date(2030, 5, 1)
        self.batch.save()

        self.assertEqual(self.patch({"expires_at": None}).status_code, 200)

        self.batch.refresh_from_db()
        self.assertIsNone(self.batch.expires_at)

    def test_changing_the_quantity_keeps_what_was_already_sold(self):
        self.sell("4")  # 4 left the batch, 6 remain

        response = self.patch({"qty_initial": "20"})

        self.assertEqual(response.status_code, 200)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.qty_initial, Decimal("20"))
        self.assertEqual(self.batch.qty_remaining, Decimal("16"))  # 20 - 4 sold

    def test_quantity_cannot_drop_below_what_already_left(self):
        self.sell("4")

        response = self.patch({"qty_initial": "3"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "batch_qty_too_low")
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.qty_remaining, Decimal("6"))

    def test_piece_products_need_a_whole_quantity(self):
        self.assertEqual(self.patch({"qty_initial": "2.5"}).status_code, 400)

    def test_another_shops_batch_is_not_found(self):
        other = Shop.objects.create(name="Boshqa", phone="+998900000009")
        product = Product.objects.create(shop=other, name="X", min_stock=Decimal("1"))
        foreign = Batch.objects.create(
            shop=other,
            product=product,
            qty_initial=Decimal("1"),
            qty_remaining=Decimal("1"),
            cost_price=1,
            sale_price=2,
        )

        self.assertEqual(self.patch({"cost_price": 5}, batch=foreign).status_code, 404)

    def test_product_batches_are_listed_newest_first(self):
        newer = Batch.objects.create(
            shop=self.shop,
            product=self.product,
            qty_initial=Decimal("5"),
            qty_remaining=Decimal("5"),
            cost_price=1200,
            sale_price=1800,
        )

        response = self.api.get(f"/api/products/{self.product.id}/batches/")

        ids = [row["id"] for row in response.json()["data"]]
        self.assertEqual(ids, [str(newer.id), str(self.batch.id)])


class DeleteProductTests(ManageTestCase):
    def test_an_unsold_product_is_deleted_with_its_batches(self):
        WriteOff.objects.create(
            shop=self.shop, batch=self.batch, qty=Decimal("1"), cost_total=1000, reason="lost"
        )

        response = self.api.delete(f"/api/products/{self.product.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        self.assertFalse(Batch.objects.filter(shop=self.shop).exists())
        self.assertFalse(WriteOff.objects.filter(shop=self.shop).exists())

    def test_a_sold_product_cannot_be_deleted(self):
        self.sell("1")

        response = self.api.delete(f"/api/products/{self.product.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "product_in_use")
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_another_shops_product_is_not_found(self):
        other = Shop.objects.create(name="Boshqa", phone="+998900000009")
        foreign = Product.objects.create(shop=other, name="X", min_stock=Decimal("1"))

        self.assertEqual(self.api.delete(f"/api/products/{foreign.id}/").status_code, 404)
