import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.models import InstitutionalFlow, MarginBalance, NewsItem, PriceBar, ScoreResult, Stock
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


class TechnicalScanClient:
    matching_closes = [
        100.3427, 99.4041, 99.647, 100.2619, 100.7026, 101.1671, 100.921, 100.9415,
        100.174, 100.4921, 100.598, 100.2963, 99.4255, 98.7622, 98.4549, 98.9783,
        98.7828, 99.218, 98.5676, 98.0228, 97.4511, 96.9611, 97.2833, 96.9231,
        96.4852, 96.6251, 96.3898, 96.8458, 97.009, 97.3905, 97.1243, 96.8059,
        96.5795, 97.2097, 97.7702, 97.7278, 97.5674, 96.733, 97.1557, 97.1817,
        96.6971, 97.1134, 96.6992, 96.7995, 95.9042, 96.2635, 95.5179, 94.9763,
        94.7993, 94.8496, 93.9881, 94.1081, 94.6467, 94.0573, 94.0102,
    ]

    def get_stock_info(self):
        return [
            Stock("1111", "轉折股", "測試產業", "twse"),
            Stock("2222", "趨勢股", "測試產業", "twse"),
        ]

    def get_twse_latest_snapshot(self):
        return []

    def get_prices(self, stock_id: str, days: int = 180):
        closes = self.matching_closes if stock_id == "1111" else [float(50 + index) for index in range(55)]
        start = date(2026, 1, 1)
        return [
            PriceBar(
                date=(start + timedelta(days=index)).isoformat(),
                stock_id=stock_id,
                open=close - 0.4,
                high=close + 1.2,
                low=close - 1.2,
                close=close,
                volume=1_000_000 + index * 1000,
                amount=0,
            )
            for index, close in enumerate(closes)
        ]


class GuardedStorage:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def __getattr__(self, name):
        raise AssertionError(f"technical scan must not touch local storage: {name}")


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

    def test_daily_reversal_setup_filter(self):
        service = ScreenerService()
        scores = [
            ScoreResult(
                stock_id="1111",
                name="setup",
                industry="test",
                market="twse",
                run_date="2026-05-25",
                buy_score=60,
                technical_score=55,
                chip_score=50,
                sentiment_score=50,
                risk_score=55,
                entry_watch_price=10,
                stop_loss_price=9,
                target_zone="10.5 - 11.0",
                buy_reason="",
                avoid_reason="",
                data_freshness="test",
                decision="watch",
                details={
                    "filter_flags": {
                        "daily_macd_kdj_reversal_setup": True,
                        "macd_bearish_weakening": True,
                        "kdj_pre_golden_cross": True,
                    },
                    "local_model": {},
                    "latest_volume": 1_000_000,
                },
            ),
            ScoreResult(
                stock_id="2222",
                name="plain",
                industry="test",
                market="twse",
                run_date="2026-05-25",
                buy_score=60,
                technical_score=55,
                chip_score=50,
                sentiment_score=50,
                risk_score=55,
                entry_watch_price=10,
                stop_loss_price=9,
                target_zone="10.5 - 11.0",
                buy_reason="",
                avoid_reason="",
                data_freshness="test",
                decision="watch",
                details={
                    "filter_flags": {"daily_macd_kdj_reversal_setup": False},
                    "local_model": {},
                    "latest_volume": 1_000_000,
                },
            ),
        ]
        filtered = service._apply_filters(scores, {"setup_pattern": "daily_macd_kdj_reversal"})
        self.assertEqual([score.stock_id for score in filtered], ["1111"])

    def test_direct_api_technical_scan_uses_client_not_local_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage_path = Path(tmp) / "test.sqlite"
            storage = Storage(storage_path)
            service = ScreenerService(storage=storage, client=TechnicalScanClient())
            payload = service.technical_scan_direct(
                {
                    "market": "all",
                    "limit": 0,
                    "require_macd_bearish_weakening": True,
                    "require_kdj_pre_golden_cross": True,
                    "bollinger_mode": "all",
                }
            )
            self.assertEqual(payload["source"], "api")
            self.assertEqual(payload["data_policy"], "direct_api_only")
            self.assertFalse(payload["uses_local_market_data"])
            self.assertEqual(payload["scanned"], 2)
            self.assertEqual(payload["unmatched"], 1)
            self.assertEqual(payload["failed"], 0)
            self.assertEqual([item["stock_id"] for item in payload["results"]], ["1111"])
            self.assertEqual(storage.get_stocks(), [])

    def test_direct_api_technical_scan_progress_splits_unmatched_and_failed(self):
        service = ScreenerService(client=TechnicalScanClient())
        progress_events = []
        payload = service.technical_scan_direct(
            {
                "market": "all",
                "require_macd_bearish_weakening": True,
                "require_kdj_pre_golden_cross": True,
                "bollinger_mode": "all",
            },
            progress_callback=lambda scanned, total, matched, failed, current, results: progress_events.append(
                {
                    "scanned": scanned,
                    "total": total,
                    "matched": matched,
                    "unmatched": max(0, scanned - matched - failed),
                    "failed": failed,
                    "current": current,
                    "results": [item["stock_id"] for item in results],
                }
            ),
        )
        self.assertEqual(payload["unmatched"], 1)
        self.assertEqual(progress_events[-1]["matched"], 1)
        self.assertEqual(progress_events[-1]["unmatched"], 1)
        self.assertEqual(progress_events[-1]["failed"], 0)
        self.assertEqual(progress_events[-1]["results"], ["1111"])

    def test_direct_api_technical_scan_never_reads_or_writes_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ScreenerService(storage=GuardedStorage(Path(tmp) / "guard.sqlite"), client=TechnicalScanClient())
            payload = service.technical_scan_direct(
                {
                    "market": "all",
                    "require_macd_bearish_weakening": True,
                    "require_kdj_pre_golden_cross": True,
                    "bollinger_mode": "all",
                }
            )
            self.assertEqual(payload["data_policy"], "direct_api_only")
            self.assertEqual([item["stock_id"] for item in payload["results"]], ["1111"])


if __name__ == "__main__":
    unittest.main()
