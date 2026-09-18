"""Fills a shop with realistic demo products, batches, and categories.

Meant for trying out the app with a believable catalog instead of one or
two hand-entered items — quantities, prices, and expiry dates are randomized
within plausible ranges, not pulled from real supplier data.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.catalog.models import Batch, Category, Product
from apps.shops.models import Shop

# (category name, unit for its products, [base item names])
# Every base name is combined with each brand below to reach 500+ products
# while still reading like real shop inventory.
_CATEGORIES: list[tuple[str, str, list[str]]] = [
    (
        "Oziq-ovqat",
        Product.Unit.PIECE,
        [
            "Guruch", "Un", "Shakar", "Tuz", "O'simlik yog'i", "Sariyog'",
            "Makaron", "Vermishel", "Yorma (grechka)", "Tuzlangan bodring",
            "Konserva pomidor", "Konserva no'xat", "Sirka", "Ziravorlar to'plami",
            "Qand", "Nuxat", "Loviya", "Un yormasi",
        ],
    ),
    (
        "Ichimliklar",
        Product.Unit.PIECE,
        [
            "Suv 0.5L", "Suv 1.5L", "Gazli ichimlik Cola", "Gazli ichimlik Fanta",
            "Sok olma", "Sok apelsin", "Choy qora", "Choy ko'k", "Kofe",
            "Energetik ichimlik", "Kvas", "Kompot", "Limonad",
        ],
    ),
    (
        "Non mahsulotlari",
        Product.Unit.PIECE,
        ["Non", "Bulochka", "Lavash", "Pechenye", "Vafli", "Tort", "Krendel", "Somsa"],
    ),
    (
        "Sut mahsulotlari",
        Product.Unit.LITER,
        ["Sut", "Qatiq", "Tvorog", "Pishloq", "Smetana", "Kefir", "Ayron"],
    ),
    (
        "Go'sht mahsulotlari",
        Product.Unit.KG,
        ["Qo'y go'shti", "Mol go'shti", "Tovuq go'shti", "Kolbasa", "Sosiska", "Qiyma"],
    ),
    (
        "Meva-sabzavot",
        Product.Unit.KG,
        [
            "Olma", "Banan", "Apelsin", "Uzum", "Pomidor", "Bodring", "Kartoshka",
            "Piyoz", "Sarimsoq", "Sabzi", "Qulupnay", "Tarvuz", "Qovun", "Limon",
        ],
    ),
    (
        "Maishiy kimyo",
        Product.Unit.PIECE,
        [
            "Kir yuvish kukuni", "Idish yuvish suyuqligi", "Sovun", "Tish pastasi",
            "Shampun", "Dush geli", "Tozalash vositasi", "Xushbo'y hid purkagich",
        ],
    ),
    (
        "Gigiena",
        Product.Unit.PIECE,
        ["Tualet qog'ozi", "Salfetka", "Bolalar tagligi", "Prokladka", "Tish cho'tkasi", "Sochiq"],
    ),
    (
        "Shirinliklar",
        Product.Unit.PIECE,
        ["Shokolad", "Konfet", "Jeleybobo", "Marmelad", "Muzqaymoq", "Sagiz"],
    ),
    (
        "Boshqa",
        Product.Unit.PIECE,
        ["Sigareta", "Gugurt", "Batareyka", "Elektr lampochka", "Bir martalik idish"],
    ),
]

_BRANDS = [
    "Lazzat", "Oltin don", "Mahalliy", "Import", "Standart",
    "Premium", "Chempion", "Yulduz", "Baraka", "Nur",
]

_PRICE_RANGES = {
    Product.Unit.PIECE: (2_000, 60_000),
    Product.Unit.KG: (8_000, 120_000),
    Product.Unit.LITER: (5_000, 25_000),
}

_PERISHABLE_CATEGORIES = {"Meva-sabzavot", "Sut mahsulotlari", "Go'sht mahsulotlari", "Non mahsulotlari"}


class Command(BaseCommand):
    help = "Belgilangan do'konga demo mahsulotlar, kategoriyalar va partiyalarni to'ldiradi."

    def add_arguments(self, parser):
        parser.add_argument("--phone", required=True, help="Do'kon egasining telefon raqami")
        parser.add_argument(
            "--count", type=int, default=500, help="Yaratiladigan mahsulotlar soni (default: 500)"
        )
        parser.add_argument(
            "--barcode-ratio",
            type=float,
            default=0.6,
            help="Shtrix-kodli mahsulotlar ulushi, 0-1 oralig'ida (default: 0.6)",
        )

    def handle(self, *args, **options):
        try:
            shop = Shop.objects.get(users__phone=options["phone"])
        except Shop.DoesNotExist as exc:
            raise CommandError(f"'{options['phone']}' raqamli foydalanuvchi topilmadi.") from exc

        target_count = options["count"]
        barcode_ratio = options["barcode_ratio"]

        categories = {}
        for name, _unit, _items in _CATEGORIES:
            category, _ = Category.objects.get_or_create(shop=shop, name=name)
            categories[name] = category

        combos = [
            (cat_name, unit, item, brand)
            for cat_name, unit, items in _CATEGORIES
            for item in items
            for brand in _BRANDS
        ]
        random.shuffle(combos)
        combos = combos[:target_count]

        existing_barcodes = set(
            Product.objects.filter(shop=shop, barcode__isnull=False).values_list(
                "barcode", flat=True
            )
        )
        barcode_counter = 2_900_000_000_000

        products: list[Product] = []
        now = timezone.now()

        for cat_name, unit, item, brand in combos:
            name = f"{item} ({brand})"
            low, high = _PRICE_RANGES[unit]

            give_barcode = random.random() < barcode_ratio
            barcode = None
            if give_barcode:
                while str(barcode_counter) in existing_barcodes:
                    barcode_counter += 1
                barcode = str(barcode_counter)
                existing_barcodes.add(barcode)
                barcode_counter += 1

            if unit == Product.Unit.PIECE:
                min_stock = Decimal(random.randint(5, 20))
            else:
                min_stock = Decimal(str(round(random.uniform(2, 15), 3)))

            products.append(
                Product(
                    shop=shop,
                    category=categories[cat_name],
                    name=name,
                    barcode=barcode,
                    unit=unit,
                    markup_pct=Decimal(str(random.randint(10, 35))),
                    min_stock=min_stock,
                    is_active=True,
                )
            )

        Product.objects.bulk_create(products)

        batches = []
        for product in products:
            low, high = _PRICE_RANGES[product.unit]
            cost_price = random.randint(low, high)
            sale_price = int(round(cost_price * (1 + product.markup_pct / Decimal("100"))))

            if product.unit == Product.Unit.PIECE:
                qty = Decimal(random.randint(10, 200))
            else:
                qty = Decimal(str(round(random.uniform(5, 100), 3)))

            expires_at = None
            if product.category.name in _PERISHABLE_CATEGORIES and random.random() < 0.7:
                expires_at = (now + timedelta(days=random.randint(-3, 60))).date()

            batches.append(
                Batch(
                    shop=shop,
                    product=product,
                    qty_initial=qty,
                    qty_remaining=qty,
                    cost_price=cost_price,
                    sale_price=sale_price,
                    expires_at=expires_at,
                    received_at=now,
                )
            )

        Batch.objects.bulk_create(batches)

        with_barcode = sum(1 for p in products if p.barcode)
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(products)} ta mahsulot yaratildi ({with_barcode} tasi shtrix-kodli, "
                f"{len(products) - with_barcode} tasi shtrix-kodsiz), har biriga 1 tadan partiya bilan."
            )
        )
