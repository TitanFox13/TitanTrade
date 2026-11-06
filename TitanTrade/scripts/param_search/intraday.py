"""A fast de-risk layer on the core legs — "wouldn't we do better if we saw the market falling within a minute?"
(operator, 2026-11-06, the morning after SPY's −4.4 % session). The descriptive count (SPY 15-minute closes 2016 →:
after a −2 / −3 / −5 % intraday fall the rest of the day is a coin flip and the next day's close is up on average by
+0.31 / +0.48 / +1.54 %) said no; this is the pre-registered test with costs, a placebo and the luck meter.

The book here is the two CORE legs the switches actually sell — 40 % SPY (the dip sleeve's residual) / 60 % SPMO —
rebuilt from the SIP 15-minute bars (`external/alpaca_15min/`, split- and dividend-adjusted, Decision 100) on the
decade 2017-01-03 → 2026-10-12, with the live close-based switches from the daily archive (`books.decade()`: the
two-signal insurance ×0.5 at the previous close, the shock trigger −7 % / 10 / 20 ×0.5, exposure = min). The dip
positions themselves are not modelled: they carry their own broker stops and the switches never sell them (068).
Books: B0 no switches; B1 the live switches (the baseline); B1 + FAST: when SPY's first 15-minute close of the session
is at or below −X % against the previous close, both legs go to half for the rest of the session (exposure =
min(slow, 0.5)), restored at that session's close ("close"), at the next session's close ("next") or after 5 / 20
sessions ("h5" / "h20"); X ∈ {2, 3, 4, 5} %; B3 FAST alone (no slow switches — the watcher *instead of* the rules);
B4 the live shock rule read intraday: it fires at the first 15-minute close where SPY is −7 % against the close ten
sessions earlier instead of waiting for the close, then the same 20-session hold. Costs: 5 bp per side on the traded
half (fastbt's convention) — 5 bp of the book per halving, charged on the trigger day; the slow switches, as in every
harness number, trade free (a bias in the slow rules' favour of ≈ 0.1 pp/yr, 13 switches a decade).
Scores vs SPY (the market): excess CAGR, halves (split 2022-01-01), eras 2017–19 / 2020–22 / 2023 →, max drawdown,
Sharpe, worst relative year; the headline cells against B1 with the luck meter (400 draws); a placebo per headline
cell = the same number of trigger days drawn at random among the sessions the slow switches left at full exposure,
trigger times drawn from the real events, the same restore rule, 20 draws (10–90 % band); the big falls.

Hypotheses, written before the run:
  I1 B1 + FAST at −2 % / next: −1.5 … −3 pp/yr against B1 (13 triggers a year, the rebound missed on half the book,
     0.65 pp/yr of cost), the 2020 fall within 2 points of B1's (the slow shock is already on through March 2020);
     −3 % / next −1 … −2; the "close" restores cost less (−0.5 … −1.5) and protect nothing.
  I2 −5 % / next: −0.3 … +0.3 (nine events, all 2020 and April 2025), the 2020 fall 1 … 3 points shallower.
  I3 FAST alone (B3) at −3 % / next or h20: 2 … 4 pp/yr below B0 and below B1 in the second half; the 2020 fall
     between B0's and B1's — the watcher cannot replace the rules.
  I4 B4 (the shock rule read intraday): within ±0.3 pp/yr of B1, the 2020 fall 0 … 3 points shallower (2020-03-09 and
     03-12 caught at the open instead of the next session), 1 … 3 extra triggers over the decade that closed above −7 %.
  I5 placebo: the −2 % and −3 % cells INSIDE their random-trigger bands (the trigger carries no information about the
     rest of the day — the count's 49 %); the −5 % cell inside too (nine events cannot leave a band).
  I6 luck: −2 % / next against B1 t −1 … −2.5, P(excess > 0) under 10 %; −5 % / next t −0.5 … +0.5.
Drop rule: a fast layer (or B4) becomes a proposal only if its cell beats B1 on return in both halves and all three
eras with a Sharpe no lower and a 2020 fall no deeper, AND sits above its placebo's 90th percentile. Expected: no cell.
Nothing changes live. Run: uv run --with numpy python -I scripts/param_search/intraday.py
"""
import datetime as dt
import json
import os
import sys
import zoneinfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import books  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402

ET = zoneinfo.ZoneInfo("America/New_York"); EXT = f"{datasets.S}/external/alpaca_15min"
W_SPY, W_MOM, COST = 0.4, 0.6, 0.0005
SPLIT = "2022-01-01"; ERAS = [("2017-01-01", "2020-01-01"), ("2020-01-01", "2023-01-01"), ("2023-01-01", "2026-12-31")]
DEPTHS = (0.02, 0.03, 0.04, 0.05); RESTORES = ("close", "next", "h5", "h20")
EPISODES = [("2018-02", "2018-01-26", "2018-02-08"), ("2018Q4", "2018-09-20", "2018-12-24"), ("2020", "2020-02-19", "2020-03-23"),
            ("2022", "2022-01-03", "2022-10-12"), ("2025-04", "2025-02-19", "2025-04-08")]


