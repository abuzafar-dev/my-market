"""Sale endpoints — FIFO checkout, listing, and cancellation (TZ v2 8.2–8.3)."""

from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.catalog.models import Product
from apps.catalog.services import requires_whole_number
from apps.debt.models import Customer

from .models import Sale
from .serializers import SaleCreateSerializer, SaleReadSerializer
from .services import CartLine, InsufficientStock, can_cancel_sale, cancel_sale, create_sale


class SaleViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "head", "options"]
    serializer_class = SaleReadSerializer

    def get_throttles(self):
        # Basic abuse protection on checkout (P5) — browsing sales stays
        # under the default anon-only throttling.
        if self.action == "create":
            self.throttle_scope = "writes"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        queryset = (
            Sale.objects.filter(shop=self.request.user.shop)
            .prefetch_related("items__product")
            .order_by("-sold_at")
        )
        date_ = self.request.query_params.get("date")
        status_ = self.request.query_params.get("status")
        if date_:
            try:
                queryset = queryset.filter(sold_at__date=date.fromisoformat(date_))
            except ValueError:
                raise ValidationError(
                    {"date": "Sana YYYY-MM-DD ko'rinishida bo'lishi kerak."}
                ) from None
        if status_:
            queryset = queryset.filter(status=status_)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        shop = request.user.shop

        # A retry of a checkout that already went through (the response was
        # lost on a flaky connection) must get that sale back — even if a
        # product was archived or sold out in the meantime, which the checks
        # below would otherwise report as a fresh error (TZ v2 6.5).
        existing = Sale.objects.filter(shop=shop, client_id=data["client_id"]).first()
        if existing:
            return Response(
                SaleReadSerializer(existing, context=self.get_serializer_context()).data,
                status=status.HTTP_201_CREATED,
            )

        product_ids = [item["product_id"] for item in data["items"]]
        products = {p.id: p for p in Product.objects.filter(shop=shop, id__in=product_ids)}
        missing = set(product_ids) - set(products)
        if missing:
            return Response(
                {
                    "data": None,
                    "error": {"code": "product_not_found", "message": "Mahsulot topilmadi."},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        for product in products.values():
            if not product.is_active:
                return Response(
                    {
                        "data": None,
                        "error": {
                            "code": "product_inactive",
                            "message": f"{product.name}: arxivlangan mahsulotni sotib bo'lmaydi.",
                            "product_id": str(product.id),
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        for item in data["items"]:
            product = products[item["product_id"]]
            if requires_whole_number(product.unit, item["qty"]):
                return Response(
                    {
                        "data": None,
                        "error": {
                            "code": "invalid_quantity",
                            "message": f"{product.name}: dona hisobida faqat butun son bo'lishi kerak.",
                            "product_id": str(product.id),
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        cart = [CartLine(product=products[i["product_id"]], qty=i["qty"]) for i in data["items"]]

        customer = None
        if data.get("customer_id"):
            # An archived customer is hidden everywhere — no new debt on them.
            customer = get_object_or_404(
                Customer, shop=shop, id=data["customer_id"], is_active=True
            )

        try:
            sale = create_sale(
                shop=shop,
                user=request.user,
                client_id=data["client_id"],
                payment_type=data["payment_type"],
                customer=customer,
                cart=cart,
            )
        except InsufficientStock as exc:
            return Response(
                {
                    "data": None,
                    "error": {
                        "code": "insufficient_stock",
                        "message": str(exc),
                        "product_id": str(exc.product.id),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            SaleReadSerializer(sale, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        sale = self.get_object()
        if not can_cancel_sale(request.user, sale):
            raise PermissionDenied("Sotuvchi faqat o'zining bugungi chekini bekor qila oladi.")
        sale = cancel_sale(sale, request.user)
        return Response(SaleReadSerializer(sale, context=self.get_serializer_context()).data)
