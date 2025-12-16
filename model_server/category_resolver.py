# category_resolver.py

"""
사용자 자연어 입력으로부터 category_id를
OpenAI 임베딩 기반으로 추론하는 모듈.

- products_all_ver1.json 에서 실제 category_id 목록을 추출
- OpenAI text-embedding-3-large로
  카테고리 문장과 유저 입력을 임베딩
- 코사인 유사도 가장 높은 카테고리를 반환
"""

import json
from typing import Optional, List

import numpy as np
from openai import OpenAI

from config import EMBEDDING_MODEL_NAME, PRODUCTS_JSON_PATH


# 전역 캐시
_client: OpenAI | None = None
_category_labels: List[str] | None = None
_category_vecs: np.ndarray | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def _embed_texts(texts: List[str]) -> np.ndarray:
    """
    OpenAI text-embedding-3-large로 여러 문장 임베딩
    - 반환: (N, dim) numpy array (L2 정규화 포함)
    """
    client = _get_client()
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL_NAME,
        input=texts,
    )
    vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)

    # L2 정규화 (코사인 유사도 계산용)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.clip(norms, 1e-8, None)
    vecs = vecs / norms
    return vecs


def _ensure_initialized():
    """
    - OpenAI 클라이언트 생성
    - products_all_ver1.json에서 category_id 고유값 추출
    - 각 카테고리에 대한 임베딩 미리 계산
    """
    global _category_labels, _category_vecs

    if _category_labels is not None and _category_vecs is not None:
        return

    print("🔎 [CategoryResolver] 초기화 중...")

    # 1) JSON에서 카테고리 목록 추출
    with open(PRODUCTS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    category_set = set()
    for item in data:
        cid = item.get("category_id")
        if cid:
            category_set.add(cid)

    _category_labels = sorted(category_set)

    # 2) 카테고리 문장을 약간 풍부하게 만들어서 임베딩
    category_texts = [
        f"인테리어 상품 카테고리 {cid}"
        for cid in _category_labels
    ]

    _category_vecs = _embed_texts(category_texts)

    print(f"🔎 [CategoryResolver] 카테고리 개수: {len(_category_labels)}개 초기화 완료")


def infer_category_from_text(
    user_text: str,
    min_similarity: float = 0.42,
) -> Optional[str]:
    """
    유저 자연어 입력을 받아서
    가장 유사한 category_id를 반환한다.

    - min_similarity: 이 값보다 낮으면 None (카테고리 추론 실패로 간주)
    """
    _ensure_initialized()

    assert _category_labels is not None
    assert _category_vecs is not None

    text = user_text.strip()
    if not text:
        return None

    # 유저 입력 임베딩
    q_vec = _embed_texts([text])[0]  # shape: (dim,)

    # 코사인 유사도 = dot(normalized_vecs)
    sims = np.dot(_category_vecs, q_vec)  # shape: (num_categories,)
    best_idx = int(np.argmax(sims))
    best_sim = float(sims[best_idx])

    best_cat = _category_labels[best_idx]

    print(
        f"[CategoryResolver] best category = {best_cat} "
        f"(similarity={best_sim:.3f})"
    )

    if best_sim < min_similarity:
        return None

    return best_cat
