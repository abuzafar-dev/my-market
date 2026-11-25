"""Idempotently create a demo shop that looks like a shop in use: 100 real
products with real photos (apps/catalog/demo_catalog/, sources and licences in
its ATTRIBUTION.md), an owner and a seller with fixed, known credentials, a few
customers, and 30 days of sales history — so the reports, the top sellers, the
low-stock and expiry warnings and the debt book all have something to show.

Runs on container start only when SEED_DEMO=true (see deploy/docker-entrypoint.sh).
A real server leaves SEED_DEMO off and creates its shop with `manage.py create_shop`.

The history goes through the real sale / debt services (FIFO stock, debt
ledger), then gets its timestamps moved back into the past. Stock arrives in
two deliveries (before the month and in its middle), sized from how well each
product sells. A fixed random seed makes every fresh demo the same.
"""

import json
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Batch, Category, Product
from apps.debt.models import Customer, DebtEntry
from apps.debt.services import add_payment
from apps.sales.models import Sale
from apps.sales.services import CartLine, InsufficientStock, create_sale
from apps.shops.models import Shop, ShopSettings, User

DEMO_PHONE = "+998900000001"
DEMO_SELLER_PHONE = "+998900000002"
DEMO_PASSWORD = "demo12345"

CATALOG_DIR = Path(__file__).resolve().parents[3] / "catalog" / "demo_catalog"
HISTORY_DAYS = 30
PERISHABLE = {"Sut mahsulotlari", "Go'sht mahsulotlari", "Non mahsulotlari", "Meva-sabzavot"}

CUSTOMERS = [
    ("Aziza Karimova", "+998901112233"),
    ("Bekzod Toshmatov", "+998935554411"),
    ("Dilnoza Rahimova", "+998977776655"),
    ("Jasur Aliyev", "+998998887766"),
    ("Malika Yusupova", "+998946663322"),
    ("Sardor Qodirov", "+998911234567"),
]

# Rough size of the month, used only to size the deliveries.
_SALES_PER_DAY = 22
_LINES_PER_SALE = 3
_QTY_PER_LINE = Decimal("1.6")


@dataclass
class _Item:
    product: Product
    popularity: float
    cost: int
    price: int
    short: bool  # delivered too little: ends the month on the low-stock list


