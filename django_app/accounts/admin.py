# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import EmailVerification, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("개인 정보", {"fields": ("first_name", "last_name", "birth_date", "gender", "mbti")}),
        (
            "권한",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("중요 일자", {"fields": ("last_login", "date_joined")}),
        ("로그인 잠금", {"fields": ("failed_login_count", "lock_until")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )
    list_display = ("email", "is_staff", "is_active")
    search_fields = ("email",)
    ordering = ("email",)


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("email", "purpose", "code", "created_at", "expires_at", "is_used", "send_count", "lock_until")
    list_filter = ("purpose", "is_used")
    search_fields = ("email", "code")

