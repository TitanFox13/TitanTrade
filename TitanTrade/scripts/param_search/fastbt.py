"""Fast numpy engine for the Decision 061 mechanical strategy — semantics
identical to titantrade.backtest.mechanical.run_mechanical_backtest (validated
trade-for-trade by validate.py). Precomputations are cached per
(lookback, trend_sma, insurance_sma) so a parameter grid runs in ms per point.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

import numpy as np

DEFAULTS = dict(dip_pct=0.10, dip_lookback_days=60, trend_sma_days=200, slot_pct=0.20,
                max_slots=3, tp_pct=0.10, stop_pct=0.12, max_hold_days=40,
                insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=0.5,
                cash_reserve_pct=0.05, cost_per_side=0.0005, core_band_pct=0.05,
                trail_pct=None,   # optional trailing stop below the high-water mark, armed once above entry
                rank="deepest",  # candidate order when slots are free: "deepest" dip first (live) or "shallowest"
                dip_max=None)     # optional upper bound on the dip: skip names that fell more than this (crash filter)


class Market:
    """Date-aligned close matrices. `names` and `sectors` map symbol → {date: close}."""

    def __init__(self, spy: dict[str, float], names: dict[str, dict[str, float]],
                 sectors: dict[str, dict[str, float]]):
        self.dates = sorted(spy)
        self.idx = {d: i for i, d in enumerate(self.dates)}
        T = len(self.dates)
        self.spy = np.array([spy[d] for d in self.dates])
        self.name_list = sorted(names)
        self.sector_list = sorted(sectors)
        self.names = np.full((T, len(self.name_list)), np.nan)
        for j, n in enumerate(self.name_list):
            for d, c in names[n].items():
                i = self.idx.get(d)
                if i is not None:
                    self.names[i, j] = c
        self.sectors = np.full((T, len(self.sector_list)), np.nan)
        for j, n in enumerate(self.sector_list):
            for d, c in sectors[n].items():
                i = self.idx.get(d)
                if i is not None:
                    self.sectors[i, j] = c
        self._cache: dict = {}

    # --- rolling stats over each column's *available* values (gap-skipping, like series()) ---
    @staticmethod
    def _col_roll(col: np.ndarray, n: int, kind: str) -> np.ndarray:
        """Rolling over the valid values of `col`, placed back at the valid positions.
        sma: NaN until n values; max: NaN until n//2 values (rolling_high semantics)."""
        out = np.full(col.shape, np.nan)
        valid = ~np.isnan(col)
        v = col[valid]
        if len(v) == 0:
            return out
        res = np.full(len(v), np.nan)
        if kind == "sma":
            if len(v) >= n:
                cs = np.cumsum(np.insert(v, 0, 0.0))
                res[n - 1:] = (cs[n:] - cs[:-n]) / n
        else:  # max of the last n values, needs at least max(1, n//2)
            need = max(1, n // 2)
            run_max = np.maximum.accumulate(v)          # prefix max for the first n-1 values
            res[:] = run_max
            if len(v) >= n:
                from numpy.lib.stride_tricks import sliding_window_view
                res[n - 1:] = sliding_window_view(v, n).max(axis=1)
            res[:need - 1] = np.nan
        out[valid] = res
        return out

    def pre(self, lookback: int, trend: int, ins_sma: int):
        key = (lookback, trend, ins_sma)
        if key in self._cache:
            return self._cache[key]
        T, N = self.names.shape
        high = np.column_stack([self._col_roll(self.names[:, j], lookback, "max") for j in range(N)]) if N else np.zeros((T, 0))
        sma = np.column_stack([self._col_roll(self.names[:, j], trend, "sma") for j in range(N)]) if N else np.zeros((T, 0))
        with np.errstate(invalid="ignore", divide="ignore"):
            dip = (high - self.names) / high
            above = self.names > sma
        # insurance: SPY above its SMA (needs > ins_sma values, i.e. index >= ins_sma)
        spy_sma = self._col_roll(self.spy, ins_sma, "sma")
        spy_above = np.full(T, np.nan)
        ok = np.arange(T) >= ins_sma
        spy_above[ok] = (self.spy[ok] > spy_sma[ok]).astype(float)
        if self.sectors.shape[1]:
            s_sma = np.column_stack([self._col_roll(self.sectors[:, j], ins_sma, "sma") for j in range(self.sectors.shape[1])])
            with np.errstate(invalid="ignore"):
                flags = np.where(np.isnan(s_sma), np.nan, (self.sectors > s_sma).astype(float))
            known = ~np.isnan(flags)
            cnt = known.sum(axis=1)
            breadth = np.where(cnt > 0, np.nansum(flags, axis=1) / np.maximum(cnt, 1), np.nan)
        else:
            breadth = np.full(T, np.nan)
        self._cache[key] = (dip, above, spy_above, breadth)
        return self._cache[key]


def run(mkt: Market, params: dict | None = None, start: str | None = None, end: str | None = None,
        initial_capital: float = 100_000.0, want_trades: bool = False) -> dict:
    p = dict(DEFAULTS)
    p.update(params or {})
    dip_m, above_m, spy_above, breadth = mkt.pre(p["dip_lookback_days"], p["trend_sma_days"], p["insurance_sma_days"])
    dates = mkt.dates
    i0 = next((i for i, d in enumerate(dates) if not start or d >= start), None)
    i1 = max((i for i, d in enumerate(dates) if not end or d <= end), default=None)
    if i0 is None or i1 is None or i1 - i0 < 1:
        return {"error": "range"}
    warm = max(p["trend_sma_days"], p["insurance_sma_days"], p["dip_lookback_days"]) + 5
    N = len(mkt.name_list)
    reserve = p["cash_reserve_pct"]
    cash = initial_capital * reserve
    v_spy = initial_capital - cash
    v_name = np.zeros(N)
    entry = np.full(N, np.nan)
    hwm = np.full(N, np.nan)
    day_index = np.full(N, -1)
    trail = p.get("trail_pct")
    # A name whose series ends (delisting / acquisition) is settled at its last price on the next day.
    has = ~np.isnan(mkt.names)
    last_valid = np.array([int(np.nonzero(has[:, j])[0].max()) if has[:, j].any() else -1 for j in range(N)])
    pending: list[int] = []
    curve = []
    trades = []
    expo = []
    risk_off_days = 0
    scale = 1.0
    signal_ok = (dip_m >= p["dip_pct"]) & (above_m == True)  # noqa: E712
    if p.get("dip_max"):
        signal_ok &= dip_m <= p["dip_max"]
    if p.get("eligible") is not None:
        signal_ok &= np.asarray(p["eligible"], dtype=bool)
    for i in range(i0, i1 + 1):
        if i > i0:
            v_spy *= mkt.spy[i] / mkt.spy[i - 1]
            r = mkt.names[i] / mkt.names[i - 1]
            held = v_name > 0
            ok = held & ~np.isnan(r)
            v_name[ok] *= r[ok]
        total = v_spy + v_name.sum() + cash
        for j in pending:
            if v_name[j] > 0 or np.isnan(mkt.names[i, j]):
                continue
            amt = p["slot_pct"] * total
            if v_spy < amt:
                continue
            v_spy -= amt
            v_name[j] += amt * (1 - p["cost_per_side"])
            entry[j] = mkt.names[i, j]
            hwm[j] = entry[j]
            day_index[j] = len(curve)
        pending = []
        for j in np.nonzero(v_name > 0)[0]:
            c = mkt.names[i, j]
            if np.isnan(c):
                if i <= last_valid[j]:
                    continue                      # a gap in the series: hold on
                c = mkt.names[last_valid[j], j]   # series ended: settle at the last price
                kind = "delist"
            else:
                kind = None
            ret = c / entry[j] - 1
            held_days = len(curve) - day_index[j]
            hwm[j] = max(hwm[j], c)
            if kind is None:
                kind = "tp" if ret >= p["tp_pct"] else "stop" if ret <= -p["stop_pct"] else "time" if held_days >= p["max_hold_days"] else None
            if kind is None and trail and hwm[j] > entry[j] and c <= hwm[j] * (1 - trail):
                kind = "trail"
            if kind:
                v_spy += v_name[j] * (1 - p["cost_per_side"])
                v_name[j] = 0.0
                if want_trades:
                    trades.append({"ticker": mkt.name_list[j], "exit_date": dates[i], "return": round(float(ret), 4), "exit": kind, "days": int(held_days)})
                else:
                    trades.append((float(ret), kind, i - i0))
        total = v_spy + v_name.sum() + cash
        sa = spy_above[i]
        b = breadth[i]
        risk_off = (not np.isnan(sa)) and sa == 0.0 and (not np.isnan(b)) and b < p["insurance_breadth"]
        scale = p["insurance_scale"] if risk_off else 1.0
        risk_off_days += int(risk_off)
        overlay = v_name.sum()
        target = max(0.0, scale * (1 - reserve) * total - overlay)
        drift = v_spy - target
        if abs(drift) > p["core_band_pct"] * total:
            v_spy -= drift
            cash += drift
        tot = v_spy + v_name.sum() + cash
        curve.append(tot)
        expo.append((v_spy + v_name.sum()) / tot if tot else 0.0)
        if i + 1 >= warm and not risk_off:
            free = p["max_slots"] - int((v_name > 0).sum())
            if free > 0:
                cand = np.nonzero(signal_ok[i] & (v_name <= 0))[0]
                if len(cand):
                    key = dip_m[i, cand] if p.get("rank") == "shallowest" else -dip_m[i, cand]
                    order = cand[np.argsort(key, kind="stable")]
                    pending = [int(j) for j in order[:free]]
    curve = np.array(curve)
    spy_curve = mkt.spy[i0:i1 + 1] / mkt.spy[i0]
    out = {"params": p, "start": dates[i0], "end": dates[i1], "metrics": metrics(curve, trades), "spy": metrics(spy_curve, []),
           "avg_exposure": float(np.mean(expo)) if len(expo) else None, "risk_off_days": risk_off_days, "n_trades": len(trades)}
    if want_trades:
        out["trades"] = trades
        out["curve"] = curve
    out["_curve"] = curve
    out["_spy_curve"] = spy_curve
    return out


def metrics(curve: np.ndarray, trades) -> dict:
    if len(curve) < 2:
        return {"cagr": 0.0, "max_drawdown": 0.0, "sharpe": 0.0, "total_return": 0.0, "trades": 0, "win_rate": None, "calmar": None}
    rs = curve[1:] / curve[:-1] - 1
    peak = np.maximum.accumulate(curve)
    mdd = float((curve / peak - 1).min())
    years = len(rs) / 252
    cagr = float((curve[-1] / curve[0]) ** (1 / years) - 1) if years > 0 else 0.0
    sd = float(rs.std())
    sharpe = float(rs.mean() / sd * math.sqrt(252)) if sd else 0.0
    rets = [t["return"] if isinstance(t, dict) else t[0] for t in trades]
    kinds = [t["exit"] if isinstance(t, dict) else t[1] for t in trades]
    return {"cagr": cagr, "max_drawdown": mdd, "sharpe": sharpe, "total_return": float(curve[-1] / curve[0] - 1),
            "trades": len(trades), "win_rate": (sum(1 for r in rets if r > 0) / len(rets)) if rets else None,
            "avg_trade": statistics.mean(rets) if rets else None,
            "calmar": (cagr / -mdd) if mdd < 0 else None,
            "exits": {k: kinds.count(k) for k in ("tp", "stop", "time", "trail", "delist")}}


def yearly_excess(res: dict, dates: list[str]) -> dict[str, float]:
    """Calendar-year strategy − SPY return for a run result."""
    curve, spy = res["_curve"], res["_spy_curve"]
    i0 = dates.index(res["start"])
    out = {}
    years = sorted({d[:4] for d in dates[i0:i0 + len(curve)]})
    for y in years:
        ks = [k for k in range(len(curve)) if dates[i0 + k][:4] == y]
        if len(ks) < 2:
            continue
        a, b = ks[0], ks[-1]
        out[y] = float(curve[b] / curve[a] - spy[b] / spy[a])
    return out


def load_dir(path: str, names: list[str], sectors: list[str]) -> Market:
    d = Path(path)
    def closes(sym):
        bars = json.load(open(d / f"{sym}.json"))
        return {b["date"]: float(b["close"]) for b in bars}
    return Market(closes("SPY"), {n: closes(n) for n in names if (d / f"{n}.json").exists()},
                  {s: closes(s) for s in sectors if (d / f"{s}.json").exists()})
