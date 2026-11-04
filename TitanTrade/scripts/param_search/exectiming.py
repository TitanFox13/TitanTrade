"""Execution timing — the two scheduled runs against the close the backtests fill at (roadmap C5; handover §8 idea 5;
Decision 100 research, 2026-11-04; Alpaca 15-minute bars fetched on titanserver with the project's keys).

The live book trades at two runs, 10:15 and 15:30 ET: a NEW entry is a near-market bracket at the 10:15 run after the
signal (the bundle is built from the previous close), its stop and target rest on the broker and fill intraday, the
holding-limit exit is a settled close at the 10:15 run of the 60th session. Every backtest (fastbt, backtest-mech)
fills at the session close instead. The fill ledger (Decision 069) measures the gap live, one row per entry — one
row so far. This prices it on history: the dip sleeve's trades re-priced with 15-minute bars.
Data: `external/alpaca_15min/<SYM>.json` — SIP 15-minute bars, split- and dividend-adjusted, 2016-01 → 2026-11 for
SPY, SPMO, the 11 sector ETFs and the 15 shadow names (`fetch_15min.py` on the server, the research machine has no
broker keys). The fastbt trades on universe **D** (the 11 sector ETFs, the live universe) and **A** (the 15 names)
from 2017-01-03 with the live parameters; each trade re-priced: the entry at the open of the **10:15** bar (live),
the **15:30** bar (the other run), the **09:30** bar (the open) and the close (the backtest); the stop at entry × 0.88
and the target at entry × 1.20 set from the live entry, filled at the first 15-minute bar whose low / high reaches
them (at the level, or at the bar's open when it gapped through — the stop as a stop-limit is assumed filled, the
worse case), the holding limit at the 10:15 open of the 60th session; the backtest's exit is its close-based one.
Intraday prices are read as ratios to the day's last bar and applied to the daily close, so any adjustment
difference between the two feeds cancels. Gross returns both sides (the costs are the same). The sleeve-level effect
= the per-trade difference × a 10 % slot, summed per year; the band = a 400-draw bootstrap of the per-trade
differences. Halves split 2022-01-01 by entry date.
Pre-registered hypotheses (the expected numbers were written before the first run):
  X1  entries: the 10:15 fill against the close fill on entry days is within **±0.3 % per entry** on average (a
      dipped name's drift from mid-morning to the close carries no sign); the 15:30 fill within ±0.1 % (thirty
      minutes); the open within ±0.5 %. On the book: within ±0.05 pp/yr.
  X2  the stop on the broker against the close-based exit: it fires at the level, so on days the close breached it
      the live exit is 0.5 … 1.5 % higher; it also fires on **10 … 30 %** more days — the close recovered above the
      level after the touch (the whipsaw) — and those trades the backtest went on to hold; net per stop event
      ±1 %, on the book ±0.05 pp/yr.
  X3  the target as a resting limit: it sells at +20 % on the touch while the backtest waits for a close at or
      above it (often higher) — 0 … 1 % lower per target event, but it catches touches the close never confirmed
      (0 … 20 % more target exits); net ±0.05 pp/yr.
  X4  the whole sleeve re-priced live (10:15 entries, broker stops and targets, 10:15 holding-limit exits) against
      the backtest: **within ±0.2 pp/yr** on both universes (the Decision 069 / 081 expectation for the fill
      ledger); the 15:30 run against the 10:15 run within ±0.3 pp/yr, not the same sign in both halves. Context:
      SPY's mean drift from 10:15 to the close and from 15:30 to the close within ±2 bp a day.
Drop rule, written first: the entry run moves (10:15 → 15:30, or the exits change) only if one run beats the other by
more than 0.3 pp/yr in both halves on the ETFs with the same sign on the names — else nothing changes. Expected:
nothing — the roadmap's 0.06 pp/yr at 10 bp of slippage is the size of the whole question. Nothing live changes.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/exectiming.py
"""
import datetime as dt
import json
import os
import sys
import zoneinfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402
from books import DECADE_SPLIT, DECADE_START, LIVE  # noqa: E402

EXT = f"{datasets.S}/external/alpaca_15min"
ET = zoneinfo.ZoneInfo("America/New_York")
RUNS = ("10:15", "15:30", "09:30")
SLOT = 0.10


