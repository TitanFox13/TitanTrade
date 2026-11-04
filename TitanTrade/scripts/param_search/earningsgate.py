"""The earnings gate valued on history (roadmap B10; Decision 093 research, 2026-11-04; the operator's Alpha Vantage key).

The live gate (`earnings.py`): no new entry while the name's next report is within 2 calendar days (narrowed from 5
in the LLM era). Live it is moot since Decision 070 — the dip sleeve trades sector ETFs, which have no earnings — so
this prices the gate on the only universe it can touch: the 15 shadow names, 1999-11 → 2026-11 on Tiingo (universe H),
with Alpha Vantage's reported dates (`external/alphavantage/<SYM>_earnings.json`, 1996 →). The gate is a T × N
eligibility mask into `fastbt`; the dip rule and its slots are the live ones (insurance off inside, as in the grids).
Pre-registered hypotheses (the expected numbers were written before the first run):
  E1  the live 2-day gate moves the names' excess vs SPY by **≤ 0.2 pp/yr either way** over 27 years and in each
      half; the old 5-day gate ≤ 0.4; a "through" gate (the report day and the session after it blocked too) ≤ 0.3.
      The gate blocks 2–4 % of sessions and removes 3–8 % of the entries (the next free session often takes them).
  E2  the entries the live gate would have blocked are **no worse** than the rest: their median return within ±2
      points of the unblocked entries', the stop rate within ±10 points — Decision 066's finding (nothing at entry
      predicts a trade) with earnings now a feature; the gate's effect sits inside the 5–95 % band of a placebo —
      twenty draws of random blackout windows, the same count and length per name.
  E3  the live book is untouched by the gate (sector ETFs); the gate's value is for the shadow list's tracking only.
Drop rule: the gate stays as it is whatever the numbers — it is a safety rule for single names and the live universe
has none; only if it costs more than 0.5 pp/yr on the names *and* the blocked entries beat the rest outside the
placebo band would its removal be proposed to the operator (never applied here). Nothing live changes.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/earningsgate.py
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402
from books import LIVE  # noqa: E402

START, SPLIT = "1999-11-01", "2013-05-01"
DRAWS = 20


def report_dates(sym):
    q = json.load(open(f"{datasets.S}/external/alphavantage/{sym}_earnings.json"))["quarterlyEarnings"]
    return sorted({x["reportedDate"] for x in q if x.get("reportedDate") and x["reportedDate"][:4] >= "1999"})


def mask(mkt, reports, before=2, after=-1):
    """Eligible (T × N): False on sessions from ``before`` calendar days ahead of a report to ``after`` days past it."""
    days = np.array([dt.date.fromisoformat(d).toordinal() for d in mkt.dates]); out = np.ones((len(days), len(mkt.name_list)), bool)
    for j, sym in enumerate(mkt.name_list):
        for r in reports.get(sym, []):
            o = dt.date.fromisoformat(r).toordinal(); gap = o - days
            out[(gap <= before) & (gap >= -after), j] = False
    return out


def run(mkt, elig=None):
    r = fastbt.run(mkt, {**LIVE, **({"eligible": elig} if elig is not None else {})}, START, None, want_trades=True)
    i0 = mkt.dates.index(r["start"]); c = r["_curve"]; dd = mkt.dates[i0:i0 + len(c)]; spy = mkt.spy[i0:i0 + len(c)]
    s = master.score(c[1:] / c[:-1] - 1, spy[1:] / spy[:-1] - 1, dd, SPLIT); s["trades"] = r["trades"]; return s


def main():
    mkt = datasets.load("H_tiingo_names_1999"); reports = {s: report_dates(s) for s in mkt.name_list}
    print(f"=== the 15 names on Tiingo {START} → {mkt.dates[-1]}, split {SPLIT}; reports per name: " + ", ".join(f"{s} {len(v)}" for s, v in reports.items()))
    base = run(mkt); rows = {"no gate": (base, None)}
    for label, b, a in (("live gate: 2 days before", 2, -1), ("old gate: 5 days before", 5, -1), ("through: 2 before + the day after", 2, 1)):
        m = mask(mkt, reports, b, a); rows[label] = (run(mkt, m), m)
    print(f"\n  {'gate':36} {'excess':>7} {'IS':>7} {'OOS':>7} | {'DD':>6} {'Sh':>5} | {'trades':>6} {'blocked sessions':>16} | vs no gate")
    for label, (s, m) in rows.items():
        blk = f"{1 - m.mean():.1%}" if m is not None else ""
        print(f"  {label:36} {s['excess']:+7.2%} {s['is']:+7.2%} {s['oos']:+7.2%} | {s['dd']:6.1%} {s['sharpe']:5.2f} | {len(s['trades']):6} {blk:>16} | {s['excess'] - base['excess']:+.2%}")
    # E2: the entries the live gate would have blocked, in the no-gate run
    live = mask(mkt, reports, 2, -1); blocked, free = [], []
    for t in base["trades"]:
        j = mkt.name_list.index(t["ticker"]); k = mkt.idx[t["entry_date"]]
        (blocked if not live[k, j] else free).append(t)
    def desc(ts):
        rr = np.array([t["return"] for t in ts]); stops = np.mean([t["exit"] == "stop" for t in ts]) if ts else float("nan")
        return f"{len(ts)} entries, median {np.median(rr):+.1%}, mean {rr.mean():+.1%}, stops {stops:.0%}" if ts else "0 entries"
    print(f"\n  E2 — entries on a blocked session (no-gate run): {desc(blocked)}\n       the rest:                                 {desc(free)}")
    rng = np.random.default_rng(93); effects = []
    for _ in range(DRAWS):
        fake = {s: [dt.date.fromordinal(int(x)).isoformat() for x in rng.choice(np.arange(dt.date.fromisoformat(START).toordinal(), dt.date.fromisoformat(mkt.dates[-1]).toordinal()), size=len(v), replace=False)] for s, v in reports.items()}
        effects.append(run(mkt, mask(mkt, fake, 2, -1))["excess"] - base["excess"])
    e = np.array(effects); gate = rows["live gate: 2 days before"][0]["excess"] - base["excess"]
    print(f"  placebo (random windows, same count and length, {DRAWS} draws): effect 5 % {np.percentile(e, 5):+.2%} / median {np.median(e):+.2%} / 95 % {np.percentile(e, 95):+.2%}; the live gate {gate:+.2%} → {'inside' if np.percentile(e, 5) <= gate <= np.percentile(e, 95) else 'OUTSIDE'} the band")
    print("\n  E3 — the live universe is the 11 sector ETFs: no earnings, the gate never fires; this prices it for the shadow list only.")


if __name__ == "__main__":
    main()
