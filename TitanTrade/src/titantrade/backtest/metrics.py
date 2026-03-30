"""Backtest performance metrics computation."""

from __future__ import annotations

import math
from typing import Any


def compute_metrics(
    equity_curve: list[dict[str, Any]],
    trade_log: list[dict[str, Any]],
    spy_bars: list[dict[str, Any]] | None = None,
    initial_capital: float = 100_000.0,
) -> dict[str, Any]:
    """Compute performance metrics from backtest results."""
    if not equity_curve:
        return {"error": "Empty equity curve"}

    final_value = equity_curve[-1]["portfolio_value"]
    total_return_pct = (final_value - initial_capital) / initial_capital * 100

    # SPY benchmark
    spy_return_pct = 0.0
    if spy_bars and len(spy_bars) >= 2:
        spy_start = spy_bars[0]["close"]
        spy_end = spy_bars[-1]["close"]
        spy_return_pct = (spy_end - spy_start) / spy_start * 100

    # Trade statistics
    sells = [t for t in trade_log if t["action"] == "SELL"]
    wins = [t for t in sells if t.get("pnl_pct", 0) > 0]
    losses = [t for t in sells if t.get("pnl_pct", 0) <= 0]

    win_rate = len(wins) / len(sells) * 100 if sells else 0
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
    avg_hold = sum(t.get("days_held", 0) for t in sells) / len(sells) if sells else 0

    gross_wins = sum(t["pnl_pct"] for t in wins) if wins else 0
    gross_losses = abs(sum(t["pnl_pct"] for t in losses)) if losses else 0
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else float("inf")

    # Max drawdown
    peak = initial_capital
    max_dd = 0.0
    max_dd_duration = 0
    dd_start = 0
    for i, point in enumerate(equity_curve):
        val = point["portfolio_value"]
        if val > peak:
            peak = val
            dd_start = i
        dd = (peak - val) / peak * 100
        if dd > max_dd:
            max_dd = dd
            max_dd_duration = i - dd_start

    # Sharpe ratio (annualized, 252 trading days)
    if len(equity_curve) >= 2:
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]["portfolio_value"]
            curr = equity_curve[i]["portfolio_value"]
            if prev > 0:
                daily_returns.append((curr - prev) / prev)

        if daily_returns:
            mean_ret = sum(daily_returns) / len(daily_returns)
            std_ret = (sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
            sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0

            # Sortino (downside deviation only)
            downside = [r for r in daily_returns if r < 0]
            down_std = (sum(r ** 2 for r in downside) / len(downside)) ** 0.5 if downside else 0
            sortino = (mean_ret / down_std * math.sqrt(252)) if down_std > 0 else 0
        else:
            sharpe = sortino = 0.0
    else:
        sharpe = sortino = 0.0

    # Exit trigger breakdown
    triggers: dict[str, int] = {}
    for t in sells:
        trig = t.get("trigger", "unknown")
        triggers[trig] = triggers.get(trig, 0) + 1

    return {
        "total_return_pct": round(total_return_pct, 2),
        "spy_return_pct": round(spy_return_pct, 2),
        "alpha_pct": round(total_return_pct - spy_return_pct, 2),
        "final_value": round(final_value, 2),
        "total_trades": len(sells),
        "win_rate": round(win_rate, 1),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "max_drawdown_days": max_dd_duration,
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "avg_holding_days": round(avg_hold, 1),
        "exit_triggers": triggers,
    }
