"""Universe screens — can a point-in-time, price-based rule pick the names? (operator question, 2026-10-27)

Pre-registered hypotheses (written before any result was seen), all on the S&P 500 members as of each rebalance
date (742 names 2016 → 2026, delisted names included), features computed from the prior 252 trading days only:
  S1 momentum      top-N by 12-1 month return (Jegadeesh–Titman)
  S2 low vol       bottom-N by 1-year realised volatility (Ang et al., Blitz–van Vliet)
  S3 near high     top-N by closeness to the 52-week high (George–Hwang)
  S4 smooth mom    top-N by 1-year Sharpe (momentum with low volatility)
  S5 conservative  rank-average of momentum and low vol (Blitz–van Vliet without payout)
  S6 LT reversal   bottom-N by the return from year −3 to year −1 (De Bondt–Thaler); needs 3 years, so from 2019
  S7 quiet winners top-N by the fraction of positive days in the past year (Da–Gurun–Warachka "frog in the pan")
  S8 anti-momentum bottom-N by 12-1 momentum (the mirror of S1 — a sanity check, expected to lose)
Baselines: SPY (cap-weighted) and EW-all (equal-weight of every eligible member, same rebalance) — a screen only counts if it
beats EW-all, otherwise it is the equal-weight effect. Held equal-weight, rebalanced yearly (first session of January) or
quarterly, 0.05% per side on turnover, a delisted name's proceeds sit in cash until the next rebalance.
In-sample 2017–2021 / out-of-sample 2022 → 2026. Run: uv run --with numpy python -I scripts/param_search/screens.py"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402

S = datasets.S
COST = 0.0005
SPLIT = "2022-01-01"


def load_universe():
    union = json.load(open(f"{S}/universes/sp500_union_2016_2026.json"))
    syms = [s for s in union if os.path.exists(f"{S}/alpaca_hist/sp500_2016/{s}.json")]
    mkt = fastbt.Market(datasets.alpaca("SPY"), {s: datasets.alpaca(s, "sp500_2016") for s in syms},
                        {s: datasets.alpaca(s) for s in datasets.SECT})
    T, N = mkt.names.shape
    member = np.zeros((T, N), dtype=bool)
    idx = {s: j for j, s in enumerate(mkt.name_list)}
    for r in csv.DictReader(open(f"{S}/universes/sp500_ticker_start_end.csv")):
        j = idx.get(r["ticker"])
        if j is None:
            continue
        a = np.searchsorted(mkt.dates, r["start_date"]); b = np.searchsorted(mkt.dates, r["end_date"]) if r["end_date"] else T
        member[a:b, j] = True
    return mkt, member


def features(P, spy, t):
    """Price-based features at index t from the prior 252 sessions (row t included, nothing after it)."""
    w = P[t - 252:t + 1]; r = w[1:] / w[:-1] - 1
    with np.errstate(all="ignore"):
        mom = P[t - 21] / P[t - 252] - 1
        mom_6_1 = P[t - 21] / P[t - 126] - 1
        mom_12_2 = P[t - 42] / P[t - 252] - 1
        vol = np.nanstd(r, axis=0) * np.sqrt(252)
        mean = np.nanmean(r, axis=0)
        sharpe = mean / np.nanstd(r, axis=0) * np.sqrt(252)
        hi = P[t] / np.nanmax(w, axis=0) - 1
        pos = np.nanmean(r > 0, axis=0)
        ltrev = (P[t - 252] / P[t - 750] - 1) if t >= 750 else np.full(P.shape[1], np.nan)
        rs = mom - (spy[t - 21] / spy[t - 252] - 1)
    return {"mom": mom, "mom_6_1": mom_6_1, "mom_12_2": mom_12_2, "vol": vol, "sharpe": sharpe, "hi52": hi, "posdays": pos, "ltrev": ltrev, "rs": rs}


def rank_avg(*cols):
    out = np.zeros_like(cols[0], dtype=float)
    for c in cols:
        r = np.argsort(np.argsort(np.nan_to_num(c, nan=-1e9))).astype(float) / max(len(c) - 1, 1)
        out += r
    return out / len(cols)


SCREENS = {
    "S1 momentum":      lambda f: f["mom"],
    "S2 low vol":       lambda f: -f["vol"],
    "S3 near high":     lambda f: f["hi52"],
    "S4 smooth mom":    lambda f: f["sharpe"],
    "S5 conservative":  lambda f: rank_avg(f["mom"], -f["vol"]),
    "S6 LT reversal":   lambda f: -f["ltrev"],
    "S7 quiet winners": lambda f: f["posdays"],
    "S8 anti-momentum": lambda f: -f["mom"],
}


def rebalance_dates(dates, freq, anchor_month=1):
    """First session of each period: yearly (anchored on ``anchor_month``) or quarterly."""
    out, last = [], None
    for i, d in enumerate(dates):
        m = int(d[5:7])
        if freq == "Y":
            key = str(int(d[:4]) - (1 if m < anchor_month else 0)) if m == anchor_month or last is None else last
            if m != anchor_month:
                continue
        else:
            key = d[:4] + str((m - 1) // 3)
        if key != last and d >= "2017-01-01":
            out.append(i); last = key
    return out


def simulate(mkt, member, screen, n, freq, start_year=2017, anchor_month=1, picks_out=None, score_matrix=None):
    """Equal-weight hold of the screen's top-n, rebalanced; returns (curve, spy_curve, dates_slice, turnover_per_year).
    ``picks_out`` (list) receives (rebalance index, picked column indices) for eligibility masks. ``score_matrix``
    (T × N, NaN = ineligible) ranks by a precomputed score instead of a price-feature screen (qualpick.py)."""
    P, spy, dates = mkt.names, mkt.spy, mkt.dates
    rebs = [i for i in rebalance_dates(dates, freq, anchor_month) if dates[i] >= f"{start_year}-01-01"]
    i0 = rebs[0]; T = len(dates)
    value = np.zeros(P.shape[1]); cash = 1.0; curve = []; held = set(); turnover = 0.0
    for t in range(i0, T):
        if t > i0:
            r = P[t] / P[t - 1]; ok = (value > 0) & ~np.isnan(r)
            value[ok] *= r[ok]
            dead = (value > 0) & np.isnan(P[t]) & (t > 0)
            # a name whose series ended → its last value becomes cash
            ended = [j for j in np.nonzero(dead)[0] if np.all(np.isnan(P[t:min(t + 5, T), j]))]
            for j in ended:
                cash += value[j]; value[j] = 0.0
        if t in rebs:
            f = features(P, spy, t)
            elig = member[t] & ~np.isnan(P[t]) & ~np.isnan(P[t - 252])
            score = np.where(elig, score_matrix[t] if score_matrix is not None else (screen(f) if screen else 0.0), -np.inf)
            score = np.where(np.isnan(score), -np.inf, score)
            if screen is None and score_matrix is None:
                pick = np.nonzero(elig)[0]
            else:
                pick = np.argsort(-score, kind="stable")[:n]
                pick = pick[np.isfinite(score[pick])]
            total = value.sum() + cash
            new = set(pick.tolist()); churn = 1 - len(held & new) / max(len(new), 1) if held else 1.0
            turnover += churn
            cost = COST * 2 * churn * total if held else COST * total
            total -= cost
            value[:] = 0.0; cash = 0.0
            value[pick] = total / len(pick)
            held = new
            if picks_out is not None:
                picks_out.append((t, np.asarray(pick)))
        curve.append(value.sum() + cash)
    curve = np.array(curve); spyc = spy[i0:] / spy[i0]
    years = len(curve) / 252
    return curve, spyc, dates[i0:], turnover / years


def row(label, curve, spyc, dates, ew_curve=None, turnover=None):
    m = fastbt.metrics(curve, []); sp = fastbt.metrics(spyc, [])
    ks = next(k for k, d in enumerate(dates) if d >= SPLIT)
    is_x = fastbt.metrics(curve[:ks + 1], [])["cagr"] - fastbt.metrics(spyc[:ks + 1], [])["cagr"]
    oos_x = fastbt.metrics(curve[ks:], [])["cagr"] - fastbt.metrics(spyc[ks:], [])["cagr"]
    vs_ew = (m["cagr"] - fastbt.metrics(ew_curve, [])["cagr"]) if ew_curve is not None else float("nan")
    print(f"{label:30} CAGR {m['cagr']:6.1%}  vs SPY {m['cagr']-sp['cagr']:+6.1%}  (IS {is_x:+5.1%} / OOS {oos_x:+5.1%})  vs EW-all {vs_ew:+6.1%} | DD {m['max_drawdown']:6.1%} vs {sp['max_drawdown']:6.1%} | Sharpe {m['sharpe']:4.2f} vs {sp['sharpe']:4.2f}"
          + (f" | turnover {turnover:4.0%}/yr" if turnover is not None else ""))
    return m


def main():
    mkt, member = load_universe()
    print(f"universe: {len(mkt.name_list)} names, {mkt.dates[0]} → {mkt.dates[-1]}, members on 2017-01-03: {int(member[np.searchsorted(mkt.dates, '2017-01-03')].sum())}")
    for freq in ("Y", "Q"):
        print(f"\n=== rebalance {'yearly' if freq == 'Y' else 'quarterly'}, 2017-01 → {mkt.dates[-1]}, split {SPLIT}")
        ew, spyc, dates, to = simulate(mkt, member, None, 0, freq)
        row("EW-all (baseline)", ew, spyc, dates, None, to)
        for n in (15, 30):
            print(f"--- top {n}")
            for name, fn in SCREENS.items():
                sy = 2019 if name.startswith("S6") else 2017
                c, s2, d2, to = simulate(mkt, member, fn, n, freq, sy)
                ew2 = ew[len(ew) - len(c):] / ew[len(ew) - len(c)] if sy != 2017 else ew
                row(f"{name} N={n}" + (" (from 2019)" if sy != 2017 else ""), c, s2, d2, ew2, to)


def grid(mkt, member):
    """Momentum robustness: formation window × list size × yearly anchor month."""
    print("\n=== momentum grid: excess CAGR vs SPY, yearly rebalance; cells = median [min … max] over anchor months Jan/Apr/Jul/Oct")
    windows = {"6-1": "mom_6_1", "12-1": "mom", "12-2": "mom_12_2"}
    print(f"{'window':6} {'N':>3} | {'full':>22} | {'IS 2017-21':>22} | {'OOS 2022-26':>22} | {'maxDD med':>9}")
    for wname, key in windows.items():
        for n in (10, 15, 20, 30, 50):
            full, iss, oos, dds = [], [], [], []
            for am in (1, 4, 7, 10):
                c, spyc, dates, _ = simulate(mkt, member, (lambda f, k=key: f[k]), n, "Y", 2017, am)
                m = fastbt.metrics(c, []); sp = fastbt.metrics(spyc, [])
                ks = next(k for k, d in enumerate(dates) if d >= SPLIT)
                full.append(m["cagr"] - sp["cagr"]); dds.append(m["max_drawdown"])
                iss.append(fastbt.metrics(c[:ks + 1], [])["cagr"] - fastbt.metrics(spyc[:ks + 1], [])["cagr"])
                oos.append(fastbt.metrics(c[ks:], [])["cagr"] - fastbt.metrics(spyc[ks:], [])["cagr"])
            f = lambda v: f"{np.median(v):+6.1%} [{min(v):+5.1%}…{max(v):+5.1%}]"  # noqa: E731
            print(f"{wname:6} {n:3d} | {f(full)} | {f(iss)} | {f(oos)} | {np.median(dds):9.1%}")


def overlay(mkt, member):
    """The live dip rule restricted to a screen's picks (eligibility mask), vs SPY and vs holding the picks equal-weight."""
    LIVE = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12,
                slot_pct=0.25, max_slots=3, insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=0.5)
    print("\n=== live dip rule on a screened universe (eligibility = the screen's current picks), 2017-01 →")
    for sname, n in (("S1 momentum", 15), ("S1 momentum", 30), ("S3 near high", 15), ("S4 smooth mom", 15)):
        picks = []
        ew, spyc, dates, _ = simulate(mkt, member, SCREENS[sname], n, "Y", 2017, 1, picks)
        elig = np.zeros(mkt.names.shape, dtype=bool)
        for k, (t, pk) in enumerate(picks):
            t_next = picks[k + 1][0] if k + 1 < len(picks) else mkt.names.shape[0]
            elig[t:t_next, pk] = True
        for slots, slot in ((3, 0.25), (10, 0.075)):
            p = dict(LIVE, max_slots=slots, slot_pct=slot, eligible=elig)
            r = fastbt.run(mkt, p, dates[0], None, want_trades=True)
            m, sp = r["metrics"], r["spy"]; curve = r["_curve"]
            ks = next(k for k, d in enumerate(dates) if d >= SPLIT)
            is_x = fastbt.metrics(curve[:ks + 1], [])["cagr"] - fastbt.metrics(r["_spy_curve"][:ks + 1], [])["cagr"]
            oos_x = fastbt.metrics(curve[ks:], [])["cagr"] - fastbt.metrics(r["_spy_curve"][ks:], [])["cagr"]
            ewm = fastbt.metrics(ew, [])
            print(f"{sname} N={n:2d}, {slots:2d} slots: dip rule vs SPY {m['cagr']-sp['cagr']:+6.1%} (IS {is_x:+5.1%} / OOS {oos_x:+5.1%}) | EW-hold of the same picks vs SPY {ewm['cagr']-sp['cagr']:+6.1%} | DD {m['max_drawdown']:6.1%} (EW {ewm['max_drawdown']:6.1%}, SPY {sp['max_drawdown']:6.1%}) | Sharpe {m['sharpe']:4.2f} (EW {ewm['sharpe']:4.2f}, SPY {sp['sharpe']:4.2f}) | {r['n_trades']} trades, win {m['win_rate'] or 0:3.0%}")


