"""Backtester for the mechanical strategy (Decision 061).

Uses ``titantrade.signals`` — the same rule code the live executor runs — on
daily closes. Accounting mirrors the live book: SPY is the residual, each dip
entry takes a ``slot_pct`` slot out of SPY at the *next* close after the
signal (no look-ahead), exits at the target / stop / holding limit are
evaluated at the close, a cash reserve is kept, and the insurance switch
scales total exposure. Costs are charged per side.

    python -m titantrade backtest-mech data/historical --start 2016-01-01 --split 2022-01-01 --grid
"""
from __future__ import annotations

import itertools
import json
import math
import statistics
from typing import Any

from titantrade.backtest.data_loader import load_historical_data
from titantrade.signals import (
    above_sma_flags, breadth, dip_state, insurance_state, rank_dips,
)

DEFAULT_PARAMS: dict[str, Any] = {
    "dip_pct": 0.10, "dip_lookback_days": 60, "trend_sma_days": 200,
    "slot_pct": 0.20, "max_slots": 3, "tp_pct": 0.10, "stop_pct": 0.12,
    "max_hold_days": 40, "insurance_sma_days": 200, "insurance_breadth": 0.5,
    "insurance_scale": 0.5, "cash_reserve_pct": 0.05, "cost_per_side": 0.0005,
    "core_band_pct": 0.05,
}

# A small, deliberately coarse grid for walk-forward checks. The operator's
# large parameter search extends it; keep few parameters and look for
# plateaus, not peaks.
DEFAULT_GRID: list[dict[str, Any]] = [
    {"dip_pct": d, "max_hold_days": h, "insurance_scale": s}
    for d, h, s in itertools.product((0.08, 0.10, 0.12), (40, 60), (0.5, 1.0))
]

SECTOR_ETFS = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLB", "XLRE", "XLP", "XLU", "XLC"]


def params_from_config(cfg: Any) -> dict[str, Any]:
    t = cfg.trading
    p = dict(DEFAULT_PARAMS)
    p.update({
        "dip_pct": t.dip_pct, "dip_lookback_days": t.dip_lookback_days,
        "trend_sma_days": t.trend_sma_days, "slot_pct": t.slot_pct,
        "max_slots": t.max_slots, "tp_pct": t.tp_pct, "stop_pct": t.stop_pct,
        "max_hold_days": t.max_hold_days, "insurance_sma_days": t.insurance_sma_days,
        "insurance_breadth": t.insurance_breadth, "insurance_scale": t.insurance_scale,
    })
    return p


def _closes(bars: list[dict[str, Any]]) -> dict[str, float]:
    return {b["date"]: float(b["close"]) for b in bars}


def _metrics(curve: list[float], trades: list[dict[str, Any]], days_per_year: int = 252) -> dict[str, Any]:
    if len(curve) < 2:
        return {"total_return": 0.0, "cagr": 0.0, "max_drawdown": 0.0, "sharpe": 0.0, "trades": 0}
    rs = [curve[k] / curve[k - 1] - 1 for k in range(1, len(curve))]
    peak = curve[0]
    mdd = 0.0
    for v in curve:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    years = len(rs) / days_per_year
    total = curve[-1] / curve[0] - 1
    cagr = (curve[-1] / curve[0]) ** (1 / years) - 1 if years > 0 and curve[0] > 0 else 0.0
    sd = statistics.pstdev(rs)
    sharpe = statistics.mean(rs) / sd * math.sqrt(days_per_year) if sd else 0.0
    wins = [t for t in trades if t["return"] > 0]
    return {
        "total_return": round(total, 4), "cagr": round(cagr, 4),
        "max_drawdown": round(mdd, 4), "sharpe": round(sharpe, 3),
        "calmar": round(cagr / -mdd, 3) if mdd < 0 else None,
        "trades": len(trades),
        "win_rate": round(len(wins) / len(trades), 3) if trades else None,
        "avg_trade": round(statistics.mean(t["return"] for t in trades), 4) if trades else None,
        "exits": {k: sum(1 for t in trades if t["exit"] == k) for k in ("tp", "stop", "time")},
    }


