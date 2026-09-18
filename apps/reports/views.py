"""Dashboard, statistics, and CSV export (TZ v2 8.2, 9.6)."""
import csv

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsOwner
from apps.sales.models import Sale
from apps.shops.models import User

from .services import dashboard, sales_stats, top_products, write_off_total

_VALID_PERIODS = {"day", "week", "month"}


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
    """GET /api/reports/?period=day|week|month"""

    permission_classes = [IsAuthenticated, IsOwner]

    def get(self, request):
        period = request.query_params.get("period", "day")
        if period not in _VALID_PERIODS:
            period = "day"
        shop = request.user.shop
        return Response(
            {
                "period": period,
                "stats": sales_stats(shop, period),
                "top_products": top_products(shop, period),
                "write_offs_total": write_off_total(shop, period),
            }
        )


class ReportsExportView(APIView):
    """GET /api/reports/export/ — plain CSV, not the JSON envelope (TZ v2 9.6)."""

    permission_classes = [IsAuthenticated, IsOwner]

    def get(self, request):
        shop = request.user.shop
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="hisobot.csv"'

        writer = csv.writer(response)
        writer.writerow(["Sana", "Jami summa", "To'lov turi", "Sof foyda"])
        sales = Sale.objects.filter(shop=shop, status=Sale.Status.COMPLETED).order_by("sold_at")
        for sale in sales:
            writer.writerow(
                [
                    sale.sold_at.strftime("%Y-%m-%d %H:%M"),
                    sale.total,
                    sale.get_payment_type_display(),
                    sale.total - sale.cost_total,
                ]
            )
        return response
