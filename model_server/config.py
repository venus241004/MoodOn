# model_server/config.py

from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

ENV_PATH = Path(r"C:\my_envs\.env")
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
VECTOR_DB_DIR = BASE_DIR / "vector_db"

HF_QWEN_MODEL_NAME = "MyeongHo0621/Qwen2.5-14B-Korean"

EMBEDDING_MODEL_NAME = "text-embedding-3-large"
VLM_MODEL_NAME = "Qwen/Qwen2.5-VL-7B-Instruct"

PRODUCTS_JSON_PATH = str(DATA_DIR / "products_all_ver1_vlm.json")
VECTOR_DB_PATH = str(VECTOR_DB_DIR)

# 🔹 NEW: 정제된 무드 사전 경로
MOOD_VOCAB_PATH = DATA_DIR / "mood_keywords_clean.json"

RAG_TOP_K = 20
RECOMMEND_TOP_N = 3
PRICE_TOLERANCE = 1.15
