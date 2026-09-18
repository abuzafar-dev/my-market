"""Business logic for products, stock, and batches (TZ v2 sections 3.6, 3.7, 7.1, 7.6, 7.7)."""
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q, QuerySet, Sum
from django.db.models.functions import Coalesce
from django.http import Http404

from apps.shops.models import Shop, User

from .models import Batch, Product, WriteOff


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


def quick_products(shop: Shop, limit: int = 15) -> QuerySet[Product]:
    """Best sellers for the quick-buttons panel (TZ v2 3.4)."""
    return (
        with_stock(Product.objects.filter(shop=shop, is_active=True))
        .annotate(
            sold_qty=Coalesce(
                Sum("sale_items__qty", filter=Q(sale_items__sale__status="completed")),
                Decimal("0"),
            )
        )
        .order_by("-sold_qty", "name")[:limit]
    )


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

    return WriteOff.objects.create(
        shop=shop,
        batch=batch,
        qty=qty,
        cost_total=int(qty * batch.cost_price),
        reason=reason,
        note=note,
        created_by=user,
    )
