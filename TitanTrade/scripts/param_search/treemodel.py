"""The entry-time model with non-linear learners (Decision 112, 2026-11-18) — the operator's question: "we did
statistics; did we ever try real models, AI? Is it worth exploring?"

Brainstorm #33 (entrymodel.py, Decision 068 addendum) fitted a ridge regression on ten entry-time features and found
no out-of-sample skill on 1,156 century trades. A linear model cannot see interactions (a deep dip *in* a weak
market), so the open half of the question is whether a flexible learner finds what the ridge could not. One change
against #33: the model class. Same ten features (entrymodel.trade_table, nothing after the signal close), same
target (the trade's return), same walk-forward both ways. No tuning on the test era: every setting below is fixed
here, before the first run, and nothing else is tried.

Models: ridge (λ = 10 — #33's, the reference; its two shared samples must reproduce #33's numbers, asserted);
boosted trees (200 trees, depth 3, rate 0.05, leaf ≥ 20); random forest (300 trees, leaf ≥ 20, a third of the
features per split); a small neural network (16-8 hidden units, weight decay 1.0, early stopping, the mean of three
seeds, standardised inputs and target).

Samples: F the 49 industries 1927 → at the live 3 × 25 % (#33's 1,156 trades) and with every signal taken
(49 × 2 % — several thousand trades, so "too little data" is tested rather than assumed), split 1975; E the
point-in-time S&P 500 2017 → at 10 × 7.5 % (#33's 623 trades) and with every signal taken (200 × 0.5 %), split 2022;
G the 11 sector ETFs 1999 → (the live universe, Tiingo) with every signal taken (11 × 9 %), split 2013-05. #33's
199-trade S&P sample is left out: a tree cannot be fitted on 91 trades.

Placebo: the training outcomes rotated in time order by a random offset (20 draws) — the outcomes keep their
clustering (dips come in bunches that share a market path) and lose their alignment with the features. #33's plain
shuffle is too narrow a band once every signal is taken.

Pre-registered hypotheses, with the numbers expected:
  T1  the null holds: for every model and sample the out-of-sample rank correlation between prediction and outcome
      is inside the placebo's 10–90 band in at least one direction; expected |ρ| ≤ 0.08 everywhere;
  T2  memorising: the trees fit their own training era (in-sample ρ ≥ 0.30, expected 0.4 … 0.7; ridge ≤ 0.2) while
      their out-of-sample ρ stays ≤ 0.05 — the more flexible the model, the wider the gap between the two;
  T3  the top half of predictions beats the bottom half by < 2 pp per trade out of sample, or not in both
      directions, for every model and sample;
  T4  more data does not rescue it: the every-signal samples give an out-of-sample ρ within ± 0.05 of the
      slot-limited samples on the same universe.

The rule. A model *passes* on a sample when, in both directions, its out-of-sample ρ is above the placebo's 90th
percentile and its top half beats its bottom half by ≥ 2 pp per trade. Fifteen model × sample cells at about a 1 %
chance each under the null make one lucky cell about a one-in-seven event, so the door reopens only if the same
model passes on the century (F) and on a modern sample (E or G). That would earn a second, separately
pre-registered stage — a 60-session embargo at the split, then the model as a walk-forward entry filter in the book
with the luck meter — and nothing more. Anything less: closed, "Models: the entry-time model, linear and
non-linear". Nothing live changes either way.

Run from TitanTrade/: uv run --with numpy --with scikit-learn python -I scripts/param_search/treemodel.py

ADDENDUM (2026-11-18, `--addendum`; written after the first run, before any second look). The first run closed the
question by the rule, with one hit the rule did not accept: on G (the 11 sector ETFs 1999 →, 153 trades) the boosted
trees passed both ways (+0.30 / +0.30) and the ridge reached +0.20 / +0.38. Seen so far: that table and how the
trades spread in time (91 entry months). Not seen: any feature table on G, any other window or split, any French
basket over 1999 →. Same models, same settings, same placebo. A 90-calendar-day embargo around each split (training
side) from here on. The French 10 industries (NoDur … Other, 1926 →) stand in for the sectors over a century.
  A1  replication, same window: the French 10 industries 1999-11 →, every signal (10 × 9 %), split 2013-05 — the
      boosted trees' out-of-sample ρ ≥ +0.15 both ways if the hit belongs to the window's sector baskets and not to
      the 153 trades; expected to hold, at about 60 %;
  A2  the narrower baskets, same window: the 49 industries 1999-11 →, every signal, split 2013-05 — expected weaker,
      +0.05 … +0.15, above the placebo band at least one way;
  A3  the century at sector granularity (the test the rule asked for): the French 10 industries 1927 →, every
      signal, split 1975 and split 1999-11 (before ↔ after) — expected inside the placebo band, |ρ| ≤ 0.08: whatever
      holds since 1999 did not hold before;
  A4  what carries it on G: (a) at most three of the ten features have the same sign and |ρ| ≥ 0.15 with the trade
      return in both halves, and they are market-state features; (b) on the five market-state features alone
      (mkt_above, mkt_ret12, mkt_vol20, mkt_dd252, breadth) the boosted trees and the ridge keep ρ ≥ +0.15 both
      ways; on the five name features alone (dip90, dip252, worst20, own_mom, rel_str) they fall inside the band at
      least one way — it is *when* to buy a dip, not *which*;
  A5  robustness on G: (a) splits 2008-06 / 2013-05 / 2018-11, both ways — the boosted trees pass (above the
      placebo's 90th percentile, top − bottom ≥ 2 pp) in at least 4 of 6 cells; (b) 2009 and 2020 left out — ρ stays
      ≥ +0.15 both ways; (c) the live cell 3 × 25 % — the same sign both ways, ρ ≥ +0.10; (d) walk-forward as it
      would have been used — re-fitted each calendar year from 2006 on every earlier trade, a trade "taken" when its
      prediction is above the model's own training median: ρ ≥ +0.15, above the placebo's 90th percentile, taken −
      skipped ≥ 2 pp per trade.
The verdict, fixed now. *A fluke*: A1 fails or A5 fails ((a) under 4 of 6, or (d) inside its band) → closed, explained
as luck among twenty cells. *An era*: A1 and A5 hold and A3 does not show it → real in the last quarter-century's
sector baskets and absent before; it fails the every-era bar, is recorded as knowledge, and a filter in the book is
priced only on the operator's word, recommended against. *Real*: A1, A5 and A3 (a pass both ways on the century,
either split, trees or ridge) → a filter in the book is pre-registered separately and proposed. Nothing live changes
in any case.
Run: uv run --with numpy --with scikit-learn python -I scripts/param_search/treemodel.py --addendum
"""
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402
from sklearn.compose import TransformedTargetRegressor  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor  # noqa: E402
from sklearn.exceptions import ConvergenceWarning  # noqa: E402
from sklearn.linear_model import Ridge  # noqa: E402
from sklearn.neural_network import MLPRegressor  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

