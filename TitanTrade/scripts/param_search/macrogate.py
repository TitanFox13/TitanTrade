"""The macro gate valued on history (roadmap A6's other half; Decision 094 research, 2026-11-04; free data only).

The live gate (`risk_manager.check_macro_blackout`): no new entry within MACRO_BLACKOUT_HOURS = 6 of a scheduled
high-impact macro event; the calendar is `data/fomc_dates.json` (decision days at 14:00 ET) plus the FRED release
calendar at 08:30 ET. As coded it matches only "fomc" and "nonfarm payrolls" against the native provider's names
(the keyword list was written for FMP's names, Decision 046) and neither scheduled run (10:15 / 15:30 ET) falls within
six hours *before* an 08:30 release — so live it fires on the morning run of a decision day and nothing else. The
docs (features.md, risk_management.md) describe a wider gate: FOMC / NFP / CPI / core PCE / GDP. This test prices
both readings on 27 years with the dip rule and its slots unchanged (insurance off inside, as in the grids):
universe G (the 11 sector ETFs, the live universe) and H (the 15 names), 1999-11 → 2026-11 on Tiingo.

Data (key-free, fetched by `fetch_external.py --only=fed,bls` into `external/fed/` and `external/bls/`): the Fed's
FOMC calendar pages (one per year 1999 → 2020, the current page 2021 →) and the BLS "Schedule of Selected Releases"
pages (one per year 2000 →; the Employment Situation and the CPI with their dates). Pre-registered before any
result was looked at — which events count: **scheduled FOMC meetings only** (the decision day = the last day of the
meeting; conference calls, unscheduled meetings, cancelled meetings and notation votes are out — the live file is a
calendar known in advance), **the Employment Situation**, **the CPI**. Sets: "coded" = FOMC + Employment Situation
(what the keyword list matches), "documented" = coded + CPI (what the docs say), "fomc" = FOMC alone (what fires
live). Shapes, in fill terms (fastbt signals at the close of S and fills at the close of S + 1, so a blocked fill on
session F masks the signal on F − 1): "spec" = no fill on the event session E or the session before it (the
handover's definition), "before" = no fill on E − 1 only (the entry that would sit through the release; the daily
analogue of "within six hours before"). E is the first session on or after the event date (a release on Good Friday
counts on the Monday, its "session before" is the Thursday). Primary = spec × coded. The mask is a T × N eligibility
matrix into `fastbt`, all names at once.
Pre-registered hypotheses (the expected numbers were written before the first run):
  M1  the primary gate moves the excess vs SPY by **≤ 0.2 pp/yr either way** on both universes over 27 years, and by
      ≤ 0.4 in each half and each era (noisier windows); "documented" ≤ 0.3; "before × coded" ≤ 0.2; "before × fomc"
      (the live footprint) ≤ 0.1. The primary gate blocks ~15 % of fill sessions (20 events × 2 sessions of ~252),
      "documented" ~24 %; 10–20 % of the entries move, most by one session (the dip persists), few are lost.
  M2  the entries the primary gate would have blocked (the no-gate run, fill on a blocked session) are **no worse**
      than the rest: median return within ±2 points, stop rate within ±10 points (nothing at entry predicts a trade,
      Decision 066; the earnings gate found the same, 093); the gate's effect sits inside the 5–95 % band of a
      placebo — twenty draws of random blackout sessions, the same count per year and the same two-session shape.
  M3  the live book is universe G: M1 on G is the live number; the gate as coded touches ~8 mornings a year, the
      "before × fomc" cell bounds it. The docs / code mismatch is a finding for the operator, not fixed here.
Luck meter (master.score with luck_draws=400) on the no-gate run and the primary gate: the universes' own excess is
judged by its band; the gate by the placebo's.
Drop rule: the gate stays as it is whatever the numbers — it is a safety rule; only if the primary gate costs more
than 0.5 pp/yr on *both* universes *and* the blocked entries beat the rest outside the placebo band would its removal
be proposed to the operator (never applied here). Nothing live changes.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/macrogate.py
"""
import bisect
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402
from books import LIVE  # noqa: E402

START, SPLIT = "1999-11-01", "2013-05-01"
ERAS = [("1999-11-01", "2007-10-01"), ("2007-10-01", "2015-01-01"), ("2015-01-01", "2026-12-31")]   # longhist's three
DRAWS = 20
MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
EXT = f"{datasets.S}/external"


def _mon(name):
    return MONTHS[name.strip().lower()[:3]]


