"""Shock early release on a fast rebound (Decision 068 addendum, 2026-10-29; brainstorm candidate 2).

The shock trigger halves exposure for 20 sessions after a −7 % move over 10 sessions and its known cost is the rebound
after the fall. The post-crash tilt and the five momentum-crash guards were *state* rules and failed; this is the
trigger's mirror, a *fact* rule: a +X % move over N sessions, while the hold is on, ends it early (the next −7 % re-arms
it as before). Pre-registered hypotheses, written before any result:
  R1  decade (2017 →): +0.3 … +0.6 pp/yr over the recommended book, from the 2018-12, 2020-03 and 2025-04 rebounds;
      the worst drawdown within 2 points of the book's −20 %;
  R2  century: 0 ± 0.3 pp/yr — the 1929–32 and 2008 bear-market rallies release into the next leg down and give back
      what 1932-06, 1987-10 and 2009-03 gain;
  R3  the decade gain beats the placebo (the same number of releases at random sessions *inside* the holds, 20 draws);
      the century gain sits inside the placebo spread;
  R4  the cells agree in sign across +5 / +7 / +10 % and 5 / 10 sessions (a plateau), and the release is not just a
      shorter hold: the unconditional hold-10 and hold-5 cells of the Decision 067 grid are the reference rows.
Drop rule (pre-registered): decade gain < +0.2, century < −0.3, drawdown > 2 points worse, or the decade gain below the
placebo's 90th percentile. Mechanics as master.py: e = min(insurance ×0.5, shock ×0.5), book = e × (0.4 dip + 0.6 mom),
decade = sector dip book + SPMO (split 2022), century = industries + top momentum decile (split 1975, four eras);
signals from the previous session; de-risked capital earns 0. Run: uv run --with numpy python -I scripts/param_search/release.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import master  # noqa: E402


def lookback_ret(level, look):
    n = len(level) - 1
    r = np.array([np.nan] * look + [level[i] / level[i - look] - 1 for i in range(look, n + 1)])[1:]
    return master.prev(r)


def new_high(level, look):
    n = len(level) - 1
    h = np.array([False] * look + [level[i] >= level[i - look:i].max() for i in range(look, n + 1)])[1:]
    return np.concatenate([[False], h[:-1]])


def shock_with_release(level, release, thr=-0.07, look=10, hold=20, forced=None):
    """Shock flags with an early release: `release[i]` (previous-session fact) or `forced[i]` ends an active hold."""
    n = len(level) - 1
    ret = lookback_ret(level, look)
    e = np.zeros(n, dtype=bool); fired = np.zeros(n, dtype=bool); k = 0
    for i in range(n):
        if ret[i] < thr:
            k = hold
        elif k > 0 and ((release is not None and release[i]) or (forced is not None and forced[i])):
            k = 0; fired[i] = True
        e[i] = k > 0; k = max(0, k - 1)
    return e, fired


def main():
    rng = np.random.default_rng(11)
    eps_all = {"decade": [("2018reb", "2018-12-24", "2019-03-24"), ("2020reb", "2020-03-23", "2020-06-23"), ("2022jun", "2022-06-16", "2022-08-16"),
                          ("2022oct", "2022-10-12", "2023-01-12"), ("2025reb", "2025-04-08", "2025-07-08")],
               "century": [("1929-32", "1929-09-03", "1932-06-01"), ("1932reb", "1932-06-01", "1932-12-01"), ("1987", "1987-10-19", "1988-01-19"),
                           ("2008", "2008-09-15", "2009-03-09"), ("2009reb", "2009-03-09", "2009-06-09"), ("2020reb", "2020-03-23", "2020-06-23")]}
    for name, dd, lvl, r, bear, split, eras in carry.sets():
        n = len(r["mkt"]); eps = eps_all[name]
        core = 0.4 * r["dip"] + 0.6 * r["mom"]
        shock0 = master.shock_flags(lvl, -0.07, 10, 20)
        base = carry.exposure(bear, shock0) * core; sb = master.score(base, r["mkt"], dd, split, eras)
        hold_days = np.nonzero(shock0)[0]

        def episodes(rr):
            c = np.concatenate([[1.0], np.cumprod(1 + rr)]); m = np.concatenate([[1.0], np.cumprod(1 + r["mkt"])]); out = []
            for _, a, b in eps:
                ia = next(k for k, x in enumerate(dd) if x >= a); ib = next(k for k, x in enumerate(dd) if x >= b); out.append(c[ib] / c[ia] - m[ib] / m[ia])
            return out

        print(f"\n=== shock early release — {name} {dd[0]} → {dd[-1]}: recommended book {sb['excess']:+.2%} (IS {sb['is']:+.1%} / OOS {sb['oos']:+.1%}), DD {sb['dd']:.1%}, Sharpe {sb['sharpe']:.2f}, de-risked {np.mean(shock0):.1%} by the shock; episodes = book − market")
        print(f"{'release rule':34} {'excess':>7} {'gain':>6} {'IS':>6} {'OOS':>6} | {'DD':>6} {'Sh':>5} | {'shock%':>6} {'rel':>3} | " + " ".join(f"{x[0]:>8}" for x in eps) + " | placebo gain med [p10…p90], beaten")
        print(f"{'none (recommended book)':34} {sb['excess']:+7.2%} {'':>6} {sb['is']:+6.1%} {sb['oos']:+6.1%} | {sb['dd']:6.1%} {sb['sharpe']:5.2f} | {np.mean(shock0):6.1%} {'':>3} | " + " ".join(f"{x:+8.1%}" for x in episodes(base)))
        for hold in (10, 5):   # the unconditional reference: simply a shorter hold
            sh = master.shock_flags(lvl, -0.07, 10, hold); rr = carry.exposure(bear, sh) * core; s = master.score(rr, r["mkt"], dd, split, eras)
            print(f"{f'reference: hold {hold} (no release)':34} {s['excess']:+7.2%} {s['excess'] - sb['excess']:+6.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['dd']:6.1%} {s['sharpe']:5.2f} | {np.mean(sh):6.1%} {'':>3} | " + " ".join(f"{x:+8.1%}" for x in episodes(rr)))
        rules = {}
        for up in (0.05, 0.07, 0.10):
            for look in (5, 10):
                rules[f"+{up:.0%} over {look} sessions"] = lookback_ret(lvl, look) > up
        for look in (10, 20):
            rules[f"{look}-session high"] = new_high(lvl, look)
        for rname, rel in rules.items():
            sh, fired = shock_with_release(lvl, rel); rr = carry.exposure(bear, sh) * core; s = master.score(rr, r["mkt"], dd, split, eras)
            m = int(fired.sum()); gains = []
            for _ in range(20):
                forced = np.zeros(n, dtype=bool); forced[rng.choice(hold_days, size=min(m, len(hold_days)), replace=False)] = True
                sh2, _ = shock_with_release(lvl, None, forced=forced)
                gains.append(master.score(carry.exposure(bear, sh2) * core, r["mkt"], dd, split, eras)["excess"] - sb["excess"])
            g = np.array(gains); gain = s["excess"] - sb["excess"]
            print(f"{rname:34} {s['excess']:+7.2%} {gain:+6.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['dd']:6.1%} {s['sharpe']:5.2f} | {np.mean(sh):6.1%} {m:3d} | "
                  + " ".join(f"{x:+8.1%}" for x in episodes(rr)) + f" | {np.median(g):+5.2%} [{np.percentile(g, 10):+5.2%}…{np.percentile(g, 90):+5.2%}], {np.mean(gain > g):3.0%}")
        if eras:
            print("  eras (book / +7 % over 10): " + "; ".join(f"{a[:4]}–{b[:4]} {x:+.1%} / {y:+.1%}" for (a, b), x, y in
                  zip(eras, sb["eras"], master.score(carry.exposure(bear, shock_with_release(lvl, rules['+7% over 10 sessions'])[0]) * core, r["mkt"], dd, split, eras)["eras"])))


if __name__ == "__main__":
    main()
