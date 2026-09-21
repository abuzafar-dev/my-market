"""Add a staff member (seller) or a second owner to an existing shop.

This is the safe way to create accounts on a server where the Django admin is
switched off: it takes an existing owner's phone to find the shop.
"""

from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.shops.models import User

WEAK_PASSWORD_NOTICE = (
    "Diqqat: parol xavfsizlik tekshiruvisiz o'rnatildi — uzunroq parol tavsiya etiladi."
)


class Command(BaseCommand):
    help = "Mavjud do'konga yangi sotuvchi (yoki ega) qo'shadi."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--owner-phone", required=True, help="Do'kon egasining telefoni")
        parser.add_argument("--phone", required=True, help="Yangi xodimning telefoni (+998...)")
        parser.add_argument("--full-name", required=True, help="Yangi xodimning ismi")
        parser.add_argument("--password", required=True, help="Yangi xodimning paroli")
        parser.add_argument(
            "--role", choices=[User.Role.SELLER, User.Role.OWNER], default=User.Role.SELLER
        )
        parser.add_argument(
            "--allow-weak-password",
            action="store_true",
            help="Serverda ham qisqa/oddiy parolga ruxsat berish (xavfsizlik tekshiruvini o'chiradi)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            owner = User.objects.get(phone=options["owner_phone"], role=User.Role.OWNER)
        except User.DoesNotExist:
            raise CommandError(f"'{options['owner_phone']}' raqamli ega topilmadi.") from None

        if User.objects.filter(phone=options["phone"]).exists():
            raise CommandError(f"'{options['phone']}' raqami allaqachon band.")

        allow_weak: bool = options["allow_weak_password"]
        if not settings.DEBUG and not allow_weak:
            # a real server gets a real password unless the operator opts out
            try:
                validate_password(options["password"])
            except ValidationError as exc:
                raise CommandError("Parol yaroqsiz: " + " ".join(exc.messages)) from None

        User.objects.create_user(
            phone=options["phone"],
            password=options["password"],
            shop=owner.shop,
            full_name=options["full_name"],
            role=options["role"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{options['full_name']} ({options['phone']}) qo'shildi: {owner.shop.name}"
            )
        )
        if allow_weak:
            self.stdout.write(self.style.WARNING(WEAK_PASSWORD_NOTICE))
