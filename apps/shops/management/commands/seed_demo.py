"""Idempotently create a demo shop + owner with fixed, known credentials and a
small catalogue of 10 products with stock.

Runs on container start only when SEED_DEMO=true (see docker-entrypoint.sh) —
a fresh demo `docker compose up --build` then has something to log into (there
is no public sign-up) and to sell. A real server leaves SEED_DEMO off and
creates its shop with `manage.py create_shop`.
"""

from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Batch, Category, Product
from apps.shops.models import Shop, ShopSettings, User

DEMO_PHONE = "+998900000001"
DEMO_PASSWORD = "demo12345"

# name, unit, barcode, category, cost (so'm), markup (so'm), stock, minimum stock
PRODUCTS = [
    ("Non", Product.Unit.PIECE, "4780000000014", "Non mahsulotlari", 2500, 500, 40, 10),
    ("Sut 1 litr", Product.Unit.PIECE, "4780000000021", "Sut mahsulotlari", 9000, 1500, 24, 6),
    ("Qatiq 0.5 litr", Product.Unit.PIECE, "4780000000038", "Sut mahsulotlari", 6000, 1000, 18, 5),
    ("Shakar", Product.Unit.KG, None, "Oziq-ovqat", 12000, 1500, 50, 10),
    ("Un", Product.Unit.KG, None, "Oziq-ovqat", 6500, 1000, 80, 15),
    ("Guruch", Product.Unit.KG, None, "Oziq-ovqat", 14000, 2000, 60, 10),
    ("Osh yog'i 1 litr", Product.Unit.LITER, None, "Oziq-ovqat", 22000, 3000, 30, 5),
    ("Choy 100 g", Product.Unit.PIECE, "4780000000045", "Ichimliklar", 8000, 2000, 36, 8),
    ("Banan", Product.Unit.KG, None, "Meva-sabzavot", 16000, 4000, 20, 5),
    ("Suv 1.5 litr", Product.Unit.PIECE, "4780000000052", "Ichimliklar", 2000, 500, 48, 12),
]


class Command(BaseCommand):
    help = "Demo do'kon, uning egasi va 10 ta mahsulotni (agar mavjud bo'lmasa) yaratadi."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        if User.objects.filter(phone=DEMO_PHONE).exists():
            self.stdout.write("Demo foydalanuvchi allaqachon mavjud, o'tkazib yuborildi.")
            return

        shop = Shop.objects.create(name="Demo Do'koni")
        ShopSettings.objects.create(shop=shop)
        owner = User.objects.create_user(
            phone=DEMO_PHONE,
            password=DEMO_PASSWORD,
            shop=shop,
            full_name="Demo Owner",
            role=User.Role.OWNER,
            is_staff=True,
        )

        categories = {}
        for name, unit, barcode, category, cost, markup, stock, minimum in PRODUCTS:
            if category not in categories:
                categories[category] = Category.objects.create(shop=shop, name=category)
            product = Product.objects.create(
                shop=shop,
                category=categories[category],
                name=name,
                unit=unit,
                barcode=barcode,
                markup_amount=markup,
                min_stock=Decimal(minimum),
            )
            Batch.objects.create(
                shop=shop,
                product=product,
                qty_initial=Decimal(stock),
                qty_remaining=Decimal(stock),
                cost_price=cost,
                sale_price=cost + markup,
                created_by=owner,
            )

        self.stdout.write(
            self.style.SUCCESS(f"Demo do'kon yaratildi ({len(PRODUCTS)} ta mahsulot).")
        )
        self.stdout.write(f"Telefon: {DEMO_PHONE}")
        self.stdout.write(f"Parol: {DEMO_PASSWORD}")
