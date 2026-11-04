"""A small crypto momentum sleeve beside the book (roadmap C3; Decision 095 research, 2026-11-04; free Coinbase candles).

The question (handover §8 idea 2): would a few percent of the book in bitcoin, held or timed by its own trend, have
added to the two-sleeve book — and is the answer anything but one bubble-shaped sample? Data: `fetch_crypto.py` →
`external/coinbase/{BTC,ETH,LTC}-USD.csv`, UTC daily closes from Coinbase Exchange (BTC 2015-07, ETH 2016-05, LTC
2016-08 — the three coins the exchange listed before the window opened, the only hindsight-free basket; the coins
that died never listed there, so the survivorship of the asset class itself is *not* priced here and cannot be).
The book: `books.decade()` — the live blend min(insurance ×0.5, shock ×0.5) × (0.4 dip sleeve + 0.6 SPMO) on
2017-01-03 → 2026-11, split 2022-01-01, the series every Decision 067 → 091 number came from (constant daily weights,
free rebalancing). The sleeve takes its weight w ∈ {2, 5, 10 %} pro rata from both sleeves: book' = (1 − w) × book +
w × sleeve. The sleeve's return on a session is the coin's UTC-day close on the session date against the previous
session's (the crypto day closes 3–4 h after the NYSE close; weekends land on Monday). Rules, on the coin's own
calendar-day series, read at the close of the day before the session (one day late, like the book's switches):
**held** (always long), **sma200** (close above its 200-calendar-day average), **mom12** (the close 30 days ago above
the close 365 days ago — 12-1 momentum). **Outside** the exposure rules = the sleeve ignores the book's switches;
**inside** = scaled by the same min(insurance, shock) factor. Costs: **0.25 % per side** (Alpaca's crypto taker fee at
the lowest tier) on every change of the sleeve's weight; the daily rebalancing of the constant weight is free, as for
the rest of the blend. A coin joins the basket once its rule has history (ETH's sma200 2016-12, LTC's 2017-03).
Pre-registered hypotheses (the expected numbers were written before the first run):
  C1  **held**: BTC at 5 % adds **+2 … +3 pp/yr** to the book's excess over SPY (BTC ≈ +55 %/yr over the window;
      ≈ +1 at 2 %, ≈ +4.5 at 10 %), the max drawdown **2 … 4 points deeper** (2022: BTC −65 % while the book fell),
      the worst relative year up to 3 points worse (2018 or 2022); the first half (2017's ×14 and 2020–21) carries
      ≥ 2/3 of it, the second half (2022 →, BTC ≈ +11 %/yr) under +0.5. The sleeve's own excess has t < 2.
  C2  **timing**: sma200 / mom12 on BTC keep **60 … 110 %** of the held sleeve's return and cut its own max drawdown
      from ≈ 80 % to ≈ 50 % (2018 and 2022 were slow bears); against the placebo — twenty draws of BTC's history with
      its calendar months shuffled, the rule re-applied — the **drawdown cut lies above the 95th percentile** (the
      trend structure is real in this sample) while the **return edge over holding sits inside the band** (placebo-
      level return, as the roadmap row expects). Inside vs outside the exposure rules: within ±0.5 pp/yr (BTC's bears
      and SPY's overlapped in 2022 only).
  C3  **the basket** (BTC / ETH / LTC equal weight): within ±1 pp/yr of BTC alone at 5 % with a deeper drawdown (2018:
      ETH −94 %, LTC −95 %); the three survived, so the basket flatters — the dead coins are not in the data.
  C4  **the sample**: the contribution is a few years' — with its best calendar year removed, the held sleeve's
      excess over the book falls by more than half; the luck meter on the book with the sleeve: P(excess > 0) up
      from the book's own, t still under 1.
Drop rule: the sleeve becomes a *proposal* (never a change) only if, at 2 % or 5 %, (a) the book's excess rises in
both halves, (b) the worst relative year is no more than 2 points worse and the max drawdown no more than 3 points
deeper, (c) a timed sleeve's drawdown cut beats its placebo's 95th percentile and its return edge is not below the
5th, and (d) with its best calendar year removed the sleeve still adds in both halves. Expected: the held sleeve at
2 % passes (a) and (b) narrowly and fails (d) on the second half; at 5 % it fails (b); the timed sleeves cut the
drawdown but not the return. Whatever clears is a *priced bet on an asset class whose survival is known only in
hindsight*, reported to the operator as such with the roadmap row's health warning; nothing live changes.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/crypto.py
"""
import csv
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import books  # noqa: E402
import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402

