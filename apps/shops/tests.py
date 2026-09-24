from io import StringIO

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.shops.models import Shop, ShopSettings, User


class AuthUserPayloadTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Asosiy do'kon", phone="+998900000000")
        ShopSettings.objects.create(shop=self.shop)
        User.objects.create_user(
            phone="+998901112233", password="pass1234", shop=self.shop, full_name="Egasi"
        )

    def test_login_returns_shop_name_for_the_header(self):
        response = APIClient().post(
            "/api/auth/login/", {"phone": "+998901112233", "password": "pass1234"}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        user = response.json()["data"]["user"]
        self.assertEqual(user["shop_name"], "Asosiy do'kon")
        self.assertEqual(user["shop_id"], str(self.shop.id))


class LoginPhoneFormatTests(TestCase):
    def setUp(self):
        shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        ShopSettings.objects.create(shop=shop)
        User.objects.create_user(phone="+998772874307", password="1", shop=shop, full_name="Egasi")

    def login(self, phone):
        return APIClient().post(
            "/api/auth/login/", {"phone": phone, "password": "1"}, format="json"
        )

    def test_number_without_country_code_logs_in(self):
        self.assertEqual(self.login("772874307").status_code, 200)

    def test_spaced_and_prefixed_forms_log_in(self):
        for phone in ("+998772874307", "998772874307", "+998 77 287 43 07", " 77-287-43-07 "):
            with self.subTest(phone=phone):
                self.assertEqual(self.login(phone).status_code, 200)

    def test_wrong_number_is_still_rejected(self):
        self.assertEqual(self.login("772874308").status_code, 400)


class RefreshTokenTests(TestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        ShopSettings.objects.create(shop=self.shop)
        self.user = User.objects.create_user(
            phone="+998901112233", password="pass1234", shop=self.shop, full_name="Egasi"
        )

    def refresh(self):
        client = APIClient(raise_request_exception=False)
        client.cookies["refresh_token"] = str(RefreshToken.for_user(self.user))
        return client.post("/api/auth/refresh/", {}, format="json")

    def test_active_user_gets_a_new_access_token_and_their_profile(self):
        response = self.refresh()

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("access", data)
        self.assertEqual(data["user"]["shop_name"], "Do'kon")

    def test_deactivated_user_cannot_refresh(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)

        response = self.refresh()

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.content.decode())

    def test_missing_cookie_is_401(self):
        response = APIClient().post("/api/auth/refresh/", {}, format="json")

        self.assertEqual(response.status_code, 401)


class ShopWithoutSettingsTests(TestCase):
    """A shop added through the admin has no ShopSettings row yet."""

    def setUp(self):
        self.shop = Shop.objects.create(name="Yangi do'kon", phone="+998900000009")
        self.user = User.objects.create_user(
            phone="+998901112244", password="pass1234", shop=self.shop, full_name="Egasi"
        )
        self.client = APIClient(raise_request_exception=False)
        self.client.force_authenticate(self.user)

    def test_dashboard_works_and_creates_default_settings(self):
        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ShopSettings.objects.get(shop=self.shop).expiry_warn_days, 7)

    def test_settings_endpoint_reads_and_updates(self):
        self.assertEqual(self.client.get("/api/settings/").status_code, 200)

        response = self.client.patch("/api/settings/", {"expiry_warn_days": 3}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ShopSettings.objects.get(shop=self.shop).expiry_warn_days, 3)

    def test_settings_reject_out_of_range_window_and_currency_edits(self):
        for days in (0, 366):
            response = self.client.patch(
                "/api/settings/", {"expiry_warn_days": days}, format="json"
            )
            self.assertEqual(response.status_code, 400)

        self.client.patch("/api/settings/", {"currency": "USD"}, format="json")
        self.assertEqual(ShopSettings.objects.get(shop=self.shop).currency, "UZS")

    def test_expiring_filter_works(self):
        self.assertEqual(self.client.get("/api/products/", {"filter": "expiring"}).status_code, 200)


class ProvisioningCommandTests(TestCase):
    def test_create_shop_can_set_the_owner_password(self):
        from django.core.management import call_command

        call_command(
            "create_shop",
            shop_name="Yangi",
            phone="+998772874307",
            full_name="Egasi",
            password="Kuchli-Parol-2026",
            stdout=StringIO(),
        )

        user = User.objects.get(phone="+998772874307")
        self.assertEqual(user.role, User.Role.OWNER)
        self.assertTrue(user.check_password("Kuchli-Parol-2026"))
        self.assertTrue(ShopSettings.objects.filter(shop=user.shop).exists())

    def test_a_server_refuses_weak_passwords_for_new_accounts(self):
        from django.core.management import CommandError, call_command

        with self.assertRaises(CommandError):
            call_command(
                "create_shop",
                shop_name="Yangi",
                phone="+998772874307",
                full_name="Egasi",
                password="1",
                stdout=StringIO(),
            )
        self.assertFalse(User.objects.filter(phone="+998772874307").exists())

    def test_add_user_puts_a_seller_in_the_owners_shop(self):
        from django.core.management import call_command

        call_command(
            "create_shop",
            shop_name="Yangi",
            phone="+998772874307",
            full_name="Egasi",
            password="Kuchli-Parol-2026",
            stdout=StringIO(),
        )
        call_command(
            "add_user",
            owner_phone="+998772874307",
            phone="+998907654321",
            full_name="Sotuvchi",
            password="Sotuvchi-Parol-77",
            stdout=StringIO(),
        )

        seller = User.objects.get(phone="+998907654321")
        owner = User.objects.get(phone="+998772874307")
        self.assertEqual((seller.role, seller.shop_id), (User.Role.SELLER, owner.shop_id))

    def test_seed_demo_makes_ten_sellable_products_once(self):
        from django.core.management import call_command

        from apps.catalog.models import Product

        for _ in range(2):  # idempotent
            call_command("seed_demo", stdout=StringIO())

        shop = User.objects.get(phone="+998900000001").shop
        products = Product.objects.filter(shop=shop)
        self.assertEqual(products.count(), 10)
        self.assertEqual(Shop.objects.count(), 1)
        self.assertTrue(all(p.batches.filter(qty_remaining__gt=0).exists() for p in products))


class EnsureAdminTests(TestCase):
    def run_command(self):
        from django.core.management import call_command

        call_command("ensure_admin", stdout=StringIO())

    def login(self, phone="777777777", password="admin1"):  # pragma: allowlist secret
        return APIClient().post(
            "/api/auth/login/", {"phone": phone, "password": password}, format="json"
        )

    def test_it_waits_until_a_shop_exists(self):
        self.run_command()

        self.assertFalse(User.objects.filter(phone="+998777777777").exists())

    def test_the_admin_logs_in_as_owner_of_the_first_shop(self):
        first = Shop.objects.create(name="Birinchi", phone="+998900000001")
        Shop.objects.create(name="Ikkinchi", phone="+998900000002")

        self.run_command()

        response = self.login()
        self.assertEqual(response.status_code, 200)
        user = response.json()["data"]["user"]
        self.assertEqual(user["role"], "owner")
        self.assertEqual(user["shop_id"], str(first.id))

    def test_rerunning_restores_the_password_and_access(self):
        Shop.objects.create(name="Birinchi", phone="+998900000001")
        self.run_command()
        User.objects.filter(phone="+998777777777").update(password="x", is_active=False)

        self.run_command()

        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(User.objects.filter(phone="+998777777777").count(), 1)
