from __future__ import annotations

from datetime import date
from typing import Any

from .indicators import atr, macd, pct_change, rolling_max, rolling_min, rsi, sma, stochastic_kd, volatility
from .models import InstitutionalFlow, MarginBalance, NewsItem, PriceBar, ScoreResult, Stock

POSITIVE_TERMS = [
    "AI",
    "伺服器",
    "營收成長",
    "創高",
    "接單",
    "上修",
    "看好",
    "買超",
    "擴產",
    "毛利率",
    "需求",
    "獲利",
    "法說",
    "訂單",
    "出貨",
    "高檔",
]

NEGATIVE_TERMS = [
    "下修",
    "衰退",
    "虧損",
    "警示",
    "處置",
    "跌停",
    "調查",
    "延遲",
    "裁員",
    "違約",
    "風險",
    "觀望",
    "賣壓",
    "疲弱",
    "法說保守",
]


ANALYSIS_MODE_CONFIGS: dict[str, dict[str, Any]] = {
    "short": {
        "label": "短線",
        "portfolio_label": "短期",
        "description": "1-5 日，重視短均線、量價、法人短買與停損效率。",
        "weights": {"technical": 0.42, "chip": 0.28, "sentiment": 0.18, "risk": 0.12},
        "entry_note": "短線候選",
        "stop_ma": "ma10",
        "stop_floor": 0.045,
        "target": (1.03, 1.08),
        "min_buy_score": 72,
        "min_watch_score": 60,
        "min_risk_score": 52,
        "liquidity_min": 600_000,
        "liquidity_strong": 2_000_000,
        "atr_ok": 0.035,
        "atr_watch": 0.07,
        "overheat_metric": "change_5d",
        "overheat_label": "5日漲幅",
        "overheat_ok": 12,
        "overheat_watch": 22,
        "support_label": "10日線支撐",
    },
    "swing": {
        "label": "波段",
        "portfolio_label": "中期",
        "description": "2-8 週，重視 MA20/MA60、法人延續性、整理突破與波動容忍度。",
        "weights": {"technical": 0.36, "chip": 0.30, "sentiment": 0.14, "risk": 0.20},
        "entry_note": "波段觀察名單",
        "stop_ma": "ma20",
        "stop_floor": 0.075,
        "target": (1.08, 1.18),
        "min_buy_score": 70,
        "min_watch_score": 58,
        "min_risk_score": 50,
        "liquidity_min": 400_000,
        "liquidity_strong": 1_200_000,
        "atr_ok": 0.055,
        "atr_watch": 0.105,
        "overheat_metric": "change_20d",
        "overheat_label": "20日漲幅",
        "overheat_ok": 22,
        "overheat_watch": 42,
        "support_label": "20日線支撐",
    },
    "long": {
        "label": "長線",
        "portfolio_label": "長期",
        "description": "3-12 個月，重視 MA60 趨勢、波動可承受度、題材持續性與風險邊際。",
        "weights": {"technical": 0.30, "chip": 0.18, "sentiment": 0.22, "risk": 0.30},
        "entry_note": "長線觀察名單",
        "stop_ma": "ma60",
        "stop_floor": 0.12,
        "target": (1.15, 1.35),
        "min_buy_score": 68,
        "min_watch_score": 56,
        "min_risk_score": 48,
        "liquidity_min": 250_000,
        "liquidity_strong": 800_000,
        "atr_ok": 0.075,
        "atr_watch": 0.14,
        "overheat_metric": "change_20d",
        "overheat_label": "20日漲幅",
        "overheat_ok": 35,
        "overheat_watch": 65,
        "support_label": "60日線支撐",
    },
}


def normalize_analysis_mode(value: str | None) -> str:
    key = str(value or "short").strip().lower()
    aliases = {
        "day": "short",
        "intraday": "short",
        "短線": "short",
        "短期": "short",
        "mid": "swing",
        "middle": "swing",
        "medium": "swing",
        "波段": "swing",
        "中期": "swing",
        "longterm": "long",
        "long-term": "long",
        "長線": "long",
        "長期": "long",
    }
    key = aliases.get(key, key)
    return key if key in ANALYSIS_MODE_CONFIGS else "short"


