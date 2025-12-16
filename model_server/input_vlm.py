# input_vlm.py
"""
Qwen2.5-VL-7B-Instruct 기반 VLM 모듈

- 모델: Qwen/Qwen2.5-VL-7B-Instruct
- 용도: 방/인테리어 이미지를 보고 공간/무드/컬러/재질 등을 추출해서
        RAG 추천 챗봇에 넘길 구조화된 JSON을 생성

추가 기능:
- 너무 흐리거나 어두운 사진 사전 차단
- 인테리어 공간이 아닌 사진(인물/반려동물/풍경/제품 클로즈업 등) 차단

필수:
    pip install qwen-vl-utils
    pip install numpy pillow
    (transformers 5.0.0.dev0 기준)

config.py 에는 최소한 아래 값이 정의되어 있어야 함:
    VLM_MODEL_NAME = "Qwen/Qwen2.5-VL-7B-Instruct"
(이미 있다면 그대로 사용)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import torch
from transformers import AutoProcessor
from transformers import Qwen2_5_VLForConditionalGeneration
from qwen_vl_utils import process_vision_info

from config import VLM_MODEL_NAME  # 예: "Qwen/Qwen2.5-VL-7B-Instruct"

# 🔹 추가: 품질 검사용
import numpy as np
from PIL import Image


# =========================
# 내부 설정
# =========================

# 해상도 제한 (픽셀 수 기준) → VRAM 절약용
#   28*28 단위로 픽셀 수를 맞추는게 공식 권장 방식
MIN_PIXELS = 256 * 28 * 28   # 너무 작은 사진 방지
MAX_PIXELS = 768 * 28 * 28   # 1024*28*28 정도까지 올려도 되지만 VRAM에 따라 조절

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if torch.cuda.is_available() else torch.float32


SYSTEM_PROMPT = """
당신은 인테리어 스타일링 전문가입니다.
사용자가 올린 방/인테리어 이미지를 보고 아래 항목을 **반드시 JSON 형식으로만** 출력하세요.

출력 JSON 스키마 (키 이름/타입을 정확히 지켜주세요):

{
  "image_type": "이미지 종류. 아래 중 하나: 'interior_room', 'human', 'pet', 'landscape', 'object_closeup', 'document', 'other'",
  "image_type_detail": "짧은 한국어 설명 (예: '인물 셀카', '고양이 클로즈업', '거실 인테리어', '제품 상세샷' 등)",
  "space_ko": "문자열, 한국어로 공간 설명 (예: '따뜻한 느낌의 원룸 거실')",
  "space_en": "문자열, 영어로 짧은 공간 타입 (예: 'living room', 'bedroom', 'home office')",
  "style_keywords": ["스타일 키워드 한국어", ...],
  "color_keywords": ["색감/톤 키워드 한국어", ...],
  "mood_keywords": ["감성/분위기 키워드 한국어", ...],
  "material_keywords": ["재질/마감 키워드 한국어", ...],
  "lighting_keywords": ["조명 관련 키워드 한국어", ...],
  "overall_comment_ko": "한두 문장 정도의 한국어 요약 코멘트"
}

image_type 분류 규칙:
- 'interior_room' : 방/거실/주방/작업실 등, 실내 인테리어가 화면의 대부분을 차지하는 경우
- 'human' : 사람(얼굴/상반신/전신)이 화면에서 가장 눈에 띄는 경우 (셀카, 프로필 사진 등)
- 'pet' : 고양이, 강아지 등 반려동물이 화면의 주인공인 경우
- 'landscape' : 자연 풍경, 도시 야경, 바다, 산 등 실내가 아닌 풍경 사진
- 'object_closeup' : 제품 하나, 가구 일부, 작은 물건이 화면 대부분을 차지하는 클로즈업 샷
- 'document' : 문서/화면 캡처/텍스트가 중심인 이미지
- 'other' : 위 어느 쪽에도 뚜렷하게 속하지 않는 경우

[키워드 작성 규칙 – 매우 중요]
- style_keywords, color_keywords, mood_keywords, material_keywords, lighting_keywords 항목에 들어가는
  모든 문자열은 반드시 **순수 한국어 단어**로만 작성하세요.
- 영어 단어, 알파벳, 숫자, 특수문자, 언더스코어("_")는 절대 사용하지 마세요.
- 잘된 예시:
  - "mood_keywords": ["따뜻한", "편안한", "포근한"]
  - "color_keywords": ["베이지 톤", "우드톤", "브라운 톤"]
  - "material_keywords": ["코튼", "벨벳", "린넨"]
  - "lighting_keywords": ["은은한 조명", "노란 조명"]
