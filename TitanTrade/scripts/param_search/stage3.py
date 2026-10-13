"""Stage 3: honest walk-forward — the SELECTION PROCEDURE is tested, not a config.
For each (train, test) window: run the stage-1 grid on the train window only, select by
plateau full-period excess subject to DD not worse than 1.15× SPY's and >=3 trades/yr,
then run the selected config fresh on the test window. Also reports the live default and
the stage-1 consensus centre on every test window."""
import json
import sys
import time
from multiprocessing import Pool
import fastbt
import search
import analyze1_lib as al
S = search.S
WINDOWS = {
    "A_alpaca_names_2016":   [("2016-01-04","2021-12-31","2022-01-01","2026-10-12")],
    "D_alpaca_sectors_2016": [("2016-01-04","2021-12-31","2022-01-01","2026-10-12")],
    "B_yahoo_names_1999":    [("1999-01-04","2008-12-31","2009-01-01","2017-12-31"), ("1999-01-04","2017-12-31","2018-01-01","2026-10-12"), ("2004-01-01","2013-12-31","2014-01-01","2019-12-31")],
    "C_yahoo_sectors_1999":  [("1999-01-04","2008-12-31","2009-01-01","2017-12-31"), ("1999-01-04","2017-12-31","2018-01-01","2026-10-12"), ("2004-01-01","2013-12-31","2014-01-01","2019-12-31")],
}
FIXED = dict(insurance_scale=1.0, slot_pct=0.20, max_slots=3)
_mkt = None
def _init(name):
    global _mkt
    _mkt = search.DATASETS[name]()
def _run(args):
    pt, a, b = args
    p = dict(pt); p.update(FIXED)
    r = fastbt.run(_mkt, p, a, b)
    if "error" in r: return None
    yrs = len(r["_curve"])/252
    return {"pt": pt, "excess": r["metrics"]["cagr"]-r["spy"]["cagr"], "mdd": r["metrics"]["max_drawdown"], "spy_mdd": r["spy"]["max_drawdown"],
            "cagr": r["metrics"]["cagr"], "spy_cagr": r["spy"]["cagr"], "sharpe": r["metrics"]["sharpe"], "trades_per_year": r["n_trades"]/yrs}
def select(rows):
    by = al.plateau(rows, "excess")
    ok = [r for r in by.values() if r["trades_per_year"] >= 3 and r["mdd"] >= 1.15*r["spy_mdd"]]
    if not ok: ok = [r for r in by.values() if r["trades_per_year"] >= 3]
    return max(ok, key=lambda r: r["plat_excess"])
if __name__ == "__main__":
    which = sys.argv[1:] or list(WINDOWS)
    out = {}
    for name in which:
        with Pool(16, initializer=_init, initargs=(name,)) as pool:
            for (ta, tb, sa, sb) in WINDOWS[name]:
                t0 = time.time()
                rows = [x for x in pool.map(_run, [(pt, ta, tb) for pt in search.POINTS], chunksize=25) if x]
                sel = select(rows)
                test = pool.map(_run, [(sel["pt"], sa, sb), (al.DEFAULT, sa, sb), (dict(dip_pct=0.08, dip_lookback_days=120, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.10), sa, sb)])
                res = {"train": (ta, tb), "test": (sa, sb), "selected": sel["pt"], "train_excess": sel["excess"], "train_plat": sel["plat_excess"],
                       "test_selected": test[0], "test_default": test[1], "test_consensus": test[2], "n_train_beating_spy": sum(1 for r in rows if r["excess"] > 0), "n": len(rows)}
                out.setdefault(name, []).append(res)
                f = lambda r: f"excess {r['excess']*100:+5.2f} (CAGR {r['cagr']*100:5.1f} vs {r['spy_cagr']*100:5.1f}) DD {r['mdd']*100:5.1f} vs {r['spy_mdd']*100:5.1f} Sh {r['sharpe']:.2f} tr/yr {r['trades_per_year']:.1f}"
                print(f"{name} train {ta}→{tb} (grid: {res['n_train_beating_spy']}/{res['n']} beat SPY) → test {sa}→{sb}  [{time.time()-t0:.0f}s]")
                print(f"   selected {sel['pt']} (train excess {sel['excess']*100:+.2f}, plateau {sel['plat_excess']*100:+.2f})")
                print(f"     test selected : {f(test[0])}\n     test default  : {f(test[1])}\n     test consensus: {f(test[2])}")
    json.dump(out, open(f"{S}/stage3.json", "w"), indent=1)
