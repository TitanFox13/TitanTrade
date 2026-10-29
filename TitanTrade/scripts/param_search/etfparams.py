"""Re-check of the dip rule's parameters on the hindsight-free universes, after Decision 070 made the 11 sector ETFs
the live dip universe (operator's pick, 2026-10-29). Decision 062 chose the live cell (dip 8 % / 90 d / SMA150 / 60 d /
+20 % / −12 %) as the consensus plateau across four universes, two of them the hand-picked names; "a watchlist change is
a strategy change — test it like one" (Decision 065 Evidence). Same stage-1 grid (6,000 cells), same plateau scoring
(median over the twelve one-step neighbours), same stage-3 walk-forward of the *selection procedure*, now on D (the 11
sector ETFs, Alpaca 2016 →, split 2022) and F (the 49 French industries 1927 →, split 1990; four quarter-century eras
for the finalists); C (Yahoo sectors 1999 →) is still unavailable. Slots 3 × 25 % of the dip book (the live sleeve),
insurance off in the grid as in 062, ×0.5 in the slot grid and the two-sleeve scoring. Pre-registered hypotheses:
  P1  plateau: the live cell sits on a plateau on both universes — the median of its twelve neighbours within ±0.5
      pp/yr of the cell, and on D no neighbour flips the sign of the full-period excess;
  P2  marginals: the knob directions of Decision 062 hold on D and F (target 20 ≥ 15 ≥ 10, dip 8 ≥ 10, SMA 150 ≥ 200
      ≥ 100, hold 40–90 flat, stop 8–20 flat); where a direction differs, the difference is under 0.5 pp;
  P3  walk-forward: the cell the selection procedure picks on a training window does no better than the fixed live
      cell on the test window, averaged over the windows (062: the per-window winners lost);
  P4  sizing: 3 × 25 % is on the slot plateau (2–4 slots × 20–33 %), and the two-sleeve book's excess moves < 0.3 pp
      across that plateau;
  P5  consensus: the cross-universe top region (average rank by plateau out-of-sample excess over D and F) contains
      the live cell or a cell one step from it. Only if the best consensus cell differs by more than one step in some
      knob AND beats the live cell out of sample on both D and F by > 0.5 pp AND does so inside the two-sleeve book is
      it proposed (as a Decision for the operator, never applied here). Anything else → no change.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/etfparams.py   (grids cached in data/param_search/etfparams_*.json)
"""
import json
import os
import statistics
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import analyze1_lib as al  # noqa: E402
import carry  # noqa: E402
import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402
import search  # noqa: E402
import stage3  # noqa: E402

LIVE_CELL = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12)
SECTOR_BEST_062 = dict(dip_pct=0.08, dip_lookback_days=60, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.20)
FIXED = dict(insurance_scale=1.0, slot_pct=0.25, max_slots=3)
UNI = {"D": ("D_alpaca_sectors_2016", "2016-01-04", "2022-01-01"), "F": ("F_french_49ind_1926", "1927-07-01", "1990-01-01")}
WINDOWS = {"D": [("2016-01-04", "2021-12-31", "2022-01-01", "2026-10-12")],
           "F": [("1927-07-01", "1974-12-31", "1975-01-01", "2026-08-31"), ("1975-01-01", "2026-08-31", "1927-07-01", "1974-12-31"),
                 ("1927-07-01", "1989-12-31", "1990-01-01", "2026-08-31"), ("1950-01-01", "1999-12-31", "2000-01-01", "2026-08-31")]}
MIN_TR = {"D": 2.0, "F": 3.0}
_mkt = None


def _init(key):
    global _mkt
    _mkt = datasets.load(UNI[key][0])


def _eval(args):
    pt, a, b, split = args
    p = dict(pt); p.update(FIXED)
    r = fastbt.run(_mkt, p, a, b)
    if "error" in r:
        return None
    curve, spyc, dates = r["_curve"], r["_spy_curve"], _mkt.dates; i0 = dates.index(r["start"]); yrs = len(curve) / 252
    row = {"pt": pt, "excess": r["metrics"]["cagr"] - r["spy"]["cagr"], "cagr": r["metrics"]["cagr"], "spy_cagr": r["spy"]["cagr"],
           "mdd": r["metrics"]["max_drawdown"], "spy_mdd": r["spy"]["max_drawdown"], "sharpe": r["metrics"]["sharpe"], "spy_sharpe": r["spy"]["sharpe"],
           "trades_per_year": r["n_trades"] / yrs, "win": r["metrics"]["win_rate"]}
    if split:
        ks = next((k for k, d in enumerate(dates[i0:i0 + len(curve)]) if d >= split), None)
        if ks:
            row["is_excess"] = fastbt.metrics(curve[:ks + 1], [])["cagr"] - fastbt.metrics(spyc[:ks + 1], [])["cagr"]
            row["oos_excess"] = fastbt.metrics(curve[ks:], [])["cagr"] - fastbt.metrics(spyc[ks:], [])["cagr"]
    return row


