"""Stage 2: insurance + sizing grid around entry/exit centres, all datasets."""
import itertools
import json
import sys
import time
from multiprocessing import Pool
import fastbt
import search
S = search.S
CENTRES = {
    "c1_consensus":  dict(dip_pct=0.08, dip_lookback_days=120, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.10),
    "c2_sector_best": dict(dip_pct=0.08, dip_lookback_days=60, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.20),
    "c0_live_default": dict(dip_pct=0.10, dip_lookback_days=60, trend_sma_days=200, max_hold_days=40, tp_pct=0.10, stop_pct=0.12),
}
GRID2 = dict(insurance_sma_days=[150, 200], insurance_breadth=[0.4, 0.5, 0.6], insurance_scale=[0.0, 0.25, 0.5, 0.75, 1.0],
             slot_pct=[0.15, 0.20, 0.25], max_slots=[2, 3, 4, 5])
K2 = list(GRID2)
POINTS2 = [dict(zip(K2, v)) for v in itertools.product(*GRID2.values())]
_mkt = None; _name = None
def _init(name):
    global _mkt, _name
    _mkt = search.DATASETS[name](); _name = name
def _eval(args):
    cname, pt = args
    p = dict(CENTRES[cname]); p.update(pt)
    r = fastbt.run(_mkt, p, search.START[_name], None)
    if "error" in r: return None
    curve, spyc, dates = r["_curve"], r["_spy_curve"], _mkt.dates; i0 = dates.index(r["start"])
    ks = dates.index(next(d for d in dates if d >= search.SPLIT[_name])) - i0
    m_is, m_oos = fastbt.metrics(curve[:ks+1], []), fastbt.metrics(curve[ks:], [])
    s_is, s_oos = fastbt.metrics(spyc[:ks+1], []), fastbt.metrics(spyc[ks:], [])
    eps = {k: search._window(curve, spyc, dates, i0, a, b) for k, a, b in [("dotcom","2000-03-24","2002-10-09"),("gfc","2007-10-09","2009-03-09"),("covid","2020-02-19","2020-03-23"),("bear22","2022-01-03","2022-10-12"),("tariff25","2025-02-19","2025-04-08"),("rec09","2009-03-09","2010-03-09"),("rec20","2020-03-23","2020-09-23"),("rec25","2025-04-08","2025-10-08")]}
    ye = fastbt.yearly_excess(r, dates); yrs = sorted(ye)
    rec = sum(0.8**(2026-int(y))*ye[y] for y in yrs)/sum(0.8**(2026-int(y)) for y in yrs) if yrs else 0.0
    return {"centre": cname, "pt": pt, "cagr": r["metrics"]["cagr"], "spy_cagr": r["spy"]["cagr"], "excess": r["metrics"]["cagr"]-r["spy"]["cagr"],
            "mdd": r["metrics"]["max_drawdown"], "spy_mdd": r["spy"]["max_drawdown"], "sharpe": r["metrics"]["sharpe"], "spy_sharpe": r["spy"]["sharpe"],
            "is_excess": m_is["cagr"]-s_is["cagr"], "oos_excess": m_oos["cagr"]-s_oos["cagr"], "oos_mdd": m_oos["max_drawdown"], "oos_spy_mdd": s_oos["max_drawdown"],
            "rec_excess": rec, "episodes": eps, "risk_off_days": r["risk_off_days"], "avg_exposure": r["avg_exposure"], "trades_per_year": r["n_trades"]/(len(curve)/252)}
if __name__ == "__main__":
    which = sys.argv[1:] or list(search.DATASETS)
    for name in which:
        t0 = time.time()
        jobs = [(c, pt) for c in CENTRES for pt in POINTS2]
        with Pool(16, initializer=_init, initargs=(name,)) as pool:
            rows = [x for x in pool.map(_eval, jobs, chunksize=20) if x]
        json.dump(rows, open(f"{S}/stage2_{name}.json", "w"))
        print(f"{name}: {len(rows)} runs in {time.time()-t0:.0f}s")
