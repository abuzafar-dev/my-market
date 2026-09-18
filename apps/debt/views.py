"""Customer / debt-ledger endpoints (TZ v2 8.2)."""

from django.db.models import Prefetch
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import Customer, DebtEntry
from .serializers import (
    CustomerDetailSerializer,
    CustomerSerializer,
    DebtActionInputSerializer,
)
from .services import add_debt, add_payment


class CustomerViewSet(viewsets.ModelViewSet):
    # No hard delete: customers, like everything with a ledger, are archived.
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_throttles(self):
        # Basic abuse protection on the write-heavy debt actions (P5) —
        # browsing/creating customers stays under the default anon-only
        # throttling.
        if self.action in {"debt", "payment"}:
            self.throttle_scope = "writes"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CustomerDetailSerializer
        return CustomerSerializer

    def get_queryset(self):
        queryset = Customer.objects.filter(shop=self.request.user.shop, is_active=True)

        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                Prefetch("entries", queryset=DebtEntry.objects.order_by("-created_at"))
            )

        search = self.request.query_params.get("q")
        if search:
            queryset = queryset.filter(full_name__icontains=search)

        return queryset.order_by("-debt_balance")

    @action(detail=True, methods=["post"])
    def debt(self, request, pk=None):
        customer = self.get_object()
        serializer = DebtActionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        add_debt(customer=customer, user=request.user, **serializer.validated_data)
        return Response(
            CustomerDetailSerializer(
                self.get_queryset().get(pk=customer.pk), context=self.get_serializer_context()
            ).data
        )

    @action(detail=True, methods=["post"])
    def payment(self, request, pk=None):
        customer = self.get_object()
        serializer = DebtActionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        add_payment(customer=customer, user=request.user, **serializer.validated_data)
        return Response(
            CustomerDetailSerializer(
                self.get_queryset().get(pk=customer.pk), context=self.get_serializer_context()
            ).data
        )
