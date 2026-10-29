"""The international book (roadmap E2; Decision 073 research, 2026-10-29).

The operator's second fear is a weaker US market and a weaker dollar, and every number behind the live book is
US-only. International equities are the one instrument class with a diversification case for this book: lost decades
differ by region (Japan 1990–2010, the US 2000–2010, Europe 2007–2017), the momentum premium is documented in every
developed region, and country ETFs are diversified baskets — the only universe class on which the dip rule has ever
been ≥ 0. The caveats are pre-registered too: equity correlations converge to 0.8–0.9 in a crash, so any
diversification is in the decades, not in the week that hurts; the ex-US ETFs reach back to 2016 only (one decade,
two halves — weaker evidence than the US century); US-listed ex-US ETFs carry the dollar.

Data: Kenneth French's regional daily factors and momentum (WML) 1990-11 → 2026-09, in USD (Developed ex-US, Europe,
Japan, Asia-Pacific ex-Japan; ``external/french_intl/``, zips unpacked in place); 39 region / country ETFs, Alpaca SIP
2016-01-04 →, dividend-adjusted (``alpaca_hist/intl/``): ACWX (MSCI ACWI ex-US) as the ex-US book's index and core,
IMTM / IDMO as the momentum vehicles, the 20 single-country funds as the dip universe (EWA EWC EWD EWG EWH EWI EWJ EWL
EWN EWP EWQ EWS EWT EWU EWW EWY EWZ FXI INDA MCHI); FRED DEXUSEU (USD per EUR) for the currency view. The US book is
``carry.sets()``'s decade (sector dip sleeve 40 / SPMO 60, exposure = min(insurance ×0.5, shock ×0.5)), 2017-01-03 →,
split 2022-01-01; the ex-US book is built the same way on its own index.

Pre-registered hypotheses (the expected numbers were written before the first run):
  I1  the momentum premium exists in every developed region: French WML, annualised mean, is positive in both halves
      (split 2008-01-01) for Developed ex-US, Europe and Asia-Pacific ex-Japan; Japan is the documented exception
      (≈ 0, either sign). Expected +3 … +8 pp/yr long-short ex-US, with the 2009 crash in every region. Each region's
      WML correlates +0.3 … +0.6 with the US WML daily — a related bet, not the same one.
  I2  an ex-US momentum ETF held outright beats its index: IMTM and / or IDMO vs ACWX, excess CAGR ≥ 0 in both halves
      (split 2022-01-01); expected +1 … +3 pp/yr (SPMO made +5.2 vs SPY; a long-only ex-US factor fund captures less).
      Also shown vs EFA and IEFA (the developed parent the vehicles actually track), and through 2025-12-31.
  I3  the sector-floor test on a new universe of baskets: the live dip rule on the 20 country ETFs, 3 × 25 % slots,
      ACWX as the residual, the insurance from the region's own breadth (ACWX below its 200-day SMA and fewer than half
      of the 20 countries above theirs) is ≥ 0 vs ACWX and ≥ 0 vs the equal-weight basket of the 20 in both halves.
      Expected 0 … +1 pp/yr (the sector floor is +0.4), more trades and more stops than the sectors (countries are
      more volatile and less correlated than sectors), drawdown no worse than ACWX's.
  I4  the ex-US two-sleeve book (country dip 40 / IMTM 60, exposure = min(insurance ×0.5, shock ×0.5) read off ACWX)
      and the US book bet on different things: the correlation of their daily *active* returns (each over its own
      index) is < 0.5, expected +0.1 … +0.3; their *total* returns correlate +0.7 … +0.85 (the crash caveat), about
      what ACWX and SPY do.
  I5  the global blend, US book w / ex-US book (1 − w), w = 0.5 / 0.6 / 0.7 (0.8 and 0.9 for the marginal), rebalanced
      daily, judged vs SPY and against the US book alone: at w = 0.6 or 0.7 it improves the drawdown or the Sharpe of
      the US book, and the return it gives back vs SPY is no larger than what the placebos give back at the same
      weight. Placebo P1 = ACWX held in the ex-US slot (does the ex-US *book* add anything beyond ex-US *exposure*?);
      placebo P2 = three random country ETFs, equal weight, re-drawn every calendar year, 20 draws (a random region
      weighting with the same slot count). Expected on this decade: the blend gives back 2 … 4 pp/yr vs SPY (2017 →
      2026 is the worst decade for ex-US in the record), Sharpe within ±0.05, drawdown 1 … 3 points shallower — so I5
      is expected to fail on return, and the test is run to find out.
  I6  every headline number is reported through 2025-12-31 beside the full period, because 2026 dominates momentum
      numbers.
  I7  currency: the US book, the ex-US book and the blends converted to euros with DEXUSEU over the decade (both
      halves), and — because the ETF decade holds neither — the US market vs the Developed ex-US market (French, USD)
      in euro terms over the dollar's fall 2002-01 → 2008-07 (EUR/USD 0.90 → 1.60) and its rise 2008-07 → 2022-09
      (1.60 → 0.96). Expected: in the fall ex-US beats the US by 5 … 10 pp/yr in euros, in the rise the reverse; the
      euro view moves every decade number by the dollar's annual drift (≈ ±1 pp/yr). CZK is not in the library; the
      euro is the proxy (the koruna has tracked the euro within a few percent a year). Reference only: DBEF vs EFA
      (hedged vs unhedged developed ex-US) over the decade — roadmap E4, not decided here.

Drop rules, written first:
  - I2 fails (no vehicle positive in both halves vs ACWX) or I3 fails (not ≥ 0 in both halves vs ACWX and vs the
    basket) → no ex-US book; the result is recorded and roadmap E3 stays closed.
  - I5 fails (no weight at which the blend improves the drawdown or the Sharpe, or the give-back exceeds the
    placebos') → no blend.
  - A Decision is proposed only if I2 and I3 and I5 all hold, and then only as a Decision with the expected numbers
    and the build (a second book under the same engine: ``watchlist`` = the 20 country ETFs, ``momentum_ticker`` =
    IMTM, ``core_ticker`` = ACWX, per-book cash reserve, overlay cap and drawdown breaker — roadmap C5), never applied
    without the operator's go.
  - Whatever the outcome, I1 and I7 are knowledge, not a build: they say whether the fear is addressable at all.

Costs: the ETF series are total return with expense ratios in the price; the dip run charges 0.05 % a side; the blends
are rebalanced daily without cost (as every blend in this harness). De-risked capital earns 0.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/intl.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

COUNTRIES = ["EWA", "EWC", "EWD", "EWG", "EWH", "EWI", "EWJ", "EWL", "EWN", "EWP", "EWQ", "EWS", "EWT", "EWU", "EWW", "EWY", "EWZ", "FXI", "INDA", "MCHI"]
REGIONS = {"Developed ex-US": "Developed_ex_US", "Europe": "Europe", "Japan": "Japan", "Asia-Pacific ex-Japan": "Asia_Pacific_ex_Japan"}
START, SPLIT, THROUGH = "2017-01-03", "2022-01-01", "2025-12-31"


def main():
    raise NotImplementedError("pre-registered 2026-10-29; the code follows the hypotheses above, nothing has run")


if __name__ == "__main__":
    main()
