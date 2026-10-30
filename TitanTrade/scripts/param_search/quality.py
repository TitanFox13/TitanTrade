"""Quality over a century (roadmap B2; Decision 075 research, 2026-10-30).

"Quality" — steadily profitable companies that invest conservatively — is the one documented equity premium the book
has never held, and the question behind roadmap B9 (a fundamentals pipeline for a single-name dip universe) is
whether profitability separates a dip from a break. Both are answered here on hindsight-free data before any pipeline
is built: Kenneth French's daily portfolios formed on operating profitability (OP) and on investment (INV), the 25
size × profitability portfolios and the five-factor file (RMW, CMA), all 1963-07 → 2026-09; AQR's Quality-Minus-Junk
factor for the US, daily 1957-07 →; QUAL (MSCI USA Quality) on the decade. Quality was closed as an ETF vehicle in
Decision 067 (QUAL −0.7 vs SPY) and as a screen in Decision 066 (low volatility, "quiet winners"); the century is a
different question. Loaders ``datasets.french_levels(…, sub="external/french")``, ``datasets.french_factors5``,
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

W63 = ("1963-07-01", "2026-08-31", "1995-01-01", [("1963-07-01", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")])
THROUGH = "2025-12-31"


def main():
    raise NotImplementedError("pre-registered 2026-10-30; the code follows the hypotheses above, nothing has run")


if __name__ == "__main__":
    main()
