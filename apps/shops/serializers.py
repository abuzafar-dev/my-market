"""Serializers for the authentication API."""

import re

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import Throttled

from apps.common.limits import MAX_PASSWORD

from .models import ShopSettings, User
from .security import PAIR_WINDOW, is_locked


class UserSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="shop.name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "phone", "full_name", "role", "shop_id", "shop_name"]


def normalize_phone(raw: str) -> str:
    """Accept the number however it's typed: "772874307", "998772874307",
    "+998 77 287 43 07" all become the stored "+998772874307" form. Anything
    that doesn't look like a Uzbek number is returned untouched."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    return raw.strip()


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    password = serializers.CharField(
        write_only=True, max_length=MAX_PASSWORD, style={"input_type": "password"}
    )

    def validate(self, attrs):
        request = self.context["request"]
        phone = normalize_phone(attrs["phone"])
        if is_locked(request, phone):
            raise Throttled(wait=PAIR_WINDOW)
        user = authenticate(request, username=phone, password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Telefon raqam yoki parol noto'g'ri.")
        attrs["user"] = user
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, max_length=MAX_PASSWORD)
    new_password = serializers.CharField(write_only=True, max_length=MAX_PASSWORD)

    def validate_old_password(self, value: str) -> str:
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Joriy parol noto'g'ri.")
        return value

    def validate_new_password(self, value: str) -> str:
        validate_password(value, user=self.context["request"].user)
        return value


class ShopSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopSettings
        fields = ["expiry_warn_days", "currency"]
