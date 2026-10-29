"""The entry-time model, done properly (brainstorm #33; Decision 068 addendum, 2026-10-29).

"Can AI pick the trades?" — Decision 066 sorted 637 dip trades on the S&P 500 by entry-time features and every
feature flipped sign between halves. This fits a model instead, on the century's ~1,100 industry dip trades, with a
placebo. Features known at the signal close (nothing after it): dip depth (90-day), dip from the 252-day high, the
worst session of the last 20 (speed of the fall), the market above its 200-day SMA, the market's 12-month return,
20-day volatility and distance from its 252-day high, industry breadth (share above the 200-day SMA), the
industry's own 12-1 momentum and its relative strength vs the market. Model: ridge regression on standardised
features, target = the trade's return. Walk-forward: train 1927–74 → test 1975 →, and the reverse; on the decade the
S&P 500 point-in-time trades (3 × 25 % and 10 × 7.5 %), split 2022. Pre-registered hypotheses:
  M1  the out-of-sample rank correlation between prediction and outcome sits inside the placebo spread (the training
      outcomes shuffled, 20 draws) in at least one direction on every sample;
  M2  trades in the top half of predictions beat the bottom half by < 2 pp per trade out of sample, or not in both
      directions;
  M3  the only feature with the same sign in both eras is the market regime (above / below the SMA), which the
      design already uses.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/entrymodel.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import dynamic_universe as du  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402
import screens  # noqa: E402

LIVE = du.LIVE
FEATS = ["dip90", "dip252", "worst20", "mkt_above", "mkt_ret12", "mkt_vol20", "mkt_dd252", "breadth", "own_mom", "rel_str"]


def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def trade_table(mkt, member, start, params):
    res = fastbt.run(mkt, {**params, **({"eligible": member} if member is not None else {})}, start, None, want_trades=True)
    dates = mkt.dates; P = mkt.names; spy = mkt.spy; T = len(dates)
    dip_m, _, _, _ = mkt.pre(90, 150, 200)
    _, above200, _, _ = mkt.pre(90, 200, 200)
    ok = ~np.isnan(P) & (member if member is not None else True)
    cnt = ok.sum(1)
    with np.errstate(invalid="ignore"):
        breadth = np.where(cnt > 0, (above200 & ok).sum(1) / np.maximum(cnt, 1), np.nan)
    sma200 = fastbt.Market._col_roll(spy, 200, "sma")
    rs = np.concatenate([[np.nan], spy[1:] / spy[:-1] - 1])
    rows, y, when, kinds = [], [], [], []
    col = {t: j for j, t in enumerate(mkt.name_list)}
    for tr in res["trades"]:
        ie = dates.index(tr["exit_date"]); s = ie - tr["days"] - 1    # the signal close: fill is the next session
        j = col[tr["ticker"]]
        if s < 260 or np.isnan(P[s, j]) or np.isnan(P[s - 252, j]):
            continue
        with np.errstate(invalid="ignore", divide="ignore"):
            r20 = P[s - 19:s + 1, j] / P[s - 20:s, j] - 1
            f = [dip_m[s, j], 1 - P[s, j] / np.nanmax(P[s - 251:s + 1, j]), np.nanmin(r20),
                 1.0 if spy[s] > sma200[s] else 0.0, spy[s] / spy[s - 252] - 1, np.nanstd(rs[s - 19:s + 1]) * np.sqrt(252),
                 spy[s] / spy[s - 251:s + 1].max() - 1, breadth[s], P[s - 21, j] / P[s - 252, j] - 1,
                 (P[s - 21, j] / P[s - 252, j] - 1) - (spy[s - 21] / spy[s - 252] - 1)]
        if any(np.isnan(f)):
            continue
        rows.append(f); y.append(tr["return"]); when.append(dates[s]); kinds.append(tr["exit"])
    return np.array(rows), np.array(y), np.array(when), np.array(kinds)


def ridge(Xtr, ytr, Xte, lam=10.0):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-12
    A = (Xtr - mu) / sd; B = (Xte - mu) / sd
    w = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ (ytr - ytr.mean()))
    return B @ w + ytr.mean(), w


def evaluate(label, X, y, when, split, rng):
    tr = when < split; te = ~tr
    print(f"\n--- {label}: {len(y)} trades, train {tr.sum()} / test {te.sum()}, mean trade {y.mean():+.1%}")
    print(f"{'feature':10} " + " ".join(f"{'ρ ' + s:>10}" for s in ("train", "test")) + "   (Spearman with the trade return, each era)")
    for k, fn in enumerate(FEATS):
        print(f"{fn:10} {spearman(X[tr, k], y[tr]):+10.2f} {spearman(X[te, k], y[te]):+10.2f}")
    for direction, a, b in (("train early → test late", tr, te), ("train late → test early", te, tr)):
        pred, w = ridge(X[a], y[a], X[b])
        rho = spearman(pred, y[b]); top = pred >= np.median(pred)
        gap = y[b][top].mean() - y[b][~top].mean()
        pl = []
        for _ in range(20):
            p2, _ = ridge(X[a], rng.permutation(y[a]), X[b]); pl.append(spearman(p2, y[b]))
        pl = np.array(pl)
        print(f"  {direction:26}: OOS Spearman {rho:+.3f} (placebo {np.median(pl):+.3f} [{np.percentile(pl, 10):+.3f}…{np.percentile(pl, 90):+.3f}], beaten {np.mean(rho > pl):3.0%}); "
              f"top half {y[b][top].mean():+.1%} vs bottom half {y[b][~top].mean():+.1%} per trade (gap {gap:+.1%}); weights " + ", ".join(f"{fn} {wk:+.3f}" for fn, wk in zip(FEATS, w)))


def main():
    rng = np.random.default_rng(33)
    F = datasets.load("F_french_49ind_1926")
    X, y, when, _ = trade_table(F, None, "1927-07-01", LIVE)
    evaluate("F 49 industries 1927 →, 3 × 25 %", X, y, when, "1975-01-01", rng)
    E, memb = screens.load_universe()
    X, y, when, _ = trade_table(E, memb, "2017-01-03", LIVE)
    evaluate("E S&P 500 point-in-time, 3 × 25 %", X, y, when, "2022-01-01", rng)
    X, y, when, _ = trade_table(E, memb, "2017-01-03", {**LIVE, "slot_pct": 0.075, "max_slots": 10})
    evaluate("E S&P 500 point-in-time, 10 × 7.5 %", X, y, when, "2022-01-01", rng)


if __name__ == "__main__":
    main()