def bars(sym):
    """{session date: [(hh:mm, open, high, low, close), …]} regular-session 15-minute bars in Eastern time."""
    out = {}
    for b in json.load(open(f"{EXT}/{sym}.json")):
        t = dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(ET); hhmm = t.strftime("%H:%M")
        if "09:30" <= hhmm < "16:00":
            out.setdefault(t.strftime("%Y-%m-%d"), []).append((hhmm, b["o"], b["h"], b["l"], b["c"]))
    return out


def at(day, hhmm):
    """The open of the first bar at or after ``hhmm`` (the last bar's close on a short day), as a ratio to the day's close."""
    close = day[-1][4]
    for t, o, _, _, _ in day:
        if t >= hhmm:
            return o / close
    return 1.0


def live_path(days, dates, k, entry_px, entry_hhmm, closes, stop_pct, tp_pct, hold):
    """From the entry at (session k, time) scan the bars for the first stop / target touch, else the 10:15 open of session k + hold."""
    stop, target = entry_px * (1 - stop_pct), entry_px * (1 + tp_pct)
    for s in range(k, min(k + hold, len(dates) - 1) + 1):
        day = days.get(dates[s]); c = closes[s]
        if day is None or np.isnan(c):
            continue
        if s == k + hold:
            return at(day, "10:15") * c, "time", s
        for t, o, h, lo, cl in day:
            if s == k and t < entry_hhmm:
                continue
            o, h, lo = o / day[-1][4] * c, h / day[-1][4] * c, lo / day[-1][4] * c
            if lo <= stop:
                return min(stop, o), "stop", s
            if h >= target:
                return max(target, o), "tp", s
    return closes[min(k + hold, len(dates) - 1)], "time", min(k + hold, len(dates) - 1)