def analysis_mode_options() -> list[dict[str, str]]:
    return [
        {
            "key": key,
            "label": str(config["label"]),
            "portfolio_label": str(config["portfolio_label"]),
            "description": str(config["description"]),
        }
        for key, config in ANALYSIS_MODE_CONFIGS.items()
    ]


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _consecutive_positive(values: list[float]) -> int:
    count = 0
    for value in reversed(values):
        if value <= 0:
            break
        count += 1
    return count


def _latest_or_none(items: list):
    return items[-1] if items else None


def _round(value: Any, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _state_from_delta(delta: float) -> str:
    if delta >= 8:
        return "bullish"
    if delta >= 3:
        return "slightly_bullish"
    if delta <= -8:
        return "bearish"
    if delta <= -3:
        return "slightly_bearish"
    return "neutral"


def _indicator(
    key: str,
    label: str,
    value: Any,
    delta: float,
    explanation: str,
    unit: str = "",
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "unit": unit,
        "impact": round(delta, 1),
        "state": _state_from_delta(delta),
        "explanation": explanation,
    }


def _sum_recent(values: list[float], count: int) -> float:
    if not values:
        return 0.0
    return sum(values[-count:])


def _safe_ratio(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


def score_stock(
    stock: Stock,
    prices: list[PriceBar],
    flows: list[InstitutionalFlow] | None = None,
    margins: list[MarginBalance] | None = None,
    news: list[NewsItem] | None = None,
    run_date: str | None = None,
    data_source: str = "local",
    analysis_mode: str = "short",
) -> ScoreResult:
    mode = normalize_analysis_mode(analysis_mode)
    mode_config = ANALYSIS_MODE_CONFIGS[mode]
    flows = sorted(flows or [], key=lambda item: item.date)
    margins = sorted(margins or [], key=lambda item: item.date)
    news = news or []
    prices = sorted(prices, key=lambda item: item.date)
    if not prices:
        raise ValueError(f"{stock.stock_id} has no price data")

    closes = [item.close for item in prices]
    highs = [item.high for item in prices]
    lows = [item.low for item in prices]
    volumes = [item.volume for item in prices]
    latest = prices[-1]
    ma5 = sma(closes, 5)
    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    volume_ma20 = sma(volumes, 20) or latest.volume
    volume_ratio = _safe_ratio(latest.volume, volume_ma20)
    rsi14 = rsi(closes, 14)
    macd_line, macd_signal, macd_histogram = macd(closes)
    k_value, d_value = stochastic_kd(highs, lows, closes)
    atr14 = atr(highs, lows, closes, 14)
    atr_ratio = _safe_ratio(atr14 or 0, latest.close)
    change_1d = pct_change(closes, 1) or 0.0
    change_5d = pct_change(closes, 5) or 0.0
    change_20d = pct_change(closes, 20) or 0.0
    previous_20_high = max(highs[-21:-1]) if len(highs) >= 21 else rolling_max(highs, min(10, len(highs)))
    previous_20_low = min(lows[-21:-1]) if len(lows) >= 21 else rolling_min(lows, min(10, len(lows)))
    previous_60_high = max(highs[-61:-1]) if len(highs) >= 61 else rolling_max(highs, min(30, len(highs)))
    previous_60_low = min(lows[-61:-1]) if len(lows) >= 61 else rolling_min(lows, min(30, len(lows)))
    recent_low = rolling_min(lows, min(10, len(lows))) or latest.close * 0.95
    medium_low = rolling_min(lows, min(20, len(lows))) or recent_low
    long_low = rolling_min(lows, min(60, len(lows))) or medium_low
    vol20 = volatility(closes, 20)

    technical_indicators: list[dict[str, Any]] = []
    chip_indicators: list[dict[str, Any]] = []
    sentiment_indicators: list[dict[str, Any]] = []
    risk_indicators: list[dict[str, Any]] = []
    buy_reasons: list[str] = []
    avoid_reasons: list[str] = []

    trend_delta = 0.0
    if ma5 and ma10 and ma20:
        if ma5 > ma10 > ma20:
            trend_delta = 22
            buy_reasons.append("短中期均線呈多頭排列")
            trend_text = "MA5 > MA10 > MA20，趨勢偏多"
        elif ma5 > ma10 and latest.close > ma20:
            trend_delta = 14
            buy_reasons.append("短均線轉強")
            trend_text = "MA5站上MA10且價格站回MA20"
        elif latest.close < ma10:
            trend_delta = -12
            avoid_reasons.append("價格尚未站穩10日線")
            trend_text = "收盤價跌破MA10，短線偏弱"
        else:
            trend_delta = 3
            trend_text = "均線結構中性偏多"
    else:
        trend_text = "均線資料不足"
    technical_indicators.append(_indicator("ma_trend", "均線結構", _round(ma5), trend_delta, trend_text, "MA5"))

    breakout_delta = 0.0
    if previous_20_high and latest.close >= previous_20_high * 0.995:
        breakout_delta = 18
        buy_reasons.append("接近或突破20日高點")
        breakout_text = "價格接近20日高點，動能延續"
    elif previous_20_low and latest.close <= previous_20_low * 1.02:
        breakout_delta = -12
        avoid_reasons.append("接近20日低點")
        breakout_text = "價格靠近20日低點，需防守"
    else:
        breakout_delta = 2
        breakout_text = "尚未突破區間"
    technical_indicators.append(_indicator("breakout_20d", "20日突破", _round(latest.close), breakout_delta, breakout_text))

    volume_delta = 0.0
    if volume_ratio >= 1.5:
        volume_delta = 16
        buy_reasons.append("成交量明顯放大")
        volume_text = "量比超過1.5，資金動能明顯"
    elif volume_ratio >= 1.15:
        volume_delta = 9
        buy_reasons.append("量能溫和增溫")
        volume_text = "量比大於1.15，買盤開始增溫"
    elif volume_ratio < 0.65:
        volume_delta = -8
        avoid_reasons.append("量能不足")
        volume_text = "量比低於0.65，短線追價意願不足"
    else:
        volume_delta = 1
        volume_text = "量能中性"
    technical_indicators.append(_indicator("volume_ratio", "成交量比", _round(volume_ratio), volume_delta, volume_text))

    rsi_delta = 0.0
    if rsi14 is not None:
        if 45 <= rsi14 <= 70:
            rsi_delta = 13
            buy_reasons.append("RSI位於偏強但未過熱區")
            rsi_text = "RSI在45-70，動能健康"
        elif 70 < rsi14 <= 82:
            rsi_delta = 5
            rsi_text = "RSI偏熱但仍可觀察"
        elif rsi14 > 82:
            rsi_delta = -8
            avoid_reasons.append("RSI過熱")
            rsi_text = "RSI高於82，追價風險升高"
        elif rsi14 < 35:
            rsi_delta = -10
            avoid_reasons.append("RSI偏弱")
            rsi_text = "RSI低於35，弱勢未明顯修復"
        else:
            rsi_delta = 1
            rsi_text = "RSI中性"
    else:
        rsi_text = "RSI資料不足"
    technical_indicators.append(_indicator("rsi14", "RSI14", _round(rsi14), rsi_delta, rsi_text))

    macd_delta = 0.0
    if macd_histogram is not None:
        if macd_histogram > 0 and (macd_line or 0) > (macd_signal or 0):
            macd_delta = 12
            buy_reasons.append("MACD柱狀體轉正")
            macd_text = "MACD在訊號線上方且柱狀體為正"
        elif macd_histogram < 0:
            macd_delta = -8
            avoid_reasons.append("MACD動能偏空")
            macd_text = "MACD柱狀體為負，動能尚未翻多"
        else:
            macd_delta = 1
            macd_text = "MACD中性"
    else:
        macd_text = "MACD資料不足"
    technical_indicators.append(_indicator("macd_histogram", "MACD", _round(macd_histogram, 4), macd_delta, macd_text))

    kd_delta = 0.0
    if k_value is not None and d_value is not None:
        if k_value > d_value and k_value < 85:
            kd_delta = 8
            kd_text = "KD黃金交叉且未過熱"
        elif k_value < d_value:
            kd_delta = -5
            kd_text = "KD向下交叉，短線動能降溫"
        else:
            kd_delta = -2
            kd_text = "KD偏熱，需等拉回"
    else:
        kd_text = "KD資料不足"
    technical_indicators.append(_indicator("kd", "KD", f"K {_round(k_value)} / D {_round(d_value)}", kd_delta, kd_text))

    if mode in {"swing", "long"}:
        medium_delta = 0.0
        if ma20 and ma60:
            if latest.close > ma20 > ma60:
                medium_delta = 18 if mode == "swing" else 14
                buy_reasons.append("中期均線維持多頭")
                medium_text = "收盤價站上MA20且MA20高於MA60，波段趨勢偏多"
            elif latest.close > ma20:
                medium_delta = 8
                medium_text = "價格守住MA20，但MA60趨勢仍待確認"
            elif latest.close < ma60:
                medium_delta = -14
                avoid_reasons.append("價格跌破中長期均線")
                medium_text = "收盤價跌破MA60，中期趨勢偏弱"
            else:
                medium_delta = -4
                medium_text = "價格介於MA20與MA60之間，趨勢未明"
        else:
            medium_text = "MA20/MA60資料不足"
        technical_indicators.append(_indicator("medium_trend", "MA20/MA60趨勢", _round(ma60), medium_delta, medium_text, "MA60"))

        range_high = previous_60_high if mode == "long" else previous_20_high
        range_low = previous_60_low if mode == "long" else previous_20_low
        range_label = "60日區間" if mode == "long" else "20日區間"
        range_delta = 0.0
        if range_high and latest.close >= range_high * 0.97:
            range_delta = 10 if mode == "long" else 14
            buy_reasons.append(f"接近{range_label}上緣")
            range_text = f"價格接近{range_label}高點，趨勢延續性較佳"
        elif range_low and latest.close <= range_low * 1.04:
            range_delta = -10
            avoid_reasons.append(f"接近{range_label}下緣")
            range_text = f"價格接近{range_label}低點，需確認支撐"
        else:
            range_delta = 2
            range_text = f"價格位於{range_label}中段"
        technical_indicators.append(_indicator("mode_range_position", range_label, _round(latest.close), range_delta, range_text))

    technical_score = clamp(50 + sum(item["impact"] for item in technical_indicators))

    latest_flows = flows[-5:]
    foreign_values = [item.foreign_net for item in latest_flows]
    trust_values = [item.trust_net for item in latest_flows]
    dealer_values = [item.dealer_net for item in latest_flows]
    total_values = [item.total_net for item in latest_flows]
    latest_flow = _latest_or_none(flows)

    if latest_flow:
        foreign_delta = 12 if latest_flow.foreign_net > 0 else -10
        if latest_flow.foreign_net > 0:
            buy_reasons.append("外資買超")
            foreign_text = "外資當日買超，資金偏多"
        else:
            avoid_reasons.append("外資賣超")
            foreign_text = "外資當日賣超，短線籌碼偏空"
        chip_indicators.append(_indicator("foreign_net", "外資買賣超", round(latest_flow.foreign_net), foreign_delta, foreign_text, "股"))

        trust_delta = 16 if latest_flow.trust_net > 0 else -5
        if latest_flow.trust_net > 0:
            buy_reasons.append("投信買超")
            trust_text = "投信買超，波段資金支持"
        else:
            trust_text = "投信未明顯買超"
        chip_indicators.append(_indicator("trust_net", "投信買賣超", round(latest_flow.trust_net), trust_delta, trust_text, "股"))

        dealer_delta = 5 if latest_flow.dealer_net > 0 else -3
        dealer_text = "自營商偏多" if latest_flow.dealer_net > 0 else "自營商偏保守"
        chip_indicators.append(_indicator("dealer_net", "自營商買賣超", round(latest_flow.dealer_net), dealer_delta, dealer_text, "股"))

        net_ratio = _safe_ratio(latest_flow.total_net, latest.volume)
        ratio_delta = 10 if net_ratio > 0.08 else -10 if net_ratio < -0.08 else 2
        ratio_text = "法人買超占成交量比重偏高" if ratio_delta > 5 else "法人賣壓占比偏高" if ratio_delta < -5 else "法人占比中性"
        if ratio_delta > 5:
            buy_reasons.append("法人買超占成交量比重偏高")
        elif ratio_delta < -5:
            avoid_reasons.append("法人賣壓偏重")
        chip_indicators.append(_indicator("institutional_volume_ratio", "法人量占比", _round(net_ratio * 100), ratio_delta, ratio_text, "%"))

        foreign_streak = _consecutive_positive(foreign_values)
        trust_streak = _consecutive_positive(trust_values)
        streak_delta = min(16, foreign_streak * 3 + trust_streak * 4)
        if streak_delta >= 8:
            buy_reasons.append("法人連續買盤")
        chip_indicators.append(_indicator("institutional_streak", "法人連買", f"外資{foreign_streak}日 / 投信{trust_streak}日", streak_delta, "連買日數越高，籌碼延續性越好"))

        five_day_net = _sum_recent(total_values, 5)
        five_day_delta = 8 if five_day_net > 0 else -8
        chip_indicators.append(_indicator("institutional_5d_net", "法人5日合計", round(five_day_net), five_day_delta, "近5日法人合計買賣超", "股"))
    else:
        chip_indicators.append(_indicator("institutional_missing", "法人資料", "不足", 0, "缺少法人資料，籌碼面以中性處理"))
        foreign_values = []
        trust_values = []
        dealer_values = []

    latest_margin = _latest_or_none(margins)
    if latest_margin:
        margin_delta = 4 if latest_margin.margin_change > 0 and latest.close > (ma5 or latest.close) else -8 if latest_margin.margin_change > 0 and change_5d < 0 else 0
        margin_text = "融資增加且價格站上短均線" if margin_delta > 0 else "融資增加但價格未轉強" if margin_delta < 0 else "融資變化中性"
        if margin_delta < 0:
            avoid_reasons.append("融資增加但價格未轉強")
        chip_indicators.append(_indicator("margin_change", "融資變化", round(latest_margin.margin_change), margin_delta, margin_text, "張"))

        short_delta = 5 if latest_margin.short_change < 0 else -3 if latest_margin.short_change > 0 else 0
        short_text = "融券下降，空方回補" if short_delta > 0 else "融券增加，空方壓力上升" if short_delta < 0 else "融券變化中性"
        chip_indicators.append(_indicator("short_change", "融券變化", round(latest_margin.short_change), short_delta, short_text, "張"))
    else:
        chip_indicators.append(_indicator("margin_missing", "融資融券", "不足", 0, "缺少融資融券資料，暫不扣分"))

    chip_score = clamp(50 + sum(item["impact"] for item in chip_indicators))

    sentiment_result = score_sentiment(news, detailed=True)
    sentiment_score = float(sentiment_result["score"])
    sentiment_indicators.extend(sentiment_result["indicators"])
    if sentiment_score >= 65:
        buy_reasons.append("新聞與公告語氣偏正向")
    elif sentiment_score <= 38:
        avoid_reasons.append("近期新聞或公告偏保守")

    liquidity_delta = 14 if latest.volume >= mode_config["liquidity_strong"] else 8 if latest.volume >= mode_config["liquidity_min"] else -12
    if liquidity_delta < 0:
        avoid_reasons.append("成交量偏低")
    risk_indicators.append(_indicator("liquidity", "流動性", round(latest.volume), liquidity_delta, f"成交量越高，{mode_config['label']}進出與風控彈性越好", "股"))

    atr_delta = 14 if atr_ratio <= mode_config["atr_ok"] else 6 if atr_ratio <= mode_config["atr_watch"] else -12
    if atr_delta < 0:
        avoid_reasons.append(f"{mode_config['label']}波動偏大")
    risk_indicators.append(_indicator("atr_ratio", "ATR波動", _round(atr_ratio * 100), atr_delta, "ATR占收盤價比重，用來衡量停損距離", "%"))

    overheat_value = change_5d if mode_config["overheat_metric"] == "change_5d" else change_20d
    overheat_delta = 12 if overheat_value <= mode_config["overheat_ok"] else 2 if overheat_value <= mode_config["overheat_watch"] else -14
    if overheat_delta < 0:
        avoid_reasons.append(f"{mode_config['label']}漲幅過熱")
    elif overheat_delta < 5:
        avoid_reasons.append(f"近{mode_config['overheat_label']}偏高，追價風險上升")
    risk_indicators.append(_indicator("mode_overheat", str(mode_config["overheat_label"]), _round(overheat_value), overheat_delta, "漲幅過高會降低風控分", "%"))

    support_value = {"ma10": ma10, "ma20": ma20, "ma60": ma60}.get(str(mode_config["stop_ma"]), ma10)
    support_delta = 8 if support_value and latest.close >= support_value else -8
    risk_indicators.append(_indicator("mode_support", str(mode_config["support_label"]), _round(support_value), support_delta, f"價格是否守住{mode_config['label']}支撐", str(mode_config["stop_ma"]).upper()))

    risk_score = clamp(50 + sum(item["impact"] for item in risk_indicators))

    factor_weights = dict(mode_config["weights"])
    buy_score = clamp(
        technical_score * factor_weights["technical"]
        + chip_score * factor_weights["chip"]
        + sentiment_score * factor_weights["sentiment"]
        + risk_score * factor_weights["risk"]
    )
    direction = infer_direction(technical_score, chip_score, sentiment_score, risk_score, buy_score)
    decision = infer_decision(buy_score, risk_score, direction, mode_config)
    investment_advice = investment_advice_text(decision, direction, buy_score, risk_score, mode_config)

    stop_reference = {"ma10": ma10, "ma20": ma20, "ma60": ma60}.get(str(mode_config["stop_ma"]))
    mode_low = recent_low if mode == "short" else medium_low if mode == "swing" else long_low
    stop_anchor = min(
        value
        for value in [
            stop_reference or latest.close * (1 - float(mode_config["stop_floor"])),
            mode_low,
            latest.close * (1 - max(float(mode_config["stop_floor"]), atr_ratio * 1.4)),
        ]
        if value
    )
    stop_loss_price = round(stop_anchor * 0.99, 2)
    entry_watch_price = round(latest.close, 2)
    target_low, target_high = mode_config["target"]
    target_zone = f"{latest.close * target_low:.2f} - {latest.close * target_high:.2f}"

    if not buy_reasons:
        buy_reasons.append("目前訊號未形成明確優勢")
    if decision == "適合買入" and not avoid_reasons:
        avoid_reasons.append("若跌破停損價或量縮失守短均線則取消")
    elif not avoid_reasons:
        avoid_reasons.append("分數尚未達積極買入門檻")

    indicator_breakdown = {
        "technical": {
            "label": "技術面",
            "score": round(technical_score, 1),
            "direction": score_direction(technical_score),
            "indicators": technical_indicators,
            "summary": summarize_group(technical_indicators),
        },
        "chip": {
            "label": "籌碼面",
            "score": round(chip_score, 1),
            "direction": score_direction(chip_score),
            "indicators": chip_indicators,
            "summary": summarize_group(chip_indicators),
        },
        "sentiment": {
            "label": "市場情緒",
            "score": round(sentiment_score, 1),
            "direction": score_direction(sentiment_score),
            "indicators": sentiment_indicators,
            "summary": summarize_group(sentiment_indicators),
        },
        "risk": {
            "label": "風控",
            "score": round(risk_score, 1),
            "direction": score_direction(risk_score),
            "indicators": risk_indicators,
            "summary": summarize_group(risk_indicators),
        },
    }

    local_model = local_model_analysis(indicator_breakdown, buy_score, risk_score)
    details = {
        "analysis_version": 3,
        "analysis_mode": mode,
        "analysis_mode_label": mode_config["label"],
        "analysis_mode_description": mode_config["description"],
        "portfolio_horizon": mode_config["portfolio_label"],
        "latest_price": latest.close,
        "latest_volume": latest.volume,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "volume_ratio": volume_ratio,
        "rsi14": rsi14,
        "macd": {"line": macd_line, "signal": macd_signal, "histogram": macd_histogram},
        "kd": {"k": k_value, "d": d_value},
        "atr_ratio": atr_ratio,
        "change_1d": change_1d,
        "change_5d": change_5d,
        "change_20d": change_20d,
        "volatility20": vol20,
        "previous_20_high": previous_20_high,
        "previous_20_low": previous_20_low,
        "previous_60_high": previous_60_high,
        "previous_60_low": previous_60_low,
        "latest_flow": latest_flow.__dict__ if latest_flow else None,
        "latest_margin": latest_margin.__dict__ if latest_margin else None,
        "news": [item.__dict__ for item in news[:8]],
        "indicator_breakdown": indicator_breakdown,
        "factor_weights": factor_weights,
        "direction": direction,
        "investment_advice": investment_advice,
        "local_model": local_model,
        "filter_flags": build_filter_flags(indicator_breakdown, local_model, latest_flow),
    }

    return ScoreResult(
        stock_id=stock.stock_id,
        name=stock.name,
        industry=stock.industry,
        market=stock.market,
        run_date=run_date or date.today().isoformat(),
        buy_score=buy_score,
        technical_score=technical_score,
        chip_score=chip_score,
        sentiment_score=sentiment_score,
        risk_score=risk_score,
        entry_watch_price=entry_watch_price,
        stop_loss_price=stop_loss_price,
        target_zone=target_zone,
        buy_reason="；".join(dict.fromkeys(buy_reasons[:6])),
        avoid_reason="；".join(dict.fromkeys(avoid_reasons[:6])),
        data_freshness=f"{data_source} / 最新價格日 {latest.date}",
        decision=decision,
        details=details,
    )


def score_sentiment(news: list[NewsItem], detailed: bool = False) -> float | dict[str, Any]:
    if not news:
        indicators = [
            _indicator("news_count", "新聞/公告數", 0, 0, "缺少近期新聞與公告，情緒面以中性處理"),
            _indicator("positive_terms", "正向字詞", 0, 0, "未偵測到正向題材"),
            _indicator("negative_terms", "負向字詞", 0, 0, "未偵測到負向風險"),
        ]
        return {"score": 50.0, "indicators": indicators} if detailed else 50.0

    positive_hits = 0
    negative_hits = 0
    external_sentiment = 0.0
    for item in news[:12]:
        text = f"{item.title} {item.summary}"
        external_sentiment += item.sentiment
        positive_hits += sum(1 for term in POSITIVE_TERMS if term in text)
        negative_hits += sum(1 for term in NEGATIVE_TERMS if term in text)

    news_count_delta = min(8, len(news) * 1.5)
    positive_delta = min(22, positive_hits * 3.5)
    negative_delta = -min(24, negative_hits * 4.5)
    source_delta = clamp(external_sentiment * 12, -18, 18)
    score = clamp(50 + news_count_delta + positive_delta + negative_delta + source_delta)

    indicators = [
        _indicator("news_count", "新聞/公告數", len(news), news_count_delta, "近期資訊越多，題材可追蹤性越高"),
        _indicator("positive_terms", "正向字詞", positive_hits, positive_delta, "正向題材、營收或法人語氣"),
        _indicator("negative_terms", "負向字詞", negative_hits, negative_delta, "負向事件、處置、衰退或風險字詞"),
        _indicator("source_sentiment", "來源情緒", round(external_sentiment, 2), source_delta, "資料來源提供或內建估計的情緒分"),
    ]
    return {"score": score, "indicators": indicators} if detailed else score


def score_direction(score: float) -> str:
    if score >= 72:
        return "看多"
    if score >= 58:
        return "偏多"
    if score >= 44:
        return "中性"
    if score >= 30:
        return "偏空"
    return "看空"


def infer_direction(technical_score: float, chip_score: float, sentiment_score: float, risk_score: float, buy_score: float) -> str:
    weighted = technical_score * 0.36 + chip_score * 0.30 + sentiment_score * 0.18 + risk_score * 0.16
    if buy_score >= 72 and weighted >= 68:
        return "看多"
    if weighted >= 60:
        return "偏多"
    if weighted >= 48:
        return "中性"
    if weighted >= 36:
        return "偏空"
    return "看空"


def infer_decision(buy_score: float, risk_score: float, direction: str, mode_config: dict[str, Any] | None = None) -> str:
    mode_config = mode_config or ANALYSIS_MODE_CONFIGS["short"]
    if buy_score >= float(mode_config["min_buy_score"]) and risk_score >= float(mode_config["min_risk_score"]) and direction in {"看多", "偏多"}:
        return "適合買入"
    if buy_score >= float(mode_config["min_watch_score"]) and direction not in {"看空", "偏空"}:
        return "觀察"
    if buy_score >= float(mode_config["min_watch_score"]) - 4 and risk_score >= float(mode_config["min_risk_score"]) + 3:
        return "等待拉回"
    return "避開"


def investment_advice_text(decision: str, direction: str, buy_score: float, risk_score: float, mode_config: dict[str, Any] | None = None) -> str:
    mode_config = mode_config or ANALYSIS_MODE_CONFIGS["short"]
    mode_label = str(mode_config["label"])
    if decision == "適合買入":
        return f"{direction}，可列入{mode_config['entry_note']}。建議只在守住觀察價附近且量能不失真時分批，跌破停損價退出。"
    if decision == "觀察":
        return f"{direction}，{mode_label}訊號尚可但未達強勢買點。等待技術或籌碼再確認，不宜追高。"
    if decision == "等待拉回":
        return f"{direction}但分數只有{buy_score:.1f}，風控分{risk_score:.1f}。等回測{mode_label}支撐或量縮整理後再評估。"
    return f"{direction}，目前{mode_label}多方優勢不足。若技術、籌碼或情緒未改善，先避開。"


def summarize_group(indicators: list[dict[str, Any]]) -> str:
    bullish = [item["label"] for item in indicators if item["impact"] >= 5]
    bearish = [item["label"] for item in indicators if item["impact"] <= -5]
    if bullish and bearish:
        return f"偏多：{'、'.join(bullish[:3])}；偏空：{'、'.join(bearish[:3])}"
    if bullish:
        return f"主要偏多來自：{'、'.join(bullish[:4])}"
    if bearish:
        return f"主要壓力來自：{'、'.join(bearish[:4])}"
    return "目前多空訊號接近中性"


def local_model_analysis(indicator_breakdown: dict[str, Any], buy_score: float, risk_score: float) -> dict[str, Any]:
    votes = {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0}
    evidence: list[str] = []
    weights = {"technical": 1.3, "chip": 1.2, "sentiment": 0.8, "risk": 0.9}
    for group_key, group in indicator_breakdown.items():
        weight = weights.get(group_key, 1.0)
        for item in group["indicators"]:
            impact = float(item["impact"])
            if impact >= 5:
                votes["bullish"] += impact * weight
                if len(evidence) < 5:
                    evidence.append(f"{group['label']}：{item['label']}偏多")
            elif impact <= -5:
                votes["bearish"] += abs(impact) * weight
                if len(evidence) < 5:
                    evidence.append(f"{group['label']}：{item['label']}偏空")
            else:
                votes["neutral"] += 2 * weight

    total = sum(votes.values()) or 1.0
    bullish_ratio = votes["bullish"] / total
    bearish_ratio = votes["bearish"] / total
    if bullish_ratio - bearish_ratio >= 0.25 and buy_score >= 65 and risk_score >= 45:
        label = "本地模型偏多"
    elif bearish_ratio - bullish_ratio >= 0.18 or risk_score < 40:
        label = "本地模型偏空"
    else:
        label = "本地模型中性"

    confidence = max(bullish_ratio, bearish_ratio, votes["neutral"] / total)
    return {
        "label": label,
        "confidence": round(confidence * 100, 1),
        "bullish_probability": round(bullish_ratio * 100, 1),
        "bearish_probability": round(bearish_ratio * 100, 1),
        "neutral_probability": round(votes["neutral"] / total * 100, 1),
        "evidence": evidence,
        "note": "本地模型目前是規則式集成模型，使用完整指標分項投票，尚未使用外部機器學習套件。",
    }


def build_filter_flags(indicator_breakdown: dict[str, Any], local_model: dict[str, Any], latest_flow: InstitutionalFlow | None) -> dict[str, Any]:
    technical_items = {item["key"]: item for item in indicator_breakdown["technical"]["indicators"]}
    sentiment_items = {item["key"]: item for item in indicator_breakdown["sentiment"]["indicators"]}
    return {
        "ma_bullish": technical_items.get("ma_trend", {}).get("impact", 0) >= 8,
        "macd_bullish": technical_items.get("macd_histogram", {}).get("impact", 0) >= 5,
        "volume_breakout": technical_items.get("volume_ratio", {}).get("impact", 0) >= 8,
        "breakout_20d": technical_items.get("breakout_20d", {}).get("impact", 0) >= 8,
        "sentiment_positive": sentiment_items.get("positive_terms", {}).get("impact", 0) >= 5,
        "sentiment_negative": sentiment_items.get("negative_terms", {}).get("impact", 0) <= -5,
        "foreign_buy": bool(latest_flow and latest_flow.foreign_net > 0),
        "trust_buy": bool(latest_flow and latest_flow.trust_net > 0),
        "local_model_label": local_model["label"],
        "local_model_confidence": local_model["confidence"],
    }
