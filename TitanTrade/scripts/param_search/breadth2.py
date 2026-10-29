"""Member breadth for the insurance (brainstorm #10; Decision 068 addendum, 2026-10-29).

The two-signal insurance halves exposure while the market is below its 200-day SMA AND fewer than half of the 11
sector ETFs are above theirs. The analogue study found breadth is one of the two state variables that move the forward
year; this asks whether a breadth measured on the index's members (the point-in-time S&P 500, 2016 →) or on the 49
industries (1927 →) is a better second signal than the 11 ETFs. Pre-registered hypotheses, before any result:
  B1  member breadth and sector breadth agree on the big episodes (2018-Q4, 2020, 2022, 2025): the de-risked share of
      sessions differs by a few points, not tens;
  B2  the book's excess, drawdown and Sharpe move within ±0.3 pp / ±2 points / ±0.03 — inside the spread of a placebo
      (the breadth series shuffled in 63-session blocks, 20 draws);
  B3  on the century, adding industry breadth as the second condition to the SMA-only insurance *loosens* it (fewer
      de-risked sessions): return up, drawdown worse — the insurance trade-off, not an improvement.
Book = min(insurance ×0.5, shock ×0.5) × (0.4 dip + 0.6 momentum), de-risked capital at 0. Run from TitanTrade/:
uv run --with numpy python -I scripts/param_search/breadth2.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402
import screens  # noqa: E402


def breadth_series(mkt, member=None, sma=200):
    """Share of names above their own ``sma``-day SMA each day (members only when a mask is given) → {date: share}."""
    _, above, _, _ = mkt.pre(90, sma, 200)
    ok = ~np.isnan(mkt.names)
    if member is not None:
        ok &= member
    cnt = ok.sum(1)
    with np.errstate(invalid="ignore"):
        b = np.where(cnt > 0, (above & ok).sum(1) / np.maximum(cnt, 1), np.nan)
    return dict(zip(mkt.dates, b))


def aligned(series, dd):
    return master.prev(np.array([series.get(t, np.nan) for t in dd])[1:])


def block_shuffle(x, rng, block=63):
    n = len(x); idx = np.arange(0, n, block); order = rng.permutation(len(idx))
    out = np.concatenate([x[idx[k]:idx[k] + block] for k in order])
    return out[:n]


def main():
    rng = np.random.default_rng(10)
    eps_all = {"decade": [("2018Q4", "2018-09-20", "2018-12-24"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12"), ("2025", "2025-02-19", "2025-04-08")],
               "century": [("1929-32", "1929-09-03", "1932-06-01"), ("1973-74", "1973-01-11", "1974-10-03"), ("2008", "2007-10-09", "2009-03-09"), ("2009reb", "2009-03-09", "2010-03-09")]}
    E, memb = screens.load_universe()
    F = datasets.load("F_french_49ind_1926")
    sec = datasets.load("D_alpaca_sectors_2016")
    alt = {"decade": {"sector ETFs (live)": breadth_series(sec), "S&P 500 members": breadth_series(E, memb)},
           "century": {"49 industries": breadth_series(F)}}
    for name, dd, lvl, r, bear_live, split, eras in carry.sets():
        core = 0.4 * r["dip"] + 0.6 * r["mom"]; shock = master.shock_flags(lvl, -0.07, 10, 20); eps = eps_all[name]
        spy_below = master.prev(master.sma_above(lvl)[1:]) == 0.0 if name == "century" else None

        def book(bear):
            return carry.exposure(bear, shock) * core

        def episodes(rr):
            c = np.concatenate([[1.0], np.cumprod(1 + rr)]); m = np.concatenate([[1.0], np.cumprod(1 + r["mkt"])]); out = []
            for _, a, b in eps:
                ia = next(k for k, x in enumerate(dd) if x >= a); ib = next(k for k, x in enumerate(dd) if x >= b); out.append(c[ib] / c[ia] - m[ib] / m[ia])
            return out

        def line(label, bear, s, pl=None):
            print(f"{label:46} {s['excess']:+7.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['dd']:6.1%} {s['sharpe']:5.2f} | {np.mean(bear):5.1%} | " + " ".join(f"{x:+8.1%}" for x in episodes(book(bear)))
                  + (f" | placebo {np.median(pl):+5.2%} [{np.percentile(pl, 10):+5.2%}…{np.percentile(pl, 90):+5.2%}]" if pl is not None else ""))

        sb = master.score(book(bear_live), r["mkt"], dd, split, eras)
        print(f"\n=== member breadth — {name} {dd[0]} → {dd[-1]}: recommended book {sb['excess']:+.2%}; columns: excess, IS, OOS | DD, Sharpe | insurance-on share | episodes (book − market)")
        print(f"{'insurance rule':46} {'excess':>7} {'IS':>6} {'OOS':>6} | {'DD':>6} {'Sh':>5} | {'on':>5} | " + " ".join(f"{x[0]:>8}" for x in eps))
        line("live rule (reference)", bear_live, sb)
        if name == "decade":
            # the live rule is SPY < SMA200 AND sector breadth < 0.5 (from the ETF bars, 2016 warm-up)
            cur = datasets.load("A_alpaca_names_2016"); i0 = cur.dates.index(dd[0]); n = len(dd)
            _, _, spy_above, _ = cur.pre(90, 150, 200)
            spy_below = master.prev(spy_above[i0:i0 + n][1:]) == 0.0
            line("SMA200 only (no breadth condition)", spy_below, master.score(book(spy_below), r["mkt"], dd, split, eras))
        else:
            line("SMA200 only (= the live century rule)", spy_below, master.score(book(spy_below), r["mkt"], dd, split, eras))
        for bname, series in alt[name].items():
            b = aligned(series, dd)
            for thr in (0.4, 0.5, 0.6):
                bear = spy_below & (np.nan_to_num(b, nan=1.0) < thr)
                s = master.score(book(bear), r["mkt"], dd, split, eras)
                pl = None
                if thr == 0.5:
                    pl = []
                    for _ in range(20):
                        b2 = block_shuffle(np.nan_to_num(b, nan=1.0), rng)
                        pl.append(master.score(book(spy_below & (b2 < 0.5)), r["mkt"], dd, split, eras)["excess"])
                    pl = np.array(pl)
                line(f"SMA200 AND {bname} < {thr:.0%}", bear, s, pl)
            bear = np.nan_to_num(b, nan=1.0) < 0.5
            line(f"{bname} < 50% alone (no SMA condition)", bear, master.score(book(bear), r["mkt"], dd, split, eras))


if __name__ == "__main__":
    main()