def main():
    rng = np.random.default_rng(100)
    spy = bars("SPY"); sd = sorted(d for d in spy if DECADE_START <= d)
    print("=== context — SPY's mean drift from a run to the close (bp a day), " + sd[0] + " → " + sd[-1])
    for h in RUNS:
        x = np.array([1 / at(spy[d], h) - 1 for d in sd]) * 1e4; k = next(i for i, d in enumerate(sd) if d >= DECADE_SPLIT)
        print(f"  {h} → close: mean {x.mean():+.1f} bp (IS {x[:k].mean():+.1f} / OOS {x[k:].mean():+.1f}), sd {x.std():.0f} bp, n {len(x)}")
    for key, label in (("D_alpaca_sectors_2016", "the 11 sector ETFs (the live universe)"), ("A_alpaca_names_2016", "the 15 names")):
        mkt = datasets.load(key); r = fastbt.run(mkt, LIVE, DECADE_START, None, want_trades=True); days = {s: bars(s) for s in mkt.name_list}
        years = (dt.date.fromisoformat(r["end"]) - dt.date.fromisoformat(r["start"])).days / 365.25
        rows = []
        for t in r["trades"]:
            if t["exit"] == "delist":
                continue
            j = mkt.name_list.index(t["ticker"]); e = mkt.idx[t["exit_date"]]; k = e - t["days"]; closes = mkt.names[:, j]
            if mkt.dates[k] not in days[t["ticker"]]:
                continue
            bt = {"entry": closes[k], "exit": closes[e], "ret": closes[e] / closes[k] - 1, "kind": t["exit"], "days": t["days"]}
            row = {"ticker": t["ticker"], "date": mkt.dates[k], "bt": bt, "live": {}}
            for h in RUNS:
                ep = at(days[t["ticker"]][mkt.dates[k]], h) * closes[k]
                xp, kind, s = live_path(days[t["ticker"]], mkt.dates, k, ep, h, closes, LIVE["stop_pct"], LIVE["tp_pct"], LIVE["max_hold_days"])
                row["live"][h] = {"entry": ep, "exit": xp, "ret": xp / ep - 1, "kind": kind, "days": s - k}
            rows.append(row)
        n = len(rows); ks = [i for i, w in enumerate(rows) if w["date"] >= DECADE_SPLIT]; k0 = ks[0] if ks else n
        print(f"\n=== {label}: {n} trades {r['start']} → {r['end']} ({years:.1f} years), split {DECADE_SPLIT} at trade {k0}; the backtest's exits: "
              + ", ".join(f"{kd} {sum(1 for w in rows if w['bt']['kind'] == kd)}" for kd in ("tp", "stop", "time")))
        # X1 — the entry price alone
        print(f"  {'X1 entry vs the close':34} {'mean':>7} {'median':>7} {'5–95 % of the mean':>20} | on the book pp/yr")
        for h in RUNS:
            d = np.array([w["live"][h]["entry"] / w["bt"]["entry"] - 1 for w in rows]); bs = [rng.choice(d, len(d)).mean() for _ in range(400)]
            print(f"  {h + ' fill':34} {d.mean():+7.2%} {np.median(d):+7.2%} {np.percentile(bs, 5):+8.2%} … {np.percentile(bs, 95):+7.2%} | {-d.sum() * SLOT / years:+.3%} (a higher fill costs)")
        # X2 / X3 — the exits, holding the backtest's entry fixed: the live exit kinds against the backtest's
        print(f"\n  X2 / X3 exits (entry at the close, the live stop / target / limit intraday): backtest kind → live kind")
        xr = []
        for w in rows:
            j = mkt.name_list.index(w["ticker"]); k = mkt.idx[w["date"]]; closes = mkt.names[:, j]
            xp, kind, s = live_path(days[w["ticker"]], mkt.dates, k, w["bt"]["entry"], "16:00", closes, LIVE["stop_pct"], LIVE["tp_pct"], LIVE["max_hold_days"])
            xr.append((w["bt"]["kind"], kind, xp / w["bt"]["entry"] - 1 - w["bt"]["ret"], s - k - w["bt"]["days"]))
        for bk in ("tp", "stop", "time"):
            sub = [x for x in xr if x[0] == bk]
            if sub:
                print(f"  backtest {bk:5} ({len(sub):3}): live " + ", ".join(f"{lk} {sum(1 for x in sub if x[1] == lk)}" for lk in ("tp", "stop", "time"))
                      + f" | live − backtest return mean {np.mean([x[2] for x in sub]):+.2%}, median {np.median([x[2] for x in sub]):+.2%}; days earlier {-np.mean([x[3] for x in sub]):+.1f}")
        d = np.array([x[2] for x in xr]); bs = [rng.choice(d, len(d)).mean() for _ in range(400)]
        print(f"  all exits: mean {d.mean():+.2%} per trade, 5–95 % of the mean {np.percentile(bs, 5):+.2%} … {np.percentile(bs, 95):+.2%} | on the book {d.sum() * SLOT / years:+.3%} pp/yr")
        # X4 — the whole sleeve re-priced
        print(f"\n  {'X4 the sleeve re-priced':34} {'mean Δ':>7} {'IS':>7} {'OOS':>7} {'5–95 % of the mean':>20} | on the book pp/yr (IS / OOS) | live kinds")
        for h in RUNS:
            d = np.array([w["live"][h]["ret"] - w["bt"]["ret"] for w in rows]); bs = [rng.choice(d, len(d)).mean() for _ in range(400)]
            yi = max((dt.date.fromisoformat(DECADE_SPLIT) - dt.date.fromisoformat(r["start"])).days / 365.25, 0.5); yo = max(years - yi, 0.5)
            kinds = ", ".join(f"{kd} {sum(1 for w in rows if w['live'][h]['kind'] == kd)}" for kd in ("tp", "stop", "time"))
            print(f"  {h + ' entries, broker exits':34} {d.mean():+7.2%} {d[:k0].mean() if k0 else float('nan'):+7.2%} {d[k0:].mean() if k0 < n else float('nan'):+7.2%} {np.percentile(bs, 5):+8.2%} … {np.percentile(bs, 95):+7.2%} | "
                  f"{d.sum() * SLOT / years:+.3%} ({d[:k0].sum() * SLOT / yi:+.3%} / {d[k0:].sum() * SLOT / yo:+.3%}) | {kinds}")
        d1 = np.array([w["live"]["10:15"]["ret"] - w["live"]["15:30"]["ret"] for w in rows])
        print(f"  10:15 vs 15:30 (same exits): mean {d1.mean():+.2%} per trade, IS {d1[:k0].mean() if k0 else float('nan'):+.2%} / OOS {d1[k0:].mean() if k0 < n else float('nan'):+.2%} → on the book {d1.sum() * SLOT / years:+.3%} pp/yr")


if __name__ == "__main__":
    main()
