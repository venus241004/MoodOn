# mood_vocab.py
"""
정제된 무드 사전(mood_keywords_clean.json)을 기반으로:
 - 전역 무드 집합(KNOWN_MOODS) 제공
 - LLM/VLM이 뽑은 free-form 무드를 표준 키워드로 스냅(snap)
 - 사용자 문장 안에서 무드 키워드를 직접 탐지

파일 포맷 예시 (mood_keywords_clean.json):
[
  { "keyword": "아늑한", "freq": 123 },
  { "keyword": "우드톤", "freq": 87 },
  ...
]
"""

from __future__ import annotations

import json
import difflib
from pathlib import Path
from typing import List, Tuple, Set

from config import MOOD_VOCAB_PATH


_MOOD_VOCAB: List[str] | None = None
_MOOD_SET: Set[str] | None = None


def _load_vocab() -> List[str]:
    """JSON 파일에서 정제된 무드 키워드를 로딩."""
    global _MOOD_VOCAB, _MOOD_SET  # type: ignore[name-defined]

    if _MOOD_VOCAB is not None:  # type: ignore[name-defined]
        return _MOOD_VOCAB  # type: ignore[name-defined]

    path = Path(MOOD_VOCAB_PATH)
    if not path.is_file():
        _MOOD_VOCAB = []  # type: ignore[name-defined]
        _MOOD_SET = set()
        return _MOOD_VOCAB  # type: ignore[name-defined]

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # freq 내림차순 정렬 (자주 등장하는 무드를 먼저 두기)
    data.sort(key=lambda x: int(x.get("freq", 0)), reverse=True)

    vocab = [
        str(x.get("keyword", "")).strip()
        for x in data
        if str(x.get("keyword", "")).strip()
    ]
    _MOOD_VOCAB = vocab  # type: ignore[name-defined]
    _MOOD_SET = set(vocab)
    return _MOOD_VOCAB  # type: ignore[name-defined]


def get_mood_vocab() -> List[str]:
    """정제된 무드 키워드 리스트."""
    return list(_load_vocab())


def get_mood_vocab_set() -> Set[str]:
    """정제된 무드 키워드 집합."""
    global _MOOD_SET
    if _MOOD_SET is None:
        _load_vocab()
    return set(_MOOD_SET or [])


def snap_moods_to_vocab(
    raw_moods: List[str],
    min_similarity: float = 0.72,
) -> Tuple[List[str], List[str]]:
    """
    free-form 무드 리스트 → 정제된 사전 키워드로 스냅.

    Args:
        raw_moods: LLM/VLM/사용자가 준 무드 문자열 리스트
        min_similarity: difflib 유사도 컷오프 (0~1)

    Returns:
        canonical_moods: 표준 키워드로 정규화된 무드 리스트(중복 제거)
        unknown_moods: 사전 어디에도 매칭 안 된 원래 표현들
    """
    vocab = get_mood_vocab()
    vocab_set = get_mood_vocab_set()

    canonical: List[str] = []
    unknown: List[str] = []
    seen = set()

    for m in raw_moods:
        s = str(m).strip()
        if not s:
            continue

        # (1) 정확 일치
        if s in vocab_set:
            if s not in seen:
                canonical.append(s)
                seen.add(s)
            continue

        # (2) 유사도 매칭 (예: "따뜻한 느낌" → "따뜻한")
        match = difflib.get_close_matches(s, vocab, n=1, cutoff=min_similarity)
        if match:
            cand = match[0]
            if cand not in seen:
                canonical.append(cand)
                seen.add(cand)
        else:
            unknown.append(s)

    return canonical, unknown


def match_moods_in_text(text: str) -> List[str]:
    """
    한글 문장 안에서 사전에 존재하는 무드 키워드를
    단순 부분 문자열로 탐지.

    예: "따뜻하고 아늑한 우드톤 방"
      → ["따뜻한", "아늑한", "우드톤"] (사전에 있다면)
    """
    text = str(text)
    if not text:
        return []

    vocab = get_mood_vocab()
    found: List[str] = []
    seen = set()

    for kw in vocab:
        if kw and kw in text and kw not in seen:
            found.append(kw)
            seen.add(kw)

    return found
