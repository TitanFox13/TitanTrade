"""The crypto programme — every coin, the catalogue of approaches, the weight as a loss budget (roadmap C3; Decision 096
research, 2026-11-04; free data from two exchanges' public APIs).

Operator (2026-11-04, after the one-coin probe of Decision 095): "we are talking about adding a whole new instrument
… you look at just one coin … why just 2 %? … we can do stocks on Alpaca and crypto somewhere else". So: the method
of Decisions 062 / 066 / 067 / 091 applied to the asset class — a point-in-time universe, pre-registered screens
against the right baseline and a placebo of the same shape, both halves, costs, two universes for the consensus
check, the family read as a plateau, the weight read as a curve with its risk legs. Nothing live changes.

**Universes** (`fetch_crypto.py --all`): **CB** — every USD pair Coinbase Exchange ever listed (495: 404 online, 91
delisted; a delisted pair's candles still serve, so what the venue dropped is in the data) from 2015-07 (BTC);
**BN** — every USDT pair on Binance (775 trading or halted) from 2017-08. Excluded by rule, written before any run:
stablecoins (the venue's flag, the usual names, and any coin whose trailing 1-year volatility is under 15 %/yr at a
rebalance), wrapped / staked / gold-backed duplicates (WBTC, CBBTC, TBTC, WETH, CBETH, WSTETH, RETH, STETH, LSETH,
PAXG, XAUT) and Binance's leveraged tokens (…UP / …DOWN / …BULL / …BEAR). What neither venue ever listed is still
missing — the asset class's own survivorship is not priced and cannot be. **The liquid set** at each month-end
rebalance: coins with ≥ 200 days of history, ranked by the median daily dollar volume of the past 90 days, the top
30 — the point-in-time investable universe (its breadth by year is printed: single digits before 2019 on CB).
**Sessions**: the book's NYSE sessions 2017-01-03 → 2026-10 (`books.decade()`, split 2022-01-01); a coin's session
return is its UTC-day close on the session date against the previous session's; signals read the day before.
**Costs**: 0.25 % per side on every trade (Alpaca / Kraken taker class; Coinbase Advanced's lowest tier is 0.6 %,
Binance's 0.1 % — the venue question is for go-live, the research charges the middle). Between rebalances positions
drift (no daily re-weighting inside a sleeve — equal weight re-set daily on 100 %-volatility coins would book a
frictionless "rebalancing return" of 10–20 %/yr that no account earns).
**Screens** (sleeve level first; then the book with the sleeve):
  H  hold — BTC; ETH; **EW-liquid** (the equal-weight of the liquid set, re-set monthly — the baseline every
     selection screen must beat, Decision 066's rule); the top-2 by volume.
  T  trend, time-series (on BTC, ETH, EW-liquid): SMA 50 / 100 / 200 / 300 sessions; own return over 1 / 3 / 6 / 12
     months with a 5-session skip. Read as the **family median**, never the best cell; placebo = the series with
     its calendar months shuffled, the family re-applied, 20 draws — the return edge and the drawdown cut vs holding.
  X  cross-section: rank the liquid set by the past 1 / 3 / 6-month return (5-session skip), hold the top 3 / 5 / 10
     equal-weight for a month; placebo = random picks of the same count from the same liquid set, 20 draws; the
     mirror (bottom-N) as the sanity row.
  D  the book's own dip rule (dip ≥ 8 % below the 90-session high, above the 150-session average, 3 slots, +20 /
     −12 / 60 sessions, `fastbt`) on the liquid coins, vs EW-liquid.
  V  volatility-scaled BTC: exposure = min(1, 50 % / trailing 30-session volatility), vs a constant exposure of the
     same average.
  E  inside the book's switches (× the same min(insurance, shock)) vs outside, for BTC held and EW-liquid.
  W  the weight curve 0 → 25 % in 2.5-point steps for BTC held, ETH held, EW-liquid (and a screen only if it
     survives), read two ways: the blend (constant weight re-set daily, the convention of every decade number) and
     **live-like** (the slice re-set to its target only when it drifts outside ±25 % of it, 0.25 % on the trade);
     per point the excess, both halves, the max drawdown, the worst relative year; the luck meter at 5 / 10 / 20 %.
Pre-registered hypotheses (the expected numbers were written before the first run):
  P1  holding: BTC ≈ +57 %/yr and ETH ≈ +77 over 2017 → on CB (Decision 095); **EW-liquid below BTC** over the
      window (+25 … +50 %/yr) with a deeper drawdown (−85 … −92 %), ahead of BTC in 2017–21 and behind after — the
      broad market of coins lost to bitcoin since 2021; the top-2 between BTC and ETH.
  P2  trend: the family median keeps 80 … 110 % of holding's return and cuts the drawdown 10 … 25 points; **both
      inside the shuffled-months band** (Decision 095: any average cuts a 70 %-volatility series' drawdown) — on
      all three series, both venues. Trend on a coin is placebo-level.
  P3  cross-section: top-5 by 3-month beats EW-liquid by +5 … +20 pp/yr in 2018–21 and by ≈ 0 after; the random-
      picks band is ±15 pp/yr wide at N = 5, so **inside the band in at least one half**, on at least one venue;
      the mirror loses by 10 or more. No cell survives both halves on both venues.
  P4  the dip rule on coins loses to EW-liquid by 5 … 15 pp/yr (as on momentum names, Decision 066: −14).
  P5  volatility scaling cuts BTC's drawdown 15 … 25 points for 20 … 40 % of its return; at the book level at 5 %
      within ±0.5 pp/yr of the constant sleeve — churn for nothing.
  P6  the switches: inside vs outside within ±0.5 (Decision 095: 2022 is the only overlap).
  P7  the curve: the blend's excess rises ≈ +0.6 pp/yr per point of BTC (2.96 / 5); **live-like keeps 50 … 80 % of
      it** (Decision 095's +2.96 at 5 % held about one point of frictionless daily rebalancing); the drawdown deepens
      ≈ 0.3 points per point of weight above 5 % (10 % ≈ −23, 20 % ≈ −29, 25 % ≈ −32 vs −20); the worst relative
      year, better than the book's own −11.3 at 5 %, is worse than it from ≈ 15 % (a −70 % coin year × 15 % ≈ −10
      points); t under 2 at every weight.
Drop rule / how it is read: a screen is *real* only if it beats its baseline (EW-liquid for X and D, holding for T
and V) after costs in both halves, above its placebo's 95th percentile, on **both** venues — expected: none. The
weight is **not an optimum**: the curve rises with the weight because bitcoin made 57 %/yr on this sample; it is
read as a loss budget — the table marks the weight where the worst relative year falls below the book's own and
where the drawdown is 3 and 5 points deeper — and the operator picks. The held-sleeve proposal of Decision 095
stands or falls with H and W: if EW-liquid or the top-2 beats BTC in both halves, the vehicle changes. Whatever
survives is a bet on an asset class whose survival is known only in hindsight; the sample warning stays.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/cryptobook.py [--venue=CB|BN]
"""
import csv
import datetime as dt
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import books  # noqa: E402
import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402

