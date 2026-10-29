"""Three dip-sleeve tests the operator chose from the brainstorm (Decision 068 addendum, 2026-10-29): a quality short
list without hindsight (--dow), the dip measured relative to SPY (--relative), and a filter against fast dips (--gap).
Live rule throughout (dip 8 % / 90 d / SMA150 / 60 d / +20 % / −12 %, insurance ×0.5), judged vs SPY and vs the
equal-weight hold of the same universe, IS / OOS halves (decade split 2022, century split 1990), costs 0.05 % a side.
Universes: A the curated 15 (hindsight), D the 11 sector ETFs (the hindsight-free floor), E the point-in-time
S&P 500 (membership mask), F the 49 French industries 1927 →. Pre-registered hypotheses, written before any result:

--dow  (brainstorm #31)  The curated list's edge is "a short list of large, established names" (Decision 065: a small
       edge on a short list of quality names, adverse selection on a long list of anything). The Dow 30 with its actual
       2016 → 2026 membership (public record, a handful of changes) is such a list chosen without hindsight.
  D1   the dip rule on the point-in-time Dow 30 beats SPY in both halves and beats the sector floor (D);
  D2   it beats most of 20 random 30-name subsets of the 2016 S&P 500 (same engine, S&P membership mask) — the placebo
       for "is a short list of big names special, or any short list?"; if the Dow sits inside the placebo spread the
       curated list's +4 is not "quality", it is the list;
  D3   5 × 15 % slots do no better than 3 × 25 % on 30 names (Decision 065: 3 concentrated slots suit ≤ ~20 names).
--relative  (brainstorm #4)  A name 8 % below its 90-day high *relative to SPY* fell on its own; a name that fell with
       the market is a market dip, which the insurance and the shock trigger already handle.
  R1   the relative dip is not worse than the absolute one on D and F (the hindsight-free pair) in both halves;
  R2   on E it repairs part of the adverse selection (the −0.2 … −10 of the broad universe);
  R3   requiring both (absolute and relative) trades less and is no better — the relative signal is the information.
--gap  (brainstorm #5)  A dip made in one or two sessions is news (an earnings miss, a guidance cut: Bernard–Thomas
       drift) and keeps falling; a grinding dip is noise and reverts. `dip_max` tested the *size* of the fall, not its
       speed.
  G1   excluding names with a single-session fall worse than −X % in the last 20 sessions (X = 5 / 8 / 12) raises the
       median trade and cuts stops on E, where the median trade ends at the stop;
  G2   on A / D / F the filter changes little (±0.5) — ETFs and industries do not gap;
  G3   "the dip is at least K sessions old" (K = 5 / 10) is the same information, weaker.
  Drop rule for both filters: not positive in both halves on D and F, or no plateau across X (a single good cell is
  the 8–20 % band again).
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/dipfilters.py --dow | --relative | --gap
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import dynamic_universe as du  # noqa: E402
import fastbt  # noqa: E402
import screens  # noqa: E402

LIVE = du.LIVE
START, SPLIT = "2017-01-03", "2022-01-01"
# The DJIA on 2016-01-04 and every change since, from the public record (none known after 2024-11-08 as of mid-2026).
DOW_2016 = ["AAPL", "AXP", "BA", "CAT", "CSCO", "CVX", "DD", "DIS", "GE", "GS", "HD", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
            "MRK", "MSFT", "NKE", "PFE", "PG", "TRV", "UNH", "UTX", "V", "VZ", "WMT", "XOM"]
DOW_CHANGES = [("2017-09-01", "DD", "DWDP"), ("2018-06-26", "GE", "WBA"), ("2019-04-02", "DWDP", "DOW"), ("2020-04-03", "UTX", "RTX"),
               ("2020-08-31", "XOM", "AMGN"), ("2020-08-31", "PFE", "HON"), ("2020-08-31", "RTX", "CRM"), ("2024-02-26", "WBA", "AMZN"),
               ("2024-11-08", "INTC", "NVDA"), ("2024-11-08", "DOW", "SHW")]


def sp_market(symbols):
    have = [s for s in symbols if os.path.exists(f"{datasets.S}/alpaca_hist/sp500_2016/{s}.json")]
    return fastbt.Market(datasets.alpaca("SPY"), {s: datasets.alpaca(s, "sp500_2016") for s in have}, {s: datasets.alpaca(s) for s in datasets.SECT}), have


def dow_mask(mkt):
    T = len(mkt.dates); idx = {s: j for j, s in enumerate(mkt.name_list)}
    m = np.zeros((T, len(mkt.name_list)), dtype=bool)
    for s in DOW_2016:
        if s in idx: m[:, idx[s]] = True
    for date, out, inn in DOW_CHANGES:
        a = np.searchsorted(mkt.dates, date)
        if out in idx: m[a:, idx[out]] = False
        if inn in idx: m[a:, idx[inn]] = True
    return m


def dow():
    mkt, have = sp_market(sorted(set(DOW_2016) | {inn for _, _, inn in DOW_CHANGES}))
    mask = dow_mask(mkt)
    cover = {s: int((~np.isnan(mkt.names[:, j]) & mask[:, j]).sum()) for j, s in enumerate(mkt.name_list)}
    thin = [f"{s} {n}" for s, n in cover.items() if n < 200]
    print(f"=== Dow 30 point-in-time {START} → {mkt.dates[-1]}: {len(have)} names loaded; member-days per name median {int(np.median(list(cover.values())))}" + (f"; thin: {', '.join(thin)}" if thin else ""))
    du.header() if hasattr(du, "header") else None
    rows = {}
    rows["A curated 15 (hindsight)"] = du.row("A curated 15 (hindsight)", datasets.load("A_alpaca_names_2016"), LIVE, START, SPLIT)
    rows["D 11 sectors (floor)"] = du.row("D 11 sectors (floor)", datasets.load("D_alpaca_sectors_2016"), LIVE, START, SPLIT)
    E, memb = screens.load_universe()
    du.row("E S&P 500 point-in-time, 3 x 25%", E, {**LIVE, "eligible": memb}, START, SPLIT, mask=memb)
    du.row("Dow 30 point-in-time, 3 x 25%", mkt, {**LIVE, "eligible": mask}, START, SPLIT, mask=mask)
    du.row("Dow 30 point-in-time, 5 x 15%", mkt, {**LIVE, "eligible": mask, "slot_pct": 0.15, "max_slots": 5}, START, SPLIT, mask=mask)
    du.row("Dow 30 point-in-time, insurance off", mkt, {**LIVE, "eligible": mask, "insurance_scale": 1.0}, START, SPLIT, mask=mask)
    # placebo: 20 random 30-name subsets of the 2016-01-04 S&P 500, each under the S&P membership mask
    rng = np.random.default_rng(31)
    pool = [s for s in datasets.sp500_2016_symbols() if os.path.exists(f"{datasets.S}/alpaca_hist/sp500_2016/{s}.json")]
    eidx = {s: j for j, s in enumerate(E.name_list)}
    print("\n--- placebo: 20 random 30-name subsets of the 2016 S&P 500 (S&P membership mask), 3 x 25%")
    ex = []
    for k in range(20):
        sub = sorted(rng.choice(pool, size=30, replace=False))
        m2, _ = sp_market(sub)
        msk = np.column_stack([memb[:, eidx[s]] for s in m2.name_list])
        r = fastbt.run(m2, {**LIVE, "eligible": msk}, START, None)
        ex.append(r["metrics"]["cagr"] - r["spy"]["cagr"])
        print(f"  draw {k + 1:2d}: {ex[-1]:+6.1%}  {' '.join(sub[:8])} …")
    ex = np.array(ex)
    print(f"placebo excess vs SPY: median {np.median(ex):+.1%}, p10 {np.percentile(ex, 10):+.1%}, p90 {np.percentile(ex, 90):+.1%}, share positive {np.mean(ex > 0):.0%}")


def rel_dip_matrix(mkt, lookback=90):
    ratio = mkt.names / mkt.spy[:, None]
    high = np.column_stack([fastbt.Market._col_roll(ratio[:, j], lookback, "max") for j in range(ratio.shape[1])])
    with np.errstate(invalid="ignore", divide="ignore"):
        return (high - ratio) / high


def universes():
    E, memb = screens.load_universe()
    F = datasets.load("F_french_49ind_1926")
    return [("A curated (hindsight)", datasets.load("A_alpaca_names_2016"), None, START, SPLIT),
            ("D sectors (floor)", datasets.load("D_alpaca_sectors_2016"), None, START, SPLIT),
            ("E S&P 500 PIT", E, memb, START, SPLIT),
            ("F 49 industries 1927", F, None, "1927-07-01", "1990-01-01")]


def relative():
    for name, mkt, memb, start, split in universes():
        rel = rel_dip_matrix(mkt)
        base = {**LIVE} if memb is None else {**LIVE, "eligible": memb}
        print(f"\n=== relative dip — {name}")
        du.row("absolute 8% (live)", mkt, base, start, split, mask=memb)
        for thr in (0.06, 0.08, 0.10):
            ok = np.nan_to_num(rel) >= thr
            if memb is not None: ok &= memb
            du.row(f"relative to SPY ≥ {thr:.0%} (ranked by it)", mkt, {**base, "dip_pct": 0.0, "eligible": ok, "rank_matrix": rel}, start, split, mask=memb)
        ok = np.nan_to_num(rel) >= 0.08
        if memb is not None: ok &= memb
        du.row("both: absolute 8% AND relative 8%", mkt, {**base, "eligible": ok, "rank_matrix": rel}, start, split, mask=memb)


def gap():
    for name, mkt, memb, start, split in universes():
        P = mkt.names; T, N = P.shape
        r = np.full((T, N), np.nan); r[1:] = P[1:] / P[:-1] - 1
        worst = np.full((T, N), np.nan)
        from numpy.lib.stride_tricks import sliding_window_view
        with np.errstate(invalid="ignore"):
            worst[19:] = np.nanmin(sliding_window_view(np.nan_to_num(r, nan=0.0), 20, axis=0), axis=-1)   # worst session of the last 20 (today included)
        dip_m = mkt.pre(90, 150, 200)[0]
        base = {**LIVE} if memb is None else {**LIVE, "eligible": memb}
        slots = [("3 x 25%", {})] + ([("10 x 7.5%", {"slot_pct": 0.075, "max_slots": 10})] if name.startswith("E") else [])
        print(f"\n=== fast-dip filter — {name}")
        for slabel, sp in slots:
            du.row(f"live rule, {slabel}", mkt, {**base, **sp}, start, split, mask=memb)
            for x in (0.05, 0.08, 0.12):
                ok = np.nan_to_num(worst, nan=-1.0) > -x
                if memb is not None: ok &= memb
                du.row(f"no session worse than −{x:.0%} in 20, {slabel}", mkt, {**base, **sp, "eligible": ok}, start, split, mask=memb)
            for k in (5, 10):
                old = np.zeros((T, N), dtype=bool); old[k:] = np.nan_to_num(dip_m[:-k]) >= LIVE["dip_pct"]
                if memb is not None: old &= memb
                du.row(f"dip ≥ {k} sessions old, {slabel}", mkt, {**base, **sp, "eligible": old}, start, split, mask=memb)


if __name__ == "__main__":
    if "--dow" in sys.argv: dow()
    if "--relative" in sys.argv: relative()
    if "--gap" in sys.argv: gap()
