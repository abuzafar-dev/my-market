from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.common.limits import MAX_NOTE, MAX_PRICE, MAX_QTY
from apps.shops.models import User

from .exceptions import BarcodeConflict
from .models import Batch, Category, Product, WriteOff
from .services import batch_status, requires_whole_number


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]

    def create(self, validated_data):
        validated_data["shop"] = self.context["request"].user.shop
        return super().create(validated_data)


class ProductSerializer(serializers.ModelSerializer):
    stock = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "image",
            "category",
            "category_name",
            "barcode",
            "unit",
            "markup_pct",
            "min_stock",
            "is_active",
            "stock",
            "price",
        ]
        read_only_fields = ["is_active"]

    def to_representation(self, instance):
        # markup_pct is cost data in disguise (sale price = cost * (1 + markup)),
        # so it follows the same rule as SaleItem.unit_cost: owner-only. The
        # request is checked here because this serializer is also nested.
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request is not None and getattr(request.user, "role", None) != User.Role.OWNER:
            data.pop("markup_pct", None)
        return data

    def get_price(self, product: Product) -> int | None:
        """The price a sale would actually charge right now: the oldest
        (FIFO-head) batch's sale price. Different batches of the same
        product can carry different prices, so this is only a preview —
        the real price is always resolved server-side at checkout."""
        if hasattr(product, "fifo_price"):  # annotated by with_price() on list screens
            return product.fifo_price
        batch = product.batches.filter(qty_remaining__gt=0).order_by("received_at").first()
        return batch.sale_price if batch else None

    ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
    MAX_IMAGE_BYTES = 5 * 1024 * 1024
    MAX_IMAGE_SIDE = 8000

    def validate_image(self, image):
        """Only real, reasonably small JPEG/PNG/WebP pictures. Pillow has already
        opened the upload (ImageField), so SVG/HTML/scripts renamed to .jpg are
        gone; here we cap the size and the pixel dimensions (decompression
        bombs) and pin the format, because files are served back to browsers
        from the site's own origin."""
        if image is None:
            return image
        if image.size > self.MAX_IMAGE_BYTES:
            raise serializers.ValidationError("Rasm juda katta (5 MB dan oshmasin).")
        picture = getattr(image, "image", None)
        if picture is not None:
            if picture.format not in self.ALLOWED_IMAGE_FORMATS:
                raise serializers.ValidationError("Faqat JPEG, PNG yoki WebP rasm mumkin.")
            if max(picture.size) > self.MAX_IMAGE_SIDE:
                raise serializers.ValidationError("Rasm o'lchami juda katta.")
        return image

    def validate_category(self, category):
        if category and category.shop_id != self.context["request"].user.shop_id:
            raise serializers.ValidationError("Bunday kategoriya topilmadi.")
        return category

    def validate(self, attrs):
        unit = attrs.get("unit", getattr(self.instance, "unit", None))
        min_stock = attrs.get("min_stock", getattr(self.instance, "min_stock", None))
        if unit and min_stock is not None and requires_whole_number(unit, min_stock):
            raise serializers.ValidationError(
                {"min_stock": "Dona hisobidagi mahsulot uchun miqdor butun son bo'lishi kerak."}
            )
        return attrs

    def validate_barcode(self, barcode: str | None) -> str | None:
        # unique_together=("shop", "barcode") treats '' as a real, colliding
        # value (unlike NULL) — normalize every falsy input to None so a
        # second barcode-less product doesn't 500 on that constraint.
        if barcode:
            barcode = barcode.strip()
        if not barcode:
            return None
        shop = self.context["request"].user.shop
        queryset = Product.objects.filter(shop=shop, barcode=barcode)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise BarcodeConflict()
        return barcode

    def create(self, validated_data):
        validated_data["shop"] = self.context["request"].user.shop
        return super().create(validated_data)


class ExpiringBatchSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = Batch
        fields = ["id", "qty_remaining", "expires_at", "status"]

    def get_status(self, batch: Batch) -> str:
        return batch_status(batch.expires_at)


class ProductWithExpirySerializer(ProductSerializer):
    """Adds the specific expiring batches, for ?filter=expiring (TZ v2 3.6)."""

    expiring_batches = ExpiringBatchSerializer(
        many=True, read_only=True, source="_expiring_batches"
    )

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ["expiring_batches"]


class BatchCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = [
            "id",
            "product",
            "qty_initial",
            "cost_price",
            "sale_price",
            "expires_at",
            "received_at",
        ]
        extra_kwargs = {
            "sale_price": {"required": False, "max_value": MAX_PRICE},
            "cost_price": {"max_value": MAX_PRICE},
            "qty_initial": {"max_value": MAX_QTY},
            "received_at": {"required": False},
        }

    def validate_product(self, product: Product) -> Product:
        if product.shop_id != self.context["request"].user.shop_id:
            raise serializers.ValidationError("Mahsulot topilmadi.")
        return product

    def validate(self, attrs):
        product = attrs.get("product")
        qty = attrs.get("qty_initial")
        if product and qty is not None and requires_whole_number(product.unit, qty):
            raise serializers.ValidationError(
                {"qty_initial": "Dona hisobidagi mahsulot uchun miqdor butun son bo'lishi kerak."}
            )
        # The auto-calculated sale price (cost + markup) must stay in range too.
        if product and "sale_price" not in attrs and "cost_price" in attrs:
            auto_price = attrs["cost_price"] * (1 + product.markup_pct / Decimal("100"))
            if auto_price > MAX_PRICE:
                raise serializers.ValidationError({"cost_price": "Narx juda katta."})
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        product = validated_data["product"]
        cost_price = validated_data["cost_price"]

        sale_price = validated_data.get("sale_price")
        if sale_price is None:
            sale_price = round(cost_price + (cost_price * product.markup_pct / Decimal("100")))

        return Batch.objects.create(
            shop=request.user.shop,
            product=product,
            qty_initial=validated_data["qty_initial"],
            qty_remaining=validated_data["qty_initial"],
            cost_price=cost_price,
            sale_price=int(sale_price),
            expires_at=validated_data.get("expires_at"),
            received_at=validated_data.get("received_at", timezone.now()),
            created_by=request.user,
        )


class WriteOffInputSerializer(serializers.Serializer):
    qty = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001"), max_value=MAX_QTY
    )
    reason = serializers.ChoiceField(choices=WriteOff.Reason.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=MAX_NOTE)


class WriteOffSerializer(serializers.ModelSerializer):
    class Meta:
        model = WriteOff
        fields = ["id", "batch", "qty", "cost_total", "reason", "note", "created_at"]
