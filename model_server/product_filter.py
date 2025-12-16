"""
product_filter.py

RAG로 가져온 상품 후보 리스트에 대해
- 카테고리/예산/무드/중복 추천 여부를 반영해서
- 점수를 매기고 정렬하는 모듈.

입력:
    products : rag_retriever.RAGRetriever.search()가 반환한 상품 dict 리스트
    state    : main.ChatState (현재/목표 무드, 예산, 카테고리 등)

출력:
    점수가 높은 순으로 정렬된 상품 dict 리스트 (동일 객체에 'score' 필드 추가 가능)
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional


def _parse_price(price_raw: Any) -> Optional[int]:
    """
    상품 dict에 들어있는 price 값을 정수로 변환.
    실패하면 None.
    """
    if price_raw is None:
        return None
    try:
        return int(price_raw)
    except Exception:
        try:
            s = str(price_raw).replace(",", "").strip()
            return int(s)
        except Exception:
            return None


def _budget_filter_and_score(
    price: Optional[int],
    price_min: Optional[int],
    price_max: Optional[int],
) -> Optional[float]:
    """
    예산 필터 + 예산 적합도 점수.

    반환:
        - None  : 예산 범위를 아예 벗어난 상품 (필터링 대상)
        - float : 예산 내 상품에 대한 점수 (0 ~ 1 사이 값 정도)

    아이디어:
        - 예산이 주어지면 그 범위 밖은 필터링
        - 범위 안에서는 중앙에 가까울수록 점수를 조금 더 줌
    """
    if price is None:
        # 가격 정보가 없으면 예산 필터는 적용하지 않고, 점수도 0
        return 0.0

    if price_min is not None and price < price_min:
        return None
    if price_max is not None and price > price_max:
        return None

    # 예산이 아예 없는 경우 -> 필터 X, 점수 0
    if price_min is None and price_max is None:
        return 0.0

    # [min, max] 범위 안에서 중앙에 가까울수록 점수를 높게
    if price_min is not None and price_max is not None:
        center = (price_min + price_max) / 2
        half_range = max((price_max - price_min) / 2, 1)
        dist = abs(price - center)
        # dist가 0이면 1점, 범위 끝으로 갈수록 0점에 가까워지도록
        score = max(0.0, 1.0 - dist / half_range)
        return score

    # 최소값만 있는 경우: price_min 이상이면 OK, 가까울수록 살짝 점수
    if price_min is not None:
        # 최소값에서 멀어질수록 0에 가까워지도록
        dist = max(price - price_min, 0)
        # 금액 차이를 로그/스케일링 하는 등 더 정교하게 바꿔도 됨
        score = 1.0 / (1.0 + dist / max(price_min, 1))
        return score

    # 최대값만 있는 경우: price_max 이하이면 OK, 가까울수록 살짝 점수
    if price_max is not None:
        dist = max(price_max - price, 0)
        score = 1.0 / (1.0 + dist / max(price_max, 1))
        return score

    return 0.0


def _mood_match_score(
    product_moods: List[str],
    target_moods: List[str],
) -> float:
    """
    상품의 mood_keywords와 사용자의 '목표 무드(effective_target_moods)' 간의 매칭 점수.

    - 정확히 일치하는 무드가 많을수록 점수 ↑
    - 완전히 겹치는 게 없어도, 일부라도 겹치면 0.5 정도는 줌
    """
    if not target_moods:
        return 0.0
    if not product_moods:
        return 0.0

    prod_set = set(str(m).strip() for m in product_moods if m)
    targ_set = set(str(m).strip() for m in target_moods if m)

    if not prod_set or not targ_set:
        return 0.0

    inter = prod_set & targ_set
    if not inter:
        return 0.0

    # 겹치는 비율에 따라 0~1 사이 점수
    # (상품 무드/목표 무드 중 작은 쪽을 기준으로 비율 계산)
    denom = min(len(prod_set), len(targ_set))
    if denom <= 0:
        return 0.0

    base = len(inter) / denom  # 0 ~ 1
    # 살짝 가중치를 준다 (최대 2점)
    return base * 2.0


def _category_match_score(
    product_category: Optional[str],
    target_category: Optional[str],
) -> float:
    """
    상품의 category_id와 사용자가 원하는 카테고리(state.category) 매칭 점수.
    """
    if not target_category:
        return 0.0
    if not product_category:
        return 0.0

    pc = str(product_category)
    tc = str(target_category)

    if pc == tc:
        return 2.0
    if tc in pc:
        return 1.0
    return 0.0


def _space_match_score(
    product_space: Optional[str],
    target_space: Optional[str],
) -> float:
    """
    상품의 'space' 메타데이터(있다면)와 사용자가 말한 공간(state.space) 매칭 점수.

    데이터에 space 정보가 없으면 거의 0에 가깝게만 영향을 주고,
    있으면 조금 더 가중치를 줄 수 있다.
    """
    if not target_space:
        return 0.0
    if not product_space:
        return 0.0

    ps = str(product_space)
    ts = str(target_space)

    if ps == ts:
        return 1.0
    if ts in ps:
        return 0.5
    return 0.0


def filter_and_rank(
    products: List[Dict[str, Any]],
    state: Any,
) -> List[Dict[str, Any]]:
    """
    RAG로 가져온 상품 리스트에 대해
    - 예산/카테고리/무드/중복 추천 등을 반영해 점수 계산 후
    - 높은 순으로 정렬해서 반환.

    products: 각 상품은 최소한 아래 필드를 가질 수 있음:
        - "product_id"
        - "category_id"
        - "price"
        - "mood_keywords"  (리스트일 수도 있고, 문자열일 수도 있음)
        - "space"          (있으면 사용)
    state:
        - category
        - space
        - price_min, price_max
        - effective_target_moods (property)
        - last_recommended_ids   (이전에 추천한 상품 id 리스트)
    """
    target_category = getattr(state, "category", None)
    target_space = getattr(state, "space", None)
    price_min = getattr(state, "price_min", None)
    price_max = getattr(state, "price_max", None)

    # 목표 무드: 텍스트로 명시된 target_moods가 있으면 그걸 우선,
    # 없으면 current_moods를 사용하는 effective_target_moods 사용
    target_moods = getattr(state, "effective_target_moods", []) or []

    last_ids = set(getattr(state, "last_recommended_ids", []) or [])

    scored: List[Dict[str, Any]] = []

    for item in products:
        # ID 중복 방지용
        pid = item.get("product_id") or item.get("id")
        category_id = item.get("category_id")
        price_raw = item.get("price")
        product_price = _parse_price(price_raw)

        # 예산 필터 + 예산 점수
        budget_score = _budget_filter_and_score(product_price, price_min, price_max)
        if budget_score is None:
            # 예산 범위 밖 -> 후보에서 제거
            continue

        # 상품 무드 필드 정리
        moods_raw = item.get("mood_keywords") or item.get("moods") or []
        if isinstance(moods_raw, str):
            # 쉼표/공백 기준으로 잘라서 리스트로
            moods = [m.strip() for m in moods_raw.replace("/", ",").split(",") if m.strip()]
        elif isinstance(moods_raw, list):
            moods = [str(m).strip() for m in moods_raw if m]
        else:
            moods = []

        mood_score = _mood_match_score(moods, target_moods)
        category_score = _category_match_score(category_id, target_category)

        # 상품 dict 안에 space 관련 필드가 있다면 활용 (없으면 0점)
        product_space = item.get("space") or item.get("space_ko") or item.get("space_en")
        space_score = _space_match_score(product_space, target_space)

        # 기본 점수 = 무드 + 카테고리 + 공간 + 예산 적합도
        score = 0.0
        score += mood_score          # 최대 2점
        score += category_score      # 최대 2점
        score += space_score         # 최대 1점
        score += budget_score * 1.0  # 최대 1점 정도 비중

        # 가격이 너무 비싸거나 너무 싼 상품에 간단한 페널티(선택 사항)
        # (예: 예산 범위가 없을 때 극단값을 약간 깎기)
        if price_min is None and price_max is None and product_price is not None:
            # 0 ~ 1 사이로 노멀라이즈하는 대신, 너무 큰 값에는 ln 스케일 같은 걸 써도 된다.
            # 여기서는 단순히 "존재하면 살짝 보너스" 정도만 준다.
            score += 0.1

        # 이미 지난 턴에 추천했던 상품이면 약간 페널티
        if pid and pid in last_ids:
            score -= 1.0

        # 점수가 동일할 때 가격이 싼 제품을 약간 더 선호하고 싶다면
        # 가격이 낮을수록 살짝 보너스
        if product_price is not None:
            score += 0.000001 * (-product_price)

        # 계산된 점수를 item에 기록해 둠 (디버깅/로깅 용도)
        item_with_score = dict(item)
        item_with_score["_score"] = score

        scored.append(item_with_score)

    # 점수 높은 순으로 정렬
    # (동점일 경우, 위에서 price 보너스를 음수로 반영했기 때문에
    #  사실상 "점수 같으면 더 싼 상품이 먼저"가 된다.)
    scored.sort(key=lambda x: x.get("_score", 0.0), reverse=True)

    return scored