def run_mechanical_backtest(
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    spy_bars: list[dict[str, Any]],
    sector_bars: dict[str, list[dict[str, Any]]] | None = None,
    params: dict[str, Any] | None = None,
    start: str | None = None,
    end: str | None = None,
    initial_capital: float = 100_000.0,
) -> dict[str, Any]:
    p = dict(DEFAULT_PARAMS)
    p.update(params or {})
    spy = _closes(spy_bars)
    names = {t: _closes(b) for t, b in bars_by_ticker.items() if t != "SPY"}
    sectors = {t: _closes(b) for t, b in (sector_bars or {}).items()}
    dates = sorted(d for d in spy if (not start or d >= start) and (not end or d <= end))
    if len(dates) < 2:
        return {"error": "not enough SPY dates in range"}
    all_dates = sorted(spy)  # full history for warm-up windows

    def series(closes: dict[str, float], upto: str, n: int) -> list[float]:
        # last n closes at/before `upto` from the full history (warm-up allowed)
        out = [closes[d] for d in all_dates if d <= upto and d in closes]
        return out[-n:]

    warm = max(p["trend_sma_days"], p["insurance_sma_days"], p["dip_lookback_days"]) + 5
    cash = initial_capital * p["cash_reserve_pct"]
    val: dict[str, float] = {"SPY": initial_capital - cash}
    pos: dict[str, dict[str, Any]] = {}
    pending: list[str] = []
    curve: list[float] = []
    trades: list[dict[str, Any]] = []
    exposure_log: list[float] = []
    risk_off_days = 0
    scale = 1.0
    prev = None
    for day in dates:
        if prev is not None:
            for k in list(val):
                c = spy if k == "SPY" else names.get(k, {})
                if day in c and prev in c:
                    val[k] *= c[day] / c[prev]
        total = sum(val.values()) + cash
        # 1. fills from yesterday's signals, at today's close, out of SPY
        for t in pending:
            if t in pos or day not in names.get(t, {}):
                continue
            amt = p["slot_pct"] * total
            if val.get("SPY", 0.0) < amt:
                continue
            val["SPY"] -= amt
            val[t] = val.get(t, 0.0) + amt * (1 - p["cost_per_side"])
            pos[t] = {"entry": names[t][day], "day_index": len(curve), "date": day}
        pending = []
        # 2. exits at today's close
        for t in list(pos):
            c = names[t].get(day)
            if c is None:
                continue
            r = c / pos[t]["entry"] - 1
            held = len(curve) - pos[t]["day_index"]
            exit_kind = "tp" if r >= p["tp_pct"] else "stop" if r <= -p["stop_pct"] else "time" if held >= p["max_hold_days"] else None
            if exit_kind:
                val["SPY"] = val.get("SPY", 0.0) + val.pop(t, 0.0) * (1 - p["cost_per_side"])
                trades.append({"ticker": t, "entry_date": pos[t]["date"], "exit_date": day, "return": round(r, 4), "exit": exit_kind, "days": held})
                del pos[t]
        total = sum(val.values()) + cash
        # 3. insurance from today's close → applies to the core target from here
        spy_hist = series(spy, day, p["insurance_sma_days"] + 1)
        spy_above = (spy_hist[-1] > sum(spy_hist[-p["insurance_sma_days"]:]) / p["insurance_sma_days"]) if len(spy_hist) > p["insurance_sma_days"] else None
        flags = above_sma_flags({t: series(c, day, p["insurance_sma_days"]) for t, c in sectors.items()}, p["insurance_sma_days"]) if sectors else {}
        ins = insurance_state(spy_above, breadth(flags.values()) if flags else None, breadth_threshold=p["insurance_breadth"], scale=p["insurance_scale"])
        scale = ins["exposure_scale"]
        risk_off_days += int(ins["risk_off"])
        # 4. core = residual; rebalance SPY vs cash when outside the band
        overlay = sum(v for k, v in val.items() if k != "SPY")
        target_spy = max(0.0, scale * (1 - p["cash_reserve_pct"]) * total - overlay)
        drift = val.get("SPY", 0.0) - target_spy
        if abs(drift) > p["core_band_pct"] * total:
            val["SPY"] = val.get("SPY", 0.0) - drift
            cash += drift
        curve.append(sum(val.values()) + cash)
        exposure_log.append((sum(val.values())) / curve[-1] if curve[-1] else 0.0)
        # 5. tomorrow's entries from today's closes (warm-up respected)
        if len([d for d in all_dates if d <= day]) >= warm and not ins["risk_off"]:
            free = p["max_slots"] - len(pos)
            if free > 0:
                states = {
                    t: dip_state(series(c, day, max(p["dip_lookback_days"], p["trend_sma_days"])), dip_pct=p["dip_pct"], lookback=p["dip_lookback_days"], trend_sma=p["trend_sma_days"])
                    for t, c in names.items() if day in c
                }
                pending = [t for t in rank_dips(states) if t not in pos][:free]
        prev = day
    spy_curve = [spy[d] / spy[dates[0]] for d in dates]
    return {
        "params": p, "start": dates[0], "end": dates[-1], "days": len(dates),
        "metrics": _metrics(curve, trades),
        "spy": _metrics(spy_curve, []),
        "avg_exposure": round(statistics.mean(exposure_log), 3) if exposure_log else None,
        "risk_off_days": risk_off_days,
        "trades": trades,
        "equity_curve": [round(v, 2) for v in curve],
        "open_positions_at_end": sorted(pos),
    }


