# chat/admin.py

from django.contrib import admin

from .models import ChatMessage, ChatSession, SessionState


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "created_at", "updated_at", "is_deleted")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("title", "user__email")


@admin.register(SessionState)
class SessionStateAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "category", "space")
    search_fields = ("session__title", "category", "space")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "short_text", "created_at", "satisfaction")
    list_filter = ("role", "created_at")
    search_fields = ("text", "session__title", "session__user__email")

    def short_text(self, obj):
        return (obj.text or "")[:30]

