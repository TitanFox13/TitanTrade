"""Quality ETFs as vehicles (Decision 075 addendum; operator: "fetch quality funds first", 2026-10-30).

Decision 075 found the quality premium real over 63 years (the most profitable 30 % of the market +1.2 pp/yr in every
era, conservative investment +2.2) and a near-pass for quality in place of half the dip sleeve on the century — and no
investable form: QUAL, the one quality ETF in the library, lost to SPY in both decade halves. This test asks whether
any other US-listed quality fund captures the premium. **The candidate list was fixed before any price was fetched**
(every quality-labelled US equity ETF on Alpaca with SIP history from 2016, so both decade halves exist): SPHQ
(Invesco S&P 500 Quality), QUAL (MSCI USA Quality, already in the library), VIG (dividend appreciation), DGRW
(quality dividend growth), DGRO (core dividend growth), QDF and QDEF (FlexShares quality dividend), QUS (MSCI USA
StrategicFactors: quality + value + low volatility), FQAL (Fidelity quality factor), COWZ (free-cash-flow yield —
quality / value hybrid), MOAT (Morningstar wide moat), and JQUA (JPMorgan quality factor, listed 2017-11, so its
first half is ten months short — reported with that caveat). Dimensional's and Avantis's profitability-tilted funds
are too young (2019 / 2021 →) for both halves and are left out. Bars: Alpaca SIP, ``adjustment=all`` (dividend-
adjusted, like every file in the archive — never a split-only fetch), ``alpaca_hist/quality/``, archived on
titanserver. Decade 2017-01-03 → 2026-10-12, split 2022-01-01, every headline through 2025-12-31 beside full.

Pre-registered hypotheses (the expected numbers were written before the fetch):
  V1  the era first: the French top-30 %-profitability portfolio itself vs the French market over the same decade —
      if the premium's hindsight-free form lagged in 2017–2026 (expected: −1 … +1, a mega-cap-growth decade), then
      every fund lagging is the era, not the vehicle. Then the funds: 0 … 3 of the 12 beat SPY in both halves;
      the dividend-growth family (VIG, DGRW, DGRO, QDF, QDEF) lags by 1 … 3 pp/yr (a value tilt in a growth decade),
      SPHQ and FQAL within ±1.5 of SPY, COWZ −2 … +2 with a strong 2022, MOAT and QUS ±2.
  V2  a fund that passes V1 must *be* quality: its daily excess over SPY regressed on French RMW (daily, through
      2026-08) has a positive loading with t > 2, and its correlation with QUAL's excess is > 0.3; a fund that beats
      SPY with a zero or negative RMW loading is a growth or momentum fund in disguise and does not count.
  V3  the sleeve, with each survivor: dip 20 / SPMO 60 / Q 20 (quality in place of half the dip sleeve — the century
      near-pass) and dip 40 / SPMO 40 / Q 20, judged against the live book (+1.36; +0.3 / +2.5; Sharpe 1.10; → 2025
      +0.80): a Decision only if a variant beats the book on return in both halves *and* through 2025, with a Sharpe
      no lower. Expected: with no vehicle above SPY the sleeve costs 0.5 … 1.5 pp/yr (Decision 075 Q6).

The luck caveat, written first: with 12 candidates and roughly a one-in-four chance that any one fund beats SPY in
both halves by luck, three passes are expected by chance alone — which is why V2 (the factor loading) and the
through-2025 check are part of the bar, and why a survivor would still be one decade of evidence behind the century's
+1.2.

Drop rules, written first:
  - no fund passes V1 and V2 → the quality door stays closed; nothing more to do without new data (recorded).
  - a fund passes V1 and V2 but V3 fails → recorded, no sleeve; the vehicle is named for a later era.
  - V1, V2 and V3 pass → a Decision is *proposed* (the expected numbers, the vehicle, the slot taken from the dip
    sleeve, a new clean window), never applied without the operator's go.

Costs: the ETF series carry their expense ratios; the dip run charges 0.05 % a side; blends rebalance daily without
cost. Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/quality_etfs.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CANDIDATES = ["SPHQ", "QUAL", "VIG", "DGRW", "DGRO", "QDF", "QDEF", "QUS", "FQAL", "COWZ", "MOAT", "JQUA"]
THROUGH = "2025-12-31"


def main():
    raise NotImplementedError("pre-registered 2026-10-30 before the fetch; the code follows the hypotheses above, nothing has run")


if __name__ == "__main__":
    main()
