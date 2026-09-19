from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel
from apps.shops.models import Shop, User


class Category(BaseModel):
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="categories", verbose_name="Do'kon"
    )
    name = models.CharField(max_length=255, verbose_name="Nomi")

    class Meta:
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        unique_together = ("shop", "name")

    def __str__(self) -> str:
        return self.name


class Product(BaseModel):
    """Stock is never stored here — see TZ v2 7.1: it's always summed live
    from ``batches.qty_remaining`` via ``apps.catalog.services.with_stock``,
    so there is exactly one source of truth."""

    class Unit(models.TextChoices):
        PIECE = "piece", "Dona"
        KG = "kg", "Kilogram"
        LITER = "liter", "Litr"

    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="products", verbose_name="Do'kon"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        verbose_name="Kategoriya",
    )
    name = models.CharField(max_length=255, verbose_name="Nomi")
    image = models.ImageField(upload_to="products/", null=True, blank=True, verbose_name="Rasm")
    barcode = models.CharField(
        max_length=64, null=True, blank=True, db_index=True, verbose_name="Shtrix-kod"
    )
    unit = models.CharField(
        max_length=10, choices=Unit.choices, default=Unit.PIECE, verbose_name="O'lchov birligi"
    )
    # A fixed so'm amount added on top of the cost (not a percentage): the
    # shopkeeper thinks "+1 000 so'm per item", and it stays predictable
    # when the cost changes.
    markup_amount = models.PositiveBigIntegerField(default=0, verbose_name="Ustama (so'm)")
    min_stock = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="Minimal qoldiq")
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        unique_together = ("shop", "barcode")

    def __str__(self) -> str:
        return self.name


class Batch(BaseModel):
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="batches", verbose_name="Do'kon"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="batches", verbose_name="Mahsulot"
    )
    qty_initial = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
        verbose_name="Boshlang'ich miqdor",
    )
    qty_remaining = models.DecimalField(
        max_digits=12, decimal_places=3, verbose_name="Qolgan miqdor"
    )
    cost_price = models.PositiveBigIntegerField(verbose_name="Tannarx")
    sale_price = models.PositiveBigIntegerField(verbose_name="Sotuv narxi")
    produced_at = models.DateField(null=True, blank=True, verbose_name="Ishlab chiqarilgan sana")
    expires_at = models.DateField(null=True, blank=True, verbose_name="Yaroqlilik muddati")
    received_at = models.DateTimeField(default=timezone.now, verbose_name="Qabul qilingan sana")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_batches",
        verbose_name="Kim tomonidan qo'shildi",
    )

    class Meta:
        verbose_name = "Partiya"
        verbose_name_plural = "Partiyalar"
        indexes = [models.Index(fields=["product", "received_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(qty_remaining__gte=0),
                name="batch_qty_remaining_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(qty_initial__gt=0),
                name="batch_qty_initial_gt_0",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} — {self.received_at:%Y-%m-%d}"


class WriteOff(BaseModel):
    class Reason(models.TextChoices):
        EXPIRED = "expired", "Muddati o'tgan"
        DAMAGED = "damaged", "Shikastlangan"
        LOST = "lost", "Yo'qolgan"
        OTHER = "other", "Boshqa"

    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="write_offs", verbose_name="Do'kon"
    )
    batch = models.ForeignKey(
        Batch, on_delete=models.PROTECT, related_name="write_offs", verbose_name="Partiya"
    )
    qty = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
        verbose_name="Miqdor",
    )
    cost_total = models.PositiveBigIntegerField(verbose_name="Umumiy tannarx")
    reason = models.CharField(max_length=10, choices=Reason.choices, verbose_name="Sababi")
    note = models.TextField(blank=True, verbose_name="Izoh")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="write_offs",
        verbose_name="Kim tomonidan hisobdan chiqarildi",
    )

    class Meta:
        verbose_name = "Hisobdan chiqarish"
        verbose_name_plural = "Hisobdan chiqarishlar"

    def __str__(self) -> str:
        return f"{self.batch.product.name} — {self.qty}"
