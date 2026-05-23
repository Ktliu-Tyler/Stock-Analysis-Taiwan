from __future__ import annotations

from datetime import date
from typing import Any

from .storage import Storage


class PortfolioService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def list_positions(self) -> dict[str, Any]:
        positions = [self._with_market_data(position) for position in self.storage.get_positions()]
        active_positions = [item for item in positions if not item.get("closed")]
        total_cost = sum(item["cost_basis"] for item in active_positions)
        total_value = sum(item["market_value"] for item in active_positions)
        unrealized_pnl = total_value - total_cost
        unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost else 0.0
        realized_pnl = sum(item.get("realized_pnl", 0.0) for item in positions)
        by_horizon = self._group_by_horizon(active_positions)
        return {
            "summary": {
                "positions": len(active_positions),
                "all_positions": len(positions),
                "closed_positions": len(positions) - len(active_positions),
                "total_cost": round(total_cost, 2),
                "total_value": round(total_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
                "realized_pnl": round(realized_pnl, 2),
                "by_horizon": by_horizon,
            },
            "items": positions,
        }

    def add_position(self, body: dict[str, Any]) -> dict[str, Any]:
        position = self._normalize_position(body)
        position_id = self.storage.add_position(position)
        return {"id": position_id, "position": self._with_market_data(self.storage.get_position(position_id) or position)}

    def update_position(self, position_id: int, body: dict[str, Any]) -> dict[str, Any]:
        position = self._normalize_position(body)
        self.storage.update_position(position_id, position)
        return {"id": position_id, "position": self._with_market_data(self.storage.get_position(position_id) or position)}

    def delete_position(self, position_id: int) -> dict[str, Any]:
        self.storage.delete_position(position_id)
        return {"deleted": position_id}

    def sell_position(self, position_id: int, body: dict[str, Any]) -> dict[str, Any]:
        current = self.storage.get_position(position_id)
        if not current:
            raise ValueError("position_not_found")
        enriched = self._with_market_data(current)
        shares = _float(current.get("shares"), 0.0)
        sell_shares = _float(body.get("sell_shares") or body.get("shares"), shares)
        sell_shares = max(0.0, min(sell_shares, shares))
        if sell_shares <= 0:
            raise ValueError("sell_shares is required")
        sell_price = _float(body.get("sell_price") or body.get("price"), enriched.get("latest_price") or current.get("average_cost") or 0.0)
        if sell_price <= 0:
            raise ValueError("sell_price is required")
        remaining = round(shares - sell_shares, 6)
        is_closed = remaining <= 0
        position = dict(current)
        position.update(
            {
                "shares": 0.0 if is_closed else remaining,
                "sell_price": sell_price,
                "sell_date": str(body.get("sell_date") or date.today().isoformat()),
                "sell_shares": sell_shares,
                "closed": 1 if is_closed else 0,
                "position_status": "已賣出" if is_closed else "部分賣出",
                "notes": _append_note(current.get("notes", ""), f"賣出 {sell_shares:g} 股 @ {sell_price:g}"),
            }
        )
        self.storage.update_position(position_id, self._normalize_position(position))
        return {"id": position_id, "position": self._with_market_data(self.storage.get_position(position_id) or position)}

    def get_position_context(self, position_id: int) -> dict[str, Any] | None:
        position = self.storage.get_position(position_id)
        if not position:
            return None
        return self._with_market_data(position)

    def _normalize_position(self, body: dict[str, Any]) -> dict[str, Any]:
        stock_id = str(body.get("stock_id") or "").strip()
        if not stock_id:
            raise ValueError("stock_id is required")
        stock = self.storage.get_stock(stock_id)
        score = self.storage.get_score(stock_id)
        name = str(body.get("name") or (stock.name if stock else "") or (score.name if score else "") or stock_id).strip()
        return {
            "stock_id": stock_id,
            "name": name,
            "shares": _float(body.get("shares"), 0.0),
            "average_cost": _float(body.get("average_cost"), 0.0),
            "buy_date": str(body.get("buy_date") or date.today().isoformat()),
            "position_status": str(body.get("position_status") or "已持有"),
            "horizon": normalize_horizon(body.get("horizon") or body.get("analysis_mode") or "短期"),
            "risk_profile": str(body.get("risk_profile") or "中等"),
            "notes": str(body.get("notes") or ""),
            "sell_price": _float(body.get("sell_price"), 0.0),
            "sell_date": str(body.get("sell_date") or ""),
            "sell_shares": _float(body.get("sell_shares"), 0.0),
            "closed": 1 if _bool(body.get("closed")) or str(body.get("position_status") or "") == "已賣出" else 0,
        }

    def _with_market_data(self, position: dict[str, Any]) -> dict[str, Any]:
        item = dict(position)
        stock_id = str(item["stock_id"])
        score = self.storage.get_score(stock_id)
        latest_price = _latest_price_from_score(score) or _latest_price_from_prices(self.storage.get_prices(stock_id))
        shares = _float(item.get("shares"), 0.0)
        average_cost = _float(item.get("average_cost"), 0.0)
        cost_basis = shares * average_cost
        market_value = shares * latest_price
        unrealized_pnl = market_value - cost_basis
        unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis else 0.0
        sell_price = _float(item.get("sell_price"), 0.0)
        sell_shares = _float(item.get("sell_shares"), 0.0)
        realized_cost = sell_shares * average_cost
        realized_pnl = (sell_price - average_cost) * sell_shares if sell_price and sell_shares else 0.0
        closed = bool(int(_float(item.get("closed"), 0.0))) or str(item.get("position_status")) == "已賣出"
        item.update(
            {
                "shares": shares,
                "average_cost": average_cost,
                "latest_price": round(latest_price, 2),
                "market_value": 0.0 if closed else round(market_value, 2),
                "cost_basis": 0.0 if closed else round(cost_basis, 2),
                "unrealized_pnl": 0.0 if closed else round(unrealized_pnl, 2),
                "unrealized_pnl_pct": 0.0 if closed else round(unrealized_pnl_pct, 2),
                "sell_price": round(sell_price, 2),
                "sell_shares": sell_shares,
                "realized_cost": round(realized_cost, 2),
                "realized_pnl": round(realized_pnl, 2),
                "realized_pnl_pct": round(realized_pnl / realized_cost * 100, 2) if realized_cost else 0.0,
                "closed": closed,
                "horizon_category": normalize_horizon(item.get("horizon")),
                "score": score.to_dict() if score else None,
            }
        )
        return item

    def _group_by_horizon(self, positions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        output = {
            "短期": {"label": "短期", "positions": 0, "market_value": 0.0, "unrealized_pnl": 0.0},
            "中期": {"label": "中期", "positions": 0, "market_value": 0.0, "unrealized_pnl": 0.0},
            "長期": {"label": "長期", "positions": 0, "market_value": 0.0, "unrealized_pnl": 0.0},
        }
        for item in positions:
            key = normalize_horizon(item.get("horizon"))
            bucket = output[key]
            bucket["positions"] += 1
            bucket["market_value"] += item.get("market_value", 0.0)
            bucket["unrealized_pnl"] += item.get("unrealized_pnl", 0.0)
        for bucket in output.values():
            bucket["market_value"] = round(bucket["market_value"], 2)
            bucket["unrealized_pnl"] = round(bucket["unrealized_pnl"], 2)
        return output


def _latest_price_from_score(score) -> float:
    if not score:
        return 0.0
    details = score.details or {}
    return _float(details.get("latest_price") or score.entry_watch_price, 0.0)


def _latest_price_from_prices(prices) -> float:
    if not prices:
        return 0.0
    return _float(prices[-1].close, 0.0)


def _float(value: Any, default: float) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_horizon(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"short", "短線", "短期", "短線1-5日", "1-5日"}:
        return "短期"
    if text in {"swing", "mid", "medium", "波段", "中期", "波段2-8週", "2-8週"}:
        return "中期"
    if text in {"long", "longterm", "long-term", "長線", "長期", "中長線3-12月", "3-12月"}:
        return "長期"
    if "長" in text:
        return "長期"
    if "波段" in text or "中" in text:
        return "中期"
    return "短期"


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _append_note(notes: str, extra: str) -> str:
    notes = str(notes or "").strip()
    return f"{notes}\n{extra}".strip() if notes else extra
