"""The quality stage 2 — the value-weighted picks and the mega-cap confound (Decision 076 addendum, 2026-10-30).

Stage 1 (Decision 076) closed the equal-weight sleeve and left one reference line open: the top 50 / top 30 by
operating profitability, weighted by market value, beat SPY by +1.8 … +3.0 pp/yr over 2017 → 2026, three of four cells
in both halves. The suspicion, written before this run: a profitability ratio over *book equity* ranks the buyback
giants first (a company that has retired most of its equity shows an enormous ratio), so "the most profitable,
weighted by size" may be "the decade's largest winners" wearing a quality label. This stage answers that one
question with the data already in hand (the stage-1 pipeline: the point-in-time S&P 500 2016 →, the SEC filings with
their dates, shares outstanding; French RMW; SPMO). Window, anchors, costs and benchmarks as in stage 1.

Checks, fixed before the first run:
  T1  the confound measured: each weighted pick line's daily excess over SPY regressed on SPMO's excess (the decade's
      leaders), on a size tilt (the value-weighted minus the equal-weight hold of the scored set: big minus small
      inside the universe) and on French RMW (quality); the alpha that is left, with its t; and what the portfolio
      holds — the ten largest weights at the last rebalance and the share of the top five, averaged over the
      rebalances.
  T2  the confound removed by construction, three ways, all three reported, none chosen afterwards:
      (a) weights capped at 5 % per name (the excess redistributed to the rest, as a diversified index rule does);
      (b) the ranking done *within size quintiles* of the eligible names, ten picks per quintile (the Fama–French
          construction, which is where the century's +1.2 comes from), equal- and value-weighted;
      (c) a denominator buybacks cannot shrink: operating profitability over total assets, with the stage-1
          coverage (the gross-profitability definition scored only 200–280 names, a different and smaller universe,
          which is part of why it collapsed out of sample — that comparison is made on the common names).
  T3  the giants without the label: the fifty largest names by market value, value-weighted, no profitability at
      all, over the same window — the size-only control the weighted picks must beat.
  T4  the walk-forward on the weighted family (N 30 / 50 × anchor × raw / capped / within-size × OP / OP-over-
      assets): the cell chosen by in-sample excess over SPY and its out-of-sample excess, and the reverse; the
      family reading first.
  T5  the sleeve with the variant named *now*: the top 50 by OP, July, value-weighted and capped at 5 % (what a
      sleeve would plausibly trade) — dip 20 / SPMO 60 / picks 20 and dip 40 / SPMO 40 / picks 20 against the book
      over the same window (both halves and through 2025 better, Sharpe no lower); the within-size value-weighted
      top 50 as the secondary.
  T6  the dust floor with capped weights at $25k and $100k (the smallest position in a 20 % sleeve), the turnover.

Expected, written first (prior 30 % that it is quality): T1 — the SPMO loading +0.3 … +0.5 and the size loading
+0.3 … +0.6, both with t > 5, the RMW loading +0.1 … +0.3, the alpha left +0 … +1 pp/yr with t < 2; the top five
names a third or more of the top-30 portfolio and the usual giants. T2 — the 5 % cap halves the excess (+0.5 …
+1.5 vs SPY); within-size ranking +0 … +1; over assets −0.5 … +1. T3 — the largest fifty beat SPY by +1 … +2 this
decade on their own. T4 — the OP family walks forward, the within-size cells do not. T5 — the capped sleeve costs
the book 0 … 0.5 pp/yr and fails the bar.

Drop rules, written first:
  - a Decision is proposed only if (i) the alpha after SPMO and the size tilt is positive with t > 2 *or* the
    within-size value-weighted top 50 beats SPY in both halves, *and* (ii) the pre-named sleeve (T5) beats the book
    in both halves and through 2025 with a Sharpe no lower — then the proposal is the capped value-weighted picks as
    the vehicle, the slot from the dip sleeve, the build, a new clean window, never applied without the operator's go,
    and the paid long-history confirmation becomes worth buying;
  - otherwise the weighted picks were the decade's leaders: the quality door closes on free data for good, the paid
    extension is not bought, and the knowledge (a buyback-shrunk denominator is a size ranking) is kept.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/qualpick2.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CAP = 0.05
THROUGH, SPLIT = "2025-12-31", "2022-01-01"


def main():
    raise NotImplementedError("pre-registered 2026-10-30; the code follows the checks above, nothing has run")


if __name__ == "__main__":
    main()
