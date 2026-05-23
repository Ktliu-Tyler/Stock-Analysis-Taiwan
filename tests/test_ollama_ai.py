import tempfile
import unittest
from pathlib import Path

from app.ollama_ai import AIAnalysisService
from app.portfolio import PortfolioService
from app.screener import ScreenerService
from app.storage import Storage


class FakeOllama:
    host = "fake"
    default_model = "fake-model"

    def models(self):
        return []

    def generate(self, prompt: str, model: str = "", temperature: float = 0.2) -> str:
        self.last_prompt = prompt
        return "一句話結論：偏多，但需守停損。"


class AIAnalysisTests(unittest.TestCase):
    def test_stock_analysis_uses_demo_report_with_fake_ollama(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = Storage(Path(tmp) / "test.sqlite")
            screener = ScreenerService(storage=storage)
            screener.run(use_demo=True)
            fake = FakeOllama()
            service = AIAnalysisService(screener, fake)
            payload = service.analyze_stock({"stock_id": "2330", "demo": True, "model": "fake-model"})
            self.assertEqual(payload["analysis_type"], "stock_analysis")
            self.assertIn("偏多", payload["content"])
            self.assertIn("股票資料", fake.last_prompt)

    def test_position_analysis_includes_user_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = Storage(Path(tmp) / "test.sqlite")
            screener = ScreenerService(storage=storage)
            screener.run(use_demo=True)
            fake = FakeOllama()
            portfolio = PortfolioService(screener.demo_storage)
            created = portfolio.add_position({"stock_id": "2330", "shares": 1000, "average_cost": 60})
            service = AIAnalysisService(screener, fake, portfolio)
            payload = service.analyze_position(
                {
                    "position_id": created["id"],
                    "demo": True,
                    "position_status": "已持有",
                    "model": "fake-model",
                }
            )
            self.assertEqual(payload["analysis_type"], "position_analysis")
            self.assertIn("平均買入價", fake.last_prompt)


if __name__ == "__main__":
    unittest.main()
