from django.db import models

from apps.common.models import BaseModel
from apps.shops.models import Shop, User


class Customer(BaseModel):
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="customers", verbose_name="Do'kon"
    )
    full_name = models.CharField(max_length=255, verbose_name="F.I.Sh.")
    phone = models.CharField(max_length=20, verbose_name="Telefon")
    note = models.TextField(blank=True, verbose_name="Izoh")
    debt_balance = models.BigIntegerField(default=0, verbose_name="Qarz qoldig'i")
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        verbose_name = "Mijoz"
        verbose_name_plural = "Mijozlar"
        indexes = [models.Index(fields=["shop", "-debt_balance"])]

    def __str__(self) -> str:
        return self.full_name


class DebtEntry(BaseModel):
    class EntryType(models.TextChoices):
        DEBT = "debt", "Qarz"
        PAYMENT = "payment", "To'lov"

    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="debt_entries", verbose_name="Do'kon"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="entries", verbose_name="Mijoz"
    )
    sale = models.ForeignKey(
        "sales.Sale",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debt_entries",
        verbose_name="Sotuv",
    )
    amount = models.BigIntegerField(verbose_name="Summa")
    entry_type = models.CharField(
        max_length=10, choices=EntryType.choices, verbose_name="Yozuv turi"
    )
    note = models.TextField(blank=True, verbose_name="Izoh")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debt_entries",
        verbose_name="Kim tomonidan qo'shildi",
    )

    class Meta:
        verbose_name = "Qarz yozuvi"
        verbose_name_plural = "Qarz yozuvlari"
        indexes = [models.Index(fields=["customer", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.customer.full_name} — {self.amount}"
