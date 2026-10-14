"""Create the platform operator's owner-level login, once, from the environment.

The phone and password come from ``MARKET_ADMIN_PHONE`` and
``MARKET_ADMIN_PASSWORD`` (``.env`` or the container environment) — never from
the code, never from a command-line argument, and the password is never
printed. The password must pass Django's password validators.

The account is only ever *created*: if a user with that phone already exists
it is left exactly as it is (password, role, access). To change its password
use ``manage.py changepassword <phone>``.

docker-entrypoint.sh runs this with ``--if-configured`` on every start, so a
server that sets neither variable simply gets no operator account.
"""

from argparse import ArgumentParser
from typing import Any

from decouple import config
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.shops.models import Shop, User
from apps.shops.serializers import normalize_phone

ADMIN_NAME = "Admin"


class Command(BaseCommand):
    help = (
        "MARKET_ADMIN_PHONE va MARKET_ADMIN_PASSWORD o'zgaruvchilaridan admin (ega) "
        "akkauntini bir marta yaratadi. Mavjud akkauntga tegmaydi."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--if-configured",
            action="store_true",
            help="Ikkala o'zgaruvchi ham bo'sh bo'lsa, xatosiz o'tkazib yuborish (entrypoint uchun)",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        raw_phone: str = config("MARKET_ADMIN_PHONE", default="").strip()
        password: str = config("MARKET_ADMIN_PASSWORD", default="")

        if not raw_phone and not password:
            if options["if_configured"]:
                self.stdout.write("MARKET_ADMIN_PHONE/PASSWORD berilmagan — admin yaratilmadi.")
                return
            raise CommandError("MARKET_ADMIN_PHONE va MARKET_ADMIN_PASSWORD berilishi kerak.")
        if not raw_phone or not password:
            raise CommandError(
                "MARKET_ADMIN_PHONE va MARKET_ADMIN_PASSWORD ikkalasi ham berilishi kerak."
            )

        phone = normalize_phone(raw_phone)
        if User.objects.filter(phone=phone).exists():
            self.stdout.write(f"{phone} akkaunti allaqachon bor — o'zgartirilmadi.")
            return

        # The admin looks into the first (oldest) shop; before any shop exists
        # there is nothing to look into yet.
        shop = Shop.objects.order_by("created_at").first()
        if shop is None:
            self.stdout.write("Hali do'kon yo'q — admin keyinroq yaratiladi.")
            return

        admin = User(
            phone=phone,
            shop=shop,
            full_name=ADMIN_NAME,
            role=User.Role.OWNER,
            is_active=True,
            is_staff=True,
        )
        try:
            validate_password(password, user=admin)
        except ValidationError as exc:
            # the messages describe the rule that failed, never the password
            raise CommandError(
                "MARKET_ADMIN_PASSWORD yaroqsiz: " + " ".join(exc.messages)
            ) from None

        admin.set_password(password)
        admin.save()
        self.stdout.write(self.style.SUCCESS(f"Admin yaratildi: {phone} ({shop.name})"))
