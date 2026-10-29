"""Residual momentum as a self-picked name sleeve (brainstorm #7; Decision 068 addendum, 2026-10-29).

Blitz, Huij and Martens: momentum measured on the part of a stock's return the market does not explain (the
residual of a regression on the market) has about half the crash risk of raw momentum and a steadier premium.
Decision 067 found a self-picked raw-momentum sleeve fails the reverse walk-forward and chose the ETF; this asks
whether the residual version changes that. Point-in-time S&P 500 (742 names, membership mask), yearly rebalance in
January from 2018 (two years of daily data for the beta), equal weight, 0.05 % a side on turnover, judged vs SPY, vs
the equal-weight membership and vs SPMO; split 2022; also through 2025-12-31 because 2026 dominates every momentum
number. Residual momentum = the sum of daily residuals (r − β r_SPY, β over the prior 480 sessions) from 252 to 21
sessions before the rebalance, divided by their standard deviation. Pre-registered hypotheses:
  RM1  residual momentum alone beats SPY on the decade (+2 … +6) and, like raw momentum, is 2026-heavy;
  RM2  its edge over raw 12-1 momentum (S1) is not positive in both halves;
  RM3  it does not beat SPMO in both halves after costs — the ETF stays the vehicle;
  RM4  its worst drawdown is not more than 5 points better than raw momentum's (the published "half the crash risk"
       is a long-short property);
  placebo: 20 random 15-name picks per rebalance.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/resmom.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402
import screens  # noqa: E402

BETA_WIN = 480   # 2018-01 is session ~503 of the 2016 → data; 480 keeps the first rebalance


def residual_momentum(P, spy, t):
    """Per name at index t: sum of residual daily returns over [t−252, t−21) / their std; NaN when data is short."""
    w0, w1 = t - BETA_WIN, t
    R = P[w0 + 1:w1 + 1] / P[w0:w1] - 1; m = spy[w0 + 1:w1 + 1] / spy[w0:w1] - 1
    out = np.full(P.shape[1], np.nan)
    ok = ~np.isnan(R).any(0)
    mc = m - m.mean(); Rc = R[:, ok] - R[:, ok].mean(0)
    beta = (Rc * mc[:, None]).sum(0) / (mc ** 2).sum()
    resid = R[:, ok] - beta * m[:, None]
    seg = resid[BETA_WIN - 252:BETA_WIN - 21]
    out[ok] = seg.sum(0) / (seg.std(0) + 1e-12)
    return out


def main():
    rng = np.random.default_rng(7)
    mkt, member = screens.load_universe()
    P, spy, dates = mkt.names, mkt.spy, mkt.dates
    cache = {}
    orig = screens.features
    screens.features = lambda P_, spy_, t: {**orig(P_, spy_, t), "t": t}   # the screen needs the rebalance index

    def resmom_screen(f):
        t = f["t"]
        if t not in cache:
            cache[t] = residual_momentum(P, spy, t) if t >= BETA_WIN else np.full(P.shape[1], np.nan)
        return cache[t]

    def random_screen(f):
        return rng.random(P.shape[1])

    i0 = next(k for k, d in enumerate(dates) if d >= "2018-01-01")
    spmo = datasets.alpaca("SPMO"); sp = np.array([spmo.get(d, np.nan) for d in dates])

    def report(label, curve, start_idx, n_rows=None):
        d = dates[start_idx:start_idx + len(curve)]; spyc = spy[start_idx:start_idx + len(curve)] / spy[start_idx]
        ks = next(k for k, x in enumerate(d) if x >= "2022-01-01"); k25 = max(k for k, x in enumerate(d) if x <= "2025-12-31")
        m, s = fastbt.metrics(curve, []), fastbt.metrics(spyc, [])
        c = lambda a, b: fastbt.metrics(a[:b + 1], [])["cagr"]  # noqa: E731
        print(f"{label:44} {m['cagr'] - s['cagr']:+6.1%} (IS {c(curve, ks) - c(spyc, ks):+5.1%} / OOS {fastbt.metrics(curve[ks:], [])['cagr'] - fastbt.metrics(spyc[ks:], [])['cagr']:+5.1%}; through 2025 {c(curve, k25) - c(spyc, k25):+5.1%}) | DD {m['max_drawdown']:6.1%} vs {s['max_drawdown']:6.1%} | Sharpe {m['sharpe']:4.2f} vs {s['sharpe']:4.2f}")
        return m["cagr"] - s["cagr"], m["max_drawdown"]

    print(f"=== residual momentum on the point-in-time S&P 500, yearly from {dates[i0]}, equal weight, costs 0.05 %/side")
    res = {}
    for label, screen, n in (("S1 raw momentum 12-1, top 15", screens.SCREENS["S1 momentum"], 15), ("residual momentum, top 15", resmom_screen, 15),
                             ("residual momentum, top 30", resmom_screen, 30), ("equal-weight membership (all)", None, 0)):
        curve, spyc, dsl, to = screens.simulate(mkt, member, screen, n, "Y", start_year=2018)
        res[label] = report(label, curve, i0)
    spc = sp[i0:] / sp[i0]; spc = spc[~np.isnan(spc)]
    report("SPMO held", spc, i0)
    pl = []
    for _ in range(20):
        curve, _, _, _ = screens.simulate(mkt, member, random_screen, 15, "Y", start_year=2018)
        m = fastbt.metrics(curve, []); s = fastbt.metrics(spy[i0:i0 + len(curve)] / spy[i0], []); pl.append(m["cagr"] - s["cagr"])
    pl = np.array(pl)
    print(f"placebo (20 random 15-name picks per year): excess median {np.median(pl):+.1%} [p10 {np.percentile(pl, 10):+.1%} … p90 {np.percentile(pl, 90):+.1%}]")


if __name__ == "__main__":
    main()