COST, DRAWS, K_LIQ, MIN_HIST = 0.0025, 20, 30, 200
STABLE = {"USDT", "USDC", "DAI", "PAX", "GUSD", "BUSD", "PYUSD", "EURC", "USDS", "UST", "GYEN", "MUSD", "USD1", "TUSD", "USDP", "FDUSD", "USDD", "FRAX", "LUSD", "SUSD", "EUR", "GBP", "EURT", "RLUSD", "USDE", "XUSD", "AUSD"}
WRAPPED = {"WBTC", "CBBTC", "TBTC", "WETH", "CBETH", "WSTETH", "RETH", "STETH", "LSETH", "PAXG", "XAUT", "BTCB", "WBETH", "BETH", "WNXM"}
EXT = f"{datasets.S}/external"


def load(venue):
    """Calendar-day closes (D × N, NaN outside a coin's span) and dollar volumes; the market = BTC."""
    if venue == "CB":
        meta = {p["id"]: (p["base_currency"], bool(p.get("fx_stablecoin"))) for p in json.load(open(f"{EXT}/coinbase/_products.json"))}
        files = {os.path.basename(f)[:-4]: f for f in glob.glob(f"{EXT}/coinbase/*-USD.csv")}; btc = "BTC-USD"
    else:
        meta = {s["symbol"]: (s["baseAsset"], False) for s in json.load(open(f"{EXT}/binance/_exchangeInfo.json"))["symbols"]}
        files = {os.path.basename(f)[:-4]: f for f in glob.glob(f"{EXT}/binance/*USDT.csv")}; btc = "BTCUSDT"
    series = {}
    for name, path in files.items():
        base, stable = meta.get(name, (name.split("-")[0].replace("USDT", ""), False))
        if stable or base in STABLE or base in WRAPPED or (venue == "BN" and base.endswith(("UP", "DOWN", "BULL", "BEAR"))):
            continue
        rows = list(csv.DictReader(open(path)))
        if len(rows) < 30:
            continue
        series[name] = {r["date"]: (float(r["close"]), float(r.get("usd_volume") or float(r["volume"]) * float(r["close"]))) for r in rows}
    names = sorted(series); d0 = dt.date.fromisoformat(min(min(v) for v in series.values())); D = (dt.date.fromisoformat(max(max(v) for v in series.values())) - d0).days + 1
    C = np.full((D, len(names)), np.nan); V = np.zeros((D, len(names)))
    for j, n in enumerate(names):
        s = series[n]; days = sorted(s); k0 = (dt.date.fromisoformat(days[0]) - d0).days; k1 = (dt.date.fromisoformat(days[-1]) - d0).days; last = np.nan
        for k in range(k0, k1 + 1):
            v = s.get((d0 + dt.timedelta(days=k)).isoformat()); last = v[0] if v else last; C[k, j] = last; V[k, j] = v[1] if v else 0.0
    return dict(venue=venue, d0=d0, C=C, V=V, names=names, btc=names.index(btc), base=[meta.get(n, (n, False))[0] for n in names])


