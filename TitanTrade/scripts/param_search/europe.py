"""E6 — a European strategy of its own (roadmap E6, handover §8 item 6; Decision 101 research, 2026-11-05; free data).

The operator's brief (2026-10-29): "not a copy of the US book but a research programme on one region (Europe first) —
the catalogue of ideas re-run on that region's data, a design chosen there, then the US and the regional book judged
together." Parked for better priorities; started 2026-11-05 on the operator's word with the ideas block complete.
What Decision 073 settled on the decade: ex-US momentum is real (Europe's WML +9.9 pp/yr long-short, both halves),
the dip rule on twenty country ETFs is not a floor (negative in the first half of 2017 →), two long-only equity books
fall together (0.85 total, 0.58 active), and a blend gave back 2 … 4 pp/yr for 1 point of drawdown. This programme
takes the long, hindsight-free data the roadmap asked for and re-runs the catalogue on Europe alone.
Data: Kenneth French's **Europe** daily files 1990-11 → 2026-09 (USD): the market (Mkt-RF + RF), the 6 and 25
size × prior-return sorts (daily, prior = −250 … −20 days) — **BIG HiPRIOR**, large winners, is the held momentum
sleeve, the published sort a 1990 investor could have held; the US side on the same dates = the century book
(`books.century()`: the dip sleeve on 49 industries 40 / the top momentum decile 60 under min(SMA insurance ×0.5,
shock ×0.5)). Tiingo (`fetch_keyed.py`): the **ten European country ETFs from 1996-04** (EWG EWU EWQ EWL EWN EWP EWI
EWD EWK EWO — the dip universe, baskets like the sectors), IEV (2000-07, the European index), EZU, VGK, FEZ, EFA,
**IDMO** (2012-02, the investable momentum vehicle), HEDJ (hedged Europe); FRED DEXUSEU for the euro view 1999 →.
Windows: **W1** 1990-11-01 → 2026-09-30 (French; split 2008-07-01; eras 1990–2000 / 2000–2010 / 2010 →),
**W2** 1997-04-01 → 2026-11-03 (the ETFs after their first year; split 2012-01-01; eras 1997–2003 / 2003–2012 / 2012 →).
Costs 0.05 %/side on the ETF sleeve; the French portfolios frictionless (as the century book); blends re-set daily.
Screens and pre-registered hypotheses (the expected numbers were written before the first run):
  F1  base rates, knowledge: Europe's market vs the US market 1990 → in USD, by era — expected −2 … −4 pp/yr over
      the window, ≈ even in 1990–2008 and 4 … 6 behind after; in euros 1999 → the gap narrows by ≈ 1.
  F2  momentum held in Europe: BIG HiPRIOR vs the European market 1990 → **+3 … +6 pp/yr, positive in both halves
      and every era**, the drawdown within 5 points of the market's, 2009 the worst relative year; IDMO vs VGK
      2012 → +2 … +5 (073: +4.3 vs ACWX); the luck meter on BIG HiPRIOR.
  F3  the dip rule on the ten country ETFs 1997 → (the live cell, 3 × 25 % slots, the equal-weight basket as the
      index and the residual, the insurance off inside): **≤ 0 vs the basket in at least one half** (countries are
      not sectors: more volatile, less mean-reverting — 073), and in the 36-cell grid (dip 6 / 8 / 10 / 12 × target
      15 / 20 / 30 × hold 40 / 60 / 90) **fewer than a third of the cells ≥ 0 in both halves**: no European dip
      floor. Reopened only if the live cell is ≥ 0 in both halves *and* the grid's median is ≥ 0.
  F4  the switches on Europe (the index below its 200-day SMA AND fewer than half the ten countries above theirs
      → ×0.5; the shock trigger −7 % / 10 sessions → ×0.5; exposure = min) on the basket 1997 →: **+0 … +1 pp/yr**
      net, the worst fall 10 … 15 points shallower (2000–03 and 2008 pay, 2012–21 costs ≈ 1 a year), and on the
      French market 1990 → with the SMA alone the same shape; each against a block-shuffled placebo of its flags
      (63-session blocks, 20 draws) — expected above the placebo's median, not necessarily its 90th percentile.
  F5  the European book — momentum 60 / (the dip sleeve if F3 reopens it, else the index) 40 under the switches —
      vs its own market: **+2 … +4 pp/yr on W1, positive in both halves and every era**, the worst fall 10 … 20
      points shallower than the market's; vs SPY −1 … +1 over W1 (Europe's momentum premium against the US
      market's own run). The luck meter on the book's excess over its market (t 1.5 … 3 on 36 years).
  F6  the two books together, W1 and W2: US / Europe at 100 / 0, 80 / 20, 70 / 30, 60 / 40, 50 / 50, vs SPY and
      vs the US book alone; placebo P1 = the European *market* in the European slot (does the European *book* add
      anything beyond European exposure?). Expected: the 70 / 30 blend gives back **0.5 … 2 pp/yr** against the US
      book, the worst fall 1 … 3 points shallower, the Sharpe within ±0.05; ≈ even in the first halves (Europe ≈ US
      to 2008), the give-back in the second; the European book in the slot beats the European market in the slot
      by +1 … +2 at 70 / 30 (its own premium); the active returns of the two books correlate 0.3 … 0.5.
Drop rule, written first: a European book is proposed as a second book only if (a) it beats its own market in both
halves and every era of W1 and W2 (F5) **and** (b) the 70 / 30 blend beats the US book alone on both the Sharpe and
the worst fall in both halves of W1 with a return give-back under 1 pp/yr vs SPY — else recorded, no second book.
Whatever F5 shows, holding Europe at all is a regional bet (the US beat Europe for fifteen years; a 1990 investor
did not know that), priced here like the bitcoin bet was, never applied. Nothing live changes.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/europe.py
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import books  # noqa: E402
import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402
from books import LIVE  # noqa: E402
from breadth2 import block_shuffle  # noqa: E402
from intl import fx_eur, in_eur, levels, rets  # noqa: E402
from putwrite import cut  # noqa: E402

COUNTRIES = ["EWG", "EWU", "EWQ", "EWL", "EWN", "EWP", "EWI", "EWD", "EWK", "EWO"]
W1 = ("1990-11-01", "2026-09-30", "2008-07-01", [("1990-11-01", "2000-01-01"), ("2000-01-01", "2010-01-01"), ("2010-01-01", "2026-10-01")])
W2 = ("1997-04-01", "2026-11-03", "2012-01-01", [("1997-04-01", "2003-01-01"), ("2003-01-01", "2012-01-01"), ("2012-01-01", "2026-12-01")])
GRID = list(itertools.product((0.06, 0.08, 0.10, 0.12), (0.15, 0.20, 0.30), (40, 60, 90)))
HDR = f"{'':58} {'excess':>7} {'IS':>6} {'OOS':>6} | {'DD':>6} {'mktDD':>6} | {'Sh':>5} {'mkt':>5} | {'worst':>6} | eras"


def fmt(label, s):
    return (f"{label:58} {s['excess']:+7.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['dd']:6.1%} {s['mkt_dd']:6.1%} | {s['sharpe']:5.2f} {s['mkt_sharpe']:5.2f} | {s['worst_year']:+6.1%} | "
            + (" ".join(f"{x:+6.1%}" for x in s["eras"]) if "eras" in s else f"roll3 {s['roll3_pos']:.0%}") + (f" | {master.luck_line(s)}" if "t" in s else ""))


def ew_basket(symbols):
    """The equal-weight basket of the country ETFs, re-set daily, as {date: level} (the index before IEV exists)."""
    px = {s: datasets.tiingo(s) for s in symbols}; dates = sorted(set.intersection(*(set(v) for v in px.values()))); lvl = 100.0; out = {dates[0]: lvl}
    for i in range(1, len(dates)):
        lvl *= 1 + np.mean([px[s][dates[i]] / px[s][dates[i - 1]] - 1 for s in symbols]); out[dates[i]] = lvl
    return out


def main():
    rng = np.random.default_rng(101); fx = fx_eur()
    # ---------- W1: the French window ----------
    cen = books.century(); a, b, split, eras = W1
    eu_mkt = datasets.french_regional("Europe", "mkt"); eu6 = datasets.french_levels("Europe_6_Portfolios_ME_Prior_250_20_Daily.csv", "external/french_intl")
    d, rs = cut(cen["d"], {"dip": cen["r"]["dip"], "mom": cen["r"]["mom"], "mkt": cen["r"]["mkt"], "bear": cen["bear"]}, a, b)
    us_lvl = np.concatenate([[1.0], np.cumprod(1 + rs["mkt"])]); us_shock = books.shock_flags(us_lvl, -0.07, 10, 20); master.shock_scale_holder[0] = 0.5
    us_book = master.book(0.4, rs["dip"], rs["mom"], rs["mkt"], rs["bear"], 0.5, us_shock, None, False, None)
    r_eu = np.array([eu_mkt.get(t, 0.0) for t in d[1:]]); eu_lvl = np.concatenate([[1.0], np.cumprod(1 + r_eu)])
    r_big = rets(eu6["BIG HiPRIOR"], d); r_small = rets(eu6["SMALL HiPRIOR"], d)
    sc = lambda r, rm, dd=d, sp=split, er=eras, luck=0: master.score(r, rm, dd, sp, er, luck_draws=luck)  # noqa: E731
    print(f"=== W1 — Europe on Kenneth French's daily files, {d[0]} → {d[-1]} (USD), split {split}; the US side = the century book on the same dates")
    print(HDR)
    print(fmt("F1 Europe's market vs the US market", sc(r_eu, rs["mkt"])))
    k99 = next(i for i, t in enumerate(d) if t >= "1999-01-04"); d99 = d[k99:]
    print(fmt("F1 … in euros, 1999 →", sc(in_eur(r_eu[k99:], d99, fx), in_eur(rs["mkt"][k99:], d99, fx), d99, split, [e for e in eras if e[1] > "1999-01-04"])))
    print(fmt("F2 BIG HiPRIOR (large winners) vs Europe's market", sc(r_big, r_eu, luck=400)))
    print(fmt("F2 SMALL HiPRIOR vs Europe's market (for the record)", sc(r_small, r_eu)))
    # F4 on the French market: the SMA-only insurance and the shock trigger, vs a block-shuffled placebo
    eu_above = books.sma_above(eu_lvl); eu_bear = books.prev(eu_above[1:]) == 0.0; eu_shock = books.shock_flags(eu_lvl, -0.07, 10, 20)
    e_eu = books.exposure(eu_bear, eu_shock)
    print(fmt("F4 Europe's market × (SMA insurance ×0.5, shock ×0.5)", sc(e_eu * r_eu, r_eu)))
    pl = np.array([sc(books.exposure(block_shuffle(eu_bear.astype(float), rng) > 0.5, eu_shock) * r_eu, r_eu)["excess"] for _ in range(20)])
    print(f"{'   placebo (the insurance flags block-shuffled, 20 draws)':58} median {np.median(pl):+.2%}, 10–90 % {np.percentile(pl, 10):+.2%} … {np.percentile(pl, 90):+.2%}")
    # F5 the European book on W1 (the index in the dip slot — F3 is decided on W2)
    eu_book = master.book(0.4, r_eu, r_big, r_eu, eu_bear, 0.5, eu_shock, None, False, None)
    s5 = sc(eu_book, r_eu, luck=400); print(fmt("F5 the European book (BIG HiPRIOR 60 / index 40, switches) vs Europe", s5))
    print(fmt("F5 … vs the US market", sc(eu_book, rs["mkt"]))); s_us = sc(us_book, rs["mkt"]); print(fmt("   the US book vs the US market (reference)", s_us))
    # F6 the two books together on W1
    print(f"\nF6 — the two books together on W1 (vs the US market); placebo P1 = Europe's market in the European slot; active-return correlation {np.corrcoef(us_book - rs['mkt'], eu_book - r_eu)[0, 1]:+.2f}, total {np.corrcoef(us_book, eu_book)[0, 1]:+.2f}")
    print(HDR); ok6 = {}
    for w in (1.0, 0.8, 0.7, 0.6, 0.5):
        s = sc(w * us_book + (1 - w) * eu_book, rs["mkt"]); p1 = sc(w * us_book + (1 - w) * e_eu * r_eu, rs["mkt"])
        print(fmt(f"US book {w:.0%} / European book {1 - w:.0%}", s)); print(fmt(f"   P1: US book {w:.0%} / Europe's market (switched) {1 - w:.0%}", p1))
        ok6[w] = (s["sharpe"] > s_us["sharpe"] and s["dd"] > s_us["dd"] and s["is"] > s_us["is"] - 0.01 and s["oos"] > s_us["oos"] - 0.01 and s["excess"] > s_us["excess"] - 0.01)
    # ---------- W2: the ETF window ----------
    a, b, split, eras = W2; basket = ew_basket(COUNTRIES)
    mkt = fastbt.Market(basket, {s: datasets.tiingo(s) for s in COUNTRIES}, {s: datasets.tiingo(s) for s in COUNTRIES})
    r0 = fastbt.run(mkt, LIVE, a, None, want_trades=True); i0 = mkt.dates.index(r0["start"]); dd = mkt.dates[i0:i0 + len(r0["_curve"])]
    dipc = r0["_curve"]; bk = r0["_spy_curve"]; r_dip = dipc[1:] / dipc[:-1] - 1; r_bk = bk[1:] / bk[:-1] - 1
    _, _, spy_above, breadth = mkt.pre(90, 150, 200); bear2 = (books.prev(spy_above[i0:i0 + len(dd)][1:]) == 0.0) & (books.prev(breadth[i0:i0 + len(dd)][1:]) < 0.5)
    shock2 = books.shock_flags(bk, -0.07, 10, 20); e2 = books.exposure(bear2, shock2)
    sc2 = lambda r, rm, luck=0: master.score(r, rm, dd, split, eras, luck_draws=luck)  # noqa: E731
    print(f"\n=== W2 — the ten European country ETFs, {dd[0]} → {dd[-1]} (USD), split {split}; the index = their equal-weight basket")
    print(HDR)
    s3 = sc2(r_dip, r_bk); print(fmt(f"F3 the live dip rule on the ten countries vs the basket ({len(r0['trades'])} trades)", s3))
    iev = rets(datasets.tiingo("IEV"), dd); k_iev = next(i for i, t in enumerate(dd[1:]) if t >= "2000-08-01")
    print(fmt("   the basket vs IEV, 2000-08 → (the basket as the index)", master.score(r_bk[k_iev:], iev[k_iev:], dd[k_iev:], split, [e for e in eras if e[1] > "2000-08-01"])))
    grid = []
    for dp, tp, hold in GRID:
        rr = fastbt.run(mkt, {**LIVE, "dip_pct": dp, "tp_pct": tp, "max_hold_days": hold}, a, None); c = rr["_curve"]; s = sc2(c[1:] / c[:-1] - 1, r_bk); grid.append((dp, tp, hold, s["excess"], s["is"], s["oos"]))
    both = [g for g in grid if g[4] >= 0 and g[5] >= 0]
    print(f"   the 36-cell grid vs the basket: median excess {np.median([g[3] for g in grid]):+.2%}, cells ≥ 0 in both halves {len(both)} / 36; best {max(grid, key=lambda g: g[3])[:3]} {max(g[3] for g in grid):+.2%}; the live cell ranks {sorted([g[3] for g in grid], reverse=True).index(s3['excess']) + 1 if s3['excess'] in [g[3] for g in grid] else 'n/a'}")
    reopen = s3["is"] >= 0 and s3["oos"] >= 0 and np.median([g[3] for g in grid]) >= 0
    print(f"   F3 verdict: {'the dip floor REOPENS on Europe' if reopen else 'no European dip floor — the book keeps the index in the slot'}")
    print(fmt("F4 the basket × (two-signal insurance ×0.5, shock ×0.5)", sc2(e2 * r_bk, r_bk)))
    pl2 = np.array([sc2(books.exposure(block_shuffle(bear2.astype(float), rng) > 0.5, shock2) * r_bk, r_bk)["excess"] for _ in range(20)])
    print(f"{'   placebo (the insurance flags block-shuffled, 20 draws)':58} median {np.median(pl2):+.2%}, 10–90 % {np.percentile(pl2, 10):+.2%} … {np.percentile(pl2, 90):+.2%}")
    # the momentum sleeve on W2: BIG HiPRIOR (French) to 2012-02, IDMO after — the investable splice; and IDMO vs VGK alone
    big2 = rets(eu6["BIG HiPRIOR"], dd); idmo = rets(datasets.tiingo("IDMO"), dd); vgk = rets(datasets.tiingo("VGK"), dd)
    k_id = next(i for i, t in enumerate(dd[1:]) if t >= "2012-03-01"); mom2 = np.concatenate([big2[:k_id], idmo[k_id:]])
    print(fmt("F2 IDMO vs VGK, 2012-03 →", master.score(idmo[k_id:], vgk[k_id:], dd[k_id:], "2019-07-01", None)))
    dip_slot = r_dip if reopen else r_bk
    eu_book2 = master.book(0.4, dip_slot, mom2, r_bk, bear2, 0.5, shock2, None, False, None)
    s5b = sc2(eu_book2, r_bk, luck=400); print(fmt(f"F5 the European ETF book (momentum splice 60 / {'dip' if reopen else 'index'} 40, switches) vs the basket", s5b))
    # the US side on W2: the century book on the same dates; the blend
    d2, rs2 = cut(cen["d"], {"dip": cen["r"]["dip"], "mom": cen["r"]["mom"], "mkt": cen["r"]["mkt"], "bear": cen["bear"]}, dd[0], dd[-1])
    common = sorted(set(d2) & set(dd)); iu = [d2.index(t) for t in common]; ie = [dd.index(t) for t in common]
    us_r = {k: v[np.array(iu[1:]) - 1] for k, v in rs2.items() if k != "bear"}; us_bear = rs2["bear"][np.array(iu[1:]) - 1]
    us_lvl2 = np.concatenate([[1.0], np.cumprod(1 + us_r["mkt"])]); us_book2 = master.book(0.4, us_r["dip"], us_r["mom"], us_r["mkt"], us_bear, 0.5, books.shock_flags(us_lvl2, -0.07, 10, 20), None, False, None)
    eu_b = eu_book2[np.array(ie[1:]) - 1]; eu_m = (e2 * r_bk)[np.array(ie[1:]) - 1]
    sc3 = lambda r, rm: master.score(r, rm, common, split, eras)  # noqa: E731
    print(f"\nF6 — the two books together on W2 ({common[0]} → {common[-1]}, vs the US market); active-return correlation {np.corrcoef(us_book2 - us_r['mkt'], eu_b - r_bk[np.array(ie[1:]) - 1])[0, 1]:+.2f}")
    print(HDR); s_us2 = sc3(us_book2, us_r["mkt"]); print(fmt("the US book vs the US market (reference)", s_us2)); print(fmt("the European ETF book vs the US market", sc3(eu_b, us_r["mkt"])))
    for w in (0.8, 0.7, 0.6, 0.5):
        print(fmt(f"US book {w:.0%} / European book {1 - w:.0%}", sc3(w * us_book2 + (1 - w) * eu_b, us_r["mkt"]))); print(fmt(f"   P1: US book {w:.0%} / Europe's basket (switched) {1 - w:.0%}", sc3(w * us_book2 + (1 - w) * eu_m, us_r["mkt"])))
    # ---------- the pre-registered verdict ----------
    print("\n=== pre-registered verdict")
    a_ok = s5["is"] > 0 and s5["oos"] > 0 and all(x > 0 for x in s5["eras"]) and s5b["is"] > 0 and s5b["oos"] > 0 and all(x > 0 for x in s5b["eras"])
    print(f"  (a) the European book beats its own market in both halves and every era: W1 {s5['excess']:+.2%} ({s5['is']:+.1%} / {s5['oos']:+.1%}; eras " + " ".join(f"{x:+.1%}" for x in s5["eras"]) + f"), W2 {s5b['excess']:+.2%} ({s5b['is']:+.1%} / {s5b['oos']:+.1%}; eras " + " ".join(f"{x:+.1%}" for x in s5b["eras"]) + f") → {'ok' if a_ok else 'no'}")
    print(f"  (b) the 70 / 30 blend beats the US book on Sharpe and worst fall in both halves with a give-back under 1 pp/yr (W1): {'ok' if ok6[0.7] else 'no'}")
    print(f"  → {'a European second book is PROPOSED — read F5 / F6' if a_ok and ok6[0.7] else 'NO second book; the European book is recorded, holding Europe is a regional bet for the operator (F1, F5)'}")


if __name__ == "__main__":
    main()
