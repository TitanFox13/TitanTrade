"""Credit and financial stress as the insurance's second signal (roadmap B5; Decision 077 research, 2026-10-30).

The two-signal insurance halves exposure while SPY is below its 200-day SMA *and* fewer than half of the 11 sector
ETFs are above theirs; on the century the engine has the SMA alone (no breadth exists there). Member breadth as the
second signal failed in Decision 068's addendum: a block-shuffled breadth beat both real measures on the decade,
because the decade rewards any loosening of the insurance — "the era is talking". This test asks whether a signal
from a *different population* — the credit and funding markets, which do not look at stock prices — is a better
second condition: the Chicago Fed's National Financial Conditions Index (NFCI, weekly, 1971 →, zero = average
conditions, positive = tighter), its adjusted twin (ANFCI), the St. Louis Fed stress index (STLFSI4, weekly, 1993 →),
and the VIX (daily, 1990 →) as the unrevised cross-check. All from the Decision 072 library.

Two caveats written first. **Revisions**: NFCI, ANFCI and STLFSI4 are re-estimated and their whole history is revised
at each release, so the current vintage knows the future's normalisation — a mild look-ahead the VIX does not have;
the test lags every weekly value by one week (publication) and reads the VIX result as the point-in-time version.
**The era**: the decade wants less insurance; a rule that fires less looks smart there whatever it is, so the decade
is judged only against its placebo, and the 1971 → window (the century book restricted to the NFCI's history, where the
incumbent is the SMA alone) carries the verdict.

Design, fixed before the first run: the book = min(insurance ×0.5, shock ×0.5) × (0.4 dip + 0.6 momentum), de-risked
capital at 0; insurance variants, each with its placebo (the stress indicator block-shuffled in 63-session blocks, 20
draws — the same firing frequency, no information):
  - the incumbent: SMA200 AND sector breadth < 50 % (decade); SMA200 alone (1971 → and the century);
  - SMA200 AND stress > x — NFCI x ∈ {0, +0.5, +1}, STLFSI4 x ∈ {0, +1, +2} (1993 →), VIX x ∈ {20, 25, 30};
  - SMA200 AND breadth < 50 % AND stress > x (decade, a third condition);
  - stress > x alone (no SMA) — the stress as the first signal;
  - the live book plus stress > x as a third rule in the min() (the decade and 1971 →).
Windows: the decade 2017-01-03 → 2026-10-12 (split 2022); **1971-01 → 2026-08** (split 1998-07, eras 1971–2000 /
2000–26); the episodes 1973–74, 1980–82, 1987, 1990, 2000–02, 2008, 2011, 2020, 2022 — the fall and the rebound year.

Pre-registered hypotheses (the expected numbers were written before the first run):
  C1  stress and the SMA agree on the deep bears and disagree on the shallow ones: with NFCI > 0 the de-risked share
      of sessions over 1971 → falls from the SMA's ≈ 27 % to 10 … 15 %, keeping 1973–74, 2008 and 2020 and dropping
      most of the 1990s and 2010s false alarms; 1987 is missed by both (stress rose after the crash).
  C2  on the 1971 → window the stress-gated insurance (SMA AND NFCI > 0 or > 0.5) beats the SMA-only book by +0.3 …
      +1.0 pp/yr with a drawdown no more than 3 points deeper, positive in both halves — *and* it is inside its
      placebo's spread, because fewer firings pay on that window too (prior ≈ 30 % that it beats the placebo's 90th
      percentile).
  C3  on the decade every stress variant reads ≥ the live book (+1.36) and inside its placebo, as member breadth did.
  C4  stress alone (no SMA) is worse than the SMA alone on both windows (it fires late: 1987, 2020-02).
  C5  stress as a third rule in the min() costs 0.3 … 0.8 pp/yr on the decade for ≤ 2 points of drawdown — the
      volatility-target family.
  C6  the VIX version agrees with the NFCI version in sign on every line (so the revisions are not what is driving
      it); STLFSI4 agrees where it exists.

Drop rules, written first:
  - a Decision (stress as the second signal, or the third rule) only if the variant beats the incumbent in both
    halves of the 1971 → window with a drawdown no more than 3 points deeper *and* beats its placebo's 90th
    percentile there *and* the VIX twin agrees in sign *and* the decade reads no worse than its placebo's median;
  - otherwise recorded: the insurance keeps its two signals; credit stress joins member breadth in Track D.

Addendum, pre-registered after the first run and before the second (2026-10-30). The first run met the bar on the
letter (SMA AND NFCI > 0.5 on 1971 →: +3.50 vs +2.62, both halves, DD −37.4 vs −35.6, all 20 placebo draws beaten)
and failed it in spirit: the VIX twin agreed by +0.1 with a 7-point-deeper drawdown and no placebo beaten, and the
ALFRED archive shows the NFCI was revised by a quarter of a point in March 2020 (the real-time reading at 2020-04-03
was +0.07, the current one +0.31). Two checks, written before they run, decide B5:
  S1  the real-time NFCI: the initial-release values (the FRED API's first vintage of each observation, read on the
      day they were released) replace the current vintage over the window the archive covers; expected: the real-time
      rule fires on different weeks and reads *worse* than the current-vintage rule on the same window — the gap is
      the size of the revision flattery; the tracked window holds only 2020 and 2022, so it cannot carry a verdict.
  S2  the unrevised twin over the century: Moody's corporate spreads (never revised) — BAA − AAA monthly from 1919,
      read one month late, as SMA AND spread > x, x ∈ {1.2, 1.5, 2.0} pp, on the century book 1927 → (split 1975,
      the four quarter-centuries) and on the same 1971 → window as the NFCI; the daily DBAA − DAAA > {1.0, 1.3, 1.6}
      and BAA10Y > {3.0, 3.5, 4.0} on 1986 → (split 2006-07); each middle threshold against its block-shuffled placebo.
      Expected (prior 40 %): the spread gate reproduces the NFCI's shape — a third of the firings, 1931–32, 1974, 2008
      kept, the shallow bears skipped — at +0.3 … +0.8 over the SMA alone on 1971 → and +0.2 … +0.6 over the century,
      at the edge of its placebo; if it does not, the NFCI's gain was the revisions.
  S3  the drawdown leg per era: the gated rule's worst drawdown in each quarter-century no more than 3 points deeper
      than the SMA-only's; 1929–32 is the test the NFCI cannot take (expected: kept — spreads were extreme).
Drop rule for the whole of B5: a Decision only if the *unrevised* spread gate passes the first run's bar on 1971 →
(both halves, drawdown within 3 points, the placebo's 90th percentile beaten) *and* is ahead of the SMA alone in all
four century eras *and* the real-time NFCI does not contradict it where it exists; the rule proposed would then be
the spread (free, daily, unrevised), not the NFCI. Otherwise B5 is recorded as a candidate that failed its
robustness check, and the insurance keeps its two signals.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/stress.py [--spread]
"""
import bisect
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402
from breadth2 import block_shuffle  # noqa: E402
from putwrite import cut, ep  # noqa: E402