def profile(mkt, member):
    """Where the operator's 2026-03-30 picks sat in the S&P 500 cross-section that day (percentile ranks)."""
    picks = ["CRWD", "ANET", "LLY", "DXCM", "HCA", "JPM", "GS", "DVN", "FANG", "URI", "GE", "DASH", "DECK", "FCX", "EQIX"]
    t = int(np.searchsorted(mkt.dates, "2026-03-30")); f = features(mkt.names, mkt.spy, t)
    elig = member[t] & ~np.isnan(mkt.names[t]) & ~np.isnan(mkt.names[t - 252])
    idx = {s: j for j, s in enumerate(mkt.name_list)}
    print(f"\n=== the operator's picks on {mkt.dates[t]} as percentiles of the {int(elig.sum())} eligible S&P members (100 = top)")
    keys = ["mom", "mom_6_1", "vol", "sharpe", "hi52", "posdays", "rs"]
    print(f"{'ticker':7}" + "".join(f"{k:>9}" for k in keys))
    table = []
    for s in picks:
        j = idx.get(s)
        if j is None or not elig[j]:
            print(f"{s:7} not in the S&P 500 then"); continue
        row_ = []
        for k in keys:
            v = f[k]; x = v[j]
            pct = float(np.mean(v[elig][~np.isnan(v[elig])] <= x) * 100) if not np.isnan(x) else float("nan")
            row_.append(pct)
        table.append(row_); print(f"{s:7}" + "".join(f"{x:9.0f}" for x in row_))
    med = np.nanmedian(np.array(table), axis=0)
    print(f"{'MEDIAN':7}" + "".join(f"{x:9.0f}" for x in med))


