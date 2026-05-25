from __future__ import annotations

import math
from collections.abc import Sequence


def _clean(values: Sequence[float | int | None]) -> list[float]:
    return [float(v) for v in values if v is not None and math.isfinite(float(v))]


def sma(values: Sequence[float | int | None], period: int) -> float | None:
    clean = _clean(values)
    if period <= 0 or len(clean) < period:
        return None
    return sum(clean[-period:]) / period


def ema_series(values: Sequence[float | int | None], period: int) -> list[float]:
    clean = _clean(values)
    if not clean or period <= 0:
        return []
    alpha = 2 / (period + 1)
    result = [clean[0]]
    for value in clean[1:]:
        result.append(value * alpha + result[-1] * (1 - alpha))
    return result


def rsi(values: Sequence[float | int | None], period: int = 14) -> float | None:
    clean = _clean(values)
    if len(clean) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(clean[-period - 1 : -1], clean[-period:]):
        delta = current - previous
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))
    average_gain = sum(gains) / period
    average_loss = sum(losses) / period
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def macd_series(values: Sequence[float | int | None]) -> tuple[list[float], list[float], list[float]]:
    clean = _clean(values)
    if len(clean) < 26:
        return [], [], []
    fast = ema_series(clean, 12)
    slow = ema_series(clean, 26)
    offset = len(fast) - len(slow)
    macd_line = [fast[index + offset] - slow[index] for index in range(len(slow))]
    signal_line = ema_series(macd_line, 9)
    if not signal_line:
        return macd_line, [], []
    histogram = [line - signal for line, signal in zip(macd_line, signal_line)]
    return macd_line, signal_line, histogram


def macd(values: Sequence[float | int | None]) -> tuple[float | None, float | None, float | None]:
    macd_line, signal_line, histogram = macd_series(values)
    if not macd_line or not signal_line or not histogram:
        return None, None, None
    return macd_line[-1], signal_line[-1], histogram[-1]


def stochastic_kd(
    highs: Sequence[float | int | None],
    lows: Sequence[float | int | None],
    closes: Sequence[float | int | None],
    period: int = 9,
) -> tuple[float | None, float | None]:
    k, d, _ = stochastic_kdj(highs, lows, closes, period)
    return k, d


def stochastic_kdj(
    highs: Sequence[float | int | None],
    lows: Sequence[float | int | None],
    closes: Sequence[float | int | None],
    period: int = 9,
) -> tuple[float | None, float | None, float | None]:
    k_values, d_values, j_values = stochastic_kdj_series(highs, lows, closes, period)
    if not k_values:
        return None, None, None
    return k_values[-1], d_values[-1], j_values[-1]


def stochastic_kdj_series(
    highs: Sequence[float | int | None],
    lows: Sequence[float | int | None],
    closes: Sequence[float | int | None],
    period: int = 9,
) -> tuple[list[float], list[float | None], list[float | None]]:
    high_values = _clean(highs)
    low_values = _clean(lows)
    close_values = _clean(closes)
    if len(high_values) < period or len(low_values) < period or len(close_values) < period:
        return [], [], []
    k_values: list[float] = []
    for index in range(period, len(close_values) + 1):
        window_high = max(high_values[index - period : index])
        window_low = min(low_values[index - period : index])
        close = close_values[index - 1]
        if window_high == window_low:
            k_values.append(50.0)
        else:
            k_values.append((close - window_low) / (window_high - window_low) * 100)

    d_values: list[float | None] = []
    j_values: list[float | None] = []
    for index, k_value in enumerate(k_values):
        d_value = sma(k_values[: index + 1], 3)
        d_values.append(d_value)
        j_values.append(3 * k_value - 2 * d_value if d_value is not None else None)
    return k_values, d_values, j_values


