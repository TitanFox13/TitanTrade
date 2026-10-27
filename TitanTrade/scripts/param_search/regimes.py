"""Regime switching on the 50/50 book (operator question, 2026-10-27): does a richer "which epoch are we in" rule beat
the live two-signal insurance? Rules set each day's exposure from the previous session's signals; the remainder sits in
SPY (or in cash where the rule's point is de-risking). Decade = sector-dip book + MTUM/SPMO; century = dip on 49
industries + top momentum decile. Run: uv run --with numpy python -I scripts/param_search/regimes.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402

LIVE = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12,
            slot_pct=0.25, max_slots=3, insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=1.0)   # raw dip book, insurance applied here


def cagr(c):
    return fastbt.metrics(c, [])["cagr"]


def sma_above(x, n=200):
    out = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        out[i] = 1.0 if x[i] > x[i - n:i].mean() else 0.0
    return out


def roll_vol(r, n=20):
    out = np.full(len(r), np.nan)
    for i in range(n, len(r)):
        out[i] = r[i - n:i].std() * np.sqrt(252)
    return out


def run_rules(dates, r_dip, r_mom, r_mkt, mkt_level, breadth, mom_level, split, episodes, label_extra=""):
    n = len(r_dip); T = n + 1
    above = sma_above(mkt_level)[1:]                       # aligned to returns index i (signal from day i-1 → we shift below)
    vol = roll_vol(r_mkt)
    ret10 = np.array([np.nan] * 10 + [mkt_level[i] / mkt_level[i - 10] - 1 for i in range(10, T)])[1:]
    mom12 = np.array([np.nan] * 252 + [mom_level[i - 21] / mom_level[i - 252] - 1 for i in range(252, T)])[1:]
    br = breadth[1:] if breadth is not None else np.full(n, np.nan)
    def prev(a):  # previous-session signal
        return np.concatenate([[np.nan], a[:-1]])
    above_p, vol_p, ret10_p, mom12_p, br_p = prev(above), prev(vol), prev(ret10), prev(mom12), prev(br)
    bear2 = (above_p == 0.0) & (br_p < 0.5) if breadth is not None else (above_p == 0.0)
    one_bear = ((above_p == 0.0) | (br_p < 0.5)) if breadth is not None else (above_p == 0.0)
    rules = {}
    rules["R0 no regime rule (50/50 always)"] = (np.full(n, .5), np.full(n, .5), np.zeros(n))
    rules["R1 live two-signal: everything ×0.5"] = (np.where(bear2, .25, .5), np.where(bear2, .25, .5), np.zeros(n))
    rules["R2 three-state mix (bull 50/50, caution 65/35, bear dip-only)"] = (np.where(bear2, .5, np.where(one_bear, .65, .5)), np.where(bear2, 0.0, np.where(one_bear, .35, .5)), np.zeros(n))
    rules["R3 sleeve on its own momentum (12-1 > 0 else SPY)"] = (np.full(n, .5), np.where(mom12_p > 0, .5, 0.0), np.zeros(n))
    vt = np.clip(0.15 / np.where(np.isnan(vol_p), 0.15, vol_p), 0.0, 1.0)
    rules["R4 volatility target 15% (rest in cash)"] = (.5 * vt, .5 * vt, 1 - vt)
    shock = np.zeros(n, dtype=bool); k = 0
    for i in range(n):
        if ret10_p[i] < -0.07: k = 20
        shock[i] = k > 0; k = max(0, k - 1)
    rules["R5 shock trigger: SPY −7% in 10 d → ×0.5 for 20 d (rest cash)"] = (np.where(shock, .25, .5), np.where(shock, .25, .5), np.where(shock, .5, 0.0))
    rules["R6 = R1 + R5"] = (np.where(bear2 | shock, .25, .5), np.where(bear2 | shock, .25, .5), np.where(shock, .5, 0.0))
    ks = next(k for k, d in enumerate(dates) if d >= split)
    print(f"{'rule':62} {'vs mkt':>7} {'IS':>6} {'OOS':>6} | {'DD':>6} {'mktDD':>6} | {'Sharpe':>6} {'mkt':>5} | " + " ".join(f"{e[0]:>9}" for e in episodes) + " | time de-risked")
    for name, (wd, wm, wc) in rules.items():
        r = wd * r_dip + wm * r_mom + (1 - wd - wm - wc) * r_mkt
        c = np.concatenate([[1.0], np.cumprod(1 + r)]); m = np.concatenate([[1.0], np.cumprod(1 + r_mkt)])
        mm, mk = fastbt.metrics(c, []), fastbt.metrics(m, [])
        eps = []
        for _, a, b in episodes:   # relative return peak → trough
            ia = next(i for i, d in enumerate(dates) if d >= a); ib = next(i for i, d in enumerate(dates) if d >= b)
            eps.append((c[ib] / c[ia]) - (m[ib] / m[ia]))
        derisk = float(np.mean((wd + wm) < 0.99))
        print(f"{name:62} {mm['cagr']-mk['cagr']:+7.1%} {cagr(c[:ks+1])-cagr(m[:ks+1]):+6.1%} {cagr(c[ks:])-cagr(m[ks:]):+6.1%} | {mm['max_drawdown']:6.1%} {mk['max_drawdown']:6.1%} | {mm['sharpe']:6.2f} {mk['sharpe']:5.2f} | " + " ".join(f"{x:+9.1%}" for x in eps) + f" | {derisk:4.0%}")


def main():
    # ---- decade
    cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index("2017-01-03")
    _, _, _, breadth = cur.pre(90, 150, 200)
    SEC = fastbt.run(sec, LIVE, "2017-01-03", None)["_curve"]; d = dates[i0:]
    def etf(sym):
        v = datasets.alpaca(sym); x = np.array([v.get(t, np.nan) for t in d]); return x
    MT, SP = etf("MTUM"), etf("SPMO"); n = min(len(SEC), len(MT), len(SP)); d = d[:n]
    spy = cur.spy[i0:i0 + n]
    r_dip = SEC[1:n] / SEC[:n - 1] - 1; r_mom = 0.5 * (MT[1:n] / MT[:n - 1] - 1) + 0.5 * (SP[1:n] / SP[:n - 1] - 1); r_mkt = spy[1:] / spy[:-1] - 1
    mom_level = np.concatenate([[1.0], np.cumprod(1 + r_mom)])
    print("=== decade 2017 → 2026, sector-dip book (raw) + MTUM/SPMO; columns at the right = book minus SPY from the peak to the market trough")
    run_rules(d, r_dip, r_mom, r_mkt, spy, breadth[i0:i0 + n], mom_level, "2022-01-01",
              [("2020 covid", "2020-02-19", "2020-03-23"), ("2022 bear", "2022-01-03", "2022-10-12"), ("2025 tariff", "2025-02-19", "2025-04-08"), ("2023 (rally yr)", "2023-01-03", "2023-12-29")])
    # ---- century
    ind = datasets.load("F_french_49ind_1926"); mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
    r = fastbt.run(ind, LIVE, "1927-07-01", None); fd = ind.dates[ind.dates.index(r["start"]):]
    dip = r["_curve"]; mk = r["_spy_curve"]; hi = np.array([mom["Hi PRIOR"].get(x, np.nan) for x in fd])
    r_dip = dip[1:] / dip[:-1] - 1; r_mkt = mk[1:] / mk[:-1] - 1; r_mom = np.nan_to_num(hi[1:] / hi[:-1] - 1)
    print("\n=== century 1927 → 2026, dip on 49 industries (raw) + top momentum decile; no breadth series, so the two-signal rule is SMA200-only here")
    run_rules(fd, r_dip, r_mom, r_mkt, mk, None, np.concatenate([[1.0], np.cumprod(1 + r_mom)]), "1990-01-01",
              [("1929 crash", "1929-09-03", "1932-06-01"), ("1973 bear", "1973-01-11", "1974-10-03"), ("2008 crisis", "2007-10-09", "2009-03-09"), ("2009 rebound", "2009-03-09", "2010-03-09")])


def shock_grid():
    """Robustness of the shock trigger: drop threshold × lookback × hold × scale, decade and century; cost vs no rule."""
    import itertools
    sets = []
    cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index("2017-01-03")
    SEC = fastbt.run(sec, LIVE, "2017-01-03", None)["_curve"]; d = dates[i0:]
    def etf(sym):
        v = datasets.alpaca(sym); return np.array([v.get(t, np.nan) for t in d])
    MT, SP = etf("MTUM"), etf("SPMO"); n = min(len(SEC), len(MT), len(SP)); spy = cur.spy[i0:i0 + n]
    sets.append(("decade", d[:n], SEC[1:n] / SEC[:n - 1] - 1, 0.5 * (MT[1:n] / MT[:n - 1] - 1) + 0.5 * (SP[1:n] / SP[:n - 1] - 1), spy[1:] / spy[:-1] - 1, spy, "2022-01-01"))
    ind = datasets.load("F_french_49ind_1926"); mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
    r = fastbt.run(ind, LIVE, "1927-07-01", None); fd = ind.dates[ind.dates.index(r["start"]):]
    dip = r["_curve"]; mk = r["_spy_curve"]; hi = np.array([mom["Hi PRIOR"].get(x, np.nan) for x in fd])
    sets.append(("century", fd, dip[1:] / dip[:-1] - 1, np.nan_to_num(hi[1:] / hi[:-1] - 1), mk[1:] / mk[:-1] - 1, mk, "1990-01-01"))
    grid = list(itertools.product((-0.05, -0.07, -0.10), (5, 10, 20), (10, 20, 40), (0.5, 0.25, 0.0)))
    for name, dd, r_dip, r_mom, r_mkt, level, split in sets:
        n = len(r_dip); ks = next(k for k, x in enumerate(dd) if x >= split)
        base = np.concatenate([[1.0], np.cumprod(1 + 0.5 * r_dip + 0.5 * r_mom)]); m = np.concatenate([[1.0], np.cumprod(1 + r_mkt)])
        b0 = cagr(base) - cagr(m); bdd = fastbt.metrics(base, [])["max_drawdown"]; bsh = fastbt.metrics(base, [])["sharpe"]
        print(f"\n=== {name}: shock trigger grid — no rule: excess {b0:+.1%}, DD {bdd:.1%}, Sharpe {bsh:.2f}; cells show excess (cost vs no rule) | DD | Sharpe | IS/OOS excess")
        rows = []
        for thr, look, hold, scale in grid:
            retL = np.array([np.nan] * look + [level[i] / level[i - look] - 1 for i in range(look, n + 1)])[1:]
            retL = np.concatenate([[np.nan], retL[:-1]])
            e = np.ones(n); k = 0
            for i in range(n):
                if retL[i] < thr: k = hold
                e[i] = scale if k > 0 else 1.0; k = max(0, k - 1)
            rr = e * (0.5 * r_dip + 0.5 * r_mom)
            c = np.concatenate([[1.0], np.cumprod(1 + rr)]); mm = fastbt.metrics(c, [])
            rows.append((thr, look, hold, scale, mm["cagr"] - cagr(m), mm["max_drawdown"], mm["sharpe"], cagr(c[:ks+1]) - cagr(m[:ks+1]), cagr(c[ks:]) - cagr(m[ks:]), float(np.mean(e < 1))))
        print(f"{'thr':>5} {'look':>4} {'hold':>4} {'scale':>5} | {'excess':>7} {'cost':>6} | {'DD':>6} | {'Sharpe':>6} | {'IS':>6} {'OOS':>6} | de-risked")
        for thr, look, hold, scale, ex, mdd, sh, is_, oos, t in rows:
            print(f"{thr:+5.0%} {look:4d} {hold:4d} {scale:5.2f} | {ex:+7.1%} {ex-b0:+6.1%} | {mdd:6.1%} | {sh:6.2f} | {is_:+6.1%} {oos:+6.1%} | {t:4.0%}")
        exs = [x[4] - b0 for x in rows]; dds = [x[5] for x in rows]; shs = [x[6] for x in rows]
        print(f"summary {name}: return cost median {np.median(exs):+.1%} [{min(exs):+.1%} … {max(exs):+.1%}]; DD median {np.median(dds):.1%} (no rule {bdd:.1%}); Sharpe median {np.median(shs):.2f} (no rule {bsh:.2f}); cells with Sharpe > no-rule: {sum(1 for x in shs if x > bsh)}/{len(shs)}; cells with return cost > 1 pp: {sum(1 for x in exs if x < -0.01)}/{len(exs)}")


if __name__ == "__main__":
    if "--grid" in sys.argv:
        shock_grid()
    else:
        main()
