# analysis/technical.py — 技術面分析模組
# 使用 pandas-ta 計算各種技術指標並給出 0–100 分

import logging
import pandas as pd
import numpy as np

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import TECH_PARAMS, FILTERS

logger = logging.getLogger(__name__)


def _sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def _macd(series: pd.Series, fast: int, slow: int, signal: int) -> pd.DataFrame:
    macd_line = _ema(series, fast) - _ema(series, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        f'MACD_{fast}_{slow}_{signal}': macd_line,
        f'MACDs_{fast}_{slow}_{signal}': signal_line,
        f'MACDh_{fast}_{slow}_{signal}': histogram,
    })


def _stoch(high: pd.Series, low: pd.Series, close: pd.Series, k: int, d: int, smooth_k: int) -> pd.DataFrame:
    lowest_low = low.rolling(k, min_periods=k).min()
    highest_high = high.rolling(k, min_periods=k).max()
    raw_k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    stoch_k = raw_k.rolling(smooth_k, min_periods=smooth_k).mean()
    stoch_d = stoch_k.rolling(d, min_periods=d).mean()
    return pd.DataFrame({
        f'STOCHk_{k}_{d}_{smooth_k}': stoch_k,
        f'STOCHd_{k}_{d}_{smooth_k}': stoch_d,
    })


def _bbands(series: pd.Series, length: int, std: int) -> pd.DataFrame:
    middle = series.rolling(length, min_periods=length).mean()
    deviation = series.rolling(length, min_periods=length).std(ddof=0)
    upper = middle + std * deviation
    lower = middle - std * deviation
    bandwidth = (upper - lower) / middle.replace(0, pd.NA)
    return pd.DataFrame({
        f'BBU_{length}_{float(std):.1f}': upper,
        f'BBM_{length}_{float(std):.1f}': middle,
        f'BBL_{length}_{float(std):.1f}': lower,
        f'BBB_{length}_{float(std):.1f}': bandwidth,
    })


def analyze(df: pd.DataFrame) -> dict:
    """
    輸入：個股日K DataFrame（含 date, open, high, low, close, volume）
    輸出：{
        'score': 0–100,
        'signals': {指標名: 描述},
        'detail': {指標名: 數值},
    }
    """
    result = {
        'score':   0,
        'signals': {},
        'detail':  {},
    }

    if df is None or len(df) < 30:
        result['signals']['error'] = '資料不足，無法計算技術指標'
        return result

    df = df.copy().sort_values('date').reset_index(drop=True)

    # 確保數值型態
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['close', 'volume'])

    if len(df) < 20:
        result['signals']['error'] = '有效資料不足'
        return result

    scores   = []
    signals  = {}
    detail   = {}

    # ── 1. 均線系統（20分）───────────────────────────────────────────────
    ma_score  = _analyze_ma(df, signals, detail)
    scores.append(('MA均線', ma_score, 20))

    # ── 2. MACD（20分）──────────────────────────────────────────────────
    macd_score = _analyze_macd(df, signals, detail)
    scores.append(('MACD', macd_score, 20))

    # ── 3. KD 指標（20分）────────────────────────────────────────────────
    kd_score = _analyze_kd(df, signals, detail)
    scores.append(('KD', kd_score, 20))

    # ── 4. 成交量（20分）────────────────────────────────────────────────
    vol_score = _analyze_volume(df, signals, detail)
    scores.append(('量能', vol_score, 20))

    # ── 5. 布林通道（20分）──────────────────────────────────────────────
    bb_score = _analyze_bollinger(df, signals, detail)
    scores.append(('布林通道', bb_score, 20))

    # ── 加總 ────────────────────────────────────────────────────────────
    total_score = sum(s * w / 100 for _, s, w in scores)
    total_score = round(min(100, max(0, total_score)), 1)

    result['score']   = total_score
    result['signals'] = signals
    result['detail']  = detail
    result['breakdown'] = {name: {'score': s, 'weight': w} for name, s, w in scores}
    return result