- 잘못된 예시 (절대로 사용 금지):
  - ["warm", "comfortable", "relaxing"]
  - ["_beige", "beige", "brown"]
  - ["cotton", "velvet", "wool"]
  - ["natural light", "soft lighting"]
- 영어로 먼저 떠올랐다면, 반드시 그 의미에 맞는 한국어 감성/스타일 단어로 바꾸어 적으세요.

규칙:
- 설명은 최대한 구체적으로, 그러나 과장 없이 작성합니다.
- 색감/무드/스타일은 실제 이미지에서 보이는 것만 기반으로 추론합니다.
- JSON 이외의 문장, 설명, 마크다운은 절대 출력하지 마세요.
- 모든 문자열은 큰따옴표(\")를 사용하고, JSON 문법을 엄격히 지키세요.
"""


@dataclass
class VLMResult:
    """VLM 분석 결과를 파이썬 객체로 감싸는 헬퍼 (선택적)."""
    image_type: str
    image_type_detail: str
    space_ko: str
    space_en: str
    style_keywords: List[str]
    color_keywords: List[str]
    mood_keywords: List[str]
    material_keywords: List[str]
    lighting_keywords: List[str]
    overall_comment_ko: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VLMResult":
        return cls(
            image_type=str(data.get("image_type", "")),
            image_type_detail=str(data.get("image_type_detail", "")),
            space_ko=str(data.get("space_ko", "")),
            space_en=str(data.get("space_en", "")),
            style_keywords=list(data.get("style_keywords", [])),
            color_keywords=list(data.get("color_keywords", [])),
            mood_keywords=list(data.get("mood_keywords", [])),
            material_keywords=list(data.get("material_keywords", [])),
            lighting_keywords=list(data.get("lighting_keywords", [])),
            overall_comment_ko=str(data.get("overall_comment_ko", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_type": self.image_type,
            "image_type_detail": self.image_type_detail,
            "space_ko": self.space_ko,
            "space_en": self.space_en,
            "style_keywords": self.style_keywords,
            "color_keywords": self.color_keywords,
            "mood_keywords": self.mood_keywords,
            "material_keywords": self.material_keywords,
            "lighting_keywords": self.lighting_keywords,
            "overall_comment_ko": self.overall_comment_ko,
        }


# =========================
# 품질 체크 헬퍼
# =========================

def _check_image_quality(image_path: Union[str, Path]) -> Optional[str]:
    """
    - 너무 흐린 사진
    - 너무 어두운 사진
    - 너무 작은 사진
    등을 사전에 걸러서 문제 있으면 한국어 에러 메시지 문자열을 반환.
    문제 없으면 None 반환.
    """
    try:
        img = Image.open(image_path).convert("L")  # grayscale
    except Exception:
        return "이미지를 불러올 수 없습니다. 파일 경로와 형식을 다시 확인해 주세요."

    arr = np.array(img, dtype=np.float32)

    h, w = arr.shape
    if h * w < 128 * 128:
        return "이미지가 너무 작아서 분위기를 분석하기 어렵습니다. 좀 더 큰 사이즈의 사진으로 다시 시도해 주세요."

    # 밝기 체크
    brightness = float(arr.mean())
    if brightness < 35:  # 너무 어두움
        return "사진이 너무 어둡습니다. 조명을 켜거나 밝은 환경에서 찍은 사진으로 다시 시도해 주세요."

    # 흐림(블러) 체크: 간단한 라플라시안 기반
    # 중심 픽셀 - 주변 픽셀 4개 합 → 라플라시안 근사
    center = arr[1:-1, 1:-1]
    lap = (
        arr[0:-2, 1:-1]
        + arr[2:, 1:-1]
        + arr[1:-1, 0:-2]
        + arr[1:-1, 2:]
        - 4 * center
    )
    blur_var = float(lap.var())

    # 값이 너무 낮으면 흐린 사진이라고 판단
    if blur_var < 50.0:
        return "이미지의 분위기를 인식하기 어렵습니다. 사진이 너무 흐리게 찍혀 있어요. 조금 더 밝고 선명한 사진으로 다시 시도해 주세요."

    return None


class QwenVLClient:
    """Qwen2.5-VL-7B-Instruct 래퍼. 모델/프로세서 1회 로딩."""

    def __init__(
        self,
        model_name: str = VLM_MODEL_NAME,
        device: str = DEVICE,
        dtype: torch.dtype = DTYPE,
    ) -> None:
        self.model_name = model_name
        self.device = device

        # 모델 로드
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=dtype,
            device_map="auto" if device == "cuda" else None,
            attn_implementation="eager",  # flash_attn 안쓰면 가장 안전
        )

        # 프로세서 로드 (해상도 제한 설정)
        self.processor = AutoProcessor.from_pretrained(
            model_name,
            min_pixels=MIN_PIXELS,
            max_pixels=MAX_PIXELS,
        )

    # =========================
    # public: 이미지 → JSON
    # =========================
    def analyze_image(
        self,
        image_path: str | Path,
        user_hint: Optional[str] = None,
        max_new_tokens: int = 256,
        temperature: float = 0.2,
        top_p: float = 0.9,
    ) -> Dict[str, Any]:
        """
        방/인테리어 이미지 한 장을 분석해서 JSON dict 리턴.

        Args:
            image_path: 이미지 파일 경로
            user_hint: 사용자가 추가로 알려주는 텍스트(원하는 무드/설명 등), 없어도 됨.
        """
        image_path = str(image_path)
        if not Path(image_path).is_file():
            raise FileNotFoundError(f"[VLM] 이미지 파일을 찾을 수 없습니다: {image_path}")

        # 🔹 0) 기본 품질 체크 (너무 흐림 / 어두움 / 작은 이미지)
        quality_msg = _check_image_quality(image_path)
        if quality_msg:
            # 기존 파이프라인을 깨지 않기 위해 JSON 스키마는 유지하되,
            # overall_comment_ko 에 안내 메시지를 넣고 나머지는 비워서 반환.
            return {
                "image_type": "invalid_quality",
                "image_type_detail": "",
                "space_ko": "",
                "space_en": "",
                "style_keywords": [],
                "color_keywords": [],
                "mood_keywords": [],
                "material_keywords": [],
                "lighting_keywords": [],
                "overall_comment_ko": quality_msg,
            }

        # 유저 힌트 문장 구성
        if user_hint:
            hint_text = (
                "다음 이미지는 사용자의 실제 방/인테리어 사진일 수도 있고 아닐 수도 있습니다. "
                f"사용자가 추가로 남긴 설명: {user_hint!r}\n\n"
                "이 이미지가 인테리어 공간인지, 인물/반려동물/풍경/제품 클로즈업인지 먼저 판단한 뒤, "
                "앞서 설명한 JSON 스키마에 맞게 정보를 추출하세요."
            )
        else:
            hint_text = (
                "다음 이미지는 사용자의 실제 사진입니다. "
                "이 이미지가 인테리어 공간인지, 인물/반려동물/풍경/제품 클로즈업인지 먼저 판단한 뒤, "
                "앞서 설명한 JSON 스키마에 맞게 정보를 추출하세요."
            )

        # Qwen2.5-VL 메시지 포맷
        messages = [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": SYSTEM_PROMPT.strip()},
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "image": image_path,  # qwen_vl_utils 가 경로를 읽어서 처리
                    },
                    {
                        "type": "text",
                        "text": hint_text,
                    },
                ],
            },
        ]

        # vision 전처리 (이미지/비디오 텐서 준비)
        image_inputs, video_inputs = process_vision_info(messages)

        # text + vision → 모델 입력 텐서 생성
        text = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,  # assistant 응답 위치까지 프롬프트 생성
        )

        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(self.device)

        # 생성
        with torch.no_grad():
            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=temperature,
                top_p=top_p,
            )

        # prompt 부분을 잘라내고 assistant 응답만 디코딩
        input_ids = inputs["input_ids"]
        input_len = input_ids.shape[1]
        output_ids = generated_ids[:, input_len:]

        raw_text = self.processor.batch_decode(
            output_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )[0]

        # 🔍 임시 디버그: 모델이 실제로 뭘 뱉는지 보기
        print("===== [VLM RAW OUTPUT] =====")
        print(raw_text)
        print("============================")

        # JSON 파싱
        parsed = self._safe_parse_json(raw_text)

        # 🔹 1차 결과를 VLMResult로 래핑
        result = VLMResult.from_dict(parsed)
        image_type = (result.image_type or "").strip().lower()

        # =========================
        # 인테리어 공간이 아닌 경우 사전 차단
        # =========================
        if image_type and image_type != "interior_room":
            # 이미지 종류별 안내 메시지
            if image_type == "human":
                msg = "공간이 아닌 인물 사진이네요. 인테리어 공간 사진을 올려주시면 그에 맞게 추천드릴게요."
            elif image_type == "pet":
                msg = "고양이·강아지 같은 반려동물 중심 사진이라 방 분위기를 분석하긴 어려워요. 방 전체가 보이는 사진으로 다시 올려주세요."
            elif image_type == "landscape":
                msg = "야외 풍경 사진이라 실내 인테리어 분위기를 분석하기 어렵습니다. 방이나 거실처럼 실내 공간이 보이는 사진으로 다시 시도해 주세요."
            elif image_type == "object_closeup":
                msg = "제품이나 물건 하나만 크게 찍힌 사진이라 공간 전체의 무드를 파악하기 어렵습니다. 방 전체가 어느 정도 보이도록 찍은 사진을 올려주세요."
            elif image_type == "document":
                msg = "문서·화면 캡처처럼 보이는 이미지라 인테리어 공간 분석에는 사용할 수 없어요. 방이나 거실 사진을 올려주세요."
            else:
                msg = "방 인테리어가 잘 보이지 않는 사진이라 분위기를 분석하기 어렵습니다. 방 전체가 보이는 사진으로 다시 시도해 주세요."

            # 기존 스키마는 유지하되, 추천 파이프라인에 영향이 없도록 대부분 비워서 반환
            return {
                "image_type": image_type,
                "image_type_detail": result.image_type_detail,
                "space_ko": "",
                "space_en": "",
                "style_keywords": [],
                "color_keywords": [],
                "mood_keywords": [],
                "material_keywords": [],
                "lighting_keywords": [],
                "overall_comment_ko": msg,
            }

        # =========================
        # 인테리어 공간으로 인정되는 경우: 기존 동작 그대로 유지
        # =========================
        return result.to_dict()

    # =========================
    # 내부 헬퍼
    # =========================
    @staticmethod
    def _safe_parse_json(text: str) -> Dict[str, Any]:
        """
        VLM이 출력한 텍스트에서 JSON 부분만 최대한 안전하게 뽑아내서 파싱한다.

        전략:
        1) ```json ... ``` 코드블록 안을 먼저 시도
        2) 전체 문자열에서 { ... } 균형이 맞는 덩어리들을 모두 찾아서,
           길이가 긴 것부터 하나씩 json.loads 시도
        3) 그래도 안 되면, 기존처럼 첫 { ~ 마지막 } 범위를 한 번 더 시도
        4) 완전히 실패하면 기본 스켈레톤 반환
        """
        text = text.strip()

        def _try_parse(candidate: str) -> Optional[Dict[str, Any]]:
            candidate = candidate.strip()
            if not candidate:
                return None

            # 1차: 있는 그대로
            try:
                return json.loads(candidate)
            except Exception:
                pass

            # 2차: 너무 지저분한 문자만 제거 (언더스코어 등은 유지)
            try:
                cand2 = candidate.replace("\n", " ").replace("\r", " ")
                cand2 = re.sub(
                    r"[^\{\}\[\]0-9A-Za-z가-힣_\"\'\:\,\.\s\-]",
                    "",
                    cand2,
                )
                return json.loads(cand2)
            except Exception:
                return None

        # --------------------------------
        # 1) ```json ... ``` 또는 ``` ... ``` 코드블록 우선 시도
        # --------------------------------
        fence = re.search(r"```json([\s\S]*?)```", text, re.IGNORECASE)
        if not fence:
            fence = re.search(r"```([\s\S]*?)```", text)

        if fence:
            block = fence.group(1)
            parsed = _try_parse(block)
            if parsed is not None:
                return parsed

        # --------------------------------
        # 2) 전체 텍스트에서 { ... } 균형 잡힌 덩어리들 모두 추출
        #    (스택으로 바깥/안쪽 중괄호 매칭)
        # --------------------------------
        candidates: List[str] = []
        stack = []
        start_idx: Optional[int] = None

        for i, ch in enumerate(text):
            if ch == "{":
                if not stack:
                    start_idx = i
                stack.append("{")
            elif ch == "}":
                if stack:
                    stack.pop()
                    if not stack and start_idx is not None:
                        candidates.append(text[start_idx:i + 1])
                        start_idx = None

        # 길이 긴 것(=바깥 JSON일 가능성)이 먼저 가도록 정렬
        for cand in sorted(candidates, key=len, reverse=True):
            parsed = _try_parse(cand)
            if parsed is not None:
                return parsed

        # --------------------------------
        # 3) 마지막 fallback: 첫 { ~ 마지막 } 범위 한 번 더 시도
        # --------------------------------
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            cand = text[start:end + 1]
            parsed = _try_parse(cand)
            if parsed is not None:
                return parsed

        # --------------------------------
        # 4) 완전 실패 → 기본 스켈레톤
        # --------------------------------
        return {
            "image_type": "",
            "image_type_detail": "",
            "space_ko": "",
            "space_en": "",
            "style_keywords": [],
            "color_keywords": [],
            "mood_keywords": [],
            "material_keywords": [],
            "lighting_keywords": [],
            "overall_comment_ko": "",
        }




# 싱글톤 형태로 재사용 (Streamlit / CLI 양쪽에서 공용으로 쓰기 편하게)
_vlm_client: Optional[QwenVLClient] = None


def get_vlm_client() -> QwenVLClient:
    global _vlm_client
    if _vlm_client is None:
        _vlm_client = QwenVLClient()
    return _vlm_client


def analyze_room_image(
    image_path: str | Path,
    user_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    외부에서 주로 호출하는 헬퍼 함수.

    예)
        from input_vlm import analyze_room_image
        result = analyze_room_image("examples/room.jpg", "원목가구 위주, 따뜻한 분위기 좋아함")
    """
    client = get_vlm_client()
    return client.analyze_image(image_path, user_hint=user_hint)