def _cost(price: int) -> int:
    """Purchase price: about 80 % of the shelf price, in whole hundreds."""
    return max(100, int(price * 0.8) // 100 * 100)


def _image(file_name: str) -> str:
    """Storage path of a catalogue photo, copied into media on first use."""
    path = f"products/demo/{file_name}"
    if not default_storage.exists(path):
        default_storage.save(path, ContentFile((CATALOG_DIR / "images" / file_name).read_bytes()))
    return path


def _aware(day: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return timezone.make_aware(datetime.combine(day, time(hour, minute, second)))


def _opening_hours_moment(day: date, rng: random.Random) -> datetime:
    """A moment within opening hours (08:00–21:59, shop time), busier evenings."""
    hour = rng.choices(range(8, 22), weights=[2, 3, 4, 4, 5, 5, 4, 4, 5, 6, 7, 7, 5, 3])[0]
    return _aware(day, hour, rng.randrange(60), rng.randrange(60))


class Command(BaseCommand):
    help = (
        "Demo do'kon: 100 ta haqiqiy rasmli mahsulot, egasi, sotuvchi, mijozlar va "
        "30 kunlik sotuv tarixi (agar mavjud bo'lmasa)."
    )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        if User.objects.filter(phone=DEMO_PHONE).exists():
            self.stdout.write("Demo foydalanuvchi allaqachon mavjud, o'tkazib yuborildi.")
            return

        self.rng = random.Random(2026)
        self.now = timezone.now()
        self.today = timezone.localdate()
        start = self.today - timedelta(days=HISTORY_DAYS)

        self.shop = Shop.objects.create(name="Demo Do'koni")
        ShopSettings.objects.create(shop=self.shop)
        self.owner = User.objects.create_user(
            phone=DEMO_PHONE,
            password=DEMO_PASSWORD,
            shop=self.shop,
            full_name="Demo Owner",
            role=User.Role.OWNER,
            is_staff=True,
        )
        seller = User.objects.create_user(
            phone=DEMO_SELLER_PHONE,
            password=DEMO_PASSWORD,
            shop=self.shop,
            full_name="Demo Sotuvchi",
            role=User.Role.SELLER,
        )
        self.staff = [self.owner, seller]
        self.customers = [
            Customer.objects.create(shop=self.shop, full_name=name, phone=phone)
            for name, phone in CUSTOMERS
        ]

        items = self._catalog(created=_aware(start - timedelta(days=5), 9))
        self._deliver(items, _aware(start - timedelta(days=5), 9), half=1, last=False)
        middle = start + timedelta(days=HISTORY_DAYS // 2)
        sales = self._sell(items, start, middle - timedelta(days=1))
        self._deliver(items, _aware(middle, 8, 30), half=2, last=True)
        sales += self._sell(items, middle, self.today)

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo do'kon yaratildi: {len(items)} ta mahsulot, "
                f"{sales} ta sotuv ({HISTORY_DAYS} kun)."
            )
        )
        self.stdout.write(f"Egasi:    {DEMO_PHONE} / {DEMO_PASSWORD}")
        self.stdout.write(f"Sotuvchi: {DEMO_SELLER_PHONE} / {DEMO_PASSWORD}")

    def _catalog(self, created: datetime) -> list[_Item]:
        rng = self.rng
        catalogue = json.loads((CATALOG_DIR / "products.json").read_text(encoding="utf-8"))
        categories: dict[str, Category] = {}
        items = []
        for entry in catalogue:
            if entry["category"] not in categories:
                categories[entry["category"]] = Category.objects.create(
                    shop=self.shop, name=entry["category"]
                )
            price, cost = entry["price"], _cost(entry["price"])
            by_kg = entry["unit"] == Product.Unit.KG
            product = Product.objects.create(
                shop=self.shop,
                category=categories[entry["category"]],
                name=entry["name"],
                unit=entry["unit"],
                barcode=entry["barcode"],
                image=_image(entry["image"]),
                markup_amount=price - cost,
                min_stock=Decimal(5 if by_kg else rng.choice([5, 6, 8, 10])),
            )
            items.append(
                _Item(
                    product=product,
                    # A few clear best-sellers, a long tail, a few that barely move.
                    popularity=min(rng.paretovariate(1.4), 5.0),
                    cost=cost,
                    price=price,
                    short=rng.random() < 0.07,
                )
            )
        Product.objects.filter(shop=self.shop).update(created_at=created)
        return items

    def _deliver(self, items: list[_Item], at: datetime, *, half: int, last: bool) -> None:
        """One delivery: enough for about half the month's demand of each
        product, plus some left on the shelf after the last one."""
        rng = self.rng
        total_popularity = sum(item.popularity for item in items)
        month_qty = HISTORY_DAYS * _SALES_PER_DAY * _LINES_PER_SALE * _QTY_PER_LINE
        for item in items:
            demand = month_qty * Decimal(item.popularity / total_popularity) / 2
            if item.short and last:
                qty = demand * Decimal("0.8")
            else:
                spare = rng.randint(10, 35) if last else rng.randint(3, 10)
                qty = demand * Decimal("1.15") + spare
            qty = Decimal(int(qty) + 1)  # whole units; kg goods are weighed out of it
            expires = None
            if item.product.category.name in PERISHABLE and rng.random() < 0.6:
                # The second delivery is what is on the shelf now: mostly
                # fresh, a few close to their date (expiry warning).
                days = rng.choice([3, 6, 15, 20, 30, 45, 60]) if last else rng.randint(35, 50)
                expires = (self.today if last else at.date()) + timedelta(days=days)
            batch = Batch.objects.create(
                shop=self.shop,
                product=item.product,
                qty_initial=qty,
                qty_remaining=qty,
                cost_price=item.cost,
                sale_price=item.price,
                expires_at=expires,
                received_at=at,
                created_by=self.owner,
            )
            Batch.objects.filter(pk=batch.pk).update(created_at=at)

    def _sell(self, items: list[_Item], first: date, last: date) -> int:
        rng = self.rng
        weights = [item.popularity for item in items]
        count = 0
        day = first
        while day <= last:
            per_day = rng.randint(24, 34) if day.weekday() >= 5 else rng.randint(16, 26)
            for moment in sorted(_opening_hours_moment(day, rng) for _ in range(per_day)):
                if moment > self.now:
                    break
                if self._one_sale(items, weights, moment):
                    count += 1
            day += timedelta(days=1)
        return count

    def _one_sale(self, items: list[_Item], weights: list[float], moment: datetime) -> bool:
        rng = self.rng
        cart: dict[int, CartLine] = {}
        for item in rng.choices(items, weights=weights, k=rng.randint(1, 5)):
            if item.product.unit == Product.Unit.KG:
                qty = Decimal(rng.choice(["0.5", "0.7", "1", "1", "1.5", "2", "2.5", "3"]))
            else:
                qty = Decimal(rng.choice([1, 1, 1, 1, 2, 2, 3]))
            cart[item.product.pk] = CartLine(product=item.product, qty=qty)

        roll = rng.random()
        if roll < 0.08:
            payment, customer = Sale.PaymentType.DEBT, rng.choice(self.customers)
        elif roll < 0.33:
            payment, customer = Sale.PaymentType.CARD, None
        else:
            payment, customer = Sale.PaymentType.CASH, None

        while cart:
            try:
                sale = create_sale(
                    shop=self.shop,
                    user=rng.choice(self.staff),
                    client_id=uuid.uuid4(),
                    payment_type=payment,
                    customer=customer,
                    cart=list(cart.values()),
                )
                break
            except InsufficientStock as exc:
                # Sold out: the customer takes the rest of the basket.
                cart.pop(exc.product.pk)
        else:
            return False

        Sale.objects.filter(pk=sale.pk).update(sold_at=moment, created_at=moment)
        if customer:
            DebtEntry.objects.filter(sale=sale).update(
                created_at=moment, due_date=timezone.localdate(moment) + timedelta(days=14)
            )
            # Most debtors bring back part of it a few days later.
            paid_on = moment + timedelta(days=rng.randint(2, 9))
            if paid_on < self.now and rng.random() < 0.6:
                customer.refresh_from_db()
                amount = min(customer.debt_balance, max(1000, sale.total // 1000 * 1000))
                if amount > 0:
                    entry = add_payment(customer=customer, user=self.owner, amount=amount)
                    DebtEntry.objects.filter(pk=entry.pk).update(created_at=paid_on)
        return True
