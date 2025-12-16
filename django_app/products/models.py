# products/models.py
from django.db import models


class Product(models.Model):
    """
    상품 마스터 (RAG JSON 스펙 기반)
    - review 배열은 현재 저장하지 않는다.
    """

    product_id = models.CharField(max_length=50, unique=True)
    category_id = models.CharField(max_length=50, db_index=True)
    brand_name = models.CharField(max_length=100, blank=True)
    product_name = models.CharField(max_length=255)

    price = models.IntegerField()  # JSON 문자열 가격을 정수로 저장

    link_url = models.URLField()
    image_url = models.URLField()
    s3_url = models.URLField(blank=True)

    description = models.TextField(blank=True)

    mood_category = models.CharField(max_length=50, blank=True)
    mood_keywords = models.JSONField(default=list, blank=True)
    raw_mood_keywords = models.TextField(blank=True)
    unknown_mood_keywords = models.TextField(blank=True)

    source_site = models.CharField(max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product_id"]
        indexes = [
            models.Index(fields=["category_id"]),
            models.Index(fields=["mood_category"]),
            models.Index(fields=["source_site"]),
        ]

    def __str__(self) -> str:
        return f"{self.product_name} ({self.brand_name})" if self.brand_name else self.product_name
