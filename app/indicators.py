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


def macd(values: Sequence[float | int | None]) -> tuple[float | None, float | None, float | None]:
    clean = _clean(values)
    if len(clean) < 26:
        return None, None, None
    fast = ema_series(clean, 12)
    slow = ema_series(clean, 26)
    offset = len(fast) - len(slow)
    macd_line = [fast[index + offset] - slow[index] for index in range(len(slow))]
    signal_line = ema_series(macd_line, 9)
    if not signal_line:
        return None, None, None
    histogram = macd_line[-1] - signal_line[-1]
    return macd_line[-1], signal_line[-1], histogram


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
    high_values = _clean(highs)
    low_values = _clean(lows)
    close_values = _clean(closes)
    if len(high_values) < period or len(low_values) < period or len(close_values) < period:
        return None, None, None
    recent_high = max(high_values[-period:])
    recent_low = min(low_values[-period:])
    if recent_high == recent_low:
        return 50.0, 50.0, 50.0
    raw_k = (close_values[-1] - recent_low) / (recent_high - recent_low) * 100
    k_values: list[float] = []
    for index in range(period, len(close_values) + 1):
        window_high = max(high_values[index - period : index])
        window_low = min(low_values[index - period : index])
        close = close_values[index - 1]
        if window_high == window_low:
            k_values.append(50.0)
        else:
            k_values.append((close - window_low) / (window_high - window_low) * 100)
    d = sma(k_values, 3)
    if d is None:
        return raw_k, None, None
    j = 3 * raw_k - 2 * d
    return raw_k, d, j


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
