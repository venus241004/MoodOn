# favorites/urls.py

from django.urls import path

from . import views

app_name = "favorites"

api_urlpatterns = [
    path("", views.FavoriteListCreateView.as_view(), name="favorite-list-create"),
    path("<int:pk>/", views.FavoriteDeleteView.as_view(), name="favorite-delete"),
]

web_urlpatterns = [
    path("mypage/", views.mypage, name="mypage"),
    path("preference/", views.preference_page, name="preference-page"),
    path("reference-board/", views.reference_board_page, name="reference-board-page"),
]

urlpatterns = api_urlpatterns

