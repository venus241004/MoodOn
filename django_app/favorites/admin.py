# favorites/admin.py

from django.contrib import admin

from .models import Favorite


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_email",
        "product_id",
        "product_brand",
        "created_at",
    )
    search_fields = (
        "user__email",
        "product__product_id",
        "product__brand_name",
        "product__product_name",
    )
    list_filter = (
        "product__brand_name",
        "product__category_id",
        "product__source_site",
        "created_at",
    )
    ordering = ("-created_at",)

    def user_email(self, obj):
        return obj.user.email

    def product_id(self, obj):
        return obj.product.product_id

    def product_brand(self, obj):
        return obj.product.brand_name

