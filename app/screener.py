from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from .backtest import run_backtest
from .config import DEFAULT_WATCHLIST
from .data_sources import DataFetchError, MarketDataClient
from .fixtures import demo_market
from .models import InstitutionalFlow, MarginBalance, NewsItem, PriceBar, ScoreResult, Stock
from .scoring import score_stock
from .storage import Storage


class ScreenerService:
    def __init__(self, storage: Storage | None = None, client: MarketDataClient | None = None):
        self.storage = storage or Storage()
        self._demo_db_path = self.storage.db_path.with_name(f"{self.storage.db_path.stem}.demo{self.storage.db_path.suffix}")
        self._demo_storage: Storage | None = None
        self.client = client or MarketDataClient()

    @property
    def demo_storage(self) -> Storage:
        if self._demo_storage is None:
            self._demo_storage = Storage(self._demo_db_path)
        return self._demo_storage

    def run(self, use_demo: bool = False, mode: str = "after_hours") -> dict[str, Any]:
        if use_demo:
            scores = self.load_demo_scores(mode=mode)
            return self._run_response(scores, source="demo")

        self.remove_demo_data(clear_market_data=False)
        try:
            stocks, universe_source = self.client.select_universe()
            self.storage.upsert_stocks(stocks)
            downloaded_stock_ids: list[str] = []
            for stock in stocks:
                try:
                    prices = self.client.get_prices(stock.stock_id)
                    if len(prices) < 30:
                        continue
                    flows = self.client.get_institutional_flows(stock.stock_id)
                    margins = self.client.get_margin(stock.stock_id)
                    news = self.client.get_news(stock)
                except DataFetchError:
                    continue
                self.storage.clear_stock_market_data(stock.stock_id)
                self.storage.upsert_prices(prices)
                self.storage.upsert_institutional_flows(flows)
                self.storage.upsert_margin_balances(margins)
                self.storage.upsert_news(news)
                downloaded_stock_ids.append(stock.stock_id)

            if not downloaded_stock_ids:
                return {
                    "source": "real_data_unavailable",
                    "run_date": date.today().isoformat(),
                    "count": 0,
                    "items": [],
                    "message": "No real market data was downloaded; demo data was not used.",
                }

            scores = self.score_universe(
                [stock for stock in stocks if stock.stock_id in downloaded_stock_ids],
                data_source=f"{universe_source}/{mode}",
            )
            return self._run_response(scores, source=universe_source)
        except Exception as exc:
            return {
                "source": "real_data_error",
                "run_date": date.today().isoformat(),
                "count": 0,
                "items": [],
                "message": f"Real market data update failed; demo data was not used. {exc}",
            }

    def load_demo_scores(self, mode: str = "after_hours") -> list[ScoreResult]:
        self.demo_storage.purge_demo_artifacts([item["stock_id"] for item in DEFAULT_WATCHLIST])
        stocks, prices_by_stock, flows_by_stock, margins_by_stock, news_by_stock = demo_market()
        self.demo_storage.upsert_stocks(stocks)
        for stock in stocks:
            self.demo_storage.clear_stock_market_data(stock.stock_id)
            self.demo_storage.upsert_prices(prices_by_stock[stock.stock_id])
            self.demo_storage.upsert_institutional_flows(flows_by_stock[stock.stock_id])
            self.demo_storage.upsert_margin_balances(margins_by_stock[stock.stock_id])
            self.demo_storage.upsert_news(news_by_stock[stock.stock_id])
        return self.score_universe(
            stocks,
            data_source=f"demo/{mode}",
            run_date=f"demo-{date.today().isoformat()}",
            include_demo=True,
            storage=self.demo_storage,
        )

    def score_universe(
        self,
        stocks: list[Stock],
        data_source: str,
        run_date: str | None = None,
        include_demo: bool = False,
        storage: Storage | None = None,
    ) -> list[ScoreResult]:
        storage = storage or self.storage
        run_date = run_date or date.today().isoformat()
        scores: list[ScoreResult] = []
        storage.delete_scores_for_run(run_date, include_demo=include_demo)
        for stock in stocks:
            prices = storage.get_prices(stock.stock_id)
            if not prices:
                continue
            flows = storage.get_institutional_flows(stock.stock_id)
            margins = storage.get_margin_balances(stock.stock_id)
            news = storage.get_news(stock.stock_id)
            scores.append(score_stock(stock, prices, flows, margins, news, run_date=run_date, data_source=data_source))
        scores.sort(key=lambda item: item.buy_score, reverse=True)
        storage.upsert_scores(scores)
        return scores

    def today_scores(self, filters: dict[str, str] | None = None, auto_seed: bool = True) -> dict[str, Any]:
        filters = filters or {}
        include_demo = _bool_filter(filters.get("demo"))
        storage = self.demo_storage if include_demo else self.storage
        scores = storage.get_scores(include_demo=include_demo)
        if include_demo and not scores and auto_seed:
            scores = self.load_demo_scores()
        elif not include_demo and scores and auto_seed and not scores[0].details.get("analysis_version"):
            stocks = storage.get_stocks()
            scores = self.score_universe(stocks, data_source="local/rescore", storage=storage)
        filtered = self._apply_filters(scores, filters)
        return {
            "run_date": storage.latest_run_date(include_demo=include_demo),
            "count": len(filtered),
            "items": [score.to_dict() for score in filtered],
            "industries": sorted({score.industry for score in scores}),
            "demo": include_demo,
        }

    def stock_report(self, stock_id: str, include_demo: bool = False) -> dict[str, Any]:
        storage = self.demo_storage if include_demo else self.storage
        score = storage.get_score(stock_id, include_demo=include_demo)
        if include_demo and not score:
            self.load_demo_scores()
            score = storage.get_score(stock_id, include_demo=True)
        stock = storage.get_stock(stock_id)
        if not score or not stock:
            return {"error": "stock_not_found", "stock_id": stock_id}
        prices = storage.get_prices(stock_id)
        flows = storage.get_institutional_flows(stock_id)
        margins = storage.get_margin_balances(stock_id)
        news = storage.get_news(stock_id)
        return {
            "stock": asdict(stock),
            "score": score.to_dict(),
            "prices": [asdict(item) for item in prices[-90:]],
            "institutional_flows": [asdict(item) for item in flows[-45:]],
            "margin_balances": [asdict(item) for item in margins[-45:]],
            "news": [asdict(item) for item in news],
            "signals": self.stock_signals(stock_id, include_demo=include_demo),
        }

    def stock_signals(self, stock_id: str, include_demo: bool = False) -> dict[str, Any]:
        storage = self.demo_storage if include_demo else self.storage
        score = storage.get_score(stock_id, include_demo=include_demo)
        if include_demo and not score:
            self.load_demo_scores()
            score = storage.get_score(stock_id, include_demo=True)
        if not score:
            return {"error": "stock_not_found", "stock_id": stock_id}
        details = score.details
        latest_flow = details.get("latest_flow") or {}
        latest_margin = details.get("latest_margin") or {}
        breakdown = details.get("indicator_breakdown") or {}
        return {
            "stock_id": stock_id,
            "decision": score.decision,
            "direction": details.get("direction", score.decision),
            "investment_advice": details.get("investment_advice", ""),
            "indicator_breakdown": breakdown,
            "local_model": details.get("local_model", {}),
            "summary": {
                "buy_score": round(score.buy_score, 1),
                "technical_score": round(score.technical_score, 1),
                "chip_score": round(score.chip_score, 1),
                "sentiment_score": round(score.sentiment_score, 1),
                "risk_score": round(score.risk_score, 1),
            },
            "technical": [
                {"label": "MA5", "value": _round(details.get("ma5")), "state": _state(details.get("ma5"), details.get("ma10"))},
                {"label": "MA10", "value": _round(details.get("ma10")), "state": _state(details.get("ma10"), details.get("ma20"))},
                {"label": "RSI14", "value": _round(details.get("rsi14")), "state": "strong" if 45 <= (details.get("rsi14") or 0) <= 70 else "watch"},
                {"label": "量比", "value": _round(details.get("volume_ratio")), "state": "strong" if (details.get("volume_ratio") or 0) >= 1.2 else "watch"},
                {"label": "5日漲幅", "value": _round(details.get("change_5d")), "state": "risk" if (details.get("change_5d") or 0) > 18 else "watch"},
            ],
            "chips": [
                {"label": "外資買賣超", "value": _round(latest_flow.get("foreign_net")), "state": "strong" if latest_flow.get("foreign_net", 0) > 0 else "risk"},
                {"label": "投信買賣超", "value": _round(latest_flow.get("trust_net")), "state": "strong" if latest_flow.get("trust_net", 0) > 0 else "watch"},
                {"label": "融資變化", "value": _round(latest_margin.get("margin_change")), "state": "watch"},
                {"label": "融券變化", "value": _round(latest_margin.get("short_change")), "state": "watch"},
            ],
            "sentiment": {
                "latest_news": details.get("news", [])[:5],
                "score": round(score.sentiment_score, 1),
            },
            "risk": {
                "stop_loss_price": score.stop_loss_price,
                "target_zone": score.target_zone,
                "avoid_reason": score.avoid_reason,
            },
        }

    def backtest(self, include_demo: bool = False) -> dict[str, Any]:
        storage = self.demo_storage if include_demo else self.storage
        scores = storage.get_scores(include_demo=include_demo)
        if include_demo and not scores:
            self.load_demo_scores()
            scores = storage.get_scores(include_demo=True)
        stocks = [
            Stock(score.stock_id, score.name, score.industry, score.market)
            for score in scores
        ]
        if not stocks:
            return {"strategy": "score>=68 and risk>=45", "results": []}
        prices_by_stock: dict[str, list[PriceBar]] = {}
        flows_by_stock: dict[str, list[InstitutionalFlow]] = {}
        margins_by_stock: dict[str, list[MarginBalance]] = {}
        news_by_stock: dict[str, list[NewsItem]] = {}
        for stock in stocks:
            prices_by_stock[stock.stock_id] = storage.get_prices(stock.stock_id)
            flows_by_stock[stock.stock_id] = storage.get_institutional_flows(stock.stock_id)
            margins_by_stock[stock.stock_id] = storage.get_margin_balances(stock.stock_id)
            news_by_stock[stock.stock_id] = storage.get_news(stock.stock_id)
        return run_backtest(stocks, prices_by_stock, flows_by_stock, margins_by_stock, news_by_stock)

    def remove_demo_data(self, clear_market_data: bool = True) -> int:
        demo_stock_ids = [item["stock_id"] for item in DEFAULT_WATCHLIST] if clear_market_data else []
        return self.storage.purge_demo_artifacts(demo_stock_ids)

    def _apply_filters(self, scores: list[ScoreResult], filters: dict[str, str]) -> list[ScoreResult]:
        min_score = _float_filter(filters.get("min_score"), 0)
        min_technical = _float_filter(filters.get("min_technical"), 0)
        min_chip = _float_filter(filters.get("min_chip"), 0)
        min_sentiment = _float_filter(filters.get("min_sentiment"), 0)
        min_risk = _float_filter(filters.get("min_risk"), 0)
        min_model_confidence = _float_filter(filters.get("min_model_confidence"), 0)
        min_volume = _float_filter(filters.get("min_volume"), 0)
        industry = filters.get("industry", "")
        direction = filters.get("direction", "")
        advice = filters.get("advice", "")
        foreign_or_trust = filters.get("foreign_or_trust_only", "").lower() in {"1", "true", "yes"}
        exclude_high_risk = filters.get("exclude_high_risk", "").lower() in {"1", "true", "yes"}
        require_ma_bullish = _bool_filter(filters.get("ma_bullish"))
        require_macd_bullish = _bool_filter(filters.get("macd_bullish"))
        require_volume_breakout = _bool_filter(filters.get("volume_breakout"))
        require_breakout = _bool_filter(filters.get("breakout_20d"))
        require_sentiment_positive = _bool_filter(filters.get("sentiment_positive"))
        require_model_bullish = _bool_filter(filters.get("local_model_bullish"))
        output: list[ScoreResult] = []
        for score in scores:
            if score.buy_score < min_score:
                continue
            if score.technical_score < min_technical:
                continue
            if score.chip_score < min_chip:
                continue
            if score.sentiment_score < min_sentiment:
                continue
            if score.risk_score < min_risk:
                continue
            if industry and industry != "all" and score.industry != industry:
                continue
            score_direction = score.details.get("direction", "")
            if direction and direction != "all" and score_direction != direction:
                continue
            if advice and advice != "all" and score.decision != advice:
                continue
            if min_volume and (score.details.get("latest_volume") or 0) < min_volume:
                continue
            latest_flow = score.details.get("latest_flow") or {}
            if foreign_or_trust and latest_flow.get("foreign_net", 0) <= 0 and latest_flow.get("trust_net", 0) <= 0:
                continue
            if exclude_high_risk and score.risk_score < 52:
                continue
            flags = score.details.get("filter_flags") or {}
            local_model = score.details.get("local_model") or {}
            if min_model_confidence and (local_model.get("confidence") or 0) < min_model_confidence:
                continue
            if require_ma_bullish and not flags.get("ma_bullish"):
                continue
            if require_macd_bullish and not flags.get("macd_bullish"):
                continue
            if require_volume_breakout and not flags.get("volume_breakout"):
                continue
            if require_breakout and not flags.get("breakout_20d"):
                continue
            if require_sentiment_positive and not flags.get("sentiment_positive"):
                continue
            if require_model_bullish and local_model.get("label") != "本地模型偏多":
                continue
            output.append(score)
        return output

    def _run_response(self, scores: list[ScoreResult], source: str) -> dict[str, Any]:
        return {
            "source": source,
            "run_date": date.today().isoformat(),
            "count": len(scores),
            "items": [score.to_dict() for score in scores],
        }


def _round(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _state(value: Any, comparison: Any) -> str:
    if value is None or comparison is None:
        return "watch"
    return "strong" if float(value) > float(comparison) else "risk"


def _float_filter(value: str | None, default: float) -> float:
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _bool_filter(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}
