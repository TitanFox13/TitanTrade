"""The recommended book's inputs, built once (Decision 085).

Every research script that judges the live design needs the same series: the sector dip sleeve run through
``fastbt`` with the live parameters, the momentum ETF, SPY, the two-signal insurance flags and the shock flags on
the ETF decade from 2017-01-03; and on the French century from 1927-07-01 the dip sleeve on the 49 industries, the
top momentum decile (frictionless) and the market with the SMA-only insurance. ``carry.sets()`` and ``master``
re-export these names, so older scripts keep working unchanged; new scripts import ``books`` directly.
De-risked capital earns 0 here by design (a bias against de-risking rules); ``rf_daily`` is the bill rate for the
honest-expectation line. Run nothing from here: it is a library.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402

# The live dip rule as the sleeve inside a book: insurance_scale 1.0 because the book applies the exposure rules itself.
LIVE = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12,
            slot_pct=0.25, max_slots=3, insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=1.0)
DECADE_START, DECADE_SPLIT = "2017-01-03", "2022-01-01"
CENTURY_START, CENTURY_SPLIT = "1927-07-01", "1975-01-01"
ERAS = [("1927-07-01", "1950-01-01"), ("1950-01-01", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]


def prev(a):
    """The previous session's value (signals act one session late in the blend)."""
    return np.concatenate([[np.nan], a[:-1]])


def sma_above(x, n=200):
    out = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        out[i] = 1.0 if x[i] > x[i - n:i].mean() else 0.0
    return out


def shock_flags(level, thr, look, hold):
    """The shock trigger on a level series: a ``look``-session return below ``thr`` seen at the previous close → on for ``hold`` sessions."""
    n = len(level) - 1
    ret = np.array([np.nan] * look + [level[i] / level[i - look] - 1 for i in range(look, n + 1)])[1:]
    ret = prev(ret); e = np.zeros(n, dtype=bool); k = 0
    for i in range(n):
        if ret[i] < thr: k = hold
        e[i] = k > 0; k = max(0, k - 1)
    return e


def exposure(bear, shock):
    """The live rule: min(insurance ×0.5, shock ×0.5)."""
    return np.minimum(np.where(bear, 0.5, 1.0), np.where(shock, 0.5, 1.0))


def decade(curated=False, etfs=("SPMO",)):
    """The ETF decade from 2017-01-03. ``r``: ``sec`` the sector dip sleeve's daily return, ``mkt`` SPY's, one key per
    requested ETF, ``cur`` the curated-list sleeve when asked; ``bear`` the previous-session two-signal insurance flag;
    ``spy`` the level series the shock trigger reads; plus the Markets, the full date list and the index for scripts
    that need the raw matrices."""
    cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index(DECADE_START)
    _, _, spy_above, breadth = cur.pre(90, 150, 200)
    SEC = fastbt.run(sec, LIVE, DECADE_START, None)["_curve"]; d = dates[i0:]
    def etf(sym):
        v = datasets.alpaca(sym); return np.array([v.get(t, np.nan) for t in d])
    series = {s: etf(s) for s in etfs}
    CUR = fastbt.run(cur, LIVE, DECADE_START, None)["_curve"] if curated else None
    n = min([len(SEC)] + [len(v) for v in series.values()] + ([len(CUR)] if curated else []))
    d = d[:n]; spy = cur.spy[i0:i0 + n]
    r = {"sec": SEC[1:n] / SEC[:n - 1] - 1, "mkt": spy[1:] / spy[:-1] - 1}
    for s, v in series.items():
        r[s] = v[1:n] / v[:n - 1] - 1
    if curated:
        r["cur"] = CUR[1:n] / CUR[:n - 1] - 1
    bear = (prev(spy_above[i0:i0 + n][1:]) == 0.0) & (prev(breadth[i0:i0 + n][1:]) < 0.5)
    return dict(d=d, spy=spy, r=r, bear=bear, cur=cur, sec=sec, dates=dates, i0=i0, n=n, spy_above=spy_above, breadth=breadth)


def century():
    """The French century from 1927-07-01. ``r``: ``dip`` the sleeve on the 49 industries, ``mom`` the top momentum
    decile, ``mkt`` the market; ``bear`` the previous-session SMA-only insurance flag; ``mkt`` (level) for the shock
    trigger; plus the industries Market, the decile levels and the fastbt result for scripts that need more."""
    ind = datasets.load("F_french_49ind_1926"); mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
    r0 = fastbt.run(ind, LIVE, CENTURY_START, None); fd = ind.dates[ind.dates.index(r0["start"]):]
    dip = r0["_curve"]; mk = r0["_spy_curve"]; hi = np.array([mom["Hi PRIOR"].get(x, np.nan) for x in fd])
    r = {"dip": dip[1:] / dip[:-1] - 1, "mom": np.nan_to_num(hi[1:] / hi[:-1] - 1), "mkt": mk[1:] / mk[:-1] - 1}
    bear = prev(sma_above(mk)[1:]) == 0.0
    return dict(d=fd, mkt=mk, r=r, bear=bear, ind=ind, mom=mom, r0=r0)


def sets():
    """The two books as ``(name, dates, level series, {dip, mom, mkt}, bear, split, eras)`` — the shape every
    Decision 068 → 080 script reads through ``carry.sets()``."""
    dec = decade(); cen = century()
    return [("decade", dec["d"], dec["spy"], {"dip": dec["r"]["sec"], "mom": dec["r"]["SPMO"], "mkt": dec["r"]["mkt"]}, dec["bear"], DECADE_SPLIT, None),
            ("century", cen["d"], cen["mkt"], cen["r"], cen["bear"], CENTURY_SPLIT, ERAS)]


def rf_daily():
    """Kenneth French's daily T-bill return, decimal, by date."""
    cols, rows = datasets._french_section(f"{datasets.S}/french/F-F_Research_Data_Factors_daily.csv", ",Mkt-RF")
    i = cols.index("RF")
    return {d: rows[d][i] / 100 for d in sorted(rows)}


def align_rf(dates, rf):
    """RF for each return day (dates[1:]); a date missing from the French file carries the last known rate."""
    out = np.zeros(len(dates) - 1); last = 0.0
    for k, d in enumerate(dates[1:]):
        last = rf.get(d, last); out[k] = last
    return out
