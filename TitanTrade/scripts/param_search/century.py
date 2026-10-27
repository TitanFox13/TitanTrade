"""Century check on Kenneth French's daily momentum deciles (12-2 prior return, value-weighted, 1927 →):
(a) the momentum premium itself by era, (b) the live dip rule with the deciles as "names" — all ten vs the top three —
against the market factor. Run: uv run --with numpy python -I scripts/param_search/century.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402

LIVE = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12,
            slot_pct=0.25, max_slots=3, insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=0.5)
ERAS = [("1927-07-01", "1950-01-01"), ("1950-01-01", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]


def cagr(levels, dates, a, b):
    ia = next(i for i, d in enumerate(dates) if d >= a); ib = max(i for i, d in enumerate(dates) if d <= b)
    return (levels[ib] / levels[ia]) ** (252 / (ib - ia)) - 1


def main():
    mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
    market = datasets.french_market()
    mkt_all = fastbt.Market(market, mom, mom)
    dates = mkt_all.dates
    print("=== momentum deciles vs market, CAGR by era (value-weighted, total return)")
    print(f"{'era':24} {'market':>7} {'Lo':>7} {'P5':>7} {'P9':>7} {'Hi':>7} {'Hi−mkt':>7}")
    for a, b in ERAS + [("1927-07-01", "2026-09-01")]:
        m = cagr(mkt_all.spy, dates, a, b)
        cols = {c: cagr(mkt_all.names[:, j], dates, a, b) for j, c in enumerate(mkt_all.name_list) if c in ("Lo PRIOR", "PRIOR 5", "PRIOR 9", "Hi PRIOR")}
        print(f"{a[:4]}–{b[:4]:18} {m:7.1%} {cols['Lo PRIOR']:7.1%} {cols['PRIOR 5']:7.1%} {cols['PRIOR 9']:7.1%} {cols['Hi PRIOR']:7.1%} {cols['Hi PRIOR']-m:+7.1%}")
    print("\n=== live dip rule on the deciles as names (insurance on), vs market")
    for label, keep in (("all 10 deciles", None), ("top 3 deciles (8, 9, Hi)", ("PRIOR 8", "PRIOR 9", "Hi PRIOR")), ("bottom 3 deciles", ("Lo PRIOR", "PRIOR 2", "PRIOR 3"))):
        names = {c: v for c, v in mom.items() if keep is None or c in keep}
        mkt = fastbt.Market(market, names, mom)
        for a, b in ERAS + [("1927-07-01", "2026-09-01")]:
            r = fastbt.run(mkt, LIVE, a, b)
            if "error" in r:
                continue
            m, sp = r["metrics"], r["spy"]
            print(f"{label:26} {a[:4]}–{b[:4]}: excess {m['cagr']-sp['cagr']:+6.2%}  DD {m['max_drawdown']:6.1%} vs {sp['max_drawdown']:6.1%}  Sharpe {m['sharpe']:4.2f} vs {sp['sharpe']:4.2f}  trades/yr {r['n_trades']/(len(r['_curve'])/252):4.1f}")


def regime():
    """Hi momentum decile with a trend guard (market above its 200-day SMA → Hi decile, else the market), by era."""
    mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv"); market = datasets.french_market()
    mkt = fastbt.Market(market, mom, mom); dates = mkt.dates; hi = mkt.names[:, mkt.name_list.index("Hi PRIOR")]
    sma = np.array([np.nan] * 200 + [mkt.spy[i - 200:i].mean() for i in range(200, len(dates))])
    rh = hi[1:] / hi[:-1] - 1; rm = mkt.spy[1:] / mkt.spy[:-1] - 1
    above = (mkt.spy[:-1] > sma[:-1]).astype(float)
    print("\n=== century: Hi momentum decile, unguarded vs trend-guarded (else market), CAGR − market and max drawdown")
    print(f"{'era':14} {'market':>8} {'Hi':>8} {'Hi guarded':>11} | {'DD mkt':>7} {'DD Hi':>7} {'DD guarded':>10}")
    for a, b in ERAS + [("1927-07-01", "2026-09-01")]:
        ia = next(i for i, d in enumerate(dates) if d >= a); ib = max(i for i, d in enumerate(dates) if d <= b)
        seg = slice(ia, ib)
        cm = np.cumprod(1 + rm[seg]); ch = np.cumprod(1 + np.nan_to_num(rh[seg])); cg = np.cumprod(1 + np.where(above[seg] == 1, np.nan_to_num(rh[seg]), rm[seg]))
        yrs = (ib - ia) / 252
        f = lambda c: c[-1] ** (1 / yrs) - 1  # noqa: E731
        dd = lambda c: float((c / np.maximum.accumulate(c) - 1).min())  # noqa: E731
        print(f"{a[:4]}–{b[:4]:9} {f(cm):8.1%} {f(ch)-f(cm):+8.1%} {f(cg)-f(cm):+11.1%} | {dd(cm):7.0%} {dd(ch):7.0%} {dd(cg):10.0%}")


if __name__ == "__main__":
    if "--regime" in sys.argv:
        regime()
    else:
        main()
