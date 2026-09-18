import uuid
from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Batch, Product
from apps.debt.models import Customer
from apps.sales.models import Sale
from apps.sales.services import CartLine, InsufficientStock, cancel_sale, create_sale
from apps.shops.models import Shop, User


class SalesTestCase(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        self.user = User.objects.create_user(
            phone="+998901112233", password="pass1234", shop=self.shop, full_name="Sotuvchi"
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name="Non",
            unit=Product.Unit.PIECE,
            markup_pct=Decimal("10"),
            min_stock=Decimal("5"),
        )

    def make_batch(self, qty, cost_price, sale_price, received_at=None):
        kwargs = {"received_at": received_at} if received_at else {}
        return Batch.objects.create(
            shop=self.shop,
            product=self.product,
            qty_initial=qty,
            qty_remaining=qty,
            cost_price=cost_price,
            sale_price=sale_price,
            **kwargs,
        )


class CreateSaleFifoTests(SalesTestCase):
    def test_consumes_oldest_batch_first(self):
        from django.utils import timezone

        old_batch = self.make_batch(
            Decimal("5"), 1000, 1500, received_at=timezone.now() - timezone.timedelta(days=2)
        )
        self.make_batch(Decimal("5"), 1100, 1600)

        sale = create_sale(
            shop=self.shop,
            user=self.user,
            client_id=uuid.uuid4(),
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=[CartLine(product=self.product, qty=Decimal("3"))],
        )

        old_batch.refresh_from_db()
        self.assertEqual(old_batch.qty_remaining, Decimal("2"))
        self.assertEqual(sale.total, 3 * 1500)

    def test_splits_across_batches_when_one_is_insufficient(self):
        from django.utils import timezone

        old_batch = self.make_batch(
            Decimal("2"), 1000, 1500, received_at=timezone.now() - timezone.timedelta(days=2)
        )
        new_batch = self.make_batch(Decimal("5"), 1100, 1600)

        sale = create_sale(
            shop=self.shop,
            user=self.user,
            client_id=uuid.uuid4(),
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=[CartLine(product=self.product, qty=Decimal("4"))],
        )

        old_batch.refresh_from_db()
        new_batch.refresh_from_db()
        self.assertEqual(old_batch.qty_remaining, Decimal("0"))
        self.assertEqual(new_batch.qty_remaining, Decimal("3"))
        self.assertEqual(sale.total, 2 * 1500 + 2 * 1600)

    def test_insufficient_stock_raises_and_nothing_is_consumed(self):
        batch = self.make_batch(Decimal("2"), 1000, 1500)

        with self.assertRaises(InsufficientStock):
            create_sale(
                shop=self.shop,
                user=self.user,
                client_id=uuid.uuid4(),
                payment_type=Sale.PaymentType.CASH,
                customer=None,
                cart=[CartLine(product=self.product, qty=Decimal("10"))],
            )

        batch.refresh_from_db()
        self.assertEqual(batch.qty_remaining, Decimal("2"))
        self.assertEqual(Sale.objects.count(), 0)

    def test_repeated_client_id_is_idempotent(self):
        self.make_batch(Decimal("5"), 1000, 1500)
        client_id = uuid.uuid4()
        cart = [CartLine(product=self.product, qty=Decimal("1"))]

        first = create_sale(
            shop=self.shop,
            user=self.user,
            client_id=client_id,
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=cart,
        )
        second = create_sale(
            shop=self.shop,
            user=self.user,
            client_id=client_id,
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=cart,
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Sale.objects.count(), 1)

    def test_debt_sale_creates_debt_entry_and_updates_balance(self):
        self.make_batch(Decimal("5"), 1000, 1500)
        customer = Customer.objects.create(shop=self.shop, full_name="Mijoz")

        create_sale(
            shop=self.shop,
            user=self.user,
            client_id=uuid.uuid4(),
            payment_type=Sale.PaymentType.DEBT,
            customer=customer,
            cart=[CartLine(product=self.product, qty=Decimal("2"))],
        )

        customer.refresh_from_db()
        self.assertEqual(customer.debt_balance, 2 * 1500)


class CancelSaleTests(SalesTestCase):
    def test_cancel_restocks_batches(self):
        batch = self.make_batch(Decimal("5"), 1000, 1500)
        sale = create_sale(
            shop=self.shop,
            user=self.user,
            client_id=uuid.uuid4(),
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=[CartLine(product=self.product, qty=Decimal("3"))],
        )

        cancel_sale(sale, self.user)

        batch.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(batch.qty_remaining, Decimal("5"))
        self.assertEqual(sale.status, Sale.Status.CANCELLED)

    def test_cancel_debt_sale_reverses_customer_balance(self):
        self.make_batch(Decimal("5"), 1000, 1500)
        customer = Customer.objects.create(shop=self.shop, full_name="Mijoz")
        sale = create_sale(
            shop=self.shop,
            user=self.user,
            client_id=uuid.uuid4(),
            payment_type=Sale.PaymentType.DEBT,
            customer=customer,
            cart=[CartLine(product=self.product, qty=Decimal("2"))],
        )
        customer.refresh_from_db()
        self.assertEqual(customer.debt_balance, 3000)

        cancel_sale(sale, self.user)

        customer.refresh_from_db()
        self.assertEqual(customer.debt_balance, 0)

    def test_cancelling_twice_is_a_noop(self):
        self.make_batch(Decimal("5"), 1000, 1500)
        sale = create_sale(
            shop=self.shop,
            user=self.user,
            client_id=uuid.uuid4(),
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=[CartLine(product=self.product, qty=Decimal("3"))],
        )
        cancel_sale(sale, self.user)
        cancel_sale(sale, self.user)

        batch = Batch.objects.get(product=self.product)
        self.assertEqual(batch.qty_remaining, Decimal("5"))