# ─────────────────────────────────────────────────────────────────────────────
def _analyze_ma(df: pd.DataFrame, signals: dict, detail: dict) -> float:
    """均線系統分析：多頭排列、站穩均線"""
    score = 0
    close = df['close']

    try:
        p = TECH_PARAMS['ma_periods']
        mas = {}
        for period in p:
            if len(df) >= period:
                mas[period] = _sma(close, period).iloc[-1]

        latest = close.iloc[-1]
        detail['price'] = round(latest, 2)

        # 多頭排列：5MA > 10MA > 20MA
        if len(mas) >= 3:
            ma5, ma10, ma20 = mas.get(5), mas.get(10), mas.get(20)
            if all(v is not None for v in [ma5, ma10, ma20]):
                detail['MA5']  = round(ma5, 2)
                detail['MA10'] = round(ma10, 2)
                detail['MA20'] = round(ma20, 2)

                if ma5 > ma10 > ma20:
                    score += 40
                    signals['MA'] = '✅ 均線多頭排列（5>10>20MA）'
                elif ma5 > ma20:
                    score += 20
                    signals['MA'] = '⚠️ 短線均線偏多但排列未完整'
                else:
                    signals['MA'] = '❌ 均線空頭排列'

                # 股價站上 20MA
                if latest > ma20:
                    score += 30
                # 股價站上 60MA
                if 60 in mas and latest > mas[60]:
                    score += 30
                    detail['MA60'] = round(mas[60], 2)

        # 均線向上斜率（MA20 5日前 vs 今）
        if len(df) >= 25:
            ma20_series = _sma(close, 20)
            ma20_now  = ma20_series.iloc[-1]
            ma20_prev = ma20_series.iloc[-6]
            if pd.notna(ma20_now) and pd.notna(ma20_prev):
                slope = (ma20_now - ma20_prev) / ma20_prev * 100
                detail['MA20_slope_pct'] = round(slope, 2)
                if slope > 0.5:
                    score = min(100, score + 10)

    except Exception as e:
        logger.debug(f"MA 計算失敗: {e}")

    return round(min(100, max(0, score)), 1)


def _analyze_macd(df: pd.DataFrame, signals: dict, detail: dict) -> float:
    """MACD 分析：黃金交叉、柱狀體翻正"""
    score = 0
    try:
        close = df['close']
        macd_df = _macd(
            close,
            fast=TECH_PARAMS['macd_fast'],
            slow=TECH_PARAMS['macd_slow'],
            signal=TECH_PARAMS['macd_signal'],
        )
        if macd_df is None or macd_df.empty:
            return 0

        cols     = macd_df.columns.tolist()
        macd_col = [c for c in cols if 'MACD_' in c and 'MACDh' not in c and 'MACDs' not in c]
        hist_col = [c for c in cols if 'MACDh' in c]
        sig_col  = [c for c in cols if 'MACDs' in c]

        if not (macd_col and hist_col and sig_col):
            return 0

        macd_line = macd_df[macd_col[0]]
        histogram  = macd_df[hist_col[0]]
        signal_line = macd_df[sig_col[0]]

        detail['MACD']      = round(macd_line.iloc[-1], 4) if pd.notna(macd_line.iloc[-1]) else None
        detail['MACD_hist'] = round(histogram.iloc[-1], 4) if pd.notna(histogram.iloc[-1]) else None

        # 黃金交叉（MACD 穿越 Signal 線）
        if (pd.notna(macd_line.iloc[-1]) and pd.notna(signal_line.iloc[-1]) and
                pd.notna(macd_line.iloc[-2]) and pd.notna(signal_line.iloc[-2])):
            if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
                score += 50
                signals['MACD'] = '✅ MACD 黃金交叉（當日）'
            elif macd_line.iloc[-1] > signal_line.iloc[-1]:
                score += 30
                signals['MACD'] = '✅ MACD > Signal 線（多方）'
            else:
                signals['MACD'] = '❌ MACD 死亡交叉或偏空'

        # 柱狀體翻正且連續放大
        if len(histogram) >= 3:
            h1, h2, h3 = histogram.iloc[-1], histogram.iloc[-2], histogram.iloc[-3]
            if pd.notna(h1) and pd.notna(h2):
                if h1 > 0:
                    score += 30
                    if h1 > h2 > 0:
                        score += 20
                        signals['MACD_hist'] = '✅ MACD 柱狀體翻正且擴大'
                    else:
                        signals['MACD_hist'] = '✅ MACD 柱狀體正值'
                else:
                    if h1 > h2:  # 雖負但縮小中
                        score += 10
                        signals['MACD_hist'] = '⚠️ MACD 柱狀體負值但收斂'

    except Exception as e:
        logger.debug(f"MACD 計算失敗: {e}")

    return round(min(100, max(0, score)), 1)


