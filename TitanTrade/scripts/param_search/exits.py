"""Exit-side variants on the live entry (Decision 065 Evidence, 2026-10-27): does capping wins at +20% / 60 days
cost us, and are the strategy's profits concentrated in its best trades? Live parameters, insurance on.
Run: uv run --with numpy python -I scripts/param_search/exits.py [dataset keys]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402

LIVE = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12,
            slot_pct=0.25, max_slots=3, insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=0.5)
NONE = 9.0
VARIANTS = [
    ("live: tp 20% / hold 60",           dict()),
    ("tp 30% / hold 60",                 dict(tp_pct=0.30)),
    ("tp 40% / hold 60",                 dict(tp_pct=0.40)),
    ("no target / hold 60",              dict(tp_pct=NONE)),
    ("tp 20% / hold 120",                dict(max_hold_days=120)),
    ("no target / hold 120",             dict(tp_pct=NONE, max_hold_days=120)),
    ("no target / hold 250",             dict(tp_pct=NONE, max_hold_days=250)),
    ("trail 10% / no target / no clock", dict(tp_pct=NONE, max_hold_days=10**6, trail_pct=0.10)),
    ("trail 15% / no target / no clock", dict(tp_pct=NONE, max_hold_days=10**6, trail_pct=0.15)),
    ("trail 15% / no target / hold 120", dict(tp_pct=NONE, max_hold_days=120, trail_pct=0.15)),
    ("live exits, shallowest dip first",  dict(rank="shallowest")),
]


# Universe-shape variants (--universe): is a broad universe's result the rule or the 3-slot concentration?
UNIVERSE_VARIANTS = [
    ("live: 3 × 25%, deepest first",          dict()),
    ("10 × 7.5%, deepest first",              dict(max_slots=10, slot_pct=0.075)),
    ("20 × 4%, deepest first",                dict(max_slots=20, slot_pct=0.04)),
    ("3 × 25%, dip 8–20% only",               dict(dip_max=0.20)),
    ("10 × 7.5%, dip 8–20% only",             dict(max_slots=10, slot_pct=0.075, dip_max=0.20)),
    ("10 × 7.5%, shallowest first",           dict(max_slots=10, slot_pct=0.075, rank="shallowest")),
    ("10 × 7.5%, dip 8–20%, shallowest",      dict(max_slots=10, slot_pct=0.075, dip_max=0.20, rank="shallowest")),
    ("20 × 4%, dip 8–20%, shallowest",        dict(max_slots=20, slot_pct=0.04, dip_max=0.20, rank="shallowest")),
]


# Crash-filter variants (--band): an upper bound on the dip, live slots.
BAND_VARIANTS = [
    ("live: dip ≥ 8%, no upper bound", dict()),
    ("dip 8–20%",                      dict(dip_max=0.20)),
    ("dip 8–25%",                      dict(dip_max=0.25)),
    ("dip 8–30%",                      dict(dip_max=0.30)),
    ("dip 8–20%, 10 × 7.5%",           dict(dip_max=0.20, max_slots=10, slot_pct=0.075)),
]


def seg_excess(curve, spyc, a, b):
    return fastbt.metrics(curve[a:b + 1], [])["cagr"] - fastbt.metrics(spyc[a:b + 1], [])["cagr"]


def concentration(rets):
    if not rets:
        return None
    r = sorted(rets, reverse=True); k = max(1, round(len(r) * 0.10))
    top = sum(r[:k]); gross = sum(x for x in r if x > 0)
    return {"top10": (top / gross) if gross else 0.0, "net_wo_top10": sum(r) - top, "median": float(np.median(r)), "best": r[0]}


def decade_excess(res, dates):
    ye = fastbt.yearly_excess(res, dates); out = {}
    for y, x in ye.items():
        out.setdefault(y[:3] + "0s", []).append(x)
    return {d: float(np.mean(v)) for d, v in out.items()}


def main(keys, variants=VARIANTS):
    for key in keys:
        mkt = datasets.load(key); dates = mkt.dates
        start, split = datasets.START[key], datasets.SPLIT[key]
        print(f"\n=== {key}  ({start} → {dates[-1]}, {len(mkt.name_list)} names, split {split})")
        print(f"{'variant':34} {'excess':>7} {'IS':>6} {'OOS':>6} | {'mdd':>6} {'spyDD':>6} | {'Sh':>5} {'spySh':>5} | {'tr/yr':>5} {'win':>4} {'exits':30} | {'top10%':>6} {'net-top10':>9} {'median':>6} {'best':>5}")
        for label, over in variants:
            p = dict(LIVE); p.update(over)
            r = fastbt.run(mkt, p, start, None, want_trades=True)
            if "error" in r:
                print(label, "range error"); continue
            curve, spyc = r["_curve"], r["_spy_curve"]; i0 = dates.index(r["start"])
            ks = dates.index(next(d for d in dates if d >= split)) - i0
            m, sp = r["metrics"], r["spy"]
            rets = [t["return"] for t in r["trades"]]; c = concentration(rets); years = len(curve) / 252
            ex = ",".join(f"{k}:{v}" for k, v in m["exits"].items() if v)
            print(f"{label:34} {m['cagr']-sp['cagr']:+7.2%} {seg_excess(curve, spyc, 0, ks):+6.1%} {seg_excess(curve, spyc, ks, len(curve)-1):+6.1%} | "
                  f"{m['max_drawdown']:6.1%} {sp['max_drawdown']:6.1%} | {m['sharpe']:5.2f} {sp['sharpe']:5.2f} | {len(rets)/years:5.1f} {m['win_rate'] or 0:4.0%} {ex:30} | "
                  + (f"{c['top10']:6.0%} {c['net_wo_top10']:+9.2f} {c['median']:+6.1%} {c['best']:+5.0%}" if c else ""))
            if label.startswith("live"):
                dec = decade_excess(r, dates)
                print("    live by decade (mean yearly excess vs benchmark):", " ".join(f"{d}:{x:+.1%}" for d, x in sorted(dec.items())))
        print(f"benchmark CAGR {sp['cagr']:.2%}, max DD {sp['max_drawdown']:.1%}")


if __name__ == "__main__":
    args = sys.argv[1:]
    chosen = UNIVERSE_VARIANTS if "--universe" in args else BAND_VARIANTS if "--band" in args else VARIANTS
    args = [a for a in args if not a.startswith("--")]
    main(args or list(datasets.START), chosen)
