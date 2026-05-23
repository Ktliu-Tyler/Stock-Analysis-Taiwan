from __future__ import annotations

import math
from datetime import date, timedelta

from .config import DEFAULT_WATCHLIST
from .models import InstitutionalFlow, MarginBalance, NewsItem, PriceBar, Stock


def business_days(days: int = 90) -> list[str]:
    today = date.today()
    cursor = today - timedelta(days=days * 2)
    output: list[str] = []
    while cursor <= today:
        if cursor.weekday() < 5:
            output.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return output[-days:]


def demo_market(days: int = 90) -> tuple[
    list[Stock],
    dict[str, list[PriceBar]],
    dict[str, list[InstitutionalFlow]],
    dict[str, list[MarginBalance]],
    dict[str, list[NewsItem]],
]:
    dates = business_days(days)
    stocks = [Stock(**item) for item in DEFAULT_WATCHLIST[:12]]
    prices: dict[str, list[PriceBar]] = {}
    flows: dict[str, list[InstitutionalFlow]] = {}
    margins: dict[str, list[MarginBalance]] = {}
    news: dict[str, list[NewsItem]] = {}

    for stock_index, stock in enumerate(stocks):
        base_price = 42 + stock_index * 18
        if stock.stock_id in {"2330", "2382", "3017"}:
            trend = 0.82
            flow_bias = 380_000
            news_tone = "positive"
        elif stock.stock_id in {"2454", "3231", "2308"}:
            trend = 0.42
            flow_bias = 180_000
            news_tone = "positive"
        elif stock.stock_id in {"2603", "2609"}:
            trend = -0.08
            flow_bias = -90_000
            news_tone = "mixed"
        else:
            trend = 0.12
            flow_bias = 30_000
            news_tone = "neutral"

        stock_prices: list[PriceBar] = []
        stock_flows: list[InstitutionalFlow] = []
        stock_margins: list[MarginBalance] = []
        close = base_price
        margin_balance = 6_000 + stock_index * 340
        short_balance = 500 + stock_index * 30
        for day_index, day in enumerate(dates):
            wave = math.sin(day_index / 4 + stock_index) * 1.2
            late_push = max(0, day_index - len(dates) + 18) * trend
            close = max(10, base_price + day_index * trend * 0.18 + late_push + wave)
            open_price = close * (1 + math.sin(day_index + stock_index) * 0.006)
            high = max(open_price, close) * (1.01 + abs(math.sin(day_index / 3)) * 0.006)
            low = min(open_price, close) * (0.99 - abs(math.cos(day_index / 5)) * 0.004)
            volume = 1_200_000 + stock_index * 80_000 + abs(math.sin(day_index / 2)) * 760_000
            if day_index > len(dates) - 8 and stock.stock_id in {"2330", "2382", "3017", "2454"}:
                volume *= 1.75
            stock_prices.append(
                PriceBar(
                    date=day,
                    stock_id=stock.stock_id,
                    open=round(open_price, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(close, 2),
                    volume=round(volume),
                    amount=round(volume * close),
                )
            )

            foreign_net = flow_bias + math.sin(day_index / 3 + stock_index) * 140_000
            trust_net = flow_bias * 0.35 + math.cos(day_index / 4) * 70_000
            dealer_net = flow_bias * 0.18 + math.sin(day_index / 2) * 35_000
            stock_flows.append(
                InstitutionalFlow(
                    date=day,
                    stock_id=stock.stock_id,
                    foreign_net=round(foreign_net),
                    trust_net=round(trust_net),
                    dealer_net=round(dealer_net),
                    total_net=round(foreign_net + trust_net + dealer_net),
                )
            )

            margin_change = math.sin(day_index / 5 + stock_index) * 95
            short_change = math.cos(day_index / 6 + stock_index) * 30
            margin_balance += margin_change
            short_balance += short_change
            stock_margins.append(
                MarginBalance(
                    date=day,
                    stock_id=stock.stock_id,
                    margin_balance=round(max(margin_balance, 0)),
                    short_balance=round(max(short_balance, 0)),
                    margin_change=round(margin_change),
                    short_change=round(short_change),
                )
            )

        prices[stock.stock_id] = stock_prices
        flows[stock.stock_id] = stock_flows
        margins[stock.stock_id] = stock_margins
        if news_tone == "positive":
            stock_news = [
                NewsItem(
                    stock_id=stock.stock_id,
                    title=f"{stock.name}受惠AI伺服器需求，法人看好短線動能",
                    summary="營收成長與接單展望支撐買盤，投信與外資同步關注。",
                    source="demo",
                    published_at=dates[-2],
                    sentiment=0.75,
                ),
                NewsItem(
                    stock_id=stock.stock_id,
                    title=f"{stock.name}公告近期業績維持高檔",
                    summary="市場聚焦毛利率與產能利用率變化。",
                    source="demo",
                    published_at=dates[-5],
                    sentiment=0.45,
                ),
            ]
        elif news_tone == "mixed":
            stock_news = [
                NewsItem(
                    stock_id=stock.stock_id,
                    title=f"{stock.name}運價波動擴大，短線資金轉趨觀望",
                    summary="題材仍在，但波動與追價風險同步升高。",
                    source="demo",
                    published_at=dates[-3],
                    sentiment=-0.2,
                )
            ]
        else:
            stock_news = [
                NewsItem(
                    stock_id=stock.stock_id,
                    title=f"{stock.name}近期公告無重大異常",
                    summary="股價以技術與籌碼訊號為主要觀察依據。",
                    source="demo",
                    published_at=dates[-4],
                    sentiment=0.0,
                )
            ]
        news[stock.stock_id] = stock_news

    return stocks, prices, flows, margins, news

