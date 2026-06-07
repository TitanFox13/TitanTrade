"""Main backtest engine — ties everything together.

Usage:
    python -m titantrade backtest --data-dir data/historical
    python -m titantrade download-history --data-dir data/historical
"""

from __future__ import annotations

from typing import Any

from titantrade.backtest.data_loader import load_historical_data
from titantrade.backtest.metrics import compute_metrics
from titantrade.backtest.simulator import PortfolioSimulator
from titantrade.backtest.synthetic_thesis import generate_synthetic_thesis


# Static sector map for backtest (avoids FMP API calls)
SECTOR_MAP = {
    "CRWD": "Technology", "ANET": "Technology",
    "LLY": "Healthcare", "DXCM": "Healthcare", "HCA": "Healthcare",
    "JPM": "Financials", "GS": "Financials",
    "DVN": "Energy", "FANG": "Energy",
    "URI": "Industrials", "GE": "Industrials",
    "DASH": "Consumer Discretionary", "DECK": "Consumer Discretionary",
    "FCX": "Materials", "EQIX": "Real Estate",
    # Legacy watchlist tickers
    "AAPL": "Technology", "NVDA": "Technology", "TSLA": "Consumer Discretionary",
    "MSFT": "Technology", "AMZN": "Consumer Discretionary", "GOOGL": "Communication Services",
    "META": "Communication Services", "BRK.B": "Financials",
}


def run_backtest(
    data_dir: str,
    tickers: list[str] | None = None,
    initial_capital: float = 100_000.0,
    start_date: str | None = None,
    end_date: str | None = None,
    thesis_interval_days: int = 7,
    use_confidence_scaling: bool = False,
    strategy_v2: bool = False,
) -> dict[str, Any]:
    """Run a full backtest simulation.

    Args:
        data_dir: Directory with {TICKER}.json OHLCV files
        tickers: Stocks to trade (default: current watchlist)
        initial_capital: Starting cash
        start_date: Backtest start (YYYY-MM-DD)
        end_date: Backtest end (YYYY-MM-DD)
        thesis_interval_days: How often to generate new thesis (default: weekly)
        use_confidence_scaling: If True, scale position size by confidence
            (0.7x at 0.70 confidence to 1.3x at 1.00). Defaults to False so
            pre-existing backtest calls behave identically.
    """
    if tickers is None:
        tickers = list(SECTOR_MAP.keys())[:15]

    # Load data
    all_data = load_historical_data(tickers + ["SPY"], data_dir, start_date, end_date)
    spy_bars = all_data.pop("SPY", [])

    if not all_data:
        return {"error": "No historical data loaded"}

    # Build date index: all unique dates across all tickers
    all_dates: set[str] = set()
    for bars in all_data.values():
        for b in bars:
            all_dates.add(b["date"])
    sorted_dates = sorted(all_dates)

    if not sorted_dates:
        return {"error": "No dates in historical data"}

    # Index bars by date for each ticker
    bars_by_date: dict[str, dict[str, dict]] = {}
    for ticker, bars in all_data.items():
        for b in bars:
            bars_by_date.setdefault(b["date"], {})[ticker] = b

    # SPY bars indexed by date for thesis generation
    spy_by_date: dict[str, dict] = {b["date"]: b for b in spy_bars}

    # Simulator
    sim = PortfolioSimulator(
        initial_capital=initial_capital,
        use_confidence_scaling=use_confidence_scaling,
        strategy_v2=strategy_v2,
    )

    # Track thesis generation schedule
    last_thesis_date = ""
    active_theses: dict[str, dict] = {}
    lookback = 250

    for i, date in enumerate(sorted_dates):
        day_bars = bars_by_date.get(date, {})
        # v2 needs the core ticker's bar in day_bars so manage_core_position
        # can rebalance. SPY was popped from all_data above (used separately
        # for thesis market context) — splice it back in.
        if strategy_v2 and date in spy_by_date:
            day_bars = dict(day_bars)
            day_bars[sim.core_ticker] = spy_by_date[date]

        # Generate new thesis every N days
        new_theses = None
        days_since = _date_diff(last_thesis_date, date) if last_thesis_date else thesis_interval_days
        if days_since >= thesis_interval_days:
            new_theses = {}
            for ticker in tickers:
                # Build lookback window
                ticker_bars = all_data.get(ticker, [])
                # Find bars up to current date
                hist = [b for b in ticker_bars if b["date"] <= date]
                hist = hist[-lookback:] if len(hist) > lookback else hist

                spy_hist = [b for b in spy_bars if b["date"] <= date]
                spy_hist = spy_hist[-lookback:] if len(spy_hist) > lookback else spy_hist

                thesis = generate_synthetic_thesis(
                    ticker, hist, spy_hist, SECTOR_MAP.get(ticker, "Unknown")
                )
                if thesis.get("thesis") == "BULLISH":
                    new_theses[ticker] = thesis
                    # Apply stop/TP to existing positions
                    sim.apply_thesis_levels(ticker, thesis)

                active_theses[ticker] = thesis
            last_thesis_date = date

        history_by_ticker: dict[str, list[dict]] | None = None
        if strategy_v2:
            history_by_ticker = {}
            for t, ts_bars in all_data.items():
                history_by_ticker[t] = [b for b in ts_bars if b["date"] <= date]
        sim.process_day(date, day_bars, new_theses, SECTOR_MAP, history_by_ticker)

    # Compute metrics
    metrics = compute_metrics(sim.equity_curve, sim.trade_log, spy_bars, initial_capital)

    result = {
        "config": {
            "initial_capital": initial_capital,
            "tickers": tickers,
            "start_date": sorted_dates[0] if sorted_dates else None,
            "end_date": sorted_dates[-1] if sorted_dates else None,
            "trading_days": len(sorted_dates),
            "thesis_interval_days": thesis_interval_days,
            "use_confidence_scaling": use_confidence_scaling,
        },
        "metrics": metrics,
        "trade_count": len(sim.trade_log),
        "final_equity_curve": sim.equity_curve[-10:] if sim.equity_curve else [],
    }

    return result


