# streamlit_app.py
"""
MoodOn – 무드 기반 인테리어 추천 챗봇 (Streamlit 프론트엔드, chat_input 버전)

실행 방법 (final_project 가상환경에서):
    1) 모델 서버 실행
       python -m uvicorn model_server:app --host 0.0.0.0 --port 8000 --reload

    2) 이 파일 실행
       streamlit run streamlit_app.py
"""

import uuid
import requests
import streamlit as st

# =========================
# 설정
# =========================

MODEL_SERVER_URL = "http://127.0.0.1:8000"  # 나중에 EC2 올리면 이 주소만 바꾸면 됨

# =========================
# 세션 상태 초기화
# =========================

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    # [{"role": "user"|"assistant", "content": "..."}]
    st.session_state.messages = []

if "last_debug_summary" not in st.session_state:
    st.session_state.last_debug_summary = ""

if "is_image_processing" not in st.session_state:
    st.session_state.is_image_processing = False

session_id = st.session_state.session_id

# =========================
# 페이지 설정
# =========================

st.set_page_config(
    page_title="MoodOn – 무드 기반 인테리어 추천",
    layout="wide",
    page_icon="🛋️",
)

# 상단 제목
st.markdown("# 🛋️ MoodOn – 무드 기반 인테리어 추천 챗봇")
st.caption("방 사진과 취향을 기반으로, 어울리는 인테리어 무드를 함께 찾아봐요.")

# =========================
# 사이드바 (세션 / 상태)
# =========================

st.sidebar.markdown("### 🔐 세션 정보")
st.sidebar.code(session_id, language="text")

if st.sidebar.button("세션 초기화", use_container_width=True):
    try:
        resp = requests.post(
            f"{MODEL_SERVER_URL}/session/reset",
            json={"session_id": session_id},
            timeout=10,
        )
        if resp.status_code == 200:
            st.sidebar.success("세션을 초기화했습니다.")
            # 새 세션/대화 상태로 교체
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.last_debug_summary = ""
        else:
            st.sidebar.error(f"초기화 실패: {resp.status_code}")
    except Exception as e:
        st.sidebar.error(f"요청 실패: {e}")

tab_chat, tab_image, tab_debug = st.tabs(["💬 텍스트 대화", "🖼️ 방 이미지 분석", "🔍 디버그 요약"])

# =========================
# 탭 1: 텍스트 대화 (chat_input 스타일)
# =========================

with tab_chat:
    st.subheader("텍스트로 상담하기")

    # 지금까지의 대화를 위에서부터 순서대로 보여줌
    for msg in st.session_state.messages:
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.markdown(msg["content"])

    # 아래에 chat_input 하나만 띄워서 새 입력 받기
    prompt = st.chat_input(
        "메시지를 입력하세요 (예: 안녕, 내 방을 아늑하게 꾸미고 싶은데 뭐부터 하면 좋을까?)"
    )

    # 사용자가 메시지를 입력한 경우
    if prompt:
        # 1) 유저 메시지를 히스토리에 추가하고 바로 화면에 표시
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2) 모델 서버 호출 + 응답 표시
        with st.chat_message("assistant"):
            with st.spinner("MoodOn이 답변을 준비하고 있어요..."):
                try:
                    resp = requests.post(
                        f"{MODEL_SERVER_URL}/chat/text",
                        json={
                            "session_id": session_id,
                            "message": prompt,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        reply = data.get("reply", "")
                        st.markdown(reply)
                        # 히스토리와 디버그 요약 업데이트
                        st.session_state.messages.append(
                            {"role": "assistant", "content": reply}
                        )
                        st.session_state.last_debug_summary = data.get(
                            "debug_state_summary", ""
                        )
                    else:
                        err = f"모델 서버 오류: {resp.status_code} {resp.text}"
                        st.error(err)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": err}
                        )
                except Exception as e:
                    err = f"요청 실패: {e}"
                    st.error(err)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": err}
                    )

        # 여기서 rerun 호출 필요 없음.
        # Streamlit은 다음 입력 때 자동으로 전체 코드 다시 실행하면서
        # st.session_state.messages에 저장된 히스토리를 재렌더링함.

# =========================
# 탭 2: 방 이미지 분석
# =========================

with tab_image:
    st.subheader("방 사진 / 레퍼런스 이미지 분석")

    st.markdown(
        """
- **현재 방 사진**을 올리면 → VLM이 공간/무드/컬러를 분석해서 `current_*` 상태에 반영해요.  
- **원하는 분위기(레퍼런스) 이미지**를 올리면 → `target_image_*` 상태에 반영돼요.
"""
    )

    col_upload, col_preview = st.columns([2, 3])

    with col_upload:
        image_file = st.file_uploader(
            "이미지 파일 선택 (jpg / png)",
            type=["jpg", "jpeg", "png"],
        )
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            btn_current = st.button(
                "현재 방으로 분석",
                use_container_width=True,
                disabled=st.session_state.is_image_processing or image_file is None,
            )
        with col_btn2:
            btn_want = st.button(
                "원하는 분위기(레퍼런스)로 분석",
                use_container_width=True,
                disabled=st.session_state.is_image_processing or image_file is None,
            )

    with col_preview:
        if image_file is not None:
            st.image(
                image_file,
                caption="업로드한 이미지 미리보기",
                use_container_width=True,
            )
        else:
            st.info("먼저 이미지를 업로드해 주세요.")

    # 버튼이 눌렸을 때 실제 API 호출
    if image_file is not None and (btn_current or btn_want):
        if st.session_state.is_image_processing:
            st.warning("이미 다른 이미지가 분석 중입니다. 잠시만 기다려 주세요.")
        else:
            st.session_state.is_image_processing = True
            is_want = bool(btn_want)

            files = {
                "file": (image_file.name, image_file.read(), image_file.type),
            }
            data = {
                "session_id": session_id,
                "is_want": str(is_want).lower(),  # "true"/"false"
            }

            label = "현재 방" if not is_want else "원하는 분위기(레퍼런스)"
            with st.spinner(f"{label} 이미지 분석 중... (VLM 호출)"):
                try:
                    resp = requests.post(
                        f"{MODEL_SERVER_URL}/chat/image",
                        data=data,
                        files=files,
                        timeout=300,
                    )
                except Exception as e:
                    st.error(f"요청 실패: {e}")
                else:
                    if resp.status_code == 200:
                        data = resp.json()
                        st.success("이미지 분석 완료!")
                        st.markdown("**VLM 분석 결과 메시지:**")
                        st.write(data.get("message", ""))
                        st.session_state.last_debug_summary = data.get(
                            "debug_state_summary", ""
                        )
                    else:
                        st.error(f"모델 서버 오류: {resp.status_code} {resp.text}")
                finally:
                    st.session_state.is_image_processing = False

# =========================
# 탭 3: 디버그 요약
# =========================

with tab_debug:
    st.subheader("세션 상태 요약 (디버그용)")

    st.markdown(
        """
현재 세션의 `current_*`, `target_*`, `target_image_*` 상태를 한 번에 확인하고 싶을 때 사용하는 탭이에요.  
LLM/VLM 호출 후 내부 상태가 어떻게 누적됐는지 디버깅할 때 유용합니다.
"""
    )

    summary = st.session_state.get("last_debug_summary")

    if summary:
        with st.expander("요약 텍스트 보기", expanded=True):
            st.text(summary)
    else:
        st.info("아직 요약 정보가 없습니다. 텍스트 대화 또는 이미지 분석을 먼저 해보세요.")
