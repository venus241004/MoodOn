# db/init_rds_from_json.py

import json
from pathlib import Path

import pymysql

# =========================
# 1. 경로 / RDS 설정
# =========================

# Final_Project/data/products_all_ver1_vlm.json 기준 예시
BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCTS_JSON_PATH = BASE_DIR / "data" / "products_all_ver1_vlm.json"

RDS_HOST = "127.0.0.1"
RDS_PORT = 3306
RDS_DB   = "moodon"
RDS_USER = "root"
RDS_PASSWORD = "141004"


def get_conn():
    return pymysql.connect(
        host=RDS_HOST,
        port=RDS_PORT,
        user=RDS_USER,
        password=RDS_PASSWORD,
        database=RDS_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


# =========================
# 2. 헬퍼 함수들 (upsert)
# =========================

def upsert_category(cur, category_name: str) -> int:
    """product_category에 category_name을 추가하고 category_id를 리턴."""
    cur.execute(
        "SELECT category_id FROM product_category WHERE category_name=%s",
        (category_name,),
    )
    row = cur.fetchone()
    if row:
        return row["category_id"]

    cur.execute(
        "INSERT INTO product_category (category_name) VALUES (%s)",
        (category_name,),
    )
    return cur.lastrowid


def upsert_mood(cur, mood_name: str) -> int:
    """mood 테이블 upsert."""
    cur.execute(
        "SELECT mood_id FROM mood WHERE mood_name=%s",
        (mood_name,),
    )
    row = cur.fetchone()
    if row:
        return row["mood_id"]

    cur.execute(
        "INSERT INTO mood (mood_name) VALUES (%s)",
        (mood_name,),
    )
    return cur.lastrowid


def upsert_product(cur, item: dict, category_id: int) -> int:
    """
    JSON 한 건을 product 테이블에 upsert.
    - source_product_id = item["product_id"]
    - price는 int로 캐스팅
    """
    source_id = item.get("product_id")
    brand_name = item.get("brand_name") or ""
    product_name = item.get("product_name") or ""
    link_url = item.get("link_url")
    image_url = item.get("image_url")
    s3_path = item.get("s3_path")
    s3_url = item.get("s3_url")

    price_raw = item.get("price")
    try:
        price = int(str(price_raw).replace(",", "")) if price_raw is not None else None
    except ValueError:
        price = None

    # 기존 row 여부 확인
    cur.execute(
        "SELECT product_id FROM product WHERE source_product_id=%s",
        (source_id,),
    )
    row = cur.fetchone()

    if row:
        product_id = row["product_id"]
        cur.execute(
            """
            UPDATE product
               SET category_id=%s,
                   brand_name=%s,
                   product_name=%s,
                   link_url=%s,
                   image_url=%s,
                   s3_path=%s,
                   s3_url=%s,
                   price=%s
             WHERE product_id=%s
            """,
            (
                category_id,
                brand_name,
                product_name,
                link_url,
                image_url,
                s3_path,
                s3_url,
                price,
                product_id,
            ),
        )
        return product_id

    # 신규 insert
    cur.execute(
        """
        INSERT INTO product (
            source_product_id,
            category_id,
            brand_name,
            product_name,
            link_url,
            image_url,
            s3_path,
            s3_url,
            price,
            created_at
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, CURDATE())
        """,
        (
            source_id,
            category_id,
            brand_name,
            product_name,
            link_url,
            image_url,
            s3_path,
            s3_url,
            price,
        ),
    )
    return cur.lastrowid


def upsert_product_mood(cur, product_id: int, mood_id: int) -> None:
    """product_mood 테이블 upsert."""
    cur.execute(
        """
        SELECT product_mood_id FROM product_mood
         WHERE product_id=%s AND mood_id=%s
        """,
        (product_id, mood_id),
    )
    row = cur.fetchone()
    if row:
        return

    cur.execute(
        """
        INSERT INTO product_mood (product_id, mood_id)
        VALUES (%s, %s)
        """,
        (product_id, mood_id),
    )


def upsert_product_detail(cur, product_id: int, item: dict) -> None:
    """product_detail.parsed_json에 전체 JSON 저장."""
    json_str = json.dumps(item, ensure_ascii=False)

    cur.execute(
        "SELECT product_detail_id FROM product_detail WHERE product_id=%s",
        (product_id,),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            """
            UPDATE product_detail
               SET parsed_json=%s
             WHERE product_id=%s
            """,
            (json_str, product_id),
        )
    else:
        cur.execute(
            """
            INSERT INTO product_detail (product_id, parsed_json)
            VALUES (%s, %s)
            """,
            (product_id, json_str),
        )


# =========================
# 3. 메인 로직
# =========================

def main():
    print(f"[INFO] Loading JSON from: {PRODUCTS_JSON_PATH}")
    with open(PRODUCTS_JSON_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for idx, item in enumerate(items, start=1):
                category_name = item.get("category_id") or "기타"
                mood_category = item.get("mood_category") or "기타"

                category_id = upsert_category(cur, category_name)
                mood_id = upsert_mood(cur, mood_category)
                product_id = upsert_product(cur, item, category_id)
                upsert_product_mood(cur, product_id, mood_id)
                upsert_product_detail(cur, product_id, item)

                if idx % 100 == 0:
                    conn.commit()
                    print(f"[INFO] processed {idx} items...")

        conn.commit()
        print(f"[DONE] imported {len(items)} products into RDS.")

    except Exception as e:
        conn.rollback()
        print("[ERROR]", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
