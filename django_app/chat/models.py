# chat/models.py

from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    """사용자 1명과 연결된 하나의 채팅 세션."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    title = models.CharField(max_length=255)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.title}"

    @property
    def last_message_preview(self) -> str:
        """가장 최근 메시지의 앞부분만 반환."""
        latest = self.messages.order_by("-created_at").first()
        if not latest or not latest.text:
            return ""
        return (latest.text or "")[:80]

    @property
    def last_message_at(self):
        latest = self.messages.order_by("-created_at").first()
        return latest.created_at if latest else None


class SessionState(models.Model):
    """
    세션 상태 (사이드바에 보여줄 내용)
    - 카테고리/공간/예산
    - 타겟/현재 무드
    - 스타일/색상/재질/조명 키워드
    - VLM/대표 이미지 설명 등
    """

    session = models.OneToOneField(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="state",
    )

    # 기본 상태
    category = models.CharField(max_length=100, null=True, blank=True)
    space = models.CharField(max_length=100, null=True, blank=True)
    price_min = models.IntegerField(null=True, blank=True)
    price_max = models.IntegerField(null=True, blank=True)
    mode = models.CharField(max_length=30, null=True, blank=True)

    # 무드·스타일 관련 (리스트)
    target_moods = models.JSONField(default=list, blank=True)
    current_moods = models.JSONField(default=list, blank=True)
    style_keywords = models.JSONField(default=list, blank=True)
    color_keywords = models.JSONField(default=list, blank=True)
    material_keywords = models.JSONField(default=list, blank=True)
    lighting_keywords = models.JSONField(default=list, blank=True)

    # 이미지 기반 설명
    vlm_description = models.TextField(null=True, blank=True)
    target_image_description = models.TextField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"State of {self.session}"


class ChatMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"

    ROLE_CHOICES = [
        (ROLE_USER, "사용자"),
        (ROLE_ASSISTANT, "챗봇"),
    ]

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    text = models.TextField(null=True, blank=True)
    image = models.ImageField(
        upload_to="chat_images/",
        null=True,
        blank=True,
    )
    IMAGE_TYPE_CHOICES = [
        ("current", "현재 방 사진"),
        ("reference", "레퍼런스 사진"),
    ]
    image_type = models.CharField(
        max_length=20,
        choices=IMAGE_TYPE_CHOICES,
        null=True,
        blank=True,
    )

    # 모델 서버가 추천한 상품들 (product_id, 이름, 이미지 URL, 링크 등)
    recommended_products = models.JSONField(default=list, blank=True)

    # 사용자가 남긴 만족도 (1~5점)
    satisfaction = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        short = (self.text or "").replace("\n", " ")
        return f"{self.role}: {short[:30]}"

