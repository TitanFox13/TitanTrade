"""The de-risk destination — cash, bills, bonds and gold judged together (roadmap B8; Decision 080 research, 2026-10-30).

When the insurance or the shock trigger halves exposure, the idle half earns 0 in the research engine (a deliberate
bias against de-risking rules) and in the paper book; at go-live it earns the bank sweep or SGOV's bill yield
(Decision 071). Decision 068's addendum priced bills (+0.17 pp/yr on the decade, +0.5 on the century); Decision 074
tried a protective put (worse drawdown); Decision 079 found gold as the parking place beat bills over 1971 → on the
strength of 1973–74 alone. This test asks the whole question once: with the idle half in cash, bills, a Treasury
bond, gold, or a half-and-half mix, which parking place does the book best — judged on both halves, every era the
data allows, the drawdown leg, and a timing placebo for each asset. Data, all in the library: Kenneth French's daily
bill return (1926 →), FRED's constant-maturity Treasury yields (10-year from 1962, 2-year from 1976) turned into daily
total returns by repricing a par bond (coupon = yesterday's yield, priced at today's yield, plus the accrual), the
gold step series of Decision 079, and on the decade the ETFs IEF (7–10-year), TLT (20-year+), GLD and the bill return.

Windows: **1971-09 → 2026-08** (all four destinations; split 1998-07, eras 1971–2000 / 2000–26); **1962-01 → 2026-08**
(cash, bills, the 10-year; split 1994-05, eras 1962–75 / 1975–2000 / 2000–26); the ETF decade 2017 → 2026-10 (split
2022, through 2025 beside full). The 2-year is shown from 1976 inside the 1971 window (cash before). The book =
min(insurance ×0.5, shock ×0.5) × (0.4 dip + 0.6 momentum), the destination = the (1 − e) share. A bond *sleeve*
(10 % permanent, from the momentum sleeve) is one reference line, the question closed on the decade by 2022.

Pre-registered hypotheses (the expected numbers were written before the first run):
  D1  the destinations alone, 1971 →: bills ≈ 4.5 %/yr, the 2-year ≈ 5.5, the 10-year 6.5 … 7.5 with a −20 … −25 %
      drawdown (2020 → 2023), gold 8.6 with −62 %; daily correlation with the market: bills 0, the 10-year ≈ +0.1
      over the whole window (positive before 2000, negative after — the regime), gold ≈ 0.
  D2  the idle half in the 10-year beats bills by +0.3 … +0.8 pp/yr over 1971 → — bonds rallied in 2000–02, 2008 and
      2020 — ahead in the second half and about even in the first (1973–74 and 1980–82 were bond bears too), with the
      drawdown within 2 points of cash's and 2022 the one episode it loses (bonds fell with stocks). On 1962 → the
      1962–75 era is behind bills (the inflation decade). At or above its timing placebo's median, below the 90th.
  D3  gold as the destination repeats Decision 079: +1.4 over bills on 1971 → from 1973–74, behind bills in the first
      half from 1975, the placebo's median.
  D4  the 2-year ≈ bills + 0.2 … 0.4, drawdown within 1 point — the carry with a little duration.
  D5  the mixes (bills 50 / gold 50; the 10-year 50 / gold 50) +0.3 … +0.8 over bills with the drawdown within 2
      points — the diversified parking place — and not ahead in both halves (gold's 1980–98).
  D6  the decade: IEF idle ≈ bills (±0.3) with a deeper drawdown in 2022, TLT worse, GLD +1.5 (the 2020s).
  D7  no destination beats bills in every era available: bonds lose 1962–75, gold loses 1975–2000.

Drop rules, written first:
  - a Decision (the idle capital's destination at go-live — the `cash_ticker` leg already exists for any ticker — set
    to a bond or gold ETF instead of the sweep / SGOV) only if that destination beats the *bills* line in both halves
    of 1971 → *and* in every era the data allows, with a drawdown within 2 points of cash's, *and* above its timing
    placebo's 90th percentile — the Decision 074 / 079 standard, both legs;
  - otherwise bills stand (the sweep or SGOV at go-live, Decision 071), the question is closed with the numbers, and
    the bond sleeve stays closed.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/destination.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

W71 = ("1971-09-01", "2026-08-31", "1998-07-01", [("1971-09-01", "2000-01-01"), ("2000-01-01", "2026-09-01")])
W62 = ("1962-01-02", "2026-08-31", "1994-05-01", [("1962-01-02", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")])


def main():
    raise NotImplementedError("pre-registered 2026-10-30; the code follows the design above, nothing has run")


if __name__ == "__main__":
    main()
