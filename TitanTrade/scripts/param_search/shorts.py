"""Shorts — can the book stop being long-only? (operator question, 2026-10-27)

Pre-registered hypotheses, written before any result was seen:
  H1  WML sleeve. Kenneth French's winners-minus-losers factor (daily 1927 →, long past winners / short past losers,
      self-financed) laid over the recommended book (dip 40 / momentum 60, insurance ×0.5, shock trigger) at 25 / 50 / 100 %
      of equity, and the long-only momentum sleeve replaced by long Hi / short Lo decile with the capital in the market.
      Expectation: higher Sharpe over the century; the momentum crashes (1932–33, 2009) land on top of the book's own
      rebound-year cost; thinner after 2000. On the decade (2017 →, French WML on the ETF book's dates) about neutral.
  H2  Short the market instead of cash while de-risked. The de-risked fraction (1 − e) earns −r_mkt (−1× SPY, or the SH
      ETF's actual returns) instead of 0; tested for the insurance alone, the shock trigger alone and both.
      Expectation: pays in the long bears (1929, 1973, 2008) through the insurance, costs in every rebound (2009, 2020,
      2025) through the shock trigger; negative over the decade, where the slow signal whipsaws.
  H3  Anti-dip mirror. The live rule on inverted prices (1/P): short a name that has rallied ≥ 8 % from its 90-day low
      while below its 150-day SMA, cover at −16.7 % (= +20 % on 1/P) / +13.6 % (= −12 % on 1/P) / 60 sessions; deepest
      (largest rally) first, 3 × 25 %. On the sector ETFs, the point-in-time S&P 500 and the 49 industries, as a
      self-financed overlay on a 100 % market core, beside the long rule built the same way. Expectation: negative on
      every universe (shorts pay the drift; the long rule is ≈ market on hindsight-free universes), least bad when
      entries are restricted to a market below its 200-day SMA.
Costs: 0.05 % per side, 1 %/yr borrow on short notional, de-risked capital otherwise earns 0 (no T-bill).
Decade split 2022-01-01, century split 1975 with four quarter-centuries; the through-2025 number is shown beside the
full period where 2026 could dominate. Run: uv run --with numpy python -I scripts/param_search/shorts.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import books  # noqa: E402
import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402
import screens  # noqa: E402

BORROW = 0.01 / 252
LIVE = master.LIVE
ERAS = [("1927-07-01", "1950-01-01"), ("1950-01-01", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]
EP_C = [("1929", "1929-09-03", "1932-06-01"), ("1932mom", "1932-06-01", "1933-06-01"), ("1973", "1973-01-11", "1974-10-03"),
        ("2008", "2007-10-09", "2009-03-09"), ("2009reb", "2009-03-09", "2010-03-09")]
EP_D = [("covid", "2020-02-19", "2020-03-23"), ("2020reb", "2020-03-23", "2021-03-23"), ("2022", "2022-01-03", "2022-10-12"),
        ("2025", "2025-02-19", "2025-04-08"), ("2023yr", "2023-01-03", "2023-12-29")]


def french_wml():
    cols, rows = datasets._french_section(f"{datasets.S}/french/F-F_Momentum_Factor_daily.csv", ",Mom")
    return {d: rows[d][0] / 100 for d in rows if rows[d][0] is not None}


def episodes(c, m, dates, eps):
    out = []
    for _, a, b in eps:
        ia = next(k for k, x in enumerate(dates) if x >= a); ib = next(k for k, x in enumerate(dates) if x >= b)
        out.append(c[ib] / c[ia] - m[ib] / m[ia])
    return out


def line(label, r, r_mkt, dates, split, eras=None, eps=(), to=None):
    """One result row: excess / IS / OOS, DD, Sharpe, worst year, era-min or roll-3 hit rate, episodes; `to` truncates."""
    if to:
        n = sum(1 for d in dates[1:] if d <= to); r, r_mkt, dates = r[:n], r_mkt[:n], dates[:n + 1]
    s = master.score(r, r_mkt, dates, split, eras)
    c = np.concatenate([[1.0], np.cumprod(1 + r)]); m = np.concatenate([[1.0], np.cumprod(1 + r_mkt)])
    tail = f" eras+ {sum(1 for x in s['eras'] if x > 0)}/4 min {s['era_min']:+5.1%}" if eras else f" roll3 {s['roll3_pos']:3.0%}"
    print(f"{label:58} {s['excess']:+6.1%} ({s['is']:+5.1%}/{s['oos']:+5.1%}) DD {s['dd']:6.1%} Sh {s['sharpe']:4.2f} worst {s['worst_year']:+5.1%}{tail} | "
          + " ".join(f"{x:+6.1%}" for x in episodes(c, m, dates, eps)))
    return s


def century_base():
    c = books.century(); d, mk, mom = c["d"], c["mkt"], c["mom"]
    lo = np.array([mom["Lo PRIOR"].get(x, np.nan) for x in d])
    r = dict(c["r"]); r["lo"] = np.nan_to_num(lo[1:] / lo[:-1] - 1)
    wml = french_wml(); r["wml"] = np.array([wml.get(x, 0.0) for x in d[1:]])
    shock = master.shock_flags(mk, -0.07, 10, 20)
    return d, r, c["bear"], shock


def decade_base():
    b = books.decade(etfs=("SPMO", "SH")); d, spy = b["d"], b["spy"]
    r = {"dip": b["r"]["sec"], "mom": b["r"]["SPMO"], "sh": b["r"]["SH"], "mkt": b["r"]["mkt"]}
    wml = french_wml(); r["wml"] = np.array([wml.get(t, np.nan) for t in d[1:]])
    shock = master.shock_flags(spy, -0.07, 10, 20)
    return d, r, b["bear"], shock


def exposure(bear, shock, ins=0.5, use_ins=True, use_shock=True):
    e = np.ones(len(bear))
    if use_ins:
        e = np.where(bear, ins, e)
    if use_shock:
        e = np.where(shock, np.minimum(e, 0.5), e)
    return e


def h1(label, d, r, bear, shock, split, eras, eps, to):
    print(f"\n=== H1 WML long-short sleeve — {label}: excess vs market (IS / OOS), DD, Sharpe, worst calendar year | episodes = book minus market")
    print(f"{'':58} {'':>6} {'':>13} {'':>9} {'':>7} {'':>11}{'':>22} | " + " ".join(f"{e[0]:>6}" for e in eps))
    e = exposure(bear, shock)
    core = 0.4 * r["dip"] + 0.6 * r["mom"]
    base = e * core
    line("market + WML 50 % (factor alone, borrow 1 %/yr)", r["mkt"] + 0.5 * (r["wml"] - BORROW), r["mkt"], d, split, eras, eps)
    line("market + WML 100 %", r["mkt"] + 1.0 * (r["wml"] - BORROW), r["mkt"], d, split, eras, eps)
    line("book: dip 40 / mom 60, ins x0.5, shock (reference)", base, r["mkt"], d, split, eras, eps)
    for w in (0.25, 0.5, 1.0):
        line(f"book + WML {w:.0%} overlay", base + w * (r["wml"] - BORROW), r["mkt"], d, split, eras, eps)
    line("book + WML 50 %, overlay scaled by the same e", base + e * 0.5 * (r["wml"] - BORROW), r["mkt"], d, split, eras, eps)
    if "lo" in r:
        ls = 0.4 * r["dip"] + 0.6 * (r["mkt"] + r["mom"] - r["lo"] - BORROW)
        line("book, momentum sleeve long Hi / short Lo, capital in market", e * ls, r["mkt"], d, split, eras, eps)
    if to:
        print(f"--- through {to}")
        line("book (reference)", base, r["mkt"], d, split, eras, eps, to)
        line("book + WML 50 % overlay", base + 0.5 * (r["wml"] - BORROW), r["mkt"], d, split, eras, eps, to)


def h2(label, d, r, bear, shock, split, eras, eps, to):
    print(f"\n=== H2 short the market instead of cash while de-risked — {label}")
    print(f"{'':58} {'':>6} {'':>13} {'':>9} {'':>7} {'':>11}{'':>22} | " + " ".join(f"{e[0]:>6}" for e in eps))
    core = 0.4 * r["dip"] + 0.6 * r["mom"]
    shorts = {"-1x market": -r["mkt"] - BORROW}
    if "sh" in r:
        shorts["SH ETF actual"] = r["sh"]
    for trig, ui, us in (("insurance + shock", True, True), ("insurance only", True, False), ("shock only", False, True)):
        e = exposure(bear, shock, 0.5, ui, us)
        line(f"{trig}: de-risked half in cash (reference)", e * core, r["mkt"], d, split, eras, eps)
        for sname, rs in shorts.items():
            line(f"{trig}: de-risked half {sname}", e * core + (1 - e) * rs, r["mkt"], d, split, eras, eps)
        print(f"  (de-risked {np.mean(e < 1):.0%} of sessions)")
    if to:
        print(f"--- through {to}")
        e = exposure(bear, shock)
        line("insurance + shock: cash", e * core, r["mkt"], d, split, eras, eps, to)
        line("insurance + shock: -1x market", e * core + (1 - e) * (-r["mkt"] - BORROW), r["mkt"], d, split, eras, eps, to)


def overlay_curve(mkt_real, names, sectors, params, start, eligible=None):
    """The rule's overlay P&L on a 0 % cash core (flat 'SPY', insurance never fires) + 1 %/yr borrow on the held notional
    when `short`; returns (daily overlay return, trades, dates, n_open per day)."""
    flat = {dd: 1.0 for dd in mkt_real.dates}
    m = fastbt.Market(flat, names, sectors)
    p = dict(params, insurance_breadth=-1.0)
    if eligible is not None:
        p["eligible"] = eligible
    r = fastbt.run(m, p, start, None, want_trades=True)
    c = r["_curve"]; d = m.dates[m.dates.index(r["start"]):]
    n_open = np.zeros(len(c))
    for t in r["trades"]:
        ie = d.index(t["exit_date"]); n_open[max(0, ie - t["days"]):ie] += 1
    return c[1:] / c[:-1] - 1, r["trades"], d, n_open


def true_short(mk, trades, d, slot):
    """Daily P&L of the same trades as real shorts: −slot × ΔP/P_entry per open trade (notional fixed at entry), 1 %/yr borrow."""
    idx = {s: j for j, s in enumerate(mk.name_list)}; off = mk.dates.index(d[0]); P = mk.names
    r = np.zeros(len(d) - 1)
    for t in trades:
        ie = d.index(t["exit_date"]); i0 = ie - t["days"]; j = idx[t["ticker"]]; p0 = P[off + i0, j]
        for k in range(i0 + 1, ie + 1):
            a, b = P[off + k - 1, j], P[off + k, j]
            if np.isnan(a) or np.isnan(b):
                continue
            r[k - 1] -= slot * (b - a) / p0 + slot * BORROW
    return r


def pnl_year(r):
    return float(np.prod(1 + r) ** (252 / len(r)) - 1)


def h3():
    print("\n=== H3 anti-dip mirror — the live rule on 1/P (short the rally inside a downtrend) as a self-financed overlay")
    print("    P&L/yr = the overlay's own return on equity (long: funded from SPY, hurdle = SPY's return on the held fraction; short: hurdle 0 + borrow);")
    print("    'true' = the same trades as real shorts on the real price path; episodes = the overlay's absolute return over the window")
    univ = []
    sec = datasets.load("D_alpaca_sectors_2016"); univ.append(("D sectors 2017→", sec, None, "2017-01-03", "2022-01-01", None))
    e_mkt, member = screens.load_universe(); univ.append(("E S&P 500 point-in-time 2017→", e_mkt, member, "2017-01-03", "2022-01-01", None))
    f_mkt = datasets.load("F_french_49ind_1926"); univ.append(("F 49 industries 1927→", f_mkt, None, "1927-07-01", "1975-01-01", ERAS))
    for label, mk, member_mask, start, split, eras in univ:
        print(f"\n--- {label}")
        names = {n: {dd: v for dd, v in zip(mk.dates, mk.names[:, j]) if not np.isnan(v)} for j, n in enumerate(mk.name_list)}
        inv = {n: {dd: 1.0 / v for dd, v in s.items()} for n, s in names.items()}
        sectors = {n: {dd: v for dd, v in zip(mk.dates, mk.sectors[:, j]) if not np.isnan(v)} for j, n in enumerate(mk.sector_list)}
        spy = mk.spy; T = len(mk.dates)
        below = np.zeros(T, dtype=bool); below[201:] = np.array([spy[i - 1] < spy[i - 201:i - 1].mean() for i in range(201, T)])
        regime = np.repeat(below[:, None], len(mk.name_list), axis=1)
        masks = {"no regime filter": member_mask, "entries only with market < SMA200": (regime if member_mask is None else (regime & member_mask))}
        r_mkt_all = spy[1:] / spy[:-1] - 1
        eps = EP_D if eras is None else EP_C
        print(f"{'overlay':52} {'P&L/yr':>7} {'IS':>6} {'OOS':>6} | {'hurdle':>7} | " + " ".join(f"{e[0]:>7}" for e in eps) + " | trades")
        for side, series in (("long (live rule)", names), ("short (1/P)", inv)):
            for mname, mask in masks.items():
                r_ov, trades, d, n_open = overlay_curve(mk, series, sectors, LIVE, start, mask)
                i0 = mk.dates.index(d[0]); r_mkt = r_mkt_all[i0:i0 + len(r_ov)]
                rets = np.array([t["return"] for t in trades]); kinds = {k: sum(1 for t in trades if t["exit"] == k) for k in ("tp", "stop", "time")}
                ks = next(k for k, x in enumerate(d) if x >= split)
                variants = [(f"{side} {mname}", r_ov - (BORROW * LIVE["slot_pct"] * n_open[1:] if side.startswith("short") else 0.0))]
                if side.startswith("short"):
                    variants.append(("  true short path, same trades", true_short(mk, trades, d, LIVE["slot_pct"])))
                held = LIVE["slot_pct"] * n_open[1:]
                hurdle = pnl_year(held * r_mkt) if side.startswith("long") else 0.0
                for vlabel, rr in variants:
                    c = np.concatenate([[1.0], np.cumprod(1 + rr)])
                    ep = [c[next(k for k, x in enumerate(d) if x >= b)] / c[next(k for k, x in enumerate(d) if x >= a)] - 1 for _, a, b in eps]
                    print(f"{vlabel:52} {pnl_year(rr):+7.1%} {pnl_year(rr[:ks]):+6.1%} {pnl_year(rr[ks:]):+6.1%} | {hurdle:+7.1%} | " + " ".join(f"{x:+7.1%}" for x in ep)
                          + (f" | {len(trades)} ({len(trades) / (len(d) / 252):.1f}/yr) win {np.mean(rets > 0):3.0%} mean {rets.mean():+.1%} median {np.median(rets):+.1%} tp/stop/time {kinds['tp']}/{kinds['stop']}/{kinds['time']}, held {np.mean(n_open > 0):3.0%} of days" if vlabel[0] != " " else ""))


def main():
    d, r, bear, shock = century_base()
    print(f"CENTURY 1927-07 → {d[-1]} (French: dip on 49 industries, top momentum decile, WML factor; insurance = SMA200 only)")
    h1("century", d, r, bear, shock, "1975-01-01", ERAS, EP_C, None)
    h2("century", d, r, bear, shock, "1975-01-01", ERAS, EP_C, None)
    d, r, bear, shock = decade_base()
    ok = ~np.isnan(r["wml"]); last = max(i for i in range(len(ok)) if ok[i]); dw = d[:last + 2]; rw = {k: v[:last + 1] for k, v in r.items()}
    print(f"\nDECADE 2017-01 → {d[-1]} (sector-dip book + SPMO; WML rows end {dw[-1]} where the French file ends)")
    h1("decade (to the French file's end)", dw, rw, bear[:last + 1], shock[:last + 1], "2022-01-01", None, EP_D, "2025-12-31")
    h2("decade", d, r, bear, shock, "2022-01-01", None, EP_D, "2025-12-31")
    h3()


if __name__ == "__main__":
    main()