def trades(mkt, member):
    """Winners vs losers of the dip rule on the whole membership (10 slots), by entry-time feature quintile, IS and OOS."""
    LIVE = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12,
                slot_pct=0.075, max_slots=10, insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=0.5, eligible=member)
    r = fastbt.run(mkt, LIVE, "2017-01-03", None, want_trades=True)
    dates = mkt.dates; idx = {s: j for j, s in enumerate(mkt.name_list)}
    spy_sma = np.array([np.nan] * 200 + [mkt.spy[i - 200:i].mean() for i in range(200, len(dates))])
    rows = []
    for tr in r["trades"]:
        ie = dates.index(tr["exit_date"]) - tr["days"]; j = idx[tr["ticker"]]
        if ie < 252:
            continue
        f = features(mkt.names, mkt.spy, ie)
        w = mkt.names[ie - 90:ie + 1, j]
        rows.append(dict(ret=tr["return"], oos=dates[ie] >= SPLIT, mom=f["mom"][j], vol=f["vol"][j], sharpe=f["sharpe"][j],
                         dip=1 - mkt.names[ie, j] / np.nanmax(w), hi52=f["hi52"][j], posdays=f["posdays"][j], rs=f["rs"][j],
                         spy_regime=float(mkt.spy[ie] > spy_sma[ie]), exit=tr["exit"]))
    print(f"\n=== dip-rule trades on the whole membership, 10 slots: {len(rows)} trades ({sum(1 for x in rows if not x['oos'])} IS / {sum(1 for x in rows if x['oos'])} OOS); mean return {np.mean([x['ret'] for x in rows]):+.2%}, win {np.mean([x['ret'] > 0 for x in rows]):.0%}")
    for key in ("mom", "vol", "sharpe", "dip", "posdays", "rs"):
        vals = np.array([x[key] for x in rows]); rets = np.array([x["ret"] for x in rows]); oos = np.array([x["oos"] for x in rows])
        q = np.nanquantile(vals, [0.2, 0.4, 0.6, 0.8]); bins = np.digitize(vals, q)
        line = f"{key:8}"
        for b in range(5):
            m_is = rets[(bins == b) & ~oos]; m_oos = rets[(bins == b) & oos]
            line += f" | Q{b+1}: IS {np.mean(m_is) if len(m_is) else float('nan'):+5.1%} ({len(m_is):3d}) OOS {np.mean(m_oos) if len(m_oos) else float('nan'):+5.1%} ({len(m_oos):3d})"
        print(line)
    reg = np.array([x["spy_regime"] for x in rows]); rets = np.array([x["ret"] for x in rows])
    print(f"SPY above SMA200 at entry: {np.mean(rets[reg == 1]):+.2%} ({int((reg == 1).sum())}) | below: {np.mean(rets[reg == 0]) if (reg == 0).any() else float('nan'):+.2%} ({int((reg == 0).sum())})")


