"""Backtester for the mechanical strategy (Decisions 061, 068, 081).

Uses ``titantrade.signals`` — the same rule code the live executor runs — on
daily closes, with the live book's accounting (Decision 081): the momentum ETF
is a core leg held at ``momentum_weight`` of the investable book, SPY is the
dip sleeve's residual, each dip entry takes a slot of ``slot_pct`` *of the
sleeve* out of SPY at the *next* close after the signal (no look-ahead), exits
at the target / stop / holding limit are evaluated at the close and return to
SPY (what the executor's sell-to-cash plus same-run SPY buy-back amounts to),
every core leg is rebalanced only outside its band in the executor's order, a
cash reserve is kept, and exposure = min(insurance, shock trigger) scales the
core legs while held positions keep their exits. ``momentum_weight`` 0 is the
Decision 061 dip-only book. Costs are charged per side on the dip trades.

    python -m titantrade backtest-mech data/historical --start 2016-01-01 --split 2022-01-01 --grid
"""
from __future__ import annotations

import itertools
import json
import math
import statistics
from bisect import bisect_right
from typing import Any

from titantrade.backtest.data_loader import load_historical_data
from titantrade.signals import (
    above_sma_flags, breadth, dip_state, insurance_state, rank_dips, shock_state,
)

DEFAULT_PARAMS: dict[str, Any] = {
    "dip_pct": 0.10, "dip_lookback_days": 60, "trend_sma_days": 200,
    "slot_pct": 0.20, "max_slots": 3, "tp_pct": 0.10, "stop_pct": 0.12,
    "max_hold_days": 40, "insurance_sma_days": 200, "insurance_breadth": 0.5,
    "insurance_scale": 0.5, "cash_reserve_pct": 0.05, "cost_per_side": 0.0005,
    "core_band_pct": 0.05,
    # Decision 068: the momentum ETF's share of the investable book (0 = the
    # dip-only book) and the shock trigger (drop 0 = off), combined by min().
    "momentum_weight": 0.0,
    "shock_drop_pct": 0.0, "shock_lookback_days": 10, "shock_hold_days": 20, "shock_scale": 0.5,
}

# A small, deliberately coarse grid for walk-forward checks. The operator's
# large parameter search extends it; keep few parameters and look for
# plateaus, not peaks.
DEFAULT_GRID: list[dict[str, Any]] = [
    {"dip_pct": d, "max_hold_days": h, "insurance_scale": s}
    for d, h, s in itertools.product((0.08, 0.10, 0.12), (40, 60), (0.5, 1.0))
]

SECTOR_ETFS = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLB", "XLRE", "XLP", "XLU", "XLC"]

# Valuation keys of the two optional core legs (never a dip name).
MOMENTUM, CASH_LEG = "momentum", "cash_leg"