def _last_month(mon, d1, d2):
    """The month of a meeting's last day: "April/May" with "30-1" ends in May, "January" with "28-29" in January."""
    return mon.split("/")[-1] if "/" in mon and d2 and int(d2) < int(d1) else mon.split("/")[0]


def fomc_dates():
    """Scheduled FOMC decision days (the last day of each meeting) 1999 →, from the Fed's pages."""
    out = set()
    for y in range(1999, 2021):
        page = open(f"{EXT}/fed/fomchistorical{y}.html", encoding="utf-8", errors="replace").read()
        for mon, d1, m2, d2, kind in re.findall(r"<h5[^>]*>([A-Za-z/]+) (\d+)(?:-(?:([A-Za-z]+) )?(\d+))?\s+([^<]*?)Meeting - \d{4}</h5>", page):
            if kind.strip():   # "(unscheduled)", "(cancelled)" — conference calls and notation votes never match "Meeting"
                continue
            out.add(f"{y}-{_mon(m2 or _last_month(mon, d1, d2)):02d}-{int(d2 or d1):02d}")   # "July 31-August 1" names the second month
    page = open(f"{EXT}/fed/fomccalendars.html", encoding="utf-8", errors="replace").read()
    year = None
    for yr, mon, day in re.findall(r"(\d{4}) FOMC Meetings|fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>|fomc-meeting__date[^>]*>([^<]*)</div>", page):
        if yr:
            year = int(yr)
        elif mon:
            cur = mon
        elif day and "(" not in day:   # "(notation vote)", "(unscheduled)", "(cancelled)" are out
            ds = re.findall(r"\d+", day)
            out.add(f"{year}-{_mon(_last_month(cur, ds[0], ds[-1] if len(ds) > 1 else None)):02d}-{int(ds[-1]):02d}")
    return sorted(out)


def bls_dates(release):
    """Release days of one BLS release ("Employment Situation" or "Consumer Price Index") 2000 →, from the yearly schedules."""
    out = set()
    for y in range(2000, 2027):
        t = open(f"{EXT}/bls/schedule_{y}.html", encoding="utf-8", errors="replace").read()
        t = re.sub(r"<script.*?</script>", "", t, flags=re.S); t = html.unescape(re.sub(r"<[^>]+>", " ", t)); t = re.sub(r"\s+", " ", t)
        for ref_m, ref_y, mon, day, yr in re.findall(rf"{release}(?:es)?, ([A-Za-z]+) (\d{{4}})(?:\(p\))? ([A-Z][a-z]+)\.? (\d+)(?:, (\d{{4}}))?", t):   # 2000–2007 layout
            out.add(f"{int(yr) if yr else int(ref_y) + (_mon(ref_m) == 12)}-{_mon(mon):02d}-{int(day):02d}")   # the year is omitted after the first row of a month; December's release is in January
        for mon, day, yr in re.findall(rf"[A-Z][a-z]+day, ([A-Z][a-z]+) (\d+), (\d{{4}}) \d\d:\d\d [AP]M {release} for", t):   # 2008 → layout
            out.add(f"{int(yr)}-{_mon(mon):02d}-{int(day):02d}")
    return sorted(out)


def event_sessions(mkt, dates):
    """The index of the first session on or after each event date (within the data)."""
    return sorted({bisect.bisect_left(mkt.dates, d) for d in dates if mkt.dates[0] <= d <= mkt.dates[-1]})


def mask(mkt, sessions, shape="spec"):
    """Eligible (T × N): the signal sessions masked so that no fill lands on E − 1 (and on E for "spec")."""
    out = np.ones((len(mkt.dates), len(mkt.name_list)), bool)
    for e in sessions:
        for f in ((e - 1, e) if shape == "spec" else (e - 1,)):
            if f - 1 >= 0:
                out[f - 1, :] = False   # the fill on session f comes from the signal on f − 1
    return out


def run(mkt, elig=None, luck=0):
    r = fastbt.run(mkt, {**LIVE, **({"eligible": elig} if elig is not None else {})}, START, None, want_trades=True)
    i0 = mkt.dates.index(r["start"]); c = r["_curve"]; dd = mkt.dates[i0:i0 + len(c)]; spy = mkt.spy[i0:i0 + len(c)]
    s = master.score(c[1:] / c[:-1] - 1, spy[1:] / spy[:-1] - 1, dd, SPLIT, ERAS, luck_draws=luck); s["trades"] = r["trades"]; return s


