"""Benchmark performance metrics — strategy vs SPY.

Computes beta, alpha, Sharpe, capture ratios, and drawdown from the Alpaca
portfolio-equity history against SPY, so the strategy can be judged on
RISK-ADJUSTED terms (alpha, Sharpe) rather than raw return.

Why this matters: a downside-protected, sub-1-beta strategy lags SPY in a
strong bull market *by construction* — it holds cash, runs stops that clip
the right tail, and keeps a partial passive core. Raw return vs SPY therefore
can't tell you whether the strategy is adding value or just under-exposed.
Beta isolates the market exposure; alpha is the return left over after that
exposure is paid for; Sharpe and capture ratios say whether the protection is
earning its keep. Those are the numbers that actually answer "can this
succeed, or will it always underperform?".

All the statistics live in the pure ``compute_metrics`` function (no I/O),
unit-tested with hand-computable fixtures. ``compute_benchmark`` wires it to
live data (Alpaca portfolio history + SPY daily closes), aligns the two series
by trading date, and persists the result to ``state/benchmark_metrics.json``.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from titantrade.config import STATE_DIR
from titantrade.logger import get_logger

log = get_logger("benchmark")

TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# Pure statistics helpers
# ---------------------------------------------------------------------------

def _returns(levels: list[float]) -> list[float]:
    """Simple daily returns from a level (price/equity) series."""
    out: list[float] = []
    for prev, cur in zip(levels, levels[1:]):
        out.append((cur / prev - 1.0) if prev else 0.0)
    return out


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _variance(xs: list[float], ddof: int = 1) -> float:
    n = len(xs)
    if n - ddof <= 0:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - ddof)


def _std(xs: list[float], ddof: int = 1) -> float:
    return math.sqrt(_variance(xs, ddof=ddof))


def _covariance(xs: list[float], ys: list[float], ddof: int = 1) -> float:
    n = len(xs)
    if n - ddof <= 0:
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - ddof)


def _prod_growth(returns: list[float]) -> float:
    """Cumulative total return: prod(1 + r) - 1."""
    acc = 1.0
    for r in returns:
        acc *= 1.0 + r
    return acc - 1.0


def _max_drawdown(levels: list[float]) -> float:
    """Largest peak-to-trough decline over the series (<= 0)."""
    if not levels:
        return 0.0
    peak = levels[0]
    mdd = 0.0
    for v in levels:
        if v > peak:
            peak = v
        if peak > 0:
            dd = v / peak - 1.0
            if dd < mdd:
                mdd = dd
    return mdd


def _r(value: float | None, ndigits: int) -> float | None:
    """Round, tolerating None (undefined metrics)."""
    return None if value is None else round(value, ndigits)


# ---------------------------------------------------------------------------
# Core metric computation (pure — fully unit-testable)
# ---------------------------------------------------------------------------

def compute_metrics(
    strategy_levels: list[float],
    spy_levels: list[float],
    rf_annual: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> dict[str, Any]:
    """Compute risk/return metrics of a strategy equity series vs SPY.

    ``strategy_levels`` and ``spy_levels`` are aligned, same-length series of
    daily levels (account equity and SPY close) on the SAME trading days.

    Returns a dict of metrics. ``beta`` and friends are ``None`` when they are
    mathematically undefined (e.g. SPY had zero variance over the window).
    With < 2 daily returns the result is flagged ``insufficient_data``.

    Risk-free rate defaults to 0 — the comparison is relative, and over short
    windows the rf term is negligible. It is a parameter so it can be set if
    desired (Jensen's alpha and Sharpe both net it out).
    """
    if len(strategy_levels) != len(spy_levels):
        raise ValueError("strategy and spy level series must be the same length")

    rp = _returns(strategy_levels)
    rm = _returns(spy_levels)
    n = len(rp)
    if n < 2:
        return {"insufficient_data": True, "n_days": n}

    rf_daily = rf_annual / periods_per_year
    mean_p, mean_m = _mean(rp), _mean(rm)
    std_p, std_m = _std(rp), _std(rm)
    var_m = _variance(rm)
    cov_pm = _covariance(rp, rm)

    beta = (cov_pm / var_m) if var_m > 0 else None
    alpha_daily = (
        (mean_p - rf_daily) - beta * (mean_m - rf_daily) if beta is not None else None
    )
    alpha_annual = alpha_daily * periods_per_year if alpha_daily is not None else None

    sharpe_p = ((mean_p - rf_daily) / std_p * math.sqrt(periods_per_year)) if std_p > 0 else None
    sharpe_m = ((mean_m - rf_daily) / std_m * math.sqrt(periods_per_year)) if std_m > 0 else None

    corr = (cov_pm / (std_p * std_m)) if (std_p > 0 and std_m > 0) else None
    r2 = corr ** 2 if corr is not None else None

    # Information ratio — active return per unit of active (tracking) risk.
    active = [a - b for a, b in zip(rp, rm)]
    std_active = _std(active)
    ir = (_mean(active) / std_active * math.sqrt(periods_per_year)) if std_active > 0 else None

    total_p = _prod_growth(rp)
    total_m = _prod_growth(rm)

    # Up/down capture — average strategy move on days SPY rose / fell, as a
    # fraction of SPY's average move on those days. up<1 + down<1 is the
    # signature of a defensive book (gives up some upside, eats less downside).
    up_p = [a for a, b in zip(rp, rm) if b > 0]
    up_m = [b for b in rm if b > 0]
    dn_p = [a for a, b in zip(rp, rm) if b < 0]
    dn_m = [b for b in rm if b < 0]
    up_cap = (_mean(up_p) / _mean(up_m)) if up_m and _mean(up_m) != 0 else None
    down_cap = (_mean(dn_p) / _mean(dn_m)) if dn_m and _mean(dn_m) != 0 else None

    return {
        "insufficient_data": False,
        "n_days": n,
        "beta": _r(beta, 3),
        "alpha_annual_pct": _r(alpha_annual * 100, 2) if alpha_annual is not None else None,
        "sharpe_strategy": _r(sharpe_p, 2),
        "sharpe_spy": _r(sharpe_m, 2),
        "info_ratio": _r(ir, 2),
        "correlation": _r(corr, 3),
        "r_squared": _r(r2, 3),
        "vol_strategy_annual_pct": _r(std_p * math.sqrt(periods_per_year) * 100, 2),
        "vol_spy_annual_pct": _r(std_m * math.sqrt(periods_per_year) * 100, 2),
        "total_return_strategy_pct": _r(total_p * 100, 2),
        "total_return_spy_pct": _r(total_m * 100, 2),
        "excess_return_pct": _r((total_p - total_m) * 100, 2),
        "up_capture": _r(up_cap, 2),
        "down_capture": _r(down_cap, 2),
        "up_days": len(up_m),
        "down_days": len(dn_m),
        "max_drawdown_strategy_pct": _r(_max_drawdown(strategy_levels) * 100, 2),
        "max_drawdown_spy_pct": _r(_max_drawdown(spy_levels) * 100, 2),
        "rf_annual_pct": _r(rf_annual * 100, 2),
    }


def classify(metrics: dict[str, Any]) -> str:
    """One-line plain-English verdict from a metrics dict.

    Encodes the framing from the strategy review: the question is alpha and
    Sharpe, not raw return. Positive alpha + Sharpe >= SPY = adding value.
    """
    if metrics.get("insufficient_data"):
        return "Insufficient data — need at least a few trading days of history."

    alpha = metrics.get("alpha_annual_pct")
    sp, sm = metrics.get("sharpe_strategy"), metrics.get("sharpe_spy")
    better_sharpe = sp is not None and sm is not None and sp >= sm

    if alpha is None:
        return "Beta undefined (flat benchmark window) — cannot attribute alpha yet."
    if alpha > 0 and better_sharpe:
        return f"Adding value — positive alpha (+{alpha:.1f}%/yr) AND higher risk-adjusted return than SPY."
    if alpha > 0:
        return f"Positive alpha (+{alpha:.1f}%/yr) but Sharpe still below SPY — selection helps, ride is bumpier."
    if better_sharpe:
        return f"Negative alpha ({alpha:.1f}%/yr) but smoother than SPY — protection, not selection, is doing the work."
    return f"Negative alpha ({alpha:.1f}%/yr) and no Sharpe edge — currently dominated by just holding SPY."


# ---------------------------------------------------------------------------
# Live data wiring (impure)
# ---------------------------------------------------------------------------

def _period_for_lookback(days: int) -> str:
    """Map a lookback in days to an Alpaca portfolio-history ``period`` string."""
    if days <= 31:
        return "1M"
    if days <= 93:
        return "3M"
    if days <= 186:
        return "6M"
    if days <= 366:
        return "1A"
    return "all"


def _session_date(ts: int) -> str:
    """Map an Alpaca portfolio-history unix timestamp to its trading-session date.

    Alpaca stamps 1D end-of-day equity at the market close in US/Eastern, which
    is 20:00 ET — i.e. 00:00 UTC of the *following* calendar day. A naive UTC
    date is therefore one day late and would pair each strategy day with the
    next session's SPY close, corrupting beta/correlation. Converting in market
    time (America/New_York) yields the correct, DST-safe session date. Falls
    back to (UTC date − 1 day) only if the tz database is unavailable.
    """
    try:
        from zoneinfo import ZoneInfo

        return datetime.fromtimestamp(ts, ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001 — missing tzdata; crude but correct for 00:00Z stamps
        return (datetime.fromtimestamp(ts, tz=timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def _portfolio_equity_series(
    cfg: Any, period: str, since: str | None = None
) -> list[tuple[str, float]]:
    """Daily (session_date, equity) from Alpaca portfolio history, oldest-first.

    Equity points of 0 (days before the account had value) are dropped.
    Timestamps are mapped to the market-time session date (see _session_date).
    """
    from titantrade.broker import get_portfolio_history

    ph = get_portfolio_history(cfg, period=period, timeframe="1D")
    timestamps = ph.get("timestamp", []) or []
    equity = ph.get("equity", []) or []
    out: list[tuple[str, float]] = []
    for ts, eq in zip(timestamps, equity):
        if eq is None or eq <= 0:
            continue
        out.append((_session_date(ts), float(eq)))
    if since:
        out = [(d, e) for d, e in out if d >= since]
    return out


def _spy_close_series(cfg: Any, days: int) -> list[tuple[str, float]]:
    """Daily (date, close) for SPY, oldest-first."""
    from titantrade.market_data import get_ohlcv

    bars = get_ohlcv("SPY", cfg, days=days)
    out: list[tuple[str, float]] = []
    for b in bars:
        date = str(b.get("date") or b.get("t") or "")[:10]
        close = b.get("close", b.get("c"))
        if date and close:
            out.append((date, float(close)))
    return out


def _align(
    equity: list[tuple[str, float]], spy: list[tuple[str, float]]
) -> tuple[list[str], list[float], list[float]]:
    """Inner-join the two series on trading date (oldest-first)."""
    spy_map = dict(spy)
    dates: list[str] = []
    p: list[float] = []
    m: list[float] = []
    for date, eq in equity:
        if date in spy_map:
            dates.append(date)
            p.append(eq)
            m.append(spy_map[date])
    return dates, p, m


def compute_benchmark(
    cfg: Any,
    lookback_days: int = 90,
    since: str | None = None,
    rf_annual: float = 0.0,
    persist: bool = True,
) -> dict[str, Any]:
    """Fetch live data, align by date, compute metrics, and (optionally) persist.

    ``since`` (YYYY-MM-DD) overrides ``lookback_days`` to anchor the window —
    use it to exclude an early period (e.g. before the strategy stabilized).
    """
    # When a since-date is given, fetch a wide history and filter locally.
    wide = since is not None
    period = _period_for_lookback(366 if wide else lookback_days)
    spy_days = 400 if wide else lookback_days + 15

    equity = _portfolio_equity_series(cfg, period=period, since=since)
    spy = _spy_close_series(cfg, days=spy_days)
    dates, p, m = _align(equity, spy)

    # Trim to the trailing lookback window unless a since-date was given.
    if not since and lookback_days and len(dates) > lookback_days + 1:
        dates = dates[-(lookback_days + 1):]
        p = p[-(lookback_days + 1):]
        m = m[-(lookback_days + 1):]

    metrics = compute_metrics(p, m, rf_annual=rf_annual)
    metrics["window_start"] = dates[0] if dates else None
    metrics["window_end"] = dates[-1] if dates else None
    metrics["since"] = since
    metrics["lookback_days"] = None if since else lookback_days
    metrics["computed_at"] = datetime.now(timezone.utc).isoformat()
    metrics["verdict"] = classify(metrics)

    if persist:
        save_metrics(metrics)
    return metrics


def save_metrics(metrics: dict[str, Any]) -> None:
    """Persist the latest metrics to state/benchmark_metrics.json."""
    path = STATE_DIR / "benchmark_metrics.json"
    with open(path, "w") as f:
        json.dump(metrics, f, indent=2)


def load_metrics() -> dict[str, Any] | None:
    """Load the last-computed metrics, or None if not yet computed."""
    path = STATE_DIR / "benchmark_metrics.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def format_summary_line(metrics: dict[str, Any] | None) -> str | None:
    """Compact one-line summary for the Discord daily summary, or None to skip."""
    if not metrics or metrics.get("insufficient_data"):
        return None
    beta = metrics.get("beta")
    alpha = metrics.get("alpha_annual_pct")
    sp, sm = metrics.get("sharpe_strategy"), metrics.get("sharpe_spy")
    tp, tm = metrics.get("total_return_strategy_pct"), metrics.get("total_return_spy_pct")
    n = metrics.get("n_days")

    parts: list[str] = []
    if beta is not None:
        parts.append(f"β {beta:.2f}")
    if alpha is not None:
        parts.append(f"α {alpha:+.1f}%/yr")
    if sp is not None and sm is not None:
        parts.append(f"Sharpe {sp:.2f} vs SPY {sm:.2f}")
    if tp is not None and tm is not None:
        parts.append(f"{n}d ret {tp:+.1f}% vs SPY {tm:+.1f}%")
    return " | ".join(parts) if parts else None


# ---------------------------------------------------------------------------
# CLI report
# ---------------------------------------------------------------------------

def _fmt(v: Any, suffix: str = "") -> str:
    return "n/a" if v is None else f"{v}{suffix}"


def print_report(metrics: dict[str, Any]) -> None:
    """Human-readable report for the `benchmark` CLI command."""
    print("=" * 64)
    print("  TitanTrade — performance vs SPY")
    print("=" * 64)
    if metrics.get("insufficient_data"):
        print(f"  Insufficient data ({metrics.get('n_days', 0)} daily returns).")
        return
    win = f"{metrics.get('window_start')} → {metrics.get('window_end')}"
    print(f"  Window: {win}  ({metrics['n_days']} trading days)")
    print("-" * 64)
    print(f"  Total return    strategy {_fmt(metrics['total_return_strategy_pct'], '%'):>10}"
          f"   SPY {_fmt(metrics['total_return_spy_pct'], '%'):>10}")
    print(f"  Excess (vs SPY) {_fmt(metrics['excess_return_pct'], '%'):>10}")
    print("-" * 64)
    print(f"  Beta            {_fmt(metrics['beta']):>10}")
    print(f"  Alpha (ann.)    {_fmt(metrics['alpha_annual_pct'], '%'):>10}")
    print(f"  Sharpe          strategy {_fmt(metrics['sharpe_strategy']):>10}"
          f"   SPY {_fmt(metrics['sharpe_spy']):>10}")
    print(f"  Info ratio      {_fmt(metrics['info_ratio']):>10}")
    print(f"  Correlation     {_fmt(metrics['correlation']):>10}   R² {_fmt(metrics['r_squared'])}")
    print(f"  Volatility(ann) strategy {_fmt(metrics['vol_strategy_annual_pct'], '%'):>10}"
          f"   SPY {_fmt(metrics['vol_spy_annual_pct'], '%'):>10}")
    print(f"  Up capture      {_fmt(metrics['up_capture'])}  ({metrics['up_days']} up days)")
    print(f"  Down capture    {_fmt(metrics['down_capture'])}  ({metrics['down_days']} down days)")
    print(f"  Max drawdown    strategy {_fmt(metrics['max_drawdown_strategy_pct'], '%'):>10}"
          f"   SPY {_fmt(metrics['max_drawdown_spy_pct'], '%'):>10}")
    print("-" * 64)
    print(f"  Verdict: {metrics.get('verdict', classify(metrics))}")
    print("=" * 64)


def main() -> None:
    """CLI: `python -m titantrade benchmark [lookback_days] [--since YYYY-MM-DD]`."""
    import sys

    from titantrade.config import load_config

    args = sys.argv[2:]  # argv[1] == "benchmark"
    since: str | None = None
    lookback_days = 90
    for i, a in enumerate(args):
        if a == "--since" and i + 1 < len(args):
            since = args[i + 1]
        elif a.isdigit():
            lookback_days = int(a)

    cfg = load_config()
    metrics = compute_benchmark(cfg, lookback_days=lookback_days, since=since)
    print_report(metrics)


if __name__ == "__main__":
    main()
