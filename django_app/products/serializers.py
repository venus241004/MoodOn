# products/serializers.py
from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "product_id",
            "category_id",
            "brand_name",
            "product_name",
            "price",
            "link_url",
            "image_url",
            "s3_url",
            "description",
            "mood_category",
            "mood_keywords",
            "raw_mood_keywords",
            "unknown_mood_keywords",
            "source_site",
            "created_at",
            "updated_at",
        ]
