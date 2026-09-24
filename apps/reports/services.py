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
    """First and last day (inclusive) a period covers, up to today.

    "Today" is the shop's local date (settings.TIME_ZONE), never the server
    clock's: the container runs in UTC, and between 00:00 and 05:00 in
    Tashkent ``date.today()`` would still be yesterday — while the
    ``sold_at__date`` lookups below already cut days in local time."""
    return _period_range(period, timezone.localdate())


def previous_period_bounds(period: str, today: date | None = None) -> tuple[date, date]:
    """The same stretch of the previous period, for a fair comparison: today
    vs yesterday, Monday..today vs last Monday..same weekday, 1st..today vs
    last month's 1st..same day (clamped to that month's length)."""
    today = today or timezone.localdate()
    if period == "week":
        start = today - timedelta(days=today.weekday() + 7)
        return start, today - timedelta(days=7)
    if period == "month":
        last_month_end = today.replace(day=1) - timedelta(days=1)
        start = last_month_end.replace(day=1)
        return start, last_month_end.replace(day=min(today.day, last_month_end.day))
    yesterday = today - timedelta(days=1)
    return yesterday, yesterday


def totals_between(shop: Shop, start: date, end: date) -> dict:
    """Sales count, revenue and profit over an arbitrary date range."""
    return completed_sales(shop, start, end).aggregate(
        count=Count("id"),
        revenue=Coalesce(Sum("total"), 0),
        profit=Coalesce(Sum(F("total") - F("cost_total")), 0),
    )


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
    start, end = period_bounds(period)
    stats = completed_sales(shop, start, end).aggregate(**_money_aggregates())
    stats["cash_in_register"] = stats["cash"] + stats["card"]
    return stats


def top_products(shop: Shop, period: str, limit: int = 5) -> list[dict]:
    start, end = period_bounds(period)
    return list(
        SaleItem.objects.filter(sale__in=completed_sales(shop, start, end))
        .values("product_id", "product__name", "product__unit")
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
    start, end = period_bounds(period)
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
    # Payments are stored as negative ledger amounts. A cancelled credit sale
    # also books a PAYMENT entry (linked to that sale) to reverse the debt —
    # no money came in, so it must not count as a repayment.
    paid = DebtEntry.objects.filter(
        shop=shop,
        entry_type=DebtEntry.EntryType.PAYMENT,
        sale__isnull=True,
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
        # Same rule as the debt page and the report: only what customers owe.
        # A customer who overpaid (negative balance) must not shrink the total.
        "total_debt": Customer.objects.filter(
            shop=shop, is_active=True, debt_balance__gt=0
        ).aggregate(total=Coalesce(Sum("debt_balance"), 0))["total"],
        "expiring_count": expiring_batches(shop, warn_days).count(),
        "low_stock_count": low_stock_products(shop).count(),
    }