def grid(key):
    path = f"{datasets.S}/etfparams_{key}.json"
    if os.path.exists(path):
        return json.load(open(path))
    _, start, split = UNI[key]; t0 = time.time()
    with Pool(16, initializer=_init, initargs=(key,)) as pool:
        rows = [x for x in pool.map(_eval, [(pt, start, None, split) for pt in search.POINTS], chunksize=25) if x]
    json.dump(rows, open(path, "w")); print(f"[{key}] grid: {len(rows)} cells in {time.time() - t0:.0f}s", flush=True)
    return rows


def fmt(r):
    p = r["pt"]
    return (f"dip {p['dip_pct']:.2f} lb {p['dip_lookback_days']:3} sma {p['trend_sma_days']:3} hold {p['max_hold_days']:2} tp {p['tp_pct']:.2f} stop {p['stop_pct']:.2f} | "
            f"excess {r['excess']:+6.2%} (plat {r['plat_excess']:+6.2%}) IS {r.get('is_excess', float('nan')):+6.2%} OOS {r.get('oos_excess', float('nan')):+6.2%} (plat {r['plat_oos_excess']:+6.2%}) | "
            f"DD {r['mdd']:6.1%} vs {r['spy_mdd']:6.1%} Sh {r['sharpe']:.2f}/{r['spy_sharpe']:.2f} tr/yr {r['trades_per_year']:4.1f} win {(r['win'] or 0):3.0%}")


def analyse(grids):
    by = {}
    for key, rows in grids.items():
        b = al.plateau(rows, "excess"); al.plateau(rows, "oos_excess"); by[key] = b
        ok = [r for r in b.values() if r["trades_per_year"] >= MIN_TR[key]]
        live = b[al.key(LIVE_CELL)]
        print(f"\n==== {key}: {len(rows)} cells, {len(ok)} with ≥ {MIN_TR[key]:.0f} trades/yr | SPY CAGR {rows[0]['spy_cagr']:.1%} DD {rows[0]['spy_mdd']:.1%}")
        print(f"   beat SPY full-period {sum(1 for r in ok if r['excess'] > 0)}/{len(ok)}; OOS {sum(1 for r in ok if r['oos_excess'] > 0)}/{len(ok)}; both halves {sum(1 for r in ok if r['is_excess'] > 0 and r['oos_excess'] > 0)}/{len(ok)}")
        print("   LIVE cell:        ", fmt(live))
        nb = [b[m]["excess"] for m in al.neighbours(al.key(LIVE_CELL)) if m in b]
        print(f"   live neighbours (12): excess min {min(nb):+.2%} median {statistics.median(nb):+.2%} max {max(nb):+.2%}; sign flips {sum(1 for x in nb if (x > 0) != (live['excess'] > 0))}/{len(nb)}; "
              f"live rank by plateau OOS among ok cells: {sorted(ok, key=lambda r: -r['plat_oos_excess']).index(live) + 1 if live in ok else 'n/a'} of {len(ok)}")
        print("   062 sector-best:  ", fmt(b[al.key(SECTOR_BEST_062)]))
        print("   top 8 by plateau OOS excess:")
        for r in sorted(ok, key=lambda r: -r["plat_oos_excess"])[:8]:
            print("     ", fmt(r))
        print("   top 5 by plateau full-period excess:")
        for r in sorted(ok, key=lambda r: -r["plat_excess"])[:5]:
            print("     ", fmt(r))
        print("   marginal effect of each knob (mean excess / mean OOS excess over all other settings):")
        for k in al.KEYS:
            parts = []
            for lv in al.GRID[k]:
                sub = [r for r in ok if r["pt"][k] == lv]
                if sub:
                    parts.append(f"{lv}: {statistics.mean(r['excess'] for r in sub):+.2%}/{statistics.mean(r['oos_excess'] for r in sub):+.2%}")
            print(f"     {k:18} " + "  ".join(parts))
    # consensus across D and F
    common = set.intersection(*[set(k for k, r in b.items() if r["trades_per_year"] >= MIN_TR[key]) for key, b in by.items()])
    ranks = {}
    for key, b in by.items():
        order = sorted(common, key=lambda k: -b[k]["plat_oos_excess"])
        for i, k in enumerate(order):
            ranks.setdefault(k, []).append(i)
    best = sorted(common, key=lambda k: statistics.mean(ranks[k]))
    lk = al.key(LIVE_CELL)
    print(f"\n==== consensus D + F: average rank by plateau OOS excess over {len(common)} common cells; live cell rank {best.index(lk) + 1 if lk in best else 'n/a'}")
    for k in best[:10]:
        print(f"   avg rank {statistics.mean(ranks[k]):7.1f} | " + " ".join(f"{a}={v}" for a, v in zip(al.KEYS, k)) + " | " + " ".join(f"{n}: OOS {by[n][k]['oos_excess']:+.1%} full {by[n][k]['excess']:+.1%}" for n in by))
    return by, best


