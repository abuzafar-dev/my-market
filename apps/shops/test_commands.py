"""Edge cases of the provisioning commands and the auth cookie endpoints."""

from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.shops.models import Shop, ShopSettings, User

OWNER_PHONE = "+998772874307"
STRONG = "Kuchli-Parol-2026"  # pragma: allowlist secret


def make_shop_with_owner():
    call_command(
        "create_shop",
        shop_name="Yangi",
        phone=OWNER_PHONE,
        full_name="Egasi",
        password=STRONG,
        stdout=StringIO(),
    )
    return User.objects.get(phone=OWNER_PHONE)


class CreateShopCommandTests(TestCase):
    def test_without_a_password_a_random_one_is_generated_and_shown_once(self):
        out = StringIO()

        call_command(
            "create_shop", shop_name="Yangi", phone=OWNER_PHONE, full_name="Egasi", stdout=out
        )

        user = User.objects.get(phone=OWNER_PHONE)
        password = out.getvalue().split("Vaqtinchalik parol: ")[1].splitlines()[0]
        self.assertGreaterEqual(len(password), 12)
        self.assertTrue(user.check_password(password))

    def test_the_owner_can_use_the_admin(self):
        self.assertTrue(make_shop_with_owner().is_staff)

    def test_a_taken_phone_is_refused_and_creates_no_shop(self):
        make_shop_with_owner()

        with self.assertRaises(CommandError):
            call_command(
                "create_shop",
                shop_name="Boshqa",
                phone=OWNER_PHONE,
                full_name="Boshqa",
                password=STRONG,
                stdout=StringIO(),
            )

        self.assertEqual(Shop.objects.count(), 1)


class AddUserCommandTests(TestCase):
    def add(self, **overrides):
        options = {
            "owner_phone": OWNER_PHONE,
            "phone": "+998907654321",
            "full_name": "Sotuvchi",
            "password": "Sotuvchi-Parol-77",  # pragma: allowlist secret
            "stdout": StringIO(),
        }
        call_command("add_user", **{**options, **overrides})

    def test_an_unknown_owner_is_refused(self):
        with self.assertRaises(CommandError):
            self.add()

        self.assertFalse(User.objects.filter(phone="+998907654321").exists())

    def test_a_seller_phone_cannot_stand_in_for_the_owner(self):
        owner = make_shop_with_owner()
        self.add()

        with self.assertRaises(CommandError):
            self.add(owner_phone="+998907654321", phone="+998909999999")

        self.assertEqual(User.objects.filter(shop=owner.shop).count(), 2)

    def test_a_taken_phone_is_refused(self):
        make_shop_with_owner()

        with self.assertRaises(CommandError):
            self.add(phone=OWNER_PHONE)

    def test_a_weak_password_is_refused(self):
        make_shop_with_owner()

        with self.assertRaises(CommandError):
            self.add(password="1")

        self.assertFalse(User.objects.filter(phone="+998907654321").exists())

    def test_a_second_owner_can_be_added(self):
        owner = make_shop_with_owner()

        self.add(role=User.Role.OWNER)

        second = User.objects.get(phone="+998907654321")
        self.assertEqual((second.role, second.shop_id), (User.Role.OWNER, owner.shop_id))


class AuthCookieTests(TestCase):
    def setUp(self):
        shop = Shop.objects.create(name="Do'kon", phone="+998900000000")
        ShopSettings.objects.create(shop=shop)
        self.user = User.objects.create_user(
            phone="+998901112233",
            password="pass1234",  # pragma: allowlist secret
            shop=shop,
            full_name="Egasi",
        )

    def client_with_cookie(self, token):
        client = APIClient()
        client.cookies["refresh_token"] = token
        return client

    def test_a_garbage_cookie_is_401(self):
        response = self.client_with_cookie("not-a-jwt").post(
            "/api/auth/refresh/", {}, format="json"
        )

        self.assertEqual(response.status_code, 401)

    def test_a_deleted_user_cannot_refresh(self):
        token = str(RefreshToken.for_user(self.user))
        self.user.delete()

        response = self.client_with_cookie(token).post("/api/auth/refresh/", {}, format="json")

        self.assertEqual(response.status_code, 401)

    def test_logout_revokes_the_refresh_cookie(self):
        token = str(RefreshToken.for_user(self.user))
        client = self.client_with_cookie(token)
        client.force_authenticate(self.user)

        self.assertEqual(client.post("/api/auth/logout/").status_code, 205)

        self.assertEqual(
            self.client_with_cookie(token)
            .post("/api/auth/refresh/", {}, format="json")
            .status_code,
            401,
        )

    def test_logout_without_a_cookie_still_succeeds(self):
        client = APIClient()
        client.force_authenticate(self.user)

        self.assertEqual(client.post("/api/auth/logout/").status_code, 205)

    def test_logout_needs_a_signed_in_user(self):
        self.assertEqual(APIClient().post("/api/auth/logout/").status_code, 401)
