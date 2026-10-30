"""Trade-for-trade validation of fastbt against the shipped backtester (the dip-only book), and — with
``--two-sleeve`` — Decision 081's gap table: the harness blend (``carry.sets()`` + ``master.book``, the Decision
068 numbers) against the package engine trading the same two-sleeve book path-exactly on the same decade data
(the 11 sector ETFs 2017-01-03 → 2026-10-12, split 2022-01-01), with diagnostic engine variants that isolate the
named differences (the band, the reserve, the shock trigger) and the dip sleeve alone for the trade count (H5).
Run from TitanTrade/: uv run --with numpy python scripts/param_search/validate.py [--two-sleeve]"""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, "src")
from titantrade.backtest.mechanical import run_mechanical_backtest
import fastbt
D = Path("data/param_search/alpaca_hist/historical_long")
NAMES = ["CRWD","ANET","LLY","DXCM","HCA","JPM","GS","DVN","WMT","URI","GE","DASH","DECK","FCX","EQIX"]
SECT = ["XLK","XLV","XLF","XLE","XLI","XLY","XLB","XLRE","XLP","XLU","XLC"]
spy = json.load(open(D / "SPY.json")); sect = {s: json.load(open(D / f"{s}.json")) for s in SECT}


def dip_only():
    bars = {n: json.load(open(D / f"{n}.json")) for n in NAMES}
    mkt = fastbt.load_dir(str(D), NAMES, SECT)
    for params in [{}, {"dip_pct": 0.08, "max_hold_days": 60, "tp_pct": 0.15, "stop_pct": 0.10}, {"dip_pct": 0.12, "dip_lookback_days": 90, "trend_sma_days": 100, "insurance_scale": 0.0, "max_slots": 4, "slot_pct": 0.15}]:
        t0 = time.time(); ref = run_mechanical_backtest(bars, spy, sect, params, "2018-01-01", "2026-10-12"); t1 = time.time()
        fast = fastbt.run(mkt, params, "2018-01-01", "2026-10-12", want_trades=True); t2 = time.time()
        rt = [(t["ticker"], t["exit_date"], t["exit"], t["return"]) for t in ref["trades"]]
        ft = [(t["ticker"], t["exit_date"], t["exit"], t["return"]) for t in fast["trades"]]
        same_trades = rt == ft
        eq_ref = ref["equity_curve"][-1]; eq_fast = float(fast["_curve"][-1])
        print(f"params={params}\n   ref: {len(rt)} trades, final {eq_ref:,.2f}, maxDD {ref['metrics']['max_drawdown']:.4f}, risk-off {ref['risk_off_days']}  ({t1-t0:.1f}s)\n   fast: {len(ft)} trades, final {eq_fast:,.2f}, maxDD {fast['metrics']['max_drawdown']:.4f}, risk-off {fast['risk_off_days']}  ({t2-t1:.2f}s)\n   trades identical: {same_trades}   equity rel diff: {abs(eq_ref-eq_fast)/eq_ref:.2e}")
        if not same_trades:
            for a, b in zip(rt, ft):
                if a != b: print("   first diff:", a, b); break
            print("   ref-only:", [x for x in rt if x not in ft][:3], "fast-only:", [x for x in ft if x not in rt][:3])


