"""A VIX-based shock trigger (roadmap B6; Decision 078 research, 2026-10-30).

The live shock trigger is a fact about prices: SPY's 10-session return at or below −7 % on any of the last 20
sessions → exposure ×0.5 (Decision 067 addendum: a plateau of 81 cells, cuts the worst drawdown by a third at
0 … 1 pp/yr, paid back in the rebound year). B6 asks whether the market's fear gauge — the VIX, Cboe's 30-day implied
volatility, daily from 1990 — triggers *earlier or better* than the price fall itself. Decision 077 closed the VIX as
a slow second signal for the insurance (a state); this is the fast-fact mechanism, which is a different question.
Data: Cboe VIX close 1990-01 → (the Decision 072 library, `datasets.cboe("VIX")`), VIX3M 2009 → for the term
structure; the century book on 1990-02 → 2026-08 (the French market; one era, split 2008-05, three decades 1990–2000 /
2000–2010 / 2010–2026 as the sub-eras) and the ETF book on the decade 2017 → 2026-10 (split 2022). Every VIX reading
is the previous session's close (no look-ahead; the VIX is published with the close).

Variants, fixed before the first run (each as a replacement for the price rule and as a third rule in the min()):
  - level: VIX > X, X ∈ {25, 30, 35, 40}, → ×0.5 for H sessions, re-armed, H ∈ {10, 20, 40} (12 cells);
  - jump: the VIX up by ≥ J points over L sessions, J ∈ {8, 12, 16}, L ∈ {5, 10}, → ×0.5 for H ∈ {10, 20} (12 cells);
  - term structure (2009 → only, a sub-test): VIX > VIX3M (an inverted curve) → ×0.5 for H ∈ {10, 20};
  - the reference: the live price rule (−7 % / 10 / 20 / ×0.5) on the same windows, and the book with no shock rule;
  - the timing table: for every bear of the window (1990, 1997-10, 1998-08, 2000–02, 2008, 2010-05, 2011-08, 2015-08,
    2018-02, 2018-Q4, 2020, 2022, 2025) the first session each rule fired and the VIX rule's lead in sessions;
  - the placebo for the level rule at X = 30 / H = 20: the VIX series block-shuffled (63 sessions), 20 draws — a
    state rule earns its place against a random state of the same frequency.

Pre-registered hypotheses (the expected numbers were written before the first run):
  X1  the VIX level rule and the price rule fire on the same episodes: at X = 30 / H = 20 the two agree on ≥ 85 % of
      de-risked sessions over 1990 →; the VIX leads by 1 … 3 sessions in the fast crashes (1997, 1998, 2018-02, 2020,
      2025) and lags or never fires in the slow ones (2000–02 in its first year, 2022 — the VIX stayed below 37).
  X2  no VIX cell beats the price rule's cell on 1990 → by more than noise: the best level cell is within ±0.3 pp/yr
      of the price rule's excess with a drawdown within 2 points; the jump cells are noisier (±0.5) and no better;
      the term-structure rule on 2009 → ≈ the X = 25 level rule.
  X3  the VIX as a third rule in the min() costs 0.2 … 0.5 pp/yr on both windows for ≤ 1 point of drawdown — more
      de-risked sessions, the same crashes.
  X4  the level rule is inside its placebo's spread on the decade (the era wants less de-risking) and at or above the
      placebo's median on 1990 → — the fast fact carries information the random state does not, as the price rule did.
  X5  the plateau: the level cells' excess varies by < 0.5 pp/yr across X 25 … 35 and H 10 … 20 on 1990 →; X = 40 fires
      too rarely (2008 and 2020 only).

Drop rules, written first:
  - a Decision (the VIX replacing or joining the price rule) only if a VIX cell beats the price rule's cell on 1990 →
    in both halves *and* in all three decades, with its eight neighbours within 0.3 pp/yr of it (a plateau, not a
    cell), a drawdown no deeper, and the ETF decade no worse than the price rule's — the Decision 067 bar;
  - otherwise the price rule stays: it needs nothing but closes, exists on every market and every century, and the
    VIX adds nothing a 7 % fall does not already say; B6 is recorded and closed.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/vixshock.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LEVELS, HOLDS = (25.0, 30.0, 35.0, 40.0), (10, 20, 40)
JUMPS, JUMP_LOOKBACKS, JUMP_HOLDS = (8.0, 12.0, 16.0), (5, 10), (10, 20)


def main():
    raise NotImplementedError("pre-registered 2026-10-30; the code follows the design above, nothing has run")


if __name__ == "__main__":
    main()
