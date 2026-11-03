"""Rates by era — the carry on idle capital and the insurance's cost priced on the bill rate of each era (roadmap B4;
Decision 087 research, 2026-11-03).

The book parks a share of its capital in cash whenever the insurance or the shock trigger halves exposure (and 5 % always,
the reserve). What that cash earns is carry, not a signal — nothing to fit. Decision 068's addendum priced bills over the
whole decade (+0.17 pp/yr) and the whole century (+0.5); Decision 080 chose the vehicle (a 1–3-year Treasury ETF beats
bills by +0.3). What is still unpriced is the *level*: how much the leg is worth when rates are 0 and when they are 5 %,
era by era, whether the book is de-risked when rates are high or when they have just been cut, and what the leg is worth
at today's rate for the go-live checklist — against Alpaca's cash programme, which pays on every idle dollar without an
order. Data, all free and in the library: Kenneth French's daily bill return 1926 → (`books.rf_daily`), FRED's 3-month
bill rate 1954 → (`DTB3`, the cross-check) and CPI 1947 → (the real rate, for the record). The book = min(insurance ×0.5,
shock ×0.5) × (0.4 dip + 0.6 momentum) on `books.sets()`: the century 1927-07 → (the four eras) and the ETF decade 2017 →.
Two rate series, on purpose: the carry is compounded on Kenneth French's *daily* bill return (the series Decisions 068 and
080 used, so the pickups reproduce), but that series is published to 0.01 % per *day* — three distinct values (0, 2.5,
5.0 %/yr) across the whole decade — so the *level* of rates (the bins, the rate while de-risked, the real rate) is read
from FRED's daily 3-month bill from 1954 and French's *monthly* bill rate before (0.01 % per month), and the carry is
shown on that level series too as the cross-check (a correction made after the first run showed empty rate bins).

Pre-registered hypotheses (the expected numbers were written before the first run):
  R1  the bill rate by era (French RF): 1927–50 ≈ 0.6 %/yr, 1950–75 ≈ 3.5, 1975–2000 ≈ 6.5, 2000–26 ≈ 1.6; French and
      FRED agree within 0.2 pp/yr over 1954 →; the real rate (bills − CPI inflation) was negative in the 1940s, the 1970s,
      2009–15 and 2020–22 — reported, irrelevant to the verdict (the book and SPY are both nominal).
  R2  the de-risked share of capital (mean of 1 − e) is 15–20 % over the century, 8–12 % on the decade; the bill rate
      *while de-risked* is below the era's mean in every era since 1950 by 0.5–2 pp (the Fed eases into bears), about
      equal in 1927–50 (rates near zero throughout): the carry is least when the book needs it.
  R3  the pickup by era: 1927–50 ≈ +0.1, 1950–75 +0.5 … +0.8, 1975–2000 +0.8 … +1.2, 2000–26 +0.2 … +0.3; the century
      ≈ +0.5 and the decade +0.17 reproduce Decision 068's addendum to the hundredth (the same arithmetic).
  R4  binned by the prevailing rate (0–1 / 1–3 / 3–5 / > 5 %), the in-bin pickup is ≈ idle share × rate: ≈ 0 at 0–1,
      ≈ +0.3 at 1–3, ≈ +0.7 at 3–5, +1.2 … +1.8 above 5; the idle share is largest in the lowest bin.
  R5  at a constant rate the leg's value is linear: on the century's idle share ≈ +0.8 … +1.0 pp/yr at 5 %, 0 at 0 %; on
      the decade's ≈ +0.4 … +0.6 at 5 %; at today's bill rate (≈ 4 %) with the decade's idle share ≈ +0.3 … +0.5.
  R6  the switches' cost priced on rates: with idle capital at 0 the two switches cost the decade ≈ 1.6 pp/yr (Decision 068)
      and gain the century ≈ +1; crediting bills shrinks the decade's cost by ≈ 0.2 and lifts the century's gain by ≈ 0.5;
      at a constant 5 % the switches' cost falls by the idle share × 5 ≈ 0.5 (decade) … 0.9 (century) pp/yr.
  R7  the go-live number: with Alpaca's cash programme enrolled (≈ 3.5 % on every idle dollar, the reserve included, no
      orders) the ETF leg's *increment* is (its yield − the programme's rate) × the idle share ≈ +0.05 … +0.1 pp/yr for
      SHY, ≈ 0 for SGOV; without the programme the leg is worth the whole carry of R5 (+0.3 … +0.5 at today's rate) plus
      nothing on the reserve (it must stay spendable).

What would make it a Decision (written first): nothing here is a sleeve or a rule — the outcome is one number for the
go-live checklist (Decision 071 / C5). Rule: recommend the cash programme alone, with the `cash_ticker` leg left off, if
the ETF leg's increment over the programme at today's rate and the decade's idle share is below 0.1 pp/yr; recommend the
leg (SHY, Decision 080) on top of the programme if the increment is 0.1 or more; recommend the leg regardless if the
programme turns out not to be available to the account (an operator check, not a research one). The level of rates does
not change Decision 080's vehicle choice (a relative result) and is not a reason to switch the insurance off.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/rates.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import master  # noqa: E402
from books import align_rf, exposure, rf_daily, sets  # noqa: E402
from stress import fred  # noqa: E402

PROGRAMME = 0.0356       # Alpaca High-Yield Cash, the rate read on the dashboard 2026-10-29 (Decision 071)
SGOV_DRAG, SHY_PICKUP = 0.0009, 0.003   # SGOV's expense ratio; the 2-year's edge over bills (Decision 080)
BINS = [(0, 1), (1, 3), (3, 5), (5, 99)]
LEVELS = [0.0, 0.01, 0.02, 0.03, 0.04, 0.05]


def french_monthly_rf():
    """Kenneth French's monthly bill rate, percent per month, by 'YYYY-MM' (the monthly factors file; dates are YYYYMM)."""
    lines = open(f"{datasets.S}/external/french/F-F_Research_Data_Factors.csv", encoding="latin-1").read().splitlines()
    h = next(k for k, ln in enumerate(lines) if ln.startswith(",Mkt-RF")); out = {}
    for ln in lines[h + 1:]:
        if not ln[:1].isdigit(): break
        parts = [x.strip() for x in ln.split(",")]; out[f"{parts[0][:4]}-{parts[0][4:6]}"] = float(parts[-1])
    return out


