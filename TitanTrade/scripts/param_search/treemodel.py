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
import screens  # noqa: E402

DRAWS = 20
MODELS = {
    "ridge": lambda s: [make_pipeline(StandardScaler(), Ridge(alpha=10.0))],
    "boosted trees": lambda s: [HistGradientBoostingRegressor(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=20,
                                                              early_stopping=False, random_state=s)],
    "random forest": lambda s: [RandomForestRegressor(n_estimators=300, min_samples_leaf=20, max_features=1 / 3, n_jobs=-1, random_state=s)],
    "neural net": lambda s: [TransformedTargetRegressor(
        regressor=make_pipeline(StandardScaler(), MLPRegressor((16, 8), alpha=1.0, max_iter=500, early_stopping=True, random_state=s + k)),
        transformer=StandardScaler()) for k in range(3)],
}


def rho(a, b):
    r = spearmanr(a, b).statistic    # average ranks: tree predictions are piecewise constant, full of ties
    return 0.0 if np.isnan(r) else float(r)


def predict(name, Xa, ya, Xs, seed=0):
    fits = [m.fit(Xa, ya) for m in MODELS[name](seed)]
    return [np.mean([m.predict(X) for m in fits], axis=0) for X in Xs]


def evaluate(label, X, y, when, split, rng, ridge_check=None):
    o = np.argsort(when, kind="stable"); X, y, when = X[o], y[o], when[o]
    early = when < split
    print(f"\n--- {label}: {len(y)} trades, early {early.sum()} / late {(~early).sum()}, mean trade {y.mean():+.1%}", flush=True)
    passed, ridge_rho = {}, []
    for direction, a, b in (("early → late", early, ~early), ("late → early", ~early, early)):
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
    return {name: all(v) for name, v in passed.items()}


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
            if ok:
                won[name].add(uni)
    print("\n=== the rule: a model must pass on the century (F) and on a modern sample (E or G)")
    for name, unis in won.items():
        reopen = "F" in unis and bool(unis & {"E", "G"})
        print(f"  {name:14} passes on: {', '.join(sorted(unis)) or 'nothing'} → {'REOPEN (stage 2)' if reopen else 'closed'}")


if __name__ == "__main__":
    main()
