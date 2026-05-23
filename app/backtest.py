from __future__ import annotations

from .models import InstitutionalFlow, MarginBalance, NewsItem, PriceBar, Stock
from .scoring import ANALYSIS_MODE_CONFIGS, normalize_analysis_mode, score_stock


def run_backtest(
    stocks: list[Stock],
    prices_by_stock: dict[str, list[PriceBar]],
    flows_by_stock: dict[str, list[InstitutionalFlow]] | None = None,
    margins_by_stock: dict[str, list[MarginBalance]] | None = None,
    news_by_stock: dict[str, list[NewsItem]] | None = None,
    analysis_mode: str = "short",
) -> dict:
    flows_by_stock = flows_by_stock or {}
    margins_by_stock = margins_by_stock or {}
    news_by_stock = news_by_stock or {}
    mode = normalize_analysis_mode(analysis_mode)
    mode_config = ANALYSIS_MODE_CONFIGS[mode]
    horizons = {
        "short": [1, 3, 5],
        "swing": [10, 20, 40],
        "long": [20, 60, 90],
    }[mode]
    results = []
    for horizon in horizons:
        trades = []
        equity = 1.0
        equity_curve = [equity]
        for stock in stocks:
            prices = sorted(prices_by_stock.get(stock.stock_id, []), key=lambda item: item.date)
            if len(prices) < 45 + horizon:
                continue
            flows = sorted(flows_by_stock.get(stock.stock_id, []), key=lambda item: item.date)
            margins = sorted(margins_by_stock.get(stock.stock_id, []), key=lambda item: item.date)
            for index in range(35, len(prices) - horizon):
                day = prices[index].date
                day_flows = [item for item in flows if item.date <= day]
                day_margins = [item for item in margins if item.date <= day]
                try:
                    score = score_stock(
                        stock,
                        prices[: index + 1],
                        day_flows,
                        day_margins,
                        news_by_stock.get(stock.stock_id, []),
                        run_date=day,
                        data_source="backtest",
                        analysis_mode=mode,
                    )
                except ValueError:
                    continue
                if score.buy_score < float(mode_config["min_watch_score"]) + 8 or score.risk_score < float(mode_config["min_risk_score"]) - 5:
                    continue
                entry = prices[index].close
                exit_price = prices[index + horizon].close
                if entry <= 0:
                    continue
                trade_return = exit_price / entry - 1
                trades.append(trade_return)
                equity *= 1 + trade_return / 20
                equity_curve.append(equity)
        win_count = sum(1 for item in trades if item > 0)
        average_return = sum(trades) / len(trades) * 100 if trades else 0.0
        results.append(
            {
                "horizon_days": horizon,
                "trades": len(trades),
                "win_rate": round(win_count / len(trades) * 100, 1) if trades else 0.0,
                "average_return": round(average_return, 2),
                "max_drawdown": round(_max_drawdown(equity_curve) * 100, 2),
            }
        )
    return {"strategy": f"{mode_config['label']} score/risk mode", "analysis_mode": mode, "analysis_mode_label": mode_config["label"], "results": results}


def _max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak:
            drawdown = min(drawdown, value / peak - 1)
    return abs(drawdown)