def rate_level(dd):
    """The bill rate as an annual decimal on each return day dd[1:]: FRED's 3-month bill from 1954-01-04 (a missing day
    carries the last reading), Kenneth French's monthly 1-month bill × 12 before that."""
    dtb = fred("DTB3"); fm = french_monthly_rf(); out = np.zeros(len(dd) - 1); last = np.nan
    for k, x in enumerate(dd[1:]):
        if x >= "1954-01-04":
            last = dtb.get(x, last); out[k] = last / 100
        else:
            out[k] = fm[x[:7]] * 12 / 100
    return out


def inflation(a, b):
    """CPI inflation, %/yr, averaged over [a, b): the 12-month change, monthly; NaN before 1948."""
    cpi = fred("CPIAUCSL"); ds = sorted(cpi)
    ys = [cpi[d] / cpi[ds[k - 12]] - 1 for k, d in enumerate(ds) if k >= 12 and a <= d < b]
    return float(np.mean(ys)) if ys else np.nan


def main():
    rf = rf_daily()
    for name, dd, lvl, r, bear, split, eras in sets():
        rfd = align_rf(dd, rf); lv = rate_level(dd); lvd = (1 + lv) ** (1 / 252) - 1
        shock = master.shock_flags(lvl, -0.07, 10, 20); e = exposure(bear, shock); idle = 1 - e
        core = 0.4 * r["dip"] + 0.6 * r["mom"]; base = e * core
        d1 = np.array(dd[1:]); ks = next(k for k, d in enumerate(dd[1:]) if d >= split)
        panels = [("whole", np.ones(len(rfd), bool)), ("first half", np.arange(len(rfd)) < ks), ("second half", np.arange(len(rfd)) >= ks)]
        panels += [(f"{a[:4]}–{b[:4]}", (d1 >= a) & (d1 < b)) for a, b in (eras or [])]
        sc = lambda rr, **kw: master.score(rr, r["mkt"], dd, split, eras, **kw)  # noqa: E731
        print(f"\n=== rates by era — {name} {dd[0]} → {dd[-1]}: de-risked {np.mean(e < 1):.1%} of sessions, idle capital {np.mean(idle):.1%} of the book on average")
        # R1 / R2: the rate (the French daily carry series and the level series), the real rate, the idle share, the rate while de-risked
        print(f"  {'window':12} {'French daily':>12} {'level':>7} {'infl.':>6} {'real':>6} | {'idle':>5} {'rate while idle':>15} {'gap':>6} | {'< 1 %':>6}")
        for label, m in panels:
            if not m.any(): continue
            a, b = d1[m][0], d1[m][-1]; infl = inflation(a, b); mean_lv = np.mean(lv[m])
            while_idle = np.sum(idle[m] * lv[m]) / max(np.sum(idle[m]), 1e-9)
            print(f"  {label:12} {np.mean(rfd[m]) * 252:12.2%} {mean_lv:7.2%} {infl:6.1%} {mean_lv - infl:+6.1%} | {np.mean(idle[m]):5.1%} {while_idle:15.2%} {while_idle - mean_lv:+6.2%} | {np.mean(lv[m] < 0.01):6.0%}")
        # R3: the pickup by window, compounded through master.score, on both rate series; the luck meter on the book lines
        sb, sc_, sl = sc(base, luck_draws=400), sc(base + idle * rfd, luck_draws=400), sc(base + idle * lvd)
        print(f"  the book, idle at 0:      excess {sb['excess']:+.2%}  IS {sb['is']:+.2%}  OOS {sb['oos']:+.2%}" + (f"  eras {' '.join(f'{x:+.1%}' for x in sb['eras'])}" if eras else "") + f"  | {master.luck_line(sb)}")
        print(f"  the book, idle in bills:  excess {sc_['excess']:+.2%}  IS {sc_['is']:+.2%}  OOS {sc_['oos']:+.2%}" + (f"  eras {' '.join(f'{x:+.1%}' for x in sc_['eras'])}" if eras else "") + f"  | {master.luck_line(sc_)}")
        print(f"  pickup (French daily): whole {sc_['excess'] - sb['excess']:+.2%}, IS {sc_['is'] - sb['is']:+.2%}, OOS {sc_['oos'] - sb['oos']:+.2%}" + (f", eras {' '.join(f'{y - x:+.2%}' for x, y in zip(sb['eras'], sc_['eras']))}" if eras else ""))
        print(f"  pickup (level series): whole {sl['excess'] - sb['excess']:+.2%}, IS {sl['is'] - sb['is']:+.2%}, OOS {sl['oos'] - sb['oos']:+.2%}" + (f", eras {' '.join(f'{y - x:+.2%}' for x, y in zip(sb['eras'], sl['eras']))}" if eras else ""))
        # R4: by the prevailing rate (the level series)
        print(f"  {'rate bin':10} {'sessions':>8} {'idle':>6} {'pickup/yr':>10}   (in-bin, annualised: mean(idle × rate))")
        for lo, hi in BINS:
            m = (lv >= lo / 100) & (lv < hi / 100)
            if m.any(): print(f"  {f'{lo}–{hi} %' if hi < 99 else f'> {lo} %':10} {np.mean(m):8.1%} {np.mean(idle[m]):6.1%} {np.mean(idle[m] * lv[m]):+10.2%}")
        # R5: constant rates, per window (arithmetic idle × rate, which is the compounded pickup to the hundredth)
        print(f"  {'leg at a constant rate':24} " + " ".join(f"{int(x * 100):>5} %" for x in LEVELS) + "   (pp/yr: idle share × rate)")
        for label, m in panels:
            if m.any(): print(f"  {label:24} " + " ".join(f"{np.mean(idle[m]) * x:+7.2%}" for x in LEVELS))
        # R6: the switches' cost priced on rates — each switch alone and both, with idle capital at 0 and in bills
        sn = sc(core)
        print(f"  {'the switches vs none':34} {'idle at 0':>10} {'in bills':>10}" + ("   eras at 0 | in bills" if eras else ""))
        for label, ee in (("insurance only", np.where(bear, 0.5, 1.0)), ("shock only", np.where(shock, 0.5, 1.0)), ("both (the live rule, min)", e)):
            s0, s1 = sc(ee * core), sc(ee * core + (1 - ee) * rfd)
            print(f"  {label:34} {s0['excess'] - sn['excess']:+10.2%} {s1['excess'] - sn['excess']:+10.2%}" + (f"   {' '.join(f'{x - y:+.1%}' for x, y in zip(s0['eras'], sn['eras']))} | {' '.join(f'{x - y:+.1%}' for x, y in zip(s1['eras'], sn['eras']))}" if eras else ""))
        print("  both, at a constant rate: " + ", ".join(f"{int(x * 100)} % {sb['excess'] - sn['excess'] + np.mean(idle) * x:+.2%}" for x in (0.0, 0.03, 0.05)))
        if name == "decade":
            today = [v for k, v in sorted(fred("DTB3").items())][-1] / 100; share = np.mean(idle)
            print(f"\n=== the go-live number (the decade's idle share {share:.1%}, the reserve 5 % apart; today's 3-month bill {today:.2%})")
            print(f"  the cash programme alone ({PROGRAMME:.2%} on every idle dollar, no orders): idle {share * PROGRAMME:+.2%}/yr + the reserve {0.05 * PROGRAMME:+.2%} = {(share + 0.05) * PROGRAMME:+.2%}")
            for label, y in (("SGOV (bills − expense)", today - SGOV_DRAG), ("SHY (bills + the 2-year's edge, Decision 080)", today + SHY_PICKUP)):
                print(f"  {label:46}: on its own {share * y:+.2%}/yr; increment over the programme {share * (y - PROGRAMME):+.2%}")
            print("  the pre-registered rule: increment < 0.1 → the programme alone, the leg off; ≥ 0.1 → the leg on top; the leg regardless if the programme is unavailable")


if __name__ == "__main__":
    main()
