"""Business logic for products, stock, and batches (TZ v2 sections 3.6, 3.7, 7.1, 7.6, 7.7)."""

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F, OuterRef, QuerySet, Subquery, Sum
from django.db.models.functions import Coalesce
from django.http import Http404
from django.utils import timezone

from apps.shops.models import Shop, User

from .exceptions import BatchQtyTooLow, ProductInUse
from .models import Batch, Product, WriteOff

logger = logging.getLogger(__name__)


def requires_whole_number(unit: str, qty: Decimal) -> bool:
    """TZ v2 3.1: a "dona" (piece) product can't be sold or stocked as a
    fraction — you can't have half a bottle. Only kg/liter allow decimals."""
    return unit == Product.Unit.PIECE and qty % 1 != 0


class InsufficientBatchStock(Exception):
    def __init__(self, available: Decimal) -> None:
        self.available = available
        super().__init__(f"Partiyada faqat {available} qoldi.")


def with_stock(queryset: QuerySet[Product]) -> QuerySet[Product]:
    """Annotate each product with its live stock.

    Stock is summed from batches on every read (TZ v2 7.1) rather than
    stored on Product, so this is the only correct way to get it in bulk.
    """
    return queryset.annotate(stock=Coalesce(Sum("batches__qty_remaining"), Decimal("0")))


def low_stock_products(shop: Shop) -> QuerySet[Product]:
    """Products at or below their minimum stock (TZ v2 3.7 / 7.7)."""
    return (
        with_stock(Product.objects.filter(shop=shop, is_active=True))
        .filter(stock__lte=F("min_stock"))
        .order_by("stock")
    )


def expiring_batches(shop: Shop, warn_days: int) -> QuerySet[Batch]:
    """Batches expired or expiring within the shop's warning window (TZ v2 3.6 / 7.6)."""
    warn_date = date.today() + timedelta(days=warn_days)
    return (
        Batch.objects.filter(
            shop=shop, qty_remaining__gt=0, expires_at__isnull=False, expires_at__lte=warn_date
        )
        .select_related("product")
        .order_by("expires_at")
    )


def batch_status(expires_at: date) -> str:
    return "expired" if expires_at < date.today() else "warning"


def with_price(queryset: QuerySet[Product]) -> QuerySet[Product]:
    """Annotate each product with ``fifo_price``: the sale price of its oldest
    batch that still has stock — what a sale would charge right now.

    One correlated subquery instead of a query per product row (the list
    screens show 20+ products at a time)."""
    head_batch = (
        Batch.objects.filter(product=OuterRef("pk"), qty_remaining__gt=0)
        .order_by("received_at")
        .values("sale_price")[:1]
    )
    return queryset.annotate(fifo_price=Subquery(head_batch))


QUICK_WINDOW_DAYS = 90


def quick_products(shop: Shop, limit: int = 15) -> list[Product]:
    """Best sellers of the last 90 days for the quick-buttons panel (TZ v2 3.4),
    padded alphabetically when the shop has fewer than ``limit`` sellers.

    The ranking is its own grouped query over recent sale lines. It used to be
    a correlated subquery evaluated for every product, which scanned all sale
    history per product — over a second on a shop with 8k products. Kept apart
    from ``with_stock`` on purpose: joining ``sale_items`` next to the
    ``batches`` join there multiplies rows and inflates ``stock``.
    """
    from apps.sales.models import SaleItem  # sales depends on catalog, not the reverse

    since = timezone.now() - timedelta(days=QUICK_WINDOW_DAYS)
    ranked_ids = [
        row["product_id"]
        for row in SaleItem.objects.filter(
            sale__shop=shop, sale__status="completed", sale__sold_at__gte=since
        )
        .values("product_id")
        .annotate(total=Sum("qty"))
        .order_by("-total")[: limit * 3]
    ]

    def base() -> QuerySet[Product]:
        return with_price(
            with_stock(Product.objects.filter(shop=shop, is_active=True))
        ).select_related("category")

    by_id = {product.id: product for product in base().filter(id__in=ranked_ids)}
    # Archived products can rank high; they just aren't in ``by_id``.
    products = [by_id[pk] for pk in ranked_ids if pk in by_id][:limit]
    if len(products) < limit:
        taken = [product.id for product in products]
        products += list(base().exclude(id__in=taken).order_by("name")[: limit - len(products)])
    return products


@transaction.atomic
def write_off_batch(
    *, shop: Shop, batch_id, user: User, qty: Decimal, reason: str, note: str = ""
) -> WriteOff:
    try:
        batch = Batch.objects.select_for_update().get(pk=batch_id, shop=shop)
    except Batch.DoesNotExist as exc:
        raise Http404 from exc

    if qty > batch.qty_remaining:
        raise InsufficientBatchStock(batch.qty_remaining)

    batch.qty_remaining = F("qty_remaining") - qty
    batch.save(update_fields=["qty_remaining", "updated_at"])
    batch.refresh_from_db(fields=["qty_remaining"])

    write_off = WriteOff.objects.create(
        shop=shop,
        batch=batch,
        qty=qty,
        cost_total=int(qty * batch.cost_price),
        reason=reason,
        note=note,
        created_by=user,
    )
    logger.info(
        "Write-off of %s from batch %s (%s, cost %s so'm) by user %s",
        qty,
        batch.id,
        reason,
        write_off.cost_total,
        user.id,
    )
    return write_off


@transaction.atomic
def update_batch(*, shop: Shop, batch_id, qty_initial: Decimal | None = None, **fields) -> Batch:
    """Correct a batch that was entered wrong (price, expiry, quantity).

    Changing ``qty_initial`` moves ``qty_remaining`` by the same difference, so
    what was already sold or written off stays accounted for; it cannot go below
    what already left the batch. Past sales keep the cost/price they snapshotted."""
    try:
        batch = (
            Batch.objects.select_for_update().select_related("product").get(pk=batch_id, shop=shop)
        )
    except Batch.DoesNotExist as exc:
        raise Http404 from exc

    if qty_initial is not None:
        left = batch.qty_initial - batch.qty_remaining
        if qty_initial < left:
            raise BatchQtyTooLow(left)
        batch.qty_remaining = qty_initial - left
        batch.qty_initial = qty_initial
        fields["qty_initial"] = qty_initial
        fields["qty_remaining"] = batch.qty_remaining

    for name, value in fields.items():
        setattr(batch, name, value)
    batch.save(update_fields=[*fields, "updated_at"])
    return batch


@transaction.atomic
def delete_product(product: Product) -> None:
    """Erase a product that was entered by mistake, with its stock batches.

    A product that has been sold is refused — its receipts point at it, so it
    can only be archived. Write-offs of its batches go with it."""
    if product.sale_items.exists():
        raise ProductInUse()
    WriteOff.objects.filter(batch__product=product).delete()
    product.batches.all().delete()
    if product.image:
        product.image.delete(save=False)
    product.delete()