def cal_index(u, dates, lag=0):
    return np.array([(dt.date.fromisoformat(d) - u["d0"]).days - lag for d in dates])


def eligible(u, day):
    """The liquid set as of calendar day ``day`` (data through that day): history, not a stable, top-K by 90-day median dollar volume."""
    C, V = u["C"], u["V"]
    if day - 365 < 0:
        return np.zeros(C.shape[1], bool)
    ok = ~np.isnan(C[day]) & ~np.isnan(C[day - MIN_HIST])
    lr = np.diff(np.log(C[day - 365:day + 1]), axis=0); vol = np.nanstd(lr, axis=0) * np.sqrt(365)
    ok &= ~(vol < 0.15)
    liq = np.median(V[day - 90:day + 1], axis=0); liq[~ok] = -1
    top = np.argsort(-liq, kind="stable")[:K_LIQ]; out = np.zeros(C.shape[1], bool); out[top[liq[top] > 0]] = True
    return out


def month_ends(dates):
    return [t for t in range(len(dates) - 1) if dates[t][:7] != dates[t + 1][:7]]


def sleeve_run(u, dates, picker):
    """Hold the picks between month-end rebalances (drift), re-set at each; ``picker(day, elig)`` → columns to hold equally
    (empty → cash). Returns the sleeve's session returns and the turnover per year."""
    Cs = u["C"][cal_index(u, dates)]; lag = cal_index(u, dates, 1); rebs = set(month_ends(dates)); S, N = Cs.shape
    value = np.zeros(N); cash = 1.0; curve = np.empty(S); curve[0] = 1.0; turn = 0.0
    for t in range(1, S):
        r = Cs[t] / Cs[t - 1]; ok = (value > 0) & np.isfinite(r); value[ok] *= r[ok]
        ended = (value > 0) & np.isnan(Cs[t]); cash += value[ended].sum(); value[ended] = 0.0
        if t in rebs:
            elig = eligible(u, lag[t]); picks = np.asarray(picker(lag[t], elig), dtype=int); total = value.sum() + cash
            target = np.zeros(N)
            if len(picks):
                target[picks] = total / len(picks)
            tr = np.abs(target - value).sum() + (cash if len(picks) else 0.0) * 0; turn += tr / total
            total -= COST * tr; value = target * (total / max(target.sum(), 1e-12)) if len(picks) else np.zeros(N); cash = 0.0 if len(picks) else total
        curve[t] = value.sum() + cash
    return curve[1:] / curve[:-1] - 1, turn / (S / 252)


