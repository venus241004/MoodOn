# config/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from accounts import urls as accounts_urls
from chat import urls as chat_urls
from favorites import urls as favorites_urls

urlpatterns = [
    path("admin/", admin.site.urls),

    # API 엔드포인트
    path("api/accounts/", include("accounts.urls")),
    path("api/chat/", include("chat.urls")),
    path("api/products/", include("products.urls")),
    path("api/favorites/", include("favorites.urls")),

    # 웹 페이지 (템플릿 렌더)
    path("", include((accounts_urls.web_urlpatterns, "accounts-pages"), namespace="accounts-pages")),
    path("chat/", include((chat_urls.web_urlpatterns, "chat-pages"), namespace="chat-pages")),
    path("", include((favorites_urls.web_urlpatterns, "favorites-pages"), namespace="favorites-pages")),

    # Direct template routes for static pages
    path(
        "user/mypage/",
        TemplateView.as_view(template_name="user/mypage.html"),
        name="user-mypage",
    ),
    path(
        "favorites/preference/",
        TemplateView.as_view(template_name="user/preference.html"),
        name="user-preference",
    ),
    path(
        "favorites/reference-board/",
        TemplateView.as_view(template_name="user/reference_board.html"),
        name="user-reference-board",
    ),
]

# 개발 환경에서 media 파일 서빙
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
