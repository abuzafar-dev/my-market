from datetime import date
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

from django.test import TestCase
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.catalog.models import Batch, Product
from apps.sales.models import Sale
from apps.sales.services import CartLine, cancel_sale, create_sale
from apps.shops.models import Shop, ShopSettings, User


class ReportExportTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        ShopSettings.objects.create(shop=self.shop)
        self.owner = User.objects.create_user(
            phone="+998901112233", password="pass1234", shop=self.shop, full_name="Egasi"
        )
        self.seller = User.objects.create_user(
            phone="+998907778899",
            password="pass1234",
            shop=self.shop,
            full_name="Sotuvchi",
            role=User.Role.SELLER,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def make_product(self, name, stock, min_stock="5", unit=Product.Unit.KG):
        product = Product.objects.create(
            shop=self.shop,
            name=name,
            unit=unit,
            markup_pct=Decimal("20"),
            min_stock=Decimal(min_stock),
        )
        Batch.objects.create(
            shop=self.shop,
            product=product,
            qty_initial=Decimal(stock),
            qty_remaining=Decimal(stock),
            cost_price=1000,
            sale_price=1200,
        )
        return product

    def sell(self, product, qty):
        return create_sale(
            shop=self.shop,
            user=self.owner,
            client_id=uuid4(),
            payment_type=Sale.PaymentType.CASH,
            customer=None,
            cart=[CartLine(product=product, qty=Decimal(qty))],
        )

    def sheet_rows(self, response):
        sheet = load_workbook(BytesIO(response.content)).active
        return [[cell.value for cell in row] for row in sheet.iter_rows()]

    def test_low_stock_export_lists_only_low_products(self):
        self.make_product("Un", "3")
        self.make_product("Shakar", "50")

        response = self.client.get("/api/reports/low-stock/export/")

        self.assertEqual(response.status_code, 200)
        rows = self.sheet_rows(response)
        self.assertEqual(rows[0][0], "Nomi")
        self.assertEqual([row[0] for row in rows[1:]], ["Un"])
        self.assertEqual(rows[1][3], 3.0)

    def test_unsold_export_excludes_products_with_completed_sales(self):
        sold = self.make_product("Un", "50")
        self.make_product("Guruch", "50")
        self.sell(sold, "2")

        response = self.client.get("/api/reports/unsold/export/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row[0] for row in self.sheet_rows(response)[1:]], ["Guruch"])

    def test_unsold_export_counts_cancelled_sale_as_unsold(self):
        product = self.make_product("Un", "50")
        cancel_sale(self.sell(product, "2"), self.owner)

        response = self.client.get("/api/reports/unsold/export/")

        self.assertEqual([row[0] for row in self.sheet_rows(response)[1:]], ["Un"])

    def test_exports_are_owner_only(self):
        self.client.force_authenticate(self.seller)
        for url in ("/api/reports/low-stock/export/", "/api/reports/unsold/export/"):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_reports_includes_today_profit_regardless_of_period(self):
        product = self.make_product("Un", "50")
        self.sell(product, "2")  # 2 * (1200 - 1000)

        response = self.client.get("/api/reports/", {"period": "month"})

        self.assertEqual(response.json()["data"]["today_profit"], 400)

    def test_top_products_carry_their_unit(self):
        self.sell(self.make_product("Un", "50"), "2.5")

        response = self.client.get("/api/reports/", {"period": "day"})

        top = response.json()["data"]["top_products"]
        self.assertEqual(top[0]["product__name"], "Un")
        self.assertEqual(top[0]["product__unit"], "kg")
        self.assertEqual(Decimal(top[0]["qty_sold"]), Decimal("2.5"))


class PeriodReportTests(ReportExportTests):
    """Per-day breakdown and the period export files."""

    def test_month_series_lists_every_day_up_to_today_and_puts_sales_on_today(self):
        self.sell(self.make_product("Un", "50"), "2")  # revenue 2400, profit 400

        data = self.client.get("/api/reports/", {"period": "month"}).json()["data"]

        rows = data["series"]["rows"]
        self.assertEqual(data["series"]["kind"], "day")
        self.assertEqual(len(rows), date.today().day)  # 1st .. today, zeros included
        self.assertEqual(rows[0]["key"], date.today().replace(day=1).isoformat())
        self.assertEqual(rows[-1]["key"], date.today().isoformat())
        self.assertEqual(
            (rows[-1]["count"], rows[-1]["revenue"], rows[-1]["profit"]), (1, 2400, 400)
        )
        self.assertEqual(sum(row["revenue"] for row in rows), data["stats"]["revenue"])
        self.assertEqual(data["range"]["end"], date.today().isoformat())

    def test_week_series_starts_on_monday(self):
        rows = self.client.get("/api/reports/", {"period": "week"}).json()["data"]["series"]["rows"]

        first = date.fromisoformat(rows[0]["key"])
        self.assertEqual(first.weekday(), 0)
        self.assertEqual(len(rows), date.today().weekday() + 1)

    def test_day_series_is_by_hour_and_only_hours_with_sales(self):
        self.sell(self.make_product("Un", "50"), "1")

        series = self.client.get("/api/reports/", {"period": "day"}).json()["data"]["series"]

        self.assertEqual(series["kind"], "hour")
        self.assertEqual(len(series["rows"]), 1)
        self.assertRegex(series["rows"][0]["key"], r"^\d\d:00$")

    def test_cancelled_sales_are_not_in_the_series(self):
        sale = self.sell(self.make_product("Un", "50"), "1")
        cancel_sale(sale, self.owner)

        rows = self.client.get("/api/reports/", {"period": "week"}).json()["data"]["series"]["rows"]

        self.assertEqual(sum(row["revenue"] for row in rows), 0)

    def test_xlsx_export_has_summary_days_sales_and_products_sheets(self):
        product = self.make_product("Un", "50")
        self.sell(product, "2")
        self.sell(product, "1")

        response = self.client.get(
            "/api/reports/export/", {"period": "week", "file": "xlsx", "lang": "uz"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(".xlsx", response["Content-Disposition"])
        workbook = load_workbook(BytesIO(response.content))
        self.assertEqual(
            workbook.sheetnames,
            ["Xulosa", "Kunlar bo'yicha", "Barcha sotuvlar", "Mahsulotlar bo'yicha"],
        )
        days = [[c.value for c in row] for row in workbook["Kunlar bo'yicha"].iter_rows()]
        self.assertEqual(days[0][:3], ["Sana", "Hafta kuni", "Sotuvlar soni"])
        self.assertEqual(days[-1][0], "JAMI")
        self.assertEqual(days[-1][2:4], [2, 3600])  # 2 sales, 3 kg * 1200
        sales = list(workbook["Barcha sotuvlar"].iter_rows(values_only=True))
        self.assertEqual(len(sales), 3)  # header + 2 sales
        products = list(workbook["Mahsulotlar bo'yicha"].iter_rows(values_only=True))
        self.assertEqual(products[1], ("Un", "kg", 3.0, 3600))

    def test_xlsx_export_in_russian(self):
        self.sell(self.make_product("Un", "50"), "1")

        response = self.client.get(
            "/api/reports/export/", {"period": "month", "file": "xlsx", "lang": "ru"}
        )

        workbook = load_workbook(BytesIO(response.content))
        self.assertEqual(workbook.sheetnames[0], "Итоги")
        self.assertIn("otchet_", response["Content-Disposition"])

    def test_csv_export_is_excel_friendly_and_matches_the_screen_totals(self):
        self.sell(self.make_product("Un", "50"), "2")

        response = self.client.get("/api/reports/export/", {"period": "month", "file": "csv"})

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertTrue(body.startswith("﻿"))  # BOM: Excel reads the letters right
        lines = body.lstrip("﻿").splitlines()
        self.assertTrue(lines[0].startswith("Sana;Hafta kuni;Sotuvlar soni"))
        self.assertTrue(lines[-1].startswith("JAMI;;1;2400"))

    def test_export_is_owner_only(self):
        seller = APIClient()
        seller.force_authenticate(self.seller)

        self.assertEqual(seller.get("/api/reports/export/", {"file": "xlsx"}).status_code, 403)


class DebtSummaryTests(ReportExportTests):
    """The credit block of the report: sold on credit, paid back, owed."""

    def make_customer(self, name):
        from apps.debt.models import Customer

        return Customer.objects.create(shop=self.shop, full_name=name, phone="+998901112233")

    def sell_on_credit(self, product, qty, customer):
        return create_sale(
            shop=self.shop,
            user=self.owner,
            client_id=uuid4(),
            payment_type=Sale.PaymentType.DEBT,
            customer=customer,
            cart=[CartLine(product=product, qty=Decimal(qty))],
        )

    def debt(self, period="month"):
        return self.client.get("/api/reports/", {"period": period}).json()["data"]["debt"]

    def test_credit_sales_are_summed_and_counted_apart_from_cash(self):
        product = self.make_product("Un", "100")
        aziz, vali = self.make_customer("Aziz"), self.make_customer("Vali")
        self.sell_on_credit(product, "2", aziz)  # 2400
        self.sell_on_credit(product, "1", aziz)  # 1200
        self.sell_on_credit(product, "5", vali)  # 6000
        self.sell(product, "10")  # cash — must not count

        debt = self.debt()

        self.assertEqual((debt["sold"], debt["sold_count"], debt["sold_customers"]), (9600, 3, 2))

    def test_payments_and_outstanding_balance(self):
        from apps.debt.services import add_payment

        product = self.make_product("Un", "100")
        aziz = self.make_customer("Aziz")
        self.sell_on_credit(product, "5", aziz)  # owes 6000
        add_payment(customer=aziz, user=self.owner, amount=2500)

        debt = self.debt()

        self.assertEqual(debt["paid"], 2500)
        self.assertEqual((debt["outstanding"], debt["debtors"]), (3500, 1))

    def test_cancelled_credit_sale_is_not_counted(self):
        product = self.make_product("Un", "100")
        sale = self.sell_on_credit(product, "2", self.make_customer("Aziz"))
        cancel_sale(sale, self.owner)

        self.assertEqual(self.debt()["sold"], 0)

    def test_xlsx_summary_carries_paid_and_outstanding(self):
        product = self.make_product("Un", "100")
        self.sell_on_credit(product, "5", self.make_customer("Aziz"))

        response = self.client.get(
            "/api/reports/export/", {"period": "month", "file": "xlsx", "lang": "uz"}
        )

        summary = {
            row[0]: row[1]
            for row in load_workbook(BytesIO(response.content))["Xulosa"].iter_rows(
                values_only=True
            )
            if row[0]
        }
        self.assertEqual(summary["Qarzga (so'm)"], 6000)
        self.assertEqual(summary["Hozirgi jami qarz qoldig'i (so'm)"], 6000)
