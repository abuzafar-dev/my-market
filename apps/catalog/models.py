from decimal import Decimal

from django.db import models
from django.db.models import Sum

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
    barcode = models.CharField(
        max_length=64, null=True, blank=True, db_index=True, verbose_name="Shtrix-kod"
    )
    unit = models.CharField(
        max_length=10, choices=Unit.choices, default=Unit.PIECE, verbose_name="O'lchov birligi"
    )
    markup_pct = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name="Ustama foizi"
    )
    min_stock = models.DecimalField(
        max_digits=12, decimal_places=3, verbose_name="Minimal qoldiq"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        unique_together = ("shop", "barcode")

    def __str__(self) -> str:
        return self.name

    @property
    def stock(self) -> Decimal:
        total = self.batches.aggregate(total=Sum("qty_remaining"))["total"]
        return total or Decimal("0")


class Batch(BaseModel):
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="batches", verbose_name="Do'kon"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="batches", verbose_name="Mahsulot"
    )
    qty_initial = models.DecimalField(
        max_digits=12, decimal_places=3, verbose_name="Boshlang'ich miqdor"
    )
    qty_remaining = models.DecimalField(
        max_digits=12, decimal_places=3, verbose_name="Qolgan miqdor"
    )
    cost_price = models.BigIntegerField(verbose_name="Tannarx")
    sale_price = models.BigIntegerField(verbose_name="Sotuv narxi")
    produced_at = models.DateField(verbose_name="Ishlab chiqarilgan sana")
    expires_at = models.DateField(null=True, blank=True, verbose_name="Yaroqlilik muddati")
    received_at = models.DateTimeField(verbose_name="Qabul qilingan sana")
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
            )
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
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="Miqdor")
    cost_total = models.BigIntegerField(verbose_name="Umumiy tannarx")
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
