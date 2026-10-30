"""The quality stage 1 — a self-built held profitability sleeve on free data (Decision 076 research, 2026-10-30).

Decision 075 found the quality premium real for 63 years (the most profitable 30 % of the market +1.2 pp/yr in every
era) and alive this decade (+1.6 … +3.4 vs SPY in the French portfolios), and its addendum found that none of twelve
quality ETFs captures it. The operator: "if the data says it is profitable, diversifies and stands the test of time,
why not do it" — and: free data first. This is the test of the one route left: picking the most profitable companies
ourselves and holding them. The crux is concentration — the French portfolio holds about a thousand names; a sleeve
holds thirty to fifty — and the question is whether our picks keep the premium or lose it the way the funds did.

Data, all free: the S&P 500 point-in-time universe 2016 → 2026 (742 names with the 94 delisted ones, Alpaca SIP,
dividend-adjusted; the daily membership mask from `universes/sp500_ticker_start_end.csv`); every company's annual
statements from the SEC's XBRL ``companyfacts`` API with their filing dates (``external/sec_facts/<TICKER>.json``,
fetched by ``fetch_sec_facts.py``; tickers mapped to CIKs through the SEC's current ticker file — delisted tickers
that do not map are ineligible for picking but stay in the equal-weight universe and in SPY, and their share is
reported); Kenneth French's profitability portfolios as the yardstick over the same window. Prices before 2016 are not
free on Alpaca (Tiingo's free key would extend the window to 2010 — roadmap B11); statements before 2009 are paid
(the roadmap's paid-data group). Window: from the first rebalance in 2017 to 2026-10-12, split 2022-01-01, every
headline through 2025-12-31 beside full.

Design, fixed before the first run:
  - point in time: at each rebalance date the score uses the latest 10-K *filed* before that date (strict), the
    fiscal year it reports being at most 18 months old;
  - profitability: OP = (revenue − cost of sales − SG&A − interest expense) / book equity (Fama–French operating
    profitability; a missing interest expense counts as zero, revenue, cost of sales and equity are required); the
    fallback where cost of sales is not reported (financials) is operating income / equity; firms with negative or
    missing equity are ineligible. Robustness definition: gross profitability = (revenue − cost of sales) / assets
    (Novy-Marx). Revenue, cost and equity are read from the usual tag families in a fixed order;
  - selection: the eligible members ranked by the score; the top N held equal-weight for a year (N = 50 primary,
    30 secondary); "top 30 %" of the eligible set (≈ 150 names) equal-weight is the construct-in-our-data line;
  - rebalance: yearly on the first session of July (French's convention: last year's statements are all filed by
    June) primary, January secondary; costs 0.05 % a side on the turnover (``screens.COST``);
  - benchmarks: SPY; the equal-weight hold of all eligible members rebalanced the same way (the like-for-like
    benchmark — the equal-weight effect alone was −3.9 pp/yr this decade, Decision 066); the French OP Hi 30 vs the
    French market over the same window; placebo = 50 random N-name lists from the same eligible set, re-drawn at
    every rebalance;
  - value-weighted versions (shares outstanding × price) only as a reference, where shares are reported.

Pre-registered hypotheses (the expected numbers were written before the first run):
  S1  the construct exists in our data: the top 30 % by OP, equal-weight, beats the equal-weight universe by +1 … +3
      pp/yr, positive in both halves (the French Hi 30 beat its market by +1.6 over 2017–2026); the bottom 30 % lags
      by 1 … 3 (the test has teeth). If S1 fails the pipeline, not the idea, is the problem.
  S2  concentration keeps the premium: the top-50 equal-weight beats the equal-weight universe by ≥ +0.8 pp/yr (half
      the French premium) in both halves, ranks above the 90th percentile of the 50 random lists on the full period
      and above their median in both halves; the top-30 keeps the sign with more noise (tracking error vs the top
      30 % of 3 … 5 %/yr).
  S3  vs SPY: every equal-weight line lags SPY by 2 … 4 pp/yr this decade (the equal-weight effect), so the honest
      "what we would trade" line — the top-50 equal-weight vs SPY — is expected at −2 … +1; the value-weighted top-50
      vs SPY at −1 … +2.
  S4  the selection rule walks forward: over the 12 cells (N 30 / 50 × anchor January / July × definition OP /
      gross profitability / operating income over equity) the cell chosen by in-sample excess over the equal-weight
      universe is positive out of sample and the reverse; the definition matters more than N or the month, and
      gross profitability ≈ OP.
  S5  the sleeve: dip 20 / SPMO 60 / Q 20 (quality in place of half the dip sleeve, the century near-pass) and
      dip 40 / SPMO 40 / Q 20 with the top-50 equal-weight, against the live book (+1.36; +0.3 / +2.5; Sharpe 1.10;
      through 2025 +0.80): expected −0.5 … +0.5 pp/yr, Sharpe ±0.03 — a pass needs the picks to beat SPY, which S3
      doubts.
  S6  what the sleeve would cost to run, reported: turnover per year, names held, the smallest position at $25k and
      $100k against the $500 dust floor, the share of the universe that could not be mapped to a filer.

Drop rules, written first:
  - S1 fails → stop; the pipeline is wrong or the premium is not in large caps this decade; recorded, parked.
  - S2 fails → no self-built sleeve; the quality door closes on free data and the paid long-history extension is
    not worth buying.
  - S2 passes and S5 fails → recorded: the picks keep the premium and do not improve the book; the paid extension
    stays in the paid group with that note.
  - S2 and S5 pass → a Decision is *proposed* (the picks as the vehicle: N, anchor, definition; the slot taken from
    the dip sleeve; the held-sleeve build; a new clean window) and the long-history confirmation becomes worth
    buying — never applied without the operator's go.
  - Twelve cells and two sleeve variants: the family reading first, the leaderboard never; the luck meter's bootstrap
    on any surviving cell.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/qualpick.py   (after fetch_sec_facts.py)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GRID = {"N": (50, 30), "anchor": (7, 1), "definition": ("OP", "GPA", "OIE")}
THROUGH, SPLIT = "2025-12-31", "2022-01-01"


def main():
    raise NotImplementedError("pre-registered 2026-10-30; the code follows the design above, nothing has run")


if __name__ == "__main__":
    main()
