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
            markup_pct=Decimal("20"),
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
