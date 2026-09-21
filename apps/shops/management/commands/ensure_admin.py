"""Keep the one fixed admin account in place: an owner-level login that lets
the platform operator open the site and see what is going on in the shop.

Runs on every container start (see docker-entrypoint.sh). The phone and the
password are fixed on purpose — and since the app no longer lets anyone change
a password, re-running this also puts the password back if it was altered
elsewhere (Django admin, ``changepassword``).
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.shops.models import Shop, User

ADMIN_PHONE = "+998777777777"
ADMIN_PASSWORD = "admin1"  # pragma: allowlist secret
ADMIN_NAME = "Admin"


class Command(BaseCommand):
    help = "Doimiy admin akkauntini (777777777 / admin1) yaratadi yoki tiklaydi."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        admin = User.objects.filter(phone=ADMIN_PHONE).first()

        if admin is None:
            # The admin looks into the first (oldest) shop; before any shop
            # exists there is nothing to look into yet.
            shop = Shop.objects.order_by("created_at").first()
            if shop is None:
                self.stdout.write("Hali do'kon yo'q — admin keyinroq yaratiladi.")
                return
            admin = User(phone=ADMIN_PHONE, shop=shop, full_name=ADMIN_NAME)

        admin.role = User.Role.OWNER
        admin.is_active = True
        admin.is_staff = True
        admin.set_password(ADMIN_PASSWORD)
        admin.save()
        self.stdout.write(self.style.SUCCESS(f"Admin tayyor: {ADMIN_PHONE} ({admin.shop.name})"))
