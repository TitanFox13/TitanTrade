"""Stage-1 analysis: plateau scoring, marginal effects, cross-dataset robustness."""
import json, sys, statistics, itertools
S = "data/param_search"
GRID = dict(dip_pct=[0.06, 0.08, 0.10, 0.12, 0.15], dip_lookback_days=[40, 60, 90, 120], trend_sma_days=[100, 150, 200],
            max_hold_days=[20, 40, 60, 90], tp_pct=[0.06, 0.08, 0.10, 0.15, 0.20], stop_pct=[0.08, 0.10, 0.12, 0.15, 0.20])
KEYS = list(GRID)
DEFAULT = dict(dip_pct=0.10, dip_lookback_days=60, trend_sma_days=200, max_hold_days=40, tp_pct=0.10, stop_pct=0.12)
def key(pt): return tuple(pt[k] for k in KEYS)
def neighbours(k):
    out = []
    for d, name in enumerate(KEYS):
        levels = GRID[name]; i = levels.index(k[d])
        for j in (i-1, i+1):
            if 0 <= j < len(levels):
                kk = list(k); kk[d] = levels[j]; out.append(tuple(kk))
    return out
def plateau(rows, field):
    by = {key(r["pt"]): r for r in rows}
    for k, r in by.items():
        vals = [r[field]] + [by[n][field] for n in neighbours(k) if n in by]
        r["plat_" + field] = statistics.median(vals)
        r["worst_" + field] = min(vals)
    return by
def fmt(r):
    p = r["pt"]
    return (f"dip {p['dip_pct']:.2f} lb {p['dip_lookback_days']:3} sma {p['trend_sma_days']:3} hold {p['max_hold_days']:2} tp {p['tp_pct']:.2f} stop {p['stop_pct']:.2f} | "
            f"excess {r['excess']*100:+5.2f} (plat {r['plat_excess']*100:+5.2f}) IS {r['is_excess']*100:+5.2f} OOS {r['oos_excess']*100:+5.2f} (plat {r['plat_oos_excess']*100:+5.2f}) rec {r['rec_excess']*100:+5.2f} | "
            f"CAGR {r['cagr']*100:5.1f} vs SPY {r['spy_cagr']*100:4.1f} DD {r['mdd']*100:5.1f} vs {r['spy_mdd']*100:5.1f} Sh {r['sharpe']:.2f}/{r['spy_sharpe']:.2f} tr/yr {r['trades_per_year']:4.1f} win {(r['win'] or 0)*100:3.0f}%")
names = sys.argv[1:]
allby = {}
for name in names:
    rows = json.load(open(f"{S}/stage1_{name}.json"))
    by = plateau(rows, "excess"); plateau(rows, "oos_excess")
    allby[name] = by
    ok = [r for r in by.values() if r["trades_per_year"] >= 3]
    print(f"\n==== {name}: {len(rows)} points, {len(ok)} with >=3 trades/yr | SPY CAGR {rows[0]['spy_cagr']*100:.1f}% DD {rows[0]['spy_mdd']*100:.1f}%")
    print(f"   beat SPY full-period: {sum(1 for r in ok if r['excess']>0)}/{len(ok)}; OOS: {sum(1 for r in ok if r['oos_excess']>0)}/{len(ok)}; both IS&OOS: {sum(1 for r in ok if r['is_excess']>0 and r['oos_excess']>0)}/{len(ok)}")
    d = by.get(key(DEFAULT))
    if d: print("   DEFAULT (live):", fmt(d))
    print("   top 8 by PLATEAU out-of-sample excess (>=3 trades/yr):")
    for r in sorted(ok, key=lambda r: -r["plat_oos_excess"])[:8]: print("    ", fmt(r))
    print("   top 5 by PLATEAU full-period excess:")
    for r in sorted(ok, key=lambda r: -r["plat_excess"])[:5]: print("    ", fmt(r))
    print("   marginal effect of each knob (mean excess / mean OOS excess across all other settings):")
    for k in KEYS:
        parts = []
        for lv in GRID[k]:
            sub = [r for r in ok if r["pt"][k] == lv]
            if sub: parts.append(f"{lv}: {statistics.mean(r['excess'] for r in sub)*100:+.2f}/{statistics.mean(r['oos_excess'] for r in sub)*100:+.2f}")
        print(f"     {k:18} " + "  ".join(parts))
if len(names) > 1:
    print("\n==== cross-dataset robustness: average rank of plateau OOS excess across", names)
    common = set.intersection(*[set(k for k, r in by.items() if r["trades_per_year"] >= 2) for by in allby.values()])
    ranks = {}
    for name, by in allby.items():
        order = sorted(common, key=lambda k: -by[k]["plat_oos_excess"])
        for i, k in enumerate(order): ranks.setdefault(k, []).append(i)
    best = sorted(common, key=lambda k: statistics.mean(ranks[k]))[:10]
    for k in best:
        print(f"   avg rank {statistics.mean(ranks[k]):7.1f} | " + " ".join(f"{a}={b}" for a, b in zip(KEYS, k)) + " | " + " ".join(f"{n[:1]}:{allby[n][k]['oos_excess']*100:+.1f}/{allby[n][k]['excess']*100:+.1f}" for n in names))
