"""FIFO sale processing (TZ v2 3.3, 7.2–7.4)."""
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Batch, Product
from apps.debt.models import Customer, DebtEntry
from apps.shops.models import Shop, User

from .models import Sale, SaleItem


class InsufficientStock(Exception):
    def __init__(self, product: Product, available: Decimal) -> None:
        self.product = product
        self.available = available
        super().__init__(f"Omborda faqat {available} {product.get_unit_display()} qoldi")


@dataclass
class CartLine:
    product: Product
    qty: Decimal


def _consume_fifo(product: Product, qty_needed: Decimal) -> list[SaleItem]:
    """Reduce the oldest batches first, splitting across batches as needed."""
    batches = list(
        Batch.objects.select_for_update()
        .filter(product=product, qty_remaining__gt=0)
        .order_by("received_at")
    )

    available = sum((batch.qty_remaining for batch in batches), Decimal("0"))
    if available < qty_needed:
        raise InsufficientStock(product, available)

    items = []
    remaining = qty_needed
    for batch in batches:
        if remaining <= 0:
            break
        take = min(batch.qty_remaining, remaining)
        batch.qty_remaining -= take
        batch.save(update_fields=["qty_remaining", "updated_at"])
        remaining -= take
        items.append(
            SaleItem(
                product=product,
                batch=batch,
                qty=take,
                unit_price=batch.sale_price,
                unit_cost=batch.cost_price,
                line_total=int(take * batch.sale_price),
            )
        )
    return items


@transaction.atomic
def create_sale(
    *,
    shop: Shop,
    user: User,
    client_id,
    payment_type: str,
    customer: Customer | None,
    cart: list[CartLine],
) -> Sale:
    """Idempotent on client_id — a repeated request returns the original sale
    instead of double-selling (TZ v2 6.5)."""
    existing = Sale.objects.filter(shop=shop, client_id=client_id).first()
    if existing:
        return existing

    items: list[SaleItem] = []
    for line in cart:
        items += _consume_fifo(line.product, line.qty)

    total = sum(item.line_total for item in items)
    cost_total = sum(int(item.unit_cost * item.qty) for item in items)

    sale = Sale.objects.create(
        shop=shop,
        client_id=client_id,
        customer=customer,
        total=total,
        cost_total=cost_total,
        payment_type=payment_type,
        sold_by=user,
        sold_at=timezone.now(),
    )
    for item in items:
        item.sale = sale
    SaleItem.objects.bulk_create(items)

    if payment_type == Sale.PaymentType.DEBT:
        DebtEntry.objects.create(
            shop=shop,
            customer=customer,
            sale=sale,
            amount=total,
            entry_type=DebtEntry.EntryType.DEBT,
            created_by=user,
        )
        Customer.objects.filter(pk=customer.pk).update(debt_balance=F("debt_balance") + total)

    return sale


@transaction.atomic
def cancel_sale(sale: Sale, user: User) -> Sale:
    if sale.status == Sale.Status.CANCELLED:
        return sale

    for item in sale.items.select_related("batch"):
        Batch.objects.filter(pk=item.batch_id).update(qty_remaining=F("qty_remaining") + item.qty)

    if sale.payment_type == Sale.PaymentType.DEBT and sale.customer_id:
        DebtEntry.objects.create(
            shop=sale.shop,
            customer=sale.customer,
            sale=sale,
            amount=-sale.total,
            entry_type=DebtEntry.EntryType.PAYMENT,
            note="Chek bekor qilindi",
            created_by=user,
        )
        Customer.objects.filter(pk=sale.customer_id).update(
            debt_balance=F("debt_balance") - sale.total
        )

    sale.status = Sale.Status.CANCELLED
    sale.cancelled_at = timezone.now()
    sale.save(update_fields=["status", "cancelled_at", "updated_at"])
    return sale