import datasets  # noqa: E402
import entrymodel as em  # noqa: E402
import fastbt  # noqa: E402
import screens  # noqa: E402

DRAWS = 20
MKT, NAME = [3, 4, 5, 6, 7], [0, 1, 2, 8, 9]     # em.FEATS: the market-state features, the name's own
MODELS = {
    "ridge": lambda s: [make_pipeline(StandardScaler(), Ridge(alpha=10.0))],
    "boosted trees": lambda s: [HistGradientBoostingRegressor(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=20,
                                                              early_stopping=False, random_state=s)],
    "random forest": lambda s: [RandomForestRegressor(n_estimators=300, min_samples_leaf=20, max_features=1 / 3, n_jobs=-1, random_state=s)],
    "neural net": lambda s: [TransformedTargetRegressor(
        regressor=make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(16, 8), alpha=1.0, max_iter=500, early_stopping=True, random_state=s + k)),
        transformer=StandardScaler()) for k in range(3)],
}


def rho(a, b):
    r = spearmanr(a, b).statistic    # average ranks: tree predictions are piecewise constant, full of ties
    return 0.0 if np.isnan(r) else float(r)


def predict(name, Xa, ya, Xs, seed=0):
    fits = [m.fit(Xa, ya) for m in MODELS[name](seed)]
    return [np.mean([m.predict(X) for m in fits], axis=0) for X in Xs]