# ============================================================
#  VLM 결과를 세션 상태에 바로 쓰기 좋은 형태로 가공하는 헬퍼
# ============================================================

def _normalize_str_list(val: Any) -> List[str]:
    """
    문자열 / 리스트 / 튜플 형태로 올 수 있는 키워드를
    ['키워드1', '키워드2', ...] 형태로 정규화
    """
    if isinstance(val, str):
        # 쉼표/슬래시/줄바꿈 기준으로 자르기
        chunks = re.split(r"[,\n/]", val)
        return [c.strip() for c in chunks if c.strip()]
    elif isinstance(val, (list, tuple)):
        return [str(x).strip() for x in val if str(x).strip()]
    else:
        return []


def infer_state_from_room_image(
    image_path: str | Path,
    user_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ✅ main.py에서 바로 ChatState로 옮겨 담기 좋은 형태로 가공하는 헬퍼.

    반환 형식:
        {
            "space": "침실" 또는 "거실" 등 (없으면 None),
            "moods": [...],
            "style_keywords": [...],
            "color_keywords": [...],
            "material_keywords": [...],
            "lighting_keywords": [...],
            "raw": VLM 원본 dict
        }
    """
    raw = analyze_room_image(image_path, user_hint=user_hint)

    space = raw.get("space_ko") or raw.get("space_en") or None

    moods = _normalize_str_list(raw.get("mood_keywords", []))
    style_keywords = _normalize_str_list(raw.get("style_keywords", []))
    color_keywords = _normalize_str_list(raw.get("color_keywords", []))
    material_keywords = _normalize_str_list(raw.get("material_keywords", []))
    lighting_keywords = _normalize_str_list(raw.get("lighting_keywords", []))

    return {
        "space": space if space else None,
        "moods": moods,
        "style_keywords": style_keywords,
        "color_keywords": color_keywords,
        "material_keywords": material_keywords,
        "lighting_keywords": lighting_keywords,
        "raw": raw,
    }


def infer_mood_from_room_image(
    image_path: str | Path,
    user_hint: Optional[str] = None,
):
    """
    ✅ 기존 인터페이스 유지용 래퍼.

    - 내부적으로 infer_state_from_room_image()를 호출해서
      전체 정보를 얻고,
    - 그 중에서 mood_keywords만 뽑아서 리스트로 반환한다.
    """
    info = infer_state_from_room_image(image_path, user_hint=user_hint)
    moods = info.get("moods") or []

    if isinstance(moods, str):
        moods = [m.strip() for m in moods.split(",") if m.strip()]
    elif isinstance(moods, (list, tuple)):
        moods = [str(m).strip() for m in moods if str(m).strip()]
    else:
        moods = []

    return moods


# 간단 로컬 테스트용
if __name__ == "__main__":
    import argparse
    from pprint import pprint

    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=str, help="분석할 이미지 경로")
    parser.add_argument(
        "--hint",
        type=str,
        default=None,
        help="사용자 힌트 텍스트 (선택사항)",
    )
    args = parser.parse_args()

    print(f"[VLM] 모델: {VLM_MODEL_NAME}")
    print(f"[VLM] 이미지: {args.image}")
    result_dict = analyze_room_image(args.image, user_hint=args.hint)
    pprint(result_dict, width=120)
