"""The de-risk destination — cash, bills, bonds and gold judged together (roadmap B8; Decision 080 research, 2026-10-30).

When the insurance or the shock trigger halves exposure, the idle half earns 0 in the research engine (a deliberate
bias against de-risking rules) and in the paper book; at go-live it earns the bank sweep or SGOV's bill yield
(Decision 071). Decision 068's addendum priced bills (+0.17 pp/yr on the decade, +0.5 on the century); Decision 074
tried a protective put (worse drawdown); Decision 079 found gold as the parking place beat bills over 1971 → on the
strength of 1973–74 alone. This test asks the whole question once: with the idle half in cash, bills, a Treasury
bond, gold, or a half-and-half mix, which parking place does the book best — judged on both halves, every era the
data allows, the drawdown leg, and a timing placebo for each asset. Data, all in the library: Kenneth French's daily
bill return (1926 →), FRED's constant-maturity Treasury yields (10-year from 1962, 2-year from 1976) turned into daily
total returns by repricing a par bond (coupon = yesterday's yield, priced at today's yield, plus the accrual), the
gold step series of Decision 079, and on the decade the ETFs IEF (7–10-year), TLT (20-year+), GLD and the bill return.

Windows: **1971-09 → 2026-08** (all four destinations; split 1998-07, eras 1971–2000 / 2000–26); **1962-01 → 2026-08**
(cash, bills, the 10-year; split 1994-05, eras 1962–75 / 1975–2000 / 2000–26); the ETF decade 2017 → 2026-10 (split
2022, through 2025 beside full). The 2-year is shown from 1976 inside the 1971 window (cash before). The book =
min(insurance ×0.5, shock ×0.5) × (0.4 dip + 0.6 momentum), the destination = the (1 − e) share. A bond *sleeve*
(10 % permanent, from the momentum sleeve) is one reference line, the question closed on the decade by 2022.

Pre-registered hypotheses (the expected numbers were written before the first run):
  D1  the destinations alone, 1971 →: bills ≈ 4.5 %/yr, the 2-year ≈ 5.5, the 10-year 6.5 … 7.5 with a −20 … −25 %
      drawdown (2020 → 2023), gold 8.6 with −62 %; daily correlation with the market: bills 0, the 10-year ≈ +0.1
      over the whole window (positive before 2000, negative after — the regime), gold ≈ 0.
  D2  the idle half in the 10-year beats bills by +0.3 … +0.8 pp/yr over 1971 → — bonds rallied in 2000–02, 2008 and
      2020 — ahead in the second half and about even in the first (1973–74 and 1980–82 were bond bears too), with the
      drawdown within 2 points of cash's and 2022 the one episode it loses (bonds fell with stocks). On 1962 → the
      1962–75 era is behind bills (the inflation decade). At or above its timing placebo's median, below the 90th.
  D3  gold as the destination repeats Decision 079: +1.4 over bills on 1971 → from 1973–74, behind bills in the first
      half from 1975, the placebo's median.
  D4  the 2-year ≈ bills + 0.2 … 0.4, drawdown within 1 point — the carry with a little duration.
  D5  the mixes (bills 50 / gold 50; the 10-year 50 / gold 50) +0.3 … +0.8 over bills with the drawdown within 2
      points — the diversified parking place — and not ahead in both halves (gold's 1980–98).
  D6  the decade: IEF idle ≈ bills (±0.3) with a deeper drawdown in 2022, TLT worse, GLD +1.5 (the 2020s).
  D7  no destination beats bills in every era available: bonds lose 1962–75, gold loses 1975–2000.

Drop rules, written first:
  - a Decision (the idle capital's destination at go-live — the `cash_ticker` leg already exists for any ticker — set
    to a bond or gold ETF instead of the sweep / SGOV) only if that destination beats the *bills* line in both halves
    of 1971 → *and* in every era the data allows, with a drawdown within 2 points of cash's, *and* above its timing
    placebo's 90th percentile — the Decision 074 / 079 standard, both legs;
  - otherwise bills stand (the sweep or SGOV at go-live, Decision 071), the question is closed with the numbers, and
    the bond sleeve stays closed.

Addendum, pre-registered after the first run and before the second (2026-10-30). On the letter the first run passed
three destinations — the 2-year (+0.26 over bills), bills 50 / gold 50 (+0.72) and the 10-year 50 / gold 50 (+1.13) —
and failed the 10-year on the 1962–75 era alone (by 0.3) and gold alone on its placebo (by 0.04); the passes clear
their placebos' 90th percentiles by 0.10 … 0.19, inside what fifty draws can resolve, and every gold line inherits
1973–74, which Decision 079 showed to be the whole of gold's stress-window advantage. One check, written before it runs:
  A1  the same panel from **1975-01 → 2026-08** (split 2000-09, eras 1975–2000 / 2000–26), without 1973–74: a
      destination is proposed only if it also beats bills in both halves there, in both eras, with the drawdown
      within 2 points of cash and above its timing placebo's 90th percentile. Expected: the 2-year keeps its
      +0.2 … +0.3 (carry, not timing) and passes; the gold mixes fall to the placebo's median and fail; the 10-year
      keeps +0.5 … +0.8 over bills (2000–02, 2008, 2020) with 2022 against it and clears the placebo — the one
      destination whose timing information does not rest on 1973–74, failing the strict rule only on the 1962–75
      era where the data reaches and it does not.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/destination.py [--from1975]
"""
import bisect
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402
from breadth2 import block_shuffle  # noqa: E402
from gold import gold_step  # noqa: E402
from intl import cagr_r, rets  # noqa: E402
from putwrite import cut, ep, fmt, hdr, score  # noqa: E402
from stress import era_dd, fred  # noqa: E402

