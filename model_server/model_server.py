# model_server.py
"""
FastAPI 기반 모델 서버

- 기존 Final_Project의 LLM/VLM/RAG/상태머신 로직을 HTTP API로 감싼다.
- main.py, llm_core.py, input_vlm.py, rag_retriever.py, product_filter.py 등을 그대로 재사용.

엔드포인트
---------

1) POST /chat/text
   - 텍스트 기반 대화/추천
   - 요청: { "session_id": "optional", "message": "사용자 입력" }
   - 응답: {
       "session_id": "...",
       "reply": "LLM 응답",
       "mode": "SMALLTALK|SURVEY|RECOMMEND",
       "llm_latency": 1.23,
       "debug_state_summary": "선택적으로 상태 요약"
     }

2) POST /chat/image
   - 방/레퍼런스 이미지 업로드 → VLM 분석 + 상태 업데이트
   - form-data:
       - session_id: (optional) 문자열
       - is_want: (optional, default=false) "true"/"false"
       - file: 이미지 파일
   - 응답: {
       "session_id": "...",
       "message": "VLM 결과/안내 메시지",
       "debug_state_summary": "상태 요약 (텍스트)"
     }

3) POST /session/reset
   - 세션 전체 리셋 (상태 + 히스토리 삭제)
   - 요청: { "session_id": "..." }
   - 응답: { "session_id": "...", "status": "reset" }

로컬에서 테스트
---------------
가상환경(final_project)에서:

    uvicorn model_server:app --reload --host 0.0.0.0 --port 8000

"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading

# 기존 모듈들에서 필요한 것들 가져오기
from llm_core import parse_user_query  # 카테고리/무드/예산/공간 파싱

# main.py에는 상태머신과 모드별 핸들러가 들어있다고 가정
from main import (
    ChatState,
    ChatMode,
    decide_mode,
    handle_smalltalk,
    handle_survey,
    handle_recommend,
    render_summary,
    handle_image_command,
)

# ------------------------------------------------------------
# FastAPI 앱 및 CORS 설정
# ------------------------------------------------------------

app = FastAPI(
    title="Mood-based Interior Recommendation Model Server",
    description="Qwen2.5-14B-Korean + VLM + Chroma RAG 기반 모델 서버",
    version="0.1.0",
)

# 필요하면 개발 단계에서 CORS 완전 개방 (나중에 도메인 제한 가능)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# 세션 상태/히스토리 저장소 (간단한 in-memory 구현)
# ------------------------------------------------------------

_session_lock = threading.Lock()
_sessions: Dict[str, ChatState] = {}
_histories: Dict[str, List[Tuple[str, str]]] = {}

# 업로드 이미지 임시 저장 디렉토리
BASE_DIR = Path(__file__).resolve().parent
TMP_DIR = BASE_DIR / "tmp_uploads"
TMP_DIR.mkdir(parents=True, exist_ok=True)


def _get_or_create_session(
    session_id: Optional[str],
) -> Tuple[str, ChatState, List[Tuple[str, str]]]:
    """
    세션 ID가 없으면 새로 만들고, 있으면 기존 상태/히스토리를 가져온다.
    """
    with _session_lock:
        if not session_id or session_id not in _sessions:
            new_id = session_id or str(uuid.uuid4())
            _sessions[new_id] = ChatState()
            _histories[new_id] = []
            return new_id, _sessions[new_id], _histories[new_id]

        return session_id, _sessions[session_id], _histories[session_id]


def _reset_session(session_id: str) -> None:
    """
    세션 상태와 히스토리를 완전히 삭제.
    """
    with _session_lock:
        _sessions.pop(session_id, None)
        _histories.pop(session_id, None)


def _state_to_dict(state: ChatState) -> Dict[str, Any]:
    """
    ChatState를 프론트/웹서버가 이해할 수 있는 dict로 직렬화.
    """
    return {
        "category": state.category,
        "space": state.space,
        "price_min": state.price_min,
        "price_max": state.price_max,
        "target_moods": state.target_moods,
        "unknown_target_moods": state.unknown_target_moods,
        "current_moods": state.current_moods,
        "unknown_current_moods": state.unknown_current_moods,
        "style_keywords": state.style_keywords,
        "color_keywords": state.color_keywords,
        "material_keywords": state.material_keywords,
        "lighting_keywords": state.lighting_keywords,
        "vlm_description": state.vlm_description,
        "target_image_moods": state.target_image_moods,
        "target_image_style_keywords": state.target_image_style_keywords,
        "target_image_color_keywords": state.target_image_color_keywords,
        "target_image_material_keywords": state.target_image_material_keywords,
        "target_image_lighting_keywords": state.target_image_lighting_keywords,
        "target_image_description": state.target_image_description,
        "last_intent": state.last_intent,
    }


# ------------------------------------------------------------
# Pydantic 요청/응답 모델
# ------------------------------------------------------------

class TextChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class TextChatResponse(BaseModel):
    session_id: str
    reply: str
    mode: str
    llm_latency: float
    debug_state_summary: Optional[str] = None
    session_state: Optional[Dict[str, Any]] = None
    products: Optional[List[Dict[str, Any]]] = None


class SessionResetRequest(BaseModel):
    session_id: str


class SessionResetResponse(BaseModel):
    session_id: str
    status: str


class ImageChatResponse(BaseModel):
    session_id: str
    message: str
    debug_state_summary: Optional[str] = None
    session_state: Optional[Dict[str, Any]] = None
    # 🔹 동시 텍스트 입력 대응용(선택)
    reply: Optional[str] = None
    mode: Optional[str] = None
    llm_latency: Optional[float] = None
    products: Optional[List[Dict[str, Any]]] = None


# Pydantic v2에서는 forward references가 없는 경우도 model_rebuild()를 안전하게 호출 가능
TextChatResponse.model_rebuild()
ImageChatResponse.model_rebuild()


# ------------------------------------------------------------
# 헬스 체크
# ------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok"}


# ------------------------------------------------------------
# 텍스트 대화 엔드포인트
# ------------------------------------------------------------

@app.post("/chat/text", response_model=TextChatResponse)
def chat_text(req: TextChatRequest):
    """
    텍스트 기반 대화/추천 엔드포인트.

    - 기존 main.py의 한 턴 루프 로직을 그대로 옮겨온 구조:
      · parse_user_query()
      · decide_mode()
      · ChatMode에 따라 handle_smalltalk / handle_survey / handle_recommend 호출
    """
    # 1) 세션 상태 가져오기/생성
    session_id, state, history = _get_or_create_session(req.session_id)

    user_text = req.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="message가 비어 있습니다.")

    # 2) 특수 명령 일부 지원 (원하면 프론트에서 직접 API를 나눠 써도 됨)
    # ::summary → 상태 요약만 돌려줌
    if user_text.startswith("::summary"):
        summary = render_summary(state)
        return TextChatResponse(
            session_id=session_id,
            reply=summary,
            mode="SUMMARY",
            llm_latency=0.0,
            debug_state_summary=summary,
        )

    # 여기서는 ::reset_all, ::reset_moods 는 별도 API로 처리하는 걸 권장하므로 생략

    # 3) 본격 대화 처리
    text_result = _run_text_turn(session_id, state, history, user_text)

    return TextChatResponse(**text_result)


def _run_text_turn(
    session_id: str,
    state: ChatState,
    history: List[Tuple[str, str]],
    user_text: str,
) -> Dict[str, Any]:
    """텍스트 턴 처리 공통 함수 (chat_text + 이미지 동시 입력 시 재사용)."""
    state.last_user_message = user_text  # main.py와 동일한 필드 사용 가정

    # 1) 파싱
    parsed = parse_user_query(user_text)

    # 2) 모드 결정
    mode = decide_mode(user_text, parsed, state)
    state.last_intent = mode.name

    # 3) SMALLTALK이 아닐 때만 state에 누적
    if mode != ChatMode.SMALLTALK:
        state.update_from_parsed(parsed)

    # 4) 모드별 응답 생성
    products: List[Dict[str, Any]] = []
    if mode == ChatMode.SMALLTALK:
        answer, llm_sec = handle_smalltalk(user_text, history)
        products = []
    elif mode == ChatMode.SURVEY:
        answer, llm_sec = handle_survey(user_text, state, history)
        products = []
    else:
        answer, llm_sec, products = handle_recommend(user_text, state, history)

    # 5) 히스토리 업데이트
    history.append((user_text, answer))

    # 6) 디버그용 상태 요약
    debug_summary = render_summary(state)

    return {
        "session_id": session_id,
        "reply": answer,
        "mode": mode.name,
        "llm_latency": float(llm_sec),
        "debug_state_summary": debug_summary,
        "session_state": _state_to_dict(state),
        "products": products,
    }


# ------------------------------------------------------------
# 이미지 기반 VLM 엔드포인트
# ------------------------------------------------------------

@app.post("/chat/image", response_model=ImageChatResponse)
async def chat_image(
    session_id: Optional[str] = Form(None),
    is_want: bool = Form(False),
    file: UploadFile = File(...),
    user_message: Optional[str] = Form(None),
    text: Optional[str] = Form(None),  # 프론트 필드명 호환 (text)
):
    """
    방/레퍼런스 이미지 업로드 → VLM 분석 → 상태 업데이트.

    - 기존 main.py의 handle_image_command()를 그대로 재사용한다.
    - handle_image_command()는 내부에서:
      · analyze_room_image() (input_vlm.py)
      · 인테리어/소품 필터링
      · ChatState의 current_* / target_image_* 필드 업데이트
      · 한국어 요약 문자열을 반환
    """
    # 1) 세션 상태 가져오기/생성
    session_id, state, _history = _get_or_create_session(session_id)

    # 2) 업로드 파일을 임시 디렉토리에 저장
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일 이름이 비어 있습니다.")

    suffix = Path(file.filename).suffix or ".jpg"
    tmp_path = TMP_DIR / f"{session_id}_{uuid.uuid4().hex}{suffix}"

    try:
        with tmp_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    finally:
        file.file.close()

    # 3) 기존 CLI용 handle_image_command를 재사용하기 위해
    #    "-want" 옵션 포함한 인자 문자열을 만들어 준다.
    if is_want:
        # 레퍼런스/원하는 분위기 이미지
        arg = f'-want "{tmp_path}"'
    else:
        # 현재 방 이미지
        arg = f'"{tmp_path}"'

    # 4) VLM 처리 + ChatState 업데이트
    try:
        image_message = handle_image_command(arg, state)
    finally:
        # 사용 끝난 임시 파일 제거 (실패해도 크게 상관 없으므로 예외 무시)
        try:
            tmp_path.unlink(missing_ok=True)  # Python 3.8 이하면 exist_ok 처리 필요
        except TypeError:
            # Python <3.8 호환용
            if tmp_path.exists():
                tmp_path.unlink()

    # 5) 상태 요약까지 같이 반환 (프론트에서 디버그 탭에 보여줄 수 있음)
    summary = render_summary(state)

    # 6) 선택: 이미지 업로드와 함께 텍스트까지 들어온 경우 즉시 한 턴 처리
    text_result: Dict[str, Any] = {}
    combined_text = user_message if user_message is not None else text
    if combined_text is not None:
        stripped = combined_text.strip()
        if stripped:
            text_result = _run_text_turn(session_id, state, _histories[session_id], stripped)

    return ImageChatResponse(
        session_id=session_id,
        message=image_message,
        debug_state_summary=summary,
        session_state=_state_to_dict(state),
        reply=text_result.get("reply"),
        mode=text_result.get("mode"),
        llm_latency=text_result.get("llm_latency"),
        products=text_result.get("products"),
    )


# ------------------------------------------------------------
# 세션 리셋 엔드포인트
# ------------------------------------------------------------

@app.post("/session/reset", response_model=SessionResetResponse)
def reset_session(req: SessionResetRequest):
    """
    세션 전체 리셋 (상태 + 히스토리 삭제).

    - 프론트에서 새로운 대화를 시작하고 싶을 때 호출.
    """
    if not req.session_id:
        raise HTTPException(status_code=400, detail="session_id가 비어 있습니다.")

    _reset_session(req.session_id)
    return SessionResetResponse(session_id=req.session_id, status="reset")
