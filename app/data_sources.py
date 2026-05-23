from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

from .config import DEFAULT_WATCHLIST, FINMIND_TOKEN, REQUEST_TIMEOUT, SCAN_LIMIT, USER_AGENT, configured_watchlist
from .models import InstitutionalFlow, MarginBalance, NewsItem, PriceBar, Stock


class DataFetchError(RuntimeError):
    pass


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("--", "")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _text(row: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _json_get(url: str, params: dict[str, Any] | None = None) -> Any:
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})
    full_url = f"{url}?{query}" if query else url
    request = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except Exception as exc:  # urllib raises several concrete types; grouping keeps caller logic simple.
        raise DataFetchError(str(exc)) from exc


class MarketDataClient:
    finmind_v4 = "https://api.finmindtrade.com/api/v4/data"
    finmind_v3 = "https://api.finmindtrade.com/api/v3/data"
    twse_daily_all = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    twse_news = "https://openapi.twse.com.tw/v1/news/newsList"

    def _finmind_data(
        self,
        dataset: str,
        stock_id: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        v4_params: dict[str, Any] = {
            "dataset": dataset,
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": FINMIND_TOKEN,
        }
        try:
            payload = _json_get(self.finmind_v4, v4_params)
            data = payload.get("data", payload) if isinstance(payload, dict) else payload
            if isinstance(data, list) and data:
                return data
        except DataFetchError:
            pass

        v3_params: dict[str, Any] = {
            "dataset": dataset,
            "stock_id": stock_id,
            "date": start_date,
            "end_date": end_date,
            "token": FINMIND_TOKEN,
        }
        payload = _json_get(self.finmind_v3, v3_params)
        data = payload.get("data", payload) if isinstance(payload, dict) else payload
        if isinstance(data, list):
            return data
        return []

    def get_stock_info(self) -> list[Stock]:
        rows = self._finmind_data("TaiwanStockInfo")
        stocks: list[Stock] = []
        for row in rows:
            stock_id = _text(row, ["stock_id", "code", "有價證券代號"])
            if not stock_id or not stock_id.isdigit() or len(stock_id) != 4:
                continue
            stocks.append(
                Stock(
                    stock_id=stock_id,
                    name=_text(row, ["stock_name", "name", "有價證券名稱"], stock_id),
                    industry=_text(row, ["industry_category", "industry", "產業別"], "未分類"),
                    market=_text(row, ["market", "type"], "twse").lower(),
                )
            )
        return stocks

    def get_twse_latest_snapshot(self) -> list[dict[str, Any]]:
        payload = _json_get(self.twse_daily_all)
        if not isinstance(payload, list):
            return []
        snapshots: list[dict[str, Any]] = []
        for row in payload:
            stock_id = _text(row, ["Code", "證券代號", "stock_id"])
            if not stock_id.isdigit() or len(stock_id) != 4:
                continue
            volume = _to_float(row.get("TradeVolume") or row.get("成交股數") or row.get("Trading_Volume"))
            snapshots.append(
                {
                    "stock_id": stock_id,
                    "name": _text(row, ["Name", "證券名稱", "stock_name"], stock_id),
                    "volume": volume,
                    "close": _to_float(row.get("ClosingPrice") or row.get("收盤價") or row.get("close")),
                }
            )
        return snapshots

    def select_universe(self) -> tuple[list[Stock], str]:
        defaults = {item["stock_id"]: Stock(**item) for item in DEFAULT_WATCHLIST}
        configured = configured_watchlist()
        if configured:
            output = [defaults.get(stock_id, Stock(stock_id=stock_id, name=stock_id)) for stock_id in configured]
            return output[:SCAN_LIMIT], "env_watchlist"

        stock_info: dict[str, Stock] = {}
        try:
            stock_info = {stock.stock_id: stock for stock in self.get_stock_info()}
        except DataFetchError:
            stock_info = {}

        try:
            snapshots = self.get_twse_latest_snapshot()
            snapshots.sort(key=lambda row: row["volume"], reverse=True)
            selected = []
            for row in snapshots:
                stock_id = row["stock_id"]
                selected.append(stock_info.get(stock_id) or defaults.get(stock_id) or Stock(stock_id, row["name"]))
                if len(selected) >= SCAN_LIMIT:
                    return selected, "twse_top_volume"
        except DataFetchError:
            pass

        return list(defaults.values())[:SCAN_LIMIT], "default_watchlist"

    def get_prices(self, stock_id: str, days: int = 120) -> list[PriceBar]:
        end = date.today()
        start = end - timedelta(days=days * 2)
        rows = self._finmind_data("TaiwanStockPrice", stock_id, start.isoformat(), end.isoformat())
        prices: list[PriceBar] = []
        for row in rows:
            day = _text(row, ["date"])
            if not day:
                continue
            prices.append(
                PriceBar(
                    date=day,
                    stock_id=stock_id,
                    open=_to_float(row.get("open")),
                    high=_to_float(row.get("max") or row.get("high")),
                    low=_to_float(row.get("min") or row.get("low")),
                    close=_to_float(row.get("close")),
                    volume=_to_float(row.get("Trading_Volume") or row.get("trading_volume") or row.get("volume")),
                    amount=_to_float(row.get("Trading_money") or row.get("amount")),
                )
            )
        return sorted([item for item in prices if item.close > 0], key=lambda item: item.date)

    def get_institutional_flows(self, stock_id: str, days: int = 60) -> list[InstitutionalFlow]:
        end = date.today()
        start = end - timedelta(days=days * 2)
        rows = self._finmind_data("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start.isoformat(), end.isoformat())
        grouped: dict[str, dict[str, float]] = {}
        for row in rows:
            day = _text(row, ["date"])
            if not day:
                continue
            name = _text(row, ["name", "institutional_investors", "type"])
            buy = _to_float(row.get("buy") or row.get("buy_amount") or row.get("買進股數"))
            sell = _to_float(row.get("sell") or row.get("sell_amount") or row.get("賣出股數"))
            net = _to_float(row.get("net") or row.get("buy_sell") or row.get("買賣超股數"), buy - sell)
            bucket = grouped.setdefault(day, {"foreign_net": 0.0, "trust_net": 0.0, "dealer_net": 0.0})
            lowered = name.lower()
            if "投信" in name or "trust" in lowered:
                bucket["trust_net"] += net
            elif "dealer" in lowered or "自營" in name:
                bucket["dealer_net"] += net
            else:
                bucket["foreign_net"] += net
        flows = [
            InstitutionalFlow(
                date=day,
                stock_id=stock_id,
                foreign_net=values["foreign_net"],
                trust_net=values["trust_net"],
                dealer_net=values["dealer_net"],
                total_net=sum(values.values()),
            )
            for day, values in grouped.items()
        ]
        return sorted(flows, key=lambda item: item.date)

    def get_margin(self, stock_id: str, days: int = 60) -> list[MarginBalance]:
        end = date.today()
        start = end - timedelta(days=days * 2)
        rows = self._finmind_data("TaiwanStockMarginPurchaseShortSale", stock_id, start.isoformat(), end.isoformat())
        output: list[MarginBalance] = []
        previous_margin = 0.0
        previous_short = 0.0
        for row in rows:
            day = _text(row, ["date"])
            if not day:
                continue
            margin_balance = _to_float(
                row.get("MarginPurchaseTodayBalance")
                or row.get("margin_purchase_today_balance")
                or row.get("融資今日餘額")
            )
            short_balance = _to_float(
                row.get("ShortSaleTodayBalance")
                or row.get("short_sale_today_balance")
                or row.get("融券今日餘額")
            )
            margin_change = margin_balance - previous_margin if previous_margin else 0.0
            short_change = short_balance - previous_short if previous_short else 0.0
            output.append(
                MarginBalance(
                    date=day,
                    stock_id=stock_id,
                    margin_balance=margin_balance,
                    short_balance=short_balance,
                    margin_change=margin_change,
                    short_change=short_change,
                )
            )
            previous_margin = margin_balance
            previous_short = short_balance
        return sorted(output, key=lambda item: item.date)

    def get_news(self, stock: Stock, days: int = 14) -> list[NewsItem]:
        news: list[NewsItem] = []
        try:
            rows = self._finmind_data("TaiwanStockNews", stock.stock_id, "", "")
            for row in rows[:20]:
                title = _text(row, ["title", "headline"])
                if not title:
                    continue
                news.append(
                    NewsItem(
                        stock_id=stock.stock_id,
                        title=title,
                        summary=_text(row, ["content", "summary"]),
                        source=_text(row, ["source"], "FinMind"),
                        published_at=_text(row, ["date", "published_at"]),
                        url=_text(row, ["link", "url"]),
                    )
                )
        except DataFetchError:
            pass

        if news:
            return news[:12]

        try:
            rows = _json_get(self.twse_news)
            if isinstance(rows, list):
                for row in rows:
                    title = _text(row, ["title", "Title", "標題", "subject"])
                    summary = _text(row, ["content", "Content", "內容", "description"])
                    if stock.stock_id not in title + summary and stock.name not in title + summary:
                        continue
                    news.append(
                        NewsItem(
                            stock_id=stock.stock_id,
                            title=title,
                            summary=summary,
                            source="TWSE",
                            published_at=_text(row, ["date", "Date", "發布日期"]),
                            url=_text(row, ["url", "URL", "link"]),
                        )
                    )
        except DataFetchError:
            pass
        time.sleep(0.05)
        return news[:12]

