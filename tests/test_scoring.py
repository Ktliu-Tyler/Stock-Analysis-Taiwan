import unittest

from app.fixtures import demo_market
from app.scoring import score_sentiment, score_stock


class ScoringTests(unittest.TestCase):
    def test_demo_candidate_scores_are_bounded(self):
        stocks, prices, flows, margins, news = demo_market()
        stock = next(item for item in stocks if item.stock_id == "2330")
        score = score_stock(stock, prices[stock.stock_id], flows[stock.stock_id], margins[stock.stock_id], news[stock.stock_id])
        self.assertGreaterEqual(score.buy_score, 0)
        self.assertLessEqual(score.buy_score, 100)
        self.assertIn(score.decision, {"適合買入", "觀察", "等待拉回", "避開"})
        self.assertGreater(score.entry_watch_price, score.stop_loss_price)
        self.assertIn("bollinger", score.details)
        self.assertIn("kdj", score.details)
        self.assertIn("bollinger_bullish", score.details["filter_flags"])
        self.assertIn("kdj_bullish", score.details["filter_flags"])

    def test_modes_produce_mode_metadata(self):
        stocks, prices, flows, margins, news = demo_market()
        stock = next(item for item in stocks if item.stock_id == "2330")
        score = score_stock(stock, prices[stock.stock_id], flows[stock.stock_id], margins[stock.stock_id], news[stock.stock_id], analysis_mode="long")
        self.assertEqual(score.details["analysis_mode"], "long")
        self.assertEqual(score.details["portfolio_horizon"], "長期")

    def test_sentiment_keywords_shift_score(self):
        _, _, _, _, news = demo_market()
        positive_news = news["2330"]
        self.assertGreater(score_sentiment(positive_news), 50)


if __name__ == "__main__":
    unittest.main()
