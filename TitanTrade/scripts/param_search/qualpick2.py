"""The quality stage 2 — the value-weighted picks and the mega-cap confound (Decision 076 addendum, 2026-10-30).

Stage 1 (Decision 076) closed the equal-weight sleeve and left one reference line open: the top 50 / top 30 by
operating profitability, weighted by market value, beat SPY by +1.8 … +3.0 pp/yr over 2017 → 2026, three of four cells
in both halves. The suspicion, written before this run: a profitability ratio over *book equity* ranks the buyback
giants first (a company that has retired most of its equity shows an enormous ratio), so "the most profitable,
weighted by size" may be "the decade's largest winners" wearing a quality label. This stage answers that one
question with the data already in hand (the stage-1 pipeline: the point-in-time S&P 500 2016 →, the SEC filings with
their dates, shares outstanding; French RMW; SPMO). Window, anchors, costs and benchmarks as in stage 1.

Checks, fixed before the first run:
  T1  the confound measured: each weighted pick line's daily excess over SPY regressed on SPMO's excess (the decade's
      leaders), on a size tilt (the value-weighted minus the equal-weight hold of the scored set: big minus small
      inside the universe) and on French RMW (quality); the alpha that is left, with its t; and what the portfolio
      holds — the ten largest weights at the last rebalance and the share of the top five, averaged over the
      rebalances.
  T2  the confound removed by construction, three ways, all three reported, none chosen afterwards:
      (a) weights capped at 5 % per name (the excess redistributed to the rest, as a diversified index rule does);
      (b) the ranking done *within size quintiles* of the eligible names, ten picks per quintile (the Fama–French
          construction, which is where the century's +1.2 comes from), equal- and value-weighted;
      (c) a denominator buybacks cannot shrink: operating profitability over total assets, with the stage-1
          coverage (the gross-profitability definition scored only 200–280 names, a different and smaller universe,
          which is part of why it collapsed out of sample — that comparison is made on the common names).
  T3  the giants without the label: the fifty largest names by market value, value-weighted, no profitability at
      all, over the same window — the size-only control the weighted picks must beat.
  T4  the walk-forward on the weighted family (N 30 / 50 × anchor × raw / capped / within-size × OP / OP-over-
      assets): the cell chosen by in-sample excess over SPY and its out-of-sample excess, and the reverse; the
      family reading first.
  T5  the sleeve with the variant named *now*: the top 50 by OP, July, value-weighted and capped at 5 % (what a
      sleeve would plausibly trade) — dip 20 / SPMO 60 / picks 20 and dip 40 / SPMO 40 / picks 20 against the book
      over the same window (both halves and through 2025 better, Sharpe no lower); the within-size value-weighted
      top 50 as the secondary.
  T6  the dust floor with capped weights at $25k and $100k (the smallest position in a 20 % sleeve), the turnover.

Expected, written first (prior 30 % that it is quality): T1 — the SPMO loading +0.3 … +0.5 and the size loading
+0.3 … +0.6, both with t > 5, the RMW loading +0.1 … +0.3, the alpha left +0 … +1 pp/yr with t < 2; the top five
names a third or more of the top-30 portfolio and the usual giants. T2 — the 5 % cap halves the excess (+0.5 …
+1.5 vs SPY); within-size ranking +0 … +1; over assets −0.5 … +1. T3 — the largest fifty beat SPY by +1 … +2 this
decade on their own. T4 — the OP family walks forward, the within-size cells do not. T5 — the capped sleeve costs
the book 0 … 0.5 pp/yr and fails the bar.

Drop rules, written first:
  - a Decision is proposed only if (i) the alpha after SPMO and the size tilt is positive with t > 2 *or* the
    within-size value-weighted top 50 beats SPY in both halves, *and* (ii) the pre-named sleeve (T5) beats the book
    in both halves and through 2025 with a Sharpe no lower — then the proposal is the capped value-weighted picks as
    the vehicle, the slot from the dip sleeve, the build, a new clean window, never applied without the operator's go,
    and the paid long-history confirmation becomes worth buying;
  - otherwise the weighted picks were the decade's leaders: the quality door closes on free data for good, the paid
    extension is not bought, and the knowledge (a buyback-shrunk denominator is a size ranking) is kept.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/qualpick2.py
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402
import screens  # noqa: E402
from intl import rets  # noqa: E402
from putwrite import cut, fmt, hdr, score  # noqa: E402
from quality_etfs import ols  # noqa: E402
from qualpick import FACTS, annual_records, cap_matrix, scores_for  # noqa: E402

CAP = 0.05
THROUGH, SPLIT = "2025-12-31", "2022-01-01"
EXT = "external/french"


def score_opa(rec):
    """The operating-profitability chain over total assets instead of book equity."""
    a = rec.get("assets")
    if not a or a <= 0:
        return np.nan
    rev, cogs, sga, it, oi, ni = (rec.get(k) for k in ("rev", "cogs", "sga", "int", "oi", "ni"))
    if rev is not None and cogs is not None and sga is not None:
        return (rev - cogs - sga - (it or 0.0)) / a
    if oi is not None:
        return oi / a
    return ni / a if ni is not None else np.nan


def matrix(mkt, recs, rebs, fn):
    T, N = mkt.names.shape; M = np.full((T, N), np.nan)
    for t in rebs:
        D = mkt.dates[t]; cutoff = (datetime.date.fromisoformat(D) - datetime.timedelta(days=548)).isoformat()
        for j, s in enumerate(mkt.name_list):
            r = recs.get(s)
            if not r:
                continue
            ends = [e for e, v in r.items() if v["filed"] < D and e >= cutoff]
            if ends:
                M[t, j] = fn(r[max(ends)])
    return M


def capped(w, cap=CAP):
    w = w / w.sum()
    for _ in range(60):
        over = w > cap + 1e-12
        if not over.any():
            break
        excess = (w[over] - cap).sum(); w[over] = cap; under = ~over
        if not under.any():
            break
        w[under] += excess * w[under] / w[under].sum()
    return w


def main():
    mkt, member = screens.load_universe(); dates = mkt.dates; P = mkt.names; T, N = P.shape
    recs, shares = {}, {}
    for s in mkt.name_list:
        p = f"{FACTS}/{s}.json"
        if os.path.exists(p):
            facts = json.load(open(p))["facts"]; recs[s] = annual_records(facts)
            shares[s] = [{"val": float(r["val"]), "filed": r["filed"]} for r in facts.get("EntityCommonStockSharesOutstanding", []) if r.get("val") and r.get("filed")]
    rebs = {a: [i for i in screens.rebalance_dates(dates, "Y", a) if dates[i] >= "2017-01-01"] for a in (7, 1)}
    caps = {a: cap_matrix(mkt, shares, rebs[a]) for a in (7, 1)}
    S = {(a, "OP"): matrix(mkt, recs, rebs[a], lambda r: scores_for(r, "OP")) for a in (7, 1)}
    S.update({(a, "OPA"): matrix(mkt, recs, rebs[a], score_opa) for a in (7, 1)})
    elig = {a: {t: member[t] & ~np.isnan(P[t]) & ~np.isnan(P[t - 252]) for t in rebs[a]} for a in (7, 1)}

    def picks_raw(a, dfn, n):
        out = {}
        for t in rebs[a]:
            sc = np.where(elig[a][t], S[(a, dfn)][t], -np.inf); sc = np.where(np.isnan(sc), -np.inf, sc)
            o = np.argsort(-sc, kind="stable")[:n]; out[t] = o[np.isfinite(sc[o])]
        return out

    def picks_within_size(a, dfn, n):
        per = n // 5; out = {}
        for t in rebs[a]:
            ok = elig[a][t] & ~np.isnan(S[(a, dfn)][t]) & np.isfinite(caps[a][t]) & (caps[a][t] > 0); idx = np.nonzero(ok)[0]
            if len(idx) < 5 * per:
                out[t] = idx; continue
            q = np.quantile(caps[a][t][idx], [0.2, 0.4, 0.6, 0.8]); bucket = np.searchsorted(q, caps[a][t][idx]); chosen = []
            for b in range(5):
                ib = idx[bucket == b]; chosen.extend(ib[np.argsort(-S[(a, dfn)][t][ib], kind="stable")[:per]].tolist())
            out[t] = np.array(chosen)
        return out

    def picks_largest(a, n):
        out = {}
        for t in rebs[a]:
            c = np.where(elig[a][t] & np.isfinite(caps[a][t]), caps[a][t], -np.inf); o = np.argsort(-c, kind="stable")[:n]; out[t] = o[np.isfinite(c[o])]
        return out

    def run(a, picks, weighting):
        """weighting: 'EW' | 'VW' | 'CAP' (value-weighted, capped at 5 %); returns daily returns, SPY returns, dates, turnover, the weight matrix used."""
        PM = np.full((T, N), np.nan); W = np.full((T, N), np.nan)
        for t, p in picks.items():
            PM[t, p] = 1.0
            if weighting != "EW" and len(p):
                c = caps[a][t][p]; c = np.where(np.isfinite(c) & (c > 0), c, np.nanmedian(np.where(c > 0, c, np.nan)) if np.any(c > 0) else 1.0)
                W[t, p] = capped(c.astype(float)) if weighting == "CAP" else c / c.sum()
        c, spyc, d, to = screens.simulate(mkt, member, None, 10 ** 6, "Y", 2017, a, score_matrix=PM, weights=None if weighting == "EW" else W)
        return c[1:] / c[:-1] - 1, spyc[1:] / spyc[:-1] - 1, d, to, W

    # ---------------- the lines ----------------
    f5 = datasets.french_factors("F-F_Research_Data_5_Factors_2x3_daily.csv", EXT); rmw = f5["RMW"]
    dec, _ = carry.sets(); _, dd, spy_lvl, rd, bear_d, _, _ = dec; e_d = carry.exposure(bear_d, master.shock_flags(spy_lvl, -0.07, 10, 20))
    spmo_map = dict(zip(dd[1:], rd["mom"])); spy_map = dict(zip(dd[1:], rd["mkt"]))
    results = {}
    for a in (7, 1):
        allp = {t: np.nonzero(elig[a][t] & ~np.isnan(S[(a, "OP")][t]))[0] for t in rebs[a]}
        lines = {"VW of the scored set (ref)": run(a, allp, "VW"), "EW of the scored set (ref)": run(a, allp, "EW"), "largest 50 by market value, VW (T3, no profitability)": run(a, picks_largest(a, 50), "VW"),
                 "top 50 OP, VW raw (stage 1's line)": run(a, picks_raw(a, "OP", 50), "VW"), "top 30 OP, VW raw": run(a, picks_raw(a, "OP", 30), "VW"),
                 "top 50 OP, VW capped 5 % (T2a)": run(a, picks_raw(a, "OP", 50), "CAP"), "top 30 OP, VW capped 5 %": run(a, picks_raw(a, "OP", 30), "CAP"),
                 "top 50 OP within size quintiles, EW (T2b)": run(a, picks_within_size(a, "OP", 50), "EW"), "top 50 OP within size quintiles, VW": run(a, picks_within_size(a, "OP", 50), "VW"),
                 "top 50 OP within size quintiles, VW capped": run(a, picks_within_size(a, "OP", 50), "CAP"),
                 "top 50 OP / assets, VW raw (T2c)": run(a, picks_raw(a, "OPA", 50), "VW"), "top 50 OP / assets, VW capped": run(a, picks_raw(a, "OPA", 50), "CAP"), "top 50 OP / assets, EW": run(a, picks_raw(a, "OPA", 50), "EW")}
        d = lines["VW of the scored set (ref)"][2]; rs = lines["VW of the scored set (ref)"][1]; vws = lines["VW of the scored set (ref)"][0]; ews = lines["EW of the scored set (ref)"][0]
        spmo = np.array([spmo_map.get(t, np.nan) for t in d[1:]]); spmo = np.nan_to_num(spmo)
        print(f"\n=== anchor {a} ({d[0]} → {d[-1]}): the weighted lines vs SPY; '→2025' through 2025-12-31; 'vs VWs' = excess over the value-weighted hold of the scored set")
        print(hdr(False).replace("| roll3", "| roll3 | →2025 | vs VWs | turnover"))
        print(fmt("SPMO held (ref)", score(spmo, rs, d, SPLIT), None) + f" | {score(spmo, rs, d, SPLIT, through=THROUGH)['excess']:+6.2%} |        |")
        results[a] = {"_d": d}
        for label, (r, _, _, to, W) in lines.items():
            s = score(r, rs, d, SPLIT); t2 = score(r, rs, d, SPLIT, through=THROUGH); v = score(r, vws, d, SPLIT)
            print(fmt(label, s, None) + f" | {t2['excess']:+6.2%} | {v['excess']:+6.2%} | {to:3.0%}/yr"); results[a][label] = (r, s, t2, W, to)
        # T1: the confound measured
        print(f"--- T1, anchor {a}: daily excess over SPY on SPMO's excess, the size tilt (VW − EW of the scored set) and French RMW; alpha in pp/yr, t in brackets; then without RMW")
        print(f"{'line':52} {'β SPMO':>7} {'β size':>7} {'β RMW':>6} {'α':>7} {'R²':>5} | {'β SPMO':>7} {'β size':>7} {'α':>7}")
        size = vws - ews
        for label in ("top 50 OP, VW raw (stage 1's line)", "top 30 OP, VW raw", "top 50 OP, VW capped 5 % (T2a)", "top 50 OP within size quintiles, VW", "top 50 OP / assets, VW raw (T2c)", "largest 50 by market value, VW (T3, no profitability)"):
            r = results[a][label][0]; y = r - rs; idx = [k for k, t in enumerate(d[1:]) if t in rmw]; xr = np.array([rmw[d[1:][k]] for k in idx])
            b3, t3 = ols(y[idx], [spmo[idx] - rs[idx], size[idx], xr]); b2, t2_ = ols(y, [spmo - rs, size])
            yhat = np.column_stack([np.ones(len(idx)), spmo[idx] - rs[idx], size[idx], xr]) @ b3; r2 = 1 - np.var(y[idx] - yhat) / np.var(y[idx])
            results[a][label] = results[a][label] + ((b2[0] * 252, t2_[0]),)
            print(f"{label:52} {b3[1]:+7.2f} {b3[2]:+7.2f} {b3[3]:+6.2f} {b3[0] * 252:+6.1%} ({t3[0]:+4.1f}) {r2:5.2f} | {b2[1]:+7.2f} {b2[2]:+7.2f} {b2[0] * 252:+6.1%} ({t2_[0]:+4.1f})")
        # holdings
        for label, n in (("top 30 OP, VW raw", 30), ("top 50 OP, VW raw (stage 1's line)", 50), ("top 50 OP, VW capped 5 % (T2a)", 50)):
            W = results[a][label][3]; shares5 = []
            for t in rebs[a]:
                w = W[t]; w = w[np.isfinite(w)]
                if len(w): shares5.append(np.sort(w)[::-1][:5].sum() / w.sum())
            t = rebs[a][-1]; w = W[t]; top = np.argsort(-np.nan_to_num(w, nan=-1))[:10]
            print(f"  {label}: top-5 weight share averaged over the rebalances {np.mean(shares5):.0%}; at {dates[t]}: " + ", ".join(f"{mkt.name_list[j]} {w[j]:.0%}" for j in top if np.isfinite(w[j])))

    # ---------------- T4: the walk-forward on the weighted family ----------------
    print("\n=== T4 — the weighted family: N × anchor × weighting × definition, excess vs SPY (full / IS / OOS), and the walk-forward of the selection")
    cells = []
    for a in (7, 1):
        for dfn in ("OP", "OPA"):
            for n in (50, 30):
                for wname, pk in (("VW", "raw"), ("CAP", "raw"), ("VW", "within")):
                    p = picks_raw(a, dfn, n) if pk == "raw" else picks_within_size(a, dfn, n)
                    r, rs_, d_, to, _ = run(a, p, wname); s = score(r, rs_, d_, SPLIT)
                    cells.append(dict(N=n, anchor=a, weighting=f"{wname}-{pk}", definition=dfn, excess=s["excess"], is_=s["is"], oos=s["oos"], sharpe=s["sharpe"]))
                    print(f"  N {n:2d} anchor {a:2d} {wname}-{pk:6} {dfn:3} | {s['excess']:+6.2%} ({s['is']:+5.1%} / {s['oos']:+5.1%}) Sharpe {s['sharpe']:4.2f}")
    for dim in ("definition", "weighting", "N", "anchor"):
        print(f"  marginal on {dim}: " + ", ".join(f"{v}: {np.median([c['excess'] for c in cells if c[dim] == v]):+.2%}" for v in sorted({c[dim] for c in cells}, key=str)))
    bi = max(cells, key=lambda c: c["is_"]); bo = max(cells, key=lambda c: c["oos"])
    print(f"  pick by IS → N {bi['N']} anchor {bi['anchor']} {bi['weighting']} {bi['definition']} (IS {bi['is_']:+.1%}) → OOS {bi['oos']:+.1%} (median OOS {np.median([c['oos'] for c in cells]):+.1%}); pick by OOS → N {bo['N']} anchor {bo['anchor']} {bo['weighting']} {bo['definition']} (OOS {bo['oos']:+.1%}) → IS {bo['is_']:+.1%} (median IS {np.median([c['is_'] for c in cells]):+.1%}); positive in both halves {sum(c['is_'] > 0 and c['oos'] > 0 for c in cells)} of {len(cells)}")

    # ---------------- T5: the sleeve with the pre-named variants ----------------
    print("\n=== T5 — the sleeve, vs SPY, the book over the same window as the bar (both halves and through 2025 better, Sharpe no lower)")
    print(hdr(False).replace("| roll3", "| roll3 | →2025"))
    ok_t5 = {}
    for label in ("top 50 OP, VW capped 5 % (T2a)", "top 50 OP within size quintiles, VW"):
        rq = results[7][label][0]; d7 = results[7]["_d"]; qmap = dict(zip(d7[1:], rq)); first = d7[0]
        dq = np.nan_to_num(np.array([qmap.get(t, np.nan) for t in dd[1:]]))
        dcut, rs = cut(dd, {"dip": rd["dip"], "mom": rd["mom"], "spy": rd["mkt"], "q": dq, "e": e_d}, first, dd[-1]); ee, dip, mom, spy, q = rs["e"], rs["dip"], rs["mom"], rs["spy"], rs["q"]
        sb = score(ee * (0.4 * dip + 0.6 * mom), spy, dcut, SPLIT); tb = score(ee * (0.4 * dip + 0.6 * mom), spy, dcut, SPLIT, through=THROUGH)
        print(fmt(f"the book, {dcut[0]} →", sb, None) + f" | {tb['excess']:+6.2%}")
        for sub, core in ((f"dip 20 / SPMO 60 / [{label}] 20", 0.2 * dip + 0.6 * mom + 0.2 * q), (f"dip 40 / SPMO 40 / [{label}] 20", 0.4 * dip + 0.4 * mom + 0.2 * q)):
            s = score(ee * core, spy, dcut, SPLIT); t2 = score(ee * core, spy, dcut, SPLIT, through=THROUGH); print(fmt(sub, s, None) + f" | {t2['excess']:+6.2%}")
            ok_t5[sub] = s["is"] > sb["is"] and s["oos"] > sb["oos"] and t2["excess"] > tb["excess"] and s["sharpe"] >= sb["sharpe"]

    # ---------------- T6: the dust floor ----------------
    W = results[7]["top 50 OP, VW capped 5 % (T2a)"][3]; mins = []
    for t in rebs[7]:
        w = W[t]; w = w[np.isfinite(w)]
        if len(w): mins.append(w.min())
    print(f"\n=== T6 — the dust floor: the smallest capped weight in the top 50 is {np.min(mins):.2%} … median {np.median(mins):.2%} of the sleeve → {0.2 * np.median(mins) * 25000:.0f} $ at $25k and {0.2 * np.median(mins) * 100000:.0f} $ at $100k for a 20 % sleeve (floor $500); "
          f"turnover {results[7]['top 50 OP, VW capped 5 % (T2a)'][4]:.0%}/yr capped, {results[7]['top 50 OP within size quintiles, VW'][4]:.0%}/yr within-size")

    # ---------------- the verdict ----------------
    a2 = results[7]["top 50 OP, VW raw (stage 1's line)"][5]; a2c = results[7]["top 50 OP, VW capped 5 % (T2a)"][5]; a2w = results[7]["top 50 OP within size quintiles, VW"][5]
    sw = results[7]["top 50 OP within size quintiles, VW"][1]; s3 = results[7]["largest 50 by market value, VW (T3, no profitability)"][1]
    print("\n=== pre-registered verdict (July anchor)")
    print(f"  T1 alpha after SPMO and the size tilt: raw top 50 {a2[0]:+.1%} (t {a2[1]:+.1f}), capped {a2c[0]:+.1%} (t {a2c[1]:+.1f}), within-size {a2w[0]:+.1%} (t {a2w[1]:+.1f}) → {'positive with t > 2' if any(x[0] > 0 and x[1] > 2 for x in (a2, a2c, a2w)) else 'no alpha survives'}")
    print(f"  T2b within-size VW top 50 vs SPY: {sw['excess']:+.2%} ({sw['is']:+.1%} / {sw['oos']:+.1%}) → {'both halves' if sw['is'] > 0 and sw['oos'] > 0 else 'not both halves'}; T3 the largest 50 by size alone: {s3['excess']:+.2%} ({s3['is']:+.1%} / {s3['oos']:+.1%})")
    print("  T5 the sleeve: " + "; ".join(f"{k}: {'ok' if v else 'no'}" for k, v in ok_t5.items()))
    cond1 = any(x[0] > 0 and x[1] > 2 for x in (a2, a2c, a2w)) or (sw["is"] > 0 and sw["oos"] > 0)
    print(f"  → {'DECISION PROPOSED' if cond1 and any(ok_t5.values()) else ('the premium survives the confound but the sleeve does not improve the book — recorded' if cond1 else 'the weighted picks were the decade’s leaders — the quality door closes on free data')}")


if __name__ == "__main__":
    main()