def walkforward(key):
    print(f"\n==== walk-forward of the selection — {key}")
    with Pool(16, initializer=_init, initargs=(key,)) as pool:
        for ta, tb, sa, sb in WINDOWS[key]:
            t0 = time.time()
            rows = [x for x in pool.map(_eval, [(pt, ta, tb, None) for pt in search.POINTS], chunksize=25) if x]
            sel = stage3.select(rows)
            test = pool.map(_eval, [(sel["pt"], sa, sb, None), (LIVE_CELL, sa, sb, None), (SECTOR_BEST_062, sa, sb, None)])
            f = lambda r: f"excess {r['excess']:+6.2%} DD {r['mdd']:6.1%} vs {r['spy_mdd']:6.1%} Sh {r['sharpe']:.2f} tr/yr {r['trades_per_year']:.1f}"  # noqa: E731
            print(f"  train {ta} → {tb} ({sum(1 for r in rows if r['excess'] > 0)}/{len(rows)} cells beat SPY) → test {sa} → {sb}  [{time.time() - t0:.0f}s]")
            print(f"     selected {sel['pt']} (train excess {sel['excess']:+.2%}, plateau {sel['plat_excess']:+.2%})")
            print(f"     test selected       : {f(test[0])}\n     test LIVE cell      : {f(test[1])}\n     test 062 sector-best: {f(test[2])}")


def slots():
    print("\n==== slot grid at the live cell, insurance ×0.5 (the dip book alone): excess (IS / OOS) | DD | Sharpe")
    for key, (name, start, split) in UNI.items():
        mkt = datasets.load(name); print(f"  --- {key}")
        for n in (2, 3, 4, 5):
            line = f"  {n} slots: "
            for sp in (0.15, 0.20, 0.25, 0.33):
                r = fastbt.run(mkt, {**LIVE_CELL, "insurance_scale": 0.5, "slot_pct": sp, "max_slots": n}, start, None)
                curve, spyc, dates = r["_curve"], r["_spy_curve"], mkt.dates; i0 = dates.index(r["start"])
                ks = next(k for k, d in enumerate(dates[i0:i0 + len(curve)]) if d >= split)
                is_ = fastbt.metrics(curve[:ks + 1], [])["cagr"] - fastbt.metrics(spyc[:ks + 1], [])["cagr"]; oos = fastbt.metrics(curve[ks:], [])["cagr"] - fastbt.metrics(spyc[ks:], [])["cagr"]
                line += f"| {sp:.0%}: {r['metrics']['cagr'] - r['spy']['cagr']:+5.1%} ({is_:+4.1%}/{oos:+4.1%}) DD {r['metrics']['max_drawdown']:5.0%} Sh {r['metrics']['sharpe']:.2f} "
            print(line)


def blend(cells):
    print("\n==== the finalists inside the two-sleeve book (min(insurance ×0.5, shock) × (0.4 dip + 0.6 momentum))")
    sec = datasets.load("D_alpaca_sectors_2016"); ind = datasets.load("F_french_49ind_1926")
    for name, dd, lvl, r, bear, split, eras in carry.sets():
        mkt, start = (sec, "2017-01-03") if name == "decade" else (ind, "1927-07-01")
        shock = master.shock_flags(lvl, -0.07, 10, 20); e = carry.exposure(bear, shock); n = len(r["mkt"]) + 1
        print(f"  --- {name}: " + ("excess, IS / OOS, DD, Sharpe, worst year" if not eras else "excess, 1927–74 / 1975–, DD, Sharpe; eras"))
        for label, cell in cells.items():
            c = fastbt.run(mkt, {**cell, **FIXED}, start, None)["_curve"][:n]
            dip = c[1:] / c[:-1] - 1
            s = master.score(e * (0.4 * dip + 0.6 * r["mom"]), r["mkt"], dd, split, eras)
            print(f"  {label:44} {s['excess']:+6.2%} {s['is']:+6.1%} / {s['oos']:+6.1%} | {s['dd']:6.1%} {s['sharpe']:5.2f} | {s['worst_year']:+6.1%}" + (" | " + " ".join(f"{x:+5.1%}" for x in s["eras"]) if eras else ""))


if __name__ == "__main__":
    grids = {k: grid(k) for k in UNI}
    by, best = analyse(grids)
    for k in UNI:
        walkforward(k)
    slots()
    top = {f"consensus #{i + 1}": dict(zip(al.KEYS, k)) for i, k in enumerate(best[:3])}
    bestD = max((r for r in by["D"].values() if r["trades_per_year"] >= MIN_TR["D"]), key=lambda r: r["plat_oos_excess"])["pt"]
    bestF = max((r for r in by["F"].values() if r["trades_per_year"] >= MIN_TR["F"]), key=lambda r: r["plat_oos_excess"])["pt"]
    blend({"LIVE 8/90/150/60/20/12": LIVE_CELL, "062 sector-best 8/60/150/60/20/20": SECTOR_BEST_062, "D best by plateau OOS": bestD, "F best by plateau OOS": bestF, **top})