def bars(sym):
    out = {}
    for b in json.load(open(f"{EXT}/{sym}.json")):
        t = dt.datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(ET); hm = t.strftime("%H:%M")
        if "09:30" <= hm < "16:00":
            out.setdefault(t.strftime("%Y-%m-%d"), []).append((hm, float(b["c"])))
    return out


def price_at(day, hm):
    """The last 15-minute close at or before ``hm`` (the first after it when the leg has no earlier bar that session)."""
    before = [c for t, c in day if t <= hm]
    return before[-1] if before else day[0][1]


def leg_returns(day_bars, prev_close, trig_hm, e0, e1):
    """One leg's return for the session: exposure e0 to the trigger bar, e1 after it (e0 all day with no trigger)."""
    close = day_bars[-1][1]
    if trig_hm is None:
        return e0 * (close / prev_close - 1)
    pt = price_at(day_bars, trig_hm)
    return e0 * (pt / prev_close - 1) + e1 * (close / pt - 1) - 2 * COST * (e0 - e1)


def run_book(sessions, spy, mom, slow, triggers, restore):
    """Daily returns of 0.4 SPY / 0.6 SPMO under the slow exposure ``slow`` (per session) and the fast layer:
    ``triggers`` maps a session to its trigger time. ``restore`` says how long the half-exposure lasts."""
    r = np.zeros(len(sessions)); fast_until = -1
    for i, s in enumerate(sessions):
        e_slow = slow[i]; trig = triggers.get(s)
        e0 = min(e_slow, 0.5) if i <= fast_until else e_slow
        if trig is not None and e0 > 0.5:
            e1 = 0.5
            if restore == "next": fast_until = i + 1
            elif restore == "h5": fast_until = i + 5
            elif restore == "h20": fast_until = i + 20
        else:
            e1 = e0; trig = None
        r[i] = W_SPY * leg_returns(spy[s], spy_prev[s], trig, e0, e1) + W_MOM * leg_returns(mom[s], mom_prev[s], trig, e0, e1)
    return r


def row(label, s, base=None):
    tail = " ".join(f"{x:+5.1%}" for x in s["eras"])
    d = f" | vs B1 {s['excess'] - base['excess']:+5.2%}" if base else ""
    return f"  {label:34} {s['excess']:+6.2%} {s['is']:+6.2%} / {s['oos']:+6.2%} | {s['dd']:6.1%} {s['sharpe']:5.2f} {s['worst_year']:+6.1%} | {tail}{d}"


def episode(r, dates, a, b):
    c = np.concatenate([[1.0], np.cumprod(1 + r)])
    ia = next(k for k, d in enumerate(dates) if d >= a); ib = max(k for k, d in enumerate(dates) if d <= b)
    return c[ib] / c[ia] - 1


spy_prev, mom_prev = {}, {}


