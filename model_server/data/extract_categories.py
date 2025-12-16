# extract_categories.py
import json
import re
from collections import Counter
from pathlib import Path

JSON_PATH = r"C:\my_python\Final_Project\data\products_all_ver1_vlm.json"
OUT_RAW_TXT = r"C:\my_python\Final_Project\data\mood_keywords_raw.txt"
OUT_CLEAN_JSON = r"C:\my_python\Final_Project\data\mood_keywords_clean.json"

# 한글 여부 체크용
HANGUL_RANGE = ("\uac00", "\ud7a3")

def count_hangul_and_alpha(s: str):
    hangul = 0
    alpha_other = 0
    for ch in s:
        if HANGUL_RANGE[0] <= ch <= HANGUL_RANGE[1]:
            hangul += 1
        elif ch.isalpha():  # 라틴, 키릴, 한자 등
            alpha_other += 1
    return hangul, alpha_other


def is_korean_dominant(keyword: str, min_hangul: int = 1) -> bool:
    """
    - 한글 문자가 최소 min_hangul 개 이상
    - 그리고 한글 수 >= 기타 알파벳 수
    """
    hangul, other = count_hangul_and_alpha(keyword)
    if hangul < min_hangul:
        return False
    return hangul >= other


def normalize_keyword(s: str) -> str:
    """
    간단 정규화:
    - 앞뒤 공백 제거
    - 중복 공백 제거
    - 필요하면 여기서 '톤' / '함' / '한' 같은 접미사 줄이는 것도 가능 (지금은 보수적으로)
    """
    s = s.strip()
    # 전각/특수 공백 치환
    s = re.sub(r"\s+", " ", s)
    return s


def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    counter = Counter()

    for item in data:
        mk = item.get("mood_keywords", None)
        if mk is None:
            continue

        if isinstance(mk, str):
            parts = [p.strip() for p in mk.replace("||", ",").split(",") if p.strip()]
        elif isinstance(mk, list):
            parts = [str(p).strip() for p in mk if str(p).strip()]
        else:
            continue

        for p in parts:
            norm = normalize_keyword(p)
            if norm:
                counter[norm] += 1

    # 1) raw 리스트 출력 (디버그용)
    unique_keywords = sorted(counter.keys())
    print("총 무드 키워드 개수(중복 제거):", len(unique_keywords))
    print("===================================")
    for k in unique_keywords:
        print(k)

    # 파일로도 저장
    Path(OUT_RAW_TXT).write_text(
        "\n".join(unique_keywords),
        encoding="utf-8",
    )

    # 2) 한글 위주 + 최소 빈도 기준으로 필터링
    clean_keywords = []
    for kw, freq in counter.most_common():
        # (옵션) 너무 희귀한 건 버리기 (예: 1~2번만 등장)
        if freq < 2:
            continue

        if not is_korean_dominant(kw):
            # 디버그 보고 싶으면 주석 해제
            # print("[DROP non-korean]", kw, freq)
            continue

        clean_keywords.append({"keyword": kw, "freq": freq})

    print("\n[정제 후 무드 키워드 개수]:", len(clean_keywords))

    # JSON로 저장
    with open(OUT_CLEAN_JSON, "w", encoding="utf-8") as f:
        json.dump(clean_keywords, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
