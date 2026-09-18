"""Catalog API routes, mounted at /api/ (see config/urls.py)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("products", views.ProductViewSet, basename="product")
router.register("categories", views.CategoryViewSet, basename="category")

urlpatterns = [
    path("", include(router.urls)),
    path("batches/", views.BatchCreateView.as_view(), name="batch-create"),
    path("batches/<uuid:pk>/writeoff/", views.BatchWriteOffView.as_view(), name="batch-writeoff"),
    path("purchase-list/", views.PurchaseListView.as_view(), name="purchase-list"),
]