W = (0.02, 0.05, 0.10)
COST = 0.0025
DRAWS = 20
COINS = ("BTC-USD", "ETH-USD", "LTC-USD")


def calendar(product):
    """Dense calendar-day closes from the first candle (a missing day carries the previous close)."""
    c = {r["date"]: float(r["close"]) for r in csv.DictReader(open(f"{datasets.S}/external/coinbase/{product}.csv"))}
    d0 = dt.date.fromisoformat(min(c)); n = (dt.date.fromisoformat(max(c)) - d0).days + 1; out = np.empty(n); last = np.nan
    for k in range(n):
        last = c.get((d0 + dt.timedelta(days=k)).isoformat(), last); out[k] = last
    return d0, out


def rules(px):
    """Long / flat on the calendar series; NaN (no history) counts as flat."""
    cs = np.concatenate([[0.0], np.cumsum(px)]); sma = np.full(len(px), np.nan); sma[199:] = (cs[200:] - cs[:-200]) / 200
    mom = np.full(len(px), np.nan); mom[365:] = px[335:-30] / px[:-365] - 1
    return {"held": np.ones(len(px), bool), "sma200": px > sma, "mom12": mom > 0}


def on_sessions(d0, arr, dates, lag=0):
    idx = np.array([(dt.date.fromisoformat(d) - d0).days - lag for d in dates]); out = np.full(len(dates), np.nan)
    ok = (idx >= 0) & (idx < len(arr)); out[ok] = arr[idx[ok]]; return out


def sleeve(d0, px, sig, dates, expo=None):
    """The sleeve's daily return on the book's return days: the coin's return × the rule read the day before, costs on switches."""
    p = on_sessions(d0, px, dates); r = p[1:] / p[:-1] - 1
    x = np.nan_to_num(on_sessions(d0, sig.astype(float), dates, lag=1)[1:])
    if expo is not None:
        x = x * expo
    r = np.nan_to_num(r); turn = np.abs(np.diff(np.concatenate([[0.0], x])))
    return x * r - COST * turn, x


def stats(r):
    c = np.concatenate([[1.0], np.cumprod(1 + r)]); m = fastbt.metrics(c, [])
    return m["cagr"], m["max_drawdown"], r.std() * np.sqrt(252)


def fmt(label, s, base, extra=""):
    return (f"  {label:34} {s['excess']:+7.2%} {s['is']:+7.2%} {s['oos']:+7.2%} | {s['dd']:6.1%} {s['sharpe']:5.2f} {s['worst_year']:+6.1%} {s['roll3_pos']:4.0%} | "
            f"{s['excess'] - base['excess']:+.2%}" + extra + (f" | {master.luck_line(s)}" if "t" in s else ""))