def score_rank(u, day, elig, k_months, n, mirror=False):
    C = u["C"]; s = C[day - 5] / C[day - 5 - 30 * k_months] - 1; s = np.where(elig & np.isfinite(s), s, np.nan)
    order = np.argsort((s if mirror else -s), kind="stable"); order = order[np.isfinite(s[order])]
    return order[:n]


def timed(r, sig):
    """A held series switched by a lagged 0/1 signal, 0.25 % on each switch."""
    x = np.concatenate([[0.0], sig[:-1].astype(float)]); return x * r - COST * np.abs(np.diff(np.concatenate([[0.0], x]))), x


def trend_family(level):
    """Eight time-series rules on a session-level series (True = long), read at the same session (the caller lags)."""
    out = {}; n = len(level); cs = np.concatenate([[0.0], np.cumsum(level)])
    for m in (50, 100, 200, 300):
        sma = np.full(n, np.nan); sma[m - 1:] = (cs[m:] - cs[:-m]) / m; out[f"sma{m}"] = level > sma
    for k in (1, 3, 6, 12):
        w = 21 * k; mom = np.full(n, np.nan); mom[w + 5:] = level[5:-w] / level[:-w - 5] - 1 if w + 5 < n else np.nan; out[f"mom{k}"] = mom > 0
    return out


def stats(r):
    c = np.concatenate([[1.0], np.cumprod(1 + r)]); m = fastbt.metrics(c, []); return m["cagr"], m["max_drawdown"]


def halves(r, dates, split):
    k = next(i for i, d in enumerate(dates[1:]) if d >= split); return stats(r[:k])[0], stats(r[k:])[0]


def family_edge(r, dates, split):
    """The family median of (CAGR edge over holding, drawdown cut) and the per-half median edges, on a return series."""
    level = np.concatenate([[1.0], np.cumprod(1 + r)]); fam = trend_family(level); hc, hd = stats(r); hh = halves(r, dates, split)
    es, ds, h1, h2 = [], [], [], []
    for sig in fam.values():
        rr, _ = timed(r, sig[1:]); c, d = stats(rr); a, b = halves(rr, dates, split)
        es.append(c - hc); ds.append(d - hd); h1.append(a - hh[0]); h2.append(b - hh[1])
    return float(np.median(es)), float(np.median(ds)), float(np.median(h1)), float(np.median(h2))


def shuffle_months(r, dates, rng):
    groups = {}
    for i, d in enumerate(dates[1:]):
        groups.setdefault(d[:7], []).append(i)
    keys = list(groups); return r[np.concatenate([groups[keys[i]] for i in rng.permutation(len(keys))])]


def band_mix(rb, rs, w, band=0.25):
    """The book with a crypto slice re-set to ``w`` only when it drifts outside ±band of it; 0.25 % on the trade."""
    b, s = 1 - w, w; out = np.empty(len(rb))
    for t in range(len(rb)):
        b *= 1 + rb[t]; s *= 1 + rs[t]; tot = b + s
        if not (w * (1 - band) <= s / tot <= w * (1 + band)):
            tr = abs(s - w * tot); tot -= COST * tr; s = w * tot; b = tot - s
        out[t] = tot
    return np.concatenate([[1.0], out])[1:] / np.concatenate([[1.0], out])[:-1] - 1


