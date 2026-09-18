from decimal import Decimal

from rest_framework import serializers

from .models import Sale, SaleItem


class SaleItemInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    qty = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))


class SaleCreateSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    payment_type = serializers.ChoiceField(choices=Sale.PaymentType.choices)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    items = SaleItemInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        if attrs["payment_type"] == Sale.PaymentType.DEBT and not attrs.get("customer_id"):
            raise serializers.ValidationError("Qarzga sotish uchun mijoz tanlanishi shart.")
        return attrs


class SaleItemReadSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = SaleItem
        fields = ["product_name", "qty", "unit_price", "unit_cost", "line_total"]


class SaleReadSerializer(serializers.ModelSerializer):
    items = SaleItemReadSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(
        source="customer.full_name", read_only=True, default=None
    )

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
        ]