THRESH = {"NFCI": (0.0, 0.5, 1.0), "ANFCI": (0.0, 0.5, 1.0), "STLFSI4": (0.0, 1.0, 2.0), "VIXCLS": (20.0, 25.0, 30.0)}
MID = {"NFCI": 0.5, "ANFCI": 0.5, "STLFSI4": 1.0, "VIXCLS": 25.0}
LAG_DAYS = 7
EPS_LONG = [("1973-74", "1973-01-11", "1974-10-03"), ("1980-82", "1980-11-28", "1982-08-12"), ("1987", "1987-08-25", "1987-12-04"), ("1990", "1990-07-16", "1990-10-11"), ("2000-02", "2000-03-24", "2002-10-09"),
            ("2008", "2007-10-09", "2009-03-09"), ("2011", "2011-04-29", "2011-10-03"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12")]
EPS_DEC = [("2018Q4", "2018-09-20", "2018-12-24"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12"), ("2025", "2025-02-19", "2025-04-08")]


def fred(name):
    out = {}
    for line in open(f"{datasets.S}/external/fred/{name}.csv").read().splitlines()[1:]:
        d, v = line.split(",")[:2]
        try: out[d] = float(v)
        except ValueError: pass
    return out


def known(series, dd, lag_days=LAG_DAYS):
    """The value known at each session's close: the latest observation dated at least ``lag_days`` earlier, on dd[1:] with
    the previous-close convention (the decision for the day's return uses yesterday's reading)."""
    ds = sorted(series); out = np.full(len(dd), np.nan)
    for i, d in enumerate(dd):
        c = (datetime.date.fromisoformat(d) - datetime.timedelta(days=lag_days)).isoformat(); k = bisect.bisect_right(ds, c) - 1
        if k >= 0: out[i] = series[ds[k]]
    return master.prev(out)[1:]


def main():
    rng = np.random.default_rng(77)
    raw = {k: fred(k) for k in THRESH}
    dec, cen = carry.sets()

    def report(title, dd, r, lvl, incumbent, spy_below, inds, split, eras, eps, breadth_below=None, decade=False):
        shock = master.shock_flags(lvl, -0.07, 10, 20); core = 0.4 * r["dip"] + 0.6 * r["mom"]; m = r["mkt"]
        book = lambda bear: carry.exposure(bear, shock) * core  # noqa: E731
        sc = lambda rr: master.score(rr, m, dd, split, eras)  # noqa: E731
        s_inc = sc(book(incumbent)); out = {"incumbent": s_inc}
        def line(label, rr, bear, pl=None):
            s = sc(rr); e = " ".join(f"{ep(rr, m, dd, a, b):+5.0%}/{ep(rr, m, dd, a, b, rebound=True):+4.0%}" for _, a, b in eps)
            print(f"{label:44} {s['excess']:+7.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['dd']:6.1%} {s['sharpe']:5.2f} | {np.mean(bear):5.1%} | {e}" + (f" | placebo {np.median(pl):+5.2%} [{np.percentile(pl, 10):+5.2%}…{np.percentile(pl, 90):+5.2%}], beaten {np.mean(s['excess'] > pl):3.0%}" if pl is not None else ""))
            return s
        print(f"\n=== {title}: {dd[0]} → {dd[-1]}; columns: excess vs the market, IS, OOS | DD, Sharpe | de-risked share | episodes (book − market, fall / rebound year)" + ("" if eras is None else f"; eras {', '.join(a[:4] + '–' + b[:4] for a, b in eras)}"))
        print(f"{'insurance rule':44} {'excess':>7} {'IS':>6} {'OOS':>6} | {'DD':>6} {'Sh':>5} | {'on':>5} | " + " ".join(f"{x[0]:>10}" for x in eps))
        line("incumbent (live two-signal)" if decade else "incumbent (SMA200 alone)", book(incumbent), incumbent)
        if decade:
            line("SMA200 alone (reference)", book(spy_below), spy_below)
        if eras:
            print(f"{'':44} eras of the incumbent: " + " ".join(f"{x:+6.1%}" for x in s_inc["eras"]))
        for name, ind in inds.items():
            x_mid = MID[name]; v = ind
            for x in THRESH[name]:
                bear = spy_below & (np.nan_to_num(v, nan=-np.inf) > x); pl = None
                if x == x_mid:
                    pl = np.array([sc(book(spy_below & (np.nan_to_num(block_shuffle(v, rng), nan=-np.inf) > x)))["excess"] for _ in range(20)])
                s = line(f"SMA200 AND {name} > {x:g}", book(bear), bear, pl); out[(name, x)] = (s, pl)
                if eras and x == x_mid:
                    print(f"{'':44} eras: " + " ".join(f"{e:+6.1%}" for e in s["eras"]))
            bear = np.nan_to_num(v, nan=-np.inf) > x_mid
            out[(name, "alone")] = line(f"{name} > {x_mid:g} alone (no SMA)", book(bear), bear)
            e3 = np.minimum(carry.exposure(incumbent, shock), np.where(bear, 0.5, 1.0)); rr = e3 * core
            out[(name, "third")] = line(f"incumbent + {name} > {x_mid:g} as a third rule", rr, e3 < 1)
            if decade and breadth_below is not None:
                bear = spy_below & breadth_below & (np.nan_to_num(v, nan=-np.inf) > x_mid)
                out[(name, "third-cond")] = line(f"SMA AND breadth AND {name} > {x_mid:g}", book(bear), bear)
        return out

    # ---------------- the decade ----------------
    _, dd, spy, r, bear_live, split, _ = dec
    cur = datasets.load("A_alpaca_names_2016"); i0 = cur.dates.index(dd[0]); n = len(dd); _, _, spy_above, breadth = cur.pre(90, 150, 200)
    spy_below = master.prev(spy_above[i0:i0 + n][1:]) == 0.0; br_below = master.prev(breadth[i0:i0 + n][1:]) < 0.5
    inds_dec = {k: known(raw[k], dd) for k in ("NFCI", "STLFSI4", "VIXCLS")}
    R_dec = report("the decade", dd, r, spy, bear_live, spy_below, inds_dec, split, None, EPS_DEC, breadth_below=br_below, decade=True)

    # ---------------- 1971 → (NFCI, ANFCI), 1994 → (STLFSI4), 1990 → (VIX) on the century book ----------------
    _, fd, mk, rc, bear_c, _, _ = cen; shock_c = master.shock_flags(mk, -0.07, 10, 20)
    R_long = {}
    for name, a, split_w, eras in (("NFCI", "1971-02-01", "1998-07-01", [("1971-02-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]), ("ANFCI", "1971-02-01", "1998-07-01", [("1971-02-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]),
                                   ("VIXCLS", "1990-02-01", "2008-05-01", None), ("STLFSI4", "1994-02-01", "2010-04-01", None)):
        d, rs = cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "bear": bear_c, "shock": shock_c}, a, "2026-08-31")
        lvl = np.concatenate([[1.0], np.cumprod(1 + rs["mkt"])])   # the shock flags are recomputed on the window's level below; identical in spirit
        eps = [e for e in EPS_LONG if e[1] >= a]
        R_long[name] = report(f"{name} on the century book from {a[:4]}", d, {"dip": rs["dip"], "mom": rs["mom"], "mkt": rs["mkt"]}, lvl, rs["bear"], rs["bear"], {name: known(raw[name], d)}, split_w, eras, eps)

    # ---------------- the pre-registered verdict ----------------
    print("\n=== pre-registered verdict")
    inc = R_long["NFCI"]["incumbent"]; print(f"  1971 → incumbent (SMA alone): {inc['excess']:+.2%} ({inc['is']:+.1%} / {inc['oos']:+.1%}), DD {inc['dd']:.1%}")
    verdict = False
    for x in THRESH["NFCI"]:
        s, pl = R_long["NFCI"][("NFCI", x)]; ok = s["is"] > inc["is"] and s["oos"] > inc["oos"] and s["dd"] >= inc["dd"] - 0.03
        okp = pl is not None and s["excess"] > np.percentile(pl, 90)
        vix = R_long["VIXCLS"][("VIXCLS", 25.0)][0]; vinc = R_long["VIXCLS"]["incumbent"]; agree = (vix["excess"] - vinc["excess"]) * (s["excess"] - inc["excess"]) > 0
        dec_s, dec_pl = R_dec[("NFCI", x)]; dec_ok = dec_pl is None or dec_s["excess"] >= np.median(dec_pl)
        print(f"  SMA AND NFCI > {x:g}: {s['excess']:+.2%} ({s['is']:+.1%} / {s['oos']:+.1%}), DD {s['dd']:.1%} → both halves and DD {'ok' if ok else 'no'}; placebo p90 {'beaten' if okp else ('not beaten' if pl is not None else 'n/a')}; VIX twin {'agrees' if agree else 'disagrees'}; decade vs its placebo median {'ok' if dec_ok else 'no'}")
        verdict |= ok and okp and agree and dec_ok
    t = R_long["NFCI"][("NFCI", "third")]; print(f"  incumbent + NFCI > 0.5 as a third rule, 1971 →: {t['excess']:+.2%} ({t['is']:+.1%} / {t['oos']:+.1%}), DD {t['dd']:.1%} vs the incumbent's {inc['excess']:+.2%} / {inc['dd']:.1%}")
    print(f"  → {'DECISION PROPOSED' if verdict else 'NO — the insurance keeps its two signals; credit stress joins member breadth in Track D'}")


EPS_CENT = [("1929-32", "1929-09-03", "1932-06-01"), ("1937-38", "1937-03-10", "1938-03-31"), ("1973-74", "1973-01-11", "1974-10-03"), ("1987", "1987-08-25", "1987-12-04"), ("2000-02", "2000-03-24", "2002-10-09"),
            ("2008", "2007-10-09", "2009-03-09"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12")]
ERAS4 = [("1927-07-01", "1950-01-01"), ("1950-01-01", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]


def available(avail_dates, values, dd):
    """The latest value whose availability date ≤ the session, on dd[1:] with the previous-close convention."""
    out = np.full(len(dd), np.nan)
    for i, d in enumerate(dd):
        k = bisect.bisect_right(avail_dates, d) - 1
        if k >= 0: out[i] = values[k]
    return master.prev(out)[1:]


def monthly_known(series, dd):
    """A monthly series dated the first of its month, read one month late: available from the first day of the month after next."""
    rows = []
    for d, v in sorted(series.items()):
        y, m = int(d[:4]), int(d[5:7]); m2 = m + 2; y2 = y + (m2 - 1) // 12; m2 = (m2 - 1) % 12 + 1; rows.append((f"{y2:04d}-{m2:02d}-01", v))
    return available([r[0] for r in rows], [r[1] for r in rows], dd)


def realtime_known(name, dd):
    """The first-release values (FRED API output_type 4), each available from its release date."""
    rows = []
    for line in open(f"{datasets.S}/external/fred/{name}_initial.csv").read().splitlines()[1:]:
        d, rel, v = line.split(",")[:3]
        try: rows.append((rel, float(v)))
        except ValueError: pass
    rows.sort(); return available([r[0] for r in rows], [r[1] for r in rows], dd)


def era_dd(rr, dd, eras):
    c = np.concatenate([[1.0], np.cumprod(1 + rr)]); out = []
    for a, b in eras:
        ia = next(k for k, d in enumerate(dd) if d >= a); ib = max(k for k, d in enumerate(dd) if d <= b); w = c[ia:ib + 1]; out.append(float((w / np.maximum.accumulate(w) - 1).min()))
    return out


def report2(title, dd, r, lvl, incumbent, inds, split, eras, eps, rng, extra=()):
    """inds: {label: (indicator on dd[1:], thresholds, the placebo threshold)}; extra: [(label, indicator array, threshold)] compared as single lines."""
    shock = master.shock_flags(lvl, -0.07, 10, 20); core = 0.4 * r["dip"] + 0.6 * r["mom"]; m = r["mkt"]
    book = lambda bear: carry.exposure(bear, shock) * core  # noqa: E731
    sc = lambda rr: master.score(rr, m, dd, split, eras)  # noqa: E731
    def line(label, rr, bear, pl=None):
        s = sc(rr); e = " ".join(f"{ep(rr, m, dd, a, b):+5.0%}/{ep(rr, m, dd, a, b, rebound=True):+4.0%}" for _, a, b in eps)
        print(f"{label:44} {s['excess']:+7.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['dd']:6.1%} {s['sharpe']:5.2f} | {np.mean(bear):5.1%} | {e}" + (f" | placebo {np.median(pl):+5.2%} [{np.percentile(pl, 10):+5.2%}…{np.percentile(pl, 90):+5.2%}], beaten {np.mean(s['excess'] > pl):3.0%}" if pl is not None else ""))
        if eras: print(f"{'':44} eras: " + " ".join(f"{x:+6.1%}" for x in s["eras"]) + " | era DD: " + " ".join(f"{x:6.1%}" for x in era_dd(rr, dd, eras)))
        return s
    print(f"\n=== {title}: {dd[0]} → {dd[-1]}; columns: excess vs the market, IS, OOS | DD, Sharpe | de-risked share | episodes (book − market, fall / rebound year)")
    print(f"{'insurance rule':44} {'excess':>7} {'IS':>6} {'OOS':>6} | {'DD':>6} {'Sh':>5} | {'on':>5} | " + " ".join(f"{x[0]:>10}" for x in eps))
    out = {"incumbent": line("incumbent (SMA200 alone)", book(incumbent), incumbent)}
    for name, (v, thresholds, mid) in inds.items():
        for x in thresholds:
            bear = incumbent & (np.nan_to_num(v, nan=-np.inf) > x); pl = None
            if x == mid:
                pl = np.array([sc(book(incumbent & (np.nan_to_num(block_shuffle(v, rng), nan=-np.inf) > x)))["excess"] for _ in range(20)])
            out[(name, x)] = (line(f"SMA200 AND {name} > {x:g}", book(bear), bear, pl), pl)
        bear = np.nan_to_num(v, nan=-np.inf) > mid; out[(name, "alone")] = line(f"{name} > {mid:g} alone (no SMA)", book(bear), bear)
    for label, v, x in extra:
        bear = incumbent & (np.nan_to_num(v, nan=-np.inf) > x); out[label] = line(label, book(bear), bear)
    return out


def main_spread():
    rng = np.random.default_rng(78)
    baa, aaa, dbaa, daaa, baa10 = (fred(k) for k in ("BAA", "AAA", "DBAA", "DAAA", "BAA10Y"))
    spread_m = {d: baa[d] - aaa[d] for d in baa if d in aaa}; spread_d = {d: dbaa[d] - daaa[d] for d in dbaa if d in daaa}
    _, fd, mk, rc, bear_c, _, _ = carry.sets()[1]
    # S2 — the century, 1927 → : the monthly spread read one month late
    R = {}
    R["cent"] = report2("S2 — Moody's BAA − AAA (monthly, one month late) on the century book", fd, rc, mk, bear_c, {"BAA−AAA": (monthly_known(spread_m, fd), (1.2, 1.5, 2.0), 1.5)}, "1975-01-01", ERAS4, EPS_CENT, rng)
    # S2 — the 1971 window, for the direct comparison with the NFCI
    d, rs = cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "bear": bear_c}, "1971-02-01", "2026-08-31"); lvl = np.concatenate([[1.0], np.cumprod(1 + rs["mkt"])])
    r71 = {"dip": rs["dip"], "mom": rs["mom"], "mkt": rs["mkt"]}
    R["1971"] = report2("S2 — the same spread on the 1971 → window (the NFCI's window)", d, r71, lvl, rs["bear"], {"BAA−AAA": (monthly_known(spread_m, d), (1.2, 1.5, 2.0), 1.5)}, "1998-07-01", [("1971-02-01", "2000-01-01"), ("2000-01-01", "2026-09-01")], [e for e in EPS_LONG], rng)
    # S2 — the daily spreads 1986 →
    d, rs = cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "bear": bear_c}, "1986-02-01", "2026-08-31"); lvl = np.concatenate([[1.0], np.cumprod(1 + rs["mkt"])])
    r86 = {"dip": rs["dip"], "mom": rs["mom"], "mkt": rs["mkt"]}
    R["1986"] = report2("S2 — the daily spreads (one day late) on the 1986 → window", d, r86, lvl, rs["bear"], {"DBAA−DAAA": (known(spread_d, d, 1), (1.0, 1.3, 1.6), 1.3), "BAA10Y": (known(baa10, d, 1), (3.0, 3.5, 4.0), 3.5)}, "2006-07-01", None, [e for e in EPS_LONG if e[1] >= "1986-02-01"], rng)
    # S1 — the real-time NFCI against the current vintage, 2011-06 →
    d, rs = cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "bear": bear_c}, "2011-06-10", "2026-08-31"); lvl = np.concatenate([[1.0], np.cumprod(1 + rs["mkt"])])
    r11 = {"dip": rs["dip"], "mom": rs["mom"], "mkt": rs["mkt"]}; cur_n = known(fred("NFCI"), d); rt_n = realtime_known("NFCI", d); rt_a = realtime_known("ANFCI", d); cur_a = known(fred("ANFCI"), d)
    for x in (0.0, 0.5):
        c_on = np.nan_to_num(cur_n, nan=-np.inf) > x; r_on = np.nan_to_num(rt_n, nan=-np.inf) > x
        print(f"\nS1 — NFCI > {x:g} on 2011-06 → 2026-08: current vintage on {np.mean(c_on):.1%} of sessions, real time on {np.mean(r_on):.1%}; agree {np.mean(c_on == r_on):.1%}; current-only {np.mean(c_on & ~r_on):.1%}, real-time-only {np.mean(r_on & ~c_on):.1%}; "
              f"max real-time NFCI in 2020: {np.nanmax(rt_n[[k for k, t in enumerate(d[1:]) if t[:4] == '2020']]):+.2f} vs current {np.nanmax(cur_n[[k for k, t in enumerate(d[1:]) if t[:4] == '2020']]):+.2f}")
    R["2011"] = report2("S1 — the real-time NFCI vs the current vintage, 2011-06 → (the only window the archive covers)", d, r11, lvl, rs["bear"], {"NFCI current": (cur_n, (0.0, 0.5), 0.5), "NFCI real-time": (rt_n, (0.0, 0.5), 0.5), "ANFCI real-time": (rt_a, (0.0, 0.5), 0.5), "ANFCI current": (cur_a, (0.0, 0.5), 0.5)},
                       "2019-01-01", None, [e for e in EPS_LONG if e[1] >= "2011-06-10"], rng)
    # ---------------- the verdict for the whole of B5 ----------------
    print("\n=== pre-registered verdict for the whole of B5 (the unrevised spread at its middle threshold)")
    inc71 = R["1971"]["incumbent"]; s71, pl71 = R["1971"][("BAA−AAA", 1.5)]; incc = R["cent"]["incumbent"]; sc_, plc = R["cent"][("BAA−AAA", 1.5)]
    ok_bar = s71["is"] > inc71["is"] and s71["oos"] > inc71["oos"] and s71["dd"] >= inc71["dd"] - 0.03 and s71["excess"] > np.percentile(pl71, 90)
    ok_eras = all(x > y for x, y in zip(sc_["eras"], incc["eras"]))
    dd_i = era_dd(carry.exposure(bear_c, master.shock_flags(mk, -0.07, 10, 20)) * (0.4 * rc["dip"] + 0.6 * rc["mom"]), fd, ERAS4)
    sp = monthly_known(spread_m, fd); bear = bear_c & (np.nan_to_num(sp, nan=-np.inf) > 1.5); dd_g = era_dd(carry.exposure(bear, master.shock_flags(mk, -0.07, 10, 20)) * (0.4 * rc["dip"] + 0.6 * rc["mom"]), fd, ERAS4)
    ok_dd = all(g >= i - 0.03 for g, i in zip(dd_g, dd_i))
    rt = R["2011"][("NFCI real-time", 0.5)][0]; cu = R["2011"][("NFCI current", 0.5)][0]; inc11 = R["2011"]["incumbent"]; contra = (cu["excess"] > inc11["excess"]) and (rt["excess"] < inc11["excess"])
    print(f"  1971 →: spread > 1.5 {s71['excess']:+.2%} ({s71['is']:+.1%} / {s71['oos']:+.1%}), DD {s71['dd']:.1%} vs the SMA alone {inc71['excess']:+.2%} ({inc71['is']:+.1%} / {inc71['oos']:+.1%}), DD {inc71['dd']:.1%}; placebo p90 {np.percentile(pl71, 90):+.2%} → bar {'met' if ok_bar else 'NOT met'}")
    print(f"  century eras, spread vs SMA alone: " + " ".join(f"{x:+.1%}/{y:+.1%}" for x, y in zip(sc_['eras'], incc['eras'])) + f" → {'all four ahead' if ok_eras else 'not all four'}; era DD gated vs SMA: " + " ".join(f"{g:.0%}/{i:.0%}" for g, i in zip(dd_g, dd_i)) + f" → {'within 3 points' if ok_dd else 'deeper than 3 points somewhere'}")
    print(f"  real-time NFCI 2011 →: current-vintage rule {cu['excess']:+.2%}, real-time rule {rt['excess']:+.2%}, SMA alone {inc11['excess']:+.2%} → {'CONTRADICTS' if contra else 'does not contradict'}")
    print(f"  → {'DECISION PROPOSED: the credit-spread gate on the insurance' if ok_bar and ok_eras and ok_dd and not contra else 'NO — B5 recorded as a candidate that failed its robustness check; the insurance keeps its two signals'}")


if __name__ == "__main__":
    main_spread() if "--spread" in sys.argv else main()
