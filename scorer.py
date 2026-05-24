# scorer.py — 加權評分引擎

from config import WEIGHTS


def calculate_total_score(
    tech_result:  dict,
    chips_result: dict,
    fund_result:  dict,
    sent_result:  dict,
    market_multiplier: float = 1.0,
) -> dict:
    """
    將四個維度的分數加權合計為總分
    market_multiplier：大盤情緒調整係數（0.85–1.1）
    """
    scores = {
        'technical':   tech_result.get('score', 0),
        'chips':       chips_result.get('score', 0),
        'fundamental': fund_result.get('score', 0),
        'sentiment':   sent_result.get('score', 50),
    }

    weighted_total = sum(
        scores[dim] * WEIGHTS[dim]
        for dim in WEIGHTS
    )

    # 大盤情緒調整（只在特定範圍內影響）
    adjusted_total = weighted_total * market_multiplier
    adjusted_total = round(min(100, max(0, adjusted_total)), 1)

    # 綜合訊號評級
    grade = _get_grade(adjusted_total)

    return {
        'total_score':     adjusted_total,
        'raw_score':       round(weighted_total, 1),
        'market_adj':      round(market_multiplier, 2),
        'dimension_scores': scores,
        'grade':           grade,
        'weights':         WEIGHTS,
    }


def _get_grade(score: float) -> dict:
    """根據總分給出評級"""
    if score >= 80:
        return {'label': 'A+ 強力買進', 'color': '#00a651', 'emoji': '🚀'}
    elif score >= 70:
        return {'label': 'A  建議買進', 'color': '#4caf50', 'emoji': '✅'}
    elif score >= 65:
        return {'label': 'B+ 值得關注', 'color': '#8bc34a', 'emoji': '👀'}
    elif score >= 55:
        return {'label': 'B  中性觀望', 'color': '#ffc107', 'emoji': '⚠️'}
    elif score >= 45:
        return {'label': 'C  偏弱不宜', 'color': '#ff9800', 'emoji': '⛔'}
    else:
        return {'label': 'D  建議迴避', 'color': '#f44336', 'emoji': '❌'}
