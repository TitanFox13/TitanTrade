"""Gold over a century (roadmap B7; Decision 079 research, 2026-10-30).

A permanent 10 % gold sleeve was tested on the decade alone (Decision 068 addendum, brainstorm #12): −0.3 pp/yr of
return for 1.7 points of drawdown and +0.08 of Sharpe, on a decade in which gold made about 13 % a year — not adopted,
"no century data for gold". The Decision 072 library has datahub's monthly gold price from 1833 (monthly averages,
`external/misc/gold_monthly.csv`). The honest window is the floating era: gold was a fixed-price currency until
August 1971 (a 69 % revaluation in 1934 and nothing else), so before 1971 a gold sleeve is cash with one jump. This
test asks whether the decade's Sharpe gain was the 2020s or a property gold has had for fifty-five years.

Design, fixed before the first run: the century book (dip on the 49 industries 40 / top momentum decile 60, exposure =
min(insurance ×0.5, shock ×0.5), idle capital at 0) on **1971-09 → 2026-08** (split 1998-07-01, eras 1971–2000 /
2000–26), the full 1927 → window reported with its caveat; the ETF book on the decade with GLD (daily, dividend-
adjusted; the earlier result reproduced). Gold enters as a daily step series: each month's average price becomes
known on the first session of the following month and holds until the next (the volatility is understated and the
returns lumpy; a long-held sleeve's ranking against the book is unaffected within noise). Sleeves: gold 10 % taken
from the momentum sleeve (dip 40 / mom 50 / gold 10), from the dip sleeve (30 / 60 / 10), 20 % from both (30 / 50 /
20), and gold *outside* the exposure rules (the sleeve never de-risked); gold as the de-risk destination (the idle
1 − e share in gold instead of cash; references cash, bills from `carry`, the market); no placebo — an asset held
is carry, not a signal (Decision 068 addendum #1's standard).

Pre-registered hypotheses (the expected numbers were written before the first run):
  G1  gold alone, 1971 →: 7 … 9 %/yr nominal against the market's 11 … 12, a volatility near the market's, a monthly
      correlation with the market of −0.1 … +0.1, and a drawdown of about −70 % (1980 → 2001); positive in the first
      era (1971–2000: the 1970s) and the second (2000–26) and negative in the two decades between.
  G2  a 10 % sleeve from the momentum sleeve, 1971 →: −0.2 … −0.5 pp/yr against the book, the drawdown 1 … 3 points
      shallower, the Sharpe +0.01 … +0.04; the first half (1971–98) negative because of 1980–98, the second half
      positive — not both halves, as on the decade (IS −0.5 … −0.8 / OOS +2.7 … +3.2 there).
  G3  gold as the de-risk destination: +0.2 … +0.6 pp/yr against cash over 1971 → (gold rose in 1973–74 and 2020, was
      flat in 2022 and fell in 2008's first leg), inside ±0.3 of the bills line, the drawdown within 2 points.
  G4  the decade with GLD reproduces Decision 068's numbers (−0.3 return, Sharpe +0.08, DD −18.3) to the decimal.
  G5  the century does *not* agree with the decade: the Sharpe gain of the 2020s is not present in 1980–2000, and no
      sleeve variant is ahead of the book in both halves of 1971 →.

Drop rules, written first:
  - a Decision (a permanent gold sleeve) only if a variant beats the book on return in both halves of 1971 → *and* in
    both eras with a Sharpe no lower — the momentum-sleeve bar; a Sharpe gain bought with return is a dial, not a
    result, and the operator's stated preference is return (Decision 068);
  - gold as the de-risk destination is proposed only if it beats the *bills* line in both halves with the drawdown
    within 2 points — the Decision 074 standard for the idle half;
  - otherwise gold stays closed (C3 instruments), with the century number recorded so it is not re-proposed.

Addendum, pre-registered after the first run and before the second (2026-10-30). The sleeves failed as expected
(every variant −0.2 … −0.9 pp/yr for a better Sharpe, not both halves). The de-risk destination did not: the idle
half in gold read +4.71 against bills' +3.34 over 1971 →, both halves, with a shallower drawdown — the pre-registered
bar on the letter. Two things the first run shows about that number: the first half's lead is one episode (1973–74,
when gold rose 186 % while the book was de-risked, +67 against the market vs +25 in bills), the 1975–2000 era is
*behind* bills (+3.5 vs +4.2), and on the decade the drawdown is 3 points deeper than cash. Before any record, two
checks, written first:
  A1  the timing placebo: the de-risked windows are fixed; gold's daily returns are block-shuffled (63 sessions, 50
      draws) so the windows receive random stretches of gold's own history — if "idle in gold" sits inside that
      spread, the gain is gold's unconditional return at a 12 % average weight, not a crisis property; expected: the
      real line above the placebo's median and below its 90th percentile (prior 40 % that it clears the 90th);
  A2  without 1973–74: the same lines from 1975-01 → (split 2000-09, eras 1975–2000 / 2000–26); expected: idle in gold
      behind bills in the first half and ahead in the second — one episode carried the pass.
Rule for the destination, sharpened: gold as the de-risk destination is *proposed* only if A1 clears the placebo's
90th percentile and A2 beats bills in both halves; otherwise it is recorded as a candidate and folded into B8 (bonds
as the de-risk destination), where cash, bills, bonds and gold are judged together on the same windows with the same
placebo — the destination is one question, not three.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/gold.py [--addendum]
"""
import bisect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402
from intl import cagr_r, rets  # noqa: E402
from putwrite import cut, ep, fmt, hdr, score  # noqa: E402
from stress import ERAS4, era_dd  # noqa: E402

