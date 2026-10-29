"""The international book (roadmap E2; Decision 073 research, 2026-10-29).

The operator's second fear is a weaker US market and a weaker dollar, and every number behind the live book is
US-only. International equities are the one instrument class with a diversification case for this book: lost decades
differ by region (Japan 1990–2010, the US 2000–2010, Europe 2007–2017), the momentum premium is documented in every
developed region, and country ETFs are diversified baskets — the only universe class on which the dip rule has ever
been ≥ 0. The caveats are pre-registered too: equity correlations converge to 0.8–0.9 in a crash, so any
diversification is in the decades, not in the week that hurts; the ex-US ETFs reach back to 2016 only (one decade,
two halves — weaker evidence than the US century); US-listed ex-US ETFs carry the dollar.

Data: Kenneth French's regional daily factors and momentum (WML) 1990-11 → 2026-09, in USD (Developed ex-US, Europe,
Japan, Asia-Pacific ex-Japan; ``external/french_intl/``, zips unpacked in place); 39 region / country ETFs, Alpaca SIP
2016-01-04 →, dividend-adjusted (``alpaca_hist/intl/``): ACWX (MSCI ACWI ex-US) as the ex-US book's index and core,
IMTM / IDMO as the momentum vehicles, the 20 single-country funds as the dip universe (EWA EWC EWD EWG EWH EWI EWJ EWL
EWN EWP EWQ EWS EWT EWU EWW EWY EWZ FXI INDA MCHI); FRED DEXUSEU (USD per EUR) for the currency view. The US book is
``carry.sets()``'s decade (sector dip sleeve 40 / SPMO 60, exposure = min(insurance ×0.5, shock ×0.5)), 2017-01-03 →,
split 2022-01-01; the ex-US book is built the same way on its own index.

Pre-registered hypotheses (the expected numbers were written before the first run):
  I1  the momentum premium exists in every developed region: French WML, annualised mean, is positive in both halves
      (split 2008-01-01) for Developed ex-US, Europe and Asia-Pacific ex-Japan; Japan is the documented exception
      (≈ 0, either sign). Expected +3 … +8 pp/yr long-short ex-US, with the 2009 crash in every region. Each region's
      WML correlates +0.3 … +0.6 with the US WML daily — a related bet, not the same one.
  I2  an ex-US momentum ETF held outright beats its index: IMTM and / or IDMO vs ACWX, excess CAGR ≥ 0 in both halves
      (split 2022-01-01); expected +1 … +3 pp/yr (SPMO made +5.2 vs SPY; a long-only ex-US factor fund captures less).
      Also shown vs EFA and IEFA (the developed parent the vehicles actually track), and through 2025-12-31.
  I3  the sector-floor test on a new universe of baskets: the live dip rule on the 20 country ETFs, 3 × 25 % slots,
      ACWX as the residual, the insurance from the region's own breadth (ACWX below its 200-day SMA and fewer than half
      of the 20 countries above theirs) is ≥ 0 vs ACWX and ≥ 0 vs the equal-weight basket of the 20 in both halves.
      Expected 0 … +1 pp/yr (the sector floor is +0.4), more trades and more stops than the sectors (countries are
      more volatile and less correlated than sectors), drawdown no worse than ACWX's.
  I4  the ex-US two-sleeve book (country dip 40 / IMTM 60, exposure = min(insurance ×0.5, shock ×0.5) read off ACWX)
      and the US book bet on different things: the correlation of their daily *active* returns (each over its own
      index) is < 0.5, expected +0.1 … +0.3; their *total* returns correlate +0.7 … +0.85 (the crash caveat), about
      what ACWX and SPY do.
  I5  the global blend, US book w / ex-US book (1 − w), w = 0.5 / 0.6 / 0.7 (0.8 and 0.9 for the marginal), rebalanced
      daily, judged vs SPY and against the US book alone: at w = 0.6 or 0.7 it improves the drawdown or the Sharpe of
      the US book, and the return it gives back vs SPY is no larger than what the placebos give back at the same
      weight. Placebo P1 = ACWX held in the ex-US slot (does the ex-US *book* add anything beyond ex-US *exposure*?);
      placebo P2 = three random country ETFs, equal weight, re-drawn every calendar year, 20 draws (a random region
      weighting with the same slot count). Expected on this decade: the blend gives back 2 … 4 pp/yr vs SPY (2017 →
      2026 is the worst decade for ex-US in the record), Sharpe within ±0.05, drawdown 1 … 3 points shallower — so I5
      is expected to fail on return, and the test is run to find out.
  I6  every headline number is reported through 2025-12-31 beside the full period, because 2026 dominates momentum
      numbers.
  I7  currency: the US book, the ex-US book and the blends converted to euros with DEXUSEU over the decade (both
      halves), and — because the ETF decade holds neither — the US market vs the Developed ex-US market (French, USD)
      in euro terms over the dollar's fall 2002-01 → 2008-07 (EUR/USD 0.90 → 1.60) and its rise 2008-07 → 2022-09
      (1.60 → 0.96). Expected: in the fall ex-US beats the US by 5 … 10 pp/yr in euros, in the rise the reverse; the
      euro view moves every decade number by the dollar's annual drift (≈ ±1 pp/yr). CZK is not in the library; the
      euro is the proxy (the koruna has tracked the euro within a few percent a year). Reference only: DBEF vs EFA
      (hedged vs unhedged developed ex-US) over the decade — roadmap E4, not decided here.

Drop rules, written first:
  - I2 fails (no vehicle positive in both halves vs ACWX) or I3 fails (not ≥ 0 in both halves vs ACWX and vs the
    basket) → no ex-US book; the result is recorded and roadmap E3 stays closed.
  - I5 fails (no weight at which the blend improves the drawdown or the Sharpe, or the give-back exceeds the
    placebos') → no blend.
  - A Decision is proposed only if I2 and I3 and I5 all hold, and then only as a Decision with the expected numbers
    and the build (a second book under the same engine: ``watchlist`` = the 20 country ETFs, ``momentum_ticker`` =
    IMTM, ``core_ticker`` = ACWX, per-book cash reserve, overlay cap and drawdown breaker — roadmap C5), never applied
    without the operator's go.
  - Whatever the outcome, I1 and I7 are knowledge, not a build: they say whether the fear is addressable at all.

Costs: the ETF series are total return with expense ratios in the price; the dip run charges 0.05 % a side; the blends
are rebalanced daily without cost (as every blend in this harness). De-risked capital earns 0.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/intl.py
"""
import bisect
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402

