# main.py — 台股智慧選股系統主程式
# 執行方式：python main.py

import os
import sys
import time
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict

try:
    import colorlog
except ImportError:
    colorlog = None

# ── 設定路徑 ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from config import (
    WEIGHTS, MIN_SCORE_THRESHOLD, TOP_N_STOCKS,
    FILTERS, REQUEST_DELAY, CHIPS_LOOKBACK_DAYS,
)
from fetchers.twse_fetcher import (
    get_stock_list,
    get_stock_history,
    get_institutional_all,
    get_margin_all,
    get_valuation_all,
    get_institutional_history,
)
from analysis import technical, chips, fundamental, sentiment
from scorer import calculate_total_score
import report_generator


# ── 設定 Logger ────────────────────────────────────────────────────────────
def setup_logger():
    if colorlog is not None:
        handler = colorlog.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s [%(levelname)s]%(reset)s %(message)s',
            datefmt='%H:%M:%S',
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'bold_red',
            }
        ))
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S',
        ))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    return logging.getLogger(__name__)


logger = setup_logger()


# ─────────────────────────────────────────────────────────────────────────────
def run_screener(
    quick_mode: bool = False,
    custom_list: List[str] = None,
    return_metadata: bool = False,
) -> List[Dict] | Dict:
    """
    主選股流程
    quick_mode:  True = 僅分析前 100 檔（測試用）
    custom_list: 指定股票清單 ['2330', '2317', ...]
    """
    start_time = time.time()
    today = datetime.today().strftime('%Y%m%d')

    logger.info("=" * 60)
    logger.info("🚀 台股智慧選股系統啟動")
    logger.info(f"   日期：{today} | 最低分數門檻：{MIN_SCORE_THRESHOLD}")
    logger.info("=" * 60)

    # ── Step 1: 取得股票清單 ─────────────────────────────────────────────
    logger.info("📋 Step 1/5 取得上市股票清單...")
    if custom_list:
        stock_df = pd.DataFrame({'stock_id': custom_list, 'name': [''] * len(custom_list)})
    else:
        stock_df = get_stock_list()

    if stock_df.empty:
        logger.error("無法取得股票清單，程式結束")
        if return_metadata:
            return {
                'results': [],
                'scanned_count': 0,
                'candidate_count': 0,
                'qualified_count': 0,
                'report_path': None,
                'market_info': {},
                'elapsed_seconds': round(time.time() - start_time, 1),
                'threshold': MIN_SCORE_THRESHOLD,
            }
        return []

    if quick_mode and not custom_list:
        stock_df = stock_df.head(100)
        logger.warning(f"⚡ 快速模式：只掃描前 100 檔")

    total_stocks = len(stock_df)
    logger.info(f"   共 {total_stocks} 檔股票待掃描")

    # ── Step 2: 取得全市場批次資料（三大法人、融資券、本益比）──────────
    logger.info("📊 Step 2/5 取得全市場批次資料...")
    inst_all  = get_institutional_all(today)
    margin_all = get_margin_all(today)
    val_all   = get_valuation_all(today)

    if inst_all.empty:
        logger.warning("三大法人資料取得失敗（可能非交易日）")
    if val_all.empty:
        logger.warning("本益比資料取得失敗")

    logger.info(f"   三大法人：{len(inst_all)} 筆 | 融資券：{len(margin_all)} 筆 | 本益比：{len(val_all)} 筆")

    # ── Step 3: 初步篩選（快速過濾，減少後續 API 呼叫量）───────────────
    logger.info("🔍 Step 3/5 初步籌碼篩選...")
    candidate_ids = _prefilter_by_chips(stock_df, inst_all)
    logger.info(f"   籌碼初篩後：{len(candidate_ids)} 檔（從 {total_stocks} 檔中篩出）")

    # ── Step 4: 取得大盤情緒 ────────────────────────────────────────────
    logger.info("📰 Step 4/5 分析大盤情緒...")
    market_info = sentiment.get_market_sentiment()
    logger.info(f"   大盤情緒：{market_info['description']}")

    # ── Step 5: 逐檔深度分析 ────────────────────────────────────────────
    logger.info(f"🔬 Step 5/5 開始深度分析 {len(candidate_ids)} 檔股票...")
    results = []

    for i, stock_id in enumerate(candidate_ids, 1):
        name_row = stock_df[stock_df['stock_id'] == stock_id]
        name     = name_row['name'].iloc[0] if not name_row.empty else stock_id

        logger.info(f"   [{i:3d}/{len(candidate_ids)}] 分析 {stock_id} {name}...")

        try:
            result = _analyze_stock(
                stock_id      = stock_id,
                name          = name,
                inst_all      = inst_all,
                margin_all    = margin_all,
                val_all       = val_all,
                market_info   = market_info,
            )
            if result and result['total_score'] >= MIN_SCORE_THRESHOLD:
                results.append(result)
                logger.info(
                    f"   ✅ {stock_id} {name} 總分 {result['total_score']:.1f} "
                    f"[技{result['dimension_scores']['technical']:.0f} "
                    f"籌{result['dimension_scores']['chips']:.0f} "
                    f"基{result['dimension_scores']['fundamental']:.0f} "
                    f"情{result['dimension_scores']['sentiment']:.0f}]"
                )
        except Exception as e:
            logger.warning(f"   ⚠️ {stock_id} 分析失敗: {e}")

    # ── 排序輸出 ──────────────────────────────────────────────────────────
    results.sort(key=lambda x: x['total_score'], reverse=True)
    top_results = results[:TOP_N_STOCKS]

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"🎉 掃描完成！耗時 {elapsed:.0f} 秒")
    logger.info(f"   掃描 {total_stocks} 檔 → 初篩 {len(candidate_ids)} 檔 → 推薦 {len(results)} 檔")
    logger.info("=" * 60)

    # ── 產生 HTML 報告 ────────────────────────────────────────────────────
    report_path = None
    if top_results:
        report_path = report_generator.generate(
            results       = top_results,
            scanned_count = total_stocks,
            market_info   = market_info,
        )
        logger.info(f"📄 HTML 報告：{report_path}")
        _print_summary(top_results)
    else:
        logger.warning("本次掃描無符合條件的股票")

    if return_metadata:
        return {
            'results': top_results,
            'scanned_count': total_stocks,
            'candidate_count': len(candidate_ids),
            'qualified_count': len(results),
            'report_path': report_path,
            'market_info': market_info,
            'elapsed_seconds': round(elapsed, 1),
            'threshold': MIN_SCORE_THRESHOLD,
        }

    return top_results


