# chat/services.py
"""
모델 서버(FastAPI)와 통신하는 서비스 레이어 모듈.

- Django에서 텍스트/이미지 입력을 받아 model_server.py로 전달한다.
- 응답에서 챗봇 답변, 추천 상품, 세션 상태를 정리해서 Chat 앱에서 쓰기 좋은 형태로 반환한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import requests
from django.conf import settings

# settings.py에 MODEL_SERVER_URL이 설정되어 있으면 그 값을 사용하고,
# 없으면 기본값으로 로컬 8001 포트를 사용한다.
# (Django runserver가 8000을 쓰니까 겹치지 않게 8001로 두는 걸 추천)
MODEL_SERVER_URL: str = getattr(
    settings,
    "MODEL_SERVER_URL",
    "http://127.0.0.1:8001",
)

# 타임아웃 기본값(초)
TEXT_TIMEOUT: int = getattr(settings, "MODEL_SERVER_TEXT_TIMEOUT", 120)
IMAGE_TIMEOUT: int = getattr(settings, "MODEL_SERVER_IMAGE_TIMEOUT", 300)
RESET_TIMEOUT: int = getattr(settings, "MODEL_SERVER_RESET_TIMEOUT", 30)


def _build_url(path: str) -> str:
    """기본 URL과 엔드포인트 path를 합쳐서 최종 URL을 만든다."""
    base = MODEL_SERVER_URL.rstrip("/")
    path = path.lstrip("/")
    return f"{base}/{path}"


def parse_model_server_response(data: Dict[str, Any], is_image: bool = False) -> Dict[str, Any]:
    """
    모델 서버 응답을 공통 포맷으로 정리한다.

    - 이미지 요청도 텍스트 응답(reply)을 포함할 수 있으므로 우선순위:
      1) reply (텍스트 대화 결과)
      2) message (VLM 안내 메시지)
    """
    if is_image:
        assistant_text = data.get("reply") or data.get("message") or ""
    else:
        assistant_text = data.get("reply") or ""

    recommended_products: list = data.get("products") or []
    updated_session_state: dict = data.get("session_state") or {}
    mode = data.get("mode")

    if mode:
        updated_session_state = updated_session_state or {}
        updated_session_state.setdefault("mode", mode)

    return {
        "assistant_text": assistant_text,
        "recommended_products": recommended_products,
        "updated_session_state": updated_session_state,
        "_raw": data,
    }


def call_model_server_text(
    session_id: Optional[int],
    user_text: str,
    state_payload: Optional[Dict[str, Any]] = None,
    more_like_this: bool = False,
) -> Dict[str, Any]:
    """
    Django → FastAPI 텍스트 대화 호출.

    model_server.py의 TextChatRequest 스펙은:
    { "session_id": Optional[str], "message": str }

    여기서는 더 많은 정보를 보내지만, Pydantic 기본 설정상
    extra 필드는 무시되므로 문제가 되지 않는다.
    """
    url = _build_url("/chat/text")

    payload: Dict[str, Any] = {
        "session_id": str(session_id) if session_id is not None else None,
        "message": user_text,
        # 아래 두 필드는 현재 model_server에서는 사용하지 않지만,
        # 나중에 확장할 때를 위해 남겨 둔다.
        "more_like_this": more_like_this,
        "state": state_payload or {},
    }

    resp = requests.post(url, json=payload, timeout=TEXT_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return parse_model_server_response(data, is_image=False)


def call_model_server_image(
    session_id: Optional[int],
    image_path: str,
    state_payload: Optional[Dict[str, Any]] = None,
    is_want: bool = False,
    user_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Django → FastAPI 이미지(VLM) 호출.

    - image_path: Django 쪽에서 저장된 실제 파일 경로
    - is_want: 사용자가 '원하는 분위기 / 레퍼런스 이미지'인지 여부
    """
    url = _build_url("/chat/image")

    img_path = Path(image_path)
    if not img_path.is_file():
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")

    data = {
        "session_id": str(session_id) if session_id is not None else "",
        "is_want": "true" if is_want else "false",
        # 이미지와 함께 텍스트도 전달해 한 번에 처리
        "message": user_text or "",
        "text": user_text or "",
        # state_payload도 확장용으로 함께 보낼 수 있다.
        "state": state_payload or {},
    }

    with img_path.open("rb") as f:
        files = {"file": (img_path.name, f)}
        resp = requests.post(url, data=data, files=files, timeout=IMAGE_TIMEOUT)

    resp.raise_for_status()
    data = resp.json()
    return parse_model_server_response(data, is_image=True)


def route_input_and_call_model_server(
    *,
    session_id: int,
    user_text: str = "",
    image_path: Optional[str] = None,
    state_payload: Optional[Dict[str, Any]] = None,
    more_like_this: bool = False,
    is_want_image: bool = False,
) -> Dict[str, Any]:
    """
    ChatMessageSendView에서 사용하는 공통 진입점.

    - image_path가 있으면 이미지(방/레퍼런스) 기반 호출
    - 없으면 텍스트 대화 호출
    """
    if image_path:
        return call_model_server_image(
            session_id=session_id,
            image_path=image_path,
            state_payload=state_payload,
            is_want=is_want_image,
            user_text=user_text,
        )

    return call_model_server_text(
        session_id=session_id,
        user_text=user_text,
        state_payload=state_payload,
        more_like_this=more_like_this,
    )


def call_model_server_reset(session_id: int) -> Dict[str, Any]:
    """
    세션 전체 리셋 요청 (/session/reset).
    """
    url = _build_url("/session/reset")
    payload = {"session_id": str(session_id)}

    resp = requests.post(url, json=payload, timeout=RESET_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def update_session_state(session, updated_state: Dict[str, Any]) -> None:
    """
    모델 서버에서 내려준 updated_state 딕셔너리를 SessionState에 upsert.

    - 키 이름이 SessionState의 필드 이름과 일치하는 것만 반영한다.
    - 변경 사항이 있을 때만 save()를 호출한다.
    """
    if not isinstance(updated_state, dict) or not updated_state:
        return

    from .models import SessionState  # 순환 참조 방지를 위해 함수 안에서 import

    state, _ = SessionState.objects.get_or_create(session=session)
    changed = False

    for key, value in updated_state.items():
        if hasattr(state, key):
            if value is not None:
                setattr(state, key, value)
                changed = True

    if changed:
        state.save()
