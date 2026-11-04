"""Positioning and sentiment as a regime input (roadmap C2; handover §8 idea 4; Decision 099 research, 2026-11-04).

The question: does "who is crowded" — the speculators' net position in S&P 500 futures, the public's margin debt —
know something about the market's falls that its own price (the live two-signal insurance, the shock trigger) does
not? The Decision 077 shape: a state from a *different population* as a third insurance signal on the book, judged
against the incumbent and against a placebo of the same state block-shuffled.
Data, in the library: **CFTC Commitments of Traders** (legacy futures-only, 1986 →, `external/cftc/deacot*.zip`) —
the non-commercial (speculator) net position in S&P 500 futures as a share of open interest, the big contract
(1986 → 2021) at weight 1, the E-mini (1997 →) at 0.2 and the micro (2019 →) at 0.02 in big-contract equivalents;
weekly as of Tuesday, released Friday → read with a 7-day lag (`stress.known`). **FINRA margin debt** (monthly,
1997-01 → 2026-09, `external/misc/finra_margin_statistics.xlsx`, released in the third week of the following month
→ read two months late, `stress.monthly_known`). NAAIM has no data feed (manual) and AAII is walled — both out.
States, each a rolling real-time percentile rank so the threshold never looks ahead:
  COT crowded long   the net speculative share's rank over the trailing 3 years — the contrarian reading (the crowd
                     is long → danger); COT crowded short = 1 − that rank (the trend reading: speculators net short → danger)
  margin stretched   the 12-month log change of margin debt, its rank over the trailing 5 years (leverage rising fast);
                     margin shrinking = 1 − that rank (deleveraging under way — the "margin calls" leg)
Each at thresholds 0.7 / 0.8 / 0.9 (0.8 = the placebo cell) as (a) a **gate** on the incumbent — de-risk only when the
SMA says bear AND the state is on (fewer firings), (b) an **extra warning** — de-risk when the SMA says bear OR the
state is on (more), (c) alone. The book: the century book (dip on 49 industries 40 / top momentum decile 60) under
min(insurance ×0.5, shock ×0.5), de-risked capital at 0, on **1989-01-03 → 2026-08-31** (three years of COT history
for the first rank; the margin states from 2002), split 2007-11-01, eras 1989–2000 / 2000–2010 / 2010 →; and the
ETF book on the **decade** 2017 → 2026-10 (split 2022). Placebo: the state block-shuffled in 63-session blocks, 20 draws.
Pre-registered hypotheses (the expected numbers were written before the first run):
  R1  the states are on 15 … 25 % of sessions alone; as gates they halve the incumbent's de-risked share and read
      within ±0.5 pp/yr of it, inside their placebo bands; as extra warnings they cost 0.3 … 1.0 pp/yr (more time at
      half exposure in bull years) with the drawdown within ±3 points, inside their bands.
  R2  the readings the literature favours — crowded long and margin stretched — beat neither the incumbent in both
      halves nor their placebo's 90th percentile; margin *shrinking* is the one that can look good (2008–09: margin
      debt fell by half while the market fell) — a coincident reading two months late, expected inside its band;
      the COT ranks are near noise (the speculators' net share swings ±5 % of open interest, no trend to read).
  R3  the decade: every variant within ±0.5 pp/yr of the live book (+1.36) and inside its placebo.
Drop rule, written first (Decision 077's): a state is proposed as a third signal only if its gate or its warning
beats the incumbent in both halves of the 1989 → window with a drawdown no more than 3 points deeper, beats its
placebo's 90th percentile there, and the decade reads no worse than its placebo's median — else closed. Expected:
the placebo everywhere; "who is crowded" is known after the move that made them crowded. Nothing live changes.
Run from TitanTrade/: uv run --with numpy --with openpyxl python -I scripts/param_search/positioning.py
"""
import csv
import glob
import io
import math
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402
from breadth2 import block_shuffle  # noqa: E402
from putwrite import cut, ep  # noqa: E402
from stress import era_dd, known, monthly_known  # noqa: E402