def refine(mkt, member):
    """Momentum sleeve: year-by-year consistency, a regime guard against momentum crashes, and core + sleeve blends."""
    dates = mkt.dates
    _, _, spy_above, breadth = mkt.pre(90, 150, 200)
    sma200 = np.array([np.nan] * 200 + [mkt.spy[i - 200:i].mean() for i in range(200, len(dates))])
    for wname, key in (("12-1", "mom"), ("6-1", "mom_6_1")):
        for freq, label in (("Y", "yearly"), ("H", "semi-annual")):
            if freq == "H":
                picks = []
                c1, spy1, d1, _ = simulate(mkt, member, lambda f, k=key: f[k], 15, "Y", 2017, 1)
                c2, spy2, d2, _ = simulate(mkt, member, lambda f, k=key: f[k], 15, "Y", 2017, 7)
                n = min(len(c1), len(c2)); c = np.sqrt((c1[-n:] / c1[-n]) * (c2[-n:] / c2[-n])); spyc = spy1[-n:] / spy1[-n]; dd = d1[-n:]
            else:
                c, spyc, dd, _ = simulate(mkt, member, lambda f, k=key: f[k], 15, "Y", 2017, 1)
            i0 = dates.index(dd[0])
            yrs = sorted({d[:4] for d in dd}); line = []
            for y in yrs:
                ks = [k for k, d in enumerate(dd) if d[:4] == y]
                line.append(f"{y[2:]}:{c[ks[-1]]/c[ks[0]] - spyc[ks[-1]]/spyc[ks[0]]:+.0%}")
            m = fastbt.metrics(c, []); sp = fastbt.metrics(spyc, [])
            print(f"momentum {wname} N=15 {label:11} vs SPY {m['cagr']-sp['cagr']:+5.1%} DD {m['max_drawdown']:6.1%} | by year: {' '.join(line)}")
    print("\n--- regime guards on the 6-1 N=15 yearly sleeve (exposure to the sleeve, remainder in SPY; signals from the previous session)")
    c, spyc, dd, _ = simulate(mkt, member, lambda f: f["mom_6_1"], 15, "Y", 2017, 1)
    i0 = dates.index(dd[0]); rs = c[1:] / c[:-1] - 1; rm = spyc[1:] / spyc[:-1] - 1
    sa = spy_above[i0:i0 + len(c)]; br = breadth[i0:i0 + len(c)]
    guards = {
        "none (100% sleeve)":                 lambda i: 1.0,
        "trend: sleeve only if SPY>SMA200":   lambda i: 1.0 if sa[i - 1] == 1.0 else 0.0,
        "two-signal (live insurance ×0.5)":   lambda i: 0.5 if (sa[i - 1] == 0.0 and br[i - 1] < 0.5) else 1.0,
        "two-signal, to SPY entirely":        lambda i: 0.0 if (sa[i - 1] == 0.0 and br[i - 1] < 0.5) else 1.0,
    }
    for g, fn in guards.items():
        e = np.array([fn(i) for i in range(1, len(c))]); r = e * rs + (1 - e) * rm
        curve = np.concatenate([[1.0], np.cumprod(1 + r)])
        m = fastbt.metrics(curve, []); sp = fastbt.metrics(spyc, [])
        ks = next(k for k, d in enumerate(dd) if d >= SPLIT)
        print(f"{g:36} vs SPY {m['cagr']-sp['cagr']:+5.1%} (IS {fastbt.metrics(curve[:ks+1], [])['cagr']-fastbt.metrics(spyc[:ks+1], [])['cagr']:+5.1%} / OOS {fastbt.metrics(curve[ks:], [])['cagr']-fastbt.metrics(spyc[ks:], [])['cagr']:+5.1%}) | DD {m['max_drawdown']:6.1%} vs {sp['max_drawdown']:6.1%} | Sharpe {m['sharpe']:4.2f} vs {sp['sharpe']:4.2f} | time in sleeve {np.mean(e):3.0%}")
    print("\n--- core + sleeve blends (daily-rebalanced weights; sleeve = 6-1 N=15 yearly with the two-signal ×0.5 guard)")
    e = np.array([0.5 if (sa[i - 1] == 0.0 and br[i - 1] < 0.5) else 1.0 for i in range(1, len(c))]); rsg = e * rs + (1 - e) * rm
    for w in (1.0, 0.7, 0.5, 0.3):
        r = w * rsg + (1 - w) * rm; curve = np.concatenate([[1.0], np.cumprod(1 + r)])
        m = fastbt.metrics(curve, []); sp = fastbt.metrics(spyc, [])
        ks = next(k for k, d in enumerate(dd) if d >= SPLIT)
        print(f"sleeve {w:3.0%} / SPY {1-w:3.0%}: vs SPY {m['cagr']-sp['cagr']:+5.1%} (IS {fastbt.metrics(curve[:ks+1], [])['cagr']-fastbt.metrics(spyc[:ks+1], [])['cagr']:+5.1%} / OOS {fastbt.metrics(curve[ks:], [])['cagr']-fastbt.metrics(spyc[ks:], [])['cagr']:+5.1%}) | DD {m['max_drawdown']:6.1%} vs {sp['max_drawdown']:6.1%} | Sharpe {m['sharpe']:4.2f} vs {sp['sharpe']:4.2f}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "screens"
    if mode == "screens":
        main()
    else:
        mkt_, member_ = load_universe()
        {"--grid": grid, "--overlay": overlay, "--profile": profile, "--trades": trades, "--refine": refine, "--s6": lambda m, mb: [row(f"S6 LT reversal N={n} (from 2019)", *simulate(m, mb, SCREENS["S6 LT reversal"], n, "Y", 2019)[:3], None, None) for n in (15, 30)]}[mode](mkt_, member_)
