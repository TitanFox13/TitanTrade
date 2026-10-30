"""Quality ETFs as vehicles (Decision 075 addendum; operator: "fetch quality funds first", 2026-10-30).

Decision 075 found the quality premium real over 63 years (the most profitable 30 % of the market +1.2 pp/yr in every
era, conservative investment +2.2) and a near-pass for quality in place of half the dip sleeve on the century — and no
investable form: QUAL, the one quality ETF in the library, lost to SPY in both decade halves. This test asks whether
any other US-listed quality fund captures the premium. **The candidate list was fixed before any price was fetched**
(every quality-labelled US equity ETF on Alpaca with SIP history from 2016, so both decade halves exist): SPHQ
(Invesco S&P 500 Quality), QUAL (MSCI USA Quality, already in the library), VIG (dividend appreciation), DGRW
(quality dividend growth), DGRO (core dividend growth), QDF and QDEF (FlexShares quality dividend), QUS (MSCI USA
StrategicFactors: quality + value + low volatility), FQAL (Fidelity quality factor), COWZ (free-cash-flow yield —
quality / value hybrid), MOAT (Morningstar wide moat), and JQUA (JPMorgan quality factor, listed 2017-11, so its
first half is ten months short — reported with that caveat). Dimensional's and Avantis's profitability-tilted funds
are too young (2019 / 2021 →) for both halves and are left out. Bars: Alpaca SIP, ``adjustment=all`` (dividend-
adjusted, like every file in the archive — never a split-only fetch), ``alpaca_hist/quality/``, archived on
titanserver. Decade 2017-01-03 → 2026-10-12, split 2022-01-01, every headline through 2025-12-31 beside full; a fund
listed later is scored from its first bar (SIP coverage: MOAT 2016-05, FQAL 2016-09, COWZ 2016-12, JQUA 2017-11).

Pre-registered hypotheses (the expected numbers were written before the fetch):
  V1  the era first: the French top-30 %-profitability portfolio itself vs the French market over the same decade —
      if the premium's hindsight-free form lagged in 2017–2026 (expected: −1 … +1, a mega-cap-growth decade), then
      every fund lagging is the era, not the vehicle. Then the funds: 0 … 3 of the 12 beat SPY in both halves;
      the dividend-growth family (VIG, DGRW, DGRO, QDF, QDEF) lags by 1 … 3 pp/yr (a value tilt in a growth decade),
      SPHQ and FQAL within ±1.5 of SPY, COWZ −2 … +2 with a strong 2022, MOAT and QUS ±2.
  V2  a fund that passes V1 must *be* quality: its daily excess over SPY regressed on French RMW (daily, through
      2026-08) has a positive loading with t > 2, and its correlation with QUAL's excess is > 0.3; a fund that beats
      SPY with a zero or negative RMW loading is a growth or momentum fund in disguise and does not count.
  V3  the sleeve, with each survivor: dip 20 / SPMO 60 / Q 20 (quality in place of half the dip sleeve — the century
      near-pass) and dip 40 / SPMO 40 / Q 20, judged against the live book (+1.36; +0.3 / +2.5; Sharpe 1.10; → 2025
      +0.80): a Decision only if a variant beats the book on return in both halves *and* through 2025, with a Sharpe
      no lower. Expected: with no vehicle above SPY the sleeve costs 0.5 … 1.5 pp/yr (Decision 075 Q6).

The luck caveat, written first: with 12 candidates and roughly a one-in-four chance that any one fund beats SPY in
both halves by luck, three passes are expected by chance alone — which is why V2 (the factor loading) and the
through-2025 check are part of the bar, and why a survivor would still be one decade of evidence behind the century's
+1.2.

Drop rules, written first:
  - no fund passes V1 and V2 → the quality door stays closed; nothing more to do without new data (recorded).
  - a fund passes V1 and V2 but V3 fails → recorded, no sleeve; the vehicle is named for a later era.
  - V1, V2 and V3 pass → a Decision is *proposed* (the expected numbers, the vehicle, the slot taken from the dip
    sleeve, a new clean window), never applied without the operator's go.

Costs: the ETF series carry their expense ratios; the dip run charges 0.05 % a side; blends rebalance daily without
cost. Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/quality_etfs.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402
from intl import rets  # noqa: E402
from putwrite import cut, fmt, hdr, score  # noqa: E402

CANDIDATES = ["SPHQ", "QUAL", "VIG", "DGRW", "DGRO", "QDF", "QDEF", "QUS", "FQAL", "COWZ", "MOAT", "JQUA"]
THROUGH, SPLIT, START = "2025-12-31", "2022-01-01", "2017-01-03"
EXT = "external/french"


def series(sym):
    return datasets.alpaca(sym, "historical_long" if sym == "QUAL" else "quality")


def ols(y, xs):
    """OLS with an intercept: betas and t-statistics (plain standard errors)."""
    X = np.column_stack([np.ones(len(y))] + xs); b = np.linalg.lstsq(X, y, rcond=None)[0]; res = y - X @ b
    s2 = res @ res / (len(y) - X.shape[1]); se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X))); return b, b / se


def main():
    dec, _ = carry.sets(); _, dd, spy_lvl, rd, bear_d, _, _ = dec
    e = carry.exposure(bear_d, master.shock_flags(spy_lvl, -0.07, 10, 20)); dip, mom, spy = rd["dip"], rd["mom"], rd["mkt"]
    s_book = score(e * (0.4 * dip + 0.6 * mom), spy, dd, SPLIT); t_book = score(e * (0.4 * dip + 0.6 * mom), spy, dd, SPLIT, through=THROUGH)

    # ---------------- V1: the era, then the funds ----------------
    print("=== V1a — the era: the French profitability portfolios vs the French market over the same decade (2017-01-03 → 2026-08-31, split 2022)")
    market = datasets.french_market(); fdates = sorted(market); op = datasets.french_levels("Portfolios_Formed_on_OP_Daily.csv", EXT); inv = datasets.french_levels("Portfolios_Formed_on_INV_Daily.csv", EXT)
    fd, frs = cut(fdates, {"mkt": rets(market, fdates), "OP Hi 30": rets(op["Hi 30"], fdates), "OP Hi 10": rets(op["Hi 10"], fdates), "INV Lo 30": rets(inv["Lo 30"], fdates)}, START, "2026-08-31")
    print(hdr(False).replace("| roll3", "| roll3 | →2025"))
    for k in ("OP Hi 30", "OP Hi 10", "INV Lo 30"):
        print(fmt(f"French {k} held vs the French market", score(frs[k], frs["mkt"], fd, SPLIT), None) + f" | {score(frs[k], frs['mkt'], fd, SPLIT, through=THROUGH)['excess']:+6.2%}")
    print("\n=== V1b — the funds held vs SPY, each from its first bar ≥ 2017-01-03 (excess CAGR; IS → 2021 / OOS 2022 →; '→2025' through 2025-12-31)")
    print(hdr(False).replace("| roll3", "| roll3 | →2025 | from"))
    raw = {s: series(s) for s in CANDIDATES}; f5 = datasets.french_factors("F-F_Research_Data_5_Factors_2x3_daily.csv", EXT); rmw = f5["RMW"]
    qual_x = rets(raw["QUAL"], dd) - spy; res = {}
    for s in CANDIDATES:
        first = min(d for d in raw[s] if d >= START); d, rs = cut(dd, {"x": rets(raw[s], dd), "spy": spy}, first, dd[-1])
        sc = score(rs["x"], rs["spy"], d, SPLIT); tc = score(rs["x"], rs["spy"], d, SPLIT, through=THROUGH)
        print(fmt(f"{s} held vs SPY", sc, None) + f" | {tc['excess']:+6.2%} | {first}")
        res[s] = dict(first=first, s=sc, t=tc, v1=sc["is"] > 0 and sc["oos"] > 0)
    print(fmt("SPMO held vs SPY (reference)", score(mom, spy, dd, SPLIT), None) + f" | {score(mom, spy, dd, SPLIT, through=THROUGH)['excess']:+6.2%} | {dd[0]}")

    # ---------------- V2: is it quality? ----------------
    print("\n=== V2 — is the fund quality? Daily excess over SPY regressed on French RMW and on SPMO's excess (OLS, intercept); correlation with QUAL's excess")
    print(f"{'fund':8} {'β RMW':>7} {'t':>6} | {'β SPMO-x':>8} {'t':>6} | {'α /yr':>7} | {'corr QUAL':>9} | {'days':>5}")
    for s in CANDIDATES:
        first = res[s]["first"]; x = rets(raw[s], dd) - spy; mx = mom - spy
        idx = [k for k, t in enumerate(dd[1:]) if t >= first and t in rmw]; y = x[idx]; xr = np.array([rmw[dd[1:][k]] for k in idx]); xm = mx[idx]
        b, t = ols(y, [xr, xm]); c = np.corrcoef(x[[k for k, tt in enumerate(dd[1:]) if tt >= first]], qual_x[[k for k, tt in enumerate(dd[1:]) if tt >= first]])[0, 1] if s != "QUAL" else 1.0
        res[s].update(b_rmw=b[1], t_rmw=t[1], corr_qual=c, v2=b[1] > 0 and t[1] > 2 and c > 0.3)
        print(f"{s:8} {b[1]:+7.2f} {t[1]:6.1f} | {b[2]:+8.2f} {t[2]:6.1f} | {b[0] * 252:+7.1%} | {c:+9.2f} | {len(y):5d}")
    survivors = [s for s in CANDIDATES if res[s]["v1"] and res[s]["v2"]]
    print(f"  pass V1 (both halves > 0): {[s for s in CANDIDATES if res[s]['v1']]}; pass V2 (β RMW > 0, t > 2, corr QUAL > 0.3): {[s for s in CANDIDATES if res[s]['v2']]}; survivors: {survivors}")

    # ---------------- V3: the sleeve ----------------
    top2 = sorted(CANDIDATES, key=lambda s: -res[s]["s"]["excess"])[:2]
    print(f"\n=== V3 — the sleeve on the decade, vs SPY (survivors, plus the two best by full-period excess marked 'not a survivor'); the book: {s_book['excess']:+.2%} ({s_book['is']:+.1%} / {s_book['oos']:+.1%}), Sharpe {s_book['sharpe']:.2f}, → 2025 {t_book['excess']:+.2%}")
    print(hdr(False).replace("| roll3", "| roll3 | →2025"))
    print(fmt("dip 40 / SPMO 60 (the book)", s_book, None) + f" | {t_book['excess']:+6.2%}")
    ok_v3 = {}
    for s in dict.fromkeys(survivors + top2):
        tag = "" if s in survivors else " (not a survivor)"; q = rets(raw[s], dd); first = res[s]["first"]
        for label, core in ((f"dip 20 / SPMO 60 / {s} 20 (from the dip sleeve){tag}", 0.2 * dip + 0.6 * mom + 0.2 * q), (f"dip 40 / SPMO 40 / {s} 20 (from momentum){tag}", 0.4 * dip + 0.4 * mom + 0.2 * q)):
            d, rs = cut(dd, {"r": e * core, "spy": spy, "b": e * (0.4 * dip + 0.6 * mom)}, first, dd[-1])
            sc = score(rs["r"], rs["spy"], d, SPLIT); tc = score(rs["r"], rs["spy"], d, SPLIT, through=THROUGH); sb = score(rs["b"], rs["spy"], d, SPLIT); tb = score(rs["b"], rs["spy"], d, SPLIT, through=THROUGH)
            print(fmt(label, sc, None) + f" | {tc['excess']:+6.2%}")
            if s in survivors: ok_v3[label] = sc["is"] > sb["is"] and sc["oos"] > sb["oos"] and tc["excess"] > tb["excess"] and sc["sharpe"] >= sb["sharpe"]

    # ---------------- the pre-registered verdict ----------------
    print("\n=== pre-registered verdict")
    print(f"  V1: {sum(res[s]['v1'] for s in CANDIDATES)} of 12 beat SPY in both halves ({[s for s in CANDIDATES if res[s]['v1']]}); expected 0 … 3 by luck alone ≈ 3")
    print(f"  V2 survivors (quality by loading and correlation): {survivors if survivors else 'none'}")
    print("  V3: " + ("; ".join(f"{k.split(' (')[0]}: {'ok' if v else 'no'}" for k, v in ok_v3.items()) if ok_v3 else "not reached — no survivor"))
    print(f"  → a quality sleeve: {'PROPOSED' if any(ok_v3.values()) else 'NO — the quality door stays closed'}")


if __name__ == "__main__":
    main()
