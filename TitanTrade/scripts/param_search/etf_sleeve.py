"""Momentum ETF as the second sleeve (Decision 067 research, 2026-10-27): the dip book (sector ETFs = hindsight-free,
or the curated list) blended with a momentum ETF held outright. Consistency checks: year by year, weights, both ETFs,
rolling 3-year windows. Run: uv run --with numpy python -I scripts/param_search/etf_sleeve.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402

START, SPLIT = "2017-01-03", "2022-01-01"
LIVE = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12,
            slot_pct=0.25, max_slots=3, insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=0.5)


def cagr(c):
    return fastbt.metrics(c, [])["cagr"]


def main():
    cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index(START)
    _, _, spy_above, breadth = cur.pre(90, 150, 200)
    CUR = fastbt.run(cur, LIVE, START, None)["_curve"]; SEC = fastbt.run(sec, LIVE, START, None)["_curve"]
    spy = cur.spy[i0:]; d = dates[i0:]
    def etf(sym):
        v = datasets.alpaca(sym); return np.array([v.get(t, np.nan) for t in d])
    E = {s: etf(s) for s in ("MTUM", "SPMO")}
    n = min(len(CUR), len(SEC), len(spy), *(len(x) for x in E.values()))
    series = {"CUR": CUR[:n] / CUR[0], "SEC": SEC[:n] / SEC[0], "SPY": spy[:n] / spy[i0 - i0], **{k: v[:n] / v[0] for k, v in E.items()}}
    d = d[:n]; r = {k: c[1:] / c[:-1] - 1 for k, c in series.items()}
    r["BOTH"] = 0.5 * r["MTUM"] + 0.5 * r["SPMO"]
    e = np.array([0.5 if (spy_above[i0 + i - 1] == 0.0 and breadth[i0 + i - 1] < 0.5) else 1.0 for i in range(1, n)])
    for k in ("MTUM", "SPMO", "BOTH"):
        r[k + "g"] = e * r[k] + (1 - e) * r["SPY"]
    years = sorted({x[:4] for x in d})

    def curve(rr):
        return np.concatenate([[1.0], np.cumprod(1 + rr)])

    def yearly(rr):
        c = curve(rr); s = series["SPY"]; out = []
        for y in years:
            ks = [k for k, x in enumerate(d) if x[:4] == y]
            out.append(c[ks[-1]] / c[ks[0]] - s[ks[-1]] / s[ks[0]])
        return out

    print("=== year-by-year excess vs SPY (calendar years; 2026 to Oct 12)")
    print(f"{'book':34}" + "".join(f"{y[2:]:>7}" for y in years) + f"{'pos':>6}")
    books = {"SEC dip book": r["SEC"], "CUR dip book (hindsight)": r["CUR"], "MTUM held": r["MTUM"], "SPMO held": r["SPMO"],
             "SEC 70 / MTUM 30": .7 * r["SEC"] + .3 * r["MTUM"], "SEC 50 / MTUM 50": .5 * r["SEC"] + .5 * r["MTUM"],
             "SEC 50 / SPMO 50": .5 * r["SEC"] + .5 * r["SPMO"], "SEC 50 / both ETFs 50": .5 * r["SEC"] + .5 * r["BOTH"],
             "CUR 50 / both ETFs 50": .5 * r["CUR"] + .5 * r["BOTH"], "CUR 70 / both ETFs 30": .7 * r["CUR"] + .3 * r["BOTH"]}
    for k, rr in books.items():
        ys = yearly(rr); print(f"{k:34}" + "".join(f"{x:+7.1%}" for x in ys) + f"{sum(1 for x in ys if x > 0):3d}/{len(ys)}")

    print("\n=== weights: dip book share / momentum-ETF share (both ETFs 50/50, guarded by the two-signal insurance)")
    print(f"{'book':34} {'vs SPY':>7} {'IS':>7} {'OOS':>7} {'DD':>7} {'SPY DD':>7} {'Sharpe':>7} {'SPY':>5}")
    for base in ("SEC", "CUR"):
        for w in (1.0, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.0):
            rr = w * r[base] + (1 - w) * r["BOTHg"]; c = curve(rr); s = series["SPY"]
            ks = next(k for k, x in enumerate(d) if x >= SPLIT); m = fastbt.metrics(c, []); sp = fastbt.metrics(s, [])
            print(f"{base} {w:3.0%} / ETFs {1-w:3.0%}{'':20} {m['cagr']-sp['cagr']:+7.1%} {cagr(c[:ks+1])-cagr(s[:ks+1]):+7.1%} {cagr(c[ks:])-cagr(s[ks:]):+7.1%} {m['max_drawdown']:7.1%} {sp['max_drawdown']:7.1%} {m['sharpe']:7.2f} {sp['sharpe']:5.2f}")

    print("\n=== rolling 3-year excess CAGR vs SPY, SEC 50 / both ETFs 50 (guarded) — every 3-year window ending on a quarter")
    rr = .5 * r["SEC"] + .5 * r["BOTHg"]; c = curve(rr); s = series["SPY"]; out = []
    for k in range(756, n, 63):
        out.append((d[k], (c[k] / c[k - 756]) ** (1 / 3) - (s[k] / s[k - 756]) ** (1 / 3)))
    print("  " + "  ".join(f"{x[0][:7]}:{x[1]:+.1%}" for x in out))
    print(f"  windows positive: {sum(1 for x in out if x[1] > 0)}/{len(out)}, worst {min(x[1] for x in out):+.1%}, median {np.median([x[1] for x in out]):+.1%}")
    print("  same for SEC alone:", end=" ")
    c = curve(r["SEC"]); out = [((c[k] / c[k - 756]) ** (1 / 3) - (s[k] / s[k - 756]) ** (1 / 3)) for k in range(756, n, 63)]
    print(f"positive {sum(1 for x in out if x > 0)}/{len(out)}, worst {min(out):+.1%}, median {np.median(out):+.1%}")


if __name__ == "__main__":
    main()
