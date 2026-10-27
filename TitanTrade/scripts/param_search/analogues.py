"""Which regime are we in, and what followed days like today? (operator question, 2026-10-27)

State on each session, from that session's close (the plan reads the same inputs the next morning), in coarse buckets:
  trend     market above / below its 200-day SMA
  ret12     trailing 252-session return: ≤ 0 / 0–15 % / > 15 %
  vol20     20-session realised volatility, annualised: < 12 / 12–20 / > 20 %
  dd52      distance below the 252-session high: < 3 / 3–10 / > 10 %
  breadth   share of sectors above their 200-day SMA (decade: the 11 SPDRs as live; century: the 49 industries): < 50 / 50–70 / > 70 %
  lead      momentum sleeve's trailing 12-month return minus the market's (decade SPMO, century the top decile): > 0 / ≤ 0
Today's state is read from the latest bars on disk (SPY to 2026-10-12; the Oct 27 check had breadth at 54.5 %, same bucket).
Pre-registered expectation (written before any result): the slow state variables carry little about the next one to two
years — Decision 067 addendum found every slow regime rule adds nothing — so the analogue days' forward distributions will
overlap the unconditional one, and the designs' relative returns will not separate by state beyond the known shape (dip
book ahead in bears, behind in rebounds). Analogue days overlap, so episodes (gaps > 63 sessions) are counted beside days;
a cell with fewer than 8 episodes is relaxed one dimension at a time (lead, then vol20, then dd52) and said so.
Read marginals first: each dimension alone against the unconditional distribution. Nothing here is a switching rule.
Run: uv run --with numpy python -I scripts/param_search/analogues.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402

LIVE = master.LIVE
DIMS = ("trend", "ret12", "vol20", "dd52", "breadth", "lead")
H = {"1y": 252, "2y": 504}


def sma(x, n):
    out = np.full(len(x), np.nan); c = np.concatenate([[0.0], np.cumsum(x)])
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def state(level, sectors, lead_level):
    """Bucket labels per session (strings), NaN-safe; `sectors` is a T × K level matrix."""
    T = len(level); r = np.concatenate([[np.nan], level[1:] / level[:-1] - 1])
    s200 = sma(level, 200); ret12 = np.full(T, np.nan); ret12[252:] = level[252:] / level[:-252] - 1
    vol = np.full(T, np.nan)
    for i in range(20, T):
        vol[i] = r[i - 19:i + 1].std() * np.sqrt(252)
    hi = np.full(T, np.nan)
    for i in range(252, T):
        hi[i] = level[i] / level[i - 251:i + 1].max() - 1
    K = sectors.shape[1]; above = np.full((T, K), np.nan)
    for k in range(K):
        col = sectors[:, k]; ok = ~np.isnan(col); v = col[ok]
        if len(v) > 200:
            a = np.full(len(v), np.nan); a[200:] = (v[200:] > sma(v, 200)[200:]).astype(float)   # SMA of the prior 200 (excl. today), like live
            above[ok, k] = a
    br = np.nanmean(above, axis=1) if K else np.full(T, np.nan)
    ld = np.full(T, np.nan); ld[252:] = (lead_level[252:] / lead_level[:-252] - 1) - ret12[252:]
    raw = {"trend": level > s200, "ret12": ret12, "vol20": vol, "dd52": -hi, "breadth": br, "lead": ld}
    b = {}
    b["trend"] = np.where(np.isnan(s200), None, np.where(level > s200, "above", "below"))
    b["ret12"] = np.where(np.isnan(ret12), None, np.where(ret12 <= 0, "≤0", np.where(ret12 <= 0.15, "0–15", ">15")))
    b["vol20"] = np.where(np.isnan(vol), None, np.where(vol < 0.12, "<12", np.where(vol <= 0.20, "12–20", ">20")))
    b["dd52"] = np.where(np.isnan(hi), None, np.where(hi > -0.03, "<3", np.where(hi > -0.10, "3–10", ">10")))
    b["breadth"] = np.where(np.isnan(br), None, np.where(br < 0.5, "<50", np.where(br <= 0.7, "50–70", ">70")))
    b["lead"] = np.where(np.isnan(ld), None, np.where(ld > 0, ">0", "≤0"))
    return b, raw


def forward(curve, h):
    out = np.full(len(curve), np.nan); out[:-h] = curve[h:] / curve[:-h] - 1
    return out


def episodes(idx, gap=63):
    n, last = 0, -10 ** 9; firsts = []
    for i in idx:
        if i - last > gap:
            n += 1; firsts.append(i)
        last = i
    return n, firsts


def dist(x):
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return "   n/a"
    return f"p10 {np.percentile(x, 10):+6.1%} med {np.median(x):+6.1%} p90 {np.percentile(x, 90):+6.1%} pos {np.mean(x > 0):3.0%}"


def report(label, dates, b, mask, fm, fdesign, today, show_episodes=False):
    idx = np.nonzero(mask)[0]
    ne, firsts = episodes(idx)
    print(f"\n{label}: {len(idx)} days, {ne} episodes")
    for h in H:
        print(f"  market {h}: {dist(fm[h][idx])}")
    for name, fd in fdesign.items():
        print(f"  {name:38} 1y excess: {dist(fd['1y'][idx])} | 2y: {dist(fd['2y'][idx])}")
    if show_episodes:
        print("  episodes (first day → market 1y / 2y): " + ", ".join(f"{dates[i][:7]} {fm['1y'][i]:+.0%}/{fm['2y'][i]:+.0%}" if not np.isnan(fm['1y'][i]) else f"{dates[i][:7]} (open)" for i in firsts))
    return ne


def run_set(label, dates, level, sectors, lead_level, designs, split, i0=0, also=()):
    """State over the whole series; forwards from i0 (the decade's designs start in 2017, their state needs the 2016 bars)."""
    b, raw = state(level, sectors, lead_level); raw["level"] = level
    T = len(dates); valid = np.array([all(b[k][i] is not None for k in DIMS) for i in range(T)]) & (np.arange(T) >= i0)
    today = {k: b[k][-1] for k in DIMS}
    print(f"\n{'=' * 100}\n{label}: {dates[i0]} → {dates[-1]}; state on {dates[-1]}: " + ", ".join(f"{k} {today[k]}" for k in DIMS)
          + f"  (raw: ret12 {raw['ret12'][-1]:+.1%}, vol20 {raw['vol20'][-1]:.1%}, below high {raw['dd52'][-1]:.1%}, breadth {raw['breadth'][-1]:.0%}, lead {raw['lead'][-1]:+.1%})")
    fm = {h: forward(level, n) for h, n in H.items()}
    fdesign = {name: {h: forward(c, n) - fm[h] for h, n in H.items()} for name, c in designs.items()}
    base = valid & ~np.isnan(fm["1y"])
    report("unconditional (every session with a 1-year forward)", dates, b, base, fm, fdesign, today)
    key = next(iter(fdesign)); ks = next(k for k, d in enumerate(dates) if d >= split)
    for hname, sl in (("first half", slice(0, ks)), ("second half", slice(ks, T))):
        mm = np.zeros(T, dtype=bool); mm[sl] = True; idx = np.nonzero(base & mm)[0]
        print(f"  {hname:12}: {len(idx):5d} d | market 1y {dist(fm['1y'][idx])} | {key[:22]:22} {dist(fdesign[key]['1y'][idx])}")
    print("\n--- marginals: each dimension alone (market 1y forward; the recommended book's 1y excess)")
    for k in DIMS:
        for v in sorted({x for x in b[k] if x is not None}, key=str):
            m = base & (b[k] == v); idx = np.nonzero(m)[0]; ne, _ = episodes(idx)
            mark = " ◄ today" if v == today[k] else ""
            print(f"  {k:8} {v:6} {len(idx):6d} d {ne:4d} ep | market 1y {dist(fm['1y'][idx])} | {key[:22]:22} {dist(fdesign[key]['1y'][idx])}{mark}")
    for tlabel, tstate in (("today as read from these bars", today),) + tuple(also):
        print(f"\n--- analogues of {tlabel} (exact match on all six, relaxed one dimension at a time when fewer than 8 episodes)")
        dims = list(DIMS)
        while True:
            m = base.copy()
            for k in dims:
                m &= (b[k] == tstate[k])
            ne = report("match on " + ", ".join(f"{k}={tstate[k]}" for k in dims), dates, b, m, fm, fdesign, tstate, show_episodes=True)
            if ne >= 8 or len(dims) <= 3:
                break
            dims.remove(next(k for k in ("lead", "vol20", "dd52") if k in dims))
        for name, sl in (("first half", slice(0, ks)), ("second half", slice(ks, T))):   # is the forward picture stable across eras?
            mm = np.zeros(T, dtype=bool); mm[sl] = True; idx = np.nonzero(m & mm)[0]
            if len(idx):
                ne, _ = episodes(idx); print(f"  {name:12}: {len(idx):5d} d {ne:3d} ep | market 1y {dist(fm['1y'][idx])} | {key[:22]:22} {dist(fdesign[key]['1y'][idx])}")
    return b, raw


def last_12_months(dates, b, raw):
    print("\n--- the state over the past 12 months (month-end sessions)")
    print(f"{'month':8} {'SPY':>8} {'ret12':>7} {'vol20':>6} {'dd52':>6} {'breadth':>7} {'lead':>6} | buckets")
    months = sorted({d[:7] for d in dates[-270:]})
    for mth in months:
        i = max(k for k, d in enumerate(dates) if d[:7] == mth)
        print(f"{mth:8} {raw['level'][i]:8.1f} {raw['ret12'][i]:+7.1%} {raw['vol20'][i]:6.1%} {raw['dd52'][i]:6.1%} {raw['breadth'][i]:7.0%} {raw['lead'][i]:+6.1%} | " + ", ".join(f"{b[k][i]}" for k in DIMS))


def main():
    # ---- decade: SPY, 11 sectors, SPMO; designs from master.decade's components
    cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index("2017-01-03")
    _, _, spy_above, breadth = cur.pre(90, 150, 200)
    SEC = fastbt.run(sec, LIVE, "2017-01-03", None)["_curve"]; d = dates[i0:]
    v = datasets.alpaca("SPMO"); SP = np.array([v.get(t, np.nan) for t in d]); n = min(len(SEC), len(SP)); d = d[:n]; spy = cur.spy[i0:i0 + n]
    r = {"dip": SEC[1:n] / SEC[:n - 1] - 1, "mom": SP[1:n] / SP[:n - 1] - 1, "mkt": spy[1:] / spy[:-1] - 1}
    bear = (master.prev(spy_above[i0:i0 + n][1:]) == 0.0) & (master.prev(breadth[i0:i0 + n][1:]) < 0.5); shock = master.shock_flags(spy, -0.07, 10, 20)
    def lvl(rr):
        return np.concatenate([[1.0], np.cumprod(1 + rr)])
    designs = {"dip 40 / SPMO 60, ins x0.5, shock": lvl(master.book(0.4, r["dip"], r["mom"], r["mkt"], bear, 0.5, shock, None, False, None)),
               "live (dip only, ins x0.5)": lvl(master.book(1.0, r["dip"], r["mom"], r["mkt"], bear, 0.5, None, None, False, None)),
               "dip 40 / SPMO 60, no ins, shock": lvl(master.book(0.4, r["dip"], r["mom"], r["mkt"], bear, None, shock, None, False, None)),
               "SPMO only, ins x0.5, shock": lvl(master.book(0.0, r["dip"], r["mom"], r["mkt"], bear, 0.5, shock, None, False, None))}
    full_spy = cur.spy; full_sec = sec.sectors; full_sp = np.array([v.get(t, np.nan) for t in dates])
    designs_full = {k: np.concatenate([np.full(i0, np.nan), c]) for k, c in designs.items()}
    spy_state = {"trend": "above", "ret12": ">15", "vol20": "<12", "dd52": "<3", "breadth": "<50", "lead": ">0"}   # the Oct 12 bars
    oct27 = dict(spy_state, breadth="50–70")                                                                      # breadth 54.5 % at the Oct 27 check
    b, raw = run_set("DECADE (SPY, 11 SPDR sectors, SPMO; state from the 2016 bars)", dates, full_spy, full_sec, full_sp, designs_full, "2022-01-01", i0,
                     also=(("the Oct 27 check (breadth 54.5 %)", oct27),))
    last_12_months(dates, b, raw)
    # ---- century: French market, 49 industries, top momentum decile
    ind = datasets.load("F_french_49ind_1926"); mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
    r0 = fastbt.run(ind, LIVE, "1927-07-01", None); fd = ind.dates[ind.dates.index(r0["start"]):]
    dip = r0["_curve"]; mk = r0["_spy_curve"]; hi = np.array([mom["Hi PRIOR"].get(x, np.nan) for x in fd])
    rc = {"dip": dip[1:] / dip[:-1] - 1, "mom": np.nan_to_num(hi[1:] / hi[:-1] - 1), "mkt": mk[1:] / mk[:-1] - 1}
    bearc = master.prev(master.sma_above(mk)[1:]) == 0.0; shockc = master.shock_flags(mk, -0.07, 10, 20)
    designs_c = {"dip 40 / mom 60, ins x0.5, shock": lvl(master.book(0.4, rc["dip"], rc["mom"], rc["mkt"], bearc, 0.5, shockc, None, False, None)),
                 "live (dip only, ins x0.5)": lvl(master.book(1.0, rc["dip"], rc["mom"], rc["mkt"], bearc, 0.5, None, None, False, None)),
                 "dip 40 / mom 60, no ins, shock": lvl(master.book(0.4, rc["dip"], rc["mom"], rc["mkt"], bearc, None, shockc, None, False, None)),
                 "mom only, ins x0.5, shock": lvl(master.book(0.0, rc["dip"], rc["mom"], rc["mkt"], bearc, 0.5, shockc, None, False, None))}
    j0 = ind.dates.index(fd[0]); sect = ind.sectors[j0:j0 + len(fd)]
    hi_lvl = np.where(np.isnan(hi), np.nan, hi); hi_lvl = np.array([x if not np.isnan(x) else (hi_lvl[i - 1] if i else 100.0) for i, x in enumerate(hi_lvl)])
    run_set("CENTURY (French market, 49 industries, top momentum decile; split 1975)", fd, mk, sect, hi_lvl, designs_c, "1975-01-01",
            also=(("today's SPY state with the 11-sector breadth of the Oct 12 bars (< 50 %)", spy_state), ("the same with the Oct 27 breadth (50–70 %)", oct27)))


if __name__ == "__main__":
    main()
