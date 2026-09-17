from django.contrib import admin
from django.http import HttpRequest

from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "shop",
        "customer",
        "total",
        "payment_type",
        "status",
        "sold_by",
        "sold_at",
    )
    list_filter = ("status", "payment_type", "shop")
    search_fields = ("client_id",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [SaleItemInline]

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False