def _analyze_kd(df: pd.DataFrame, signals: dict, detail: dict) -> float:
    """KD 指標分析：低檔黃金交叉、K>D"""
    score = 0
    try:
        period = TECH_PARAMS['kd_period']
        stoch  = _stoch(df['high'], df['low'], df['close'], k=period, d=3, smooth_k=3)
        if stoch is None or stoch.empty:
            return 0

        k_col = [c for c in stoch.columns if 'STOCHk' in c]
        d_col = [c for c in stoch.columns if 'STOCHd' in c]
        if not (k_col and d_col):
            return 0

        k = stoch[k_col[0]]
        d = stoch[d_col[0]]

        k_now, d_now = k.iloc[-1], d.iloc[-1]
        k_prev, d_prev = k.iloc[-2], d.iloc[-2]

        if pd.isna(k_now) or pd.isna(d_now):
            return 0

        detail['K'] = round(k_now, 1)
        detail['D'] = round(d_now, 1)

        # 低檔黃金交叉（K<50 且剛穿越 D）
        if k_now > d_now and k_prev <= d_prev:
            if k_now < 50:
                score += 70
                signals['KD'] = f'✅ KD 低檔黃金交叉（K={k_now:.0f}）'
            else:
                score += 40
                signals['KD'] = f'✅ KD 黃金交叉（K={k_now:.0f}）'
        elif k_now > d_now:
            # K > D，多方格局
            if k_now < 30:
                score += 60
                signals['KD'] = f'✅ KD 超賣區多方（K={k_now:.0f}）'
            elif k_now < 50:
                score += 40
                signals['KD'] = f'✅ KD 低檔偏多（K={k_now:.0f}）'
            else:
                score += 20
                signals['KD'] = f'⚠️ KD 偏多但偏高（K={k_now:.0f}）'
        else:
            if k_now > 80:
                signals['KD'] = f'❌ KD 高檔死亡交叉（K={k_now:.0f}），注意風險'
            else:
                signals['KD'] = f'❌ K < D，偏空（K={k_now:.0f}）'

        # K 值方向加分
        if len(k) >= 3 and pd.notna(k.iloc[-3]):
            if k_now > k.iloc[-2] > k.iloc[-3]:
                score = min(100, score + 15)

    except Exception as e:
        logger.debug(f"KD 計算失敗: {e}")

    return round(min(100, max(0, score)), 1)


