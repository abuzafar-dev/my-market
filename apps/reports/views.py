"""Dashboard, statistics, and CSV export (TZ v2 8.2, 9.6)."""

from datetime import date
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.catalog.services import low_stock_products
from apps.common.permissions import IsOwner
from apps.shops.models import User

from .exports import period_csv_response, period_xlsx_response, safe_row
from .services import (
    dashboard,
    debt_summary,
    period_bounds,
    previous_period_bounds,
    sales_series,
    sales_stats,
    sold_products,
    totals_between,
    unsold_products,
    write_off_total,
)

_VALID_PERIODS = {"day", "week", "month"}


def _anchor(request) -> date | None:
    """``?date=YYYY-MM-DD`` — any day inside the period to show (default:
    today). A future date is pulled back to today by ``period_bounds``."""
    raw = request.query_params.get("date")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValidationError({"date": "Sana YYYY-MM-DD ko'rinishida bo'lishi kerak."}) from None


class DashboardView(APIView):
    """GET /api/dashboard/ — one call for the home screen (TZ v2 3.6/3.7/3.8/4.1).

    Open to both roles (it's the landing page after login), but the "today"
    revenue/profit breakdown is financial data — owner-only, stripped for
    sellers (permissions matrix, P1)."""

    def get(self, request):
        data = dashboard(request.user.shop)
        if request.user.role != User.Role.OWNER:
            data.pop("today", None)
        return Response(data)


class ReportsView(APIView):
    """GET /api/reports/?period=day|week|month&date=YYYY-MM-DD

    The day, week (Mon–Sun) or month that contains ``date`` (default: today),
    cut off at today. ``today`` is sent back so the client never has to trust
    the device's clock or time zone for "is this the current period"."""

    permission_classes = [IsAuthenticated, IsOwner]

    def get(self, request):
        period = request.query_params.get("period", "day")
        if period not in _VALID_PERIODS:
            period = "day"
        shop = request.user.shop
        start, end = period_bounds(period, _anchor(request))
        prev_start, prev_end = previous_period_bounds(period, end)
        return Response(
            {
                "period": period,
                "today": timezone.localdate().isoformat(),
                "range": {"start": start.isoformat(), "end": end.isoformat()},
                # The same stretch of the previous period, for "+12%" arrows.
                "previous": {
                    "range": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
                    **totals_between(shop, prev_start, prev_end),
                },
                "series": sales_series(shop, start, end),
                "stats": sales_stats(shop, start, end),
                "products": sold_products(shop, start, end),
                "debt": debt_summary(shop, start, end),
                "write_offs_total": write_off_total(shop, start, end),
            }
        )


class ReportsExportView(APIView):
    """GET /api/reports/export/?period=day|week|month&date=YYYY-MM-DD&file=xlsx|csv&lang=uz|ru

    The sales report for one period, as a file (not the JSON envelope, TZ v2
    9.6). xlsx -> a workbook (summary, per-day, every sale, per-product);
    csv -> the per-day table."""

    permission_classes = [IsAuthenticated, IsOwner]
    # Building a workbook is heavy: keep one account from hammering it.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "exports"

    def get(self, request):
        period = request.query_params.get("period", "month")
        if period not in _VALID_PERIODS:
            period = "month"
        lang = "ru" if request.query_params.get("lang") == "ru" else "uz"
        shop = request.user.shop
        start, end = period_bounds(period, _anchor(request))
        if request.query_params.get("file") == "xlsx":
            return period_xlsx_response(shop, period, start, end, lang)
        return period_csv_response(shop, start, end, lang)


_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(filename: str, sheet_title: str, headers: list[str], rows) -> HttpResponse:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_title
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(safe_row(row))
    for column in sheet.columns:
        width = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = min(max(width + 2, 10), 50)

    buffer = BytesIO()
    workbook.save(buffer)
    response = HttpResponse(buffer.getvalue(), content_type=_XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class LowStockExportView(APIView):
    """GET /api/reports/low-stock/export/ — products at/below min stock, as .xlsx."""

    permission_classes = [IsAuthenticated, IsOwner]
    # Building a workbook is heavy: keep one account from hammering it.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "exports"

    def get(self, request):
        products = low_stock_products(request.user.shop)
        rows = (
            [
                product.name,
                product.barcode or "",
                product.get_unit_display(),
                float(product.stock),
                float(product.min_stock),
            ]
            for product in products
        )
        return _xlsx_response(
            "kam_qolgan_tovarlar.xlsx",
            "Kam qolganlar",
            ["Nomi", "Shtrix-kod", "O'lchov birligi", "Qoldiq", "Minimal qoldiq"],
            rows,
        )


class UnsoldExportView(APIView):
    """GET /api/reports/unsold/export/ — products never sold, as .xlsx."""

    permission_classes = [IsAuthenticated, IsOwner]
    # Building a workbook is heavy: keep one account from hammering it.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "exports"

    def get(self, request):
        products = unsold_products(request.user.shop)
        rows = (
            [
                product.name,
                product.barcode or "",
                product.get_unit_display(),
                float(product.stock),
                product.created_at.strftime("%Y-%m-%d"),
            ]
            for product in products
        )
        return _xlsx_response(
            "sotilmagan_tovarlar.xlsx",
            "Sotilmaganlar",
            ["Nomi", "Shtrix-kod", "O'lchov birligi", "Qoldiq", "Qo'shilgan sana"],
            rows,
        )
