"""Dashboard and reporting aggregates (TZ v2 3.8, 7.5)."""
from datetime import date, timedelta

from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce

from apps.catalog.models import WriteOff
from apps.catalog.services import expiring_batches, low_stock_products
from apps.debt.models import Customer
from apps.sales.models import Sale, SaleItem
from apps.shops.models import Shop


def _period_range(period: str, today: date) -> tuple[date, date]:
    if period == "week":
        start = today - timedelta(days=today.weekday())
    elif period == "month":
        start = today.replace(day=1)
    else:
        start = today
    return start, today


def sales_stats(shop: Shop, period: str = "day") -> dict:
    today = date.today()
    start, end = _period_range(period, today)

    stats = Sale.objects.filter(
        shop=shop,
        status=Sale.Status.COMPLETED,
        sold_at__date__gte=start,
        sold_at__date__lte=end,
    ).aggregate(
        revenue=Coalesce(Sum("total"), 0),
        cash=Coalesce(Sum("total", filter=Q(payment_type=Sale.PaymentType.CASH)), 0),
        card=Coalesce(Sum("total", filter=Q(payment_type=Sale.PaymentType.CARD)), 0),
        debt=Coalesce(Sum("total", filter=Q(payment_type=Sale.PaymentType.DEBT)), 0),
        profit=Coalesce(Sum(F("total") - F("cost_total")), 0),
    )
    stats["cash_in_register"] = stats["cash"] + stats["card"]
    return stats


def top_products(shop: Shop, period: str, limit: int = 5) -> list[dict]:
    today = date.today()
    start, end = _period_range(period, today)
    return list(
        SaleItem.objects.filter(
            sale__shop=shop,
            sale__status=Sale.Status.COMPLETED,
            sale__sold_at__date__gte=start,
            sale__sold_at__date__lte=end,
        )
        .values("product__name")
        .annotate(qty_sold=Sum("qty"), revenue=Sum("line_total"))
        .order_by("-qty_sold")[:limit]
    )


def write_off_total(shop: Shop, period: str) -> int:
    today = date.today()
    start, end = _period_range(period, today)
    return WriteOff.objects.filter(
        shop=shop, created_at__date__gte=start, created_at__date__lte=end
    ).aggregate(total=Coalesce(Sum("cost_total"), 0))["total"]


def dashboard(shop: Shop) -> dict:
    warn_days = shop.settings.expiry_warn_days
    return {
        "today": sales_stats(shop, "day"),
        "total_debt": Customer.objects.filter(shop=shop, is_active=True).aggregate(
            total=Coalesce(Sum("debt_balance"), 0)
        )["total"],
        "expiring_count": expiring_batches(shop, warn_days).count(),
        "low_stock_count": low_stock_products(shop).count(),
    }
