# analysis/sentiment.py — 市場情緒分析模組
# 抓取鉅亨網、Yahoo Finance TW 新聞，做關鍵字情緒分析

import logging
import requests
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from typing import List, Tuple

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}


def analyze(stock_id: str, stock_name: str) -> dict:
    """
    抓取個股相關新聞，分析情緒，輸出 0–100 分
    """
    result = {
        'score':   50,  # 預設中性分
        'signals': {},
        'detail':  {},
    }

    try:
        news_items = _fetch_news(stock_id, stock_name)
        if not news_items:
            result['signals']['news'] = '⚠️ 無法取得新聞資料，給予中性分數'
            return result

        pos_count, neg_count, pos_news, neg_news = _score_news(news_items)
        total_news = len(news_items)

        result['detail']['total_news']  = total_news
        result['detail']['positive']    = pos_count
        result['detail']['negative']    = neg_count
        result['detail']['sample_news'] = [title for title, _ in news_items[:5]]

        # 計算情緒分數
        if total_news == 0:
            score = 50
        else:
            net_sentiment = (pos_count - neg_count) / max(total_news, 1)
            # 映射到 0–100
            score = 50 + net_sentiment * 50
            score = max(0, min(100, score))

        result['score'] = round(score, 1)

        # 產生訊號說明
        if pos_count > neg_count:
            result['signals']['news'] = (
                f'✅ 近期新聞偏正面（正面 {pos_count} 則，負面 {neg_count} 則）'
            )
            if pos_news:
                result['signals']['positive_sample'] = f'範例：{pos_news[0][:30]}...'
        elif neg_count > pos_count:
            result['signals']['news'] = (
                f'❌ 近期新聞偏負面（負面 {neg_count} 則，正面 {pos_count} 則）'
            )
            if neg_news:
                result['signals']['negative_sample'] = f'範例：{neg_news[0][:30]}...'
        else:
            result['signals']['news'] = (
                f'⚠️ 新聞情緒中性（共 {total_news} 則）'
            )

    except Exception as e:
        logger.warning(f"情緒分析失敗 {stock_id}: {e}")
        result['signals']['news'] = '⚠️ 情緒分析發生錯誤，給予中性分數'

    return result


# ─────────────────────────────────────────────────────────────────────────────
def _fetch_news(stock_id: str, stock_name: str) -> List[Tuple[str, str]]:
    """
    從多個來源抓取個股新聞
    回傳 [(標題, 日期), ...]
    """
    news = []

    # 1. 鉅亨網個股新聞
    news += _fetch_cnyes(stock_id, stock_name)

    # 2. Yahoo Finance TW 搜尋
    news += _fetch_yahoo_tw(stock_id, stock_name)

    # 去除重複標題
    seen = set()
    unique = []
    for title, date in news:
        if title not in seen:
            seen.add(title)
            unique.append((title, date))

    logger.debug(f"{stock_id} {stock_name} 取得 {len(unique)} 則新聞")
    return unique[:30]  # 最多 30 則


def _fetch_cnyes(stock_id: str, stock_name: str) -> List[Tuple[str, str]]:
    """抓取鉅亨網個股新聞"""
    news = []
    try:
        url = f'https://news.cnyes.com/news/cat/tw_stock_news?stock={stock_id}'
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(resp.text, 'lxml')

        # 嘗試多種選擇器
        for selector in ['h3.sc-1daag2h-2', 'a.c-listItem__title', '.news-title', 'h3']:
            items = soup.select(selector)
            if items:
                for item in items[:15]:
                    title = item.get_text(strip=True)
                    if len(title) > 5:
                        news.append((title, ''))
                break
    except Exception as e:
        logger.debug(f"鉅亨網抓取失敗: {e}")
    return news


def _fetch_yahoo_tw(stock_id: str, stock_name: str) -> List[Tuple[str, str]]:
    """抓取 Yahoo Finance TW 新聞"""
    news = []
    try:
        # Yahoo Finance TW search
        query = f'{stock_id} {stock_name}'
        url   = f'https://tw.stock.yahoo.com/quote/{stock_id}.TW/news'
        resp  = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        soup  = BeautifulSoup(resp.text, 'lxml')

        for selector in ['h3.Mb\(5px\)', 'li[class*="StreamMegaItem"] h3', 'h3', 'a[class*="newsTitle"]']:
            items = soup.select(selector)
            if items:
                for item in items[:15]:
                    title = item.get_text(strip=True)
                    if len(title) > 5 and (stock_name in title or stock_id in title or _is_general_market_news(title)):
                        news.append((title, ''))
                break
    except Exception as e:
        logger.debug(f"Yahoo TW 抓取失敗: {e}")
    return news


def _is_general_market_news(title: str) -> bool:
    """判斷是否為一般市場新聞（不一定含股票名稱）"""
    market_words = ['大盤', '台股', '加權', '法人', '外資', '主力', '盤勢']
    return any(w in title for w in market_words)


def _score_news(news_items: List[Tuple[str, str]]) -> Tuple[int, int, List[str], List[str]]:
    """
    對新聞標題做關鍵字情緒分析
    回傳：(正面數, 負面數, 正面標題清單, 負面標題清單)
    """
    pos_count = 0
    neg_count = 0
    pos_news  = []
    neg_news  = []

    for title, _ in news_items:
        pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in title)
        neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in title)

        if pos > neg:
            pos_count += 1
            pos_news.append(title)
        elif neg > pos:
            neg_count += 1
            neg_news.append(title)
        # neutral → 不計

    return pos_count, neg_count, pos_news, neg_news


# ─────────────────────────────────────────────────────────────────────────────
# 大盤情緒（影響全市場推薦強度）
# ─────────────────────────────────────────────────────────────────────────────
def get_market_sentiment() -> dict:
    """
    分析大盤整體情緒
    回傳：{
        'sentiment': 'bullish' | 'neutral' | 'bearish',
        'score_multiplier': 0.8–1.2,
        'description': str,
    }
    """
    try:
        # 抓取台股大盤新聞
        url  = 'https://news.cnyes.com/news/cat/tw_stock'
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(resp.text, 'lxml')

        titles = []
        for item in soup.select('h3, .news-title, a')[:30]:
            text = item.get_text(strip=True)
            if len(text) > 5:
                titles.append(text)

        pos = sum(1 for t in titles for kw in POSITIVE_KEYWORDS if kw in t)
        neg = sum(1 for t in titles for kw in NEGATIVE_KEYWORDS if kw in t)

        if pos > neg * 1.5:
            return {
                'sentiment':         'bullish',
                'score_multiplier':  1.1,
                'description':       f'大盤情緒偏多（正面 {pos}，負面 {neg}）',
            }
        elif neg > pos * 1.5:
            return {
                'sentiment':         'bearish',
                'score_multiplier':  0.85,
                'description':       f'大盤情緒偏空（負面 {neg}，正面 {pos}），推薦強度降低',
            }
        else:
            return {
                'sentiment':         'neutral',
                'score_multiplier':  1.0,
                'description':       f'大盤情緒中性（正面 {pos}，負面 {neg}）',
            }
    except Exception as e:
        logger.warning(f"大盤情緒分析失敗: {e}")
        return {'sentiment': 'neutral', 'score_multiplier': 1.0, 'description': '大盤情緒分析失敗，使用中性'}
