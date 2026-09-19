"""Dashboard/report routes, mounted at /api/ (see config/urls.py)."""

from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("reports/", views.ReportsView.as_view(), name="reports"),
    path("reports/export/", views.ReportsExportView.as_view(), name="reports-export"),
    path(
        "reports/low-stock/export/",
        views.LowStockExportView.as_view(),
        name="reports-low-stock-export",
    ),
    path("reports/unsold/export/", views.UnsoldExportView.as_view(), name="reports-unsold-export"),
]
