# favorites/models.py
from django.conf import settings
from django.db import models


class Favorite(models.Model):
    """
    관심 상품 (찜)
    - user + product 조합 unique
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "관심 상품"
        verbose_name_plural = "관심 상품"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_favorite_user_product"
            )
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} ❤️ {self.product.product_id}"
