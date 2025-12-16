# chat/serializers.py

import re

from django.utils import timezone
from rest_framework import serializers

from .models import ChatMessage, ChatSession, SessionState


class ChatMessageSerializer(serializers.ModelSerializer):
    """
    히스토리/대화창에 내려줄 메시지 직렬화기.
    - 이미지가 있으면 image_url 로 절대 경로 제공
    - recommended_products 는 그대로 JSON (리스트) 형태로 내려줌
    """

    image_url = serializers.SerializerMethodField()

    session = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "session",
            "role",
            "text",
            "image_url",
            "image_type",
            "created_at",
            "recommended_products",
            "satisfaction",
        ]

    def get_image_url(self, obj: ChatMessage):
        request = self.context.get("request")
        if obj.image and request is not None:
            return request.build_absolute_uri(obj.image.url)
        if obj.image:
            return obj.image.url
        return None


class ChatMessageCreateSerializer(serializers.ModelSerializer):
    """
    사용자가 보낸 메시지를 생성할 때 사용하는 Serializer.

    - text (옵션, 이미지 없을 때는 필수)
    - image (옵션)
    - more_like_this (옵션, bool) : '다른 상품 원해요' 플래그
    """

    more_like_this = serializers.BooleanField(default=False)

    image_type = serializers.ChoiceField(
        choices=[("current", "현재 방 사진"), ("reference", "레퍼런스 사진")],
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ChatMessage
        fields = ["text", "image", "more_like_this", "image_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].required = False

    def validate(self, attrs):
        text = (attrs.get("text") or "").strip()
        has_image = self.context.get("has_image", False)

        if not text and not has_image:
            raise serializers.ValidationError("텍스트 또는 이미지를 입력해야 합니다.")

        if text and len(text) > 200:
            raise serializers.ValidationError({"text": "질문은 200자 이하로 입력해 주세요."})

        # 언어/문자 종류 제한을 두지 않는다 (사용자 입력 유연성 확보)
        return attrs


class SessionStateSerializer(serializers.ModelSerializer):
    """
    사이드바에 보여줄 세션 상태 직렬화기.
    """

    class Meta:
        model = SessionState
        fields = [
            "id",
            "category",
            "space",
            "price_min",
            "price_max",
            "mode",
            "target_moods",
            "current_moods",
            "style_keywords",
            "color_keywords",
            "material_keywords",
            "lighting_keywords",
            "vlm_description",
            "target_image_description",
        ]


class ChatSessionSerializer(serializers.ModelSerializer):
    last_message_preview = serializers.SerializerMethodField()
    last_message_at = serializers.DateTimeField(
        read_only=True, allow_null=True
    )

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "title",
            "created_at",
            "updated_at",
            "last_message_preview",
            "last_message_at",
        ]

    def get_last_message_preview(self, obj: ChatSession) -> str:
        return obj.last_message_preview


class ChatSessionDetailSerializer(ChatSessionSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)
    state = SessionStateSerializer(read_only=True)

    class Meta(ChatSessionSerializer.Meta):
        fields = ChatSessionSerializer.Meta.fields + ["messages", "state"]


class ChatSessionCreateSerializer(serializers.ModelSerializer):
    """
    새 채팅 세션 생성.
    - 클라이언트에서 받는 필드는 없고,
    - 오늘 날짜 기준으로 1, 2, 3... 자동 타이틀 생성.
    """

    class Meta:
        model = ChatSession
        fields = []  # 클라이언트에서 받는 필드 없음

    def create(self, validated_data):
        user = self.context["request"].user
        today = timezone.localdate()
        qs = ChatSession.objects.filter(user=user, created_at__date=today)
        idx = qs.count() + 1
        title = f"{today.isoformat()}-{idx}"
        return ChatSession.objects.create(user=user, title=title)


class SatisfactionSerializer(serializers.Serializer):
    """
    추천 결과에 대한 만족도(1~5) 입력용.
    """

    satisfaction = serializers.IntegerField(min_value=1, max_value=5)