def _analyze_volume(df: pd.DataFrame, signals: dict, detail: dict) -> float:
    """成交量分析：量增價漲、突破均量"""
    score = 0
    try:
        close  = df['close']
        volume = df['volume']

        avg_vol_20 = volume.rolling(20).mean().iloc[-1]
        avg_vol_5  = volume.rolling(5).mean().iloc[-1]
        today_vol  = volume.iloc[-1]
        today_close = close.iloc[-1]
        prev_close  = close.iloc[-2] if len(close) >= 2 else today_close

        if pd.isna(avg_vol_20) or avg_vol_20 == 0:
            return 0

        vol_ratio = today_vol / avg_vol_20
        detail['volume']      = round(today_vol, 0)
        detail['avg_vol_20']  = round(avg_vol_20, 0)
        detail['vol_ratio']   = round(vol_ratio, 2)

        # 初步流動性門檻
        if today_vol < FILTERS['min_avg_volume']:
            signals['volume'] = f'❌ 成交量過低（{today_vol:.0f}張）'
            return 10

        price_up = today_close >= prev_close

        if vol_ratio >= 2.0 and price_up:
            score += 80
            signals['volume'] = f'✅ 量增價漲（成交量 {vol_ratio:.1f}x 均量）'
        elif vol_ratio >= 1.5 and price_up:
            score += 60
            signals['volume'] = f'✅ 量溫和放大（{vol_ratio:.1f}x）配合上漲'
        elif vol_ratio >= 1.2 and price_up:
            score += 40
            signals['volume'] = f'⚠️ 量略增（{vol_ratio:.1f}x）配合上漲'
        elif vol_ratio < 0.7 and not price_up:
            score += 20
            signals['volume'] = f'⚠️ 量縮下跌（{vol_ratio:.1f}x）'
        elif vol_ratio >= 2.0 and not price_up:
            score += 5
            signals['volume'] = f'❌ 量增價跌，出貨警訊（{vol_ratio:.1f}x）'
        else:
            score += 30
            signals['volume'] = f'⚠️ 量能普通（{vol_ratio:.1f}x 均量）'

        # 近 5 日均量 vs 20 日均量（量能趨勢）
        if pd.notna(avg_vol_5) and avg_vol_20 > 0:
            if avg_vol_5 > avg_vol_20 * 1.2:
                score = min(100, score + 20)

    except Exception as e:
        logger.debug(f"Volume 計算失敗: {e}")

    return round(min(100, max(0, score)), 1)


def _analyze_bollinger(df: pd.DataFrame, signals: dict, detail: dict) -> float:
    """布林通道分析：突破中軌、帶寬收縮後突破"""
    score = 0
    try:
        close  = df['close']
        period = TECH_PARAMS['bb_period']
        std    = TECH_PARAMS['bb_std']

        bb = _bbands(close, length=period, std=std)
        if bb is None or bb.empty:
            return 50

        upper_col  = [c for c in bb.columns if 'BBU' in c]
        middle_col = [c for c in bb.columns if 'BBM' in c]
        lower_col  = [c for c in bb.columns if 'BBL' in c]
        bwp_col    = [c for c in bb.columns if 'BBB' in c]

        if not (upper_col and middle_col and lower_col):
            return 50

        upper  = bb[upper_col[0]].iloc[-1]
        middle = bb[middle_col[0]].iloc[-1]
        lower  = bb[lower_col[0]].iloc[-1]
        price  = close.iloc[-1]

        detail['BB_upper']  = round(upper, 2) if pd.notna(upper) else None
        detail['BB_middle'] = round(middle, 2) if pd.notna(middle) else None
        detail['BB_lower']  = round(lower, 2) if pd.notna(lower) else None

        if pd.isna(upper) or pd.isna(middle) or pd.isna(lower):
            return 50

        band_width = (upper - lower) / middle if middle > 0 else 0

        # 股價位置判斷
        if price > upper:
            score += 30
            signals['BB'] = '⚠️ 布林上軌突破，短線超買注意'
        elif price > middle:
            score += 70
            signals['BB'] = '✅ 站上布林中軌，多方格局'
        elif price > lower:
            score += 30
            signals['BB'] = '⚠️ 布林中軌下方，弱勢整理'
        else:
            score += 10
            signals['BB'] = '❌ 跌破布林下軌，超賣'
            # 跌破下軌後反彈可能（反彈買點）
            if close.iloc[-1] > close.iloc[-2]:
                score += 15

        # 帶寬收縮後突破中軌（起漲訊號）
        if bwp_col and len(bb) >= 10:
            bwp_now  = bb[bwp_col[0]].iloc[-1]
            bwp_avg  = bb[bwp_col[0]].rolling(10).mean().iloc[-1]
            if pd.notna(bwp_now) and pd.notna(bwp_avg):
                if bwp_now < bwp_avg * 0.8 and price > middle:
                    score = min(100, score + 20)
                    signals['BB'] += ' + 帶寬收縮後突破（起漲訊號）'

    except Exception as e:
        logger.debug(f"Bollinger 計算失敗: {e}")
        return 50

    return round(min(100, max(0, score)), 1)
