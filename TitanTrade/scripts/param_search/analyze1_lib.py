"""Stage-1 analysis: plateau scoring, marginal effects, cross-dataset robustness."""
import json, sys, statistics, itertools  # noqa
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