def main():
    venues = [a.split("=")[1] for a in sys.argv if a.startswith("--venue=")] or ["CB", "BN"]
    dec = books.decade(); d = dec["d"]; r = dec["r"]; bear = dec["bear"]; shock = books.shock_flags(dec["spy"], -0.07, 10, 20)
    master.shock_scale_holder[0] = 0.5; expo = books.exposure(bear, shock); split = books.DECADE_SPLIT
    rb = master.book(0.4, r["sec"], r["SPMO"], r["mkt"], bear, 0.5, shock, None, False, None)
    sc = lambda rr, dd=d, luck=0: master.score(rr, r["mkt"][len(d) - len(dd):], dd, split, luck_draws=luck)  # noqa: E731
    base = sc(rb); print(f"=== the book {d[0]} → {d[-1]}: excess {base['excess']:+.2%} (IS {base['is']:+.2%} / OOS {base['oos']:+.2%}), DD {base['dd']:.1%}, worst year {base['worst_year']:+.1%}")
    rng = np.random.default_rng(96); curves = {}
    for venue in venues:
        u = load(venue); lag = cal_index(u, d, 1); rebs = month_ends(d)
        breadth = {d[t][:4]: int(eligible(u, lag[t]).sum()) for t in rebs}
        first = next((t for t in rebs if eligible(u, lag[t]).sum() >= 5), None)
        if first is None:
            print(f"\n=== {venue}: no month with 5 eligible coins — skipped"); continue
        dd = d[first:]; rbv = rb[first:]; basev = sc(rbv, dd)
        print(f"\n=== {venue}: {len(u['names'])} coins after exclusions, window {dd[0]} → {dd[-1]} (first month with ≥ 5 liquid coins); liquid set at the first rebalance of each year: "
              + " ".join(f"{y[2:]}:{n}" for y, n in sorted(breadth.items())))
        hold = {}
        def col(j):
            return lambda day, elig: [j] if not np.isnan(u["C"][day, j]) else []
        eth = next((j for j, b in enumerate(u["base"]) if b == "ETH"), None)
        hold["BTC"] = sleeve_run(u, d, col(u["btc"]))[0]
        hold["ETH"] = sleeve_run(u, d, col(eth))[0]
        hold["EW-liquid"] = sleeve_run(u, d, lambda day, elig: np.nonzero(elig)[0])[0]
        hold["top-2 by volume"] = sleeve_run(u, d, lambda day, elig: np.argsort(-np.where(elig, np.median(u["V"][day - 90:day + 1], axis=0), -1))[:2] if elig.sum() >= 2 else np.nonzero(elig)[0])[0]
        print(f"\n  {'H — held sleeves':30} {'CAGR':>7} {'IS':>7} {'OOS':>7} {'DD':>6} | book +5 %: excess (IS / OOS) DD worst | vs book")
        for k, rs in hold.items():
            rs = rs[first:]; c, mdd = stats(rs); a, b = halves(rs, dd, split); s = sc(0.95 * rbv + 0.05 * rs, dd)
            print(f"  {k:30} {c:+7.1%} {a:+7.1%} {b:+7.1%} {mdd:6.0%} | {s['excess']:+6.2%} ({s['is']:+.2%} / {s['oos']:+.2%}) {s['dd']:6.1%} {s['worst_year']:+6.1%} | {s['excess'] - basev['excess']:+.2%}")
        curves[venue] = {k: v[first:] for k, v in hold.items()}
        # T — the trend family on BTC, ETH, EW-liquid: the family median vs holding, and the shuffled-months placebo
        print(f"\n  {'T — trend family (median of 8)':30} {'edge':>7} {'IS':>7} {'OOS':>7} {'DDcut':>6} | placebo edge 5 / 50 / 95 | placebo DD cut 5 / 50 / 95 | verdict")
        for k in ("BTC", "ETH", "EW-liquid"):
            rs = hold[k][first:]; e, dc, h1, h2 = family_edge(rs, dd, split); pe, pd = [], []
            for _ in range(DRAWS):
                fe, fd, _, _ = family_edge(shuffle_months(rs, dd, rng), dd, split); pe.append(fe); pd.append(fd)
            pe, pd = np.array(pe), np.array(pd)
            print(f"  {k:30} {e:+7.1%} {h1:+7.1%} {h2:+7.1%} {dc:+6.0%} | {np.percentile(pe, 5):+.1%} / {np.median(pe):+.1%} / {np.percentile(pe, 95):+.1%} | {np.percentile(pd, 5):+.0%} / {np.median(pd):+.0%} / {np.percentile(pd, 95):+.0%} | "
                  + ("edge " + ("OUTSIDE" if e > np.percentile(pe, 95) else "inside") + ", DD cut " + ("OUTSIDE" if dc > np.percentile(pd, 95) else "inside")))
        # X — the cross-section vs EW-liquid, with random picks of the same count
        ew = hold["EW-liquid"][first:]; ewc = stats(ew)[0]; ewh = halves(ew, dd, split)
        print(f"\n  {'X — top-N by past k months':30} {'CAGR':>7} {'vs EW':>7} {'IS':>7} {'OOS':>7} {'DD':>6} {'turn':>5} | random picks vs EW 5 / 50 / 95 (IS, OOS) | verdict")
        best = None
        for k_m in (1, 3, 6):
            for n in (3, 5, 10):
                rs = sleeve_run(u, d, lambda day, elig, k_m=k_m, n=n: score_rank(u, day, elig, k_m, n))
                tr = rs[1]; rs = rs[0][first:]; c, mdd = stats(rs); a, b = halves(rs, dd, split)
                pl = []
                for _ in range(DRAWS):
                    pr = sleeve_run(u, d, lambda day, elig, n=n: rng.choice(np.nonzero(elig)[0], size=min(n, int(elig.sum())), replace=False) if elig.sum() else [])[0][first:]
                    pa, pb = halves(pr, dd, split); pl.append((stats(pr)[0] - ewc, pa - ewh[0], pb - ewh[1]))
                pl = np.array(pl); both = (a - ewh[0] > np.percentile(pl[:, 1], 95)) and (b - ewh[1] > np.percentile(pl[:, 2], 95)) and a > ewh[0] and b > ewh[1]
                print(f"  {f'top-{n} by {k_m}m':30} {c:+7.1%} {c - ewc:+7.1%} {a - ewh[0]:+7.1%} {b - ewh[1]:+7.1%} {mdd:6.0%} {tr:5.1f} | {np.percentile(pl[:, 0], 5):+.0%} / {np.median(pl[:, 0]):+.0%} / {np.percentile(pl[:, 0], 95):+.0%} "
                      f"(IS {np.percentile(pl[:, 1], 95):+.0%}, OOS {np.percentile(pl[:, 2], 95):+.0%}) | {'SURVIVES both halves' if both else 'inside / fails a half'}")
                if both and (best is None or c > best[1]):
                    best = (f"top-{n} by {k_m}m", c, rs)
        rs = sleeve_run(u, d, lambda day, elig: score_rank(u, day, elig, 3, 5, mirror=True))[0][first:]; c = stats(rs)[0]; a, b = halves(rs, dd, split)
        print(f"  {'mirror: bottom-5 by 3m':30} {c:+7.1%} {c - ewc:+7.1%} {a - ewh[0]:+7.1%} {b - ewh[1]:+7.1%}")
        if best:
            curves[venue][best[0]] = best[2]
        # D — the dip rule on the liquid coins (fastbt), vs EW-liquid
        Cs = u["C"][cal_index(u, d)]; liq_any = np.zeros(len(u["names"]), bool)
        for t in rebs:
            liq_any |= eligible(u, lag[t])
        cols = np.nonzero(liq_any)[0]
        mkt = fastbt.Market({dd_: float(Cs[t, u["btc"]]) for t, dd_ in enumerate(d) if np.isfinite(Cs[t, u["btc"]])},
                            {u["names"][j]: {dd_: float(Cs[t, j]) for t, dd_ in enumerate(d) if np.isfinite(Cs[t, j])} for j in cols}, {})
        elig_m = np.zeros((len(mkt.dates), len(mkt.name_list)), bool); cur = np.zeros(len(u["names"]), bool)
        for t, dd_ in enumerate(d):
            if t in rebs:
                cur = eligible(u, lag[t])
            i = mkt.idx.get(dd_)
            if i is not None:
                elig_m[i] = cur[cols]
        res = fastbt.run(mkt, {**books.LIVE, "cost_per_side": COST, "eligible": elig_m}, dd[0], None, want_trades=True)
        cv = res["_curve"]; rdip = cv[1:] / cv[:-1] - 1; i0 = mkt.dates.index(res["start"]); ddd = mkt.dates[i0:i0 + len(cv)]
        c, mdd = stats(rdip); a, b = halves(rdip, ddd, split); ewa, ewb = halves(ew[len(dd) - len(ddd):], ddd, split) if len(ddd) <= len(dd) else ewh
        print(f"\n  D — the dip rule on the liquid coins ({len(cols)} ever liquid): CAGR {c:+.1%} (IS {a:+.1%} / OOS {b:+.1%}), DD {mdd:.0%}, {len(res['trades'])} trades | vs EW-liquid {c - stats(ew[len(dd) - len(ddd):])[0]:+.1%} (IS {a - ewa:+.1%} / OOS {b - ewb:+.1%})")
        # V — volatility-scaled BTC vs a constant exposure of the same average
        rs = hold["BTC"][first:]; vol = np.array([np.std(rs[max(0, t - 30):t]) * np.sqrt(252) if t >= 10 else np.nan for t in range(len(rs))])
        e = np.clip(0.5 / vol, 0, 1); e = np.nan_to_num(e, nan=1.0); x = np.concatenate([[1.0], e[:-1]]); rv = x * rs - COST * np.abs(np.diff(np.concatenate([[0.0], x])))
        rc = x.mean() * rs; sv, scst = sc(0.95 * rbv + 0.05 * rv, dd), sc(0.95 * rbv + 0.05 * rc, dd)
        print(f"  V — BTC vol-scaled (target 50 %, mean exposure {x.mean():.0%}): CAGR {stats(rv)[0]:+.1%}, DD {stats(rv)[1]:.0%} vs constant {x.mean():.0%}: CAGR {stats(rc)[0]:+.1%}, DD {stats(rc)[1]:.0%} | book +5 %: {sv['excess'] - basev['excess']:+.2%} vs {scst['excess'] - basev['excess']:+.2%}")
        # E — inside the book's switches
        for k in ("BTC", "EW-liquid"):
            rs = hold[k][first:]; ex = expo[first:]; xi = np.concatenate([[1.0], ex[:-1]]); ri = xi * rs - COST * np.abs(np.diff(np.concatenate([[0.0], xi])))
            print(f"  E — {k} inside the switches at 5 %: {sc(0.95 * rbv + 0.05 * ri, dd)['excess'] - basev['excess']:+.2%} vs outside {sc(0.95 * rbv + 0.05 * rs, dd)['excess'] - basev['excess']:+.2%}")
        # W — the weight curve, blend and live-like
        print(f"\n  W — the weight curve ({venue}, window {dd[0]} →): per weight the blend's excess (IS / OOS) and the live-like excess, drawdown, worst relative year; budget lines: worst year below the book's {basev['worst_year']:+.1%}, drawdown 3 / 5 points deeper than {basev['dd']:.1%}")
        for k, rs in curves[venue].items():
            print(f"  {k}:")
            for w in np.arange(0.025, 0.2501, 0.025):
                sb = sc((1 - w) * rbv + w * rs, dd); luck = 400 if k == "BTC" and round(w, 3) in (0.05, 0.10, 0.20) else 0; sl = sc(band_mix(rbv, rs, w), dd, luck)
                flags = ("" if sl["worst_year"] >= basev["worst_year"] else " worst<book") + (" DD+3" if sl["dd"] < basev["dd"] - 0.03 else "") + (" DD+5" if sl["dd"] < basev["dd"] - 0.05 else "")
                print(f"    {w:5.1%}  blend {sb['excess']:+6.2%} ({sb['is']:+.2%} / {sb['oos']:+.2%}) | live-like {sl['excess']:+6.2%} ({sl['is']:+.2%} / {sl['oos']:+.2%}) DD {sl['dd']:6.1%} worst {sl['worst_year']:+6.1%}{flags}"
                      + (f" | {master.luck_line(sl)}" if "t" in sl else ""))


if __name__ == "__main__":
    main()
