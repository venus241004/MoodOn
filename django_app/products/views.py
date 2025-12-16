# products/views.py
from rest_framework import generics, permissions

from .models import Product
from .serializers import ProductSerializer


class ProductListView(generics.ListAPIView):
    """
    상품 목록 조회

    GET /api/products/
    - category_id: 카테고리 필터
    - mood_category: 무드 대분류 필터
    - mood_keyword: 무드 키워드 포함 필터 (단일 또는 콤마구분 다중)
    - product_ids: 콤마구분 product_id 목록 (챗봇 추천 조회용)
    """

    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Product.objects.all().order_by("product_id")

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        category_id = params.get("category_id")
        mood_category = params.get("mood_category")
        mood_keyword = params.get("mood_keyword")
        product_ids = params.get("product_ids")

        if category_id:
            qs = qs.filter(category_id=category_id)

        if mood_category:
            qs = qs.filter(mood_category=mood_category)

        if mood_keyword:
            keywords = [kw.strip() for kw in mood_keyword.split(",") if kw.strip()]
            for kw in keywords:
                qs = qs.filter(mood_keywords__contains=[kw])

        if product_ids:
            pid_list = [p.strip() for p in product_ids.split(",") if p.strip()]
            if pid_list:
                qs = qs.filter(product_id__in=pid_list)

        return qs


class ProductDetailView(generics.RetrieveAPIView):
    """
    상품 상세 조회
    GET /api/products/<id>/
    """

    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Product.objects.all()
