"""Credit and financial stress as the insurance's second signal (roadmap B5; Decision 077 research, 2026-10-30).

The two-signal insurance halves exposure while SPY is below its 200-day SMA *and* fewer than half of the 11 sector
ETFs are above theirs; on the century the engine has the SMA alone (no breadth exists there). Member breadth as the
second signal failed in Decision 068's addendum: a block-shuffled breadth beat both real measures on the decade,
because the decade rewards any loosening of the insurance — "the era is talking". This test asks whether a signal
from a *different population* — the credit and funding markets, which do not look at stock prices — is a better
second condition: the Chicago Fed's National Financial Conditions Index (NFCI, weekly, 1971 →, zero = average
conditions, positive = tighter), its adjusted twin (ANFCI), the St. Louis Fed stress index (STLFSI4, weekly, 1993 →),
and the VIX (daily, 1990 →) as the unrevised cross-check. All from the Decision 072 library.

Two caveats written first. **Revisions**: NFCI, ANFCI and STLFSI4 are re-estimated and their whole history is revised
at each release, so the current vintage knows the future's normalisation — a mild look-ahead the VIX does not have;
the test lags every weekly value by one week (publication) and reads the VIX result as the point-in-time version.
**The era**: the decade wants less insurance; a rule that fires less looks smart there whatever it is, so the decade
is judged only against its placebo, and the 1971 → window (the century book restricted to the NFCI's history, where the
incumbent is the SMA alone) carries the verdict.

Design, fixed before the first run: the book = min(insurance ×0.5, shock ×0.5) × (0.4 dip + 0.6 momentum), de-risked
capital at 0; insurance variants, each with its placebo (the stress indicator block-shuffled in 63-session blocks, 20
draws — the same firing frequency, no information):
  - the incumbent: SMA200 AND sector breadth < 50 % (decade); SMA200 alone (1971 → and the century);
  - SMA200 AND stress > x — NFCI x ∈ {0, +0.5, +1}, STLFSI4 x ∈ {0, +1, +2} (1993 →), VIX x ∈ {20, 25, 30};
  - SMA200 AND breadth < 50 % AND stress > x (decade, a third condition);
  - stress > x alone (no SMA) — the stress as the first signal;
  - the live book plus stress > x as a third rule in the min() (the decade and 1971 →).
Windows: the decade 2017-01-03 → 2026-10-12 (split 2022); **1971-01 → 2026-08** (split 1998-07, eras 1971–2000 /
2000–26); the episodes 1973–74, 1980–82, 1987, 1990, 2000–02, 2008, 2011, 2020, 2022 — the fall and the rebound year.

Pre-registered hypotheses (the expected numbers were written before the first run):
  C1  stress and the SMA agree on the deep bears and disagree on the shallow ones: with NFCI > 0 the de-risked share
      of sessions over 1971 → falls from the SMA's ≈ 27 % to 10 … 15 %, keeping 1973–74, 2008 and 2020 and dropping
      most of the 1990s and 2010s false alarms; 1987 is missed by both (stress rose after the crash).
  C2  on the 1971 → window the stress-gated insurance (SMA AND NFCI > 0 or > 0.5) beats the SMA-only book by +0.3 …
      +1.0 pp/yr with a drawdown no more than 3 points deeper, positive in both halves — *and* it is inside its
      placebo's spread, because fewer firings pay on that window too (prior ≈ 30 % that it beats the placebo's 90th
      percentile).
  C3  on the decade every stress variant reads ≥ the live book (+1.36) and inside its placebo, as member breadth did.
  C4  stress alone (no SMA) is worse than the SMA alone on both windows (it fires late: 1987, 2020-02).
  C5  stress as a third rule in the min() costs 0.3 … 0.8 pp/yr on the decade for ≤ 2 points of drawdown — the
      volatility-target family.
  C6  the VIX version agrees with the NFCI version in sign on every line (so the revisions are not what is driving
      it); STLFSI4 agrees where it exists.

Drop rules, written first:
  - a Decision (stress as the second signal, or the third rule) only if the variant beats the incumbent in both
    halves of the 1971 → window with a drawdown no more than 3 points deeper *and* beats its placebo's 90th
    percentile there *and* the VIX twin agrees in sign *and* the decade reads no worse than its placebo's median;
  - otherwise recorded: the insurance keeps its two signals; credit stress joins member breadth in Track D.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/stress.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

THRESH = {"NFCI": (0.0, 0.5, 1.0), "STLFSI4": (0.0, 1.0, 2.0), "VIXCLS": (20.0, 25.0, 30.0)}
LAG_DAYS = 7


def main():
    raise NotImplementedError("pre-registered 2026-10-30; the code follows the design above, nothing has run")


if __name__ == "__main__":
    main()