def evaluate(label, X, y, when, split, rng, ridge_check=None, embargo=0):
    o = np.argsort(when, kind="stable"); X, y, when = X[o], y[o], when[o]
    early = when < split
    near = np.abs((when.astype("datetime64[D]") - np.datetime64(split)).astype(int)) < embargo   # dropped from training only
    print(f"\n--- {label}: {len(y)} trades, early {early.sum()} / late {(~early).sum()}, mean trade {y.mean():+.1%}", flush=True)
    passed, ridge_rho = {}, []
    for direction, a, b in (("early → late", early, ~early), ("late → early", ~early, early)):
        a = a & ~near
        n = int(a.sum()); shifts = rng.integers(n // 10, n - n // 10, DRAWS)
        for name in MODELS:
            p_in, p_out = predict(name, X[a], y[a], (X[a], X[b]))
            r = rho(p_out, y[b]); top = p_out >= np.median(p_out)
            gap = y[b][top].mean() - y[b][~top].mean() if (~top).any() else 0.0
            pl = np.array([rho(predict(name, X[a], np.roll(y[a], int(k)), (X[b],), seed=int(k))[0], y[b]) for k in shifts])
            ok = bool(r > np.percentile(pl, 90) and gap >= 0.02)
            passed.setdefault(name, []).append(ok)
            if name == "ridge":
                ridge_rho.append(r)
            print(f"  {direction:13} {name:14} in-sample ρ {rho(p_in, y[a]):+.2f} | out-of-sample ρ {r:+.3f} (placebo {np.median(pl):+.3f} "
                  f"[{np.percentile(pl, 10):+.3f}…{np.percentile(pl, 90):+.3f}], beaten {np.mean(r > pl):4.0%}) | top − bottom half {gap:+.1%} per trade"
                  f"{'   PASS' if ok else ''}", flush=True)
    if ridge_check:     # the plumbing check: the reference model on #33's sample gives #33's published numbers
        assert np.allclose(ridge_rho, ridge_check, atol=2e-3), (ridge_rho, ridge_check)
    return passed       # per model: [early → late, late → early]


def main():
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    rng = np.random.default_rng(112)
    F = datasets.load("F_french_49ind_1926"); E, memb = screens.load_universe(); G = datasets.load("G_tiingo_sectors_1999")
    L = em.LIVE
    samples = [   # label, universe (F century / E, G modern), market, membership, start, parameters, split, #33's ridge numbers
        ("F 49 industries 1927 →, 3 × 25 % (#33's sample)", "F", F, None, "1927-07-01", L, "1975-01-01", (-0.025, -0.133)),
        ("F 49 industries 1927 →, every signal (49 × 2 %)", "F", F, None, "1927-07-01", {**L, "slot_pct": 0.02, "max_slots": 49}, "1975-01-01", None),
        ("E S&P 500 point-in-time, 10 × 7.5 % (#33's sample)", "E", E, memb, "2017-01-03", {**L, "slot_pct": 0.075, "max_slots": 10}, "2022-01-01", (-0.063, 0.006)),
        ("E S&P 500 point-in-time, every signal (200 × 0.5 %)", "E", E, memb, "2017-01-03", {**L, "slot_pct": 0.005, "max_slots": 200}, "2022-01-01", None),
        ("G 11 sector ETFs 1999 →, every signal (11 × 9 %)", "G", G, None, "1999-11-01", {**L, "slot_pct": 0.09, "max_slots": 11}, "2013-05-01", None),
    ]
    won = {name: set() for name in MODELS}
    for label, uni, mkt, member, start, params, split, check in samples:
        X, y, when, _ = em.trade_table(mkt, member, start, params)
        for name, ok in evaluate(label, X, y, when, split, rng, check).items():
            if all(ok):
                won[name].add(uni)
    print("\n=== the rule: a model must pass on the century (F) and on a modern sample (E or G)")
    for name, unis in won.items():
        reopen = "F" in unis and bool(unis & {"E", "G"})
        print(f"  {name:14} passes on: {', '.join(sorted(unis)) or 'nothing'} → {'REOPEN (stage 2)' if reopen else 'closed'}")


def walk_forward(label, X, y, when, first_year, rng):
    """As it would have been used: re-fit each calendar year on every earlier trade; a trade's score is its prediction
    minus the model's own training median, so "taken" (score ≥ 0) needs nothing from the future."""
    o = np.argsort(when, kind="stable"); X, y, when = X[o], y[o], when[o]
    yr = np.array([w[:4] for w in when]); years = sorted(set(yr[yr >= first_year])); test = yr >= first_year
    print(f"\n--- {label}: {int(test.sum())} test trades over {len(years)} years ({int((~test).sum())} before {first_year})", flush=True)
    for name in MODELS:
        def run(shift):      # shift None = the real outcomes; else each training set's outcomes rotated by that fraction
            p = np.full(len(y), np.nan)
            for Y in years:
                a, b = yr < Y, yr == Y
                ya = y[a] if shift is None else np.roll(y[a], int(shift * a.sum()))
                p_a, p_b = predict(name, X[a], ya, (X[a], X[b]), seed=int(Y))
                p[b] = p_b - np.median(p_a)
            return p[test]
        p = run(None); r = rho(p, y[test]); top = p >= 0
        gap = y[test][top].mean() - y[test][~top].mean() if top.any() and (~top).any() else 0.0
        pl = np.array([rho(run(s), y[test]) for s in rng.uniform(0.1, 0.9, DRAWS)])
        ok = bool(r > np.percentile(pl, 90) and r >= 0.15 and gap >= 0.02)
        print(f"  {name:14} out-of-sample ρ {r:+.3f} (placebo {np.median(pl):+.3f} [{np.percentile(pl, 10):+.3f}…{np.percentile(pl, 90):+.3f}], beaten "
              f"{np.mean(r > pl):4.0%}) | taken {int(top.sum())} at {y[test][top].mean() if top.any() else 0:+.1%}, skipped {int((~top).sum())} at "
              f"{y[test][~top].mean() if (~top).any() else 0:+.1%} (gap {gap:+.1%}){'   HOLDS' if ok else ''}", flush=True)


def addendum():
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(1122)
    L = em.LIVE
    ind10 = datasets.french_levels("10_Industry_Portfolios_Daily.csv", "external/french")
    T10 = fastbt.Market(datasets.french_market(), ind10, ind10)
    F = datasets.load("F_french_49ind_1926"); G = datasets.load("G_tiingo_sectors_1999")

    def every(n, pct):
        return {**L, "slot_pct": pct, "max_slots": n}

    print("=== A1 / A2: the same window and split on the French baskets (90-day embargo throughout)")
    evaluate("A1 French 10 industries 1999-11 →, every signal (10 × 9 %)", *em.trade_table(T10, None, "1999-11-01", every(10, 0.09))[:3], "2013-05-01", rng, embargo=90)
    evaluate("A2 49 industries 1999-11 →, every signal (49 × 2 %)", *em.trade_table(F, None, "1999-11-01", every(49, 0.02))[:3], "2013-05-01", rng, embargo=90)
    print("\n=== A3: the century at sector granularity")
    X, y, when, _ = em.trade_table(T10, None, "1927-07-01", every(10, 0.09))
    evaluate("A3 French 10 industries 1927 →, every signal, split 1975", X, y, when, "1975-01-01", rng, embargo=90)
    evaluate("A3 French 10 industries 1927 →, every signal, split 1999-11", X, y, when, "1999-11-01", rng, embargo=90)
    print("\n=== A4: what carries it on G")
    X, y, when, _ = em.trade_table(G, None, "1999-11-01", every(11, 0.09))
    early = when < "2013-05-01"
    print(f"{'feature':10} {'ρ early':>9} {'ρ late':>9}   (Spearman with the trade return; {early.sum()} / {(~early).sum()} trades)")
    for k, fn in enumerate(em.FEATS):
        a, b = rho(X[early, k], y[early]), rho(X[~early, k], y[~early])
        print(f"{fn:10} {a:+9.2f} {b:+9.2f}{'   same sign, both ≥ 0.15' if a * b > 0 and min(abs(a), abs(b)) >= 0.15 else ''}")
    evaluate("A4b G, the five market-state features alone", X[:, MKT], y, when, "2013-05-01", rng, embargo=90)
    evaluate("A4b G, the five name features alone", X[:, NAME], y, when, "2013-05-01", rng, embargo=90)
    print("\n=== A5: robustness on G")
    cells = []
    for split in ("2008-06-01", "2013-05-01", "2018-11-01"):
        cells += evaluate(f"A5a G, split {split}", X, y, when, split, rng, embargo=90)["boosted trees"]
    print(f"\n  A5a boosted trees pass in {sum(cells)} of {len(cells)} cells (needs ≥ 4)")
    keep = ~np.isin([w[:4] for w in when], ("2009", "2020"))
    evaluate("A5b G without 2009 and 2020", X[keep], y[keep], when[keep], "2013-05-01", rng, embargo=90)
    evaluate("A5c G at the live 3 × 25 %", *em.trade_table(G, None, "1999-11-01", L)[:3], "2013-05-01", rng, embargo=90)
    walk_forward("A5d G walk-forward, re-fitted each year from 2006", X, y, when, "2006", rng)


if __name__ == "__main__":
    addendum() if "--addendum" in sys.argv else main()