def run_ab_comparison(
    data_dir: str,
    tickers: list[str] | None = None,
    initial_capital: float = 100_000.0,
    start_date: str | None = None,
    end_date: str | None = None,
    thesis_interval_days: int = 7,
) -> dict[str, Any]:
    """Run the backtest twice — once with flat risk-per-trade, once with
    confidence-scaled sizing — and return a side-by-side comparison.

    This lets you empirically validate whether the 0.7x-1.3x confidence curve
    beats the flat 10% baseline on your historical data.
    """
    baseline = run_backtest(
        data_dir, tickers, initial_capital, start_date, end_date,
        thesis_interval_days, use_confidence_scaling=False,
    )
    scaled = run_backtest(
        data_dir, tickers, initial_capital, start_date, end_date,
        thesis_interval_days, use_confidence_scaling=True,
    )

    bm = baseline.get("metrics", {})
    sm = scaled.get("metrics", {})

    def _diff(key: str) -> dict[str, Any]:
        b = bm.get(key)
        s = sm.get(key)
        if b is None or s is None:
            return {"baseline": b, "scaled": s, "delta": None}
        try:
            return {
                "baseline": round(float(b), 4),
                "scaled": round(float(s), 4),
                "delta": round(float(s) - float(b), 4),
            }
        except (TypeError, ValueError):
            return {"baseline": b, "scaled": s, "delta": None}

    return {
        "baseline": baseline,
        "scaled": scaled,
        "comparison": {
            "total_return_pct": _diff("total_return_pct"),
            "alpha_vs_spy_pct": _diff("alpha_vs_spy_pct"),
            "sharpe_ratio": _diff("sharpe_ratio"),
            "sortino_ratio": _diff("sortino_ratio"),
            "max_drawdown_pct": _diff("max_drawdown_pct"),
            "win_rate_pct": _diff("win_rate_pct"),
            "profit_factor": _diff("profit_factor"),
            "trade_count": {
                "baseline": baseline.get("trade_count"),
                "scaled": scaled.get("trade_count"),
            },
        },
    }


def print_summary(result: dict[str, Any]) -> None:
    """Print a human-readable backtest summary."""
    if "error" in result:
        print(f"Backtest error: {result['error']}")
        return

    cfg = result["config"]
    m = result["metrics"]

    print("=" * 60)
    print("TITANTRADE BACKTEST RESULTS")
    print("=" * 60)
    print(f"Period:       {cfg['start_date']} to {cfg['end_date']} ({cfg['trading_days']} days)")
    print(f"Capital:      ${cfg['initial_capital']:,.0f}")
    print(f"Tickers:      {len(cfg['tickers'])}")
    print()
    print(f"Total Return: {m['total_return_pct']:+.1f}%  (${m['final_value']:,.0f})")
    print(f"SPY Return:   {m['spy_return_pct']:+.1f}%")
    print(f"Alpha:        {m['alpha_pct']:+.1f}%")
    print()
    print(f"Trades:       {m['total_trades']}")
    print(f"Win Rate:     {m['win_rate']:.0f}%")
    print(f"Avg Win:      {m['avg_win_pct']:+.1f}%")
    print(f"Avg Loss:     {m['avg_loss_pct']:+.1f}%")
    print(f"Profit Factor:{m['profit_factor']:.2f}")
    print()
    print(f"Max Drawdown: {m['max_drawdown_pct']:.1f}%  ({m['max_drawdown_days']}d)")
    print(f"Sharpe:       {m['sharpe_ratio']:.2f}")
    print(f"Sortino:      {m['sortino_ratio']:.2f}")
    print(f"Avg Hold:     {m['avg_holding_days']:.0f} days")
    print()
    print(f"Exit triggers: {m['exit_triggers']}")
    print("=" * 60)


def _date_diff(d1: str, d2: str) -> int:
    if not d1:
        return 999
    from datetime import datetime
    try:
        dt1 = datetime.strptime(d1[:10], "%Y-%m-%d")
        dt2 = datetime.strptime(d2[:10], "%Y-%m-%d")
        return (dt2 - dt1).days
    except (ValueError, TypeError):
        return 999
