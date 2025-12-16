# favorites/views.py

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Favorite
from .serializers import FavoriteSerializer


class FavoriteListCreateView(APIView):
    """
    관심상품 목록 조회 / 등록
    GET    /api/favorites/
    POST   /api/favorites/ { "product_id": "guud_97008" }
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        favorites = Favorite.objects.filter(user=request.user).select_related("product")
        serializer = FavoriteSerializer(favorites, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = FavoriteSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        favorite = serializer.save()
        out = FavoriteSerializer(favorite).data
        return Response(out, status=status.HTTP_201_CREATED)


class FavoriteDeleteView(APIView):
    """
    관심상품 삭제
    DELETE /api/favorites/<id>/
    """

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk: int):
        favorite = get_object_or_404(Favorite, pk=pk, user=request.user)
        favorite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# -------------------------
# Template pages
# -------------------------


@login_required
def mypage(request):
    return render(request, "user/mypage.html")


@login_required
def preference_page(request):
    return render(request, "user/preference.html")


@login_required
def reference_board_page(request):
    return render(request, "user/reference_board.html")