W71 = ("1971-09-01", "2026-08-31", "1998-07-01", [("1971-09-01", "2000-01-01"), ("2000-01-01", "2026-09-01")])
W62 = ("1962-01-02", "2026-08-31", "1994-05-01", [("1962-01-02", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")])
EPS = [("1973-74", "1973-01-11", "1974-10-03"), ("1980-82", "1980-11-28", "1982-08-12"), ("1987", "1987-08-25", "1987-12-04"), ("2000-02", "2000-03-24", "2002-10-09"), ("2008", "2007-10-09", "2009-03-09"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12")]
EPS_DEC = [("2018Q4", "2018-09-20", "2018-12-24"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12"), ("2025", "2025-02-19", "2025-04-08")]


def bond_rets(yields, dd, T):
    """Daily total return of a constant-maturity par Treasury on dd[1:]: yesterday's coupon repriced at today's yield plus
    the accrual over the calendar days between sessions; yields in percent; NaN where the series has not started."""
    ds = sorted(yields); y = np.full(len(dd), np.nan)
    for i, d in enumerate(dd):
        k = bisect.bisect_right(ds, d) - 1
        if k >= 0 and (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(ds[k])).days <= 10: y[i] = yields[ds[k]] / 100
    out = np.full(len(dd) - 1, np.nan); n = 2 * T
    for i in range(1, len(dd)):
        y0, y1 = y[i - 1], y[i]
        if np.isnan(y0) or np.isnan(y1): continue
        c, r = y0 / 2, y1 / 2; price = c * (1 - (1 + r) ** (-n)) / r + (1 + r) ** (-n) if r > 1e-9 else 1 + c * n
        out[i - 1] = price - 1 + y0 * (datetime.date.fromisoformat(dd[i]) - datetime.date.fromisoformat(dd[i - 1])).days / 365
    return out


def panel(title, dd, r, e, dests, split, eras, eps, rng, through=None, sleeve=None):
    """dests: {label: daily returns on dd[1:]} — the idle (1 − e) half in each; a placebo for every asset but cash and the market."""
    core = 0.4 * r["dip"] + 0.6 * r["mom"]; m = r["mkt"]; book = e * core
    sc = lambda rr: score(rr, m, dd, split, eras)  # noqa: E731
    print(f"\n=== {title}: {dd[0]} → {dd[-1]}; de-risked {np.mean(e < 1):.0%} of sessions")
    print("--- the destinations alone: CAGR, σ relative to the market, drawdown, Sharpe, daily correlation with the market, excess vs the market by era")
    for label, x in dests.items():
        if label in ("cash", "the market"): continue
        s = sc(x); print(f"  {label:26} {cagr_r(x):+6.1%}/yr  σ/σm {s['vol_ratio']:4.2f}  DD {s['dd']:6.1%}  Sharpe {s['sharpe']:5.2f}  corr {np.corrcoef(x, m)[0, 1]:+.2f}" + (f"  eras " + " ".join(f"{v:+.1%}" for v in s["eras"]) if eras else ""))
    print("--- the book with the idle half in each destination: excess vs the market, gain vs bills, IS, OOS | σ/σm | DD, market DD | Sharpe | worst year | " + ("eras" if eras else "roll3") + (" | →2025" if through else "") + " | episodes (fall / rebound) | placebo")
    print(hdr(bool(eras)).replace(f"{'excess':>7}", f"{'excess':>7} {'vs bills':>8}") + (" |  →2025" if through else "") + " | " + " ".join(f"{x[0]:>9}" for x in eps))
    out = {}; s_bills = sc(book + (1 - e) * dests["bills"])
    for label, x in dests.items():
        rr = book + (1 - e) * x; s = sc(rr); pl = None
        if label not in ("cash", "the market"):
            pl = np.array([sc(book + (1 - e) * block_shuffle(x, rng))["excess"] for _ in range(50)])
        line = fmt(f"idle in {label}", s, eras).replace(" | ", f" {s['excess'] - s_bills['excess']:+8.2%} | ", 1)
        if through: line += f" | {score(rr, m, dd, split, eras, through=through)['excess']:+6.2%}"
        line += " | " + " ".join(f"{ep(rr, m, dd, a, b):+4.0%}/{ep(rr, m, dd, a, b, rebound=True):+4.0%}" for _, a, b in eps)
        if pl is not None: line += f" | {np.median(pl):+5.2%} [{np.percentile(pl, 10):+5.2%}…{np.percentile(pl, 90):+5.2%}] beaten {np.mean(s['excess'] > pl):3.0%}"
        print(line)
        if eras: print(f"{'':60} era DD: " + " ".join(f"{v:6.1%}" for v in era_dd(rr, dd, eras)))
        out[label] = (s, pl, era_dd(rr, dd, eras) if eras else None)
    if sleeve is not None:
        s = sc(e * (0.4 * r["dip"] + 0.5 * r["mom"] + 0.1 * sleeve)); print(fmt("reference: a permanent 10 % 10-year sleeve from momentum", s, eras).replace(" | ", f" {s['excess'] - out['cash'][0]['excess']:+8.2%} | ", 1) + " (vs the book)")
    return out


def main():
    rng = np.random.default_rng(80); rf = carry.rf_daily(); y10, y2 = fred("DGS10"), fred("DGS2")
    dec, cen = carry.sets(); _, fd, mk, rc, bear_c, _, _ = cen; e_c = carry.exposure(bear_c, master.shock_flags(mk, -0.07, 10, 20))
    glv = gold_step(fd); rg_full = np.nan_to_num(glv[1:] / glv[:-1] - 1); b10_full = bond_rets(y10, fd, 10); b2_full = bond_rets(y2, fd, 2)
    results = {}
    for name, (a, b, split, eras), with_gold in (("1971 →", W71, True), ("1962 →", W62, False)):
        d, rs = cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "e": e_c, "g": rg_full, "b10": b10_full, "b2": b2_full}, a, b)
        bills = carry.align_rf(d, rf); b10 = np.nan_to_num(rs["b10"]); b2 = np.nan_to_num(rs["b2"]); g = rs["g"]
        dests = {"cash": np.zeros(len(d) - 1), "bills": bills, "the 10-year": b10}
        if with_gold: dests.update({"the 2-year (from 1976)": b2, "gold": g, "bills 50 / gold 50": 0.5 * bills + 0.5 * g, "the 10-year 50 / gold 50": 0.5 * b10 + 0.5 * g})
        dests["the market"] = rs["mkt"]
        results[name] = panel(f"B8 — {name}", d, {k: rs[k] for k in ("dip", "mom", "mkt")}, rs["e"], dests, split, eras, [x for x in EPS if x[1] >= a], rng, sleeve=b10)
    _, dd, spy, rd, bear_d, split_d, _ = dec; e_d = carry.exposure(bear_d, master.shock_flags(spy, -0.07, 10, 20)); bills_d = carry.align_rf(dd, rf)
    etf = {k: rets(datasets.alpaca(k), dd) for k in ("IEF", "TLT", "GLD")}
    dests_d = {"cash": np.zeros(len(dd) - 1), "bills": bills_d, "the 2-year (constructed)": np.nan_to_num(bond_rets(y2, dd, 2)), "the 10-year (constructed)": np.nan_to_num(bond_rets(y10, dd, 10)), "IEF (7–10-year)": etf["IEF"], "TLT (20-year+)": etf["TLT"], "GLD": etf["GLD"],
               "bills 50 / GLD 50": 0.5 * bills_d + 0.5 * etf["GLD"], "IEF 50 / GLD 50": 0.5 * etf["IEF"] + 0.5 * etf["GLD"], "the market": rd["mkt"]}
    results["decade"] = panel("B8 — the decade with the ETFs", dd, {k: rd[k] for k in ("dip", "mom", "mkt")}, e_d, dests_d, split_d, None, EPS_DEC, rng, through="2025-12-31")
    # ---------------- the pre-registered verdict ----------------
    R = results["1971 →"]; sb, _, dd_b = R["bills"]; sc_, _, _ = R["cash"]; R62 = results["1962 →"]
    print("\n=== pre-registered verdict (the idle half's destination vs bills on 1971 →; every era the data allows; drawdown within 2 points of cash; above the timing placebo's 90th percentile)")
    passed = []
    for label in ("the 10-year", "the 2-year (from 1976)", "gold", "bills 50 / gold 50", "the 10-year 50 / gold 50"):
        s, pl, _ = R[label]; halves = s["is"] > sb["is"] and s["oos"] > sb["oos"]; eras_ok = all(x > y for x, y in zip(s["eras"], sb["eras"]))
        if label == "the 10-year":
            s62, _, _ = R62["the 10-year"]; sb62, _, _ = R62["bills"]; eras_ok = eras_ok and all(x > y for x, y in zip(s62["eras"], sb62["eras"]))
        dd_ok = s["dd"] >= sc_["dd"] - 0.02; pl_ok = s["excess"] > np.percentile(pl, 90); ok = halves and eras_ok and dd_ok and pl_ok
        print(f"  {label:26} {s['excess']:+.2%} vs bills {sb['excess']:+.2%} ({s['is']:+.1%} / {s['oos']:+.1%} vs {sb['is']:+.1%} / {sb['oos']:+.1%}); eras {'all ahead' if eras_ok else 'not all'}; DD {s['dd']:.1%} vs cash {sc_['dd']:.1%} {'ok' if dd_ok else 'no'}; placebo p90 {np.percentile(pl, 90):+.2%} {'cleared' if pl_ok else 'not cleared'} → {'PASSES' if ok else 'no'}")
        if ok: passed.append(label)
    print(f"  → {'DECISION PROPOSED: ' + ', '.join(passed) if passed else 'NO — bills stand (the sweep or SGOV at go-live); the destination question is closed'}")


def main_1975():
    rng = np.random.default_rng(81); rf = carry.rf_daily(); y10, y2 = fred("DGS10"), fred("DGS2")
    _, cen = carry.sets(); _, fd, mk, rc, bear_c, _, _ = cen; e_c = carry.exposure(bear_c, master.shock_flags(mk, -0.07, 10, 20))
    glv = gold_step(fd); rg_full = np.nan_to_num(glv[1:] / glv[:-1] - 1); b10_full = bond_rets(y10, fd, 10); b2_full = bond_rets(y2, fd, 2)
    a, b, split, eras = "1975-01-02", "2026-08-31", "2000-09-01", [("1975-01-02", "2000-01-01"), ("2000-01-01", "2026-09-01")]
    d, rs = cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "e": e_c, "g": rg_full, "b10": b10_full, "b2": b2_full}, a, b)
    bills = carry.align_rf(d, rf); b10 = np.nan_to_num(rs["b10"]); b2 = np.nan_to_num(rs["b2"]); g = rs["g"]
    dests = {"cash": np.zeros(len(d) - 1), "bills": bills, "the 10-year": b10, "the 2-year (from 1976)": b2, "gold": g, "bills 50 / gold 50": 0.5 * bills + 0.5 * g, "the 10-year 50 / gold 50": 0.5 * b10 + 0.5 * g, "the market": rs["mkt"]}
    R = panel("B8 addendum — 1975 → (without 1973–74)", d, {k: rs[k] for k in ("dip", "mom", "mkt")}, rs["e"], dests, split, eras, [x for x in EPS if x[1] >= a], rng)
    sb, _, _ = R["bills"]; sc_, _, _ = R["cash"]
    print("\n=== the addendum's verdict (1975 →: both halves and both eras ahead of bills, DD within 2 points of cash, above the placebo's 90th percentile)")
    passed = []
    for label in ("the 10-year", "the 2-year (from 1976)", "gold", "bills 50 / gold 50", "the 10-year 50 / gold 50"):
        s, pl, _ = R[label]; halves = s["is"] > sb["is"] and s["oos"] > sb["oos"]; eras_ok = all(x > y for x, y in zip(s["eras"], sb["eras"])); dd_ok = s["dd"] >= sc_["dd"] - 0.02; pl_ok = s["excess"] > np.percentile(pl, 90); ok = halves and eras_ok and dd_ok and pl_ok
        print(f"  {label:26} {s['excess']:+.2%} vs bills {sb['excess']:+.2%} ({s['is']:+.1%} / {s['oos']:+.1%} vs {sb['is']:+.1%} / {sb['oos']:+.1%}); eras {'both ahead' if eras_ok else 'not both'}; DD {s['dd']:.1%} vs cash {sc_['dd']:.1%} {'ok' if dd_ok else 'no'}; placebo median {np.median(pl):+.2%}, p90 {np.percentile(pl, 90):+.2%} {'cleared' if pl_ok else 'not cleared'} → {'PASSES' if ok else 'no'}")
        if ok: passed.append(label)
    print(f"  → on 1975 → as well: {', '.join(passed) if passed else 'none'}")


if __name__ == "__main__":
    main_1975() if "--from1975" in sys.argv else main()
