"""Stage 1: entry/exit grid, insurance off, slot 20% × 3. Four datasets. Plateau-scored."""
import itertools
import json
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I drops the script directory
import datasets  # noqa: E402
import fastbt  # noqa: E402
from analyze1_lib import GRID, KEYS  # noqa: E402  (the stage-1 grid, shared with the analysis — Decision 085)
S = datasets.S
# The four stage-1 datasets, loaded by datasets.py (Decision 085: one loader per universe, not a copy here).
DATASETS = {k: (lambda k=k: datasets.load(k)) for k in ("A_alpaca_names_2016", "D_alpaca_sectors_2016", "B_yahoo_names_1999", "C_yahoo_sectors_1999")}
START, SPLIT = datasets.START, datasets.SPLIT
POINTS = [dict(zip(KEYS, v)) for v in itertools.product(*GRID.values())]
_mkt = None; _name = None
def _init(name):
    global _mkt, _name
    _mkt = DATASETS[name](); _name = name
def _window(curve, spy, dates, i0, a, b):
    ia = next((k for k, d in enumerate(dates[i0:i0+len(curve)]) if d >= a), None)
    ib = max((k for k, d in enumerate(dates[i0:i0+len(curve)]) if d <= b), default=None)
    if ia is None or ib is None or ib <= ia: return None
    return float(curve[ib]/curve[ia]-1), float(spy[ib]/spy[ia]-1)
def _eval(pt):
    p = dict(pt); p.update(insurance_scale=1.0, slot_pct=0.20, max_slots=3)
    r = fastbt.run(_mkt, p, START[_name], None)
    if "error" in r: return None
    curve, spyc, dates = r["_curve"], r["_spy_curve"], _mkt.dates
    i0 = dates.index(r["start"])
    split = SPLIT[_name]
    ks = dates.index(next(d for d in dates if d >= split)) - i0
    m_is = fastbt.metrics(curve[:ks+1], [t for t in r["trades"] if t[2] <= ks]) if False else fastbt.metrics(curve[:ks+1], [])
    m_oos = fastbt.metrics(curve[ks:], [])
    s_is = fastbt.metrics(spyc[:ks+1], []); s_oos = fastbt.metrics(spyc[ks:], [])
    ye = fastbt.yearly_excess(r, dates)
    yrs = sorted(ye); rec = sum(0.8**(2026-int(y))*ye[y] for y in yrs)/sum(0.8**(2026-int(y)) for y in yrs) if yrs else 0.0
    eps = {k: _window(curve, spyc, dates, i0, a, b) for k, a, b in [("dotcom","2000-03-24","2002-10-09"),("gfc","2007-10-09","2009-03-09"),("covid","2020-02-19","2020-03-23"),("bear22","2022-01-03","2022-10-12"),("tariff25","2025-02-19","2025-04-08")]}
    years = len(curve)/252
    return {"pt": pt, "cagr": r["metrics"]["cagr"], "spy_cagr": r["spy"]["cagr"], "excess": r["metrics"]["cagr"]-r["spy"]["cagr"],
            "mdd": r["metrics"]["max_drawdown"], "spy_mdd": r["spy"]["max_drawdown"], "sharpe": r["metrics"]["sharpe"], "spy_sharpe": r["spy"]["sharpe"],
            "trades_per_year": r["n_trades"]/years, "win": r["metrics"]["win_rate"], "exits": r["metrics"]["exits"],
            "is_excess": m_is["cagr"]-s_is["cagr"], "oos_excess": m_oos["cagr"]-s_oos["cagr"], "oos_mdd": m_oos["max_drawdown"], "oos_spy_mdd": s_oos["max_drawdown"],
            "rec_excess": rec, "yearly_excess": ye, "episodes": eps}
if __name__ == "__main__":
    which = sys.argv[1:] or list(DATASETS)
    for name in which:
        t0 = time.time()
        with Pool(16, initializer=_init, initargs=(name,)) as pool:
            rows = [x for x in pool.map(_eval, POINTS, chunksize=25) if x]
        json.dump(rows, open(f"{S}/stage1_{name}.json", "w"))
        print(f"{name}: {len(rows)} points in {time.time()-t0:.0f}s")
