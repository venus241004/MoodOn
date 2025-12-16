# rag_index.py
"""
products_all_ver1_vlm.json → Chroma VectorDB 인덱싱 스크립트 (OpenAI Embedding 버전)

- 한 상품당 하나의 document
- 무드 키워드 / 카테고리 / 가격 / 브랜드 등 메타데이터 저장
- 임베딩: OpenAI text-embedding-3-large (config.EMBEDDING_MODEL_NAME)

⚠️ 주의:
  - build_vector_db.py와 동일하게 'products' 컬렉션을 생성한다.
  - 이 파일을 실행하면 기존 'products' 컬렉션을 삭제하고 다시 만든다.
"""

import json
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from chromadb.config import Settings
from openai import OpenAI

from config import (
    PRODUCTS_JSON_PATH,
    VECTOR_DB_DIR,
    EMBEDDING_MODEL_NAME,
)

# 🔹 무드 정규화 유틸 (mood_vocab.py)
from mood_vocab import snap_moods_to_vocab


# =========================
# 0. OpenAI Embedding 헬퍼
# =========================

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()  # OPENAI_API_KEY는 .env / 환경변수에서 읽음
    return _client


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    OpenAI text-embedding-3-large로 여러 문장을 임베딩.
    """
    client = _get_client()
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL_NAME,
        input=texts,
    )
    return [d.embedding for d in resp.data]


# =========================
# 1. 인덱스 빌더
# =========================

COLLECTION_NAME = "products"


def build_index():
    print("▶ RAG 인덱싱 시작 (OpenAI Embeddings)")
    print(f"  - JSON: {PRODUCTS_JSON_PATH}")
    print(f"  - Vector DB: {VECTOR_DB_DIR}")
    print(f"  - EMBEDDING_MODEL: {EMBEDDING_MODEL_NAME}")

    # 경로 생성
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)

    # Chroma 클라이언트
    client = chromadb.PersistentClient(
        path=str(VECTOR_DB_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    # 기존 컬렉션 삭제 후 재생성
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"  - 기존 '{COLLECTION_NAME}' 컬렉션 삭제")
    except Exception:
        print(f"  - 기존 '{COLLECTION_NAME}' 컬렉션 없음 (무시)")

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # JSON 로드
    with open(PRODUCTS_JSON_PATH, "r", encoding="utf-8") as f:
        products: List[Dict[str, Any]] = json.load(f)

    print(f"📦 총 상품 수(원본): {len(products)}개")

    ids: List[str] = []
    docs: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    seen_ids = set()
    skipped_duplicates = 0

    for p in products:
        product_id = p.get("product_id")
        if not product_id:
            # product_id가 아예 없으면 스킵 (안정성용)
            continue

        # 🔹 동일 product_id가 이미 들어가 있으면 스킵
        if product_id in seen_ids:
            skipped_duplicates += 1
            # 필요하면 여기서 디버그 출력 가능:
            # print(f"  - 중복 product_id 발견, 스킵: {product_id}")
            continue

        seen_ids.add(product_id)

        category_id = p.get("category_id", "")
        brand_name = p.get("brand_name", "")
        product_name = p.get("product_name", "")
        price_str = p.get("price", "0")

        # ---- 가격 파싱 ----
        try:
            price_int = int(price_str)
        except Exception:
            price_int = 0

        # ---- 무드 처리: raw → 정규화(vocab) ----
        raw_moods = p.get("mood_keywords", []) or p.get("moods", []) or []

        if isinstance(raw_moods, str):
            raw_mood_list = [m.strip() for m in raw_moods.split(",") if m.strip()]
        elif isinstance(raw_moods, list):
            raw_mood_list = [str(m).strip() for m in raw_moods if str(m).strip()]
        else:
            raw_mood_list = []

        # 🔹 vocab에 맞춰 정규화 (대표 무드로 스냅)
        canonical_moods, unknown_moods = snap_moods_to_vocab(raw_mood_list)

        # doc_text에 넣을 무드 텍스트: 가능하면 정규화된 무드 사용
        moods_for_text = canonical_moods or raw_mood_list
        if moods_for_text:
            moods_str = ", ".join(moods_for_text)
        else:
            moods_str = ""

        # 메타데이터용 문자열 버전들 (Chroma는 리스트를 허용하지 않음)
        canonical_moods_str = ", ".join(canonical_moods) if canonical_moods else ""
        raw_moods_str = ", ".join(raw_mood_list) if raw_mood_list else ""
        unknown_moods_str = ", ".join(unknown_moods) if unknown_moods else ""

        # 임베딩용 텍스트 구성
        text_parts = [
            f"[카테고리] {category_id}",
            f"[브랜드] {brand_name}",
            f"[상품명] {product_name}",
            f"[가격] {price_str}원",
        ]
        if moods_str:
            text_parts.append("[무드 키워드] " + moods_str)

        doc_text = "\n".join(text_parts)

        ids.append(product_id)
        docs.append(doc_text)
        metadatas.append(
            {
                "product_id": product_id,
                "category_id": category_id,
                "brand_name": brand_name,
                "price": price_int,
                # 🔹 RAG 검색에서 사용할 표준화된 무드 (문자열)
                "mood_keywords": canonical_moods_str or raw_moods_str,
                "mood_keywords_count": len(canonical_moods or raw_mood_list),
                # 🔹 원본 JSON에 있던 무드 (로우 데이터 보존, 문자열)
                "raw_mood_keywords": raw_moods_str,
                # 🔹 vocab에 매칭되지 않은 무드들(분석/디버깅용, 문자열)
                "unknown_mood_keywords": unknown_moods_str,
                "link_url": p.get("link_url", ""),
                "image_url": p.get("image_url", ""),
                "s3_path": p.get("s3_path", ""),
                "s3_url": p.get("s3_url", ""),
                "mood_category": p.get("mood_category", ""),
                "source_site": infer_source_site(product_id),
            }
        )

    print(f"✅ 중복 제거 후 실제 인덱싱 대상 상품 수: {len(ids)}개")
    if skipped_duplicates > 0:
        print(f"  - 중복 product_id로 인해 스킵된 개수: {skipped_duplicates}개")

    print("🧠 임베딩 계산 중... (OpenAI API)")
    embeddings: List[List[float]] = []
    BATCH_SIZE = 128
    total = len(docs)

    for i in range(0, total, BATCH_SIZE):
        batch_docs = docs[i : i + BATCH_SIZE]
        batch_embs = embed_texts(batch_docs)
        embeddings.extend(batch_embs)
        print(f"  - {i + len(batch_docs)}/{total}개 완료")

    print("💾 Chroma 컬렉션에 추가 중...")
    collection.add(
        ids=ids,
        documents=docs,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print("✅ 인덱싱 완료!")


def infer_source_site(product_id: str) -> str:
    """
    product_id 패턴으로 간단히 출처 분류
    예: ten_..., kakao_..., guud_...
    """
    if not isinstance(product_id, str):
        return "unknown"

    if product_id.startswith("ten_"):
        return "10x10"
    if product_id.startswith("kakao_"):
        return "kakao"
    if product_id.startswith("guud_"):
        return "guud"
    return "unknown"


if __name__ == "__main__":
    build_index()