def two_sleeve():
    import numpy as np
    import carry
    import master
    _, dd, lvl, r, bear, split, _ = carry.sets()[0]   # the decade: sector dip sleeve (fastbt) + SPMO, the blend's inputs
    shock = master.shock_flags(lvl, -0.07, 10, 20); e = carry.exposure(bear, shock)
    blend = e * (0.4 * r["dip"] + 0.6 * r["mom"])
    spmo = json.load(open(D / "SPMO.json"))
    live = dict(master.LIVE, insurance_scale=0.5, momentum_weight=0.6, shock_drop_pct=0.07, shock_lookback_days=10, shock_hold_days=20, shock_scale=0.5)
    variants = [
        ("engine, path-exact, live parameters", live),
        ("  … band 0 (every leg rebalanced daily)", {**live, "core_band_pct": 0.0}),
        ("  … reserve 2 % (≈ the blend's, on 40 % of the book)", {**live, "cash_reserve_pct": 0.02}),
        ("  … band 0 and reserve 2 %", {**live, "core_band_pct": 0.0, "cash_reserve_pct": 0.02}),
        ("  … shock trigger off", {**live, "shock_drop_pct": 0.0}),
        ("  … insurance off (scale 1)", {**live, "insurance_scale": 1.0}),
        ("engine, dip sleeve alone (momentum 0, insurance ×0.5; what --shadow prints)", {**live, "momentum_weight": 0.0}),
    ]
    dates = [d for d in sorted(b["date"] for b in spy) if dd[0] <= d <= dd[-1]]
    assert dates == list(dd), "the blend and the engine must sit on the same sessions"
    spy_c = {b["date"]: float(b["close"]) for b in spy}; m = np.array([spy_c[d] for d in dates]); r_mkt = m[1:] / m[:-1] - 1
    hdr = f"{'line':74} {'excess':>7} {'IS':>7} {'OOS':>7} | {'DD':>6} {'Sharpe':>6} {'worst':>6} {'roll3':>5} | {'trades (tp/stop/time)':>22} | {'SPMO':>5} {'de-risked / risk-off / shock':>28} | core trades"
    print(f"\n=== Decision 081 — the harness blend vs the path-exact engine: sector ETFs {dd[0]} → {dd[-1]} ({len(dd)} sessions), split {split}, vs SPY\n{hdr}")
    fb = fastbt.run(fastbt.load_dir(str(D), SECT, SECT), master.LIVE, dd[0], dd[-1], want_trades=True)
    ex = fb["metrics"]["exits"]
    def row(label, s, trades="", mom="", derisk="", core=""):
        print(f"{label:74} {s['excess']:+7.2%} {s['is']:+7.2%} {s['oos']:+7.2%} | {s['dd']:6.1%} {s['sharpe']:6.2f} {s['worst_year']:+6.1%} {s['roll3_pos']:5.0%} | {trades:>22} | {mom:>5} {derisk:>28} | {core}")
    row("blend (carry.sets + master.book — the Decision 068 number)", master.score(blend, r["mkt"], dd, split),
        f"{fb['n_trades']} ({ex['tp']}/{ex['stop']}/{ex['time']}) in its dip sleeve", "60 %", f"{np.mean(e < 1):.1%} / {np.mean(bear):.1%} / {np.mean(shock):.1%}", "daily, free")
    out = {}
    for label, prm in variants:
        t0 = time.time()
        res = run_mechanical_backtest(sect, spy, sect, prm, dd[0], dd[-1], momentum_bars=spmo)
        c = np.array(res["equity_curve"]); rr = c[1:] / c[:-1] - 1
        s = master.score(rr, r_mkt, dates, split); ex = res["metrics"]["exits"]; n = len(dates)
        row(label, s, f"{res['metrics']['trades']} ({ex['tp']}/{ex['stop']}/{ex['time']})",
            f"{res['avg_momentum_share']:.0%}" if res["avg_momentum_share"] is not None else "0 %",
            f"— / {res['risk_off_days'] / n:.1%} / {res['shock_days'] / n:.1%}", f"{res['core_trades']}  ({time.time() - t0:.0f}s)")
        out[label.strip()] = {"score": {k: float(v) for k, v in s.items()}, "metrics": res["metrics"], "avg_exposure": res["avg_exposure"],
                              "min_exposure": res["min_exposure"], "avg_momentum_share": res["avg_momentum_share"], "core_trades": res["core_trades"],
                              "risk_off_days": res["risk_off_days"], "shock_days": res["shock_days"]}
    out["blend"] = {k: float(v) for k, v in master.score(blend, r["mkt"], dd, split).items()}
    Path("data/param_search/two_sleeve_gap.json").write_text(json.dumps(out, indent=2, default=str))
    print("\n  saved data/param_search/two_sleeve_gap.json")


if __name__ == "__main__":
    two_sleeve() if "--two-sleeve" in sys.argv else dip_only()
