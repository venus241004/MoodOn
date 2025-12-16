"""
rag_retriever.py

ChromaDB 기반 RAG 검색기 (OpenAI text-embedding-3-large 버전)

- OpenAI Embedding API로 쿼리 임베딩 생성
- ChromaDB에서 top_k 검색
- metadata 필터(category_id 등)도 where로 줄 수 있음
- distance(코사인 거리) → sim_score(0~1)로 변환해서 메타데이터에 포함

설계 포인트:
- search()에서는 카테고리로 where 필터를 걸지 않고,
  전체에서 벡터 검색한 뒤 product_filter.filter_and_rank()에서
  카테고리/무드/가격을 기반으로 rerank 한다.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from openai import OpenAI

from config import EMBEDDING_MODEL_NAME, VECTOR_DB_PATH, RAG_TOP_K


# rag_index.py / build_vector_db.py에서 생성한 경로와 동일해야 함
CHROMA_DIR = VECTOR_DB_PATH
COLLECTION_NAME = "products"  # rag_index.py에서 생성한 이름과 동일해야 함


class RAGRetriever:
    """
    - 초기화 시:
        · Chroma PersistentClient + 'products' 컬렉션 로딩
        · OpenAI 임베딩 클라이언트 준비
    - 주요 메서드:
        · query(query_text, filters=None, top_k=...)  → 로우 레벨
        · search(query_text, state=None, top_k=None) → main.py에서 쓰는 하이 레벨
    """

    def __init__(self):
        # 1) Chroma 클라이언트
        self.client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )

        # 2) 컬렉션 로드
        self.collection = self.client.get_collection(name=COLLECTION_NAME)

        # 3) OpenAI 클라이언트 (임베딩용)
        self.embedding_client = OpenAI()  # OPENAI_API_KEY는 .env / 환경변수에서 읽음

    # ========================================================
    # 1. 쿼리 임베딩
    # ========================================================

    def _embed_query(self, text: str) -> List[float]:
        """
        OpenAI text-embedding-3-large로 쿼리 임베딩 생성.
        """
        resp = self.embedding_client.embeddings.create(
            model=EMBEDDING_MODEL_NAME,
            input=[text],
        )
        return resp.data[0].embedding

    # ========================================================
    # 2. 로우 레벨 query
    # ========================================================

    def query(
        self,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        query_text: 사용자 메시지 및 대화 상태를 기반으로 만든 검색 문장
        filters   : {"category_id": "...", ...} 형태 (없으면 None)
        top_k     : 검색 결과 개수

        return: [metadata(dict), metadata(dict), ...]
                각 dict 안에는 sim_score(0~1) 추가
        """
        # 1) 쿼리 문장을 임베딩
        query_vec = self._embed_query(query_text)

        where = filters if filters else None

        # 2) 거리 정보까지 함께 가져오기
        results = self.collection.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            where=where,
            include=["metadatas", "distances"],
        )

        metadatas_list = results.get("metadatas", [[]])[0]
        distances_list = results.get("distances", [[]])[0]

        cleaned: List[Dict[str, Any]] = []

        for m, d in zip(metadatas_list, distances_list):
            if not m:
                continue

            item = dict(m)

            # distance(코사인 거리) → 유사도(0~1)로 변환
            try:
                dist = float(d)
                sim = 1.0 - dist  # cosine distance이므로 1 - dist
                sim = max(0.0, min(1.0, sim))
            except Exception:
                sim = 0.0

            item["sim_score"] = round(sim, 4)

            # price 정수 변환 시도
            if "price" in item:
                try:
                    item["price"] = int(item["price"])
                except Exception:
                    try:
                        s = str(item["price"]).replace(",", "").strip()
                        item["price"] = int(s)
                    except Exception:
                        # 실패하면 그대로 둔다
                        pass

            # mood_keywords 정규화 (문자열 → 리스트)
            if "mood_keywords" in item:
                if isinstance(item["mood_keywords"], str):
                    raw = item["mood_keywords"]
                    # 혹시 모를 괄호/따옴표 정리
                    raw = (
                        raw.replace("[", "")
                        .replace("]", "")
                        .replace("'", "")
                    )
                    item["mood_keywords"] = [
                        p.strip()
                        for p in raw.split(",")
                        if p.strip()
                    ]
                elif isinstance(item["mood_keywords"], list):
                    item["mood_keywords"] = [
                        str(p).strip()
                        for p in item["mood_keywords"]
                        if str(p).strip()
                    ]

            cleaned.append(item)

        return cleaned

    # ========================================================
    # 3. 하이 레벨 search (main.py에서 사용하는 인터페이스)
    # ========================================================

    def search(
        self,
        query_text: str,
        state: Optional[Any] = None,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        main.py에서 사용하는 편의 메서드.

        Args:
            query_text: 검색용 문장 (사용자 입력 + 무드/공간 등)
            state     : ChatState 또는 유사 객체
                        (category, price_min, price_max 등 필드 가진 객체)
            top_k     : None이면 config.RAG_TOP_K 사용

        Returns:
            query()와 동일하게, 상품 메타데이터 dict 리스트.
        """
        if top_k is None:
            top_k = RAG_TOP_K

        # ⚠️ 카테고리 필터는 여기서 걸지 않는다.
        # - LLM이 "lighting" 같은 애매한 값을 줄 때,
        #   Chroma 메타데이터의 "category_id" (예: "조명", "러그_커튼")와
        #   안 맞아서 결과가 0개 나오는 문제가 있었음.
        # - 대신 전체에서 벡터 검색을 하고,
        #   product_filter.filter_and_rank()에서 카테고리/무드/가격으로 재랭크한다.
        #
        # 필요하다면 나중에 다음처럼 다시 활성화할 수 있음:
        # filters = {}
        # if state is not None and getattr(state, "category", None):
        #     filters["category_id"] = state.category
        # return self.query(query_text, filters=filters or None, top_k=top_k)

        return self.query(query_text, filters=None, top_k=top_k)


# ============================================================
# 4. 단독 테스트용 실행
# ============================================================

if __name__ == "__main__":
    retriever = RAGRetriever()

    test_query = "아늑한 베이지톤 거실 러그 추천해줘"
    results = retriever.search(test_query, state=None, top_k=5)

    print("\n=== TEST RESULT ===")
    for r in results:
        print(
            f"{r.get('product_name')} / moods={r.get('mood_keywords')} "
            f"/ category={r.get('category_id')} "
            f"/ sim_score={r.get('sim_score')}"
        )
