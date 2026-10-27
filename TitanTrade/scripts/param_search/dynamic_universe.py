"""A dip universe that is not hand-picked — long-term, self-correcting (operator question, 2026-10-27)

Pre-registered hypotheses, written before any result was seen:
  U1  Multi-asset ETFs. The live rule on 28 ETFs — the 11 SPDR sectors + GLD TLT IEF EEM EFA IWM VNQ DBC LQD HYG SLV +
      XBI SMH ITB KRE XOP IBB — 2017 →, 3 × 25 % and 5 × 15 % slots; subsets: equity ETFs (17) and multi-asset (22).
      Breadth stays the 11 sectors (as live). Expectation: lower drawdown, excess vs SPY at or below the sector floor
      (+0.4) because bonds and commodities lagged equities this decade; judged against SPY and the equal-weight universe.
  U2  Stop cooldown 60 / 120 / 250 sessions (`fastbt.stop_cooldown_days`: a stopped name is excluded for months) on the
      point-in-time S&P 500 (3 × 25 % and 10 × 7.5 %), the sectors and the 49 industries. Expectation: repairs part of
      the broad-universe adverse selection (the stopped names are the blow-ups); no effect where stops are rare.
  U3  Eligibility = the name's own trailing 12-month return > 0, and the mirror < 0, inside the dip rule on the same
      universes. Expectation: > 0 is negative on the S&P (a winner's dip is its break — Decision 066 found −14 on the
      top-15 momentum names); the mirror (a loser that is back above its 150-day SMA) is an open hypothesis.
Costs 0.05 % per side; IS / OOS at 2022-01-01 (decade) and 1975 (century); through-2025 beside full where 2026 could
dominate; every row against SPY and against the equal-weight hold of the same universe.
Run: uv run --with numpy python -I scripts/param_search/dynamic_universe.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402
import screens  # noqa: E402

LIVE = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12,
            slot_pct=0.25, max_slots=3, insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=0.5)
MULTI = ["GLD", "TLT", "IEF", "EEM", "EFA", "IWM", "VNQ", "DBC", "LQD", "HYG", "SLV"]
INDUSTRY = ["XBI", "SMH", "ITB", "KRE", "XOP", "IBB"]


def cagr(c):
    return fastbt.metrics(c, [])["cagr"]


def ew_curve(mkt, i0, i1, mask=None):
    """Equal-weight, daily-rebalanced hold of every name with a price (and in `mask`), from i0."""
    P = mkt.names; r = P[1:] / P[:-1] - 1; out = [1.0]
    for i in range(i0 + 1, i1 + 1):
        ok = ~np.isnan(r[i - 1]) & ~np.isnan(P[i - 1])
        if mask is not None:
            ok &= mask[i - 1]
        out.append(out[-1] * (1 + (r[i - 1][ok].mean() if ok.any() else 0.0)))
    return np.array(out)


def row(label, mkt, params, start, split, ew=None, to=None, mask=None):
    r = fastbt.run(mkt, params, start, to, want_trades=True)
    c, s = r["_curve"], r["_spy_curve"]; d = mkt.dates[mkt.dates.index(r["start"]):]
    ks = next(k for k, x in enumerate(d) if x >= split)
    m, sp = r["metrics"], r["spy"]
    i0 = mkt.dates.index(r["start"]); e = ew_curve(mkt, i0, i0 + len(c) - 1, mask)
    print(f"{label:46} {m['cagr'] - sp['cagr']:+6.1%} ({cagr(c[:ks + 1]) - cagr(s[:ks + 1]):+5.1%}/{cagr(c[ks:]) - cagr(s[ks:]):+5.1%}) "
          f"vs EW {m['cagr'] - cagr(e):+6.1%} (EW vs SPY {cagr(e) - sp['cagr']:+5.1%}) | DD {m['max_drawdown']:6.1%}/{sp['max_drawdown']:6.1%} Sh {m['sharpe']:4.2f}/{sp['sharpe']:4.2f} | "
          f"{r['n_trades']:4d} tr, win {m['win_rate'] or 0:3.0%}, med {np.median([t['return'] for t in r['trades']]) if r['trades'] else 0:+.1%}, stops {m['exits']['stop']:3d}")
    return r


def header():
    print(f"{'universe / variant':46} {'vs SPY':>6} {'(IS/OOS)':>13} {'vs EW':>12} {'':>14} | {'DD':>13} {'Sharpe':>9} | trades")


def u1():
    print("=== U1 multi-asset ETF universe, live rule, insurance x0.5, 2017-01 → (breadth = the 11 sectors)")
    header()
    spy = datasets.alpaca("SPY"); sect = {s: datasets.alpaca(s) for s in datasets.SECT}
    sets = {"11 sectors (reference floor)": list(datasets.SECT), "17 equity ETFs (sectors + industries)": datasets.SECT + INDUSTRY,
            "22 multi-asset (sectors + bonds/gold/intl/...)": datasets.SECT + MULTI, "28 all": datasets.SECT + MULTI + INDUSTRY,
            "11 multi-asset only (no sectors)": MULTI}
    for label, syms in sets.items():
        mkt = fastbt.Market(spy, {s: datasets.alpaca(s) for s in syms}, sect)
        for slots, slot in ((3, 0.25), (5, 0.15)):
            p = dict(LIVE, max_slots=slots, slot_pct=slot)
            row(f"{label} {slots}x{slot:.0%}", mkt, p, "2017-01-03", "2022-01-01")
        row(f"{label} 3x25% through 2025", mkt, dict(LIVE), "2017-01-03", "2022-01-01", to="2025-12-31")


def own_mom_mask(mkt, sign):
    P = mkt.names; T, N = P.shape; m = np.zeros((T, N), dtype=bool)
    with np.errstate(invalid="ignore"):
        r12 = P[252:] / P[:-252] - 1
    m[252:] = (r12 > 0) if sign > 0 else (r12 < 0)
    m &= ~np.isnan(P)
    return m


def u2_u3():
    e_mkt, member = screens.load_universe(); d_mkt = datasets.load("D_alpaca_sectors_2016"); f_mkt = datasets.load("F_french_49ind_1926")
    sets = [("E S&P 500 point-in-time 3x25%", e_mkt, member, "2017-01-03", "2022-01-01", 3, 0.25),
            ("E S&P 500 point-in-time 10x7.5%", e_mkt, member, "2017-01-03", "2022-01-01", 10, 0.075),
            ("D 11 sectors 3x25%", d_mkt, None, "2017-01-03", "2022-01-01", 3, 0.25),
            ("F 49 industries 3x25%", f_mkt, None, "1927-07-01", "1975-01-01", 3, 0.25)]
    print("\n=== U2 stop cooldown (sessions a stopped name stays ineligible; 0 = live 72 h) — insurance x0.5")
    header()
    for label, mkt, mask, start, split, slots, slot in sets:
        for cd in (0, 60, 120, 250):
            p = dict(LIVE, max_slots=slots, slot_pct=slot, stop_cooldown_days=cd)
            if mask is not None:
                p["eligible"] = mask
            row(f"{label} cooldown {cd}", mkt, p, start, split, mask=mask)
    print("\n=== U3 eligibility by the name's own 12-month return (none / > 0 / < 0) — insurance x0.5")
    header()
    for label, mkt, mask, start, split, slots, slot in sets:
        for ename, sign in (("none", 0), ("12m > 0", 1), ("12m < 0", -1)):
            p = dict(LIVE, max_slots=slots, slot_pct=slot)
            el = None if sign == 0 else own_mom_mask(mkt, sign)
            if mask is not None:
                el = mask if el is None else (el & mask)
            if el is not None:
                p["eligible"] = el
            row(f"{label} elig {ename}", mkt, p, start, split, mask=el if sign else mask)
        if label.startswith("E") or label.startswith("D"):
            for ename, sign in (("12m > 0", 1), ("12m < 0", -1)):
                p = dict(LIVE, max_slots=slots, slot_pct=slot); el = own_mom_mask(mkt, sign)
                if mask is not None:
                    el &= mask
                p["eligible"] = el
                row(f"{label} elig {ename} through 2025", mkt, p, start, split, to="2025-12-31", mask=el)
    print("\n=== U2 × U3 on the S&P 500: cooldown 120 with each eligibility (interaction check)")
    header()
    for label, mkt, mask, start, split, slots, slot in sets[:2]:
        for ename, sign in (("12m > 0", 1), ("12m < 0", -1)):
            el = own_mom_mask(mkt, sign) & mask
            row(f"{label} cooldown 120 + elig {ename}", mkt, dict(LIVE, max_slots=slots, slot_pct=slot, stop_cooldown_days=120, eligible=el), start, split, mask=el)


if __name__ == "__main__":
    u1(); u2_u3()
