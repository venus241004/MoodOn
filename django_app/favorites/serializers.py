# favorites/serializers.py

from rest_framework import serializers

from products.models import Product
from .models import Favorite


class ProductNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "product_id",
            "brand_name",
            "product_name",
            "price",
            "link_url",
            "image_url",
            "s3_url",
            "mood_category",
            "mood_keywords",
        ]


class FavoriteSerializer(serializers.ModelSerializer):
    product = ProductNestedSerializer(read_only=True)
    product_id = serializers.CharField(write_only=True)

    class Meta:
        model = Favorite
        fields = ["id", "product", "product_id", "created_at"]
        read_only_fields = ["id", "product", "created_at"]

    def validate_product_id(self, value: str):
        try:
            product = Product.objects.get(product_id=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError("존재하지 않는 상품입니다.")
        self.context["product_instance"] = product
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        product = self.context["product_instance"]
        favorite, _ = Favorite.objects.get_or_create(user=user, product=product)
        return favorite

