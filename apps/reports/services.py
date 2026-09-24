"""Dashboard and reporting aggregates (TZ v2 3.8, 7.5)."""

from datetime import date, timedelta

from django.db.models import Count, DecimalField, F, Q, QuerySet, Sum
from django.db.models.functions import Coalesce, TruncDate, TruncHour
from django.utils import timezone

from apps.catalog.models import Product, WriteOff
from apps.catalog.services import expiring_batches, low_stock_products, with_stock
from apps.debt.models import Customer, DebtEntry
from apps.sales.models import Sale, SaleItem
from apps.shops.models import Shop


def _last_day_of_month(day: date) -> date:
    next_month = day.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)


def period_bounds(period: str, anchor: date | None = None) -> tuple[date, date]:
    """First and last day (inclusive) of the day / week / month that contains
    ``anchor`` (default: today), never past today.

    ``anchor`` lets the owner look at any earlier day, week or month; a future
    anchor is pulled back to today. "Today" is the shop's local date
    (settings.TIME_ZONE), never the server clock's: the container runs in UTC,
    and between 00:00 and 05:00 in Tashkent ``date.today()`` would still be
    yesterday — while the ``sold_at__date`` lookups below already cut days in
    local time."""
    today = timezone.localdate()
    anchor = min(anchor or today, today)
    if period == "week":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
    elif period == "month":
        start = anchor.replace(day=1)
        end = _last_day_of_month(anchor)
    else:
        start = end = anchor
    return start, min(end, today)


def previous_period_bounds(period: str, today: date | None = None) -> tuple[date, date]:
    """The same stretch of the previous period, for a fair comparison.

    ``today`` is the last day of the range being compared (default: today):
    a day vs the day before, Monday..that day vs last Monday..same weekday,
    1st..that day vs last month's 1st..same day (clamped to that month's
    length). For a finished past week or month that is the whole previous one."""
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


def sales_series(shop: Shop, start: date, end: date) -> dict:
    """How much was sold in each slice of the range.

    several days -> one row per calendar day (days with no sales are included
    as zeros, so the list is complete).
    a single day -> one row per hour that had sales."""
    sales = completed_sales(shop, start, end)

    if start == end:
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


def sales_stats(shop: Shop, start: date, end: date) -> dict:
    stats = completed_sales(shop, start, end).aggregate(**_money_aggregates())
    stats["cash_in_register"] = stats["cash"] + stats["card"]
    return stats


def sold_products(shop: Shop, start: date, end: date) -> list[dict]:
    """Everything sold in the range, one row per product, best-earning first:
    how much went out, what it brought in, the profit on it and in how many
    receipts it appeared. Profit uses each line's own cost snapshot, so a
    product bought at different prices over the period is still exact."""
    rows = (
        SaleItem.objects.filter(sale__in=completed_sales(shop, start, end))
        .values("product_id", "product__name", "product__unit")
        .annotate(
            qty_sold=Sum("qty"),
            revenue=Sum("line_total"),
            cost=Sum(F("unit_cost") * F("qty"), output_field=DecimalField()),
            receipts=Count("sale_id", distinct=True),
        )
        .order_by("-revenue", "product__name")
    )
    return [
        {
            "product_id": row["product_id"],
            "name": row["product__name"],
            "unit": row["product__unit"],
            "qty": row["qty_sold"],
            "revenue": row["revenue"],
            "profit": row["revenue"] - round(row["cost"]),
            "receipts": row["receipts"],
        }
        for row in rows
    ]


def unsold_products(shop: Shop) -> QuerySet[Product]:
    """Active products that have never appeared in a completed sale.

    Cancelled sales don't count: the goods went back on the shelf, so the
    product still hasn't actually sold."""
    return (
        with_stock(Product.objects.filter(shop=shop, is_active=True))
        .exclude(sale_items__sale__status=Sale.Status.COMPLETED)
        .order_by("name")
    )


def write_off_total(shop: Shop, start: date, end: date) -> int:
    return WriteOff.objects.filter(
        shop=shop, created_at__date__gte=start, created_at__date__lte=end
    ).aggregate(total=Coalesce(Sum("cost_total"), 0))["total"]


def debt_summary(shop: Shop, start: date, end: date) -> dict:
    """Credit ("nasiya") picture for a period: how much was sold on credit, how
    much of the debt was paid back meanwhile, what customers owe right now, and
    how many customers owe. ``outstanding`` / ``debtors`` are "as of today" — a
    debt does not disappear when the period ends. (Who owes how much lives on
    the Qarz screen, not in the report.)"""

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
        "today": sales_stats(shop, *period_bounds("day")),
        # Same rule as the debt page and the report: only what customers owe.
        # A customer who overpaid (negative balance) must not shrink the total.
        "total_debt": Customer.objects.filter(
            shop=shop, is_active=True, debt_balance__gt=0
        ).aggregate(total=Coalesce(Sum("debt_balance"), 0))["total"],
        "expiring_count": expiring_batches(shop, warn_days).count(),
        "low_stock_count": low_stock_products(shop).count(),
    }
