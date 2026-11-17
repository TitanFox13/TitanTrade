"""The 8 % drawdown gate — live has it, the backtest never did (Check 2026-11-17, finding 2; Decision 109 research).

Live, `risk_manager.check_drawdown_circuit_breaker` refuses every new dip entry while the account is 8 % or more below
the recorded peak (`MAX_DRAWDOWN_PCT`, a gate from the LLM era). The peak is written only by that check, so it is the
highest equity seen *at an entry attempt*, not the true high-water mark. `backtest/mechanical.py` has no such gate, and
every expected number of the book (Decisions 068 / 081 / 090 / 092) was computed without it. The paper account never
came near it (its peak was the LLM-era $114k); the live account's peak is the deposit, and three sessions in it is
4.8 % under it. This script trades the live book path-exactly on the package engine, with and without the gate.

Windows: the decade (Alpaca bars, the 11 sector ETFs + SPY + SPMO, 2017-01-03 →, split 2022-01-01 — Decision 081's
path) and 1999 → (Tiingo adjusted, the sector ETFs as they list, the momentum sleeve the labelled splice of Decision
092: French top decile → MTUM → SPMO; 1999-11-01 →, split 2013-05-01). Costs 5 bp a side on the dip trades, the 2 %
reserve, the 5 % band, exposure = min(insurance ×0.5, shock ×0.5). The engine has no bitcoin leg: the live equity is a
little more volatile than the engine's, so the live gate binds slightly more often than counted here.

Lines per window: gate off (the backtest of record); the gate as live (peak updated only at entry attempts, seeded
with the starting capital) at 5 / 8 / 10 / 12 / 15 %; the same thresholds against the true high-water mark; the
placebo — the as-live 8 % gate's own on-days shifted in time by a random offset (the same number of days without
entries, at a random time), DDGATE_DRAWS draws.

Pre-registered expectations (written before the first run):
  G1  it binds. On the decade the book is 8 % or more under its high-water mark on 15 … 30 % of sessions (2018-Q4,
      2020, 2022, 2025) and the as-live gate refuses 5 … 15 of the dip entries; on 1999 → 25 … 40 % of sessions.
  G2  the live peak is looser than the true high-water mark (it only moves at entry attempts), so the as-live gate
      refuses fewer entries than the high-water gate — about half.
  G3  it costs a little: −0.1 … −0.4 pp/yr against gate-off on both windows (the dips bought deep in a book drawdown
      sit in the rebound's path), and — a refused slot stays in SPY — the worst fall moves by less than 1 point.
  G4  the as-live 8 % gate sits inside its placebo band (5th … 95th percentile) on both windows.
  G5  no threshold from 5 to 15 %, on either peak, beats gate-off in both halves of both windows.

The rule (committed with this file, before the run):
  KEEP the gate — and make it the package backtester's default, so every number includes it — only if the as-live
  8 % gate (a) beats gate-off on excess return in both halves of both windows, or cuts the worst fall by 2 points or
  more on both windows at a cost under 0.2 pp/yr, AND (b) lies outside its placebo band on the good side.
  Otherwise PROPOSE REMOVING it from the live entry gates (live then equals the backtest of record: by the project's
  own bar an addition that does not beat its placebo is not kept); if its cost is inside ±0.2 pp/yr on both windows,
  "keep it as a harmless leftover and model it" is named as the alternative. The suspect-value guard (Decision 084)
  uses the same peak file and is not touched either way. Nothing live changes in this run; the operator decides.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/ddgate.py     (DDGATE_DRAWS=200)
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "src")
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import longhist  # noqa: E402
from books import LIVE  # noqa: E402
from titantrade.backtest.mechanical import run_mechanical_backtest  # noqa: E402

BOOK = dict(LIVE, insurance_scale=0.5, momentum_weight=0.6, shock_drop_pct=0.07, shock_lookback_days=10, shock_hold_days=20, shock_scale=0.5)
CAP, LIVE_PCT, THRESHOLDS = 100_000.0, 0.08, (0.05, 0.08, 0.10, 0.12, 0.15)
DRAWS = int(os.environ.get("DDGATE_DRAWS", "200"))


def bars(closes):
    return [{"date": d, "close": float(v)} for d, v in sorted(closes.items())]


def decade():
    spy = datasets.alpaca("SPY")
    return dict(name="decade 2017 → (Alpaca, SPMO)", spy=spy, sect={s: bars(datasets.alpaca(s)) for s in datasets.SECT},
                mom=bars(datasets.alpaca("SPMO")), start="2017-01-03", split="2022-01-01")


def long_history():
    spy = datasets.tiingo("SPY"); dd = [d for d in sorted(spy) if d >= longhist.START]
    level = np.concatenate([[1.0], np.cumprod(1 + longhist.momentum_splice(dd))])
    return dict(name="1999 → (Tiingo, spliced momentum)", spy=spy, sect={s: bars(datasets.tiingo(s)) for s in datasets.SECT},
                mom=bars(dict(zip(dd, level))), start=longhist.START, split=longhist.SPLIT)


def run(ds, gate=None):
    return run_mechanical_backtest(ds["sect"], bars(ds["spy"]), ds["sect"], BOOK, ds["start"], None, CAP, momentum_bars=ds["mom"], entry_gate=gate)


def live_gate(pct, log=None):
    """The live breaker: the peak moves only at an entry attempt; refused while equity is pct or more below it."""
    peak = [CAP]

    def gate(day, equity, curve):
        peak[0] = max(peak[0], equity)
        if log is not None:
            log.append((day, peak[0]))
        return equity > peak[0] * (1 - pct)
    return gate


def hwm_gate(pct):
    """The same threshold against the true high-water mark of the daily equity."""
    st = [CAP, 0]

    def gate(day, equity, curve):
        if len(curve) > st[1]:
            st[0] = max(st[0], max(curve[st[1]:])); st[1] = len(curve)
        st[0] = max(st[0], equity)
        return equity > st[0] * (1 - pct)
    return gate


def live_mask(dates, curve, log, pct):
    """The days the as-live gate would refuse an entry, from a run's curve and the peaks its attempts recorded."""
    out, peak, k = set(), CAP, 0
    for d, eq in zip(dates, curve):
        while k < len(log) and log[k][0] <= d:
            peak = log[k][1]; k += 1
        if eq <= peak * (1 - pct):
            out.add(d)
    return out


