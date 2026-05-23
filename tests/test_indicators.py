import unittest

from app.indicators import atr, macd, pct_change, rsi, sma, stochastic_kd


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

    def test_stochastic_and_atr(self):
        highs = [10 + index for index in range(30)]
        lows = [8 + index for index in range(30)]
        closes = [9 + index for index in range(30)]
        k, d = stochastic_kd(highs, lows, closes)
        self.assertIsNotNone(k)
        self.assertIsNotNone(d)
        self.assertGreater(k, 50)
        self.assertGreater(atr(highs, lows, closes), 0)


if __name__ == "__main__":
    unittest.main()

