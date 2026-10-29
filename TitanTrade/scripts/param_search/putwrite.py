"""Put-writing and the collar indices (roadmap B1; Decision 074 research, 2026-10-29).

Brainstorm #32 ("sell a put at the dip level instead of buying") was untestable until Decision 072 fetched Cboe's
option-strategy benchmark indices. They answer two questions the book has never been able to ask: (1) is systematic
option *writing* a sleeve worth holding beside the dip and momentum sleeves — the published claim is that the put-write
index earns about the S&P's return at two thirds of its volatility over decades; (2) is a *collar or protective put*
a better insurance than de-risking to cash — today the book halves exposure on two signals and the idle half earns 0.
Daily index levels: BXMD (buy-write, 30-delta call), BXY (2 % OTM call), CMBO (covered combo), CNDR, BFLY, RXM and
PPUT (long S&P + 5 % OTM put) from 1986-07; BXMC 1990 →; BXM (at-the-money buy-write) 2003 →; **PUT (the cash-secured
put-write) daily only from 2007** (sparse points before); WPUT (weekly) 2006 →; CLL (collar 95 / 110) 2008-09 →. All
are total-return indices on the S&P 500, the put-write collateralised in bills. The market: Kenneth French's
value-weighted US market (total return, the century engine's market) on the long windows, SPY on the decade — the
Cboe indices are on the S&P 500, the French market is broader (≈ 0.3 pp/yr apart over 1986 → 2026); every sleeve and
insurance comparison is book vs book on the same market, so the choice mostly cancels. Loader ``datasets.cboe``.

Windows (each split at its midpoint, the 40-year one also by decade): **40y** 1986-07-01 → 2026-08-31 (the French
market's end), split 2006-07-01, eras 1986–96 / 96–06 / 06–16 / 16–26; **20y** 2007-01-03 → 2026-08-31 (PUT, WPUT,
BXM), split 2017-01-01; **CLL** 2008-09-02 → 2026-08-31, split 2017-07-01; **decade** 2017-01-03 → 2026-10-12 (the
ETF book, split 2022-01-01, every headline also through 2025-12-31). The book = ``carry.sets()``: the century book
(dip on 49 industries 40 / top momentum decile 60, frictionless) on the long windows, the sector-dip / SPMO book on the
decade, exposure = min(insurance ×0.5, shock ×0.5), de-risked capital at 0.

Pre-registered hypotheses (the expected numbers were written before the first run):
  O1  the indices alone vs the market: PUT within ±1 pp/yr of the market at 60–70 % of its volatility and a higher
      Sharpe (both halves of 20y); BXMD / BXY within ±1 at 75–85 % volatility over 40y, BXM (at-the-money) −1 … −2;
      PPUT −2 … −4 pp/yr over 40y with a drawdown about a third smaller (AQR's "pathetic protection"); CLL −2 … −4
      with half the drawdown. CNDR / BFLY / RXM / CMBO / BXMC / WPUT are reported for the record, not hypothesised.
  O2  an option-writing sleeve beside the book (OPT = BXMD on 40y, PUT on 20y and the decade), at 20 % taken from the
      dip sleeve, from the momentum sleeve, or replacing the dip sleeve (0 / 60 / 40): Sharpe +0.00 … +0.05, return
      −0.3 … −1.0 pp/yr on the decade and ≈ 0 ± 0.5 on the long windows, drawdown within ±2 points. The writing
      index's excess over the market correlates +0.2 … +0.4 with the dip sleeve's excess (both are short the market's
      big moves: flat and choppy years pay, strong bulls and crashes cost) and −0.1 … +0.1 with momentum's — so it is
      a second copy of the dip sleeve's bet, not a diversifier.
  O3  a protective put or a collar as the insurance: the idle (1 − e) half held in PPUT (40y) or CLL (CLL window)
      instead of cash; references = cash (the engine), bills (the carry line), and the permanent structure (the whole
      core in PPUT / CLL at all times with no de-risking). Expected: PPUT-as-the-idle-half +0.3 … +1.0 pp/yr vs cash
      over 40y (it stays in the rebounds the cash misses; the put caps the crash leg), ≈ +0 … +0.5 vs bills, with the
      worst drawdown 0 … 3 points deeper; the permanent protective put −2 … −4 pp/yr vs the book with a drawdown a
      third smaller; the collar in between.
  O4  the crash leg, reported not hypothesised: 1987-10, 2000–02, 2008, 2020, 2022 peak-to-trough and the rebound
      year after each, for the book, the book with the option sleeve, and the book with the put-as-insurance.
  O5  every decade number through 2025-12-31 beside the full period.

Drop rules, written first:
  - O2: a Decision for an option-writing sleeve only if the book with it beats the 40 / 60 book on return in both
    halves *and* in every era available, with a Sharpe no lower — else recorded, no sleeve.
  - O3: a Decision for a put / collar insurance only if it beats the *bills* line (not cash) in both halves and every
    era available, with a worst drawdown no more than 2 points deeper than the cash version — else recorded.
  - Either Decision would be a Decision only (expected numbers and the build: Alpaca options approval — cash-secured
    puts are level 1, a long put for the collar is level 2 — on SPY, not SPX; the index assumes monthly rolls at the
    volume-weighted price, a retail fill is worse), never applied without the operator's go.
  - Whatever the outcome, O1 and O4 are knowledge: what forty years of option strategies did against the market.

Costs: the Cboe indices are net of nothing but the option's own bid-ask at the roll (the methodology prices the roll
at the VWAP); the dip run charges 0.05 % a side; blends rebalance daily without cost. De-risked capital earns 0
unless the line says bills or an index.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/putwrite.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402
from intl import rets  # noqa: E402

WINDOWS = {"40y": ("1986-07-01", "2026-08-31", "2006-07-01", [("1986-07-01", "1996-07-01"), ("1996-07-01", "2006-07-01"), ("2006-07-01", "2016-07-01"), ("2016-07-01", "2026-09-01")]),
           "20y": ("2007-01-03", "2026-08-31", "2017-01-01", None), "CLL": ("2008-09-02", "2026-08-31", "2017-07-01", None)}
THROUGH = "2025-12-31"
IDX = ["PUT", "WPUT", "BXM", "BXMD", "BXY", "BXMC", "CMBO", "CNDR", "BFLY", "RXM", "PPUT", "CLL"]
O1_WINDOWS = {"PUT": WINDOWS["20y"], "WPUT": WINDOWS["20y"], "BXM": WINDOWS["20y"], "BXMD": WINDOWS["40y"], "BXY": ("1988-06-01", "2026-08-31", "2007-07-01", None),
              "BXMC": ("1990-01-31", "2026-08-31", "2008-05-01", None), "CMBO": WINDOWS["40y"], "CNDR": WINDOWS["40y"], "BFLY": WINDOWS["40y"], "RXM": WINDOWS["40y"],
              "PPUT": WINDOWS["40y"], "CLL": WINDOWS["CLL"]}
CRASHES = [("1987", "1987-08-25", "1987-12-04"), ("2000-02", "2000-03-24", "2002-10-09"), ("2008", "2007-10-09", "2009-03-09"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12")]


def cut(dates, rs, a, b):
    """Dates a → b and the matching slices of return arrays defined on dates[1:]."""
    i = next(k for k, d in enumerate(dates) if d >= a); j = max(k for k, d in enumerate(dates) if d <= b)
    return dates[i:j + 1], {k: v[i:j] for k, v in rs.items()}


def vol(r):
    return float(np.std(r) * np.sqrt(252))


def score(r, rm, dates, split, eras=None, through=None):
    if through:
        n = max(k for k, t in enumerate(dates) if t <= through); r, rm, dates = r[:n], rm[:n], dates[:n + 1]
    s = master.score(r, rm, dates, split, eras); s["vol_ratio"] = vol(r) / vol(rm); return s


def hdr(eras):
    return f"{'':60} {'excess':>7} {'IS':>6} {'OOS':>6} | {'σ/σm':>5} | {'DD':>6} {'mkt DD':>6} | {'Sh':>5} {'mkt':>5} | {'worst':>6} | " + ("eras" if eras else "roll3")


def fmt(label, s, eras):
    return (f"{label:60} {s['excess']:+7.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['vol_ratio']:5.2f} | {s['dd']:6.1%} {s['mkt_dd']:6.1%} | {s['sharpe']:5.2f} {s['mkt_sharpe']:5.2f} | {s['worst_year']:+6.1%} | "
            + (" ".join(f"{x:+6.1%}" for x in s["eras"]) if eras else f"{s['roll3_pos']:3.0%}"))


def ep(rr, rm, dates, a, b, rebound=False):
    c = np.concatenate([[1.0], np.cumprod(1 + rr)]); m = np.concatenate([[1.0], np.cumprod(1 + rm)])
    ia = next(k for k, x in enumerate(dates) if x >= a); ib = next(k for k, x in enumerate(dates) if x >= b)
    if rebound:
        ia, ib = ib, min(ib + 252, len(c) - 1)
    return c[ib] / c[ia] - m[ib] / m[ia]


def main():
    dec, cen = carry.sets(); rf = carry.rf_daily(); books = {}
    for name, dd, lvl, r, bear, split, eras in (dec, cen):
        e = carry.exposure(bear, master.shock_flags(lvl, -0.07, 10, 20))
        books[name] = dict(dd=dd, e=e, dip=r["dip"], mom=r["mom"], mkt=r["mkt"], core=0.4 * r["dip"] + 0.6 * r["mom"], rf=carry.align_rf(dd, rf), lvl=lvl)
    raw = {n: datasets.cboe(n) for n in IDX}
    cb = {bk: {n: rets(raw[n], B["dd"]) for n in IDX} for bk, B in books.items()}

    # ---------------- O1: the indices alone ----------------
    C = books["century"]
    print("=== O1 — the Cboe option-strategy indices alone vs the market (French VW market, total return); excess CAGR pp/yr, IS / OOS at each window's midpoint; σ/σm = volatility relative to the market")
    print(hdr(True))
    o1 = {}
    for n in IDX:
        a, b, split, eras = O1_WINDOWS[n]
        d, rs = cut(C["dd"], {"x": cb["century"][n], "mkt": C["mkt"]}, a, b)
        s = score(rs["x"], rs["mkt"], d, split, eras); o1[n] = s
        print(fmt(f"{n} {d[0][:7]} → {d[-1][:7]}", s, eras))
    D = books["decade"]
    print("\n--- the same on the decade vs SPY (2017-01-03 → 2026-10-12, split 2022; '→2025' = excess through 2025-12-31)")
    print(hdr(False).replace("| roll3", "| roll3 | →2025"))
    for n in IDX:
        s = score(cb["decade"][n], D["mkt"], D["dd"], "2022-01-01"); t = score(cb["decade"][n], D["mkt"], D["dd"], "2022-01-01", through=THROUGH)
        print(fmt(n, s, None) + f" | {t['excess']:+6.2%}")

    # ---------------- O2: the option-writing sleeve ----------------
    print("\n=== O2 — an option-writing sleeve beside the book (every book × exposure = min(insurance ×0.5, shock ×0.5); the sleeve is scaled like the rest)")
    ok_o2 = {}
    for wname, optname, bk in (("40y", "BXMD", "century"), ("20y", "PUT", "century"), ("decade", "PUT", "decade")):
        B = books[bk]
        a, b, split, eras = WINDOWS[wname] if wname != "decade" else (B["dd"][0], B["dd"][-1], "2022-01-01", None)
        d, rs = cut(B["dd"], {"dip": B["dip"], "mom": B["mom"], "mkt": B["mkt"], "opt": cb[bk][optname], "e": B["e"]}, a, b)
        e, dip, mom, mkt, opt = rs["e"], rs["dip"], rs["mom"], rs["mkt"], rs["opt"]
        ks = next(k for k, t in enumerate(d[1:]) if t >= split)
        cx = lambda x, y: tuple(np.corrcoef(x[sl], y[sl])[0, 1] for sl in (slice(None), slice(0, ks), slice(ks, None)))  # noqa: E731
        c1, c2 = cx(opt - mkt, dip - mkt), cx(opt - mkt, mom - mkt)
        print(f"\n--- {wname} window {d[0]} → {d[-1]} with {optname}; correlation of {optname}'s excess with the dip sleeve's excess {c1[0]:+.2f} ({c1[1]:+.2f} / {c1[2]:+.2f}), with momentum's {c2[0]:+.2f} ({c2[1]:+.2f} / {c2[2]:+.2f}); de-risked {np.mean(e < 1):.0%} of sessions")
        print(hdr(eras) + (" | →2025" if wname == "decade" else ""))
        V = {"dip 40 / mom 60 (the book)": 0.4 * dip + 0.6 * mom, f"dip 20 / mom 60 / {optname} 20 (from the dip sleeve)": 0.2 * dip + 0.6 * mom + 0.2 * opt,
             f"dip 40 / mom 40 / {optname} 20 (from the momentum sleeve)": 0.4 * dip + 0.4 * mom + 0.2 * opt, f"dip 30 / mom 50 / {optname} 20 (from both)": 0.3 * dip + 0.5 * mom + 0.2 * opt,
             f"dip 0 / mom 60 / {optname} 40 (replacing the dip sleeve)": 0.6 * mom + 0.4 * opt, f"dip 40 / mom 0 / {optname} 60 (replacing momentum)": 0.4 * dip + 0.6 * opt,
             f"{optname} 100 % under the exposure rules": opt}
        base = None; ok_o2[wname] = {}
        for label, core in V.items():
            s = score(e * core, mkt, d, split, eras); line = fmt(label, s, eras)
            if wname == "decade": line += f" | {score(e * core, mkt, d, split, eras, through=THROUGH)['excess']:+6.2%}"
            print(line)
            if base is None: base = s
            else:
                ok_o2[wname][label] = (s["is"] > base["is"] and s["oos"] > base["oos"] and s["sharpe"] >= base["sharpe"] and (not eras or all(x > y for x, y in zip(s["eras"], base["eras"]))))

    # ---------------- O3: the put / collar as the insurance ----------------
    print("\n=== O3 — a protective put or a collar as the insurance instead of cash: the idle (1 − e) share held in PPUT / CLL; references: cash (the engine), bills, the market, no insurance, the permanent structure")
    ok_o3 = {}
    for wname, bk, insts in (("40y", "century", ["PPUT"]), ("CLL", "century", ["CLL", "PPUT"]), ("decade", "decade", ["PPUT", "CLL"])):
        B = books[bk]
        a, b, split, eras = WINDOWS[wname] if wname != "decade" else (B["dd"][0], B["dd"][-1], "2022-01-01", None)
        d, rs = cut(B["dd"], {"core": B["core"], "mkt": B["mkt"], "e": B["e"], "rf": B["rf"], **{n: cb[bk][n] for n in insts}}, a, b)
        e, core, mkt, rfd = rs["e"], rs["core"], rs["mkt"], rs["rf"]
        print(f"\n--- {wname} window {d[0]} → {d[-1]}: de-risked {np.mean(e < 1):.0%} of sessions, bills {np.mean(rfd) * 252:.1%}/yr")
        print(hdr(eras) + (" | →2025" if wname == "decade" else ""))
        def line(label, rr):
            s = score(rr, mkt, d, split, eras); out = fmt(label, s, eras)
            if wname == "decade": out += f" | {score(rr, mkt, d, split, eras, through=THROUGH)['excess']:+6.2%}"
            print(out); return s
        print("  on the market alone (the insurance mechanisms compared without the sleeves):")
        line("market, no insurance", mkt); line("market × exposure rules, idle in cash", e * mkt); line("market × exposure rules, idle in bills", e * mkt + (1 - e) * rfd)
        for n in insts:
            line(f"market × exposure rules, idle in {n}", e * mkt + (1 - e) * rs[n]); line(f"{n} permanently (no de-risking)", rs[n])
        print("  on the book:")
        s_cash = line("book, idle in cash (the engine)", e * core); s_bill = line("book, idle in bills (the carry line)", e * core + (1 - e) * rfd)
        line("book, idle in the market", e * core + (1 - e) * mkt); line("book, no insurance", core)
        ok_o3[wname] = {}
        for n in insts:
            s = line(f"book, idle in {n}", e * core + (1 - e) * rs[n])
            ok_o3[wname][n] = (s["is"] > s_bill["is"] and s["oos"] > s_bill["oos"] and s["dd"] >= s_cash["dd"] - 0.02 and (not eras or all(x > y for x, y in zip(s["eras"], s_bill["eras"]))))

    # ---------------- O4: the crash leg ----------------
    print("\n=== O4 — the crash leg on the 40-year window: book minus market, peak → trough, and the rebound year after the trough (market = absolute)")
    a, b, split, eras = WINDOWS["40y"]
    d, rs = cut(C["dd"], {"core": C["core"], "mkt": C["mkt"], "e": C["e"], "dip": C["dip"], "mom": C["mom"], "BXMD": cb["century"]["BXMD"], "PPUT": cb["century"]["PPUT"], "CLL": cb["century"]["CLL"]}, a, b)
    e = rs["e"]
    rows = {"market (absolute)": rs["mkt"], "book (idle in cash)": e * rs["core"], "book + BXMD 20 from the dip sleeve": e * (0.2 * rs["dip"] + 0.6 * rs["mom"] + 0.2 * rs["BXMD"]),
            "book, idle in PPUT": e * rs["core"] + (1 - e) * rs["PPUT"], "PPUT permanently": rs["PPUT"], "CLL permanently (2008-09 →)": rs["CLL"], "BXMD permanently": rs["BXMD"]}
    print(f"{'':44} " + " ".join(f"{c[0]:>14}" for c in CRASHES) + "   (fall / rebound year)")
    for label, rr in rows.items():
        cells = []
        for name, pa, pb in CRASHES:
            if label.startswith("CLL") and pa < "2008-09-02": cells.append(f"{'n/a':>14}"); continue
            if label.startswith("market"):
                m = np.concatenate([[1.0], np.cumprod(1 + rr)]); ia = next(k for k, x in enumerate(d) if x >= pa); ib = next(k for k, x in enumerate(d) if x >= pb); ic = min(ib + 252, len(m) - 1)
                cells.append(f"{m[ib] / m[ia] - 1:+6.0%} / {m[ic] / m[ib] - 1:+5.0%}")
            else:
                cells.append(f"{ep(rr, rs['mkt'], d, pa, pb):+6.0%} / {ep(rr, rs['mkt'], d, pa, pb, rebound=True):+5.0%}")
        print(f"{label:44} " + " ".join(f"{c:>14}" for c in cells))

    # ---------------- the pre-registered verdict ----------------
    print("\n=== pre-registered verdict")
    for w, dct in ok_o2.items():
        print(f"  O2 {w}: " + "; ".join(f"{k.split(' (')[0]}: {'ok' if v else 'no'}" for k, v in dct.items()))
    for w, dct in ok_o3.items():
        print(f"  O3 {w}: " + "; ".join(f"idle in {k}: {'ok' if v else 'no'}" for k, v in dct.items()))
    go2 = any(v for dct in ok_o2.values() for v in dct.values()); go3 = any(v for dct in ok_o3.values() for v in dct.values())
    print(f"  O2 (a sleeve beats the 40 / 60 book on return in both halves and every era, Sharpe no lower): {'holds somewhere — read the window' if go2 else 'FAILS everywhere → no option-writing sleeve'}")
    print(f"  O3 (a put / collar insurance beats the bills line in both halves and every era, DD within 2 points of cash): {'holds somewhere — read the window' if go3 else 'FAILS everywhere → no put / collar insurance'}")


if __name__ == "__main__":
    main()