def cagr(x):
    return (x[-1] / x[0]) ** (252 / (len(x) - 1)) - 1


def score(ds, res):
    dates = ds["dates"]; cur = np.array(res["equity_curve"]); spy = np.array([ds["spy"][d] for d in dates])
    i = next(k for k, d in enumerate(dates) if d >= ds["split"])
    ex = lambda a, b: (cagr(cur[a:b]) - cagr(spy[a:b])) * 100   # noqa: E731
    dd = float((cur / np.maximum.accumulate(cur) - 1).min()) * 100
    b = res["blocked_entries"]
    episodes = sum(1 for k, x in enumerate(b) if not any(y["ticker"] == x["ticker"] and y["date"] == ds["prev"].get(x["date"]) for y in b[max(0, k - 12):k]))
    return dict(excess=ex(0, len(cur)), first=ex(0, i + 1), second=ex(i, len(cur)), dd=dd, trades=len(res["trades"]), refused=len(b), episodes=episodes)


def line(label, s, base=None):
    d = "" if base is None else f"  Δ {s['excess'] - base['excess']:+5.2f}  ΔDD {s['dd'] - base['dd']:+5.1f}"
    return f"  {label:44} {s['excess']:+6.2f} {s['first']:+6.2f} {s['second']:+6.2f} | DD {s['dd']:6.1f} | trades {s['trades']:3d} refused {s['refused']:4d} ({s['episodes']:3d} entries){d}"


