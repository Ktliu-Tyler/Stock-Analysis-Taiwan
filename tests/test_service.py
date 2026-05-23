import tempfile
import unittest
from pathlib import Path

from app.screener import ScreenerService
from app.storage import Storage
from app.portfolio import PortfolioService


class ServiceTests(unittest.TestCase):
    def test_demo_run_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = Storage(Path(tmp) / "test.sqlite")
            service = ScreenerService(storage=storage)
            payload = service.run(use_demo=True)
            self.assertGreater(payload["count"], 0)
            first = payload["items"][0]
            report = service.stock_report(first["stock_id"], include_demo=True)
            self.assertIn("prices", report)
            self.assertIn("score", report)
            self.assertGreater(len(report["prices"]), 0)

    def test_backtest_returns_horizons(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = Storage(Path(tmp) / "test.sqlite")
            service = ScreenerService(storage=storage)
            service.run(use_demo=True)
            payload = service.backtest(include_demo=True)
            self.assertEqual([item["horizon_days"] for item in payload["results"]], [1, 3, 5])
            swing_payload = service.backtest(include_demo=True, analysis_mode="swing")
            self.assertEqual([item["horizon_days"] for item in swing_payload["results"]], [10, 20, 40])

    def test_demo_scores_do_not_appear_in_default_today_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = Storage(Path(tmp) / "test.sqlite")
            service = ScreenerService(storage=storage)
            service.run(use_demo=True)
            default_payload = service.today_scores(auto_seed=False)
            demo_payload = service.today_scores({"demo": "1"}, auto_seed=False)
            self.assertEqual(default_payload["count"], 0)
            self.assertGreater(demo_payload["count"], 0)

    def test_portfolio_add_calculates_and_deletes_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = Storage(Path(tmp) / "test.sqlite")
            service = ScreenerService(storage=storage)
            service.run(use_demo=True)
            portfolio = PortfolioService(service.demo_storage)
            created = portfolio.add_position(
                {
                    "stock_id": "2330",
                    "shares": 1000,
                    "average_cost": 60,
                    "position_status": "已持有",
                }
            )
            payload = portfolio.list_positions()
            self.assertEqual(payload["summary"]["positions"], 1)
            self.assertGreater(payload["items"][0]["market_value"], 0)
            sold = portfolio.sell_position(created["id"], {"sell_price": 70, "sell_shares": 1000})
            self.assertTrue(sold["position"]["closed"])
            self.assertGreater(sold["position"]["realized_pnl"], 0)
            self.assertEqual(portfolio.list_positions()["summary"]["positions"], 0)
            portfolio.delete_position(created["id"])
            self.assertEqual(portfolio.list_positions()["summary"]["all_positions"], 0)


if __name__ == "__main__":
    unittest.main()
