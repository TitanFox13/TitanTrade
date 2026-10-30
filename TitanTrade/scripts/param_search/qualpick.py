"""The quality stage 1 — a self-built held profitability sleeve on free data (Decision 076 research, 2026-10-30).

Decision 075 found the quality premium real for 63 years (the most profitable 30 % of the market +1.2 pp/yr in every
era) and alive this decade (+1.6 … +3.4 vs SPY in the French portfolios), and its addendum found that none of twelve
quality ETFs captures it. The operator: "if the data says it is profitable, diversifies and stands the test of time,
why not do it" — and: free data first. This is the test of the one route left: picking the most profitable companies
ourselves and holding them. The crux is concentration — the French portfolio holds about a thousand names; a sleeve
holds thirty to fifty — and the question is whether our picks keep the premium or lose it the way the funds did.

Data, all free: the S&P 500 point-in-time universe 2016 → 2026 (742 names with the 94 delisted ones, Alpaca SIP,
dividend-adjusted; the daily membership mask from `universes/sp500_ticker_start_end.csv`); every company's annual
statements from the SEC's XBRL ``companyfacts`` API with their filing dates (``external/sec_facts/<TICKER>.json``,
fetched by ``fetch_sec_facts.py``; tickers mapped to CIKs through the SEC's current ticker file — delisted tickers
that do not map are ineligible for picking but stay in the equal-weight universe and in SPY, and their share is
reported); Kenneth French's profitability portfolios as the yardstick over the same window. Prices before 2016 are not
free on Alpaca (Tiingo's free key would extend the window to 2010 — roadmap B11); statements before 2009 are paid
(the roadmap's paid-data group). Window: from the first rebalance in 2017 to 2026-10-12, split 2022-01-01, every
headline through 2025-12-31 beside full.

Design, fixed before the first run:
  - point in time: at each rebalance date the score uses the latest 10-K *filed* before that date (strict), the
    fiscal year it reports being at most 18 months old;
  - profitability: OP = (revenue − cost of sales − SG&A − interest expense) / book equity (Fama–French operating
    profitability; a missing interest expense counts as zero, revenue, cost of sales and equity are required); the
    fallback where cost of sales is not reported (financials) is operating income / equity; firms with negative or
    missing equity are ineligible. Robustness definition: gross profitability = (revenue − cost of sales) / assets
    (Novy-Marx). Revenue, cost and equity are read from the usual tag families in a fixed order;
  - selection: the eligible members ranked by the score; the top N held equal-weight for a year (N = 50 primary,
    30 secondary); "top 30 %" of the eligible set (≈ 150 names) equal-weight is the construct-in-our-data line;
  - rebalance: yearly on the first session of July (French's convention: last year's statements are all filed by
    June) primary, January secondary; costs 0.05 % a side on the turnover (``screens.COST``);
  - benchmarks: SPY; the equal-weight hold of all eligible members rebalanced the same way (the like-for-like
    benchmark — the equal-weight effect alone was −3.9 pp/yr this decade, Decision 066); the French OP Hi 30 vs the
    French market over the same window; placebo = 50 random N-name lists from the same eligible set, re-drawn at
    every rebalance;
  - value-weighted versions (shares outstanding × price) only as a reference, where shares are reported.

Pre-registered hypotheses (the expected numbers were written before the first run):
  S1  the construct exists in our data: the top 30 % by OP, equal-weight, beats the equal-weight universe by +1 … +3
      pp/yr, positive in both halves (the French Hi 30 beat its market by +1.6 over 2017–2026); the bottom 30 % lags
      by 1 … 3 (the test has teeth). If S1 fails the pipeline, not the idea, is the problem.
  S2  concentration keeps the premium: the top-50 equal-weight beats the equal-weight universe by ≥ +0.8 pp/yr (half
      the French premium) in both halves, ranks above the 90th percentile of the 50 random lists on the full period
      and above their median in both halves; the top-30 keeps the sign with more noise (tracking error vs the top
      30 % of 3 … 5 %/yr).
  S3  vs SPY: every equal-weight line lags SPY by 2 … 4 pp/yr this decade (the equal-weight effect), so the honest
      "what we would trade" line — the top-50 equal-weight vs SPY — is expected at −2 … +1; the value-weighted top-50
      vs SPY at −1 … +2.
  S4  the selection rule walks forward: over the 12 cells (N 30 / 50 × anchor January / July × definition OP /
      gross profitability / operating income over equity) the cell chosen by in-sample excess over the equal-weight
      universe is positive out of sample and the reverse; the definition matters more than N or the month, and
      gross profitability ≈ OP.
  S5  the sleeve: dip 20 / SPMO 60 / Q 20 (quality in place of half the dip sleeve, the century near-pass) and
      dip 40 / SPMO 40 / Q 20 with the top-50 equal-weight, against the live book (+1.36; +0.3 / +2.5; Sharpe 1.10;
      through 2025 +0.80): expected −0.5 … +0.5 pp/yr, Sharpe ±0.03 — a pass needs the picks to beat SPY, which S3
      doubts.
  S6  what the sleeve would cost to run, reported: turnover per year, names held, the smallest position at $25k and
      $100k against the $500 dust floor, the share of the universe that could not be mapped to a filer.

Drop rules, written first:
  - S1 fails → stop; the pipeline is wrong or the premium is not in large caps this decade; recorded, parked.
  - S2 fails → no self-built sleeve; the quality door closes on free data and the paid long-history extension is
    not worth buying.
  - S2 passes and S5 fails → recorded: the picks keep the premium and do not improve the book; the paid extension
    stays in the paid group with that note.
  - S2 and S5 pass → a Decision is *proposed* (the picks as the vehicle: N, anchor, definition; the slot taken from
    the dip sleeve; the held-sleeve build; a new clean window) and the long-history confirmation becomes worth
    buying — never applied without the operator's go.
  - Twelve cells and two sleeve variants: the family reading first, the leaderboard never; the luck meter's bootstrap
    on any surviving cell.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/qualpick.py   (after fetch_sec_facts.py)
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

GRID = {"N": (50, 30), "anchor": (7, 1), "definition": ("OP", "GPA", "OIE")}
THROUGH, SPLIT = "2025-12-31", "2022-01-01"
FACTS = f"{datasets.S}/external/sec_facts"
FAM = {"rev": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "RevenuesNetOfInterestExpense"],
       "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices", "CostOfGoodsAndServicesSoldExcludingDepreciationDepletionAndAmortization"],
       "sga": ["SellingGeneralAndAdministrativeExpense"], "int": ["InterestExpense", "InterestExpenseNonoperating"], "oi": ["OperatingIncomeLoss"], "gp": ["GrossProfit"],
       "eq": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"], "assets": ["Assets"], "ni": ["NetIncomeLoss"]}


def annual_records(facts):
    """{fiscal-year end: {field: value, 'filed': first filing date, 'kind': 'OP' | 'OIE' | 'ROE'}} from 10-K rows: for
    each year and field the value as *first reported*, whichever tag of the family carried it then (companies switch
    revenue tags over the years and later 10-Ks restate old years under the new tag — those later rows must not win)."""
    per = {}
    for field, tags in FAM.items():
        for k, tag in enumerate(tags):
            for r in facts.get(tag, []):
                if not str(r.get("form", "")).startswith("10-K") or r.get("fp") not in ("FY", "Q4") or r.get("val") is None or not r.get("filed"):
                    continue   # the SEC labels a 10-K's annual facts "FY" for some filers and "Q4" for others; the duration check below keeps the annual ones
                if r.get("start"):
                    days = (datetime.date.fromisoformat(r["end"]) - datetime.date.fromisoformat(r["start"])).days
                    if not 340 <= days <= 380:
                        continue
                slot = per.setdefault(r["end"], {}); cur = slot.get(field)
                if cur is None or (r["filed"], k) < (cur[1], cur[2]):   # the earliest filing wins; the tag order breaks ties
                    slot[field] = (float(r["val"]), r["filed"], k)
    out = {}
    for end, fields in per.items():
        if "eq" not in fields:
            continue
        out[end] = {k: v[0] for k, v in fields.items()}; out[end]["filed"] = max(v[1] for v in fields.values())
        out[end]["kind"] = "OP" if all(k in fields for k in ("rev", "cogs", "sga")) else "OIE" if "oi" in fields else "ROE" if "ni" in fields else "none"
    return out


def scores_for(rec, definition):
    """OP → operating income / equity → net income / equity (the chain, for filers that report no cost of sales or no
    operating income: banks, insurers, REITs); GPA = gross profit / assets; OIE = the chain without the first step."""
    eq = rec.get("eq"); rev, cogs, sga, it, oi, gp, assets, ni = (rec.get(k) for k in ("rev", "cogs", "sga", "int", "oi", "gp", "assets", "ni"))
    if definition == "GPA":
        if assets and assets > 0 and rev is not None and (cogs is not None or gp is not None):
            return (rev - cogs if cogs is not None else gp) / assets
        return np.nan
    if eq is None or eq <= 0:
        return np.nan
    if definition == "OP" and rev is not None and cogs is not None and sga is not None:
        return (rev - cogs - sga - (it or 0.0)) / eq
    if oi is not None:
        return oi / eq
    return ni / eq if ni is not None else np.nan


def score_matrix(mkt, recs, rebs, definition):
    T, N = mkt.names.shape; M = np.full((T, N), np.nan)
    for t in rebs:
        D = mkt.dates[t]; cutoff = (datetime.date.fromisoformat(D) - datetime.timedelta(days=548)).isoformat()
        for j, s in enumerate(mkt.name_list):
            r = recs.get(s)
            if not r:
                continue
            ends = [e for e, v in r.items() if v["filed"] < D and e >= cutoff]
            if ends:
                M[t, j] = scores_for(r[max(ends)], definition)
    return M


def cap_matrix(mkt, shares, rebs):
    """Market cap (latest reported shares outstanding filed before the date × the close) at the rebalance rows; NaN elsewhere."""
    T, N = mkt.names.shape; W = np.full((T, N), np.nan)
    for t in rebs:
        D = mkt.dates[t]
        for j, s in enumerate(mkt.name_list):
            rows = [r for r in shares.get(s, []) if r["filed"] < D]
            if rows:
                W[t, j] = max(rows, key=lambda r: r["filed"])["val"] * mkt.names[t, j]
    return W


def main():
    mkt, member = screens.load_universe(); dates = mkt.dates; T, N = mkt.names.shape
    man = json.load(open(f"{FACTS}/manifest.json"))
    recs, shares = {}, {}
    for s in mkt.name_list:
        p = f"{FACTS}/{s}.json"
        if os.path.exists(p):
            facts = json.load(open(p))["facts"]; recs[s] = annual_records(facts)
            shares[s] = [{"val": float(r["val"]), "filed": r["filed"]} for r in facts.get("EntityCommonStockSharesOutstanding", []) if r.get("val") and r.get("filed")]
    n_rec = sum(1 for s in recs if recs[s]); print(f"=== universe {N} names; SEC facts for {len(recs)} (mapped {len(man['mapped'])}, unmapped {len(man['unmapped'])}, failed {len(man['failed'])}); with annual records {n_rec}")
    rebs_by_anchor = {a: [i for i in screens.rebalance_dates(dates, "Y", a) if dates[i] >= "2017-01-01"] for a in GRID["anchor"]}
    mats = {(a, d): score_matrix(mkt, recs, rebs_by_anchor[a], d) for a in GRID["anchor"] for d in GRID["definition"]}
    for (a, d), M in mats.items():
        print(f"  anchor {a:2d} {d}: scored members at each rebalance: " + ", ".join(f"{dates[t][:4]} {np.sum(~np.isnan(M[t]) & member[t])}/{member[t].sum()}" for t in rebs_by_anchor[a]))
    for t0 in (rebs_by_anchor[7][0], rebs_by_anchor[7][-1]):
        D = dates[t0]; cutoff = (datetime.date.fromisoformat(D) - datetime.timedelta(days=548)).isoformat(); kinds = {"OP": 0, "OIE": 0, "ROE": 0, "none": 0}
        for s, r in recs.items():
            ends = [e for e, v in r.items() if v["filed"] < D and e >= cutoff]
            if ends: kinds[r[max(ends)]["kind"]] += 1
        print(f"  at {D}: {kinds['OP']} names with the full operating-profitability formula, {kinds['OIE']} with operating income / equity, {kinds['ROE']} with net income / equity, {kinds['none']} unscorable")

    caps = {a: cap_matrix(mkt, shares, rebs_by_anchor[a]) for a in GRID["anchor"]}
    t0 = rebs_by_anchor[7][0]; print(f"  shares outstanding reported at {dates[t0]} for {np.sum(np.isfinite(caps[7][t0]) & member[t0])} of {member[t0].sum()} members (value-weighted lines are a reference)")

    def run(M, n, a, vw=False):
        c, spyc, d, to = screens.simulate(mkt, member, None, n, "Y", 2017, a, score_matrix=M, weights=caps[a] if vw else None)
        return c[1:] / c[:-1] - 1, spyc[1:] / spyc[:-1] - 1, d, to
    def ew_all(a):
        c, spyc, d, to = screens.simulate(mkt, member, None, 10 ** 6, "Y", 2017, a); return c[1:] / c[:-1] - 1
    def ew_scored(M, a):
        return run(np.where(np.isnan(M), np.nan, 0.0), 10 ** 6, a)[0]

    # ---------------- S1 / S2 / S3: the construct, the concentrated picks, the random lists (primary anchor July) ----------------
    out = {}
    for a in GRID["anchor"]:
        M = mats[(a, "OP")]; rq, rs, d, to = run(M, 50, a); ewa = ew_all(a); ews = ew_scored(M, a)
        print(f"\n=== anchor {a} (first rebalance {d[0]}, {len(d) - 1} sessions): equal-weight lines vs SPY and vs the equal-weight universe; '→2025' = full excess through 2025-12-31")
        print(hdr(False).replace("| roll3", "| roll3 | →2025 | turnover"))
        rows = {}
        for label, n, Mx in (("top 30 % by OP (≈ top 150)", 150, M), ("top 50 by OP", 50, M), ("top 30 by OP", 30, M), ("bottom 30 % by OP (≈ 150)", 150, -M)):
            r, _, _, to = run(Mx, n, a); rows[label] = (r, to)
        rows["EW of the scored set"] = (ews, np.nan); rows["EW of all eligible members"] = (ewa, np.nan)
        for label, n, Mx in (("top 30 % by OP, value-weighted", 150, M), ("top 50 by OP, value-weighted", 50, M), ("top 30 by OP, value-weighted", 30, M), ("VW of the scored set", 10 ** 6, np.where(np.isnan(M), np.nan, 0.0))):
            r, _, _, to = run(Mx, n, a, vw=True); rows[label] = (r, to)
        for label, (r, to) in rows.items():
            s = score(r, rs, d, SPLIT); t = score(r, rs, d, SPLIT, through=THROUGH); v = score(r, ews, d, SPLIT)
            print(fmt(label + " vs SPY", s, None) + f" | {t['excess']:+6.2%} | {to:4.0%}/yr" if not np.isnan(to) else fmt(label + " vs SPY", s, None) + f" | {t['excess']:+6.2%} |")
            print(fmt("    … vs the EW of the scored set (like for like)", v, None) + f" | {score(r, ews, d, SPLIT, through=THROUGH)['excess']:+6.2%} |")
        out[a] = dict(rows=rows, rs=rs, d=d, ewa=ewa, ews=ews)
        # placebo: 50 random N-name lists from the scored set, re-drawn at every rebalance (judged like for like, vs the EW of the scored set)
        rng = np.random.default_rng(76)
        for n in (50, 30):
            draws = []
            for _ in range(50):
                R = np.where(np.isnan(M), np.nan, rng.random(M.shape)); draws.append(score(run(R, n, a)[0], ews, d, SPLIT))
            ex = np.array([x["excess"] for x in draws]); isx = np.array([x["is"] for x in draws]); oosx = np.array([x["oos"] for x in draws])
            pick = score(rows[f"top {n} by OP"][0], ews, d, SPLIT)
            print(f"  placebo, {n} random names × 50 draws vs the EW of the scored set: full median {np.median(ex):+.2%} [p10 {np.percentile(ex, 10):+.2%} … p90 {np.percentile(ex, 90):+.2%}], IS median {np.median(isx):+.2%}, OOS median {np.median(oosx):+.2%}; "
                  f"the top-{n} pick {pick['excess']:+.2%} is above {np.mean(pick['excess'] > ex):.0%} of draws (IS above {np.mean(pick['is'] > isx):.0%}, OOS above {np.mean(pick['oos'] > oosx):.0%})")
            out[a][f"p{n}"] = (ex, isx, oosx, pick)

    # the French yardstick over the same window
    market = datasets.french_market(); op = datasets.french_levels("Portfolios_Formed_on_OP_Daily.csv", "external/french"); fdates = sorted(market)
    d7 = out[7]["d"]; fd, frs = cut(fdates, {"mkt": rets(market, fdates), "hi30": rets(op["Hi 30"], fdates), "lo30": rets(op["Lo 30"], fdates)}, d7[0], "2026-08-31")
    print("\n=== the yardstick: French OP Hi 30 / Lo 30 vs the French market over the same window " + f"{fd[0]} → {fd[-1]}")
    print(hdr(False)); print(fmt("French OP Hi 30 vs the French market", score(frs["hi30"], frs["mkt"], fd, SPLIT), None)); print(fmt("French OP Lo 30 vs the French market", score(frs["lo30"], frs["mkt"], fd, SPLIT), None))

    # ---------------- S4: the walk-forward over the 12 cells ----------------
    print("\n=== S4 — the 12 cells (N × anchor × definition): excess vs the EW universe, full / IS / OOS, and the walk-forward of the selection")
    cells = []
    for a in GRID["anchor"]:
        d = out[a]["d"]
        for dfn in GRID["definition"]:
            ews_d = ew_scored(mats[(a, dfn)], a)
            for n in GRID["N"]:
                r, _, _, to = run(mats[(a, dfn)], n, a); s = score(r, ews_d, d, SPLIT); cells.append(dict(N=n, anchor=a, definition=dfn, **{k: s[k] for k in ("excess", "is", "oos", "sharpe", "dd")}, to=to))
                print(f"  N {n:2d} anchor {a:2d} {dfn:3} | {s['excess']:+6.2%} ({s['is']:+5.1%} / {s['oos']:+5.1%}) | DD {s['dd']:6.1%} Sharpe {s['sharpe']:4.2f} | turnover {to:3.0%}/yr")
    for dim in ("definition", "N", "anchor"):
        print(f"  marginal on {dim}: " + ", ".join(f"{v}: {np.median([c['excess'] for c in cells if c[dim] == v]):+.2%}" for v in sorted({c[dim] for c in cells}, key=str)))
    best_is = max(cells, key=lambda c: c["is"]); best_oos = max(cells, key=lambda c: c["oos"])
    print(f"  pick by IS → N {best_is['N']} anchor {best_is['anchor']} {best_is['definition']} (IS {best_is['is']:+.1%}) → OOS {best_is['oos']:+.1%} (median OOS of all cells {np.median([c['oos'] for c in cells]):+.1%}); "
          f"pick by OOS → N {best_oos['N']} anchor {best_oos['anchor']} {best_oos['definition']} (OOS {best_oos['oos']:+.1%}) → IS {best_oos['is']:+.1%} (median IS {np.median([c['is'] for c in cells]):+.1%}); cells positive in both halves {sum(c['is'] > 0 and c['oos'] > 0 for c in cells)} of {len(cells)}")

    # ---------------- S5: the sleeve on the decade ----------------
    dec, _ = carry.sets(); _, dd, spy_lvl, rd, bear_d, _, _ = dec; e = carry.exposure(bear_d, master.shock_flags(spy_lvl, -0.07, 10, 20))
    rq7, _, d7, _ = out[7]["rows"]["top 50 by OP"][0], None, out[7]["d"], None
    qmap = dict(zip(d7[1:], rq7)); first = d7[0]
    dq = np.array([qmap.get(t, np.nan) for t in dd[1:]]); dq = np.nan_to_num(dq)
    dcut, rs = cut(dd, {"dip": rd["dip"], "mom": rd["mom"], "spy": rd["mkt"], "q": dq, "e": e}, first, dd[-1]); ee, dip, mom, spy, q = rs["e"], rs["dip"], rs["mom"], rs["spy"], rs["q"]
    print(f"\n=== S5 — the sleeve with the top-50 picks (July), {dcut[0]} → {dcut[-1]}, vs SPY; the book over the same window as the bar")
    print(hdr(False).replace("| roll3", "| roll3 | →2025"))
    ok_s5 = {}
    sb = score(ee * (0.4 * dip + 0.6 * mom), spy, dcut, SPLIT); tb = score(ee * (0.4 * dip + 0.6 * mom), spy, dcut, SPLIT, through=THROUGH)
    print(fmt("dip 40 / SPMO 60 (the book)", sb, None) + f" | {tb['excess']:+6.2%}")
    for label, core in (("dip 20 / SPMO 60 / picks 20 (from the dip sleeve)", 0.2 * dip + 0.6 * mom + 0.2 * q), ("dip 40 / SPMO 40 / picks 20 (from momentum)", 0.4 * dip + 0.4 * mom + 0.2 * q), ("picks 100 % under the exposure rules", q)):
        s = score(ee * core, spy, dcut, SPLIT); t = score(ee * core, spy, dcut, SPLIT, through=THROUGH); print(fmt(label, s, None) + f" | {t['excess']:+6.2%}")
        if "picks 20" in label: ok_s5[label] = s["is"] > sb["is"] and s["oos"] > sb["oos"] and t["excess"] > tb["excess"] and s["sharpe"] >= sb["sharpe"]

    # ---------------- S6: running it ----------------
    to50 = out[7]["rows"]["top 50 by OP"][1]; to30 = out[7]["rows"]["top 30 by OP"][1]
    print(f"\n=== S6 — running it: turnover top-50 {to50:.0%}/yr, top-30 {to30:.0%}/yr; a 20 % sleeve of N equal names = {0.2 / 50:.2%} of equity per name at N 50 ({0.2 / 50 * 25000:.0f} $ at $25k, {0.2 / 50 * 100000:.0f} $ at $100k) and {0.2 / 30:.2%} at N 30 ({0.2 / 30 * 25000:.0f} $ / {0.2 / 30 * 100000:.0f} $) against the $500 dust floor; "
          f"unmapped tickers {len(man['unmapped'])} of {N} ({len(man['unmapped']) / N:.0%}), ineligible for picking, inside the EW universe and SPY")

    # ---------------- the pre-registered verdict ----------------
    ews = out[7]["ews"]; d = out[7]["d"]
    s_top = score(out[7]["rows"]["top 30 % by OP (≈ top 150)"][0], ews, d, SPLIT); s_bot = score(out[7]["rows"]["bottom 30 % by OP (≈ 150)"][0], ews, d, SPLIT); s50 = score(out[7]["rows"]["top 50 by OP"][0], ews, d, SPLIT)
    ex, isx, oosx, _ = out[7]["p50"]
    s1 = s_top["is"] > 0 and s_top["oos"] > 0 and s_bot["excess"] < 0
    s2 = s50["is"] >= 0.008 and s50["oos"] >= 0.008 and s50["excess"] > np.percentile(ex, 90) and s50["is"] > np.median(isx) and s50["oos"] > np.median(oosx)
    print("\n=== pre-registered verdict (July anchor, OP; the universe benchmark = the EW of the scored set, like for like — the unmapped names cannot be picked)")
    print(f"  S1 (top 30 % > EW universe in both halves, bottom 30 % < 0): top {s_top['excess']:+.2%} ({s_top['is']:+.1%} / {s_top['oos']:+.1%}), bottom {s_bot['excess']:+.2%} → {'holds' if s1 else 'FAILS'}")
    print(f"  S2 (top 50 ≥ +0.8 vs EW universe in both halves, > p90 of random lists, > their median in both halves): {s50['excess']:+.2%} ({s50['is']:+.1%} / {s50['oos']:+.1%}) → {'holds' if s2 else 'FAILS'}")
    s50vw = score(out[7]["rows"]["top 50 by OP, value-weighted"][0], out[7]["rs"], d, SPLIT); s30vw = score(out[7]["rows"]["top 30 by OP, value-weighted"][0], out[7]["rs"], d, SPLIT)
    print(f"  S3 (reference, value-weighted vs SPY): top 50 {s50vw['excess']:+.2%} ({s50vw['is']:+.1%} / {s50vw['oos']:+.1%}), top 30 {s30vw['excess']:+.2%} ({s30vw['is']:+.1%} / {s30vw['oos']:+.1%})")
    print("  S5 (the sleeve beats the book in both halves and through 2025, Sharpe no lower): " + "; ".join(f"{k.split(' (')[0]}: {'ok' if v else 'no'}" for k, v in ok_s5.items()))
    print(f"  → {'DECISION PROPOSED: a held profitability sleeve' if s2 and any(ok_s5.values()) else ('recorded: the picks keep the premium but do not improve the book' if s2 else 'NO — no self-built sleeve; the quality door closes on free data')}")


if __name__ == "__main__":
    main()
