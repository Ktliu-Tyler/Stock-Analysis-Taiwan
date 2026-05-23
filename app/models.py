from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Stock:
    stock_id: str
    name: str
    industry: str = "未分類"
    market: str = "twse"


@dataclass(frozen=True)
class PriceBar:
    date: str
    stock_id: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float = 0.0


@dataclass(frozen=True)
class InstitutionalFlow:
    date: str
    stock_id: str
    foreign_net: float = 0.0
    trust_net: float = 0.0
    dealer_net: float = 0.0
    total_net: float = 0.0


@dataclass(frozen=True)
class MarginBalance:
    date: str
    stock_id: str
    margin_balance: float = 0.0
    short_balance: float = 0.0
    margin_change: float = 0.0
    short_change: float = 0.0


@dataclass(frozen=True)
class NewsItem:
    title: str
    stock_id: str = ""
    summary: str = ""
    source: str = "unknown"
    published_at: str = ""
    url: str = ""
    sentiment: float = 0.0


@dataclass
class ScoreResult:
    stock_id: str
    name: str
    industry: str
    market: str
    run_date: str
    buy_score: float
    technical_score: float
    chip_score: float
    sentiment_score: float
    risk_score: float
    entry_watch_price: float
    stop_loss_price: float
    target_zone: str
    buy_reason: str
    avoid_reason: str
    data_freshness: str
    decision: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["buy_score"] = round(self.buy_score, 1)
        payload["technical_score"] = round(self.technical_score, 1)
        payload["chip_score"] = round(self.chip_score, 1)
        payload["sentiment_score"] = round(self.sentiment_score, 1)
        payload["risk_score"] = round(self.risk_score, 1)
        payload["entry_watch_price"] = round(self.entry_watch_price, 2)
        payload["stop_loss_price"] = round(self.stop_loss_price, 2)
        return payload