def walk_forward(
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    spy_bars: list[dict[str, Any]],
    sector_bars: dict[str, list[dict[str, Any]]] | None,
    grid: list[dict[str, Any]],
    split: str,
    start: str | None = None,
    end: str | None = None,
    base_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Each grid point: in-sample (start → split) and out-of-sample (split → end)
    metrics side by side, sorted by in-sample Calmar. Pick plateaus, not peaks."""
    rows = []
    for g in grid:
        params = dict(base_params or {})
        params.update(g)
        ins = run_mechanical_backtest(bars_by_ticker, spy_bars, sector_bars, params, start, split)
        oos = run_mechanical_backtest(bars_by_ticker, spy_bars, sector_bars, params, split, end)
        rows.append({"grid": g, "in_sample": ins.get("metrics", {}), "in_sample_spy": ins.get("spy", {}),
                     "out_of_sample": oos.get("metrics", {}), "out_of_sample_spy": oos.get("spy", {})})
    rows.sort(key=lambda r: -(r["in_sample"].get("calmar") or -9))
    return rows


def _fmt(m: dict[str, Any]) -> str:
    if not m:
        return "n/a"
    return (f"CAGR {m.get('cagr', 0)*100:6.1f}%  maxDD {m.get('max_drawdown', 0)*100:6.1f}%  "
            f"Sharpe {m.get('sharpe', 0):5.2f}  trades {m.get('trades', 0):4}  win {(m.get('win_rate') or 0)*100:3.0f}%")


def main(argv: list[str]) -> None:
    from titantrade.config import load_config

    cfg = load_config()
    args = [a for a in argv if not a.startswith("--")]
    data_dir = args[0] if args else "data/historical"
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d  # noqa: E731
    start, end, split = opt("--start"), opt("--end"), opt("--split")
    tickers = list(cfg.trading.watchlist)
    data = load_historical_data(tickers + ["SPY"] + list(cfg.trading.sector_etfs), data_dir)
    spy = data.pop("SPY", [])
    sectors = {t: data.pop(t) for t in list(cfg.trading.sector_etfs) if t in data}
    params = params_from_config(cfg)
    res = run_mechanical_backtest(data, spy, sectors, params, start, end)
    if res.get("error"):
        print(res["error"])
        return
    print(f"Mechanical backtest {res['start']} → {res['end']} ({res['days']} sessions), {len(data)} names, {len(sectors)} sector ETFs")
    print(f"  SPY buy-and-hold : {_fmt(res['spy'])}")
    print(f"  strategy         : {_fmt(res['metrics'])}  exits {res['metrics']['exits']}  avg exposure {res['avg_exposure']}  risk-off days {res['risk_off_days']}")
    out = {"summary": {k: v for k, v in res.items() if k not in ("trades", "equity_curve")}, "trades": res["trades"]}
    if "--grid" in argv:
        split = split or "2022-01-01"
        rows = walk_forward(data, spy, sectors, DEFAULT_GRID, split, start, end, params)
        print(f"\n  walk-forward: in-sample → {split} → out-of-sample (sorted by in-sample Calmar)")
        for r in rows:
            print(f"  {json.dumps(r['grid']):52} IS {_fmt(r['in_sample'])} | OOS {_fmt(r['out_of_sample'])}")
        print(f"  SPY IS {_fmt(rows[0]['in_sample_spy'])} | OOS {_fmt(rows[0]['out_of_sample_spy'])}")
        out["walk_forward"] = rows
    with open("state/backtest_mechanical.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("\n  saved state/backtest_mechanical.json")
