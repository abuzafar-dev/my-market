from decimal import Decimal

from rest_framework import serializers

from apps.common.limits import MAX_LINES, MAX_QTY
from apps.shops.models import User

from .models import Sale, SaleItem
from .services import can_cancel_sale


class SaleItemInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    qty = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001"), max_value=MAX_QTY
    )


class SaleCreateSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    payment_type = serializers.ChoiceField(choices=Sale.PaymentType.choices)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    items = SaleItemInputSerializer(many=True, allow_empty=False, max_length=MAX_LINES)

    def validate(self, attrs):
        if attrs["payment_type"] == Sale.PaymentType.DEBT and not attrs.get("customer_id"):
            raise serializers.ValidationError("Qarzga sotish uchun mijoz tanlanishi shart.")
        return attrs


class SaleItemReadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = SaleItem
        fields = ["product_name", "qty", "unit_price", "unit_cost", "line_total"]

    def to_representation(self, instance):
        # unit_cost is cost-price data — owner-only (permissions matrix, P1).
        # Checked here (not via context-aware __init__) because this
        # serializer is nested inside SaleReadSerializer as a declared
        # field, so self.context isn't bound until render time.
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request is not None and getattr(request.user, "role", None) != User.Role.OWNER:
            data.pop("unit_cost", None)
        return data


class SaleReadSerializer(serializers.ModelSerializer):
    items = SaleItemReadSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True, default=None)
    can_cancel = serializers.SerializerMethodField()

    def get_can_cancel(self, sale: Sale) -> bool:
        request = self.context.get("request")
        if request is None or sale.status == Sale.Status.CANCELLED:
            return False
        return can_cancel_sale(request.user, sale)

    class Meta:
        model = Sale
        fields = [
            "id",
            "client_id",
            "total",
            "payment_type",
            "status",
            "customer",
            "customer_name",
            "items",
            "sold_at",
            "cancelled_at",
            "can_cancel",
        ]
