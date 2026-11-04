"""Selling volatility as a sleeve (roadmap C3; handover §8 idea 3; Decision 098 research, 2026-11-04; free data).

The question: is the volatility risk premium — being paid to carry the market's fear — a sleeve worth holding beside
the dip and momentum sleeves, or the put-writing result (Decision 074: Sharpe, not return; a second copy of the dip
sleeve's bet) with a worse tail (2018-02-05, when the short-VIX products lost 90 % overnight)? Built the way
`putwrite.py` was: the same books, the same blend, the same crash leg, the same drop rule.
Data: Cboe's **VPD** (VIX Premium Strategy Index: short one-month VIX futures collateralised in bills, 2007-11 →)
and **VPN** (the capped version — a VIX call bought against the short, 2008-06 →), daily levels in the library
(`fetch_external.py --only=cboe`); the investable products on Tiingo (`fetch_keyed.py`): **XIV** 2010-11-30 →
2018-02-21 (terminated after its −93 % day) spliced into **SVXY** from 2018-02-21 (which halved its leverage to −0.5×
that month — the splice is what a holder lived through), and **VXX** (the long side) for the record. The market:
Kenneth French's value-weighted market on the long window (the century engine's), SPY on the decade; the books =
`carry.sets()` (the century book on the long window, the sector-dip / SPMO book on the decade), exposure =
min(insurance ×0.5, shock ×0.5), de-risked capital at 0; the sleeve is scaled like the rest.
Windows: **19y** 2007-11-16 → 2026-08-31 on the century book, split 2017-04-01, eras 2007–11 (the crisis), 2012–18-02
(the calm that ended on 2018-02-05), 2018-03 → ; **ETP** 2010-11-30 → 2026-08-31 (the XIV → SVXY splice), split
2018-09-01; **decade** 2017-01-03 → 2026-10-12 on the ETF book, split 2022-01-01.
Pre-registered hypotheses (the expected numbers were written before the first run):
  V1  the indices alone: VPD within **±2 pp/yr of the market** over 19 years at 0.6 … 1.0× its volatility, a
      drawdown of −30 … −50 % (2008, 2020); VPN 1 … 3 pp/yr below VPD (the cap's cost); **the ETP splice −10 … +10
      %/yr at 2.5 … 3.5× the market's volatility with a −93 % day and a −95 % drawdown** — the product is not the
      index; VXX −40 … −60 %/yr.
  V2  a sleeve beside the book, 10 % and 20 % from the dip sleeve, 10 % from momentum, VPD / VPN / the ETP splice:
      at 10 % the excess within **±0.5 pp/yr** of the book, the Sharpe within ±0.05, the drawdown within ±2 points,
      on both windows and in every era; at 20 % within ±1; VPD's excess over the market correlates **+0.2 … +0.5**
      with the dip sleeve's and −0.1 … +0.2 with momentum's — a second copy of the dip sleeve's bet (flat and choppy
      years pay, crashes cost), not a diversifier; the ETP sleeve at 10 % costs 0.5 … 2 pp/yr and deepens the
      drawdown 3 … 8 points (2018-02). The luck meter on VPD alone and on the book with VPD 10 (19y).
  V3  the crash leg, reported not hypothesised: 2008, 2018-02, 2020-03 and 2022 peak-to-trough and the rebound year
      for the market, the book, the book with VPD 10, VPD, VPN and the ETP splice; expected: VPD −20 … −45 % in 2008
      (the market −55), −5 … −25 % in 2018-02 (the market −10), −20 … −40 % in 2020-03 (−34); the splice −93 % in a
      day in 2018-02 and −70 … −90 % in 2020-03.
Drop rule, written first: a Decision for a volatility-selling sleeve only if the book with it beats the 40 / 60 book
on return in both halves *and* in every era, with a Sharpe no lower, on both windows — else recorded, no sleeve.
Expected: fails everywhere; the door closes with numbers. Nothing live changes.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/volsell.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402
from intl import rets  # noqa: E402
from putwrite import cut, ep, fmt, hdr, score  # noqa: E402

W19 = ("2007-11-16", "2026-08-31", "2017-04-01", [("2007-11-16", "2012-01-01"), ("2012-01-01", "2018-03-01"), ("2018-03-01", "2026-09-01")])
WETP = ("2010-11-30", "2026-08-31", "2018-09-01", None)
CRASHES = [("2008", "2007-10-09", "2009-03-09"), ("2018-02", "2018-01-26", "2018-02-08"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12")]


def splice():
    """XIV's adjusted closes to 2018-02-20, SVXY's from 2018-02-21: the investable short-VIX path, level 1.0 at the start."""
    xiv, svxy = datasets.tiingo("XIV"), datasets.tiingo("SVXY"); out = {}; lvl = 1.0; prev = None
    for d in sorted(xiv):
        if d >= "2018-02-21":
            break
        lvl = lvl * xiv[d] / prev if prev else lvl; prev = xiv[d]; out[d] = lvl
    prev = None
    for d in sorted(svxy):
        if d < "2018-02-21":
            continue
        lvl = lvl * svxy[d] / prev if prev else lvl; prev = svxy[d]; out[d] = lvl
    return out


def worst_day(levels):
    ds = sorted(levels); r = [(levels[ds[i]] / levels[ds[i - 1]] - 1, ds[i]) for i in range(1, len(ds))]; return min(r)


def main():
    dec, cen = carry.sets(); books = {}
    for name, dd, lvl, r, bear, split, eras in (dec, cen):
        e = carry.exposure(bear, master.shock_flags(lvl, -0.07, 10, 20))
        books[name] = dict(dd=dd, e=e, dip=r["dip"], mom=r["mom"], mkt=r["mkt"])
    raw = {"VPD": datasets.cboe("VPD"), "VPN": datasets.cboe("VPN"), "ETP": splice(), "VXX": datasets.tiingo("VXX")}
    for n in ("VPD", "VPN", "ETP", "VXX"):
        w = worst_day(raw[n]); print(f"  {n}: {min(raw[n])} → {max(raw[n])}, worst day {w[0]:+.1%} on {w[1]}")
    series = {bk: {n: rets(raw[n], B["dd"]) for n in raw} for bk, B in books.items()}

    # V1 — the indices and the products alone
    C = books["century"]
    print("\n=== V1 — alone vs the market (French VW market, total return); σ/σm = volatility relative to the market")
    for n, win in (("VPD", W19), ("VPN", ("2008-06-04", "2026-08-31", "2017-07-01", None)), ("ETP", WETP), ("VXX", ("2009-01-30", "2026-08-31", "2017-10-01", None))):
        a, b, split, eras = win; d, rs = cut(C["dd"], {"x": series["century"][n], "mkt": C["mkt"]}, a, b)
        s = score(rs["x"], rs["mkt"], d, split, eras)
        if n == "VPD":
            s.update(master.luck(rs["x"], rs["mkt"], 400))
        print(hdr(eras)) if n in ("VPD", "VPN") else None
        print(fmt(f"{n} {d[0][:7]} → {d[-1][:7]}", s, eras) + (f" | {master.luck_line(s)}" if "t" in s else ""))

    # V2 — the sleeve beside the book
    print("\n=== V2 — a volatility-selling sleeve beside the book (exposure = min(insurance ×0.5, shock ×0.5); the sleeve scaled like the rest)")
    ok = {}
    for wname, bk, win in (("19y", "century", W19), ("ETP", "century", WETP), ("decade", "decade", None)):
        B = books[bk]; a, b, split, eras = win if win else (B["dd"][0], B["dd"][-1], "2022-01-01", None)
        d, rs = cut(B["dd"], {"dip": B["dip"], "mom": B["mom"], "mkt": B["mkt"], "e": B["e"], **{n: series[bk][n] for n in ("VPD", "VPN", "ETP")}}, a, b)
        e, dip, mom, mkt = rs["e"], rs["dip"], rs["mom"], rs["mkt"]
        ks = next(k for k, t in enumerate(d[1:]) if t >= split)
        cx = lambda x, y: tuple(np.corrcoef(x[sl], y[sl])[0, 1] for sl in (slice(None), slice(0, ks), slice(ks, None)))  # noqa: E731
        c1, c2 = cx(rs["VPD"] - mkt, dip - mkt), cx(rs["VPD"] - mkt, mom - mkt)
        print(f"\n--- {wname} window {d[0]} → {d[-1]}; correlation of VPD's excess with the dip sleeve's {c1[0]:+.2f} ({c1[1]:+.2f} / {c1[2]:+.2f}), with momentum's {c2[0]:+.2f} ({c2[1]:+.2f} / {c2[2]:+.2f})")
        print(hdr(eras))
        V = {"dip 40 / mom 60 (the book)": 0.4 * dip + 0.6 * mom,
             "dip 30 / mom 60 / VPD 10 (from the dip sleeve)": 0.3 * dip + 0.6 * mom + 0.1 * rs["VPD"],
             "dip 20 / mom 60 / VPD 20 (from the dip sleeve)": 0.2 * dip + 0.6 * mom + 0.2 * rs["VPD"],
             "dip 40 / mom 50 / VPD 10 (from momentum)": 0.4 * dip + 0.5 * mom + 0.1 * rs["VPD"],
             "dip 30 / mom 60 / VPN 10": 0.3 * dip + 0.6 * mom + 0.1 * rs["VPN"],
             "dip 30 / mom 60 / ETP 10 (the investable product)": 0.3 * dip + 0.6 * mom + 0.1 * rs["ETP"],
             "VPD 100 % under the exposure rules": rs["VPD"]}
        base = None; ok[wname] = {}
        for label, core in V.items():
            s = score(e * core, mkt, d, split, eras)
            if wname == "19y" and label.startswith("dip 30 / mom 60 / VPD 10"):
                s.update(master.luck(e * core, mkt, 400))
            print(fmt(label, s, eras) + (f" | {master.luck_line(s)}" if "t" in s else ""))
            if base is None:
                base = s
            else:
                ok[wname][label] = (s["is"] > base["is"] and s["oos"] > base["oos"] and s["sharpe"] >= base["sharpe"] and (not eras or all(x > y for x, y in zip(s["eras"], base["eras"]))))

    # V3 — the crash leg
    print("\n=== V3 — the crash leg on the 19-year window: peak → trough and the rebound year, book minus market (market absolute)")
    a, b, split, eras = W19; d, rs = cut(C["dd"], {"dip": C["dip"], "mom": C["mom"], "mkt": C["mkt"], "e": C["e"], "VPD": series["century"]["VPD"], "VPN": series["century"]["VPN"], "ETP": series["century"]["ETP"]}, a, b)
    e = rs["e"]
    rows = {"market (absolute)": rs["mkt"], "book (idle in cash)": e * (0.4 * rs["dip"] + 0.6 * rs["mom"]), "book + VPD 10 from the dip sleeve": e * (0.3 * rs["dip"] + 0.6 * rs["mom"] + 0.1 * rs["VPD"]),
            "VPD permanently": rs["VPD"], "VPN permanently (2008-06 →)": rs["VPN"], "the ETP splice (2010-11 →)": rs["ETP"]}
    print(f"{'':44} " + " ".join(f"{c[0]:>14}" for c in CRASHES) + "   (fall / rebound year)")
    for label, rr in rows.items():
        cells = []
        for name, pa, pb in CRASHES:
            first = {"VPN permanently (2008-06 →)": "2008-06-04", "the ETP splice (2010-11 →)": "2010-11-30"}.get(label, "1900-01-01")
            if pa < first:
                cells.append(f"{'n/a':>14}"); continue
            if label.startswith("market") or label.endswith("permanently") or label.startswith("the ETP"):
                m = np.concatenate([[1.0], np.cumprod(1 + rr)]); ia = next(k for k, x in enumerate(d) if x >= pa); ib = next(k for k, x in enumerate(d) if x >= pb); ic = min(ib + 252, len(m) - 1)
                cells.append(f"{m[ib] / m[ia] - 1:+6.0%} / {m[ic] / m[ib] - 1:+5.0%}")
            else:
                cells.append(f"{ep(rr, rs['mkt'], d, pa, pb):+6.0%} / {ep(rr, rs['mkt'], d, pa, pb, rebound=True):+5.0%}")
        print(f"{label:44} " + " ".join(f"{c:>14}" for c in cells))

    print("\n=== pre-registered verdict")
    for w, dct in ok.items():
        print(f"  V2 {w}: " + "; ".join(f"{k.split(' (')[0]}: {'ok' if v else 'no'}" for k, v in dct.items()))
    go = any(v for dct in ok.values() for v in dct.values())
    print(f"  V2 (a sleeve beats the 40 / 60 book on return in both halves and every era, Sharpe no lower, on both windows): {'holds somewhere — read the window' if go else 'FAILS everywhere → no volatility-selling sleeve'}")


if __name__ == "__main__":
    main()
