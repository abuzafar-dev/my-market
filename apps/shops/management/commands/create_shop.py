"""Provision a new shop and its owner account.

There is no public sign-up flow — every shop is created by whoever
operates the platform, through this command.
"""

import secrets
import string
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.shops.models import Shop, ShopSettings, User


def _generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Command(BaseCommand):
    help = "Yangi do'kon va uning egasini yaratadi."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--shop-name", required=True, help="Do'kon nomi")
        parser.add_argument("--phone", required=True, help="Egasining telefon raqami")
        parser.add_argument("--full-name", required=True, help="Egasining to'liq ismi")

    def handle(self, *args: Any, **options: Any) -> None:
        shop_name: str = options["shop_name"]
        phone: str = options["phone"]
        full_name: str = options["full_name"]

        if User.objects.filter(phone=phone).exists():
            raise CommandError(f"'{phone}' raqami bilan foydalanuvchi allaqachon mavjud.")

        password = _generate_password()

        with transaction.atomic():
            shop = Shop.objects.create(name=shop_name)
            ShopSettings.objects.create(shop=shop)
            User.objects.create_user(
                phone=phone,
                password=password,
                shop=shop,
                full_name=full_name,
                role=User.Role.OWNER,
                is_staff=True,
            )

        self.stdout.write(self.style.SUCCESS(f"Do'kon yaratildi: {shop_name}"))
        self.stdout.write(f"Egasi: {full_name} ({phone})")
        self.stdout.write(self.style.WARNING(f"Vaqtinchalik parol: {password}"))
        self.stdout.write(
            self.style.WARNING(
                "Diqqat: bu parol faqat shu yerda ko'rsatiladi — "
                "birinchi kirishda uni albatta almashtiring."
            )
        )