def daily_macd_kdj_reversal_setup(
    highs: Sequence[float | int | None],
    lows: Sequence[float | int | None],
    closes: Sequence[float | int | None],
) -> dict[str, float | bool | str | None]:
    """Detect a daily MACD bearish-weakening + KDJ pre-golden-cross setup."""
    _, _, histogram = macd_series(closes)
    k_values, d_values, j_values = stochastic_kdj_series(highs, lows, closes)

    macd_tail = histogram[-4:]
    k_tail = k_values[-3:]
    d_tail = d_values[-3:]
    j_tail = j_values[-3:]

    latest_hist = macd_tail[-1] if macd_tail else None
    previous_hist = macd_tail[-2] if len(macd_tail) >= 2 else None
    macd_improving_steps = 0
    if len(macd_tail) >= 2:
        macd_improving_steps = sum(
            1 for previous, current in zip(macd_tail, macd_tail[1:]) if current > previous
        )
    macd_bearish_weakening = bool(
        len(macd_tail) >= 3
        and latest_hist is not None
        and latest_hist < 0
        and macd_improving_steps >= 2
        and latest_hist > macd_tail[0]
    )

    latest_k = k_tail[-1] if k_tail else None
    previous_k = k_tail[-2] if len(k_tail) >= 2 else None
    latest_d = d_tail[-1] if d_tail else None
    previous_d = d_tail[-2] if len(d_tail) >= 2 else None
    latest_j = j_tail[-1] if j_tail else None
    previous_j = j_tail[-2] if len(j_tail) >= 2 else None
    kdj_gap = latest_d - latest_k if latest_k is not None and latest_d is not None else None
    previous_gap = previous_d - previous_k if previous_k is not None and previous_d is not None else None

    gap_is_small = kdj_gap is not None and 0 < kdj_gap <= 6
    gap_is_narrowing = previous_gap is not None and kdj_gap is not None and kdj_gap < previous_gap
    k_is_rising = latest_k is not None and previous_k is not None and latest_k > previous_k
    j_is_rising = latest_j is not None and previous_j is not None and latest_j > previous_j
    not_overheated = latest_k is not None and latest_d is not None and latest_k <= 70 and latest_d <= 75
    kdj_pre_golden_cross = bool(
        gap_is_small
        and gap_is_narrowing
        and k_is_rising
        and (j_is_rising or (latest_j is not None and latest_d is not None and latest_j > latest_d))
        and not_overheated
    )

    setup = bool(macd_bearish_weakening and kdj_pre_golden_cross)
    if setup:
        label = "日線MACD空頭減弱 + KDJ即將金叉"
    elif macd_bearish_weakening:
        label = "日線MACD空頭減弱"
    elif kdj_pre_golden_cross:
        label = "日線KDJ接近金叉"
    else:
        label = "日線轉折型態未成立"

    return {
        "daily_macd_kdj_reversal_setup": setup,
        "macd_bearish_weakening": macd_bearish_weakening,
        "kdj_pre_golden_cross": kdj_pre_golden_cross,
        "macd_histogram": latest_hist,
        "macd_previous_histogram": previous_hist,
        "macd_improving_steps": float(macd_improving_steps),
        "kdj_k": latest_k,
        "kdj_d": latest_d,
        "kdj_j": latest_j,
        "kdj_gap": kdj_gap,
        "kdj_previous_gap": previous_gap,
        "label": label,
    }


def bollinger_bands(
    values: Sequence[float | int | None],
    period: int = 20,
    deviations: float = 2.0,
) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    clean = _clean(values)
    if period <= 1 or len(clean) < period:
        return None, None, None, None, None
    window = clean[-period:]
    middle = sum(window) / period
    variance = sum((value - middle) ** 2 for value in window) / period
    stddev = math.sqrt(variance)
    upper = middle + deviations * stddev
    lower = middle - deviations * stddev
    bandwidth = ((upper - lower) / middle * 100) if middle else None
    percent_b = ((clean[-1] - lower) / (upper - lower) * 100) if upper != lower else 50.0
    return middle, upper, lower, bandwidth, percent_b


def atr(
    highs: Sequence[float | int | None],
    lows: Sequence[float | int | None],
    closes: Sequence[float | int | None],
    period: int = 14,
) -> float | None:
    high_values = _clean(highs)
    low_values = _clean(lows)
    close_values = _clean(closes)
    if len(high_values) <= period or len(low_values) <= period or len(close_values) <= period:
        return None
    true_ranges: list[float] = []
    for index in range(1, len(close_values)):
        high = high_values[index]
        low = low_values[index]
        previous_close = close_values[index - 1]
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return sma(true_ranges, period)


def pct_change(values: Sequence[float | int | None], periods: int = 1) -> float | None:
    clean = _clean(values)
    if periods <= 0 or len(clean) <= periods or clean[-periods - 1] == 0:
        return None
    return (clean[-1] / clean[-periods - 1] - 1) * 100


def rolling_max(values: Sequence[float | int | None], period: int) -> float | None:
    clean = _clean(values)
    if len(clean) < period:
        return None
    return max(clean[-period:])


def rolling_min(values: Sequence[float | int | None], period: int) -> float | None:
    clean = _clean(values)
    if len(clean) < period:
        return None
    return min(clean[-period:])


def volatility(values: Sequence[float | int | None], period: int = 20) -> float | None:
    clean = _clean(values)
    if len(clean) <= period:
        return None
    returns = []
    for previous, current in zip(clean[-period - 1 : -1], clean[-period:]):
        if previous:
            returns.append(current / previous - 1)
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
    return math.sqrt(variance)