def study(ds):
    random.seed(109)
    off_log = []; off = run(ds, live_gate(9e9, off_log))          # never refuses; records the as-live peak on the record path
    ds["dates"] = dates = [d for d in sorted(ds["spy"]) if off["start"] <= d <= off["end"]]
    ds["prev"] = dict(zip(dates[1:], dates[:-1]))
    assert off["equity_curve"] == run(ds)["equity_curve"], "a gate that never refuses must be the backtest of record"
    base = score(ds, off); cur = np.array(off["equity_curve"]); n = len(dates)
    under = (cur / np.maximum.accumulate(cur) - 1) <= -LIVE_PCT
    mask_off = live_mask(dates, off["equity_curve"], off_log, LIVE_PCT)
    flagged = [t["return"] for t in off["trades"] if t["entry_date"] in mask_off]; rest = [t["return"] for t in off["trades"] if t["entry_date"] not in mask_off]
    print(f"\n=== {ds['name']}: {dates[0]} → {dates[-1]} ({n} sessions), split {ds['split']}; excess vs SPY in pp/yr: whole, first half, second half")
    print(line("gate off — the backtest of record", base))
    print(f"    the record path: {under.mean() * 100:.0f} % of sessions 8 % or more under the high-water mark, {len(mask_off) / n * 100:.0f} % under the as-live peak;"
          f" the {len(flagged)} entries made on such days returned {np.mean(flagged) * 100 if flagged else float('nan'):+.1f} % on average, the other {len(rest)} {np.mean(rest) * 100:+.1f} %")
    out = {"window": [dates[0], dates[-1]], "off": base, "under_hwm": float(under.mean()), "under_live": len(mask_off) / n,
           "flagged": [len(flagged), float(np.mean(flagged)) if flagged else None], "rest": [len(rest), float(np.mean(rest))], "gates": {}}
    live8 = None
    for kind, make in (("as live", live_gate), ("high-water mark", hwm_gate)):
        for pct in THRESHOLDS:
            log = []; res = run(ds, make(pct, log) if kind == "as live" else make(pct)); s = score(ds, res)
            print(line(f"gate {pct * 100:.0f} %, {kind}", s, base)); out["gates"][f"{kind} {pct:.2f}"] = s
            if kind == "as live" and pct == LIVE_PCT:
                live8 = s; mask = live_mask(dates, res["equity_curve"], log, pct)
                assert run(ds, lambda day, eq, c: day not in mask)["equity_curve"] == res["equity_curve"], "the day mask must reproduce the gate"
    idx = [k for k, d in enumerate(dates) if d in mask]; pl = []
    for _ in range(DRAWS):
        k = random.randrange(60, n - 60); days = {dates[(j + k) % n] for j in idx}
        pl.append(score(ds, run(ds, lambda day, eq, c: day not in days)))
    ex = np.array([s["excess"] for s in pl]); dd = np.array([s["dd"] for s in pl])
    print(f"  placebo — the gate's {len(idx)} on-days shifted in time, {DRAWS} draws: excess median {np.median(ex):+.2f}, 5th … 95th {np.percentile(ex, 5):+.2f} … {np.percentile(ex, 95):+.2f};"
          f" the gate {live8['excess']:+.2f} beats {np.mean(ex < live8['excess']) * 100:.0f} % of them; DD median {np.median(dd):.1f} (the gate {live8['dd']:.1f})")
    out["placebo"] = {"draws": DRAWS, "on_days": len(idx), "excess_p5_p50_p95": [float(np.percentile(ex, q)) for q in (5, 50, 95)],
                      "gate_beats": float(np.mean(ex < live8["excess"])), "dd_median": float(np.median(dd))}
    return out


if __name__ == "__main__":
    results = {ds["name"]: study(ds) for ds in (decade(), long_history())}
    json.dump(results, open(os.path.join(datasets.S, "ddgate.json"), "w"), indent=1)
