import unittest

from app.indicators import (
    atr,
    bollinger_bands,
    daily_macd_kdj_reversal_setup,
    macd,
    macd_series,
    pct_change,
    rsi,
    sma,
    stochastic_kd,
    stochastic_kdj,
    stochastic_kdj_series,
)


class IndicatorTests(unittest.TestCase):
    def test_sma_and_pct_change(self):
        values = [1, 2, 3, 4, 5]
        self.assertEqual(sma(values, 3), 4)
        self.assertAlmostEqual(pct_change(values, 2), 66.6666666, places=4)

    def test_rsi_for_rising_series(self):
        values = list(range(1, 30))
        self.assertEqual(rsi(values, 14), 100.0)

    def test_macd_has_values(self):
        values = [float(index) for index in range(1, 60)]
        line, signal, histogram = macd(values)
        self.assertIsNotNone(line)
        self.assertIsNotNone(signal)
        self.assertIsNotNone(histogram)
        self.assertGreater(line, 0)
        line_series, signal_series, histogram_series = macd_series(values)
        self.assertEqual(line, line_series[-1])
        self.assertEqual(signal, signal_series[-1])
        self.assertEqual(histogram, histogram_series[-1])

    def test_stochastic_and_atr(self):
        highs = [10 + index for index in range(30)]
        lows = [8 + index for index in range(30)]
        closes = [9 + index for index in range(30)]
        k, d = stochastic_kd(highs, lows, closes)
        k2, d2, j = stochastic_kdj(highs, lows, closes)
        self.assertIsNotNone(k)
        self.assertIsNotNone(d)
        self.assertEqual(k, k2)
        self.assertEqual(d, d2)
        self.assertIsNotNone(j)
        self.assertGreater(k, 50)
        self.assertGreater(atr(highs, lows, closes), 0)
        k_series, d_series, j_series = stochastic_kdj_series(highs, lows, closes)
        self.assertEqual(k2, k_series[-1])
        self.assertEqual(d2, d_series[-1])
        self.assertEqual(j, j_series[-1])

    def test_bollinger_bands_have_position_metrics(self):
        values = [float(index) for index in range(1, 31)]
        middle, upper, lower, bandwidth, percent_b = bollinger_bands(values)
        self.assertIsNotNone(middle)
        self.assertGreater(upper, middle)
        self.assertLess(lower, middle)
        self.assertGreater(bandwidth, 0)
        self.assertGreater(percent_b, 50)

    def test_daily_macd_kdj_reversal_setup_detects_pre_cross(self):
        closes = [
            100.3427, 99.4041, 99.647, 100.2619, 100.7026, 101.1671, 100.921, 100.9415,
            100.174, 100.4921, 100.598, 100.2963, 99.4255, 98.7622, 98.4549, 98.9783,
            98.7828, 99.218, 98.5676, 98.0228, 97.4511, 96.9611, 97.2833, 96.9231,
            96.4852, 96.6251, 96.3898, 96.8458, 97.009, 97.3905, 97.1243, 96.8059,
            96.5795, 97.2097, 97.7702, 97.7278, 97.5674, 96.733, 97.1557, 97.1817,
            96.6971, 97.1134, 96.6992, 96.7995, 95.9042, 96.2635, 95.5179, 94.9763,
            94.7993, 94.8496, 93.9881, 94.1081, 94.6467, 94.0573, 94.0102,
        ]
        highs = [value + 1.2 for value in closes]
        lows = [value - 1.2 for value in closes]
        setup = daily_macd_kdj_reversal_setup(highs, lows, closes)
        self.assertTrue(setup["macd_bearish_weakening"])
        self.assertTrue(setup["kdj_pre_golden_cross"])
        self.assertTrue(setup["daily_macd_kdj_reversal_setup"])
        self.assertLess(setup["macd_histogram"], 0)
        self.assertGreater(setup["kdj_gap"], 0)


if __name__ == "__main__":
    unittest.main()
