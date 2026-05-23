from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("STOCK_DATA_DIR", ROOT_DIR / "data"))
DB_PATH = Path(os.getenv("STOCK_DB_PATH", DATA_DIR / "tw_stock_screener.sqlite"))

FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "").strip()
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))
SCAN_LIMIT = int(os.getenv("STOCK_SCAN_LIMIT", "18"))
WATCHLIST_ENV = os.getenv("TW_STOCK_WATCHLIST", "").strip()
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "0").strip() == "1"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "360"))

USER_AGENT = "tw-stock-screener/0.1 (+local research tool)"

DEFAULT_WATCHLIST = [
    {"stock_id": "2330", "name": "台積電", "industry": "半導體", "market": "twse"},
    {"stock_id": "2317", "name": "鴻海", "industry": "其他電子", "market": "twse"},
    {"stock_id": "2454", "name": "聯發科", "industry": "半導體", "market": "twse"},
    {"stock_id": "2303", "name": "聯電", "industry": "半導體", "market": "twse"},
    {"stock_id": "2382", "name": "廣達", "industry": "電腦及週邊", "market": "twse"},
    {"stock_id": "3231", "name": "緯創", "industry": "電腦及週邊", "market": "twse"},
    {"stock_id": "2308", "name": "台達電", "industry": "電子零組件", "market": "twse"},
    {"stock_id": "3711", "name": "日月光投控", "industry": "半導體", "market": "twse"},
    {"stock_id": "3034", "name": "聯詠", "industry": "半導體", "market": "twse"},
    {"stock_id": "2379", "name": "瑞昱", "industry": "半導體", "market": "twse"},
    {"stock_id": "2357", "name": "華碩", "industry": "電腦及週邊", "market": "twse"},
    {"stock_id": "3017", "name": "奇鋐", "industry": "電腦及週邊", "market": "twse"},
    {"stock_id": "2603", "name": "長榮", "industry": "航運", "market": "twse"},
    {"stock_id": "2609", "name": "陽明", "industry": "航運", "market": "twse"},
    {"stock_id": "2615", "name": "萬海", "industry": "航運", "market": "twse"},
    {"stock_id": "2881", "name": "富邦金", "industry": "金融保險", "market": "twse"},
    {"stock_id": "2882", "name": "國泰金", "industry": "金融保險", "market": "twse"},
    {"stock_id": "2891", "name": "中信金", "industry": "金融保險", "market": "twse"},
]


def configured_watchlist() -> list[str]:
    if not WATCHLIST_ENV:
        return []
    return [item.strip() for item in WATCHLIST_ENV.split(",") if item.strip()]
