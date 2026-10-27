"""Portfolio of sleeves (operator proposal, 2026-10-27): the live dip rule on the curated list + a momentum sleeve on the
S&P 500 + a 10-slot dip rule on the S&P 500, "added together". Every sleeve is a full book (its own SPY residual, the
two-signal insurance), so a weighted blend of sleeve curves is the combined book with the capital split by weight.
Steps: (1) walk-forward the two new rules (train on one half, test on the other, both ways); (2) correlation of the
sleeves' excess returns — the diversification claim; (3) blends, each shown with the hindsight-free sector-ETF sleeve
standing in for the curated list; (4) the same combination over the century on French data.
Run: uv run --with numpy python -I scripts/param_search/combo.py"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402
import screens  # noqa: E402

START, SPLIT = "2017-01-03", "2022-01-01"
LIVE = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12,
            slot_pct=0.25, max_slots=3, insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=0.5)


def cagr(c):
    return fastbt.metrics(c, [])["cagr"]


def halves(dates):
    ks = next(k for k, d in enumerate(dates) if d >= SPLIT)
    return slice(0, ks + 1), slice(ks, len(dates))


def book_from_run(r):
    return r["_curve"] / r["_curve"][0], r["_spy_curve"] / r["_spy_curve"][0]


def guarded_momentum(mkt, member, key, n, anchor, spy_above, breadth):
    """EW momentum sleeve with the live two-signal insurance (×0.5, remainder SPY); curve from its first rebalance."""
    c, spyc, dd, _ = screens.simulate(mkt, member, (lambda f: f[key]), n, "Y", 2017, anchor)
    i0 = mkt.dates.index(dd[0]); rs = c[1:] / c[:-1] - 1; rm = spyc[1:] / spyc[:-1] - 1
    sa = spy_above[i0:i0 + len(c)]; br = breadth[i0:i0 + len(c)]
    e = np.array([0.5 if (sa[i - 1] == 0.0 and br[i - 1] < 0.5) else 1.0 for i in range(1, len(c))])
    return np.concatenate([[1.0], np.cumprod(1 + e * rs + (1 - e) * rm)]), spyc, dd


def describe(label, c, spyc, dates):
    a, b = halves(dates); m = fastbt.metrics(c, []); sp = fastbt.metrics(spyc, [])
    return (f"{label:44} vs SPY {m['cagr']-sp['cagr']:+5.1%} (IS {cagr(c[a])-cagr(spyc[a]):+5.1%} / OOS {cagr(c[b])-cagr(spyc[b]):+5.1%}) "
            f"| DD {m['max_drawdown']:6.1%} vs {sp['max_drawdown']:6.1%} | Sharpe {m['sharpe']:4.2f} vs {sp['sharpe']:4.2f}")


def main():
    mkt, member = screens.load_universe(); dates = mkt.dates
    _, _, spy_above, breadth = mkt.pre(90, 150, 200)
    i_start = dates.index(START)

    # ---- (1) walk-forward: momentum sleeve ------------------------------------------------------------------------
    print("=== (1a) walk-forward of the momentum sleeve rule (window × N × anchor month; guarded; train excess picks the rule)")
    grid = list(itertools.product((("6-1", "mom_6_1"), ("12-1", "mom"), ("12-2", "mom_12_2")), (10, 15, 20), (1, 4, 7, 10)))
    rows = []
    for (wn, key), n, am in grid:
        c, spyc, dd = guarded_momentum(mkt, member, key, n, am, spy_above, breadth)
        a, b = halves(dd)
        rows.append(dict(rule=f"{wn} N={n} anchor {am}", full=cagr(c) - cagr(spyc), tr=cagr(c[a]) - cagr(spyc[a]), te=cagr(c[b]) - cagr(spyc[b]), dd=fastbt.metrics(c, [])["max_drawdown"]))
    for name, trk, tek in (("train 2017-21 → test 2022-26", "tr", "te"), ("train 2022-26 → test 2017-21", "te", "tr")):
        best = max(rows, key=lambda r: r[trk]); med = float(np.median([r[tek] for r in rows]))
        print(f"  {name}: picked {best['rule']} (train {best[trk]:+.1%}) → test {best[tek]:+.1%}; median rule in test {med:+.1%}; rules positive in test {sum(1 for r in rows if r[tek] > 0)}/{len(rows)}")
    print(f"  all 36 rules, full-period excess: median {np.median([r['full'] for r in rows]):+.1%}, min {min(r['full'] for r in rows):+.1%}, max {max(r['full'] for r in rows):+.1%}")

    # ---- (1) walk-forward: broad dip sleeve ----------------------------------------------------------------------
    print("\n=== (1b) walk-forward of the broad dip rule on the S&P 500 membership (slots × dip)")
    rows = []; broad = {}
    for slots, dip in itertools.product((6, 8, 10, 12, 15), (0.08, 0.10)):
        p = dict(LIVE, max_slots=slots, slot_pct=round(0.75 / slots, 4), dip_pct=dip, eligible=member)
        r = fastbt.run(mkt, p, START, None); c, spyc = book_from_run(r); a, b = halves(dates[i_start:])
        rows.append(dict(rule=f"{slots} slots × {0.75/slots:.1%}, dip {dip:.0%}", full=cagr(c) - cagr(spyc), tr=cagr(c[a]) - cagr(spyc[a]), te=cagr(c[b]) - cagr(spyc[b]), dd=fastbt.metrics(c, [])["max_drawdown"]))
        broad[(slots, dip)] = c
        print(f"  {rows[-1]['rule']:28} full {rows[-1]['full']:+5.1%}  IS {rows[-1]['tr']:+5.1%} / OOS {rows[-1]['te']:+5.1%}  DD {rows[-1]['dd']:6.1%}")
    for name, trk, tek in (("train 2017-21 → test 2022-26", "tr", "te"), ("train 2022-26 → test 2017-21", "te", "tr")):
        best = max(rows, key=lambda r: r[trk])
        print(f"  {name}: picked {best['rule']} (train {best[trk]:+.1%}) → test {best[tek]:+.1%}; rules positive in test {sum(1 for r in rows if r[tek] > 0)}/{len(rows)}")

    # ---- sleeves for the combination ----------------------------------------------------------------------------
    cur_mkt = datasets.load("A_alpaca_names_2016"); sec_mkt = datasets.load("D_alpaca_sectors_2016")
    assert cur_mkt.dates[:len(dates)] == dates[:len(cur_mkt.dates)]
    CUR, spyc = book_from_run(fastbt.run(cur_mkt, LIVE, START, None))
    SEC, _ = book_from_run(fastbt.run(sec_mkt, LIVE, START, None))
    BRD = broad[(10, 0.08)]
    MOM, _, _ = guarded_momentum(mkt, member, "mom_6_1", 15, 1, spy_above, breadth)
    MOM12, _, _ = guarded_momentum(mkt, member, "mom", 15, 1, spy_above, breadth)
    n = min(map(len, (CUR, SEC, BRD, MOM, MOM12, spyc))); CUR, SEC, BRD, MOM, MOM12, spyc = (x[:n] for x in (CUR, SEC, BRD, MOM, MOM12, spyc)); dd = dates[i_start:i_start + n]
    sleeves = {"CUR dip on the 15 curated (hindsight)": CUR, "SEC dip on 11 sector ETFs": SEC, "BRD dip on S&P 500, 10 × 7.5%": BRD, "MOM 6-1 N=15 guarded": MOM, "MOM 12-1 N=15 guarded": MOM12}
    print("\n=== sleeves alone (each is a full book: SPY residual + insurance)")
    for k, c in sleeves.items():
        print(describe(k, c, spyc, dd))

    # ---- (2) correlation of excess returns -----------------------------------------------------------------------
    ex = {k: (c[1:] / c[:-1]) - (spyc[1:] / spyc[:-1]) for k, c in sleeves.items()}
    keys = list(ex); M = np.corrcoef(np.array([ex[k] for k in keys]))
    print("\n=== (2) correlation of daily excess returns (vs SPY) between sleeves — the diversification the proposal relies on")
    print(" " * 40 + "".join(f"{k[:9]:>10}" for k in keys))
    for i, k in enumerate(keys):
        print(f"{k:40}" + "".join(f"{M[i, j]:10.2f}" for j in range(len(keys))))

    # ---- (3) blends ----------------------------------------------------------------------------------------------
    print("\n=== (3) combined books (weights over sleeves, daily-rebalanced; the SPY residual lives inside each sleeve)")
    rs = {k: c[1:] / c[:-1] - 1 for k, c in sleeves.items()}
    combos = [("CUR 100%", {"CUR": 1}), ("CUR 50 / MOM 50", {"CUR": .5, "MOM": .5}), ("CUR 50 / BRD 50", {"CUR": .5, "BRD": .5}),
              ("CUR 34 / BRD 33 / MOM 33", {"CUR": .34, "BRD": .33, "MOM": .33}), ("CUR 50 / BRD 25 / MOM 25", {"CUR": .5, "BRD": .25, "MOM": .25}),
              ("CUR 25 / BRD 25 / MOM 50", {"CUR": .25, "BRD": .25, "MOM": .5}), ("BRD 50 / MOM 50", {"BRD": .5, "MOM": .5}), ("MOM 100%", {"MOM": 1}), ("BRD 100%", {"BRD": 1}),
              ("CUR 34 / BRD 33 / MOM12 33", {"CUR": .34, "BRD": .33, "MOM12": .33})]
    full = {"CUR": rs["CUR dip on the 15 curated (hindsight)"], "SEC": rs["SEC dip on 11 sector ETFs"], "BRD": rs["BRD dip on S&P 500, 10 × 7.5%"], "MOM": rs["MOM 6-1 N=15 guarded"], "MOM12": rs["MOM 12-1 N=15 guarded"]}
    for label, w in combos:
        for variant, sub in (("", {}), (" [SEC for CUR]", {"CUR": "SEC"})):
            if variant and "CUR" not in w:
                continue
            r = sum(wt * full[sub.get(k, k)] for k, wt in w.items()); c = np.concatenate([[1.0], np.cumprod(1 + r)])
            print(describe(label + variant, c, spyc, dd))

    # ---- (4) century ---------------------------------------------------------------------------------------------
    print("\n=== (4) century, French data: dip rule on 49 industries (3 slots, insurance) blended with the top momentum decile (held), vs market")
    ind = datasets.load("F_french_49ind_1926"); mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
    r = fastbt.run(ind, LIVE, "1927-07-01", None); dcurve, mcurve = book_from_run(r); fd = ind.dates[ind.dates.index(r["start"]):]
    hi = np.array([mom["Hi PRIOR"].get(d, np.nan) for d in fd]); hi = hi / hi[0]
    ok = ~np.isnan(hi); rd = dcurve[1:] / dcurve[:-1] - 1; rh = np.nan_to_num(hi[1:] / hi[:-1] - 1); rm = mcurve[1:] / mcurve[:-1] - 1
    print(f"  corr(dip excess, momentum excess) over the century: {np.corrcoef(rd - rm, rh - rm)[0, 1]:+.2f}")
    eras = [("1927", "1950"), ("1950", "1975"), ("1975", "2000"), ("2000", "2027"), ("1927", "2027")]
    for label, rr in (("dip on industries", rd), ("momentum Hi decile", rh), ("50 / 50", 0.5 * rd + 0.5 * rh), ("70 dip / 30 mom", 0.7 * rd + 0.3 * rh)):
        line = f"  {label:20}"
        for a, b in eras:
            ks = [k for k in range(len(rr)) if a <= fd[k + 1][:4] < b]
            c = np.cumprod(1 + rr[ks]); m = np.cumprod(1 + rm[ks]); yrs = len(ks) / 252
            line += f" | {a}–{b}: {c[-1]**(1/yrs) - m[-1]**(1/yrs):+5.1%} DD {float((c/np.maximum.accumulate(c)-1).min()):5.0%}/{float((m/np.maximum.accumulate(m)-1).min()):5.0%}"
        print(line)


if __name__ == "__main__":
    main()
