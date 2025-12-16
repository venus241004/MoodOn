# chat/views.py

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ChatMessage, ChatSession, SessionState
from .serializers import (
    ChatMessageCreateSerializer,
    ChatMessageSerializer,
    ChatSessionCreateSerializer,
    ChatSessionDetailSerializer,
    ChatSessionSerializer,
    SatisfactionSerializer,
    SessionStateSerializer,
)
from .services import (
    call_model_server_reset,
    route_input_and_call_model_server,
    update_session_state,
)


class ChatSessionListCreateView(generics.ListCreateAPIView):
    """
    채팅 세션 목록 조회 / 새 세션 생성

    GET  /api/chat/sessions/   → 히스토리 목록 (REQ-CHT-005)
    POST /api/chat/sessions/   → 새 채팅 생성   (REQ-CHT-002)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatSession.objects.filter(
            user=self.request.user,
            is_deleted=False,
        ).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ChatSessionCreateSerializer
        return ChatSessionSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        SessionState.objects.get_or_create(session=instance)
        out = ChatSessionSerializer(instance).data
        headers = self.get_success_headers(serializer.data)
        return Response(out, status=status.HTTP_201_CREATED, headers=headers)


class ChatSessionDetailView(generics.RetrieveDestroyAPIView):
    """
    단일 세션 상세 조회 / 삭제(soft delete)

    GET    /api/chat/sessions/<id>/   → 세션 + 메시지 + 상태 (REQ-CHT-003, 004, 006)
    DELETE /api/chat/sessions/<id>/   → soft delete        (REQ-CHT-007)
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatSessionDetailSerializer

    def get_queryset(self):
        return (
            ChatSession.objects.filter(
                user=self.request.user,
                is_deleted=False,
            )
            .prefetch_related("messages", "state")
        )

    def get_object(self):
        obj = super().get_object()
        # state가 없으면 자동 생성해서 직렬화 시 오류 방지
        SessionState.objects.get_or_create(session=obj)
        return obj

    def perform_destroy(self, instance: ChatSession):
        # 모델 서버 세션도 함께 리셋 시도 (실패해도 무시)
        try:
            call_model_server_reset(instance.id)
        except Exception:
            pass
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])