WINDOW = ("1989-01-03", "2026-08-31", "2007-11-01", [("1989-01-03", "2000-01-01"), ("2000-01-01", "2010-01-01"), ("2010-01-01", "2026-09-01")])
EPS = [("2000-02", "2000-03-24", "2002-10-09"), ("2008", "2007-10-09", "2009-03-09"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12")]
WEIGHTS = {"STOCK INDEX FUTURE, S&P 500": 1.0, "S&P 500 STOCK INDEX": 1.0, "E-MINI S&P 500": 0.2, "MICRO E-MINI S&P 500": 0.02}
THRESH = (0.7, 0.8, 0.9); MID = 0.8


def cot_net_share():
    """{Tuesday: speculators' net position / open interest}, S&P 500 futures in big-contract equivalents."""
    weekly = {}
    for f in sorted(glob.glob(f"{datasets.S}/external/cftc/deacot*.zip")):
        z = zipfile.ZipFile(f); rows = list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode("latin-1")))); ci = {c.strip(): i for i, c in enumerate(rows[0])}
        for r in rows[1:]:
            name = r[0].strip().upper()
            if "S&P 500" not in name or any(x in name for x in ("BARRA", "DIVIDEND", "ADJUSTED", "CONSOLIDATED", "TOTL", "VIX")):
                continue
            w = next((v for k, v in WEIGHTS.items() if name.startswith(k)), None)
            if w is None:
                continue
            d = r[ci["As of Date in Form YYYY-MM-DD"]]; acc = weekly.setdefault(d, [0.0, 0.0])
            acc[0] += w * (float(r[ci["Noncommercial Positions-Long (All)"]]) - float(r[ci["Noncommercial Positions-Short (All)"]])); acc[1] += w * float(r[ci["Open Interest (All)"]])
    return {d: v[0] / v[1] for d, v in weekly.items() if v[1] > 0}


def margin_debt():
    import openpyxl
    ws = openpyxl.load_workbook(f"{datasets.S}/external/misc/finra_margin_statistics.xlsx", read_only=True); ws = ws[ws.sheetnames[0]]
    return {r[0] + "-01": float(r[1]) for r in ws.iter_rows(values_only=True) if r and isinstance(r[0], str) and r[0][:4].isdigit() and r[1]}


def rolling_rank(series, window):
    """{date: the value's percentile among the previous ``window`` observations}; the first ``window`` are dropped."""
    ds = sorted(series); v = np.array([series[d] for d in ds]); out = {}
    for i in range(window, len(v)):
        out[ds[i]] = float(np.mean(v[i - window:i] < v[i]))
    return out


def report(title, dd, r, lvl, incumbent, inds, split, eras, eps, rng):
    shock = master.shock_flags(lvl, -0.07, 10, 20); core = 0.4 * r["dip"] + 0.6 * r["mom"]; m = r["mkt"]
    book = lambda bear: carry.exposure(bear, shock) * core  # noqa: E731
    sc = lambda rr: master.score(rr, m, dd, split, eras)  # noqa: E731
    def line(label, bear, pl=None):
        rr = book(bear); s = sc(rr); e = " ".join(f"{ep(rr, m, dd, a, b):+5.0%}/{ep(rr, m, dd, a, b, rebound=True):+4.0%}" for _, a, b in eps)
        print(f"{label:40} {s['excess']:+7.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['dd']:6.1%} {s['sharpe']:5.2f} | {np.mean(bear):5.1%} | {e}"
              + (f" | placebo {np.median(pl):+5.2%} [{np.percentile(pl, 10):+5.2%}…{np.percentile(pl, 90):+5.2%}], beaten {np.mean(s['excess'] > pl):3.0%}" if pl is not None else ""))
        if eras:
            print(f"{'':40} eras: " + " ".join(f"{x:+6.1%}" for x in s["eras"]) + " | era DD: " + " ".join(f"{x:6.1%}" for x in era_dd(rr, dd, eras)))
        return s
    print(f"\n=== {title}: {dd[0]} → {dd[-1]}; excess vs the market, IS / OOS | DD, Sharpe | de-risked share | episodes (book − market, fall / rebound year)")
    print(f"{'insurance rule':40} {'excess':>7} {'IS':>6} {'OOS':>6} | {'DD':>6} {'Sh':>5} | {'on':>5} | " + " ".join(f"{x[0]:>10}" for x in eps))
    out = {"incumbent": line("incumbent (SMA200 alone)", incumbent)}
    for name, v in inds.items():
        vv = np.nan_to_num(v, nan=-np.inf)
        for x in THRESH:
            for mode in ("AND", "OR"):
                bear = (incumbent & (vv > x)) if mode == "AND" else (incumbent | (vv > x)); pl = None
                if x == MID:
                    draws = []
                    for _ in range(20):
                        f = np.nan_to_num(block_shuffle(v, rng), nan=-np.inf) > x; draws.append(sc(book((incumbent & f) if mode == "AND" else (incumbent | f)))["excess"])
                    pl = np.array(draws)
                out[(name, x, mode)] = (line(f"SMA200 {mode} {name} > {x:g}", bear, pl), pl)
        out[(name, "alone")] = (line(f"{name} > {MID:g} alone (no SMA)", vv > MID), None)
    return out