def main():
    dec = books.decade(); d = dec["d"]; r = dec["r"]; bear = dec["bear"]; shock = books.shock_flags(dec["spy"], -0.07, 10, 20)
    master.shock_scale_holder[0] = 0.5; expo = books.exposure(bear, shock)
    rb = master.book(0.4, r["sec"], r["SPMO"], r["mkt"], bear, 0.5, shock, None, False, None)
    sc = lambda rr, luck=0: master.score(rr, r["mkt"], d, books.DECADE_SPLIT, luck_draws=luck)  # noqa: E731
    base = sc(rb, 400); years = sorted({x[:4] for x in d})
    print(f"=== the book on the decade {d[0]} → {d[-1]}, split {books.DECADE_SPLIT}; the sleeve pro rata, costs {COST:.2%}/side on switches")
    coins = {c: calendar(c) for c in COINS}
    for c, (d0, px) in coins.items():
        p = on_sessions(d0, px, d); rr = np.nan_to_num(p[1:] / p[:-1] - 1); cagr, dd, vol = stats(rr)
        yr = " ".join(f"{y[2:]}:{np.prod(1 + rr[[k for k, x in enumerate(d[1:]) if x[:4] == y]]) - 1:+.0%}" for y in years)
        print(f"  {c} held: CAGR {cagr:+.1%}, vol {vol:.0%}, max DD {dd:.0%} | by year {yr}")
    print(f"\n  {'book':34} {'excess':>7} {'IS':>7} {'OOS':>7} | {'DD':>6} {'Sh':>5} {'worst':>6} {'rl3':>4} | vs book")
    print(fmt("no sleeve", base, base))
    d0, px = coins["BTC-USD"]; sig = rules(px); own = {}
    for rule in ("held", "sma200", "mom12"):
        for side, ex in (("outside", None), ("inside", expo)):
            rs, x = sleeve(d0, px, sig[rule], d, ex); cagr, dd, vol = stats(rs); sw = int(np.sum(np.diff(np.concatenate([[0.0], x])) != 0))
            own[(rule, side)] = (cagr, dd, sw, x.mean())
            for w in W:
                rr = (1 - w) * rb + w * rs; s = sc(rr, 400 if (w == 0.05 and side == "outside") else 0)
                print(fmt(f"BTC {rule} {side} {w:.0%}", s, base))
    print("\n  the BTC sleeve alone (on the book's sessions): " + "; ".join(f"{k[0]} {k[1]} CAGR {v[0]:+.1%}, DD {v[1]:.0%}, {v[2]} switches, in {v[3]:.0%}" for k, v in own.items()))
    # C3 — the basket of the three coins Coinbase listed before the window; a coin joins once its rule has history
    for rule, need in (("held", 0), ("sma200", 200)):
        parts = np.array([sleeve(d0_, px_, rules(px_)[rule], d)[0] for d0_, px_ in coins.values()])
        has = np.array([np.nan_to_num(on_sessions(d0_, np.arange(len(px_), dtype=float), d, lag=1)[1:], nan=-1) >= need for d0_, px_ in coins.values()])
        basket = (parts * has).sum(axis=0) / has.sum(axis=0)
        print(fmt(f"basket {rule} outside 5%", sc(0.95 * rb + 0.05 * basket), base))
    eth = coins["ETH-USD"]; print(fmt("ETH held outside 5%", sc(0.95 * rb + 0.05 * sleeve(eth[0], eth[1], rules(eth[1])["held"], d)[0]), base))
    # C2 — the placebo: BTC's history with its calendar months shuffled, the rules re-applied; the edge over holding
    rng = np.random.default_rng(95); rc = px[1:] / px[:-1] - 1; days = [d0 + dt.timedelta(days=k) for k in range(1, len(px))]
    months = {}
    for k, day in enumerate(days):
        months.setdefault(day.strftime("%Y-%m"), []).append(k)
    keys = list(months); real = {rule: stats(sleeve(d0, px, sig[rule], d)[0]) for rule in ("held", "sma200", "mom12")}
    edges = {rule: [] for rule in ("sma200", "mom12")}
    for _ in range(DRAWS):
        order = rng.permutation(len(keys)); idx = np.concatenate([months[keys[i]] for i in order]); fake = px[0] * np.concatenate([[1.0], np.cumprod(1 + rc[idx])])
        fs = rules(fake); held = stats(sleeve(d0, fake, fs["held"], d)[0])
        for rule in edges:
            cagr, dd, _ = stats(sleeve(d0, fake, fs[rule], d)[0]); edges[rule].append((cagr - held[0], dd - held[1]))
    for rule, e in edges.items():
        e = np.array(e); rc_edge = real[rule][0] - real["held"][0]; dd_edge = real[rule][1] - real["held"][1]
        print(f"  placebo {rule} vs held (BTC's months shuffled, {DRAWS} draws): return edge 5 % {np.percentile(e[:, 0], 5):+.1%} / median {np.median(e[:, 0]):+.1%} / 95 % {np.percentile(e[:, 0], 95):+.1%} — real {rc_edge:+.1%} → {'inside' if np.percentile(e[:, 0], 5) <= rc_edge <= np.percentile(e[:, 0], 95) else 'OUTSIDE'}; "
              f"drawdown cut 5 % {np.percentile(e[:, 1], 5):+.0%} / median {np.median(e[:, 1]):+.0%} / 95 % {np.percentile(e[:, 1], 95):+.0%} — real {dd_edge:+.0%} → {'above the 95th' if dd_edge > np.percentile(e[:, 1], 95) else 'inside'}")
    # C4 — the best calendar year removed: the held sleeve's contribution with that year's sleeve return zeroed
    rs, _ = sleeve(d0, px, sig["held"], d); contrib = {y: np.sum(rs[[k for k, x in enumerate(d[1:]) if x[:4] == y]]) for y in years}
    best = max(contrib, key=contrib.get); rs2 = rs.copy(); rs2[[k for k, x in enumerate(d[1:]) if x[:4] == best]] = 0.0
    for w in (0.02, 0.05):
        full = sc((1 - w) * rb + w * rs); cut = sc((1 - w) * rb + w * rs2)
        print(f"  C4 held {w:.0%}: adds {full['excess'] - base['excess']:+.2%} (IS {full['is'] - base['is']:+.2%} / OOS {full['oos'] - base['oos']:+.2%}); without {best}: {cut['excess'] - base['excess']:+.2%} (IS {cut['is'] - base['is']:+.2%} / OOS {cut['oos'] - base['oos']:+.2%})")


if __name__ == "__main__":
    main()
