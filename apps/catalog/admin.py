from django.contrib import admin

from .models import Batch, Category, Product, WriteOff


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "shop")
    list_filter = ("shop",)
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "shop",
        "category",
        "unit",
        "markup_pct",
        "min_stock",
        "stock",
        "is_active",
    )
    list_filter = ("category", "is_active", "shop")
    search_fields = ("name", "barcode")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Qoldiq")
    def stock(self, obj: Product):
        return obj.stock


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "shop",
        "qty_initial",
        "qty_remaining",
        "cost_price",
        "sale_price",
        "received_at",
        "expires_at",
    )
    list_filter = ("shop",)
    search_fields = ("product__name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(WriteOff)
class WriteOffAdmin(admin.ModelAdmin):
    list_display = ("batch", "shop", "qty", "cost_total", "reason", "created_by")
    list_filter = ("reason", "shop")
    search_fields = ("batch__product__name",)
    readonly_fields = ("created_at", "updated_at")
