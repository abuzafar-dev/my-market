"""Mustaqil ish, 9-qadam: chegaraviy qiymatlar testlari.

can_cancel_sale() va requires_whole_number() — ma'lumotlar bazasisiz,
oddiy obyektlar bilan tekshiriladi (SimpleTestCase)."""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from apps.catalog.services import requires_whole_number
from apps.sales.services import can_cancel_sale

TOSHKENT = ZoneInfo("Asia/Tashkent")
HOZIR = datetime(2026, 10, 20, 12, 0, tzinfo=TOSHKENT)


def user(uid, role="seller"):
    return SimpleNamespace(id=uid, role=role)


def sale(sold_by_id, sold_at):
    return SimpleNamespace(sold_by_id=sold_by_id, sold_at=sold_at)


@patch("django.utils.timezone.now", return_value=HOZIR)
class CanCancelSaleTests(SimpleTestCase):
    def test_owner_cancels_any_sale(self, _):
        old = sale(2, datetime(2025, 1, 1, tzinfo=TOSHKENT))
        self.assertTrue(can_cancel_sale(user(1, "owner"), old))

    def test_seller_own_sale_today(self, _):
        self.assertTrue(can_cancel_sale(user(1), sale(1, HOZIR)))

    def test_seller_colleagues_sale_today(self, _):
        self.assertFalse(can_cancel_sale(user(1), sale(2, HOZIR)))

    def test_boundary_today_00_00_00(self, _):
        tun = datetime(2026, 10, 20, 0, 0, 0, tzinfo=TOSHKENT)
        self.assertTrue(can_cancel_sale(user(1), sale(1, tun)))

    def test_boundary_yesterday_23_59_59(self, _):
        kecha = datetime(2026, 10, 19, 23, 59, 59, tzinfo=TOSHKENT)
        self.assertFalse(can_cancel_sale(user(1), sale(1, kecha)))

    def test_boundary_utc_evening_is_tashkent_today(self, _):
        # 19.10 soat 19:30 UTC = 20.10 soat 00:30 Toshkent -> bugungi sotuv
        utc = datetime(2026, 10, 19, 19, 30, tzinfo=ZoneInfo("UTC"))
        self.assertTrue(can_cancel_sale(user(1), sale(1, utc)))


class WholeNumberTests(SimpleTestCase):
    def test_piece_integer_is_ok(self):
        self.assertFalse(requires_whole_number("piece", Decimal("1")))

    def test_piece_smallest_fraction_is_refused(self):
        self.assertTrue(requires_whole_number("piece", Decimal("1.001")))

    def test_piece_just_below_integer_is_refused(self):
        self.assertTrue(requires_whole_number("piece", Decimal("0.999")))

    def test_kg_fraction_is_ok(self):
        self.assertFalse(requires_whole_number("kg", Decimal("0.001")))
