"""Rotation sleeves — can a rule rotate the "hedging bit" instead of a hand-picked list? (operator question, 2026-10-27)

The operator's intuition: the curated names look like lucky picks; a rule that rotates among sectors or asset classes,
not necessarily a dip rule, might be the self-correcting second sleeve. Published, hindsight-free families tested as
the second sleeve beside the dip book (dip 40 / sleeve 60, insurance ×0.5, shock trigger — the Decision 067 book with
the sleeve swapped), against the current candidate (SPMO held) and against SPY and the equal-weight universe:
  R1  sector rotation: the 11 SPDRs, top 1 / 2 / 3 by trailing 3 / 6 / 12-month return (last month skipped or not),
      monthly, equal weight; with and without an absolute filter (a sector is held only if its own trailing return > 0,
      otherwise that slot sits in cash at 0 %).
  R2  multi-asset rotation: SPY EFA EEM IWM TLT IEF GLD DBC VNQ LQD HYG — top 3 by 12-month return monthly, absolute
      filter; Faber's GTAA 5 (SPY EFA IEF VNQ DBC, 20 % each, each held while above its 10-month SMA, else cash).
  R3  industry rotation over the century: the 49 French industries, top 5 / 10 by 12-1 and 6-1, monthly, equal weight
      (Moskowitz–Grinblatt), vs the market and as the sleeve vs the top momentum decile.
Costs 0.05 % per side on turnover. Pre-registered expectations: sector rotation ≈ SPY ± 2 pp/yr with SPY-like drawdown
and below SPMO (which rotates inside the S&P 500 across ~100 names); multi-asset rotation cuts the drawdown to −15…−20 %
and lags SPY by 3–6 pp/yr in 2017–26 (bonds and commodities lagged); industry momentum +2–4 pp/yr gross over the century
with momentum-crash years; the value of rotation is drawdown, not return, and none is positive in both halves on return.
Decade split 2022-01-01; century split 1975 + four quarter-centuries; through-2025 beside full.
Run: uv run --with numpy python -I scripts/param_search/rotation.py
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402

LIVE = master.LIVE
COST = 0.0005
MULTI = ["SPY", "EFA", "EEM", "IWM", "TLT", "IEF", "GLD", "DBC", "VNQ", "LQD", "HYG"]
ERAS = [("1927-07-01", "1950-01-01"), ("1950-01-01", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]


def month_starts(dates):
    return [i for i in range(1, len(dates)) if dates[i][:7] != dates[i - 1][:7]]


def rotate(P, dates, form, skip, top, absolute, start_i):
    """Monthly top-`top` by trailing `form`-session return ending `skip` sessions ago; returns daily sleeve returns from start_i."""
    T, N = P.shape; R = P[1:] / P[:-1] - 1
    w = np.zeros(N); out = np.zeros(T - 1); rebs = set(month_starts(dates))
    for t in range(start_i, T - 1):
        if t in rebs:
            with np.errstate(all="ignore"):
                score = P[t - skip] / P[t - skip - form] - 1
            score = np.where(np.isnan(score) | np.isnan(P[t]), -np.inf, score)
            order = np.argsort(-score, kind="stable")[:top]
            pick = [j for j in order if np.isfinite(score[j]) and (not absolute or score[j] > 0)]
            new = np.zeros(N)
            if pick:
                new[pick] = 1.0 / top
            turnover = np.abs(new - w).sum() / 2
            out[t] -= COST * 2 * turnover
            w = new
        r = R[t]; ok = ~np.isnan(r)
        out[t] += (w[ok] * r[ok]).sum()
        w = w * np.where(ok, 1 + r, 1.0)                     # drift between rebalances
        if w.sum() > 0:
            pass
    return out


def faber(P, dates, start_i):
    """GTAA 5: equal weight, each asset held while above its 10-month SMA at the month start, else cash."""
    T, N = P.shape; R = P[1:] / P[:-1] - 1; out = np.zeros(T - 1); rebs = set(month_starts(dates)); held = np.zeros(N, dtype=bool)
    ms = month_starts(dates)
    for t in range(start_i, T - 1):
        if t in rebs:
            k = ms.index(t); prior = [ms[j] for j in range(max(0, k - 10), k)]
            if len(prior) == 10:
                sma = np.nanmean(P[prior], axis=0); new = P[t] > sma
                out[t] -= COST * 2 * (new != held).sum() / N
                held = new
        r = np.where(np.isnan(R[t]), 0.0, R[t])
        out[t] += (held * r).sum() / N
    return out


def score_line(label, r, r_mkt, dates, split, eras=None, to=None):
    if to:
        n = sum(1 for d in dates[1:] if d <= to); r, r_mkt, dates = r[:n], r_mkt[:n], dates[:n + 1]
    s = master.score(r, r_mkt, dates, split, eras)
    tail = f"eras+ {sum(1 for x in s['eras'] if x > 0)}/4 min {s['era_min']:+5.1%}" if eras else f"roll3 {s['roll3_pos']:3.0%}"
    print(f"{label:60} {s['excess']:+6.1%} ({s['is']:+5.1%}/{s['oos']:+5.1%}) DD {s['dd']:6.1%} Sh {s['sharpe']:4.2f} worst {s['worst_year']:+6.1%} {tail}")
    return s


def decade():
    cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index("2017-01-03")
    _, _, spy_above, breadth = cur.pre(90, 150, 200)
    SEC = fastbt.run(sec, LIVE, "2017-01-03", None)["_curve"]; d = dates[i0:]
    def etf(sym):
        v = datasets.alpaca(sym); return np.array([v.get(t, np.nan) for t in dates])
    SP = etf("SPMO"); n = min(len(SEC), len(SP) - i0); d = d[:n]; spy = cur.spy[i0:i0 + n]
    r_dip = SEC[1:n] / SEC[:n - 1] - 1; r_mom = SP[i0 + 1:i0 + n] / SP[i0:i0 + n - 1] - 1; r_mkt = spy[1:] / spy[:-1] - 1
    bear = (master.prev(spy_above[i0:i0 + n][1:]) == 0.0) & (master.prev(breadth[i0:i0 + n][1:]) < 0.5); shock = master.shock_flags(spy, -0.07, 10, 20)
    P_sec = sec.sectors; P_multi = np.column_stack([etf(s) for s in MULTI])
    sleeves = {"SPMO held (current candidate)": r_mom}
    for form, skip, top, absolute in itertools.product((63, 126, 252), (0, 21), (1, 2, 3), (False, True)):
        sleeves[f"sectors top{top} {form // 21}m skip{skip // 21} {'abs' if absolute else 'rel'}"] = rotate(P_sec, dates, form, skip, top, absolute, i0)[i0:i0 + n - 1]
    for form, absolute in ((252, True), (252, False), (126, True)):
        sleeves[f"multi-asset top3 {form // 21}m {'abs' if absolute else 'rel'}"] = rotate(P_multi, dates, form, 21, 3, absolute, i0)[i0:i0 + n - 1]
    sleeves["GTAA 5 (Faber, 10-month SMA)"] = faber(np.column_stack([etf(s) for s in ("SPY", "EFA", "IEF", "VNQ", "DBC")]), dates, i0)[i0:i0 + n - 1]
    ew_sec = np.nanmean(P_sec[i0 + 1:i0 + n] / P_sec[i0:i0 + n - 1] - 1, axis=1); ew_multi = np.nanmean(P_multi[i0 + 1:i0 + n] / P_multi[i0:i0 + n - 1] - 1, axis=1)
    print(f"DECADE 2017-01 → {d[-1]}: sleeves alone vs SPY (IS / OOS), DD, Sharpe, worst year, rolling-3y hit rate; then as the 60 % sleeve beside the 40 % sector dip book (ins x0.5, shock)")
    print(f"{'sleeve alone':60} {'excess':>6} {'(IS/OOS)':>13}")
    score_line("SPY", r_mkt, r_mkt, d, "2022-01-01")
    score_line("EW 11 sectors", ew_sec, r_mkt, d, "2022-01-01"); score_line("EW 11 multi-asset", ew_multi, r_mkt, d, "2022-01-01")
    rows = {}
    for k, rr in sleeves.items():
        rows[k] = score_line(k, rr, r_mkt, d, "2022-01-01")
    print("\n--- marginal effects of the sector-rotation knobs (median excess over the other settings)")
    keys = [k for k in sleeves if k.startswith("sectors")]
    for dim, vals in (("top", ("top1", "top2", "top3")), ("formation", ("3m", "6m", "12m")), ("skip", ("skip0", "skip1")), ("filter", ("abs", "rel"))):
        print(f"  {dim:10}" + " | ".join(f"{v}: {np.median([rows[k]['excess'] for k in keys if f' {v} ' in k + ' ']):+5.1%} (both halves + {np.mean([rows[k]['is'] > 0 and rows[k]['oos'] > 0 for k in keys if f' {v} ' in k + ' ']):3.0%})" for v in vals))
    print("\n--- as the sleeve in the book (dip 40 / sleeve 60, ins x0.5, shock), with the sleeve's excess correlation to the dip book")
    print(f"{'book':60} {'excess':>6} {'(IS/OOS)':>13}")
    picks = ["SPMO held (current candidate)", "sectors top3 12m skip1 rel", "sectors top3 12m skip1 abs", "sectors top1 12m skip1 rel", "sectors top3 6m skip1 abs", "sectors top2 3m skip0 rel",
             "multi-asset top3 12m abs", "multi-asset top3 12m rel", "multi-asset top3 6m abs", "GTAA 5 (Faber, 10-month SMA)"]
    for k in picks:
        rr = master.book(0.4, r_dip, sleeves[k], r_mkt, bear, 0.5, shock, None, False, None)
        corr = np.corrcoef(sleeves[k] - r_mkt, r_dip - r_mkt)[0, 1]
        score_line(f"dip 40 / {k} 60", rr, r_mkt, d, "2022-01-01")
        s2 = master.score(rr[:sum(1 for x in d[1:] if x <= '2025-12-31')], r_mkt[:sum(1 for x in d[1:] if x <= '2025-12-31')], d[:sum(1 for x in d[1:] if x <= '2025-12-31') + 1], "2022-01-01")
        print(f"{'':60}   corr with dip-book excess {corr:+.2f}; through 2025 {s2['excess']:+5.1%}")


def century():
    ind = datasets.load("F_french_49ind_1926"); mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
    r0 = fastbt.run(ind, LIVE, "1927-07-01", None); fd = ind.dates[ind.dates.index(r0["start"]):]; j0 = ind.dates.index(fd[0])
    dip = r0["_curve"]; mk = r0["_spy_curve"]; hi = np.array([mom["Hi PRIOR"].get(x, np.nan) for x in fd])
    r_dip = dip[1:] / dip[:-1] - 1; r_mom = np.nan_to_num(hi[1:] / hi[:-1] - 1); r_mkt = mk[1:] / mk[:-1] - 1
    bear = master.prev(master.sma_above(mk)[1:]) == 0.0; shock = master.shock_flags(mk, -0.07, 10, 20)
    P = ind.names; T = len(fd)
    sleeves = {"top momentum decile held (current century stand-in)": r_mom}
    for form, top in itertools.product((126, 252), (5, 10)):
        sleeves[f"industries top{top} {form // 21}m skip1"] = rotate(P, ind.dates, form, 21, top, False, j0)[j0:j0 + T - 1]
    sleeves["industries top10 12m skip1 abs"] = rotate(P, ind.dates, 252, 21, 10, True, j0)[j0:j0 + T - 1]
    ew = np.nanmean(P[j0 + 1:j0 + T] / P[j0:j0 + T - 1] - 1, axis=1)
    print(f"\n\nCENTURY 1927-07 → {fd[-1]}: industry rotation vs the market; then as the 60 % sleeve beside the dip book")
    print(f"{'sleeve alone':60} {'excess':>6} {'(1927-74/1975-)':>13}")
    score_line("EW 49 industries", ew, r_mkt, fd, "1975-01-01", ERAS)
    for k, rr in sleeves.items():
        score_line(k, rr, r_mkt, fd, "1975-01-01", ERAS)
    print(f"\n{'book':60}")
    for k in sleeves:
        rr = master.book(0.4, r_dip, sleeves[k], r_mkt, bear, 0.5, shock, None, False, None)
        score_line(f"dip 40 / {k} 60", rr, r_mkt, fd, "1975-01-01", ERAS)


if __name__ == "__main__" and "--timing" not in sys.argv:
    decade(); century()


# ---- timing (operator follow-up, 2026-10-27): how often to rotate, and whether a marker beats the calendar -----------------
# Pre-registered hypotheses, written before any result:
#   T1 calendar frequency — century industries: monthly ≈ quarterly > semi-annual > annual, spread ≤ 1.5 pp/yr net of costs;
#      daily re-ranking adds turnover and nothing; decade sectors ≈ 0 at every frequency (too little dispersion among 11).
#   T2 a rank tolerance band (hold while still inside the top 2N, refill from the top N) cuts turnover by about half at
#      about the same excess — the classic result for threshold rebalancing.
#   T3 a trend-break trigger (drop a holding once it is below its 10-month SMA, refill from the top N that are above) is
#      the absolute-momentum filter with hysteresis: lower drawdown, lower return.
#   T4 re-ranking the day after a market shock (−7 % in 10 sessions) adds nothing: the ranking barely moves in ten days,
#      and it rotates into whatever fell least, then misses the rebound.
#   SPMO's own schedule (semi-annual, March / September, set by the index) is not a knob this book holds.

def rotate2(P, dates, form, skip, top, start_i, every=1, anchor=0, band=None, trend=False, shock=None, daily=False):
    """Top-`top` by trailing return; full re-rank on the calendar (`every` months, `anchor`) and/or on triggers; cost 0.05 %/side."""
    T, N = P.shape; R = P[1:] / P[:-1] - 1
    w = np.zeros(N); out = np.zeros(T - 1); turnover = 0.0
    ms = month_starts(dates); mset = set(ms); midx = {t: k for k, t in enumerate(ms)}
    sma10 = np.full(P.shape, np.nan)
    for k in range(10, len(ms)):
        sma10[ms[k]] = np.nanmean(P[ms[k - 10:k]], axis=0)
    last_sma = np.full(N, np.nan)
    for t in range(start_i, T - 1):
        check = daily or t in mset
        if t in mset:
            last_sma = np.where(np.isnan(sma10[t]), last_sma, sma10[t])
        if not check and not (shock is not None and shock[t]):
            r = R[t]; ok = ~np.isnan(r); out[t] += (w[ok] * r[ok]).sum(); w = w * np.where(ok, 1 + r, 1.0); continue
        with np.errstate(all="ignore"):
            score = P[t - skip] / P[t - skip - form] - 1
        score = np.where(np.isnan(score) | np.isnan(P[t]), -np.inf, score)
        order = np.argsort(-score, kind="stable"); rank = np.empty(N, dtype=int); rank[order] = np.arange(N)
        held = w > 0
        full = (t in mset and (midx[t] % every == anchor % every)) or (shock is not None and shock[t]) or (daily and band is None and not trend)
        if full:
            keep = [j for j in order[:top] if np.isfinite(score[j])]
        else:
            keep = [j for j in np.nonzero(held)[0] if np.isfinite(score[j])]
            if band:
                keep = [j for j in keep if rank[j] < band * top]
            if trend:
                keep = [j for j in keep if not (P[t, j] < last_sma[j])]
            for j in order:
                if len(keep) >= top:
                    break
                if j in keep or not np.isfinite(score[j]) or rank[j] >= top or (trend and P[t, j] < last_sma[j]):
                    continue
                keep.append(j)
        new = np.zeros(N)
        if keep:
            new[keep] = 1.0 / top
        wn = w / w.sum() if w.sum() > 0 else w
        to = np.abs(new - wn).sum() / 2; turnover += to; out[t] -= COST * 2 * to
        w = new
        r = R[t]; ok = ~np.isnan(r); out[t] += (w[ok] * r[ok]).sum(); w = w * np.where(ok, 1 + r, 1.0)
    years = (T - 1 - start_i) / 252
    return out, turnover / years


def timing():
    ind = datasets.load("F_french_49ind_1926"); r0 = fastbt.run(ind, LIVE, "1927-07-01", None); fd = ind.dates[ind.dates.index(r0["start"]):]; j0 = ind.dates.index(fd[0])
    dip = r0["_curve"]; mk = r0["_spy_curve"]; r_dip = dip[1:] / dip[:-1] - 1; r_mkt = mk[1:] / mk[:-1] - 1
    bear = master.prev(master.sma_above(mk)[1:]) == 0.0; shock = master.shock_flags(mk, -0.07, 10, 20)
    shock_full = np.zeros(len(ind.dates), dtype=bool); shock_full[j0 + 1:j0 + len(fd)] = shock & ~np.concatenate([[False], shock[:-1]])   # the first day of each shock
    cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index("2017-01-03")
    _, _, spy_above, breadth = cur.pre(90, 150, 200)
    SEC = fastbt.run(sec, LIVE, "2017-01-03", None)["_curve"]; d = dates[i0:]; n = len(SEC); spy = cur.spy[i0:i0 + n]
    r_dip_d = SEC[1:] / SEC[:-1] - 1; r_mkt_d = spy[1:] / spy[:-1] - 1
    bear_d = (master.prev(spy_above[i0:i0 + n][1:]) == 0.0) & (master.prev(breadth[i0:i0 + n][1:]) < 0.5); shock_d = master.shock_flags(spy, -0.07, 10, 20)
    shock_full_d = np.zeros(len(dates), dtype=bool); shock_full_d[i0 + 1:i0 + n] = shock_d & ~np.concatenate([[False], shock_d[:-1]])
    variants = [("monthly (reference)", dict(every=1)), ("daily re-rank", dict(daily=True)), ("quarterly", dict(every=3)), ("semi-annual, Mar/Sep", dict(every=6, anchor=2)), ("semi-annual, Jun/Dec", dict(every=6, anchor=5)),
                ("annual, Jan", dict(every=12, anchor=0)), ("annual, Jul", dict(every=12, anchor=6)),
                ("band: hold while in top 1.5N, monthly check", dict(every=10 ** 6, band=1.5)), ("band: hold while in top 2N", dict(every=10 ** 6, band=2.0)), ("band: hold while in top 3N", dict(every=10 ** 6, band=3.0)),
                ("trend-break: drop below 10-month SMA, refill from top N", dict(every=10 ** 6, trend=True)), ("trend-break + band 2N", dict(every=10 ** 6, band=2.0, trend=True)),
                ("monthly + re-rank on a market shock", dict(every=1, shock="S")), ("quarterly + re-rank on a market shock", dict(every=3, shock="S")), ("band 2N, checked daily", dict(every=10 ** 6, band=2.0, daily=True))]
    for name, P, dd, start, r_dip_, r_mkt_, bear_, shock_, sfull, split, eras, top, mom_ref in (
            ("CENTURY 49 industries, top 10 by 12-1", ind.names, fd, j0, r_dip, r_mkt, bear, shock, shock_full, "1975-01-01", ERAS, 10, None),
            ("DECADE 11 sectors, top 3 by 12-1", sec.sectors, d, i0, r_dip_d, r_mkt_d, bear_d, shock_d, shock_full_d, "2022-01-01", None, 3, "SPMO")):
        print(f"\n=== timing — {name}: sleeve alone vs market (IS / OOS), DD, Sharpe, worst year, eras / rolling-3y; turnover; then dip 40 / sleeve 60 book (ins x0.5, shock)")
        print(f"{'variant':60} {'excess':>6} {'(IS/OOS)':>13} {'':>30} {'turnover':>9} | {'book':>6} {'(IS/OOS)':>13} {'DD':>7} {'Sharpe':>6}")
        if mom_ref:
            v = datasets.alpaca(mom_ref); SP = np.array([v.get(t, np.nan) for t in dd]); r_m = SP[1:] / SP[:-1] - 1
            s = master.score(r_m, r_mkt_, dd, split, eras); b = master.score(master.book(0.4, r_dip_, r_m, r_mkt_, bear_, 0.5, shock_, None, False, None), r_mkt_, dd, split, eras)
            print(f"{mom_ref + ' held (index rebalances semi-annually)':60} {s['excess']:+6.1%} ({s['is']:+5.1%}/{s['oos']:+5.1%}) DD {s['dd']:6.1%} Sh {s['sharpe']:4.2f} {'':>13} {'n/a':>9} | {b['excess']:+6.1%} ({b['is']:+5.1%}/{b['oos']:+5.1%}) {b['dd']:7.1%} {b['sharpe']:6.2f}")
        for label, kw in variants:
            kw = dict(kw)
            if kw.get("shock") == "S":
                kw["shock"] = sfull
            rr, to = rotate2(P, ind.dates if name.startswith("CENTURY") else dates, 252, 21, top, start, **kw)
            rr = rr[start:start + len(r_mkt_)]
            s = master.score(rr, r_mkt_, dd, split, eras)
            b = master.score(master.book(0.4, r_dip_, rr, r_mkt_, bear_, 0.5, shock_, None, False, None), r_mkt_, dd, split, eras)
            tail = f"eras+ {sum(1 for x in s['eras'] if x > 0)}/4" if eras else f"roll3 {s['roll3_pos']:3.0%}"
            print(f"{label:60} {s['excess']:+6.1%} ({s['is']:+5.1%}/{s['oos']:+5.1%}) DD {s['dd']:6.1%} Sh {s['sharpe']:4.2f} worst {s['worst_year']:+5.0%} {tail:>9} {to:8.0%}/yr | {b['excess']:+6.1%} ({b['is']:+5.1%}/{b['oos']:+5.1%}) {b['dd']:7.1%} {b['sharpe']:6.2f}")


if __name__ == "__main__" and "--timing" in sys.argv:
    timing()