# ─────────────────────────────────────────────────────────────────────────────
def _prefilter_by_chips(stock_df: pd.DataFrame, inst_all: pd.DataFrame) -> List[str]:
    """
    快速初篩：篩出三大法人合計買超的股票（減少後續 API 呼叫）
    若籌碼資料不可用，回傳全部股票
    """
    if inst_all.empty:
        return stock_df['stock_id'].tolist()

    merged = stock_df.merge(inst_all, on='stock_id', how='left')

    # 條件：三大法人合計買超 OR 至少外資或投信任一買超
    if 'total_net' in merged.columns and 'foreign_net' in merged.columns:
        mask = (
            (merged['total_net'].fillna(0) > 0) |
            (merged['foreign_net'].fillna(0) > 100) |
            (merged['trust_net'].fillna(0) > 0)
        )
        filtered = merged[mask]
    else:
        return stock_df['stock_id'].tolist()

    return filtered['stock_id'].tolist()


# ─────────────────────────────────────────────────────────────────────────────
def _analyze_stock(
    stock_id:    str,
    name:        str,
    inst_all:    pd.DataFrame,
    margin_all:  pd.DataFrame,
    val_all:     pd.DataFrame,
    market_info: dict,
) -> Dict:
    """對單一股票執行完整分析並計算總分"""

    # ── 技術面 ────────────────────────────────────────────────────────────
    price_history = get_stock_history(stock_id)
    tech_result   = technical.analyze(price_history)

    # 取得最新收盤價
    latest_price = None
    if price_history is not None and not price_history.empty:
        latest_price = price_history['close'].iloc[-1]

    # ── 籌碼面 ────────────────────────────────────────────────────────────
    inst_today = (
        inst_all[inst_all['stock_id'] == stock_id].iloc[0]
        if not inst_all.empty and stock_id in inst_all['stock_id'].values
        else pd.Series()
    )
    margin_today = (
        margin_all[margin_all['stock_id'] == stock_id].iloc[0]
        if not margin_all.empty and stock_id in margin_all['stock_id'].values
        else pd.Series()
    )
    # 近 N 日籌碼歷史（僅在籌碼初評較好時才抓，節省 API）
    inst_history = pd.DataFrame()
    if not inst_today.empty:
        inst_history = get_institutional_history(stock_id, CHIPS_LOOKBACK_DAYS)

    chips_result = chips.analyze(inst_today, inst_history, margin_today)

    # ── 基本面 ────────────────────────────────────────────────────────────
    val_row = (
        val_all[val_all['stock_id'] == stock_id].iloc[0]
        if not val_all.empty and stock_id in val_all['stock_id'].values
        else pd.Series()
    )
    fund_result = fundamental.analyze(val_row)

    # ── 情緒面 ────────────────────────────────────────────────────────────
    sent_result = sentiment.analyze(stock_id, name)

    # ── 計算總分 ──────────────────────────────────────────────────────────
    score_result = calculate_total_score(
        tech_result   = tech_result,
        chips_result  = chips_result,
        fund_result   = fund_result,
        sent_result   = sent_result,
        market_multiplier = market_info.get('score_multiplier', 1.0),
    )

    return {
        'stock_id':        stock_id,
        'name':            name,
        'price':           latest_price,
        'total_score':     score_result['total_score'],
        'grade':           score_result['grade'],
        'dimension_scores': score_result['dimension_scores'],
        'market_adj':      score_result['market_adj'],
        # 各維度訊號（給報告使用）
        'tech_signals':    tech_result.get('signals', {}),
        'chips_signals':   chips_result.get('signals', {}),
        'fund_signals':    fund_result.get('signals', {}),
        'sent_signals':    sent_result.get('signals', {}),
        # 詳細數值
        'tech_detail':     tech_result.get('detail', {}),
        'chips_detail':    chips_result.get('detail', {}),
        'fund_detail':     fund_result.get('detail', {}),
    }


