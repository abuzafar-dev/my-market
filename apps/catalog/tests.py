from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.catalog.models import Batch, Category, Product, WriteOff
from apps.catalog.services import (
    InsufficientBatchStock,
    requires_whole_number,
    with_stock,
    write_off_batch,
)
from apps.shops.models import Shop, User


class CatalogTestCase(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        self.user = User.objects.create_user(
            phone="+998901112233", password="pass1234", shop=self.shop, full_name="Egasi"
        )
        self.category = Category.objects.create(shop=self.shop, name="Ichimliklar")
        self.product = Product.objects.create(
            shop=self.shop,
            category=self.category,
            name="Suv",
            unit=Product.Unit.LITER,
            markup_amount=2000,
            min_stock=Decimal("5"),
        )

    def make_batch(self, qty=Decimal("10"), cost_price=1000, sale_price=1200, **kwargs):
        return Batch.objects.create(
            shop=self.shop,
            product=self.product,
            qty_initial=qty,
            qty_remaining=qty,
            cost_price=cost_price,
            sale_price=sale_price,
            created_by=self.user,
            **kwargs,
        )


class RequiresWholeNumberTests(TestCase):
    def test_piece_unit_rejects_fraction(self):
        self.assertTrue(requires_whole_number(Product.Unit.PIECE, Decimal("1.5")))

    def test_piece_unit_accepts_whole(self):
        self.assertFalse(requires_whole_number(Product.Unit.PIECE, Decimal("2")))

    def test_kg_unit_accepts_fraction(self):
        self.assertFalse(requires_whole_number(Product.Unit.KG, Decimal("1.5")))


class BatchConstraintTests(CatalogTestCase):
    def test_qty_remaining_cannot_go_negative(self):
        batch = self.make_batch()
        batch.qty_remaining = Decimal("-1")
        with self.assertRaises(IntegrityError), transaction.atomic():
            batch.save(update_fields=["qty_remaining"])

    def test_qty_initial_must_be_positive(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Batch.objects.create(
                shop=self.shop,
                product=self.product,
                qty_initial=Decimal("0"),
                qty_remaining=Decimal("0"),
                cost_price=1000,
                sale_price=1200,
            )

    def test_cost_price_cannot_be_negative(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Batch.objects.create(
                shop=self.shop,
                product=self.product,
                qty_initial=Decimal("1"),
                qty_remaining=Decimal("1"),
                cost_price=-100,
                sale_price=1200,
            )


class WithStockTests(CatalogTestCase):
    def test_stock_is_summed_live_from_batches(self):
        self.make_batch(qty=Decimal("4"))
        self.make_batch(qty=Decimal("6"))
        product = with_stock(Product.objects.filter(pk=self.product.pk)).get()
        self.assertEqual(product.stock, Decimal("10"))

    def test_stock_zero_with_no_batches(self):
        product = with_stock(Product.objects.filter(pk=self.product.pk)).get()
        self.assertEqual(product.stock, Decimal("0"))


class WriteOffBatchTests(CatalogTestCase):
    def test_write_off_reduces_batch_qty_remaining(self):
        batch = self.make_batch(qty=Decimal("10"))
        write_off_batch(
            shop=self.shop,
            batch_id=batch.pk,
            user=self.user,
            qty=Decimal("3"),
            reason=WriteOff.Reason.DAMAGED,
        )
        batch.refresh_from_db()
        self.assertEqual(batch.qty_remaining, Decimal("7"))

    def test_write_off_creates_record_with_correct_cost_total(self):
        batch = self.make_batch(qty=Decimal("10"), cost_price=1000)
        write_off = write_off_batch(
            shop=self.shop,
            batch_id=batch.pk,
            user=self.user,
            qty=Decimal("3"),
            reason=WriteOff.Reason.EXPIRED,
        )
        self.assertEqual(write_off.cost_total, 3000)

    def test_write_off_more_than_available_raises(self):
        batch = self.make_batch(qty=Decimal("2"))
        with self.assertRaises(InsufficientBatchStock):
            write_off_batch(
                shop=self.shop,
                batch_id=batch.pk,
                user=self.user,
                qty=Decimal("5"),
                reason=WriteOff.Reason.LOST,
            )
        batch.refresh_from_db()
        self.assertEqual(batch.qty_remaining, Decimal("2"))


class BarcodeSerializerTests(CatalogTestCase):
    def _serializer(self):
        from apps.catalog.serializers import ProductSerializer

        request = type("Req", (), {"user": self.user})()
        return ProductSerializer(context={"request": request})

    def test_whitespace_only_barcode_normalizes_to_none(self):
        self.assertIsNone(self._serializer().validate_barcode("   "))

    def test_blank_barcode_normalizes_to_none(self):
        self.assertIsNone(self._serializer().validate_barcode(""))

    def test_barcode_with_surrounding_whitespace_is_trimmed(self):
        self.assertEqual(self._serializer().validate_barcode("  123456  "), "123456")


class QuickProductsStockTests(CatalogTestCase):
    """Regression: joining sale_items next to batches multiplied `stock`
    (2 batches x 3 sales showed 3x the real stock on the sale screen)."""

    def sell(self, qty):
        return self.sell_product(self.product, qty)

    def sell_product(self, product, qty):
        from uuid import uuid4

        from apps.sales.models import Sale
        from apps.sales.services import CartLine, create_sale

        return create_sale(
            shop=self.shop,
            user=self.user,
            client_id=uuid4(),
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=[CartLine(product=product, qty=Decimal(qty))],
        )

    def stock_on_quick_tile(self):
        from apps.catalog.services import quick_products

        return next(p for p in quick_products(self.shop) if p.pk == self.product.pk).stock

    def test_stock_is_not_multiplied_by_the_number_of_sales(self):
        self.make_batch(qty=Decimal("10"))
        self.make_batch(qty=Decimal("10"))
        for _ in range(3):
            self.sell("1")

        self.assertEqual(self.stock_on_quick_tile(), Decimal("17"))

    def test_quick_tile_stock_matches_the_regular_product_list(self):
        self.make_batch(qty=Decimal("10"))
        self.make_batch(qty=Decimal("4"))
        self.sell("2")
        self.sell("3")

        regular = with_stock(Product.objects.filter(pk=self.product.pk)).get().stock

        self.assertEqual(self.stock_on_quick_tile(), regular)

    def test_best_sellers_come_first_and_cancelled_sales_do_not_count(self):
        from apps.catalog.services import quick_products
        from apps.sales.services import cancel_sale

        other = Product.objects.create(
            shop=self.shop,
            name="Aaa",
            unit="piece",
            markup_amount=1000,
            min_stock=Decimal("1"),
        )
        self.make_batch(qty=Decimal("50"))
        self.sell("5")
        cancel_sale(self.sell("40"), self.user)  # must not make it a best seller

        names = [p.name for p in quick_products(self.shop)]

        self.assertEqual(names, ["Suv", "Aaa"])
        self.assertEqual(other.name, "Aaa")

    def test_only_barcodeless_products_and_ranked_by_number_of_sales(self):
        from apps.catalog.services import quick_products

        scanned = Product.objects.create(
            shop=self.shop,
            name="Coca-Cola",
            barcode="4780000000001",
            unit="piece",
            markup_amount=1000,
            min_stock=Decimal("1"),
        )
        rare = Product.objects.create(
            shop=self.shop, name="Aaa", unit="piece", markup_amount=1000, min_stock=Decimal("1")
        )
        for product in (scanned, rare):
            Batch.objects.create(
                shop=self.shop,
                product=product,
                qty_initial=Decimal("50"),
                qty_remaining=Decimal("50"),
                cost_price=1000,
                sale_price=2000,
            )
        self.make_batch(qty=Decimal("50"))
        self.sell("1")
        self.sell("1")  # Suv: two sales of 1
        self.sell_product(rare, "20")  # Aaa: one big sale — more qty, fewer uses
        self.sell_product(scanned, "1")

        names = [p.name for p in quick_products(self.shop)]

        self.assertEqual(names, ["Suv", "Aaa"])


class ProductImageUploadTests(CatalogTestCase):
    """Photo upload goes over multipart/form-data. The frontend now sends a
    small JPEG made in the browser, so HEIC/oversized camera files never reach
    the server — but the API contract is pinned here."""

    def setUp(self):
        super().setUp()
        import shutil
        import tempfile

        from django.test import override_settings
        from rest_framework.test import APIClient

        self.media = tempfile.mkdtemp()  # never write test photos into the real media/
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def jpeg(self, name="photo.jpg", size=(64, 48)):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", size, (200, 80, 60)).save(buffer, "JPEG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")

    def form(self, **extra):
        return {"name": "Rasmli", "unit": "kg", "markup_amount": "2000", "min_stock": "1", **extra}

    def test_product_can_be_created_with_a_photo(self):
        response = self.client.post(
            "/api/products/", self.form(image=self.jpeg()), format="multipart"
        )

        self.assertEqual(response.status_code, 201)
        image_url = response.json()["data"]["image"]
        self.assertTrue(image_url.endswith(".jpg"))
        self.assertTrue(
            Product.objects.get(name="Rasmli").image.storage.exists(
                Product.objects.get(name="Rasmli").image.name
            )
        )

    def test_photo_can_be_replaced_on_an_existing_product(self):
        response = self.client.patch(
            f"/api/products/{self.product.id}/", {"image": self.jpeg("new.jpg")}, format="multipart"
        )

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertTrue(self.product.image.name.startswith("products/new"))

    def test_product_without_a_photo_still_works_as_plain_json(self):
        response = self.client.post("/api/products/", self.form(), format="json")

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["data"]["image"])

    def test_file_that_is_not_a_readable_image_is_a_clear_400(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        heic_like = SimpleUploadedFile(
            "IMG_1.heic", b"\x00\x00\x00\x18ftypheic" + b"x" * 500, "image/heic"
        )

        response = self.client.post(
            "/api/products/", self.form(image=heic_like), format="multipart"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.json()["error"]["fields"])
        self.assertFalse(Product.objects.filter(name="Rasmli").exists())


class ProductListFilterTests(CatalogTestCase):
    """The products page's category / ordering / barcode-search parameters."""

    def setUp(self):
        super().setUp()
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.make_batch(qty=Decimal("10"), sale_price=3000)  # Suv
        self.bread = Product.objects.create(
            shop=self.shop,
            name="Non",
            unit=Product.Unit.PIECE,
            barcode="4780001",
            markup_amount=0,
            min_stock=Decimal("1"),
        )
        Batch.objects.create(
            shop=self.shop,
            product=self.bread,
            qty_initial=Decimal("2"),
            qty_remaining=Decimal("2"),
            cost_price=1000,
            sale_price=5000,
            created_by=self.user,
        )

    def names(self, **params):
        response = self.client.get("/api/products/", params)
        self.assertEqual(response.status_code, 200)
        return [product["name"] for product in response.json()["data"]["results"]]

    def test_search_matches_barcode(self):
        self.assertEqual(self.names(q="4780001"), ["Non"])

    def test_category_filter(self):
        self.assertEqual(self.names(category=str(self.category.id)), ["Suv"])
        self.assertEqual(self.names(category="none"), ["Non"])
        self.assertEqual(self.names(category="not-a-uuid"), [])

    def test_ordering(self):
        self.assertEqual(self.names(ordering="stock"), ["Non", "Suv"])
        self.assertEqual(self.names(ordering="-stock"), ["Suv", "Non"])
        self.assertEqual(self.names(ordering="-price"), ["Non", "Suv"])
        self.assertEqual(self.names(ordering="price"), ["Suv", "Non"])
        self.assertEqual(self.names(ordering="drop table"), ["Non", "Suv"])  # falls back to name


class CategoryAndBatchValidationTests(CatalogTestCase):
    def setUp(self):
        super().setUp()
        from rest_framework.test import APIClient

        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_a_duplicate_category_is_a_validation_error_not_a_500(self):
        response = self.api.post("/api/categories/", {"name": "  ichimliklar "}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Category.objects.filter(shop=self.shop).count(), 1)

    def test_a_batch_cannot_be_received_in_the_future(self):
        from datetime import timedelta

        from django.utils import timezone

        response = self.api.post(
            "/api/batches/",
            {
                "product": str(self.product.id),
                "qty_initial": "5",
                "cost_price": 1000,
                "received_at": (timezone.now() + timedelta(days=3)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("received_at", response.json()["error"]["fields"])

    def test_products_can_be_reread_by_ids_leaving_out_archived_ones(self):
        archived = Product.objects.create(
            shop=self.shop, name="Eski", min_stock=Decimal("1"), is_active=False
        )
        self.make_batch()

        response = self.api.get(
            "/api/products/", {"ids": f"{self.product.id},{archived.id}", "page_size": 100}
        )

        results = response.json()["data"]["results"]
        self.assertEqual([p["id"] for p in results], [str(self.product.id)])
        self.assertEqual(results[0]["stock"], "10.000")
        self.assertEqual(self.api.get("/api/products/", {"ids": "junk"}).status_code, 200)
