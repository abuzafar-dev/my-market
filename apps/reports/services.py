"""Dashboard and reporting aggregates (TZ v2 3.8, 7.5)."""

from datetime import date, timedelta

from django.db.models import Count, F, Q, QuerySet, Sum
from django.db.models.functions import Coalesce, TruncDate, TruncHour
from django.utils import timezone

from apps.catalog.models import Product, WriteOff
from apps.catalog.services import expiring_batches, low_stock_products, with_stock
from apps.debt.models import Customer, DebtEntry
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


def period_bounds(period: str) -> tuple[date, date]:
    """First and last day (inclusive) a period covers, up to today."""
    return _period_range(period, date.today())


def completed_sales(shop: Shop, start: date, end: date) -> QuerySet[Sale]:
    return Sale.objects.filter(
        shop=shop,
        status=Sale.Status.COMPLETED,
        sold_at__date__gte=start,
        sold_at__date__lte=end,
    )


def _money_aggregates() -> dict:
    return {
        "count": Count("id"),
        "revenue": Coalesce(Sum("total"), 0),
        "cash": Coalesce(Sum("total", filter=Q(payment_type=Sale.PaymentType.CASH)), 0),
        "card": Coalesce(Sum("total", filter=Q(payment_type=Sale.PaymentType.CARD)), 0),
        "debt": Coalesce(Sum("total", filter=Q(payment_type=Sale.PaymentType.DEBT)), 0),
        "profit": Coalesce(Sum(F("total") - F("cost_total")), 0),
    }


_ZERO_ROW = {"count": 0, "revenue": 0, "cash": 0, "card": 0, "debt": 0, "profit": 0}


def sales_series(shop: Shop, period: str) -> dict:
    """How much was sold in each slice of the period.

    week / month -> one row per calendar day from the start of the period up to
    today (days with no sales are included as zeros, so the list is complete).
    day          -> one row per hour that had sales."""
    start, end = period_bounds(period)
    sales = completed_sales(shop, start, end)

    if period == "day":
        rows = (
            sales.annotate(slot=TruncHour("sold_at"))
            .values("slot")
            .annotate(**_money_aggregates())
            .order_by("slot")
        )
        return {
            "kind": "hour",
            "rows": [
                {"key": f"{timezone.localtime(row['slot']).hour:02d}:00"}
                | {k: row[k] for k in _ZERO_ROW}
                for row in rows
            ],
        }

    by_day = {
        row["day"]: row
        for row in sales.annotate(day=TruncDate("sold_at"))
        .values("day")
        .annotate(**_money_aggregates())
    }
    rows = []
    day = start
    while day <= end:
        found = by_day.get(day)
        rows.append({"key": day.isoformat()} | {k: (found or _ZERO_ROW)[k] for k in _ZERO_ROW})
        day += timedelta(days=1)
    return {"kind": "day", "rows": rows}


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
        .values("product__name", "product__unit")
        .annotate(qty_sold=Sum("qty"), revenue=Sum("line_total"))
        .order_by("-qty_sold")[:limit]
    )


def unsold_products(shop: Shop) -> QuerySet[Product]:
    """Active products that have never appeared in a completed sale.

    Cancelled sales don't count: the goods went back on the shelf, so the
    product still hasn't actually sold."""
    return (
        with_stock(Product.objects.filter(shop=shop, is_active=True))
        .exclude(sale_items__sale__status=Sale.Status.COMPLETED)
        .order_by("name")
    )


def write_off_total(shop: Shop, period: str) -> int:
    today = date.today()
    start, end = _period_range(period, today)
    return WriteOff.objects.filter(
        shop=shop, created_at__date__gte=start, created_at__date__lte=end
    ).aggregate(total=Coalesce(Sum("cost_total"), 0))["total"]


def debt_summary(shop: Shop, period: str) -> dict:
    """Credit ("nasiya") picture for a period: how much was sold on credit, how
    much of the debt was paid back meanwhile, what customers owe right now, and
    how many customers owe. ``outstanding`` / ``debtors`` are "as of today" — a
    debt does not disappear when the period ends. (Who owes how much lives on
    the Qarz screen, not in the report.)"""
    start, end = period_bounds(period)

    sold = (
        completed_sales(shop, start, end)
        .filter(payment_type=Sale.PaymentType.DEBT)
        .aggregate(
            amount=Coalesce(Sum("total"), 0),
            count=Count("id"),
            customers=Count("customer", distinct=True),
        )
    )
    # Payments are stored as negative ledger amounts.
    paid = DebtEntry.objects.filter(
        shop=shop,
        entry_type=DebtEntry.EntryType.PAYMENT,
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).aggregate(total=Coalesce(Sum("amount"), 0))["total"]

    owing = Customer.objects.filter(shop=shop, is_active=True, debt_balance__gt=0)
    outstanding = owing.aggregate(total=Coalesce(Sum("debt_balance"), 0), debtors=Count("id"))

    return {
        "sold": sold["amount"],
        "sold_count": sold["count"],
        "sold_customers": sold["customers"],
        "paid": -paid,
        "outstanding": outstanding["total"],
        "debtors": outstanding["debtors"],
    }


def dashboard(shop: Shop) -> dict:
    warn_days = shop.get_settings().expiry_warn_days
    return {
        "today": sales_stats(shop, "day"),
        "total_debt": Customer.objects.filter(shop=shop, is_active=True).aggregate(
            total=Coalesce(Sum("debt_balance"), 0)
        )["total"],
        "expiring_count": expiring_batches(shop, warn_days).count(),
        "low_stock_count": low_stock_products(shop).count(),
    }