def params_from_config(cfg: Any) -> dict[str, Any]:
    t = cfg.trading
    p = dict(DEFAULT_PARAMS)
    p.update({
        "dip_pct": t.dip_pct, "dip_lookback_days": t.dip_lookback_days,
        "trend_sma_days": t.trend_sma_days, "slot_pct": t.slot_pct,
        "max_slots": t.max_slots, "tp_pct": t.tp_pct, "stop_pct": t.stop_pct,
        "max_hold_days": t.max_hold_days, "insurance_sma_days": t.insurance_sma_days,
        "insurance_breadth": t.insurance_breadth, "insurance_scale": t.insurance_scale,
        "core_band_pct": t.core_rebalance_band_pct,
        "momentum_weight": t.momentum_weight,
        "shock_drop_pct": t.shock_drop_pct, "shock_lookback_days": t.shock_lookback_days,
        "shock_hold_days": t.shock_hold_days, "shock_scale": t.shock_scale,
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


class _Series:
    """A close series with O(window) lookback slices (gaps skipped, warm-up allowed)."""

    def __init__(self, closes: dict[str, float], all_dates: list[str]):
        self.dates = [d for d in all_dates if d in closes]
        self.values = [closes[d] for d in self.dates]

    def upto(self, day: str, n: int) -> list[float]:
        k = bisect_right(self.dates, day)
        return self.values[max(0, k - n):k]


def run_mechanical_backtest(
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    spy_bars: list[dict[str, Any]],
    sector_bars: dict[str, list[dict[str, Any]]] | None = None,
    params: dict[str, Any] | None = None,
    start: str | None = None,
    end: str | None = None,
    initial_capital: float = 100_000.0,
    momentum_bars: list[dict[str, Any]] | None = None,
    cash_bars: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    p = dict(DEFAULT_PARAMS)
    p.update(params or {})
    spy = _closes(spy_bars)
    names = {t: _closes(b) for t, b in bars_by_ticker.items() if t != "SPY"}
    sectors = {t: _closes(b) for t, b in (sector_bars or {}).items()}
    # The momentum leg needs its bars; without them the book is dip-only.
    w_mom = p["momentum_weight"] if momentum_bars else 0.0
    legs: dict[str, dict[str, float]] = {"SPY": spy}
    if w_mom > 0:
        legs[MOMENTUM] = _closes(momentum_bars)
    if cash_bars:
        legs[CASH_LEG] = _closes(cash_bars)
    dates = sorted(d for d in spy if (not start or d >= start) and (not end or d <= end))
    if len(dates) < 2:
        return {"error": "not enough SPY dates in range"}
    all_dates = sorted(spy)  # full history for warm-up windows
    spy_s = _Series(spy, all_dates)
    name_s = {t: _Series(c, all_dates) for t, c in names.items()}
    sector_s = {t: _Series(c, all_dates) for t, c in sectors.items()}

    warm = max(p["trend_sma_days"], p["insurance_sma_days"], p["dip_lookback_days"]) + 5
    reserve, band, cost = p["cash_reserve_pct"], p["core_band_pct"], p["cost_per_side"]
    slot = p["slot_pct"] * (1 - w_mom)   # one slot as a share of equity (TradingSettings.overlay_slot_pct)
    cash = initial_capital * reserve
    val: dict[str, float] = {"SPY": initial_capital - cash}
    pos: dict[str, dict[str, Any]] = {}
    pending: list[str] = []
    curve: list[float] = []
    trades: list[dict[str, Any]] = []
    exposure_log: list[float] = []
    mom_share: list[float] = []
    core_trades = {k: 0 for k in legs}
    risk_off_days = shock_days = 0
    prev = None
    for day in dates:
        if prev is not None:
            for k in list(val):
                c = legs.get(k) or names.get(k, {})
                if day in c and prev in c:
                    val[k] *= c[day] / c[prev]
        total = sum(val.values()) + cash
        # 1. fills from yesterday's signals, at today's close: out of SPY, then
        #    the cash above the reserve (the executor sells SPY for the planned
        #    slots first; the cash gate sizes the rest down)
        for t in pending:
            if t in pos or day not in names.get(t, {}):
                continue
            amt = min(slot * total, val.get("SPY", 0.0) + max(cash - reserve * total, 0.0))
            if amt <= 0:
                continue
            from_spy = min(amt, val.get("SPY", 0.0))
            val["SPY"] = val.get("SPY", 0.0) - from_spy
            cash -= amt - from_spy
            val[t] = val.get(t, 0.0) + amt * (1 - cost)
            pos[t] = {"entry": names[t][day], "day_index": len(curve), "date": day, "size_pct": round(amt / total, 4)}
        pending = []
        # 2. exits at today's close, back into SPY. The executor sells to cash and
        #    SPY buys the proceeds back in the same run (a slot is twice the band),
        #    which differs from this only by the reserve's drift since the last
        #    rebalance; routing through SPY keeps the dip-only book trade-for-trade
        #    equal to fastbt (validate.py), the Decision 062 floor.
        for t in list(pos):
            c = names[t].get(day)
            if c is None:
                continue
            r = c / pos[t]["entry"] - 1
            held = len(curve) - pos[t]["day_index"]
            exit_kind = "tp" if r >= p["tp_pct"] else "stop" if r <= -p["stop_pct"] else "time" if held >= p["max_hold_days"] else None
            if exit_kind:
                val["SPY"] = val.get("SPY", 0.0) + val.pop(t, 0.0) * (1 - cost)
                trades.append({"ticker": t, "entry_date": pos[t]["date"], "exit_date": day, "return": round(r, 4),
                               "exit": exit_kind, "days": held, "size_pct": pos[t]["size_pct"]})
                del pos[t]
        total = sum(val.values()) + cash
        # 3. the two rules from today's closes; exposure = min (Decision 067)
        spy_hist = spy_s.upto(day, p["insurance_sma_days"] + 1)
        spy_above = (spy_hist[-1] > sum(spy_hist[-p["insurance_sma_days"]:]) / p["insurance_sma_days"]) if len(spy_hist) > p["insurance_sma_days"] else None
        flags = above_sma_flags({t: s.upto(day, p["insurance_sma_days"]) for t, s in sector_s.items()}, p["insurance_sma_days"]) if sectors else {}
        ins = insurance_state(spy_above, breadth(flags.values()) if flags else None, breadth_threshold=p["insurance_breadth"], scale=p["insurance_scale"])
        shock = (shock_state(spy_s.upto(day, p["shock_lookback_days"] + p["shock_hold_days"] + 1), drop_pct=p["shock_drop_pct"],
                             lookback=p["shock_lookback_days"], hold=p["shock_hold_days"], scale=p["shock_scale"])
                 if p["shock_drop_pct"] else {"active": False, "exposure_scale": 1.0})
        scale = min(ins["exposure_scale"], shock["exposure_scale"])
        risk_off_days += int(ins["risk_off"])
        shock_days += int(shock["active"])
        # 4. the core legs toward their targets (mechanical.core_target_pct /
        #    momentum_target_pct / cash_target_pct), each only outside the band,
        #    in the executor's order: SPY first (its sale funds the rest), the
        #    momentum leg, and the cash leg first when it shrinks, last when it grows
        overlay = sum(v for k, v in val.items() if k not in legs)
        investable = scale * (1 - reserve) * total
        targets = [("SPY", max(0.0, investable * (1 - w_mom) - overlay))]
        if MOMENTUM in legs:
            targets.append((MOMENTUM, investable * w_mom))
        if CASH_LEG in legs:
            t_cash = (1 - scale) * (1 - reserve) * total
            targets.insert(0, (CASH_LEG, t_cash)) if val.get(CASH_LEG, 0.0) > t_cash else targets.append((CASH_LEG, t_cash))
        for leg, target in targets:
            drift = val.get(leg, 0.0) - target
            if abs(drift) <= band * total:
                continue
            if drift > 0:
                val[leg] -= drift
                cash += drift
            else:
                buy = min(-drift, max(cash - reserve * total, 0.0))
                if buy <= 0:
                    continue
                val[leg] = val.get(leg, 0.0) + buy
                cash -= buy
            core_trades[leg] += 1
        tot = sum(val.values()) + cash
        curve.append(tot)
        exposure_log.append(sum(v for k, v in val.items() if k != CASH_LEG) / tot if tot else 0.0)
        if MOMENTUM in legs:
            mom_share.append(val.get(MOMENTUM, 0.0) / tot if tot else 0.0)
        # 5. tomorrow's entries from today's closes (warm-up respected), only while neither rule is on
        if len(spy_s.upto(day, warm)) >= warm and not ins["risk_off"] and not shock["active"]:
            free = p["max_slots"] - len(pos)
            if free > 0:
                states = {
                    t: dip_state(s.upto(day, max(p["dip_lookback_days"], p["trend_sma_days"])), dip_pct=p["dip_pct"], lookback=p["dip_lookback_days"], trend_sma=p["trend_sma_days"])
                    for t, s in name_s.items() if day in names[t]
                }
                pending = [t for t in rank_dips(states) if t not in pos][:free]
        prev = day
    spy_curve = [spy[d] / spy[dates[0]] for d in dates]
    return {
        "params": p, "start": dates[0], "end": dates[-1], "days": len(dates),
        "metrics": _metrics(curve, trades),
        "spy": _metrics(spy_curve, []),
        "avg_exposure": round(statistics.mean(exposure_log), 3) if exposure_log else None,
        "min_exposure": round(min(exposure_log), 3) if exposure_log else None,
        "avg_momentum_share": round(statistics.mean(mom_share), 3) if mom_share else None,
        "risk_off_days": risk_off_days,
        "shock_days": shock_days,
        "core_trades": core_trades,
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
    momentum_bars: list[dict[str, Any]] | None = None,
    cash_bars: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Each grid point: in-sample (start → split) and out-of-sample (split → end)
    metrics side by side, sorted by in-sample Calmar. Pick plateaus, not peaks."""
    rows = []
    for g in grid:
        params = dict(base_params or {})
        params.update(g)
        ins = run_mechanical_backtest(bars_by_ticker, spy_bars, sector_bars, params, start, split, momentum_bars=momentum_bars, cash_bars=cash_bars)
        oos = run_mechanical_backtest(bars_by_ticker, spy_bars, sector_bars, params, split, end, momentum_bars=momentum_bars, cash_bars=cash_bars)
        rows.append({"grid": g, "in_sample": ins.get("metrics", {}), "in_sample_spy": ins.get("spy", {}),
                     "out_of_sample": oos.get("metrics", {}), "out_of_sample_spy": oos.get("spy", {})})
    rows.sort(key=lambda r: -(r["in_sample"].get("calmar") or -9))
    return rows


def _fmt(m: dict[str, Any]) -> str:
    if not m:
        return "n/a"
    return (f"CAGR {m.get('cagr', 0)*100:6.1f}%  maxDD {m.get('max_drawdown', 0)*100:6.1f}%  "
            f"Sharpe {m.get('sharpe', 0):5.2f}  trades {m.get('trades', 0):4}  win {(m.get('win_rate') or 0)*100:3.0f}%")


def _summary(res: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in res.items() if k not in ("trades", "equity_curve")}


def main(argv: list[str]) -> None:
    from titantrade.config import load_config

    cfg = load_config()
    t = cfg.trading
    args = [a for a in argv if not a.startswith("--")]
    data_dir = args[0] if args else "data/historical"
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d  # noqa: E731
    start, end, split = opt("--start"), opt("--end"), opt("--split")
    shadow = "--shadow" in argv
    if shadow and not t.shadow_watchlist:
        print("No shadow_watchlist in data/watchlist.json")
        return
    params = params_from_config(cfg)
    lists = [("the watchlist", list(t.watchlist))] + ([("the shadow list", list(t.shadow_watchlist))] if shadow else [])
    legs = {"momentum": t.momentum_ticker if params["momentum_weight"] > 0 else "", "cash": t.cash_ticker}
    wanted = [tk for _, lst in lists for tk in lst] + ["SPY"] + list(t.sector_etfs) + [tk for tk in legs.values() if tk]
    data = load_historical_data(list(dict.fromkeys(wanted)), data_dir)
    for leg, tk in legs.items():
        if tk and tk not in data:
            print(f"No {tk}.json in {data_dir} — the {leg} leg needs its bars; run `download-history` (it fetches the momentum and cash tickers)")
            return
    spy = data.get("SPY", [])
    sectors = {s: data[s] for s in t.sector_etfs if s in data}
    mom, cashb = data.get(legs["momentum"]), data.get(legs["cash"])
    sleeve = f", {t.momentum_ticker} sleeve {params['momentum_weight']:.0%}" if mom else ""
    out: dict[str, Any] = {}
    for label, lst in lists:
        names = {tk: data[tk] for tk in lst if tk in data}
        res = run_mechanical_backtest(names, spy, sectors, params, start, end, momentum_bars=mom, cash_bars=cashb)
        if res.get("error"):
            print(res["error"])
            return
        if not out:
            print(f"Mechanical backtest {res['start']} → {res['end']} ({res['days']} sessions), {len(sectors)} sector ETFs for breadth{sleeve}")
            print(f"  SPY buy-and-hold : {_fmt(res['spy'])}")
            out = {"summary": _summary(res), "trades": res["trades"]}
        else:
            out["shadow"] = _summary(res)
        print(f"  the book, {label} ({len(names)} names): {_fmt(res['metrics'])}  exits {res['metrics']['exits']}")
        print(f"    avg exposure {res['avg_exposure']}  risk-off days {res['risk_off_days']}  shock days {res['shock_days']}"
              + (f"  {t.momentum_ticker} share avg {res['avg_momentum_share']:.0%}  core trades {res['core_trades']}" if mom else ""))
        if mom:
            dip = run_mechanical_backtest(names, spy, sectors, {**params, "momentum_weight": 0.0}, start, end)
            out["dip_only" if "shadow" not in out else "shadow_dip_only"] = _summary(dip)
            print(f"  dip sleeve alone, {label}: {_fmt(dip['metrics'])}  exits {dip['metrics']['exits']}  avg exposure {dip['avg_exposure']}")
    if "--grid" in argv:
        split = split or "2022-01-01"
        names = {tk: data[tk] for tk in lists[0][1] if tk in data}
        rows = walk_forward(names, spy, sectors, DEFAULT_GRID, split, start, end, params, momentum_bars=mom, cash_bars=cashb)
        print(f"\n  walk-forward: in-sample → {split} → out-of-sample (sorted by in-sample Calmar)")
        for r in rows:
            print(f"  {json.dumps(r['grid']):52} IS {_fmt(r['in_sample'])} | OOS {_fmt(r['out_of_sample'])}")
        print(f"  SPY IS {_fmt(rows[0]['in_sample_spy'])} | OOS {_fmt(rows[0]['out_of_sample_spy'])}")
        out["walk_forward"] = rows
    with open("state/backtest_mechanical.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("\n  saved state/backtest_mechanical.json")
