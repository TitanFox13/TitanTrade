"""Put-writing and the collar indices (roadmap B1; Decision 074 research, 2026-10-29).

Brainstorm #32 ("sell a put at the dip level instead of buying") was untestable until Decision 072 fetched Cboe's
option-strategy benchmark indices. They answer two questions the book has never been able to ask: (1) is systematic
option *writing* a sleeve worth holding beside the dip and momentum sleeves — the published claim is that the put-write
index earns about the S&P's return at two thirds of its volatility over decades; (2) is a *collar or protective put*
a better insurance than de-risking to cash — today the book halves exposure on two signals and the idle half earns 0.
Daily index levels: BXMD (buy-write, 30-delta call), BXY (2 % OTM call), CMBO (covered combo), CNDR, BFLY, RXM and
PPUT (long S&P + 5 % OTM put) from 1986-07; BXMC 1990 →; BXM (at-the-money buy-write) 2003 →; **PUT (the cash-secured
put-write) daily only from 2007** (sparse points before); WPUT (weekly) 2006 →; CLL (collar 95 / 110) 2008-09 →. All
are total-return indices on the S&P 500, the put-write collateralised in bills. The market: Kenneth French's
value-weighted US market (total return, the century engine's market) on the long windows, SPY on the decade — the
Cboe indices are on the S&P 500, the French market is broader (≈ 0.3 pp/yr apart over 1986 → 2026); every sleeve and
insurance comparison is book vs book on the same market, so the choice mostly cancels. Loader ``datasets.cboe``.

Windows (each split at its midpoint, the 40-year one also by decade): **40y** 1986-07-01 → 2026-08-31 (the French
market's end), split 2006-07-01, eras 1986–96 / 96–06 / 06–16 / 16–26; **20y** 2007-01-03 → 2026-08-31 (PUT, WPUT,
BXM), split 2017-01-01; **CLL** 2008-09-02 → 2026-08-31, split 2017-07-01; **decade** 2017-01-03 → 2026-10-12 (the
ETF book, split 2022-01-01, every headline also through 2025-12-31). The book = ``carry.sets()``: the century book
(dip on 49 industries 40 / top momentum decile 60, frictionless) on the long windows, the sector-dip / SPMO book on the
decade, exposure = min(insurance ×0.5, shock ×0.5), de-risked capital at 0.

Pre-registered hypotheses (the expected numbers were written before the first run):
  O1  the indices alone vs the market: PUT within ±1 pp/yr of the market at 60–70 % of its volatility and a higher
      Sharpe (both halves of 20y); BXMD / BXY within ±1 at 75–85 % volatility over 40y, BXM (at-the-money) −1 … −2;
      PPUT −2 … −4 pp/yr over 40y with a drawdown about a third smaller (AQR's "pathetic protection"); CLL −2 … −4
      with half the drawdown. CNDR / BFLY / RXM / CMBO / BXMC / WPUT are reported for the record, not hypothesised.
  O2  an option-writing sleeve beside the book (OPT = BXMD on 40y, PUT on 20y and the decade), at 20 % taken from the
      dip sleeve, from the momentum sleeve, or replacing the dip sleeve (0 / 60 / 40): Sharpe +0.00 … +0.05, return
      −0.3 … −1.0 pp/yr on the decade and ≈ 0 ± 0.5 on the long windows, drawdown within ±2 points. The writing
      index's excess over the market correlates +0.2 … +0.4 with the dip sleeve's excess (both are short the market's
      big moves: flat and choppy years pay, strong bulls and crashes cost) and −0.1 … +0.1 with momentum's — so it is
      a second copy of the dip sleeve's bet, not a diversifier.
  O3  a protective put or a collar as the insurance: the idle (1 − e) half held in PPUT (40y) or CLL (CLL window)
      instead of cash; references = cash (the engine), bills (the carry line), and the permanent structure (the whole
      core in PPUT / CLL at all times with no de-risking). Expected: PPUT-as-the-idle-half +0.3 … +1.0 pp/yr vs cash
      over 40y (it stays in the rebounds the cash misses; the put caps the crash leg), ≈ +0 … +0.5 vs bills, with the
      worst drawdown 0 … 3 points deeper; the permanent protective put −2 … −4 pp/yr vs the book with a drawdown a
      third smaller; the collar in between.
  O4  the crash leg, reported not hypothesised: 1987-10, 2000–02, 2008, 2020, 2022 peak-to-trough and the rebound
      year after each, for the book, the book with the option sleeve, and the book with the put-as-insurance.
  O5  every decade number through 2025-12-31 beside the full period.

Drop rules, written first:
  - O2: a Decision for an option-writing sleeve only if the book with it beats the 40 / 60 book on return in both
    halves *and* in every era available, with a Sharpe no lower — else recorded, no sleeve.
  - O3: a Decision for a put / collar insurance only if it beats the *bills* line (not cash) in both halves and every
    era available, with a worst drawdown no more than 2 points deeper than the cash version — else recorded.
  - Either Decision would be a Decision only (expected numbers and the build: Alpaca options approval — cash-secured
    puts are level 1, a long put for the collar is level 2 — on SPY, not SPX; the index assumes monthly rolls at the
    volume-weighted price, a retail fill is worse), never applied without the operator's go.
  - Whatever the outcome, O1 and O4 are knowledge: what forty years of option strategies did against the market.

Costs: the Cboe indices are net of nothing but the option's own bid-ask at the roll (the methodology prices the roll
at the VWAP); the dip run charges 0.05 % a side; blends rebalance daily without cost. De-risked capital earns 0
unless the line says bills or an index.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/putwrite.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WINDOWS = {"40y": ("1986-07-01", "2026-08-31", "2006-07-01", [("1986-07-01", "1996-07-01"), ("1996-07-01", "2006-07-01"), ("2006-07-01", "2016-07-01"), ("2016-07-01", "2026-09-01")]),
           "20y": ("2007-01-03", "2026-08-31", "2017-01-01", None), "CLL": ("2008-09-02", "2026-08-31", "2017-07-01", None)}
THROUGH = "2025-12-31"


def main():
    raise NotImplementedError("pre-registered 2026-10-29; the code follows the hypotheses above, nothing has run")


if __name__ == "__main__":
    main()
