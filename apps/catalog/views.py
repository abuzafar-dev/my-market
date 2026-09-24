"""Product, batch, and purchase-list endpoints (TZ v2 8.2)."""

import uuid
from collections import defaultdict

from django.db.models import F, Q
from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.limits import MAX_LINES
from apps.common.permissions import IsOwner

from .models import Batch, Category, Product
from .serializers import (
    BatchCreateSerializer,
    BatchSerializer,
    BatchUpdateSerializer,
    CategorySerializer,
    ProductSerializer,
    ProductWithExpirySerializer,
    WriteOffInputSerializer,
    WriteOffSerializer,
)
from .services import (
    InsufficientBatchStock,
    delete_product,
    expiring_batches,
    low_stock_products,
    quick_products,
    update_batch,
    with_price,
    with_stock,
    write_off_batch,
)


class CategoryViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """List/create only — renaming or deleting a category stays an admin
    job (TZ v2 4.4); the SPA only needs to tag products with one."""

    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.filter(shop=self.request.user.shop).order_by("name")


# ?ordering= values the product list accepts; anything else falls back to the
# default order, never to a raw field name from the client.
PRODUCT_ORDERINGS = {
    "name": ("name",),
    "stock": ("stock", "name"),
    "-stock": ("-stock", "name"),
    "price": (F("fifo_price").asc(nulls_last=True), "name"),
    "-price": (F("fifo_price").desc(nulls_last=True), "name"),
}


class ProductViewSet(viewsets.ModelViewSet):
    # No PUT: products are patched in place. DELETE erases one entered by
    # mistake (refused once it has been sold — then it is archived instead).
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        # Sellers may browse products/stock, but only owners create, edit,
        # archive, or delete them (permissions matrix, P1).
        if self.action in {"create", "partial_update", "archive", "destroy", "batches"}:
            return [IsAuthenticated(), IsOwner()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "list" and self.request.query_params.get("filter") == "expiring":
            return ProductWithExpirySerializer
        return ProductSerializer

    def get_queryset(self):
        shop = self.request.user.shop
        queryset = with_price(with_stock(Product.objects.filter(shop=shop))).select_related(
            "category"
        )

        if self.action != "list":
            return queryset

        if self.request.query_params.get("quick"):
            return quick_products(shop)

        params = self.request.query_params
        ids = params.get("ids")
        if ids:
            # The sale screen re-reads the products of a cart restored from
            # the browser, whose saved price/stock may be hours old. Archived
            # ones are left out on purpose: they can't be sold any more.
            try:
                wanted = [uuid.UUID(part) for part in ids.split(",")[:MAX_LINES]]
            except ValueError:
                return queryset.none()
            return queryset.filter(id__in=wanted, is_active=True).order_by("name")

        filter_ = params.get("filter")
        if filter_ == "low":
            # Emptiest first unless the page asks for another order.
            queryset = with_price(low_stock_products(shop)).select_related("category")
            default_ordering = ("stock", "name")
        else:
            queryset = queryset.filter(is_active=True)
            default_ordering = ("name",)
        if filter_ == "expiring":
            product_ids = expiring_batches(shop, shop.get_settings().expiry_warn_days).values_list(
                "product_id", flat=True
            )
            queryset = queryset.filter(id__in=set(product_ids))

        search = params.get("q", "").strip()
        if search:
            # A scanned or typed barcode finds its product on this list too.
            queryset = queryset.filter(Q(name__icontains=search) | Q(barcode=search))

        category = params.get("category")
        if category == "none":
            queryset = queryset.filter(category__isnull=True)
        elif category:
            try:
                queryset = queryset.filter(category_id=uuid.UUID(category))
            except ValueError:
                queryset = queryset.none()

        ordering = PRODUCT_ORDERINGS.get(params.get("ordering"), default_ordering)
        return queryset.order_by(*ordering)

    def list(self, request, *args, **kwargs):
        if request.query_params.get("filter") != "expiring":
            return super().list(request, *args, **kwargs)

        # Products alone don't carry expiry — attach each one's qualifying
        # batches (with their 🟡/🔴 status) before serializing (TZ v2 3.6).
        shop = request.user.shop
        batches_by_product = defaultdict(list)
        for batch in expiring_batches(shop, shop.get_settings().expiry_warn_days):
            batches_by_product[batch.product_id].append(batch)

        products = list(self.filter_queryset(self.get_queryset()))
        for product in products:
            product._expiring_batches = batches_by_product.get(product.id, [])

        page = self.paginate_queryset(products)
        serializer = self.get_serializer(page if page is not None else products, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        delete_product(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def batches(self, request, pk=None):
        """The product's stock batches, newest first — what the owner edits."""
        product = self.get_object()
        batches = product.batches.order_by("-received_at")[:100]
        return Response(BatchSerializer(batches, many=True).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        product = self.get_object()
        product.is_active = False
        product.save(update_fields=["is_active", "updated_at"])
        return Response(ProductSerializer(product, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["get"], url_path=r"barcode/(?P<code>[^/]+)")
    def barcode(self, request, code=None):
        product = (
            with_price(with_stock(Product.objects.filter(shop=request.user.shop, barcode=code)))
            .select_related("category")
            .first()
        )
        if product is None:
            raise Http404
        return Response(ProductSerializer(product, context=self.get_serializer_context()).data)


class BatchCreateView(CreateAPIView):
    """POST /api/batches/ — kirim (TZ v2 3.2)."""

    permission_classes = [IsAuthenticated, IsOwner]
    serializer_class = BatchCreateSerializer


class BatchDetailView(APIView):
    """PATCH /api/batches/{id}/ — correct a wrongly entered price, quantity or expiry."""

    permission_classes = [IsAuthenticated, IsOwner]

    def patch(self, request, pk=None):
        batch = (
            Batch.objects.filter(pk=pk, shop=request.user.shop).select_related("product").first()
        )
        if batch is None:
            raise Http404
        serializer = BatchUpdateSerializer(batch, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        batch = update_batch(shop=request.user.shop, batch_id=pk, **serializer.validated_data)
        return Response(BatchSerializer(batch).data)


class BatchWriteOffView(APIView):
    """POST /api/batches/{id}/writeoff/ (TZ v2 3.6).

    Owner-only: a write-off removes stock without a sale and feeds the
    owner's "Yo'qotishlar" figure — letting a seller do it would let stock
    disappear with no money trail."""

    permission_classes = [IsAuthenticated, IsOwner]

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
        products = with_price(low_stock_products(request.user.shop)).select_related("category")
        serializer = ProductSerializer(products, many=True, context={"request": request})
        return Response(serializer.data)
