# fetchers/twse_fetcher.py — 台灣證交所資料抓取模組

import time
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import (
    REQUEST_DELAY, REQUEST_TIMEOUT, MAX_RETRIES,
    ENDPOINTS, STOCK_LIST_URL, LOOKBACK_MONTHS
)

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/html, */*',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Referer': 'https://www.twse.com.tw/',
}


def _get(url: str, params: dict = None) -> Optional[dict]:
    """帶重試機制的 GET 請求"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                url, params=params, headers=HEADERS,
                timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            time.sleep(REQUEST_DELAY)
            return resp.json()
        except requests.exceptions.JSONDecodeError:
            return {'raw': resp.text}
        except Exception as e:
            logger.warning(f"請求失敗（第 {attempt+1} 次）: {url} → {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(REQUEST_DELAY * 2)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# 1. 取得上市股票清單
# ──────────────────────────────────────────────────────────────────────────────
def get_stock_list() -> pd.DataFrame:
    """
    從 TWSE ISIN 頁面取得所有上市股票清單
    回傳欄位：stock_id, name, type
    """
    try:
        resp = requests.get(STOCK_LIST_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.encoding = 'big5'
        soup = BeautifulSoup(resp.text, 'lxml')
        rows = soup.find_all('tr')

        stocks = []
        current_type = ''
        for row in rows:
            cells = row.find_all('td')
            if not cells:
                continue
            text = cells[0].get_text(strip=True)

            # 判斷類型分隔行
            if '上市' in text and len(text) < 20:
                if '普通股' in text:
                    current_type = '普通股'
                continue
            if '上市' not in text and '上櫃' not in text and len(cells) >= 3:
                if current_type == '普通股' and len(text) > 4:
                    parts = text.split('\u3000')  # 全形空格
                    if len(parts) >= 2:
                        stock_id = parts[0].strip()
                        name     = parts[1].strip()
                        if stock_id.isdigit() and len(stock_id) == 4:
                            stocks.append({
                                'stock_id': stock_id,
                                'name':     name,
                                'type':     current_type,
                            })
        df = pd.DataFrame(stocks).drop_duplicates('stock_id')
        logger.info(f"取得上市普通股共 {len(df)} 檔")
        return df
    except Exception as e:
        logger.error(f"取得股票清單失敗: {e}")
        # 備用：使用 twstock
        return _get_stock_list_from_twstock()


def _get_stock_list_from_twstock() -> pd.DataFrame:
    """備用：從 twstock 取得股票清單"""
    try:
        import twstock
        records = []
        for code, info in twstock.codes.items():
            if (getattr(info, 'market', '') == '上市'
                    and getattr(info, 'type', '') == '普通股'):
                records.append({
                    'stock_id': code,
                    'name':     info.name,
                    'type':     info.type,
                })
        df = pd.DataFrame(records)
        logger.info(f"[備用] 從 twstock 取得 {len(df)} 檔股票")
        return df
    except Exception as e:
        logger.error(f"twstock 備用方案也失敗: {e}")
        return pd.DataFrame(columns=['stock_id', 'name', 'type'])


# ──────────────────────────────────────────────────────────────────────────────
# 2. 取得個股歷史 K 線資料
# ──────────────────────────────────────────────────────────────────────────────
def get_stock_history(stock_id: str, months: int = None) -> pd.DataFrame:
    """
    取得個股月成交資訊（TWSE），組合成 LOOKBACK_MONTHS 個月的日K資料
    回傳欄位：date, open, high, low, close, volume
    """
    if months is None:
        months = LOOKBACK_MONTHS

    all_data = []
    today    = datetime.today()

    for i in range(months):
        dt   = today - timedelta(days=30 * i)
        date = dt.strftime('%Y%m%d')
        data = _get(ENDPOINTS['stock_day'], params={
            'response': 'json',
            'stockNo':  stock_id,
            'date':     date,
        })
        if not data or data.get('stat') != 'OK':
            continue

        fields = data.get('fields', [])
        rows   = data.get('data', [])
        try:
            df = pd.DataFrame(rows, columns=fields)
            df = df.rename(columns={
                '日期': 'date', '開盤價': 'open', '最高價': 'high',
                '最低價': 'low', '收盤價': 'close', '成交股數': 'volume',
                '成交金額': 'amount', '成交筆數': 'trades',
            })
            # 清洗數字
            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(',', ''), errors='coerce'
                )
            df['volume'] = (
                pd.to_numeric(
                    df['volume'].astype(str).str.replace(',', ''), errors='coerce'
                ) / 1000  # 轉換為「張」
            )
            df['date'] = pd.to_datetime(
                df['date'].apply(_roc_to_ad), errors='coerce'
            )
            df = df.dropna(subset=['date', 'close'])
            all_data.append(df)
        except Exception as e:
            logger.debug(f"解析 {stock_id} {date} 資料失敗: {e}")

    if not all_data:
        return pd.DataFrame()

    result = pd.concat(all_data).drop_duplicates('date').sort_values('date').reset_index(drop=True)
    return result


def _roc_to_ad(roc_date: str) -> str:
    """民國年轉西元年：'113/01/02' → '2024/01/02'"""
    try:
        parts = roc_date.split('/')
        year  = int(parts[0]) + 1911
        return f"{year}/{parts[1]}/{parts[2]}"
    except Exception:
        return roc_date


# ──────────────────────────────────────────────────────────────────────────────
# 3. 取得三大法人買賣超（全市場，單日）
# ──────────────────────────────────────────────────────────────────────────────
def get_institutional_all(date: str = None) -> pd.DataFrame:
    """
    取得特定日期所有上市股票的三大法人買賣超（千元）
    date 格式：'YYYYMMDD'，預設今日
    回傳欄位：stock_id, foreign_net, trust_net, dealer_net, total_net
    """
    if not date:
        date = datetime.today().strftime('%Y%m%d')

    data = _get(ENDPOINTS['institutional'], params={
        'response':   'json',
        'date':       date,
        'selectType': 'ALLBUT0999',
    })

    if not data or data.get('stat') != 'OK':
        logger.warning(f"三大法人資料 {date} 取得失敗")
        return pd.DataFrame()

    fields = data.get('fields', [])
    rows   = data.get('data', [])
    try:
        df = pd.DataFrame(rows, columns=fields)
        df = df.rename(columns={
            '證券代號':              'stock_id',
            '外陸資買賣超股數(不含外資自營商)': 'foreign_net',
            '投信買賣超股數':           'trust_net',
            '自營商買賣超股數':          'dealer_net',
            '三大法人買賣超股數':         'total_net',
        })
        # 保留必要欄位
        keep = ['stock_id', 'foreign_net', 'trust_net', 'dealer_net', 'total_net']
        existing = [c for c in keep if c in df.columns]
        df = df[existing].copy()
        for col in existing[1:]:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(',', ''), errors='coerce'
            ).fillna(0) / 1000  # 股 → 張
        df['stock_id'] = df['stock_id'].astype(str).str.strip()
        return df
    except Exception as e:
        logger.error(f"解析三大法人資料失敗: {e}")
        return pd.DataFrame()


# ──────────────────────────────────────────────────────────────────────────────
# 4. 取得融資融券（全市場，單日）
# ──────────────────────────────────────────────────────────────────────────────
def get_margin_all(date: str = None) -> pd.DataFrame:
    """
    取得特定日期所有股票的融資融券餘額
    回傳欄位：stock_id, margin_balance, short_balance, margin_change
    """
    if not date:
        date = datetime.today().strftime('%Y%m%d')

    data = _get(ENDPOINTS['margin'], params={
        'response':   'json',
        'date':       date,
        'selectType': 'ALL',
    })

    if not data or data.get('stat') != 'OK':
        logger.warning(f"融資融券資料 {date} 取得失敗")
        return pd.DataFrame()

    try:
        fields = data.get('fields', [])
        rows   = data.get('data', [])
        df     = pd.DataFrame(rows, columns=fields)

        # 欄位名稱因版本而異，嘗試幾種可能
        rename_map = {}
        for col in df.columns:
            if '代號' in col or '代碼' in col:
                rename_map[col] = 'stock_id'
            elif '融資' in col and '餘額' in col and '變化' not in col:
                rename_map[col] = 'margin_balance'
            elif '融資' in col and '增減' in col:
                rename_map[col] = 'margin_change'
            elif '融券' in col and '餘額' in col:
                rename_map[col] = 'short_balance'
        df = df.rename(columns=rename_map)

        keep = [c for c in ['stock_id', 'margin_balance', 'short_balance', 'margin_change'] if c in df.columns]
        df = df[keep].copy()
        for col in keep[1:]:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(',', ''), errors='coerce'
            ).fillna(0)
        df['stock_id'] = df['stock_id'].astype(str).str.strip()
        return df
    except Exception as e:
        logger.error(f"解析融資融券資料失敗: {e}")
        return pd.DataFrame()


# ──────────────────────────────────────────────────────────────────────────────
# 5. 取得本益比、殖利率、淨值比（全市場）
# ──────────────────────────────────────────────────────────────────────────────
def get_valuation_all(date: str = None) -> pd.DataFrame:
    """
    取得全市場本益比（PER）、殖利率（Yield）、股價淨值比（PBR）
    回傳欄位：stock_id, per, yield_pct, pbr
    """
    if not date:
        date = datetime.today().strftime('%Y%m%d')

    data = _get(ENDPOINTS['valuation'], params={
        'response':   'json',
        'date':       date,
        'selectType': 'ALL',
    })

    if not data or data.get('stat') != 'OK':
        logger.warning(f"本益比資料 {date} 取得失敗")
        return pd.DataFrame()

    try:
        fields = data.get('fields', [])
        rows   = data.get('data', [])
        df     = pd.DataFrame(rows, columns=fields)

        rename_map = {}
        for col in df.columns:
            if '代號' in col or '代碼' in col:
                rename_map[col] = 'stock_id'
            elif '本益比' in col:
                rename_map[col] = 'per'
            elif '殖利率' in col:
                rename_map[col] = 'yield_pct'
            elif '股價淨值比' in col:
                rename_map[col] = 'pbr'
        df = df.rename(columns=rename_map)

        keep = [c for c in ['stock_id', 'per', 'yield_pct', 'pbr'] if c in df.columns]
        df = df[keep].copy()
        for col in keep[1:]:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(',', ''), errors='coerce'
            )
        df['stock_id'] = df['stock_id'].astype(str).str.strip()
        # 過濾掉本益比異常值（負值或超高）
        if 'per' in df.columns:
            df = df[(df['per'] > 0) & (df['per'] < 200)]
        return df
    except Exception as e:
        logger.error(f"解析本益比資料失敗: {e}")
        return pd.DataFrame()


# ──────────────────────────────────────────────────────────────────────────────
# 6. 取得多日三大法人資料（用於趨勢分析）
# ──────────────────────────────────────────────────────────────────────────────
def get_institutional_history(stock_id: str, days: int = 10) -> pd.DataFrame:
    """
    取得單一股票近 N 個交易日的三大法人資料
    透過抓取近幾個日期的全市場資料，再篩選出特定股票
    """
    results = []
    today   = datetime.today()

    checked = 0
    offset  = 0
    while checked < days and offset < days + 10:
        dt   = today - timedelta(days=offset)
        offset += 1
        # 跳過假日（週六、週日）
        if dt.weekday() >= 5:
            continue

        date = dt.strftime('%Y%m%d')
        df   = get_institutional_all(date)
        if df.empty:
            continue

        row = df[df['stock_id'] == stock_id]
        if not row.empty:
            row = row.copy()
            row['date'] = dt.date()
            results.append(row)
        checked += 1

    if not results:
        return pd.DataFrame()
    return pd.concat(results).sort_values('date').reset_index(drop=True)
