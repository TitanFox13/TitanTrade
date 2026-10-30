"""Quality over a century (roadmap B2; Decision 075 research, 2026-10-30).

"Quality" — steadily profitable companies that invest conservatively — is the one documented equity premium the book
has never held, and the question behind roadmap B9 (a fundamentals pipeline for a single-name dip universe) is
whether profitability separates a dip from a break. Both are answered here on hindsight-free data before any pipeline
is built: Kenneth French's daily portfolios formed on operating profitability (OP) and on investment (INV), the 25
size × profitability portfolios and the five-factor file (RMW, CMA), all 1963-07 → 2026-09; AQR's Quality-Minus-Junk
factor for the US, daily 1957-07 →; QUAL (MSCI USA Quality) on the decade. Quality was closed as an ETF vehicle in
Decision 067 (QUAL −0.7 vs SPY) and as a screen in Decision 066 (low volatility, "quiet winners"); the century is a
different question. Loaders ``datasets.french_levels(…, sub="external/french")``, ``datasets.french_factors``,
``datasets.aqr_qmj``.

Windows: **63y** 1963-07-01 → 2026-08-31 (the French market's end), split 1995-01-01 (the midpoint), eras = the
project's quarter-centuries restricted to the window (1963–75, 1975–2000, 2000–26); **QMJ** 1957-07-01 →, split
1992-01-01; **decade** 2017-01-03 → 2026-10-12 (the ETF book, split 2022-01-01, through 2025-12-31 beside full). The
book = ``carry.sets()``: the century book (dip on 49 industries 40 / top momentum decile 60, frictionless) on the long
window, the sector-dip / SPMO book on the decade; exposure = min(insurance ×0.5, shock ×0.5); idle capital at 0.

Pre-registered hypotheses (the expected numbers were written before the first run):
  Q1  the premium exists and is old (long-short): RMW and QMJ have a positive annualised mean in both halves and in
      every era, expected RMW +2 … +4 pp/yr, QMJ +3 … +5, t > 3; both are *defensive* — positive in 2000–02 and
      2008, negative in the 2003 and 2009 junk rallies; market beta −0.1 … −0.3; correlation with the momentum factor
      +0.1 … +0.3 (quality and momentum lean the same way), i.e. a cousin of the momentum sleeve, not its opposite.
  Q2  the long-only form captures about a third of it: the top profitability decile (Hi 10) and the top 30 % (Hi 30)
      beat the market by +0.5 … +2 pp/yr over 63 years at 90–100 % of its volatility with a smaller drawdown
      (2000–02 and 2008 shallower by 5 … 15 points), positive in both halves; the era test is the open question
      (expected: not every era — the 1963–75 era is the doubtful one). Conservative investment (INV Lo 10 / Lo 30)
      +0.5 … +1.5 with the same shape. The bottom decile loses 2 … 4 pp/yr (the test has teeth).
  Q3  quality as a sleeve, the momentum-sleeve bar: the book dip 40 / mom 60 against dip 40 / mom 40 / Hi 30 20,
      dip 30 / mom 50 / Hi 30 20, dip 20 / mom 60 / Hi 30 20 (from the dip sleeve) and dip 40 / mom 0 / Hi 30 60
      (quality instead of momentum). Expected: the sleeve's excess correlates +0.1 … +0.3 with momentum's and −0.1 …
      +0.1 with the dip sleeve's; it lowers the return by 0.5 … 1.5 pp/yr (momentum's +5 is the bigger premium) and
      moves the Sharpe by −0.01 … +0.03 — it fails the bar (return better in both halves and every era, Sharpe no
      lower). Quality *instead of* momentum loses 2 … 4 pp/yr with a smaller drawdown.
  Q4  the dip rule on quality portfolios — the B9 gate: the live rule (3 × 25 % slots, the market as the residual,
      insurance ×0.5 from the universe's own breadth) on (a) the 10 high-profitability portfolios of the 25 size × OP
      grid (OP4–OP5 across the five size groups), (b) the 10 low-profitability ones (OP1–OP2), (c) all 25, (d) the 10
      OP deciles, (e) the 10 INV deciles — each vs the market and vs the equal-weight hold of its universe, both halves
      and every era; the reference is the same rule on the 49 industries over the same window (the floor). Expected:
      every run ≈ 0 ± 1 vs the market like the industries (diversified portfolios do not break, and dip rarely: fewer
      trades than the industries), and **high-OP ≥ low-OP by +1 … +3 pp/yr in both halves** — profitable portfolios'
      dips revert, junk's continue. If that holds, profitability separates dips from breaks at the portfolio level
      and B9 is worth building; if the gap is inside ±1 or flips between halves, it does not.
  Q5  the crash leg, reported not hypothesised: 1973–74, 1987, 2000–02, 2008, 2020, 2022 peak-to-trough and the
      rebound year for Hi 30 OP, the momentum decile, the dip sleeve, the book, and the book with the quality sleeve.
  Q6  the decade, investable: QUAL vs SPY both halves and through 2025 (Decision 067 read −0.7 full period), QUAL's
      excess correlated with SPMO's +0.2 … +0.4; dip 40 / SPMO 40 / QUAL 20 costs 0.5 … 1.5 pp/yr vs the book with the
      Sharpe within ±0.03. The gap between the century's quality portfolios and the ETF is the vehicle (index
      construction, as MTUM vs SPMO).

Drop rules, written first:
  - A quality sleeve is proposed only if Q3 passes the momentum-sleeve bar on the long window *and* an investable
    vehicle beat SPY in both decade halves (Q6) — both; else recorded, no sleeve.
  - B9 (the fundamentals pipeline) opens only if, in Q4, the high-OP run beats the low-OP run by ≥ 1 pp/yr in both
    halves and in every era *and* the high-OP run is ≥ 0 vs the market and vs its equal-weight basket in both halves
    (the sector-floor standard); else B9 is closed and the single-name door stays shut (Decision 070).
  - Q1, Q2 and Q5 are knowledge, whatever the outcome.

Costs: French portfolios and factors are frictionless; the dip runs charge 0.05 % a side; blends rebalance daily
without cost; the ETF series carry their expense ratios. De-risked capital earns 0.
Run from TitanTrade/: uv run --with numpy --with openpyxl python -I scripts/param_search/quality.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402
from intl import rets  # noqa: E402
from putwrite import cut, ep, fmt, hdr, score  # noqa: E402

W63 = ("1963-07-01", "2026-08-31", "1995-01-01", [("1963-07-01", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")])
WQMJ = ("1957-07-01", "2026-08-31", "1992-01-01", [("1957-07-01", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")])
THROUGH = "2025-12-31"
EXT = "external/french"
CRASHES = [("1973-74", "1973-01-11", "1974-10-03"), ("1987", "1987-08-25", "1987-12-04"), ("2000-02", "2000-03-24", "2002-10-09"), ("2008", "2007-10-09", "2009-03-09"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12")]
EPIS = [("2000-02", "2000-03-24", "2002-10-09"), ("2003 rally", "2003-03-11", "2004-03-11"), ("2008", "2007-10-09", "2009-03-09"), ("2009 rally", "2009-03-09", "2010-03-09")]


def comp(f, a, b):
    """Compounded return of a {date: return} series over [a, b]."""
    return float(np.prod([1 + v for d, v in f.items() if a <= d <= b]) - 1)


def factor_row(label, f, mkt, mom, a, b, split, eras):
    ds = [d for d in sorted(f) if a <= d <= b and d in mkt]; x = np.array([f[d] for d in ds]); m = np.array([mkt[d] for d in ds])
    ks = next(k for k, d in enumerate(ds) if d >= split); t = x.mean() / x.std() * np.sqrt(len(x)); sh = x.mean() / x.std() * np.sqrt(252)
    beta = np.cov(x, m)[0, 1] / np.var(m); cm = [d for d in ds if d in mom]; corr = np.corrcoef([f[d] for d in cm], [mom[d] for d in cm])[0, 1]
    er = [np.mean([f[d] for d in ds if ea <= d < eb]) * 252 for ea, eb in eras]
    print(f"{label:30} {x.mean() * 252:+7.1%} {x[:ks].mean() * 252:+7.1%} {x[ks:].mean() * 252:+7.1%} | " + " ".join(f"{v:+6.1%}" for v in er)
          + f" | {t:5.1f} {sh:5.2f} | {beta:+5.2f} {corr:+5.2f} | " + " ".join(f"{comp(f, pa, pb):+6.0%}" for _, pa, pb in EPIS))


def dip_run(label, market, uni, cen_dates, split, eras):
    """The live dip rule (insurance ×0.5 inside) on a universe of French portfolios: vs the market and vs its EW hold."""
    mk = fastbt.Market(market, uni, uni); r = fastbt.run(mk, dict(master.LIVE, insurance_scale=0.5), W63[0], W63[1], want_trades=True)
    d = mk.dates[mk.dates.index(r["start"]):mk.dates.index(r["end"]) + 1]; c = r["_curve"]; rr = c[1:] / c[:-1] - 1; rm = r["_spy_curve"][1:] / r["_spy_curve"][:-1] - 1
    ew = np.column_stack([rets(v, d) for v in uni.values()]).mean(axis=1); m = r["metrics"]
    s1 = score(rr, rm, d, split, eras); s2 = score(rr, ew, d, split, eras); s3 = score(ew, rm, d, split, eras)
    med = np.median([t["return"] for t in r["trades"]]) if r["trades"] else np.nan; ex = m["exits"]
    print(fmt(f"{label} vs the market", s1, eras) + f" | {m['trades']} trades ({m['trades'] / (len(d) / 252):.1f}/yr), {m['win_rate']:.0%} win, median {med:+.1%}, tp/stop/time {ex['tp']}/{ex['stop']}/{ex['time']}, risk-off {r['risk_off_days'] / len(d):.0%}")
    print(fmt(f"{label} vs its EW hold", s2, eras)); print(fmt(f"  (EW hold of {label} vs the market)", s3, eras))
    return s1, s2


def main():
    # ---------------- Q1: the premium, long-short ----------------
    f3 = datasets.french_factors("F-F_Research_Data_Factors_daily.csv"); mkt = {d: f3["Mkt-RF"][d] + f3["RF"][d] for d in f3["RF"] if d in f3["Mkt-RF"]}
    mom = datasets.french_factors("F-F_Momentum_Factor_daily.csv")["Mom"]; f5 = datasets.french_factors("F-F_Research_Data_5_Factors_2x3_daily.csv", EXT); qmj = datasets.aqr_qmj("USA")
    print("=== Q1 — the quality premium, long-short: annualised mean, halves, eras | t, Sharpe | beta to the market, correlation with the momentum factor | compounded in 2000–02, the 2003 rally, 2008, the 2009 rally")
    print(f"{'factor (window)':30} {'mean':>7} {'1st':>7} {'2nd':>7} | {'era 1':>6} {'era 2':>6} {'era 3':>6} | {'t':>5} {'Sh':>5} | {'beta':>5} {'c.mom':>5} | " + " ".join(f"{e[0]:>6}" for e in EPIS))
    factor_row("RMW profitability (1963 →)", f5["RMW"], mkt, mom, *W63); factor_row("CMA investment (1963 →)", f5["CMA"], mkt, mom, *W63)
    factor_row("QMJ quality-minus-junk (1957 →)", qmj, mkt, mom, *WQMJ); factor_row("Mom momentum (1963 →, reference)", mom, mkt, mom, *W63)
    factor_row("HML value (1963 →, reference)", f3["HML"], mkt, mom, *W63)

    # ---------------- the century book on the 63-year window ----------------
    dec, cen = carry.sets(); _, fd, mk_lvl, rc, bear_c, _, _ = cen
    e_c = carry.exposure(bear_c, master.shock_flags(mk_lvl, -0.07, 10, 20))
    op = datasets.french_levels("Portfolios_Formed_on_OP_Daily.csv", EXT); inv = datasets.french_levels("Portfolios_Formed_on_INV_Daily.csv", EXT)
    a, b, split, eras = W63
    d, rs = cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "e": e_c, **{f"OP {k}": rets(op[k], fd) for k in ("Hi 10", "Hi 30", "Med 40", "Lo 30", "Lo 10")},
                     **{f"INV {k}": rets(inv[k], fd) for k in ("Lo 10", "Lo 30", "Hi 30", "Hi 10")}}, a, b)
    e, dip, mo, m = rs["e"], rs["dip"], rs["mom"], rs["mkt"]

    # ---------------- Q2: long-only quality portfolios vs the market ----------------
    print(f"\n=== Q2 — the long-only form, 63y {d[0]} → {d[-1]} (split 1995; eras 1963–75 / 1975–2000 / 2000–26); excess CAGR vs the French market")
    print(hdr(True))
    for k in ("OP Hi 10", "OP Hi 30", "OP Med 40", "OP Lo 30", "OP Lo 10", "INV Lo 10", "INV Lo 30", "INV Hi 30", "INV Hi 10"):
        print(fmt(k + " held", score(rs[k], m, d, split, eras), eras))
    print(fmt("top momentum decile held (the sleeve, reference)", score(mo, m, d, split, eras), eras))
    print(fmt("dip sleeve alone (insurance off inside, reference)", score(dip, m, d, split, eras), eras))

    # ---------------- Q3: quality as a sleeve ----------------
    q = rs["OP Hi 30"]; ks = next(k for k, t in enumerate(d[1:]) if t >= split)
    cx = lambda x, y: tuple(np.corrcoef(x[sl], y[sl])[0, 1] for sl in (slice(None), slice(0, ks), slice(ks, None)))  # noqa: E731
    c1, c2 = cx(q - m, mo - m), cx(q - m, dip - m)
    print(f"\n=== Q3 — quality (OP Hi 30) as a sleeve beside the book, 63y; correlation of its excess with momentum's {c1[0]:+.2f} ({c1[1]:+.2f} / {c1[2]:+.2f}), with the dip sleeve's {c2[0]:+.2f} ({c2[1]:+.2f} / {c2[2]:+.2f}); de-risked {np.mean(e < 1):.0%}")
    print(hdr(True))
    V = {"dip 40 / mom 60 (the book)": 0.4 * dip + 0.6 * mo, "dip 40 / mom 40 / quality 20 (from momentum)": 0.4 * dip + 0.4 * mo + 0.2 * q, "dip 30 / mom 50 / quality 20 (from both)": 0.3 * dip + 0.5 * mo + 0.2 * q,
         "dip 20 / mom 60 / quality 20 (from the dip sleeve)": 0.2 * dip + 0.6 * mo + 0.2 * q, "dip 40 / mom 0 / quality 60 (quality instead of momentum)": 0.4 * dip + 0.6 * q,
         "dip 40 / mom 40 / OP Hi 10 20 (the decile instead)": 0.4 * dip + 0.4 * mo + 0.2 * rs["OP Hi 10"], "quality 100 % under the exposure rules": q}
    base = None; ok_q3 = {}
    for label, core in V.items():
        s = score(e * core, m, d, split, eras); print(fmt(label, s, eras))
        if base is None: base = s
        else: ok_q3[label] = s["is"] > base["is"] and s["oos"] > base["oos"] and s["sharpe"] >= base["sharpe"] and all(x > y for x, y in zip(s["eras"], base["eras"]))

    # ---------------- Q4: the dip rule on quality portfolios (the B9 gate) ----------------
    print("\n=== Q4 — the live dip rule on French portfolio universes, 63y (3 × 25 %, market residual, insurance ×0.5 from the universe's own breadth): the B9 gate")
    print(hdr(True))
    market = datasets.french_market(); meop = datasets.french_levels("25_Portfolios_ME_OP_5x5_Daily.csv", EXT)
    hi = {k: v for k, v in meop.items() if "OP4" in k or "OP5" in k or "HiOP" in k}; lo = {k: v for k, v in meop.items() if "OP1" in k or "OP2" in k or "LoOP" in k}
    assert len(hi) == 10 and len(lo) == 10, (sorted(hi), sorted(lo))
    dec_cols = ["Lo 10", "Dec 2", "Dec 3", "Dec 4", "Dec 5", "Dec 6", "Dec 7", "Dec 8", "Dec 9", "Hi 10"]
    runs = {}
    for label, uni in (("10 high-profitability (size × OP4–5)", hi), ("10 low-profitability (size × OP1–2)", lo), ("all 25 size × OP", meop), ("10 OP deciles", {k: op[k] for k in dec_cols}),
                       ("10 INV deciles", {k: inv[k] for k in dec_cols}), ("49 industries (the floor, same window)", datasets.french_industries())):
        runs[label] = dip_run(label, market, uni, fd, split, eras)
    sh, sl = runs["10 high-profitability (size × OP4–5)"][0], runs["10 low-profitability (size × OP1–2)"][0]
    gap = (sh["excess"] - sl["excess"], sh["is"] - sl["is"], sh["oos"] - sl["oos"], [x - y for x, y in zip(sh["eras"], sl["eras"])])
    print(f"  high-OP minus low-OP, vs the market: {gap[0]:+.2%} (IS {gap[1]:+.1%} / OOS {gap[2]:+.1%}; eras " + " ".join(f"{x:+.1%}" for x in gap[3]) + ")")
    shb = runs["10 high-profitability (size × OP4–5)"][1]
    ok_b9 = gap[1] >= 0.01 and gap[2] >= 0.01 and all(x >= 0.01 for x in gap[3]) and sh["is"] >= 0 and sh["oos"] >= 0 and shb["is"] >= 0 and shb["oos"] >= 0

    # ---------------- Q5: the crash leg ----------------
    print("\n=== Q5 — the crash leg, 63y: minus the market, peak → trough / the rebound year after the trough (market = absolute)")
    rows = {"market (absolute)": m, "OP Hi 30 held": q, "OP Hi 10 held": rs["OP Hi 10"], "top momentum decile held": mo, "dip sleeve alone": dip, "book (dip 40 / mom 60)": e * (0.4 * dip + 0.6 * mo), "book with quality 20 from momentum": e * (0.4 * dip + 0.4 * mo + 0.2 * q)}
    print(f"{'':40} " + " ".join(f"{c[0]:>14}" for c in CRASHES) + "   (fall / rebound year)")
    for label, rr in rows.items():
        cells = []
        for name, pa, pb in CRASHES:
            if label.startswith("market"):
                lv = np.concatenate([[1.0], np.cumprod(1 + rr)]); ia = next(k for k, x in enumerate(d) if x >= pa); ib = next(k for k, x in enumerate(d) if x >= pb); ic = min(ib + 252, len(lv) - 1)
                cells.append(f"{lv[ib] / lv[ia] - 1:+6.0%} / {lv[ic] / lv[ib] - 1:+5.0%}")
            else:
                cells.append(f"{ep(rr, m, d, pa, pb):+6.0%} / {ep(rr, m, d, pa, pb, rebound=True):+5.0%}")
        print(f"{label:40} " + " ".join(f"{c:>14}" for c in cells))

    # ---------------- Q6: the decade, investable ----------------
    _, dd, spy_lvl, rd, bear_d, _, _ = dec; e_d = carry.exposure(bear_d, master.shock_flags(spy_lvl, -0.07, 10, 20))
    qual = rets(datasets.alpaca("QUAL"), dd); dipd, momd, spy = rd["dip"], rd["mom"], rd["mkt"]
    ksd = next(k for k, t in enumerate(dd[1:]) if t >= "2022-01-01")
    cxd = lambda x, y: tuple(np.corrcoef(x[sl], y[sl])[0, 1] for sl in (slice(None), slice(0, ksd), slice(ksd, None)))  # noqa: E731
    c1, c2 = cxd(qual - spy, momd - spy), cxd(qual - spy, dipd - spy)
    print(f"\n=== Q6 — the decade, investable: QUAL (MSCI USA Quality) vs SPY and in the book {dd[0]} → {dd[-1]}, split 2022, '→2025' through 2025-12-31; QUAL's excess vs SPMO's {c1[0]:+.2f} ({c1[1]:+.2f} / {c1[2]:+.2f}), vs the dip sleeve's {c2[0]:+.2f}")
    print(hdr(False) + " | →2025")
    s_qual = score(qual, spy, dd, "2022-01-01"); print(fmt("QUAL held vs SPY", s_qual, None) + f" | {score(qual, spy, dd, '2022-01-01', through=THROUGH)['excess']:+6.2%}")
    print(fmt("SPMO held vs SPY (reference)", score(momd, spy, dd, "2022-01-01"), None) + f" | {score(momd, spy, dd, '2022-01-01', through=THROUGH)['excess']:+6.2%}")
    for label, core in (("dip 40 / SPMO 60 (the book)", 0.4 * dipd + 0.6 * momd), ("dip 40 / SPMO 40 / QUAL 20", 0.4 * dipd + 0.4 * momd + 0.2 * qual), ("dip 30 / SPMO 50 / QUAL 20", 0.3 * dipd + 0.5 * momd + 0.2 * qual),
                        ("dip 40 / SPMO 0 / QUAL 60", 0.4 * dipd + 0.6 * qual)):
        print(fmt(label, score(e_d * core, spy, dd, "2022-01-01"), None) + f" | {score(e_d * core, spy, dd, '2022-01-01', through=THROUGH)['excess']:+6.2%}")
    ok_q6 = s_qual["is"] > 0 and s_qual["oos"] > 0

    # ---------------- the pre-registered verdict ----------------
    print("\n=== pre-registered verdict")
    print("  Q3 (a quality sleeve beats the 40 / 60 book on return in both halves and every era, Sharpe no lower): " + "; ".join(f"{k.split(' (')[0]}: {'ok' if v else 'no'}" for k, v in ok_q3.items()))
    print(f"  Q6 (an investable vehicle, QUAL, beat SPY in both decade halves): {'holds' if ok_q6 else 'FAILS'}")
    print(f"  → a quality sleeve: {'PROPOSED' if any(ok_q3.values()) and ok_q6 else 'NO'}")
    print(f"  B9 gate (high-OP dip run beats low-OP by ≥ 1 pp/yr in both halves and every era, and is ≥ 0 vs the market and vs its EW hold in both halves): {'OPENS' if ok_b9 else 'CLOSED'}")


if __name__ == "__main__":
    main()
