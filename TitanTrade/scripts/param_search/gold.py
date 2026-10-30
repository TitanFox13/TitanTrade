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

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/gold.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FLOAT_START, SPLIT71 = "1971-09-01", "1998-07-01"
ERAS71 = [("1971-09-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]


def main():
    raise NotImplementedError("pre-registered 2026-10-30; the code follows the design above, nothing has run")


if __name__ == "__main__":
    main()