# ─────────────────────────────────────────────────────────────────────────────
def _print_summary(results: List[Dict]):
    """在 Console 印出選股結果摘要"""
    print("\n" + "═" * 70)
    print(f"  🏆 今日推薦標的 Top {len(results)}")
    print("═" * 70)
    print(f"  {'排名':<4} {'代號':<6} {'名稱':<12} {'總分':<6} "
          f"{'技術':<5} {'籌碼':<5} {'基本':<5} {'情緒':<5} 評級")
    print("─" * 70)
    for i, s in enumerate(results, 1):
        ds = s['dimension_scores']
        print(
            f"  {i:<4} {s['stock_id']:<6} {s['name'][:10]:<12} "
            f"{s['total_score']:<6.1f} "
            f"{ds['technical']:<5.0f} {ds['chips']:<5.0f} "
            f"{ds['fundamental']:<5.0f} {ds['sentiment']:<5.0f} "
            f"{s['grade']['emoji']} {s['grade']['label']}"
        )
    print("═" * 70 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='台股智慧選股系統')
    parser.add_argument('--quick',   action='store_true', help='快速模式（只掃描前100檔）')
    parser.add_argument('--stocks',  nargs='+',           help='指定股票清單，如 2330 2317 2454')
    parser.add_argument('--threshold', type=int, default=MIN_SCORE_THRESHOLD, help=f'最低分數門檻（預設 {MIN_SCORE_THRESHOLD}）')
    args = parser.parse_args()

    # 覆寫門檻
    import config
    config.MIN_SCORE_THRESHOLD = args.threshold
    MIN_SCORE_THRESHOLD = args.threshold
    report_generator.MIN_SCORE_THRESHOLD = args.threshold

    run_screener(
        quick_mode  = args.quick,
        custom_list = args.stocks,
    )
