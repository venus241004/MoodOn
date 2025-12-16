from django.urls import path

from . import views

app_name = "chat"

api_urlpatterns = [
    path(
        "sessions/",
        views.ChatSessionListCreateView.as_view(),
        name="chat-session-list-create",
    ),
    path(
        "sessions/<int:pk>/",
        views.ChatSessionDetailView.as_view(),
        name="chat-session-detail",
    ),
    path(
        "sessions/<int:session_id>/state/",
        views.SessionStateView.as_view(),
        name="chat-session-state",
    ),
    path(
        "messages/",
        views.ChatMessageSendView.as_view(),
        name="chat-message-send",
    ),
    path(
        "messages/<int:message_id>/rate/",
        views.ChatMessageRateView.as_view(),
        name="chat-message-rate",
    ),
    path(
        "sessions/<int:session_id>/reset/",
        views.ResetSessionView.as_view(),
        name="chat-session-reset",
    ),
]

web_urlpatterns = [
    path("", views.chat_page, name="chat-page"),
]

urlpatterns = api_urlpatterns