def main():
    global spy_prev, mom_prev
    spy, mom = bars("SPY"), bars("SPMO")
    dec = books.decade(etfs=("SPMO",)); d = dec["d"]; shock = books.shock_flags(dec["spy"], -0.07, 10, 20)
    flags = {d[i + 1]: (bool(dec["bear"][i]), bool(shock[i])) for i in range(len(d) - 1)}
    sessions = [s for s in d[1:] if s in spy and s in mom]
    allspy = sorted(spy); allmom = sorted(mom)
    for s in sessions:
        spy_prev[s] = spy[allspy[allspy.index(s) - 1]][-1][1]; mom_prev[s] = mom[allmom[allmom.index(s) - 1]][-1][1]
    dates = [allspy[allspy.index(sessions[0]) - 1]] + sessions
    r_mkt = np.array([spy[s][-1][1] / spy_prev[s] - 1 for s in sessions])
    slow = np.array([0.5 if (flags[s][0] or flags[s][1]) else 1.0 for s in sessions])
    print(f"{len(sessions)} sessions {sessions[0]} → {sessions[-1]}; slow switches on {np.mean(slow < 1):.0%} of sessions; SPMO bars per session median {np.median([len(mom[s]) for s in sessions]):.0f}")
    # the triggers per depth: the first 15-minute close at or below −X % against the previous close
    trig = {}
    for x in DEPTHS:
        trig[x] = {}
        for s in sessions:
            for hm, c in spy[s]:
                if c / spy_prev[s] - 1 <= -x: trig[x][s] = hm; break
    # B4: the shock rule read intraday — against the close ten sessions earlier, on sessions the slow shock has not yet switched
    t4 = {}
    for i, s in enumerate(sessions):
        if i < 10 or flags[s][1]: continue
        base = spy[sessions[i - 10]][-1][1]
        for hm, c in spy[s]:
            if c / base - 1 <= -0.07: t4[s] = hm; break
    print(f"triggers: " + ", ".join(f"−{x:.0%} {len(trig[x])} ({len(trig[x]) / len(sessions) * 252:.1f}/yr, {sum(1 for s in trig[x] if slow[sessions.index(s)] == 1)} with the slow switches off)" for x in DEPTHS)
          + f"; the shock rule intraday: {len(t4)} sessions {sorted(t4)}")
    hdr = f"  {'book':34} {'excess':>6} {'IS':>6} / {'OOS':>6} | {'DD':>6} {'Sharpe':>5} {'worst':>6} | eras 2017–19 2020–22 2023 →"
    print("\n=== the core book 0.4 SPY / 0.6 SPMO vs SPY (the market)\n" + hdr)
    sc = lambda r, luck=0: master.score(r, r_mkt, dates, SPLIT, ERAS, luck_draws=luck)  # noqa: E731
    B0 = run_book(sessions, spy, mom, np.ones(len(sessions)), {}, "close"); B1 = run_book(sessions, spy, mom, slow, {}, "close")
    s0, s1 = sc(B0), sc(B1, 400)
    print(row("B0 no switches", s0)); print(row("B1 live switches (baseline)", s1)); print(f"  {'':34} {master.luck_line(s1)}")
    S = {}
    for x in DEPTHS:
        for rs in RESTORES:
            rr = run_book(sessions, spy, mom, slow, trig[x], rs); S[(x, rs)] = (rr, sc(rr))
            print(row(f"B1 + fast −{x:.0%} / {rs}", S[(x, rs)][1], s1))
    for x in (0.03, 0.05):
        for rs in ("next", "h20"):
            rr = run_book(sessions, spy, mom, np.ones(len(sessions)), trig[x], rs)
            print(row(f"B3 fast alone −{x:.0%} / {rs}", sc(rr), s1))
    B4 = run_book(sessions, spy, mom, slow, t4, "h20"); s4 = sc(B4)
    print(row("B4 the shock rule read intraday", s4, s1))
    print("\n=== the headline cells against B1 (the live switches as the benchmark): the luck meter, and the placebo band")
    rng = np.random.default_rng(11); free = [i for i in range(len(sessions)) if slow[i] == 1]
    for key, label, rr in [((0.02, "next"), "−2 % / next", S[(0.02, "next")][0]), ((0.03, "next"), "−3 % / next", S[(0.03, "next")][0]), ((0.05, "next"), "−5 % / next", S[(0.05, "next")][0]), (None, "B4 shock intraday", B4)]:
        dd = master.score(rr, B1, dates, SPLIT, ERAS, luck_draws=400)
        print(f"  {label:20} vs B1 {dd['excess']:+.2%} (IS {dd['is']:+.2%} / OOS {dd['oos']:+.2%}; eras {' '.join(f'{x:+.1%}' for x in dd['eras'])}); {master.luck_line(dd)}")
        if key is None: continue
        real = trig[key[0]]; times = [real[s] for s in real]; n = len(real)
        pl = []
        for _ in range(20):
            days = rng.choice(free, size=min(n, len(free)), replace=False)
            fake = {sessions[i]: times[rng.integers(len(times))] for i in days}
            pl.append(master.score(run_book(sessions, spy, mom, slow, fake, key[1]), r_mkt, dates, SPLIT, ERAS)["excess"])
        pl = np.array(pl); ex = S[key][1]["excess"]
        print(f"  {'':20} placebo ({n} random trigger days, same times and restore, 20 draws): median {np.median(pl):+.2%}, 10–90 % {np.percentile(pl, 10):+.2%} … {np.percentile(pl, 90):+.2%} — the real cell {ex:+.2%} ({'inside' if np.percentile(pl, 10) <= ex <= np.percentile(pl, 90) else 'below' if ex < np.percentile(pl, 10) else 'above'} the band)")
    print("\n=== the big falls (peak → trough over the episode's dates): the market, B0, B1, −3 % / next, −5 % / next, B4")
    for lab, a, b in EPISODES:
        print(f"  {lab:8} market {episode(r_mkt, dates, a, b):+6.1%} | B0 {episode(B0, dates, a, b):+6.1%}  B1 {episode(B1, dates, a, b):+6.1%}  −3/next {episode(S[(0.03, 'next')][0], dates, a, b):+6.1%}  −5/next {episode(S[(0.05, 'next')][0], dates, a, b):+6.1%}  B4 {episode(B4, dates, a, b):+6.1%}")


if __name__ == "__main__":
    main()
