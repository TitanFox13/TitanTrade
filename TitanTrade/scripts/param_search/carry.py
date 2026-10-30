"""T-bill carry on de-risked capital (Decision 068 addendum, 2026-10-29; brainstorm candidate 1).

The book halves exposure under the insurance or the shock trigger and the idle half earns 0 — in the research engine
by design (a bias against de-risking rules) and in the live book in fact (cash at Alpaca). Holding a T-bill ETF with the
idle half instead is carry, not a signal: nothing to fit, nothing to overfit. Pre-registered hypotheses:
  C1  in a decade like 2017 → 2026 the pickup is +0.1 … +0.3 pp/yr, because the longest de-risked stretch (2020) fell
      in the zero-rate years;
  C2  over the century it is +0.2 … +0.5 pp/yr, concentrated in the high-rate bears (1969–70, 1973–74, 1980–82) and
      ≈ 0 in 1930s and 2009–15 (rates at zero);
  C3  it flips no verdict: every era's sign is unchanged, the drawdown is unchanged to the first decimal;
  C4  the paper account does not credit ETF distributions (checked on the account's activity log before this run),
      so the pickup is invisible on paper and real only live — a build decision, not a research one.
Mechanics: recommended book r = e × (0.4 dip + 0.6 mom), e = min(insurance ×0.5, shock ×0.5); with carry
r + (1 − e) × RF, RF = Kenneth French's daily T-bill return (the factors file). A second line adds the 5 % cash reserve
(0.05 × RF) for reference — the reserve must stay spendable for brackets, so it is reported, not proposed.
Run: uv run --with numpy python -I scripts/param_search/carry.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import master  # noqa: E402
from books import LIVE, align_rf, exposure, rf_daily, sets  # noqa: E402,F401  (Decision 085: the builders live in books.py; re-exported here for the scripts that import carry)


def main():
    rf = rf_daily()
    for name, dd, lvl, r, bear, split, eras in sets():
        rfd = align_rf(dd, rf)
        shock = master.shock_flags(lvl, -0.07, 10, 20); e = exposure(bear, shock)
        base = e * (0.4 * r["dip"] + 0.6 * r["mom"])
        carry = base + (1 - e) * rfd
        carry_res = carry + 0.05 * rfd
        sb, sc, sr = (master.score(x, r["mkt"], dd, split, eras) for x in (base, carry, carry_res))
        idle = 1 - e
        print(f"\n=== T-bill carry — {name} {dd[0]} → {dd[-1]}: de-risked {np.mean(e < 1):.1%} of sessions; mean RF {np.mean(rfd) * 252:.2%}/yr, mean RF while de-risked {np.mean(rfd[e < 1]) * 252 if (e < 1).any() else 0:.2%}/yr")
        print(f"{'book':44} {'excess':>7} {'IS':>7} {'OOS':>7} | {'DD':>6} {'Sharpe':>6} | {'worst yr':>8} | eras")
        for label, s in (("recommended (idle capital at 0)", sb), ("+ idle capital in T-bills", sc), ("+ idle capital and the 5 % reserve in T-bills", sr)):
            print(f"{label:44} {s['excess']:+7.2%} {s['is']:+7.2%} {s['oos']:+7.2%} | {s['dd']:6.1%} {s['sharpe']:6.2f} | {s['worst_year']:+8.1%} | " + (" ".join(f"{x:+6.1%}" for x in s["eras"]) if eras else f"roll3 {s['roll3_pos']:.0%}"))
        print(f"  pickup: {sc['excess'] - sb['excess']:+.2%}/yr (idle), {sr['excess'] - sb['excess']:+.2%}/yr (idle + reserve)")
        # by year: idle share, RF, pickup (arithmetic: mean idle × RF, annualised)
        years = sorted({x[:4] for x in dd[1:]})
        rows = []
        for y in years:
            kk = np.array([k for k, x in enumerate(dd[1:]) if x[:4] == y])
            if len(kk) < 60: continue
            rows.append((y, float(np.mean(idle[kk])), float(np.mean(rfd[kk]) * 252), float(np.sum(idle[kk] * rfd[kk]) * 252 / len(kk))))
        hot = [x for x in rows if x[3] >= 0.0005]
        print(f"  years with a pickup ≥ 0.05 pp ({len(hot)} of {len(rows)}): " + ", ".join(f"{y} idle {i:.0%} RF {f:.1%} → {p:+.2%}" for y, i, f, p in hot))
        if name == "decade":
            print("  every year: " + ", ".join(f"{y} {p:+.2%}" for y, i, f, p in rows))


if __name__ == "__main__":
    main()
