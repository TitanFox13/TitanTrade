"""The momentum sleeve outside the switches (operator, 2026-11-05, after the drill's forced shock sold SPMO to 28 %:
"what would happen if we moved momentum to 60 % at the expense of our protection"). Read as: the momentum sleeve held
at its full 60 % through everything — the two-signal insurance and the shock trigger scale the dip sleeve only. The
book is the harness blend every Decision 067 → 101 number came from (`books.sets()`: the sector dip sleeve through
fastbt with the live rule and costs, SPMO on the decade 2017 →, the French top momentum decile on the century 1927 →,
the market, the previous-session insurance flag, the shock flags; de-risked capital earns 0 — a bias against every
switch). The blend charges no cost on the switches' own trades, which trade LESS in the exempt variants — a bias
against them. The package engine is not run: it applies one scale to both legs and 091 showed blend ≈ engine.

Variants, each 40 % dip sleeve / 60 % momentum: V0 the live book — min(insurance ×0.5, shock ×0.5) on both legs;
V1 momentum outside both switches (the question); V2 momentum outside the insurance only (the shock still sells it);
V3 momentum outside the shock only (the insurance still sells it); V4 neither switch anywhere (Decision 087's row).

Hypotheses, written before the run (the 087 addendum's on / off rows are the anchors: decade live +1.36, DD −20.0,
Sharpe 1.10, neither switch +4.53 / −31.9 / 1.06; century live +3.63, DD −58.6, Sharpe 0.86, eras +4.6 +5.5 +3.3 +1.2,
neither +3.43 / −81.9 / 0.70):
  M1 decade — V1 excess +2.5 … +3.5 (the momentum leg carries 60 % of the switches' 3.2 pp/yr cost here), both halves
     above V0's, DD −27 … −31 (2020 held in full), Sharpe 1.00 … 1.08 (below V0), worst relative year −8 … −12.
     V2 +2.0 … +2.8 with DD −20 … −23 (the shock still catches 2020), Sharpe ≈ V0's.
  M2 century — V1 +3.0 … +3.7 (the switches are worth ≈ +0.2 of return here and 23 points of drawdown), DD −70 … −78
     (1929–32 held through the decile's −80), Sharpe 0.72 … 0.78, the 1927–50 era below V0's +4.6 (expected +2 … +3.5),
     the 2000 → era at or below +1.2 (2000–02 and 2008–09 held in full), worst relative year −28 … −35 (1932 / 2009).
     V2 +3.3 … +3.7, DD −62 … −66.
  M3 placebo — V0's momentum leg under block-shuffled exposure of the same on-share (63-session blocks, 20 draws), the
     dip sleeve under the real switches: on the decade V0 sits INSIDE the placebo's 10–90 % band (the cost on momentum
     this decade is the cost of less exposure, not of bad timing); on the century V0 is ABOVE the 90th percentile on
     excess and far above on drawdown (1929 / 1973 / 2008 are timed, not random).
  M4 luck — V1 − V0: decade t +0.3 … +0.9, P(excess > 0) 65 … 80 % (noise); century t −0.5 … +0.3, P 40 … 60 %.
Drop rule (the Decision 098 bar): the exemption becomes a proposal only if V1 (or V2) beats V0 on return in both halves
on both windows and in every era on the century, with a Sharpe no lower than V0's on both windows. Expected: FAILS
(the century's first era and the Sharpe on both windows). Failing that it is a read-out of the operator's risk line
(C1), recorded like Decision 091: the decade's +1.5 … +2 against a fall 8 … 11 points deeper on the decade and
12 … 20 deeper on the century; V2 as the variant that keeps the shock's drawdown control. Nothing changes live.
Run: uv run --with numpy python -I scripts/param_search/momexempt.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import books  # noqa: E402
import master  # noqa: E402
from breadth2 import block_shuffle  # noqa: E402

W = 0.6
EPISODES = {"decade": [("2018Q4", "2018-09-20", "2018-12-24"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12"), ("2025", "2025-02-19", "2025-04-08")],
            "century": [("1929-32", "1929-09-03", "1932-06-01"), ("1973-74", "1973-01-11", "1974-10-03"), ("1987", "1987-08-25", "1987-12-04"), ("2000-02", "2000-03-24", "2002-10-09"),
                        ("2007-09", "2007-10-09", "2009-03-09"), ("2009reb", "2009-03-09", "2010-03-09"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12")]}


def variants(r, bear, shock):
    ins = np.where(bear, 0.5, 1.0); sh = np.where(shock, 0.5, 1.0); e = np.minimum(ins, sh)
    dip = (1 - W) * r["dip"]; mom = W * r["mom"]
    return {"V0 live: both switches on both legs": e * dip + e * mom,
            "V1 momentum outside both switches": e * dip + mom,
            "V2 momentum outside the insurance (shock still sells it)": e * dip + sh * mom,
            "V3 momentum outside the shock (insurance still sells it)": e * dip + ins * mom,
            "V4 neither switch anywhere": dip + mom}, e, dip, mom


def episode(r, dates, a, b):
    c = np.concatenate([[1.0], np.cumprod(1 + r)])
    ia = next(k for k, d in enumerate(dates) if d >= a); ib = max(k for k, d in enumerate(dates) if d <= b)
    return c[ib] / c[ia] - 1


def row(label, s, luck=False):
    tail = " ".join(f"{x:+5.1%}" for x in s["eras"]) if "eras" in s else f"roll3 {s['roll3_pos']:.0%}"
    out = f"  {label:58} {s['excess']:+6.2%} {s['is']:+6.2%} / {s['oos']:+6.2%} | {s['dd']:6.1%} {s['sharpe']:5.2f} {s['worst_year']:+6.1%} | {tail}"
    return out + (f"\n  {'':58} {master.luck_line(s)}" if luck else "")


def main():
    rng = np.random.default_rng(7)
    for name, dd, lvl, r, bear, split, eras in books.sets():
        shock = books.shock_flags(lvl, -0.07, 10, 20)
        V, e, dip, mom = variants(r, bear, shock)
        sm = master.score(r["mkt"], r["mkt"], dd, split, eras)
        print(f"\n=== {name} {dd[0]} → {dd[-1]} (market DD {sm['dd']:.1%}, Sharpe {sm['mkt_sharpe']:.2f}; insurance on {bear.mean():.0%} of sessions, shock on {shock.mean():.0%})")
        print(f"  {'book':58} {'excess':>6} {'IS':>6} / {'OOS':>6} | {'DD':>6} {'Sharpe':>5} {'worst':>6} | " + ("eras" if eras else "roll3"))
        S = {}
        for k, rr in V.items():
            S[k] = master.score(rr, r["mkt"], dd, split, eras, luck_draws=400 if k[:2] in ("V0", "V1") else 0)
            print(row(k, S[k], luck=k[:2] in ("V0", "V1")))
        v0, v1, v2 = list(V.values())[:3]
        d = master.score(v1, v0, dd, split, eras, luck_draws=400)
        print(f"  V1 against V0 (the live book as the benchmark): {d['excess']:+.2%} (IS {d['is']:+.2%} / OOS {d['oos']:+.2%}" + (f"; eras {' '.join(f'{x:+.1%}' for x in d['eras'])}" if eras else "") + f"); {master.luck_line(d)}")
        d2 = master.score(v2, v0, dd, split, eras)
        print(f"  V2 against V0: {d2['excess']:+.2%} (IS {d2['is']:+.2%} / OOS {d2['oos']:+.2%}" + (f"; eras {' '.join(f'{x:+.1%}' for x in d2['eras'])}" if eras else "") + ")")
        pl = [master.score(e * dip + block_shuffle(e, rng) * mom, r["mkt"], dd, split, eras) for _ in range(20)]
        ex = np.array([p["excess"] for p in pl]); dds = np.array([p["dd"] for p in pl])
        print(f"  placebo (V0's momentum leg under block-shuffled exposure, same on-share, 20 draws): excess median {np.median(ex):+.2%}, 10–90 % {np.percentile(ex, 10):+.2%} … {np.percentile(ex, 90):+.2%}; DD median {np.median(dds):.1%}, 10–90 % {np.percentile(dds, 10):.1%} … {np.percentile(dds, 90):.1%} — V0 {S[list(V)[0]]['excess']:+.2%} / {S[list(V)[0]]['dd']:.1%}")
        print(f"  the big falls (peak → trough over the episode's dates; the market, then V0 / V1 / V2):")
        for lab, a, b in EPISODES[name]:
            if a < dd[0]: continue
            print(f"    {lab:8} market {episode(r['mkt'], dd, a, b):+6.1%} | V0 {episode(v0, dd, a, b):+6.1%}  V1 {episode(v1, dd, a, b):+6.1%}  V2 {episode(v2, dd, a, b):+6.1%}")


if __name__ == "__main__":
    main()
