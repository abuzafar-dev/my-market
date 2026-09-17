from django.db import models

from apps.catalog.models import Batch, Product
from apps.common.models import BaseModel
from apps.shops.models import Shop, User


class Sale(BaseModel):
    class PaymentType(models.TextChoices):
        CASH = "cash", "Naqd"
        CARD = "card", "Karta"
        DEBT = "debt", "Nasiya"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Yakunlangan"
        CANCELLED = "cancelled", "Bekor qilingan"

    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="sales", verbose_name="Do'kon"
    )
    customer = models.ForeignKey(
        "debt.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales",
        verbose_name="Mijoz",
    )
    client_id = models.UUIDField(verbose_name="Klient ID")
    total = models.BigIntegerField(verbose_name="Jami summa")
    cost_total = models.BigIntegerField(verbose_name="Jami tannarx")
    payment_type = models.CharField(
        max_length=10, choices=PaymentType.choices, verbose_name="To'lov turi"
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.COMPLETED,
        verbose_name="Holati",
    )
    sold_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
        verbose_name="Sotgan xodim",
    )
    sold_at = models.DateTimeField(db_index=True, verbose_name="Sotilgan vaqti")
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="Bekor qilingan vaqti")

    class Meta:
        verbose_name = "Sotuv"
        verbose_name_plural = "Sotuvlar"
        unique_together = ("shop", "client_id")

    def __str__(self) -> str:
        return f"Sotuv {self.id} — {self.total}"


class SaleItem(BaseModel):
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name="items", verbose_name="Sotuv"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="sale_items", verbose_name="Mahsulot"
    )
    batch = models.ForeignKey(
        Batch, on_delete=models.PROTECT, related_name="sale_items", verbose_name="Partiya"
    )
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="Miqdor")
    unit_price = models.BigIntegerField(verbose_name="Birlik narxi")
    unit_cost = models.BigIntegerField(verbose_name="Birlik tannarxi")
    line_total = models.BigIntegerField(verbose_name="Qator summasi")

    class Meta:
        verbose_name = "Sotuv qatori"
        verbose_name_plural = "Sotuv qatorlari"

    def __str__(self) -> str:
        return f"{self.product.name} x {self.qty}"
