import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.models import InstitutionalFlow, MarginBalance, NewsItem, PriceBar, Stock
from app.screener import ScreenerService
from app.storage import Storage
from app.portfolio import PortfolioService


class CountingMarketClient:
    def __init__(self) -> None:
        self.price_calls = 0
        self.flow_calls = 0
        self.margin_calls = 0
        self.news_calls = 0

    def select_universe(self):
        return [Stock("1234", "測試股", "測試產業", "twse")], "test_universe"

    def get_prices(self, stock_id: str):
        self.price_calls += 1
        start = date(2026, 1, 1)
        prices = []
        for index in range(70):
            close = 50 + index * 0.4
            prices.append(
                PriceBar(
                    date=(start + timedelta(days=index)).isoformat(),
                    stock_id=stock_id,
                    open=close - 0.2,
                    high=close + 0.8,
                    low=close - 0.8,
                    close=close,
                    volume=900_000 + index * 1000,
                    amount=0,
                )
            )
        return prices

    def get_institutional_flows(self, stock_id: str):
        self.flow_calls += 1
        start = date(2026, 2, 1)
        return [
            InstitutionalFlow(
                date=(start + timedelta(days=index)).isoformat(),
                stock_id=stock_id,
                foreign_net=1000 + index,
                trust_net=300,
                dealer_net=100,
                total_net=1400 + index,
            )
            for index in range(20)
        ]

    def get_margin(self, stock_id: str):
        self.margin_calls += 1
        start = date(2026, 2, 1)
        return [
            MarginBalance(
                date=(start + timedelta(days=index)).isoformat(),
                stock_id=stock_id,
                margin_balance=1000 + index,
                short_balance=100 - index,
                margin_change=1,
                short_change=-1,
            )
            for index in range(20)
        ]

    def get_news(self, stock: Stock):
        self.news_calls += 1
        return [NewsItem(stock_id=stock.stock_id, title="測試股營收成長", source="test", published_at="2026-03-01")]


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

    def test_real_run_uses_same_day_cache_unless_forced(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = Storage(Path(tmp) / "test.sqlite")
            client = CountingMarketClient()
            service = ScreenerService(storage=storage, client=client)

            first = service.run(mode="manual")
            self.assertEqual(first["source"], "test_universe")
            self.assertEqual(client.price_calls, 1)
            self.assertEqual(first["stats"]["downloaded"], 1)

            cached = service.run(mode="manual", analysis_mode="swing")
            self.assertEqual(cached["source"], "local_cache")
            self.assertEqual(client.price_calls, 1)
            self.assertEqual(cached["stats"]["cached"], 1)

            rescored = service.run(mode="rescore", rescore_only=True)
            self.assertEqual(rescored["source"], "local_rescore")
            self.assertEqual(client.price_calls, 1)
            self.assertEqual(rescored["stats"]["cached"], 1)

            forced = service.run(mode="manual", force_refresh=True)
            self.assertEqual(forced["source"], "test_universe")
            self.assertEqual(client.price_calls, 2)
            self.assertEqual(forced["stats"]["downloaded"], 1)


if __name__ == "__main__":
    unittest.main()