FLOAT_START, SPLIT71 = "1971-09-01", "1998-07-01"
ERAS71 = [("1971-09-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]
EPS71 = [("1973-74", "1973-01-11", "1974-10-03"), ("1980-82", "1980-11-28", "1982-08-12"), ("1987", "1987-08-25", "1987-12-04"), ("2000-02", "2000-03-24", "2002-10-09"), ("2008", "2007-10-09", "2009-03-09"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12")]
EPS_DEC = [("2018Q4", "2018-09-20", "2018-12-24"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12"), ("2025", "2025-02-19", "2025-04-08")]


def gold_monthly():
    out = {}
    for line in open(f"{datasets.S}/external/misc/gold_monthly.csv").read().splitlines()[1:]:
        d, v = line.split(",")[:2]
        try: out[d] = float(v)
        except ValueError: pass
    return out


def gold_step(dd):
    """Each month's average price known on the first session of the following month → a daily level on dd."""
    rows = []
    for ym, v in sorted(gold_monthly().items()):
        y, m = int(ym[:4]), int(ym[5:7]); m2 = m + 1; y2 = y + (m2 - 1) // 12; m2 = (m2 - 1) % 12 + 1; rows.append((f"{y2:04d}-{m2:02d}-01", v))
    avail = [r[0] for r in rows]; lv = np.full(len(dd), np.nan)
    for i, d in enumerate(dd):
        k = bisect.bisect_right(avail, d) - 1
        if k >= 0: lv[i] = rows[k][1]
    return lv


def monthly_corr(r1, r2, dd):
    months = {}
    for t, a, b in zip(dd[1:], r1, r2):
        m = months.setdefault(t[:7], [1.0, 1.0]); m[0] *= 1 + a; m[1] *= 1 + b
    x = np.array([v[0] - 1 for v in months.values()]); y = np.array([v[1] - 1 for v in months.values()]); return np.corrcoef(x, y)[0, 1]


def panel(title, dd, r, e, rg, rf, split, eras, eps, through=None):
    core = 0.4 * r["dip"] + 0.6 * r["mom"]; m = r["mkt"]
    sc = lambda rr: score(rr, m, dd, split, eras)  # noqa: E731
    def line(label, rr, base=None):
        s = sc(rr); extra = " ".join(f"{ep(rr, m, dd, a, b):+5.0%}/{ep(rr, m, dd, a, b, rebound=True):+4.0%}" for _, a, b in eps)
        gain = f" {s['excess'] - base['excess']:+6.2%}" if base else f" {'':>7}"
        print(fmt(label, s, eras).replace(" | ", gain + " | ", 1) + (f" | →2025 {score(rr, m, dd, split, eras, through=through)['excess']:+6.2%}" if through else "") + " | " + extra)
        if eras: print(f"{'':60} era DD: " + " ".join(f"{x:6.1%}" for x in era_dd(rr, dd, eras)))
        return s
    print(f"\n=== {title}: {dd[0]} → {dd[-1]}; columns: excess vs the market, gain vs the book, IS, OOS | σ/σm | DD, market DD | Sharpe, market | worst year | " + ("eras" if eras else "roll3") + " | episodes (book − market, fall / rebound year)")
    print(hdr(bool(eras)).replace(f"{'excess':>7}", f"{'excess':>7} {'gain':>7}") + " | " + " ".join(f"{x[0]:>10}" for x in eps))
    out = {}
    g = line(f"gold alone ({cagr_r(rg):+.1%}/yr vs the market {cagr_r(m):+.1%}/yr; monthly corr. with the market {monthly_corr(rg, m, dd):+.2f})", rg)
    out["gold"] = g
    b = line("the book: dip 40 / mom 60, idle at 0", e * core); out["book"] = b
    for label, rr in (("gold 10 from the momentum sleeve (40 / 50 / 10)", e * (0.4 * r["dip"] + 0.5 * r["mom"] + 0.1 * rg)), ("gold 10 from the dip sleeve (30 / 60 / 10)", e * (0.3 * r["dip"] + 0.6 * r["mom"] + 0.1 * rg)),
                      ("gold 20 from both (30 / 50 / 20)", e * (0.3 * r["dip"] + 0.5 * r["mom"] + 0.2 * rg)), ("gold 10 outside the exposure rules", e * (0.4 * r["dip"] + 0.5 * r["mom"]) + 0.1 * rg)):
        out[label] = line(label, rr, b)
    print("--- the de-risk destination (the idle 1 − e share)")
    out["bills"] = line("idle in bills (the carry line)", e * core + (1 - e) * rf, b)
    out["idle gold"] = line("idle in gold", e * core + (1 - e) * rg, b)
    line("idle in the market", e * core + (1 - e) * m, b)
    return out


def main():
    g = gold_monthly(); print("gold, monthly average $/oz at the regime points: " + ", ".join(f"{k} {g.get(k, float('nan')):.2f}" for k in ("1933-01", "1934-02", "1971-07", "1971-09", "1974-12", "1980-01", "2001-04", "2011-09", "2020-08", "2026-09")))
    dec, cen = carry.sets(); rf = carry.rf_daily()
    # ---------------- 1971-09 → : the floating era ----------------
    _, fd, mk, rc, bear_c, _, _ = cen; shock_c = master.shock_flags(mk, -0.07, 10, 20); e_c = carry.exposure(bear_c, shock_c)
    glv = gold_step(fd); rg_full = np.nan_to_num(glv[1:] / glv[:-1] - 1)
    d, rs = cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "e": e_c, "g": rg_full}, FLOAT_START, "2026-08-31")
    R71 = panel("B7 — the floating era", d, {k: rs[k] for k in ("dip", "mom", "mkt")}, rs["e"], rs["g"], carry.align_rf(d, rf), SPLIT71, ERAS71, EPS71)
    # ---------------- 1927 → : the full century, gold = fixed-price cash before 1971 ----------------
    d0, rs0 = cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "e": e_c, "g": rg_full}, "1927-07-01", "2026-08-31")
    panel("B7 — the full century (gold a fixed-price currency before 1971: cash with the 1934 jump)", d0, {k: rs0[k] for k in ("dip", "mom", "mkt")}, rs0["e"], rs0["g"], carry.align_rf(d0, rf), "1975-01-01", ERAS4, [("1929-32", "1929-09-03", "1932-06-01")] + EPS71[:1] + EPS71[4:5])
    # ---------------- the decade with GLD ----------------
    _, dd, spy, rd, bear_d, split_d, _ = dec; e_d = carry.exposure(bear_d, master.shock_flags(spy, -0.07, 10, 20)); gld = rets(datasets.alpaca("GLD"), dd)
    RD = panel("B7 — the decade with GLD (daily)", dd, {k: rd[k] for k in ("dip", "mom", "mkt")}, e_d, gld, carry.align_rf(dd, rf), split_d, None, EPS_DEC, through="2025-12-31")
    # ---------------- the pre-registered verdict ----------------
    b = R71["book"]; bl = R71["bills"]; ig = R71["idle gold"]
    print("\n=== pre-registered verdict (1971-09 → 2026-08)")
    ok_sleeve = {}
    for label in ("gold 10 from the momentum sleeve (40 / 50 / 10)", "gold 10 from the dip sleeve (30 / 60 / 10)", "gold 20 from both (30 / 50 / 20)", "gold 10 outside the exposure rules"):
        s = R71[label]; ok_sleeve[label] = s["is"] > b["is"] and s["oos"] > b["oos"] and all(x > y for x, y in zip(s["eras"], b["eras"])) and s["sharpe"] >= b["sharpe"]
        print(f"  {label}: {s['excess']:+.2%} vs the book {b['excess']:+.2%}; halves {s['is']:+.1%} / {s['oos']:+.1%} vs {b['is']:+.1%} / {b['oos']:+.1%}; Sharpe {s['sharpe']:.2f} vs {b['sharpe']:.2f}; DD {s['dd']:.1%} vs {b['dd']:.1%} → {'passes' if ok_sleeve[label] else 'no'}")
    ok_dest = ig["is"] > bl["is"] and ig["oos"] > bl["oos"] and ig["dd"] >= b["dd"] - 0.02
    print(f"  idle in gold {ig['excess']:+.2%} ({ig['is']:+.1%} / {ig['oos']:+.1%}), DD {ig['dd']:.1%} vs bills {bl['excess']:+.2%} ({bl['is']:+.1%} / {bl['oos']:+.1%}) and cash DD {b['dd']:.1%} → {'passes' if ok_dest else 'no'}")
    bd, gd = RD["book"], RD["gold 10 from the momentum sleeve (40 / 50 / 10)"]
    print(f"  the decade reproduced: gold 10 from SPMO {gd['excess'] - bd['excess']:+.2%} of return, Sharpe {gd['sharpe']:.2f} vs {bd['sharpe']:.2f}, DD {gd['dd']:.1%} vs {bd['dd']:.1%} (Decision 068: −0.32, 1.18 vs 1.10, −18.3 vs −20.0)")
    print(f"  → {'DECISION PROPOSED' if any(ok_sleeve.values()) or ok_dest else 'NO — gold stays closed; the decade was the 2020s'}")


def main_addendum():
    from breadth2 import block_shuffle
    rng = np.random.default_rng(79); _, cen = carry.sets(); rf = carry.rf_daily()
    _, fd, mk, rc, bear_c, _, _ = cen; e_c = carry.exposure(bear_c, master.shock_flags(mk, -0.07, 10, 20)); glv = gold_step(fd); rg_full = np.nan_to_num(glv[1:] / glv[:-1] - 1)
    out = {}
    for a, split, eras, label in ((FLOAT_START, SPLIT71, ERAS71, "1971 →"), ("1975-01-02", "2000-09-01", [("1975-01-02", "2000-01-01"), ("2000-01-01", "2026-09-01")], "1975 → (without 1973–74)")):
        d, rs = cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "e": e_c, "g": rg_full}, a, "2026-08-31"); e, rg, m = rs["e"], rs["g"], rs["mkt"]; core = 0.4 * rs["dip"] + 0.6 * rs["mom"]; rfd = carry.align_rf(d, rf)
        sc = lambda rr: score(rr, m, d, split, eras)  # noqa: E731
        book = e * core; sb, sbl, sg = sc(book), sc(book + (1 - e) * rfd), sc(book + (1 - e) * rg)
        draws = np.array([sc(book + (1 - e) * block_shuffle(rg, rng))["excess"] for _ in range(50)])
        on = e < 1
        print(f"\n=== addendum, {label} {d[0]} → {d[-1]}: gold {np.mean(rg[on]) * 252:+.1%}/yr while the book is de-risked ({np.mean(on):.0%} of sessions) vs {np.mean(rg) * 252:+.1%}/yr overall; the market {np.mean(m[on]) * 252:+.1%}/yr while de-risked")
        for lab, s in (("book, idle in cash", sb), ("idle in bills", sbl), ("idle in gold", sg)):
            print(f"  {lab:22} {s['excess']:+.2%} ({s['is']:+.1%} / {s['oos']:+.1%}), DD {s['dd']:.1%}, Sharpe {s['sharpe']:.2f}; eras " + " ".join(f"{x:+.1%}" for x in s["eras"]))
        print(f"  A1 placebo (gold's returns block-shuffled, 50 draws): median {np.median(draws):+.2%} [p10 {np.percentile(draws, 10):+.2%} … p90 {np.percentile(draws, 90):+.2%}]; idle in gold {sg['excess']:+.2%} is above {np.mean(sg['excess'] > draws):.0%} of draws")
        out[label] = (sb, sbl, sg, draws)
    sb, sbl, sg, draws = out["1971 →"]; sb2, sbl2, sg2, _ = out["1975 → (without 1973–74)"]
    a1 = sg["excess"] > np.percentile(draws, 90); a2 = sg2["is"] > sbl2["is"] and sg2["oos"] > sbl2["oos"]
    print(f"\n=== the destination's verdict: A1 placebo p90 {'cleared' if a1 else 'NOT cleared'}; A2 from 1975 beats bills in both halves {'yes' if a2 else 'no'} ({sg2['is']:+.1%} / {sg2['oos']:+.1%} vs {sbl2['is']:+.1%} / {sbl2['oos']:+.1%}) → {'PROPOSED' if a1 and a2 else 'a candidate — folded into B8 (the de-risk destination judged with bonds and bills)'}")


if __name__ == "__main__":
    main_addendum() if "--addendum" in sys.argv else main()