def desc(ts):
    rr = np.array([t["return"] for t in ts]); stops = np.mean([t["exit"] == "stop" for t in ts]) if ts else float("nan")
    return f"{len(ts)} entries, median {np.median(rr):+.1%}, mean {rr.mean():+.1%}, stops {stops:.0%}" if ts else "0 entries"


def main():
    fomc, es, cpi = fomc_dates(), bls_dates("Employment Situation"), bls_dates("Consumer Price Index")
    years = sorted({d[:4] for d in fomc})
    print("=== calendars: " + ", ".join(f"{k} {len(v)} ({v[0]} → {v[-1]})" for k, v in (("FOMC", fomc), ("Employment Situation", es), ("CPI", cpi))))
    print("    per year  " + " ".join(f"{y[2:]}:{sum(d[:4] == y for d in fomc)}/{sum(d[:4] == y for d in es)}/{sum(d[:4] == y for d in cpi)}" for y in years))
    sets = {"coded": sorted(set(fomc) | set(es)), "documented": sorted(set(fomc) | set(es) | set(cpi)), "fomc": fomc}
    cells = (("spec", "coded"), ("spec", "documented"), ("before", "coded"), ("before", "fomc"))
    for key, title in (("G_tiingo_sectors_1999", "the 11 sector ETFs (live universe)"), ("H_tiingo_names_1999", "the 15 names")):
        mkt = datasets.load(key); base = run(mkt, luck=400)
        print(f"\n=== {title} on Tiingo {START} → {mkt.dates[-1]}, split {SPLIT} | no gate: {master.luck_line(base)}")
        print(f"  {'gate':24} {'excess':>7} {'IS':>7} {'OOS':>7} | eras 99–07 07–15 15– | {'DD':>6} {'Sh':>5} | {'trades':>6} {'blocked':>8} | vs no gate")
        rows = {}
        for shape, st in cells:
            m = mask(mkt, event_sessions(mkt, sets[st]), shape); s = run(mkt, m, luck=400 if (shape, st) == cells[0] else 0); rows[(shape, st)] = (s, m)
        for label, (s, m) in [("no gate", (base, None))] + list(rows.items()):
            name = label if isinstance(label, str) else f"{label[0]} × {label[1]}"
            blk = f"{1 - m[:, 0].mean():.1%}" if m is not None else ""
            print(f"  {name:24} {s['excess']:+7.2%} {s['is']:+7.2%} {s['oos']:+7.2%} | " + " ".join(f"{x:+5.1%}" for x in s["eras"])
                  + f" | {s['dd']:6.1%} {s['sharpe']:5.2f} | {len(s['trades']):6} {blk:>8} | {s['excess'] - base['excess']:+.2%}")
        prim = rows[cells[0]][0]; print(f"  primary gate luck: {master.luck_line(prim)}")
        # M2: the entries the primary gate would have blocked, in the no-gate run, against the rest
        m = rows[cells[0]][1]; blocked, free = [], []
        for t in base["trades"]:
            k = mkt.idx[t["exit_date"]] - t["days"]   # the entry (fill) session; its signal session is k − 1
            (blocked if not m[k - 1, 0] else free).append(t)
        print(f"\n  M2 — entries on a blocked session (no-gate run): {desc(blocked)}\n       the rest:                                 {desc(free)}")
        rng = np.random.default_rng(94)
        for st in ("coded", "documented"):
            ev = event_sessions(mkt, sets[st]); by_year = {}
            for e in ev:
                by_year.setdefault(mkt.dates[e][:4], []).append(e)
            effects = []
            for _ in range(DRAWS):
                fake = []
                for y, es_y in by_year.items():
                    pool = [i for i, d in enumerate(mkt.dates) if d[:4] == y]
                    fake += list(rng.choice(pool, size=len(es_y), replace=False))
                effects.append(run(mkt, mask(mkt, sorted(fake), "spec"))["excess"] - base["excess"])
            e = np.array(effects); g = rows[("spec", st)][0]["excess"] - base["excess"]
            print(f"  placebo for spec × {st} (random blackout sessions, same count per year and shape, {DRAWS} draws): effect 5 % {np.percentile(e, 5):+.2%} / median {np.median(e):+.2%} / 95 % {np.percentile(e, 95):+.2%}; the gate {g:+.2%} → {'inside' if np.percentile(e, 5) <= g <= np.percentile(e, 95) else 'OUTSIDE'} the band")
    print("\n  M3 — live, the gate as coded fires on the morning run of a decision day only (the keyword list and the 08:30 timing); the 'before × fomc' row bounds its footprint. Nothing live changes.")


if __name__ == "__main__":
    main()
