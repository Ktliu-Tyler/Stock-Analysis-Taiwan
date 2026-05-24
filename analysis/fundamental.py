# analysis/fundamental.py — 基本面分析模組
# 使用 TWSE 公開資料：本益比、殖利率、股價淨值比

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# 各產業平均本益比參考值（用於相對估值）
INDUSTRY_AVG_PER = {
    'default': 18,
    '半導體': 22,
    '電子零組件': 15,
    '電腦及週邊設備': 18,
    '通信網路': 20,
    '光電': 16,
    '其他電子': 16,
    '金融': 12,
    '塑膠': 14,
    '鋼鐵': 12,
    '食品': 20,
    '紡織': 12,
}


def analyze(valuation_row: pd.Series, industry: str = 'default') -> dict:
    """
    輸入：TWSE 本益比資料的單行（含 per, yield_pct, pbr）
    輸出：{
        'score': 0–100,
        'signals': {...},
        'detail': {...},
    }
    """
    result = {'score': 0, 'signals': {}, 'detail': {}}
    scores = []

    # ── 1. 本益比評估（40分）────────────────────────────────────────────
    per_score = _analyze_per(valuation_row, industry, result)
    scores.append(('本益比', per_score, 40))

    # ── 2. 殖利率評估（35分）────────────────────────────────────────────
    yield_score = _analyze_yield(valuation_row, result)
    scores.append(('殖利率', yield_score, 35))

    # ── 3. 股價淨值比評估（25分）────────────────────────────────────────
    pbr_score = _analyze_pbr(valuation_row, result)
    scores.append(('股價淨值比', pbr_score, 25))

    total = sum(s * w / 100 for _, s, w in scores)
    result['score']     = round(min(100, max(0, total)), 1)
    result['breakdown'] = {name: {'score': s, 'weight': w} for name, s, w in scores}
    return result


# ─────────────────────────────────────────────────────────────────────────────
def _analyze_per(row: pd.Series, industry: str, result: dict) -> float:
    """本益比分析：相對同產業評估"""
    score   = 0
    signals = result['signals']
    detail  = result['detail']

    try:
        per = float(row.get('per', np.nan))
        if pd.isna(per) or per <= 0:
            signals['本益比'] = '⚠️ 無本益比資料（可能虧損）'
            return 0

        detail['PER'] = round(per, 1)
        industry_avg  = INDUSTRY_AVG_PER.get(industry, INDUSTRY_AVG_PER['default'])

        # 絕對值評分
        if per < 8:
            score += 90
            signals['本益比'] = f'✅ 本益比極低（{per:.1f}x），深度價值'
        elif per < 12:
            score += 75
            signals['本益比'] = f'✅ 本益比偏低（{per:.1f}x），具吸引力'
        elif per < 18:
            score += 60
            signals['本益比'] = f'✅ 本益比合理（{per:.1f}x）'
        elif per < 25:
            score += 35
            signals['本益比'] = f'⚠️ 本益比偏高（{per:.1f}x）'
        elif per < 40:
            score += 15
            signals['本益比'] = f'❌ 本益比過高（{per:.1f}x），溢價明顯'
        else:
            score += 5
            signals['本益比'] = f'❌ 本益比極高（{per:.1f}x），風險大'

        # 相對同業加減分
        relative = (industry_avg - per) / industry_avg
        detail['PER_vs_industry'] = round(relative * 100, 1)
        if relative > 0.2:
            score = min(100, score + 15)
            signals['本益比'] += f'（同業均值 {industry_avg}x，便宜 {relative:.0%}）'
        elif relative < -0.3:
            score = max(0, score - 15)

    except Exception as e:
        logger.debug(f"本益比分析失敗: {e}")

    return round(min(100, max(0, score)), 1)


def _analyze_yield(row: pd.Series, result: dict) -> float:
    """殖利率分析"""
    score   = 0
    signals = result['signals']
    detail  = result['detail']

    try:
        yield_pct = float(row.get('yield_pct', np.nan))
        if pd.isna(yield_pct):
            signals['殖利率'] = '⚠️ 無殖利率資料'
            return 30

        detail['yield_pct'] = round(yield_pct, 2)

        if yield_pct >= 6:
            score += 90
            signals['殖利率'] = f'✅ 高殖利率 {yield_pct:.1f}%（存股首選）'
        elif yield_pct >= 4:
            score += 70
            signals['殖利率'] = f'✅ 殖利率 {yield_pct:.1f}%，優於定存'
        elif yield_pct >= 2.5:
            score += 50
            signals['殖利率'] = f'⚠️ 殖利率 {yield_pct:.1f}%，尚可'
        elif yield_pct >= 1:
            score += 30
            signals['殖利率'] = f'⚠️ 殖利率偏低 {yield_pct:.1f}%'
        else:
            score += 10
            signals['殖利率'] = f'❌ 殖利率極低 {yield_pct:.1f}%'

    except Exception as e:
        logger.debug(f"殖利率分析失敗: {e}")
        return 30

    return round(min(100, max(0, score)), 1)


def _analyze_pbr(row: pd.Series, result: dict) -> float:
    """股價淨值比分析"""
    score   = 0
    signals = result['signals']
    detail  = result['detail']

    try:
        pbr = float(row.get('pbr', np.nan))
        if pd.isna(pbr) or pbr <= 0:
            signals['淨值比'] = '⚠️ 無淨值比資料'
            return 30

        detail['PBR'] = round(pbr, 2)

        if pbr < 0.8:
            score += 95
            signals['淨值比'] = f'✅ 跌破淨值（PBR={pbr:.2f}x），強力支撐'
        elif pbr < 1.2:
            score += 80
            signals['淨值比'] = f'✅ 接近淨值（PBR={pbr:.2f}x），安全邊際高'
        elif pbr < 2.0:
            score += 60
            signals['淨值比'] = f'✅ PBR 合理（{pbr:.2f}x）'
        elif pbr < 3.5:
            score += 35
            signals['淨值比'] = f'⚠️ PBR 偏高（{pbr:.2f}x）'
        else:
            score += 10
            signals['淨值比'] = f'❌ PBR 過高（{pbr:.2f}x），溢價過大'

    except Exception as e:
        logger.debug(f"淨值比分析失敗: {e}")
        return 30

    return round(min(100, max(0, score)), 1)
