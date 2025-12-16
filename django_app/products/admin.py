# products/admin.py
from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "product_id",
        "product_name",
        "brand_name",
        "category_id",
        "mood_category",
        "price",
        "source_site",
        "created_at",
    )
    list_filter = ("category_id", "brand_name", "source_site", "mood_category")
    search_fields = ("product_id", "product_name", "brand_name", "category_id")
    ordering = ("product_id",)
