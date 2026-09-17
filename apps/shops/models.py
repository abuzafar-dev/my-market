import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from apps.common.models import BaseModel


class Shop(BaseModel):
    name = models.CharField(max_length=255, verbose_name="Nomi")
    phone = models.CharField(max_length=20, verbose_name="Telefon")
    address = models.TextField(blank=True, verbose_name="Manzil")

    class Meta:
        verbose_name = "Do'kon"
        verbose_name_plural = "Do'konlar"

    def __str__(self) -> str:
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, phone: str, password: str | None = None, **extra_fields):
        if not phone:
            raise ValueError("Telefon raqami kiritilishi shart")
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.OWNER)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser is_staff=True bo'lishi shart")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser is_superuser=True bo'lishi shart")

        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        OWNER = "owner", "Egasi"
        SELLER = "seller", "Sotuvchi"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="users", verbose_name="Do'kon"
    )
    phone = models.CharField(max_length=20, unique=True, verbose_name="Telefon")
    full_name = models.CharField(max_length=255, verbose_name="F.I.Sh.")
    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.OWNER, verbose_name="Rol"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    is_staff = models.BooleanField(default=False, verbose_name="Xodim")

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name", "shop"]

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

    def __str__(self) -> str:
        return f"{self.full_name} ({self.phone})"


class ShopSettings(models.Model):
    shop = models.OneToOneField(
        Shop,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="settings",
        verbose_name="Do'kon",
    )
    expiry_warn_days = models.PositiveSmallIntegerField(
        default=7, verbose_name="Muddat ogohlantirish (kun)"
    )
    currency = models.CharField(max_length=3, default="UZS", verbose_name="Valyuta")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan")

    class Meta:
        verbose_name = "Do'kon sozlamasi"
        verbose_name_plural = "Do'kon sozlamalari"

    def __str__(self) -> str:
        return f"{self.shop.name} sozlamalari"
