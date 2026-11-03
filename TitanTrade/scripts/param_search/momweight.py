"""The momentum weight as a curve (roadmap C1, the operator's dial; read-out 2026-11-03, Decision 091).

The master grid (Decision 067) scored the sleeve weight at a few points; the operator asked for the whole curve. Two
readings of the same book, min(insurance ×0.5, shock ×0.5) × (w_dip × dip sleeve + w_mom × momentum):
  - the harness blend (`master.book`) on the decade 2017 → and the century 1927 → in steps of 5 % — constant daily
    weights, free rebalancing, no reserve; the series every Decision 067 → 080 number came from;
  - the package engine (the live book, path-exact: the 2 % reserve, 10 % slots, the 5 % band, Decision 081 / 090) on
    the decade in steps of 10 %.
Per point: excess CAGR vs the market, both halves, the eras (century), max drawdown, Sharpe, worst relative year.
Not a test — a dial's read-out; nothing is pre-registered and nothing changes live.
Run from TitanTrade/: uv run --with numpy python scripts/param_search/momweight.py   (without -I: it imports the package)
Writes data/param_search/momweight.json for the chart.
"""
import json
import sys

sys.path.insert(0, "src"); sys.path.insert(0, "scripts/param_search")
import numpy as np  # noqa: E402

import carry  # noqa: E402
import master  # noqa: E402
import validate  # noqa: E402
from titantrade.backtest.mechanical import run_mechanical_backtest  # noqa: E402

BLEND_W = [round(x, 2) for x in np.arange(0, 1.0001, 0.05)]
ENGINE_W = [round(x, 1) for x in np.arange(0, 1.0001, 0.1)]


def row(label, w, s, extra=""):
    return (f"  {label:8} {w:5.0%} {s['excess']:+7.2%} {s['is']:+7.2%} {s['oos']:+7.2%} | {s['dd']:6.1%} {s['sharpe']:6.2f} {s['worst_year']:+6.1%} | "
            + (" ".join(f"{x:+5.1%}" for x in s["eras"]) if "eras" in s else f"roll3 {s['roll3_pos']:.0%}") + extra)


def main():
    out = {"blend": {}, "engine": {}}
    for name, dd, lvl, r, bear, split, eras in carry.sets():
        shock = master.shock_flags(lvl, -0.07, 10, 20); master.shock_scale_holder[0] = 0.5
        print(f"\n=== blend — {name} {dd[0]} → {dd[-1]}: excess vs the market by momentum weight (dip = 1 − w)")
        print(f"  {'':8} {'w_mom':>5} {'excess':>7} {'IS':>7} {'OOS':>7} | {'DD':>6} {'Sharpe':>6} {'worst':>6} | " + ("eras" if eras else "roll3"))
        out["blend"][name] = []
        for w in BLEND_W:
            rr = master.book(1 - w, r["dip"], r["mom"], r["mkt"], bear, 0.5, shock, None, False, None)
            s = master.score(rr, r["mkt"], dd, split, eras)
            out["blend"][name].append({"w": w, **{k: (float(v) if not isinstance(v, list) else [float(x) for x in v]) for k, v in s.items()}})
            print(row(name, w, s))
    _, dd, lvl, r, bear, split, _ = carry.sets()[0]
    spmo = validate.json.load(open(validate.D / "SPMO.json"))
    live = dict(master.LIVE, insurance_scale=0.5, shock_drop_pct=0.07, shock_lookback_days=10, shock_hold_days=20, shock_scale=0.5)
    dates = [d for d in sorted(b["date"] for b in validate.spy) if dd[0] <= d <= dd[-1]]
    spy_c = {b["date"]: float(b["close"]) for b in validate.spy}; m = np.array([spy_c[d] for d in dates]); r_mkt = m[1:] / m[:-1] - 1
    print(f"\n=== engine — the live book path-exact on the decade (2 % reserve, 10 % slots, 5 % band) by momentum weight")
    print(f"  {'':8} {'w_mom':>5} {'excess':>7} {'IS':>7} {'OOS':>7} | {'DD':>6} {'Sharpe':>6} {'worst':>6} | roll3 | trades")
    out["engine"]["decade"] = []
    for w in ENGINE_W:
        res = run_mechanical_backtest(validate.sect, validate.spy, validate.sect, {**live, "momentum_weight": w}, dd[0], dd[-1], momentum_bars=spmo)
        c = np.array(res["equity_curve"]); rr = c[1:] / c[:-1] - 1
        s = master.score(rr, r_mkt, dates, split)
        out["engine"]["decade"].append({"w": w, **{k: float(v) for k, v in s.items()}, "trades": res["metrics"]["trades"]})
        print(row("engine", w, s, f" | {res['metrics']['trades']}"))
    sm = master.score(r_mkt, r_mkt, dates, split)
    out["market"] = {"decade_dd": float(sm["dd"]), "decade_sharpe": float(sm["mkt_sharpe"])}
    cen = carry.sets()[1]; smc = master.score(cen[3]["mkt"], cen[3]["mkt"], cen[1], cen[5], cen[6])
    out["market"].update({"century_dd": float(smc["dd"]), "century_sharpe": float(smc["mkt_sharpe"])})
    json.dump(out, open("data/param_search/momweight.json", "w"), indent=1)
    print("\n  saved data/param_search/momweight.json")


if __name__ == "__main__":
    main()
