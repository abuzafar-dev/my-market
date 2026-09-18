"""Product, batch, and purchase-list endpoints (TZ v2 8.2)."""
from collections import defaultdict

from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Product
from .serializers import (
    BatchCreateSerializer,
    CategorySerializer,
    ProductSerializer,
    ProductWithExpirySerializer,
    WriteOffInputSerializer,
    WriteOffSerializer,
)
from .services import (
    InsufficientBatchStock,
    expiring_batches,
    low_stock_products,
    quick_products,
    with_stock,
    write_off_batch,
)


class CategoryViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """List/create only — renaming or deleting a category stays an admin
    job (TZ v2 4.4); the SPA only needs to tag products with one."""

    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.filter(shop=self.request.user.shop).order_by("name")


class ProductViewSet(viewsets.ModelViewSet):
    # No PUT/DELETE: products are archived (is_active=False), never replaced or deleted.
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list" and self.request.query_params.get("filter") == "expiring":
            return ProductWithExpirySerializer
        return ProductSerializer

    def get_queryset(self):
        shop = self.request.user.shop
        queryset = with_stock(Product.objects.filter(shop=shop))

        if self.action != "list":
            return queryset

        if self.request.query_params.get("quick"):
            return quick_products(shop)

        filter_ = self.request.query_params.get("filter")
        if filter_ == "low":
            return low_stock_products(shop)

        queryset = queryset.filter(is_active=True)
        if filter_ == "expiring":
            product_ids = expiring_batches(shop, shop.settings.expiry_warn_days).values_list(
                "product_id", flat=True
            )
            queryset = queryset.filter(id__in=set(product_ids))

        search = self.request.query_params.get("q")
        if search:
            queryset = queryset.filter(name__icontains=search)

        return queryset.order_by("name")

    def list(self, request, *args, **kwargs):
        if request.query_params.get("filter") != "expiring":
            return super().list(request, *args, **kwargs)

        # Products alone don't carry expiry — attach each one's qualifying
        # batches (with their 🟡/🔴 status) before serializing (TZ v2 3.6).
        shop = request.user.shop
        batches_by_product = defaultdict(list)
        for batch in expiring_batches(shop, shop.settings.expiry_warn_days):
            batches_by_product[batch.product_id].append(batch)

        products = list(self.filter_queryset(self.get_queryset()))
        for product in products:
            product._expiring_batches = batches_by_product.get(product.id, [])

        page = self.paginate_queryset(products)
        serializer = self.get_serializer(page if page is not None else products, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        product = self.get_object()
        product.is_active = False
        product.save(update_fields=["is_active", "updated_at"])
        return Response(ProductSerializer(product, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["get"], url_path=r"barcode/(?P<code>[^/]+)")
    def barcode(self, request, code=None):
        product = with_stock(Product.objects.filter(shop=request.user.shop, barcode=code)).first()
        if product is None:
            raise Http404
        return Response(ProductSerializer(product, context=self.get_serializer_context()).data)


class BatchCreateView(CreateAPIView):
    """POST /api/batches/ — kirim (TZ v2 3.2)."""

    serializer_class = BatchCreateSerializer


class BatchWriteOffView(APIView):
    """POST /api/batches/{id}/writeoff/ (TZ v2 3.6)."""

    def post(self, request, pk=None):
        serializer = WriteOffInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            write_off = write_off_batch(
                shop=request.user.shop, batch_id=pk, user=request.user, **serializer.validated_data
            )
        except InsufficientBatchStock as exc:
            return Response(
                {"data": None, "error": {"code": "insufficient_stock", "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(WriteOffSerializer(write_off).data, status=status.HTTP_201_CREATED)


class PurchaseListView(APIView):
    """GET /api/purchase-list/ — low-stock products to restock (TZ v2 3.7)."""

    def get(self, request):
        products = low_stock_products(request.user.shop)
        serializer = ProductSerializer(products, many=True, context={"request": request})
        return Response(serializer.data)