def main():
    rng = np.random.default_rng(99)
    cot = cot_net_share(); mdebt = margin_debt()
    ds = sorted(cot); print(f"COT: {len(ds)} weeks {ds[0]} → {ds[-1]}, net speculative share median {np.median([cot[d] for d in ds]):+.3f}, 5–95 % {np.percentile([cot[d] for d in ds], 5):+.3f} … {np.percentile([cot[d] for d in ds], 95):+.3f}")
    md = sorted(mdebt); chg = {md[i]: math.log(mdebt[md[i]] / mdebt[md[i - 12]]) for i in range(12, len(md))}
    print(f"margin debt: {len(md)} months {md[0]} → {md[-1]}; 12-month change median {np.median(list(chg.values())):+.1%}, 5–95 % {np.percentile(list(chg.values()), 5):+.1%} … {np.percentile(list(chg.values()), 95):+.1%}")
    cot_rank = rolling_rank(cot, 156); m_rank = rolling_rank(chg, 60)
    _, fd, mk, rc, bear_c, _, _ = carry.sets()[1]; dec = carry.sets()[0]
    a, b, split, eras = WINDOW
    d, rs = cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "bear": bear_c}, a, b); lvl = np.concatenate([[1.0], np.cumprod(1 + rs["mkt"])])
    r89 = {"dip": rs["dip"], "mom": rs["mom"], "mkt": rs["mkt"]}
    def inds_on(dd):
        c = known(cot_rank, dd, 7); mm = monthly_known(m_rank, dd)
        return {"COT crowded long": c, "COT crowded short": 1 - c, "margin stretched": mm, "margin shrinking": 1 - mm}
    R = report("R1 / R2 — positioning and leverage as a third insurance signal on the century book, 1989 →", d, r89, lvl, rs["bear"], inds_on(d), split, eras, EPS, rng)
    _, dd2, lvl2, r2, bear2, split2, _ = dec
    D = report("R3 — the same on the decade (the ETF book)", dd2, r2, lvl2, bear2, inds_on(dd2), split2, None, [e for e in EPS if e[1] >= dd2[0]], rng)
    print("\n=== pre-registered verdict (each state at 0.8, as a gate and as a warning)")
    inc = R["incumbent"]; inc_d = D["incumbent"]; any_ok = False
    for name in ("COT crowded long", "COT crowded short", "margin stretched", "margin shrinking"):
        for mode in ("AND", "OR"):
            s, pl = R[(name, MID, mode)]; sd, pld = D[(name, MID, mode)]
            halves = s["is"] > inc["is"] and s["oos"] > inc["oos"]; ddok = s["dd"] >= inc["dd"] - 0.03; p90 = s["excess"] > np.percentile(pl, 90); dec_ok = sd["excess"] >= np.median(pld)
            ok = halves and ddok and p90 and dec_ok; any_ok |= ok
            print(f"  {name} {mode:3}: 1989 → {s['excess']:+.2%} vs {inc['excess']:+.2%} (halves {'ok' if halves else 'no'}, DD {'ok' if ddok else 'no'}, placebo p90 {'beaten' if p90 else 'not beaten'}); decade {sd['excess']:+.2%} vs {inc_d['excess']:+.2%} (placebo median {np.median(pld):+.2%} → {'ok' if dec_ok else 'no'}) → {'PROPOSE' if ok else 'no'}")
    print(f"  → {'a state clears the bar — read it' if any_ok else 'NO state clears the bar → positioning and leverage closed as regime inputs; the insurance keeps its two signals'}")


if __name__ == "__main__":
    main()
