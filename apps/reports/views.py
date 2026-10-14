"""Dashboard, statistics, and CSV export (TZ v2 8.2, 9.6)."""

from datetime import date
from io import BytesIO

from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.catalog.services import low_stock_products
from apps.common.permissions import IsOwner
from apps.shops.models import User

from .exports import period_csv_response, safe_row
from .models import ExportJob
from .serializers import ExportJobSerializer
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
from .tasks import build_period_export

_VALID_PERIODS = {"day", "week", "month"}
_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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
    """CSV straight back; Excel as a background job.

    GET  /api/reports/export/?period=&date=&lang=  -> the per-day table as CSV,
    streamed row by row, done in milliseconds.

    POST /api/reports/export/  -> queues the workbook and returns the job to
    poll. The workbook has to be assembled in full before its first byte, so
    building it here would hold a gunicorn worker for the whole time; a few
    owners exporting a month at once was enough to stop the shop selling."""

    permission_classes = [IsAuthenticated, IsOwner]
    # Both paths are expensive enough to be worth a scope of their own.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "exports"

    def get(self, request):
        period = request.query_params.get("period", "month")
        if period not in _VALID_PERIODS:
            period = "month"
        lang = "ru" if request.query_params.get("lang") == "ru" else "uz"
        start, end = period_bounds(period, _anchor(request))
        return period_csv_response(request.user.shop, start, end, lang)

    def post(self, request):
        period = request.data.get("period", "month")
        if period not in _VALID_PERIODS:
            period = "month"
        lang = "ru" if request.data.get("lang") == "ru" else "uz"
        anchor = request.data.get("date") or None
        if anchor:
            try:
                date.fromisoformat(anchor)
            except TypeError, ValueError:
                raise ValidationError(
                    {"date": "Sana YYYY-MM-DD ko'rinishida bo'lishi kerak."}
                ) from None

        job = ExportJob.objects.create(
            shop=request.user.shop,
            requested_by=request.user,
            kind=ExportJob.Kind.PERIOD_XLSX,
            params={"period": period, "date": anchor, "lang": lang},
        )
        # after_commit: the worker can pick the task up before this request's
        # transaction has committed, and would then not find the row.
        transaction.on_commit(lambda: build_period_export.delay(str(job.id)))
        return Response(ExportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class ExportJobView(APIView):
    """GET /api/reports/export/<uuid>/ — what the client polls."""

    permission_classes = [IsAuthenticated, IsOwner]

    def get(self, request, job_id):
        job = _own_job(request, job_id)
        return Response(ExportJobSerializer(job).data)


class ExportJobDownloadView(APIView):
    """GET /api/reports/export/<uuid>/download/ — the finished file.

    MEDIA is served off disk without auth, so the file is never linked
    directly: this view is what checks the job belongs to the caller's shop.
    """

    permission_classes = [IsAuthenticated, IsOwner]

    def get(self, request, job_id):
        job = _own_job(request, job_id)
        if not job.is_downloadable:
            raise ValidationError({"detail": "Fayl hali tayyor emas."})
        return FileResponse(
            job.file.open("rb"),
            as_attachment=True,
            filename=job.filename or "hisobot.xlsx",
            content_type=_XLSX_CONTENT_TYPE,
        )


def _own_job(request, job_id) -> ExportJob:
    """A job from another shop must look missing, not forbidden — a 403 would
    confirm the id exists."""
    job = ExportJob.objects.filter(pk=job_id, shop=request.user.shop).first()
    if job is None:
        raise Http404
    return job


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
