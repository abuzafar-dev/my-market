from rest_framework import serializers

from .models import Customer, DebtEntry


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "full_name", "phone", "note", "debt_balance", "is_active"]
        read_only_fields = ["debt_balance", "is_active"]

    def create(self, validated_data):
        validated_data["shop"] = self.context["request"].user.shop
        return super().create(validated_data)


class DebtEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = DebtEntry
        fields = ["id", "amount", "entry_type", "note", "created_at"]


class CustomerDetailSerializer(CustomerSerializer):
    entries = DebtEntrySerializer(many=True, read_only=True)

    class Meta(CustomerSerializer.Meta):
        fields = CustomerSerializer.Meta.fields + ["entries"]


class DebtActionInputSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")