COUNTRIES = ["EWA", "EWC", "EWD", "EWG", "EWH", "EWI", "EWJ", "EWL", "EWN", "EWP", "EWQ", "EWS", "EWT", "EWU", "EWW", "EWY", "EWZ", "FXI", "INDA", "MCHI"]
REGIONS = {"Developed ex-US": "Developed_ex_US", "Europe": "Europe", "Japan": "Japan", "Asia-Pacific ex-Japan": "Asia_Pacific_ex_Japan"}
START, SPLIT, THROUGH = "2017-01-03", "2022-01-01", "2025-12-31"
EPISODES = [("covid", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12"), ("2025", "2025-02-19", "2025-04-08")]
DOLLAR = [("1990-07 → 2008-01 (French full first half)", "1990-07-02", "2008-01-02"), ("2008-01 → 2026-09 (second half)", "2008-01-02", "2026-09-30"),
          ("1999-01 → 2002-01 (dollar up, 1.18 → 0.90)", "1999-01-04", "2002-01-02"), ("2002-01 → 2008-07 (dollar down, 0.90 → 1.60)", "2002-01-02", "2008-07-15"),
          ("2008-07 → 2022-09 (dollar up, 1.60 → 0.96)", "2008-07-15", "2022-09-27"), ("2022-09 → 2026-09 (dollar down, 0.96 → 1.17)", "2022-09-27", "2026-09-30"),
          ("1999-01 → 2026-09 (the whole euro era)", "1999-01-04", "2026-09-30")]


def levels(series, dd):
    """A {date: level} series on dd; a missing day carries the last level."""
    lv = np.array([series.get(t, np.nan) for t in dd])
    for k in range(1, len(lv)):
        if np.isnan(lv[k]): lv[k] = lv[k - 1]
    return lv


def rets(series, dd):
    lv = levels(series, dd); return np.nan_to_num(lv[1:] / lv[:-1] - 1)


def to_level(r):
    """{date: return} → {date: level}."""
    level, out = 100.0, {}
    for d in sorted(r):
        level *= 1 + r[d]; out[d] = level
    return out


def us_wml():
    cols, rows = datasets._french_section(f"{datasets.S}/french/F-F_Momentum_Factor_daily.csv", ",Mom")
    i = cols.index("Mom"); return {d: rows[d][i] / 100 for d in sorted(rows) if rows[d][i] is not None}


def fx_eur():
    """USD per EUR (FRED DEXUSEU) → {date: rate}; FRED's missing days are skipped."""
    out = {}
    for line in open(f"{datasets.S}/external/fred/DEXUSEU.csv").read().splitlines()[1:]:
        d, v = line.split(",")[:2]
        try: out[d] = float(v)
        except ValueError: pass
    return out


def in_eur(r, dd, fx):
    """A USD daily-return series on dd[1:] in euro terms: (1 + r) × fx[t−1] / fx[t] − 1."""
    f = levels(fx, dd); return (1 + r) * f[:-1] / f[1:] - 1


def eur_level(level, fx):
    ds = sorted(fx)
    def at(d):
        k = bisect.bisect_right(ds, d) - 1; return fx[ds[k]] if k >= 0 else None
    return {d: v / at(d) for d, v in level.items() if d >= ds[0]}


def cagr_window(level, a, b):
    """CAGR of a {date: level} series from the first date ≥ a to the last date ≤ b (calendar years)."""
    ds = sorted(level); i = next((k for k, d in enumerate(ds) if d >= a), None); j = max((k for k, d in enumerate(ds) if d <= b), default=None)
    if i is None or j is None or j <= i: return np.nan
    yrs = (datetime.date.fromisoformat(ds[j]) - datetime.date.fromisoformat(ds[i])).days / 365.25
    return (level[ds[j]] / level[ds[i]]) ** (1 / yrs) - 1


def cagr_r(r):
    return fastbt.metrics(np.concatenate([[1.0], np.cumprod(1 + r)]), [])["cagr"]


def sc(r, rm, dd, split=SPLIT, through=None):
    """master.score, optionally on the window through a date (returns r on dd[1:])."""
    if through:
        n = max(k for k, t in enumerate(dd) if t <= through); r, rm, dd = r[:n], rm[:n], dd[:n + 1]
    return master.score(r, rm, dd, split)


def ep(rr, rm, dd):
    c = np.concatenate([[1.0], np.cumprod(1 + rr)]); m = np.concatenate([[1.0], np.cumprod(1 + rm)]); out = []
    for _, a, b in EPISODES:
        ia = next(k for k, x in enumerate(dd) if x >= a); ib = next(k for k, x in enumerate(dd) if x >= b); out.append(c[ib] / c[ia] - m[ib] / m[ia])
    return out


HDR = f"{'':54} {'excess':>7} {'IS':>6} {'OOS':>6} | {'→2025':>7} | {'DD':>6} {'idx DD':>6} {'Sharpe':>6} | {'worst':>6} {'r3':>4}"


def row(label, r, rm, dd, extra=""):
    s = sc(r, rm, dd); t = sc(r, rm, dd, through=THROUGH)
    print(f"{label:54} {s['excess']:+7.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {t['excess']:+7.2%} | {s['dd']:6.1%} {s['mkt_dd']:6.1%} {s['sharpe']:6.2f} | {s['worst_year']:+6.1%} {s['roll3_pos']:4.0%}{extra}")
    return s


def main():
    rng = np.random.default_rng(73)
    # ---------------- I1: the momentum premium by region ----------------
    print("=== I1 — the momentum premium by region: French WML (long winners / short losers, USD), daily from 1990-11, split 2008-01-01; the US from the same date for comparison")
    print(f"{'region':24} {'ann mean':>8} {'90-07':>7} {'08-26':>7} {'t':>5} {'Sharpe':>6} {'worst yr':>14} {'2009':>7} | corr with US WML")
    usw = us_wml(); ks_i1 = "2008-01-01"
    for label, key in [("US (reference)", None)] + list(REGIONS.items()):
        w = usw if key is None else datasets.french_regional(key, "mom")
        ds = [d for d in sorted(w) if d >= "1990-11-01"]; x = np.array([w[d] for d in ds]); ks = next(k for k, d in enumerate(ds) if d >= ks_i1)
        t = x.mean() / x.std() * np.sqrt(len(x)); sh = x.mean() / x.std() * np.sqrt(252)
        yrs = {}
        for d, v in zip(ds, x): yrs.setdefault(d[:4], []).append(v)
        yr = {y: float(np.prod(1 + np.array(v)) - 1) for y, v in yrs.items() if len(v) > 60}; wy = min(yr, key=yr.get)
        common = [d for d in ds if d in usw]; corr = np.corrcoef([w[d] for d in common], [usw[d] for d in common])[0, 1] if key else 1.0
        print(f"{label:24} {x.mean() * 252:+8.1%} {x[:ks].mean() * 252:+7.1%} {x[ks:].mean() * 252:+7.1%} {t:5.1f} {sh:6.2f} {wy + ' ' + f'{yr[wy]:+.0%}':>14} {yr.get('2009', np.nan):+7.0%} | {corr:+.2f}")

    # ---------------- the decade: the US book (carry.sets) and the ex-US book built the same way ----------------
    _, dd, spy_lvl, r_us, bear_us, _, _ = carry.sets()[0]; n = len(dd)
    e_us = carry.exposure(bear_us, master.shock_flags(spy_lvl, -0.07, 10, 20)); book_us = e_us * (0.4 * r_us["dip"] + 0.6 * r_us["mom"])
    acwx = datasets.alpaca("ACWX", "intl"); ctry = {c: datasets.alpaca(c, "intl") for c in COUNTRIES}
    mk = fastbt.Market(acwx, ctry, ctry); j0 = mk.dates.index(START)
    assert mk.dates[j0:j0 + n] == dd, "the ex-US calendar differs from the US book's"
    r0 = fastbt.run(mk, master.LIVE, START, dd[-1]); dipx = r0["_curve"]; assert len(dipx) == n
    _, _, above_x, breadth_x = mk.pre(90, 150, 200)
    bear_x = (master.prev(above_x[j0:j0 + n][1:]) == 0.0) & (master.prev(breadth_x[j0:j0 + n][1:]) < 0.5)
    acwx_lvl = mk.spy[j0:j0 + n]; e_x = carry.exposure(bear_x, master.shock_flags(acwx_lvl, -0.07, 10, 20))
    rx = {"dip": dipx[1:] / dipx[:-1] - 1, "mkt": acwx_lvl[1:] / acwx_lvl[:-1] - 1}
    for s in ("IMTM", "IDMO", "EFA", "IEFA", "DBEF"): rx[s] = rets(datasets.alpaca(s, "intl"), dd)
    book_x = e_x * (0.4 * rx["dip"] + 0.6 * rx["IMTM"]); book_x2 = e_x * (0.4 * rx["dip"] + 0.6 * rx["IDMO"])
    cr = np.column_stack([rets(ctry[c], dd) for c in COUNTRIES]); r_ew = cr.mean(axis=1)
    print(f"\n=== the decade {dd[0]} → {dd[-1]} ({n - 1} sessions): US book = sector dip 40 / SPMO 60; ex-US book = country dip 40 / IMTM 60, both min(insurance ×0.5, shock ×0.5) on their own index; "
          f"de-risked sessions US {np.mean(e_us < 1):.1%} / ex-US {np.mean(e_x < 1):.1%} (insurance {np.mean(bear_x):.1%}, shock {np.mean(master.shock_flags(acwx_lvl, -0.07, 10, 20)):.1%} ex-US)")

    # ---------------- I2: the ex-US momentum ETF held vs its index ----------------
    print("\n=== I2 — an ex-US momentum ETF held outright vs its index (excess CAGR pp/yr; IS → 2021, OOS 2022 →; '→2025' = full excess through 2025-12-31; r3 = rolling 3-year windows ahead)")
    print(HDR)
    row("ACWX vs SPY (the ex-US decade in one line)", rx["mkt"], r_us["mkt"], dd)
    row("EFA vs ACWX (developed vs all ex-US)", rx["EFA"], rx["mkt"], dd)
    ok_i2 = {}
    for v in ("IMTM", "IDMO"):
        for ix in ("mkt", "EFA", "IEFA"):
            s = row(f"{v} held vs {'ACWX' if ix == 'mkt' else ix}", rx[v], rx[ix], dd)
            if ix == "mkt": ok_i2[v] = s["is"] >= 0 and s["oos"] >= 0
    row("SPMO held vs SPY (the US sleeve, reference)", r_us["mom"], r_us["mkt"], dd)

    # ---------------- I3: the dip rule on the 20 country ETFs ----------------
    print("\n=== I3 — the live dip rule on the 20 country ETFs (3 × 25 %, ACWX residual, insurance ×0.5 from the region's own breadth): the sector-floor test on a new universe of baskets")
    r1 = fastbt.run(mk, dict(master.LIVE, insurance_scale=0.5), START, dd[-1], want_trades=True); c1 = r1["_curve"]; r_floor = c1[1:] / c1[:-1] - 1; m1 = r1["metrics"]
    sec = datasets.load("D_alpaca_sectors_2016"); rs = fastbt.run(sec, dict(master.LIVE, insurance_scale=0.5), START, dd[-1], want_trades=True); cs = rs["_curve"]; assert len(cs) == n
    r_sfloor = cs[1:] / cs[:-1] - 1; ms = rs["metrics"]
    def tinfo(res, m):
        med = np.median([t["return"] for t in res["trades"]]) if res["trades"] else np.nan; ex = m["exits"]
        return f" | {m['trades']} trades ({m['trades'] / ((n - 1) / 252):.1f}/yr), {m['win_rate']:.0%} win, median {med:+.1%}, tp/stop/time {ex['tp']}/{ex['stop']}/{ex['time']}, risk-off {res['risk_off_days'] / (n - 1):.0%}"
    print(HDR)
    s3a = row("country dip book vs ACWX", r_floor, rx["mkt"], dd, tinfo(r1, m1))
    s3b = row("country dip book vs the EW basket of the 20", r_floor, r_ew, dd)
    row("EW basket of the 20 vs ACWX (the universe's own drag)", r_ew, rx["mkt"], dd)
    row("11-sector dip book vs SPY (the floor, reference)", r_sfloor, r_us["mkt"], dd, tinfo(rs, ms))
    ok_i3 = s3a["is"] >= 0 and s3a["oos"] >= 0 and s3b["is"] >= 0 and s3b["oos"] >= 0
    print("--- the ex-US two-sleeve book and its parts, each vs ACWX")
    print(HDR)
    row("country dip sleeve alone (insurance off inside, as in the book)", rx["dip"], rx["mkt"], dd)
    row("ex-US book: country dip 40 / IMTM 60, min(ins, shock)", book_x, rx["mkt"], dd)
    row("ex-US book with IDMO", book_x2, rx["mkt"], dd)
    row("ex-US book, no insurance, no shock", 0.4 * rx["dip"] + 0.6 * rx["IMTM"], rx["mkt"], dd)
    row("IMTM 100 %, min(ins, shock)", e_x * rx["IMTM"], rx["mkt"], dd)

    # ---------------- I4: correlations ----------------
    print("\n=== I4 — do the two books bet on different things? Daily correlations (active = the book minus its own index): full / IS / OOS")
    a_us, a_x = book_us - r_us["mkt"], book_x - rx["mkt"]; ks = next(k for k, t in enumerate(dd[1:]) if t >= SPLIT)
    def corr(a, b): return tuple(np.corrcoef(a[sl], b[sl])[0, 1] for sl in (slice(None), slice(0, ks), slice(ks, None)))
    for label, a, b in (("active: US book vs ex-US book", a_us, a_x), ("total: US book vs ex-US book", book_us, book_x), ("total: SPY vs ACWX", r_us["mkt"], rx["mkt"]),
                        ("active: sector dip sleeve vs country dip sleeve", r_us["dip"] - r_us["mkt"], rx["dip"] - rx["mkt"]), ("active: SPMO vs IMTM", r_us["mom"] - r_us["mkt"], rx["IMTM"] - rx["mkt"]),
                        ("total: US book vs IMTM held", book_us, rx["IMTM"])):
        c = corr(a, b); print(f"  {label:50} {c[0]:+.2f} / {c[1]:+.2f} / {c[2]:+.2f}")
    ok_i4 = corr(a_us, a_x)[0] < 0.5

    # ---------------- I5: the global blend ----------------
    print("\n=== I5 — the global blend: US book w / ex-US book (1 − w), rebalanced daily, vs SPY; 'give-back' = excess vs SPY minus the US book's; 'vs w-bench' = excess over w SPY + (1 − w) ACWX; placebos at the same weight")
    print(f"{'blend':54} {'vs SPY':>7} {'IS':>6} {'OOS':>6} | {'→2025':>7} | {'give-back':>9} {'vs w-bench':>10} | {'DD':>6} {'Sharpe':>6} | {'worst':>6} {'r3':>4} | " + " ".join(f"{e[0]:>6}" for e in EPISODES))
    s_us = sc(book_us, r_us["mkt"], dd)
    def blend_row(label, rr, w):
        s = sc(rr, r_us["mkt"], dd); t = sc(rr, r_us["mkt"], dd, through=THROUGH); e = ep(rr, r_us["mkt"], dd); vb = sc(rr, w * r_us["mkt"] + (1 - w) * rx["mkt"], dd)["excess"]
        print(f"{label:54} {s['excess']:+7.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {t['excess']:+7.2%} | {s['excess'] - s_us['excess']:+9.2%} {vb:+10.2%} | {s['dd']:6.1%} {s['sharpe']:6.2f} | {s['worst_year']:+6.1%} {s['roll3_pos']:4.0%} | " + " ".join(f"{x:+6.1%}" for x in e))
        return s
    blend_row("US book alone (the live design on the sector floor)", book_us, 1.0)
    blend_row("ex-US book alone (country dip 40 / IMTM 60)", book_x, 0.0)
    blend_row("ex-US book alone, IDMO", book_x2, 0.0)
    print(f"{'SPY':54} {'':>7} {'':>6} {'':>6} | {'':>7} | {'':>9} {'':>10} | {s_us['mkt_dd']:6.1%} {s_us['mkt_sharpe']:6.2f} |")
    yrs_arr = np.array([t[:4] for t in dd[1:]])
    def p2_basket():
        out = np.zeros(n - 1)
        for y in sorted(set(yrs_arr)):
            pick = rng.choice(cr.shape[1], 3, replace=False); m = yrs_arr == y; out[m] = cr[m][:, pick].mean(axis=1)
        return out
    ok_i5, ok_i5_idmo, both_halves = {}, {}, {}
    for w in (0.9, 0.8, 0.7, 0.6, 0.5):
        sb = blend_row(f"w = {w:.1f}: US book / ex-US book", w * book_us + (1 - w) * book_x, w)
        sp1 = blend_row("        P1: US book / ACWX held", w * book_us + (1 - w) * rx["mkt"], w)
        draws = [sc(w * book_us + (1 - w) * p2_basket(), r_us["mkt"], dd) for _ in range(20)]
        ex = np.array([d["excess"] for d in draws]); ddv = np.array([d["dd"] for d in draws]); shv = np.array([d["sharpe"] for d in draws])
        print(f"        P2: US book / 3 random countries yearly, 20 draws: vs SPY median {np.median(ex):+.2%} [{np.percentile(ex, 10):+.2%} … {np.percentile(ex, 90):+.2%}], DD median {np.median(ddv):.1%}, Sharpe median {np.median(shv):.2f}; the book blend beats the draws on excess in {np.mean(sb['excess'] > ex):.0%}")
        if w >= 0.7:   # the decomposition: which part of the ex-US slot does what (IDMO = the vehicle named in I2, not the pre-registered book)
            blend_row("        IMTM held only in the ex-US slot", w * book_us + (1 - w) * rx["IMTM"], w)
            blend_row("        IDMO held only in the ex-US slot", w * book_us + (1 - w) * rx["IDMO"], w)
        if w == 0.7:
            blend_row("        country dip sleeve only in the ex-US slot", w * book_us + (1 - w) * e_x * rx["dip"], w)
        si = blend_row("        ex-US book with IDMO (post hoc: vehicle swapped)", w * book_us + (1 - w) * book_x2, w)
        crit = lambda s: (s["dd"] > s_us["dd"] or s["sharpe"] > s_us["sharpe"]) and s["excess"] >= sp1["excess"] and s["excess"] >= np.median(ex)  # noqa: E731
        ok_i5[w] = crit(sb); ok_i5_idmo[w] = crit(si); both_halves[w] = (sb["is"] > 0 and sb["oos"] > 0, si["is"] > 0 and si["oos"] > 0)

    # ---------------- I7: currency ----------------
    print("\n=== I7 — currency. (a) The decade in euros (DEXUSEU): absolute CAGR USD / EUR, EUR halves, EUR drawdown and Sharpe")
    fx = fx_eur()
    print(f"{'':54} {'CAGR USD':>8} {'CAGR EUR':>8} | {'IS EUR':>7} {'OOS EUR':>7} | {'DD EUR':>7} {'Sh EUR':>6}")
    for label, rr in (("SPY", r_us["mkt"]), ("ACWX", rx["mkt"]), ("US book", book_us), ("ex-US book", book_x), ("blend 0.7 / 0.3", 0.7 * book_us + 0.3 * book_x), ("blend 0.5 / 0.5", 0.5 * book_us + 0.5 * book_x)):
        re_ = in_eur(rr, dd, fx); c = np.concatenate([[1.0], np.cumprod(1 + re_)]); m = fastbt.metrics(c, [])
        ks1 = next(k for k, t in enumerate(dd) if t >= SPLIT)
        print(f"{label:54} {cagr_r(rr):+8.1%} {m['cagr']:+8.1%} | {master.cagr(c[:ks1 + 1]):+7.1%} {master.cagr(c[ks1:]):+7.1%} | {m['max_drawdown']:7.1%} {m['sharpe']:6.2f}")
    f0, f1 = levels(fx, dd)[0], levels(fx, dd)[-1]; print(f"  EUR/USD {dd[0]} {f0:.2f} → {dd[-1]} {f1:.2f}: the dollar's drift over the decade {((f0 / f1) ** (252 / (n - 1)) - 1):+.1%}/yr in euro terms")
    print(HDR); row("DBEF (hedged developed) vs EFA (unhedged) — E4 reference", rx["DBEF"], rx["EFA"], dd)
    print("\n--- (b) The US market vs the regional markets (French, value-weighted, USD) across the dollar's regimes: CAGR in USD / in EUR (n/a before the euro, 1999)")
    mkts = {"US": datasets.french_market(), **{lab: to_level(datasets.french_regional(key, "mkt")) for lab, key in REGIONS.items()}}
    mkts_eur = {k: eur_level(v, fx) for k, v in mkts.items()}
    print(f"{'window':44} " + " ".join(f"{lab:>21}" for lab in mkts))
    for label, a, b in DOLLAR:
        cells = []
        for lab in mkts:
            cu = cagr_window(mkts[lab], a, b); ce = cagr_window(mkts_eur[lab], a, b) if a >= min(fx) else np.nan
            cells.append(f"{cu:+6.1%} / " + (f"{ce:+6.1%}" if not np.isnan(ce) else "   n/a"))
        print(f"{label:44} " + " ".join(f"{c:>21}" for c in cells))
    ds = sorted(fx); print("  EUR/USD at the window edges: " + ", ".join(f"{d} {fx[ds[bisect.bisect_right(ds, d) - 1]]:.2f}" for d in ("1999-01-04", "2002-01-02", "2008-07-15", "2022-09-27", "2026-09-30")))

    # ---------------- the pre-registered verdict ----------------
    print("\n=== pre-registered verdict")
    print(f"  I2 (a momentum vehicle ≥ 0 vs ACWX in both halves): {ok_i2} → {'holds' if any(ok_i2.values()) else 'FAILS'}")
    print(f"  I3 (country dip book ≥ 0 vs ACWX and vs the EW basket in both halves): {'holds' if ok_i3 else 'FAILS'}")
    print(f"  I4 (active correlation < 0.5): {'holds' if ok_i4 else 'FAILS'}")
    print(f"  I5 (blend improves DD or Sharpe and gives back no more than the placebos): " + ", ".join(f"w {w}: {'ok' if v else 'no'}" for w, v in ok_i5.items()) + f" → {'holds' if (ok_i5[0.6] or ok_i5[0.7]) else 'FAILS'}")
    print(f"     the same arithmetic on the IDMO variant (post hoc, not pre-registered): " + ", ".join(f"w {w}: {'ok' if v else 'no'}" for w, v in ok_i5_idmo.items())
          + "; blends positive vs SPY in both halves (pre-registered book / IDMO variant): " + ", ".join(f"w {w}: {'yes' if a else 'no'} / {'yes' if b else 'no'}" for w, (a, b) in both_halves.items()))
    go = any(ok_i2.values()) and ok_i3 and (ok_i5[0.6] or ok_i5[0.7])
    print(f"  Decision proposed (I2 and I3 and I5): {'YES — a second book under the same engine' if go else 'NO — recorded, E3 stays closed'}")


if __name__ == "__main__":
    main()
