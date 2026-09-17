from django.contrib import admin

from .models import Shop, ShopSettings, User


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "address", "created_at")
    search_fields = ("name", "phone")
    readonly_fields = ("created_at", "updated_at")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone", "full_name", "shop", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "shop")
    search_fields = ("phone", "full_name")
    readonly_fields = ("password", "last_login", "created_at", "updated_at")


@admin.register(ShopSettings)
class ShopSettingsAdmin(admin.ModelAdmin):
    list_display = ("shop", "expiry_warn_days", "currency", "updated_at")
    readonly_fields = ("updated_at",)
