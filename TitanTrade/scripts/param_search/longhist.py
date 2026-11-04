"""The book on real ETFs through two more bears — 1999 → on Tiingo's adjusted history (roadmap B11; Decision 092
research, 2026-11-04; the operator's free key arrived the same day).

Until now the sector dip sleeve was tested on Alpaca's 2016 → bars and the century on French industry portfolios; the
Yahoo 1999 → files of Decision 062 never came back after the rate-limiting. Tiingo gives the 11 sector ETFs from their
listing (nine from 1998-12, XLRE 2015, XLC 2018), SPY from 1993, MTUM from 2013, SPMO from 2015 and the 15 names from
theirs — dividend- and split-adjusted. The window is 1999-11-01 → 2026-11-03 (the first ten months feed the 200-day
average), split 2013-05-01 (the midpoint), three eras: 1999-11 → 2007-10 (the dot-com bear and the recovery), 2007-10 →
2015-01 (the crisis and its rebound), 2015-01 → (the modern era). The momentum sleeve has no investable fund before
2013, so the book's sleeve is a **labelled splice**: the French top momentum decile (frictionless, the century's series)
to 2013-04-17, MTUM 2013-04-18 → 2015-10-11, SPMO from 2015-10-12.

Pre-registered hypotheses (the expected numbers were written before the first run):
  H1  the sector floor — the live dip rule on the sector ETFs 1999 →, alone: with the two switches off ≈ 0 … +1 pp/yr vs
      SPY over the 27 years, the first half (two bears) 1 … 3 pp better than the second (one bull); relative gains in
      2000–02 (+5 … +15 over the bear, the trend filter keeps it out) and losses in the rebound years 2003 and 2009
      (−5 … −10 each); with the switches ×0.5 the drawdown 10 … 20 points shallower than SPY's in both slow bears.
  H2  the two-sleeve book 1999 → (min(insurance ×0.5, shock ×0.5) × (0.4 dip + 0.6 the spliced momentum)): +2 … +4 pp/yr
      vs SPY, positive in both halves and all three eras; worst falls 2000–02 and 2007–09 at −30 … −40 % against SPY's
      −47 / −55; the lagging years 2003 and 2009 (−10 … −20 relative, the momentum crash of 2009 inside); the luck
      meter's band clear of zero (t > 2 on 27 years).
  H3  the parameter re-check on two more bears runs through `etfparams.py` with the new universe G beside D and F
      (its own hypotheses P1–P5 and its rule: a cell is proposed only if it is more than one step from the live cell,
      beats it out of sample on D, F and G by > 0.5 pp, and does so inside the book; anything else → no change).
      Expected: the live cell on the plateau on G as on D and F; no change.
  H4  the 15 names 1999 → (as they list; chosen in 2026 — hindsight by construction): the dip rule alone ≥ +5 pp/yr vs
      SPY, the hindsight yardstick the sector floor is measured against, never evidence.
  H5  data: Tiingo's adjusted closes agree with Alpaca's dividend-adjusted bars on 2016 → — median |Δ daily return|
      < 0.02 %, the 99th percentile < 0.2 % — except a handful of March-2020 sessions that differ by 2 … 7 % (seen in
      the preview, reported per symbol); the 2017-01-03 → 2026-10-12 segment of the Tiingo-based blend reproduces the
      Alpaca-based decade blend (+1.36, Decision 081) within ±0.3 pp/yr.
Drop rule: nothing here changes the live book; H1 / H2 / H4 / H5 are knowledge (the first look at the real ETFs through
2000–02 and 2008), H3 follows `etfparams.py`'s rule. The volatility-managed momentum share (C1) stays closed: no
investable momentum fund covers a momentum crash (MTUM lists in 2013), so the splice cannot reopen it.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/longhist.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402
from books import LIVE, exposure, prev  # noqa: E402

START, SPLIT = "1999-11-01", "2013-05-01"
ERAS = [("1999-11-01", "2007-10-01"), ("2007-10-01", "2015-01-01"), ("2015-01-01", "2026-12-31")]
SECT = datasets.SECT


def rets_on(dates, series):
    """Daily returns of a {date: level} series on the return days dates[1:]; a day missing from the series → 0."""
    lv = np.array([series.get(d, np.nan) for d in dates]); out = np.zeros(len(dates) - 1)
    for k in range(1, len(dates)):
        a, b = lv[k - 1], lv[k]
        if np.isfinite(a) and np.isfinite(b) and a > 0:
            out[k - 1] = b / a - 1
    return out


def build(key, start=START):
    """The sleeve on fastbt, the insurance flags, SPY and the dates for a Tiingo universe, the books.decade() way."""
    mkt = datasets.load(key); r0 = fastbt.run(mkt, LIVE, start, None)
    i0 = mkt.dates.index(r0["start"]); curve = r0["_curve"]; n = len(curve); dd = mkt.dates[i0:i0 + n]
    _, _, spy_above, breadth = mkt.pre(90, 150, 200)
    bear = (prev(spy_above[i0:i0 + n][1:]) == 0.0) & (prev(breadth[i0:i0 + n][1:]) < 0.5)
    spy = mkt.spy[i0:i0 + n]
    return dict(mkt=mkt, r0=r0, dd=dd, dip=curve[1:] / curve[:-1] - 1, mkt_r=spy[1:] / spy[:-1] - 1, spy=spy, bear=bear)


def momentum_splice(dd):
    fr = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")["Hi PRIOR"]
    pieces = [("French top decile", rets_on(dd, fr), None, "2013-04-17"), ("MTUM", rets_on(dd, datasets.tiingo("MTUM")), "2013-04-18", "2015-10-11"),
              ("SPMO", rets_on(dd, datasets.tiingo("SPMO")), "2015-10-12", None)]
    out = np.zeros(len(dd) - 1); d1 = np.array(dd[1:])
    for _, r, a, b in pieces:
        m = np.ones(len(d1), bool)
        if a: m &= d1 >= a
        if b: m &= d1 <= b
        out[m] = r[m]
    return out


def episodes(dd, r_mkt, books, floor=-0.20):
    m = np.concatenate([[1.0], np.cumprod(1 + r_mkt)]); peak = np.maximum.accumulate(m); ddm = m / peak - 1; out = []; i = 0
    curves = {k: np.concatenate([[1.0], np.cumprod(1 + v)]) for k, v in books.items()}
    while i < len(ddm):
        if ddm[i] < floor:
            j = i
            while j < len(ddm) and ddm[j] < 0: j += 1
            lo = i + int(np.argmin(ddm[i:j])); s0 = int(np.nonzero(ddm[:i] == 0)[0].max())
            out.append((dd[s0][:7], dd[lo][:7], ddm[lo], {k: c[lo] / c[s0] - 1 for k, c in curves.items()})); i = j
        else: i += 1
    return out


def years(dd, r_book, r_mkt):
    c = np.concatenate([[1.0], np.cumprod(1 + r_book)]); m = np.concatenate([[1.0], np.cumprod(1 + r_mkt)]); out = {}
    for y in sorted({d[:4] for d in dd}):
        kk = [k for k, d in enumerate(dd) if d[:4] == y]
        if len(kk) > 60: out[y] = c[kk[-1]] / c[kk[0]] - m[kk[-1]] / m[kk[0]]
    return out


def fmt(label, s):
    return (f"  {label:52} {s['excess']:+7.2%} {s['is']:+7.2%} {s['oos']:+7.2%} | {s['dd']:6.1%} {s['sharpe']:5.2f} {s['worst_year']:+6.1%} | "
            + " ".join(f"{x:+5.1%}" for x in s["eras"]) + (f" | {master.luck_line(s)}" if "t" in s else ""))


def main():
    print("=== H5 — Tiingo against Alpaca on the 2016 → overlap (|Δ daily return|: median, 99th percentile, days over 0.5 %, the worst day)")
    for sym in ["SPY", "SPMO", "MTUM"] + SECT:
        t = datasets.tiingo(sym); a = datasets.alpaca(sym); ds = sorted(set(t) & set(a))
        rt = np.array([t[d] for d in ds]); ra = np.array([a[d] for d in ds]); diff = np.abs(rt[1:] / rt[:-1] - ra[1:] / ra[:-1])
        print(f"  {sym:5} {ds[0]} → {ds[-1]}: median {np.median(diff):.2e}, p99 {np.percentile(diff, 99):.2e}, > 0.5 %: {int((diff > 0.005).sum())} days, worst {diff.max():.1%} on {ds[1 + int(diff.argmax())]}")
    G = build("G_tiingo_sectors_1999"); dd, r_mkt, bear, spy = G["dd"], G["mkt_r"], G["bear"], G["spy"]
    shock = master.shock_flags(spy, -0.07, 10, 20); e = exposure(bear, shock); mom = momentum_splice(dd)
    sc = lambda rr, **kw: master.score(rr, r_mkt, dd, SPLIT, ERAS, **kw)  # noqa: E731
    print(f"\n=== the sector ETFs 1999 → on Tiingo: {dd[0]} → {dd[-1]} ({len(dd)} sessions), split {SPLIT}; de-risked {np.mean(e < 1):.1%} of sessions (insurance {np.mean(bear):.1%}, shock {np.mean(shock):.1%})")
    print(f"  {'book':52} {'excess':>7} {'IS':>7} {'OOS':>7} | {'DD':>6} {'Sh':>5} {'worst':>6} | eras 1999–07 2007–15 2015–")
    sm = sc(r_mkt); print(f"  {'SPY (the market): DD / Sharpe':52} {'':>7} {'':>7} {'':>7} | {sm['dd']:6.1%} {sm['mkt_sharpe']:5.2f}")
    books = {}
    books["H1 dip sleeve alone, switches off"] = G["dip"]
    books["H1 dip sleeve alone, switches ×0.5"] = e * G["dip"]
    books["momentum splice held (reference)"] = mom
    books["H2 the book: min(ins, shock) × (0.4 dip + 0.6 mom)"] = e * (0.4 * G["dip"] + 0.6 * mom)
    books["    … switches off"] = 0.4 * G["dip"] + 0.6 * mom
    scores = {}
    for label, rr in books.items():
        s = sc(rr, luck_draws=400 if label.startswith("H2") else 0); scores[label] = s; print(fmt(label, s))
    print("\n  the market's falls ≥ 20 % from a peak — the market, then each book over the same dates:")
    for a, b, x, falls in episodes(dd, r_mkt, {k: v for k, v in books.items() if not k.startswith("    ")}):
        print(f"    {a} → {b}: market {x:+.0%} | " + " | ".join(f"{k.split(' ')[0] if k[0] == 'H' else 'mom'} {v:+.0%}" for k, v in falls.items()))
    print("\n  relative years (book − SPY), the dip sleeve alone (off) / the book:")
    y1 = years(dd, books["H1 dip sleeve alone, switches off"], r_mkt); y2 = years(dd, books["H2 the book: min(ins, shock) × (0.4 dip + 0.6 mom)"], r_mkt)
    print("    " + "  ".join(f"{y}: {y1[y]:+.0%} / {y2[y]:+.0%}" for y in y1))
    print("\n=== H4 — the 15 names 1999 → (as they list; chosen in 2026: the hindsight yardstick)")
    H = build("H_tiingo_names_1999")
    sH = master.score(H["dip"], H["mkt_r"], H["dd"], SPLIT, ERAS); print(fmt("dip rule on the 15 names, switches off", sH))
    print("\n=== H5 — the decade segment: the Tiingo-based blend 2017-01-03 → 2026-10-12 against the Alpaca-based decade (Decision 081: +1.36 blend)")
    i = dd.index("2017-01-03"); j = dd.index("2026-10-12"); seg = slice(i, j)   # return days i … j-1 cover dates i+1 … j
    rr = (e * (0.4 * G["dip"] + 0.6 * mom))[seg]; s = master.score(rr, r_mkt[seg], dd[i:j + 1], "2022-01-01")
    print(f"  Tiingo blend 2017 → 2026-10: excess {s['excess']:+.2%} (IS {s['is']:+.2%} / OOS {s['oos']:+.2%}), DD {s['dd']:.1%}, Sharpe {s['sharpe']:.2f}  — the sleeve inside this segment starts on the ETF sleeve's own 1999 history (its cooldowns and slots carry in), so ±0.3 is the bar")


if __name__ == "__main__":
    main()
