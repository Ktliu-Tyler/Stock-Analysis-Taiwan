from __future__ import annotations

from datetime import date
from typing import Any

from .storage import Storage


class PortfolioService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def list_positions(self) -> dict[str, Any]:
        positions = [self._with_market_data(position) for position in self.storage.get_positions()]
        total_cost = sum(item["cost_basis"] for item in positions)
        total_value = sum(item["market_value"] for item in positions)
        unrealized_pnl = total_value - total_cost
        unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost else 0.0
        return {
            "summary": {
                "positions": len(positions),
                "total_cost": round(total_cost, 2),
                "total_value": round(total_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
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
            "horizon": str(body.get("horizon") or "短線1-5日"),
            "risk_profile": str(body.get("risk_profile") or "中等"),
            "notes": str(body.get("notes") or ""),
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
        item.update(
            {
                "shares": shares,
                "average_cost": average_cost,
                "latest_price": round(latest_price, 2),
                "market_value": round(market_value, 2),
                "cost_basis": round(cost_basis, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
                "score": score.to_dict() if score else None,
            }
        )
        return item


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
