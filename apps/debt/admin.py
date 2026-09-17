from django.contrib import admin
from django.http import HttpRequest

from .models import Customer, DebtEntry


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "shop", "debt_balance", "is_active")
    list_filter = ("is_active", "shop")
    search_fields = ("full_name", "phone")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DebtEntry)
class DebtEntryAdmin(admin.ModelAdmin):
    list_display = ("customer", "shop", "sale", "amount", "entry_type", "created_by", "created_at")
    list_filter = ("entry_type", "shop")
    search_fields = ("customer__full_name",)
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False
