# analysis/chips.py — 籌碼面分析模組
# 分析三大法人、融資融券，給出 0–100 分

import logging
import pandas as pd
import numpy as np

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import CHIPS_LOOKBACK_DAYS

logger = logging.getLogger(__name__)


def analyze(
    institutional_today: pd.Series,
    institutional_history: pd.DataFrame,
    margin_today: pd.Series,
) -> dict:
    """
    輸入：
      institutional_today   — 今日該股三大法人（Series）
      institutional_history — 近 N 日三大法人 DataFrame
      margin_today          — 今日該股融資融券（Series）
    輸出：{
        'score': 0–100,
        'signals': {指標: 說明},
        'detail': {指標: 數值},
    }
    """
    result = {'score': 0, 'signals': {}, 'detail': {}}
    scores = []

    # ── 1. 外資分析（35分）─────────────────────────────────────────────
    foreign_score = _analyze_foreign(institutional_today, institutional_history, result)
    scores.append(('外資', foreign_score, 35))

    # ── 2. 投信分析（35分）─────────────────────────────────────────────
    trust_score = _analyze_trust(institutional_today, institutional_history, result)
    scores.append(('投信', trust_score, 35))

    # ── 3. 融資融券分析（30分）──────────────────────────────────────────
    margin_score = _analyze_margin(margin_today, result)
    scores.append(('融資券', margin_score, 30))

    total = sum(s * w / 100 for _, s, w in scores)
    result['score']     = round(min(100, max(0, total)), 1)
    result['breakdown'] = {name: {'score': s, 'weight': w} for name, s, w in scores}
    return result


# ─────────────────────────────────────────────────────────────────────────────
def _analyze_foreign(today: pd.Series, history: pd.DataFrame, result: dict) -> float:
    """外資買賣超分析"""
    score   = 0
    signals = result['signals']
    detail  = result['detail']

    try:
        foreign_today = float(today.get('foreign_net', 0)) if not pd.isna(today.get('foreign_net', np.nan)) else 0
        detail['foreign_today'] = round(foreign_today, 0)

        # 今日買超
        if foreign_today > 0:
            score += 40
            if foreign_today > 1000:
                score += 20
                signals['外資'] = f'✅ 外資大買超 {foreign_today:,.0f} 張'
            elif foreign_today > 200:
                score += 10
                signals['外資'] = f'✅ 外資買超 {foreign_today:,.0f} 張'
            else:
                signals['外資'] = f'✅ 外資小買 {foreign_today:,.0f} 張'
        else:
            signals['外資'] = f'❌ 外資賣超 {abs(foreign_today):,.0f} 張'

        # 連續買超天數
        if not history.empty and 'foreign_net' in history.columns:
            consecutive = _count_consecutive_positive(history['foreign_net'])
            detail['foreign_consecutive_days'] = consecutive
            if consecutive >= 5:
                score += 40
                signals['外資連買'] = f'✅ 外資連續買超 {consecutive} 日'
            elif consecutive >= 3:
                score += 25
                signals['外資連買'] = f'✅ 外資連買 {consecutive} 日'
            elif consecutive >= 1:
                score += 10

            # 近 N 日累積買超
            total_net = history['foreign_net'].sum()
            detail['foreign_total_net'] = round(total_net, 0)
            if total_net > 2000:
                score = min(100, score + 20)

    except Exception as e:
        logger.debug(f"外資分析失敗: {e}")

    return round(min(100, max(0, score)), 1)


def _analyze_trust(today: pd.Series, history: pd.DataFrame, result: dict) -> float:
    """投信買賣超分析"""
    score   = 0
    signals = result['signals']
    detail  = result['detail']

    try:
        trust_today = float(today.get('trust_net', 0)) if not pd.isna(today.get('trust_net', np.nan)) else 0
        detail['trust_today'] = round(trust_today, 0)

        if trust_today > 0:
            score += 50
            if trust_today > 500:
                score += 30
                signals['投信'] = f'✅ 投信大買超 {trust_today:,.0f} 張'
            else:
                signals['投信'] = f'✅ 投信買超 {trust_today:,.0f} 張'
        else:
            signals['投信'] = f'❌ 投信賣超 {abs(trust_today):,.0f} 張'

        # 連續買超（投信的連續性更重要）
        if not history.empty and 'trust_net' in history.columns:
            consecutive = _count_consecutive_positive(history['trust_net'])
            detail['trust_consecutive_days'] = consecutive
            if consecutive >= 3:
                score += 50
                signals['投信連買'] = f'✅ 投信連續買超 {consecutive} 日（強力護盤）'
            elif consecutive >= 1:
                score += 20

    except Exception as e:
        logger.debug(f"投信分析失敗: {e}")

    return round(min(100, max(0, score)), 1)


def _analyze_margin(margin: pd.Series, result: dict) -> float:
    """
    融資融券分析
    健康型態：融資減少 + 股價上漲（惜售）、融券增加可能被軋空
    """
    score   = 0
    signals = result['signals']
    detail  = result['detail']

    try:
        margin_bal  = float(margin.get('margin_balance', 0)) if not pd.isna(margin.get('margin_balance', np.nan)) else 0
        short_bal   = float(margin.get('short_balance', 0)) if not pd.isna(margin.get('short_balance', np.nan)) else 0
        margin_chg  = float(margin.get('margin_change', 0)) if not pd.isna(margin.get('margin_change', np.nan)) else 0

        detail['margin_balance'] = margin_bal
        detail['short_balance']  = short_bal
        detail['margin_change']  = margin_chg

        # 融資變化
        if margin_chg < 0:
            # 融資減少：散戶減少，主力可能開始佈局
            score += 40
            signals['融資'] = f'✅ 融資減少 {abs(margin_chg):,.0f} 張（健康去槓桿）'
        elif margin_chg == 0:
            score += 20
            signals['融資'] = '⚠️ 融資持平'
        else:
            # 融資增加：散戶追高，需謹慎
            score += 5
            signals['融資'] = f'⚠️ 融資增加 {margin_chg:,.0f} 張，留意追高風險'

        # 融資使用率（如有分子分母則更準，此處以餘額推估）
        # 融券餘額高 + 股價強：軋空行情潛力
        if short_bal > 0 and margin_bal > 0:
            short_ratio = short_bal / margin_bal
            detail['short_to_margin_ratio'] = round(short_ratio, 3)
            if short_ratio > 0.3:
                score = min(100, score + 30)
                signals['融券'] = f'✅ 融券比例高（{short_ratio:.1%}），有軋空潛力'
            elif short_ratio > 0.1:
                score = min(100, score + 15)
                signals['融券'] = f'⚠️ 融券比例 {short_ratio:.1%}'

    except Exception as e:
        logger.debug(f"融資券分析失敗: {e}")

    return round(min(100, max(0, score)), 1)


# ─────────────────────────────────────────────────────────────────────────────
def _count_consecutive_positive(series: pd.Series) -> int:
    """計算最近連續正值（買超）天數"""
    count  = 0
    values = series.dropna().tolist()[::-1]  # 從最近一天往回數
    for v in values:
        if v > 0:
            count += 1
        else:
            break
    return count
