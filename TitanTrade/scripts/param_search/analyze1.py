"""Stage-1 analysis: plateau scoring, marginal effects, cross-dataset robustness.
Run: uv run python -I scripts/param_search/analyze1.py <dataset key> [<dataset key> …] (reads data/param_search/stage1_<key>.json).
The grid, the keys and the scoring helpers live in analyze1_lib.py (Decision 085)."""
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I drops the script directory
from analyze1_lib import DEFAULT, GRID, KEYS, S, fmt, key, plateau  # noqa: E402

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
