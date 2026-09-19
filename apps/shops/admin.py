from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Shop, ShopSettings, User


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "address", "created_at")
    search_fields = ("name", "phone")
    readonly_fields = ("created_at", "updated_at")


class ShopUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("phone", "full_name", "shop", "role")


class ShopUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = ShopUserCreationForm
    form = ShopUserChangeForm
    model = User

    list_display = ("phone", "full_name", "shop", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "shop")
    search_fields = ("phone", "full_name")
    ordering = ("phone",)
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = ("last_login", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Shaxsiy ma'lumot", {"fields": ("full_name", "shop", "role")}),
        (
            "Ruxsatlar",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Sanalar", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone",
                    "full_name",
                    "shop",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(ShopSettings)
class ShopSettingsAdmin(admin.ModelAdmin):
    list_display = ("shop", "expiry_warn_days", "currency", "updated_at")
    readonly_fields = ("updated_at",)