class SessionStateView(APIView):
    """
    세션 상태 조회 / 수정 / 삭제

    GET    /api/chat/sessions/<session_id>/state/
    PATCH  /api/chat/sessions/<session_id>/state/
    DELETE /api/chat/sessions/<session_id>/state/
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, session_id: int) -> SessionState:
        session = get_object_or_404(
            ChatSession,
            id=session_id,
            user=self.request.user,
            is_deleted=False,
        )
        state, _ = SessionState.objects.get_or_create(session=session)
        return state

    def get(self, request, session_id: int):
        state = self.get_object(session_id)
        serializer = SessionStateSerializer(state)
        return Response(serializer.data)

    def patch(self, request, session_id: int):
        state = self.get_object(session_id)
        serializer = SessionStateSerializer(state, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, session_id: int):
        state = self.get_object(session_id)
        state.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatMessageSendView(APIView):
    """
    메시지 전송 (텍스트 / 이미지)

    POST /api/chat/messages/
    body: { session_id, text?, image?, more_like_this? }

    요구사항 (REQ-CHT-001):
    - 로그인 필수
    - 질문은 한국어 + 200자 제한
    - 이미지 최대 1장, 10MB 제한
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def post(self, request):
        # 1) session_id 검증
        session_id = request.data.get("session_id")
        if not session_id:
            return Response(
                {"detail": "session_id가 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            session_id = int(session_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "session_id가 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2) 세션 및 상태 조회/생성
        session = get_object_or_404(
            ChatSession,
            id=session_id,
            user=request.user,
            is_deleted=False,
        )
        state, _ = SessionState.objects.get_or_create(session=session)

        # 3) 이미지 용량 제한 체크 (10MB)
        image_file = request.FILES.get("image")
        if image_file and image_file.size > 10 * 1024 * 1024:
            return Response(
                {"detail": "이미지 용량은 10MB 이하여야 합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4) 입력 검증 (한글 / 200자 / 텍스트 or 이미지)
        has_image = bool(image_file)
        serializer = ChatMessageCreateSerializer(
            data=request.data,
            context={"request": request, "has_image": has_image},
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        text = (validated_data.get("text") or "").strip()
        image = validated_data.get("image")
        more_like_this = validated_data.get("more_like_this", False)
        image_type = validated_data.get("image_type") or None

        # 5) 사용자 메시지 저장
        user_msg = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_USER,
            text=text,
            image=image,
            image_type=image_type,
        )

        # 6) 현재 세션 상태를 payload로 준비
        state_payload = SessionStateSerializer(state).data

        # 7) 모델 서버 호출
        try:
            image_path = None
            if image:
                # ImageField는 save() 후 파일 경로가 확정되므로 refresh_from_db
                user_msg.refresh_from_db()
                image_path = user_msg.image.path

            result = route_input_and_call_model_server(
                session_id=session.id,
                user_text=text,
                image_path=image_path,
                state_payload=state_payload,
                more_like_this=more_like_this,
                is_want_image=(image_type == "reference"),
            )
        except Exception:
            # 모델 서버 오류 시, 기본 사과 메시지 반환
            assistant_msg = ChatMessage.objects.create(
                session=session,
                role=ChatMessage.ROLE_ASSISTANT,
                text="죄송합니다. 추천 생성 중 오류가 발생했습니다. 나중에 다시 시도해 주세요.",
            )
            res_serializer = ChatMessageSerializer(
                assistant_msg,
                context={"request": request},
            )
            return Response(
                {
                    "assistant_message": res_serializer.data,
                    "session_state": SessionStateSerializer(state).data,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 8) 모델 서버 응답 처리
        assistant_text = result.get("assistant_text", "")
        recommended_products = result.get("recommended_products") or []
        updated_state = result.get("updated_session_state") or {}

        assistant_msg = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.ROLE_ASSISTANT,
            text=assistant_text,
            recommended_products=recommended_products,
        )

        # 9) 세션 상태 업데이트 (필드 이름이 맞는 것만 upsert)
        update_session_state(session, updated_state)

        # 10) 세션 갱신 시간 업데이트
        session.updated_at = timezone.now()
        session.save(update_fields=["updated_at"])

        res_serializer = ChatMessageSerializer(
            assistant_msg,
            context={"request": request},
        )
        return Response(
            {
                "assistant_message": res_serializer.data,
            "session_state": SessionStateSerializer(session.state).data
                if hasattr(session, "state")
                else {},
            },
            status=status.HTTP_200_OK,
        )


class ChatMessageRateView(APIView):
    """
    추천 결과에 대한 만족도(1~5점) 입력

    POST /api/chat/messages/<message_id>/rate/
    body: { "satisfaction": 1~5 }
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, message_id: int):
        msg = get_object_or_404(
            ChatMessage,
            id=message_id,
            session__user=request.user,
            session__is_deleted=False,
            role=ChatMessage.ROLE_ASSISTANT,
        )

        serializer = SatisfactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        score = serializer.validated_data["satisfaction"]

        msg.satisfaction = score
        msg.save(update_fields=["satisfaction"])

        return Response(
            {"detail": "만족도가 저장되었습니다."},
            status=status.HTTP_200_OK,
        )


class ResetSessionView(APIView):
    """
    세션 전체 리셋 (상태 + 메시지 삭제, 모델 서버도 리셋 요청)

    POST /api/chat/sessions/<session_id>/reset/
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id: int):
        session = get_object_or_404(
            ChatSession,
            id=session_id,
            user=request.user,
            is_deleted=False,
        )

        # 1) 모델 서버 세션 리셋 시도 (실패해도 치명적이지 않으므로 무시)
        try:
            call_model_server_reset(session.id)
        except Exception:
            pass

        # 2) Django 쪽 상태만 초기화 (메시지는 유지)
        state, _ = SessionState.objects.get_or_create(session=session)
        state.category = None
        state.space = None
        state.price_min = None
        state.price_max = None
        state.mode = None
        state.target_moods = []
        state.current_moods = []
        state.style_keywords = []
        state.color_keywords = []
        state.material_keywords = []
        state.lighting_keywords = []
        state.vlm_description = None
        state.target_image_description = None
        state.save()

        session.updated_at = timezone.now()
        session.save(update_fields=["updated_at"])

        return Response(
            {
                "detail": "세션 상태가 초기화되었습니다.",
                "session_state": SessionStateSerializer(state).data,
            },
            status=status.HTTP_200_OK,
        )


# -------------------------
# Template page
# -------------------------


@login_required
def chat_page(request):
    return render(request, "chat/chat.html")
