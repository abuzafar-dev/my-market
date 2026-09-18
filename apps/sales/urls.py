"""Sale API routes, mounted at /api/ (see config/urls.py)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("sales", views.SaleViewSet, basename="sale")

urlpatterns = [path("", include(router.urls))]
