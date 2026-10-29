"""Calendar and timing variants (brainstorm #11, #36, #13; Decision 068 addendum, 2026-10-29). Pre-registered:
  S1  (#11, Bouman–Jacobsen "Halloween") halving the book's exposure May–October: negative on the decade (a
      de-risking rule at 0 % cash), small positive at best on the century, and the May phase is not the best of the
      twelve possible six-month phases on both eras (the other eleven phases are the placebo).
  S2  (#36) the month a dip entry is made carries no information: no month's mean trade return deviates from the
      overall mean by more than the shuffled-month placebo does, in both halves of the century.
  T1  (#13, Chan / Connors short-term reversal) requiring one more down session (the signal close below the previous
      close) before an entry changes the hindsight-free universes (D, F) by < 0.3 pp/yr and not in both halves.
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/seasons.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import dipfilters  # noqa: E402
import dynamic_universe as du  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402

LIVE = du.LIVE


def halloween():
    for name, dd, lvl, r, bear, split, eras in carry.sets():
        shock = master.shock_flags(lvl, -0.07, 10, 20); e = carry.exposure(bear, shock); core = 0.4 * r["dip"] + 0.6 * r["mom"]
        sb = master.score(e * core, r["mkt"], dd, split, eras)
        months = np.array([int(t[5:7]) for t in dd[1:]])
        print(f"\n=== Halloween — {name}: book {sb['excess']:+.2%}, DD {sb['dd']:.1%}, Sharpe {sb['sharpe']:.2f}; exposure ×0.5 for the six months starting in …")
        rows = []
        for m0 in range(1, 13):
            off = ((months - m0) % 12) < 6
            s = master.score(np.minimum(e, np.where(off, 0.5, 1.0)) * core, r["mkt"], dd, split, eras)
            rows.append((m0, s["excess"] - sb["excess"], s["dd"], s["sharpe"]))
        for m0, g, d_, sh in rows:
            print(f"  start month {m0:2d}{' (May = Halloween)' if m0 == 5 else '':20} gain {g:+.2%}  DD {d_:6.1%}  Sharpe {sh:.2f}")
        g = [x[1] for x in rows]; print(f"  May's rank among the 12 phases by gain: {sorted(g, reverse=True).index(rows[4][1]) + 1}; best phase {max(g):+.2%}, median {np.median(g):+.2%}")


def entry_month():
    rng = np.random.default_rng(36)
    F = datasets.load("F_french_49ind_1926"); res = fastbt.run(F, LIVE, "1927-07-01", None, want_trades=True)
    dates = F.dates
    rows = [(int(dates[dates.index(t["exit_date"]) - t["days"]][5:7]), t["return"], dates[dates.index(t["exit_date"]) - t["days"]] < "1975-01-01") for t in res["trades"]]
    m, y, early = (np.array(x) for x in zip(*rows))
    print(f"\n=== entry month — F 49 industries, {len(y)} trades, mean {y.mean():+.1%}: mean trade return by entry month, 1927–74 / 1975 → (n)")
    for k in range(1, 13):
        a, b = y[(m == k) & early], y[(m == k) & ~early]
        print(f"  month {k:2d}: {a.mean():+6.1%} ({len(a):3d}) / {b.mean():+6.1%} ({len(b):3d})")
    def maxdev(mm, yy):
        return max(abs(yy[mm == k].mean() - yy.mean()) for k in range(1, 13) if (mm == k).sum() > 10)
    for label, mask in (("1927–74", early), ("1975 →", ~early)):
        act = maxdev(m[mask], y[mask]); pl = np.array([maxdev(rng.permutation(m[mask]), y[mask]) for _ in range(20)])
        print(f"  {label}: largest month deviation {act:.1%} vs shuffled-month placebo median {np.median(pl):.1%} [p10 {np.percentile(pl, 10):.1%} … p90 {np.percentile(pl, 90):.1%}]")


def down_day():
    print("\n=== one more down session before the entry (signal close < previous close)")
    for name, mkt, memb, start, split in dipfilters.universes():
        P = mkt.names; T, N = P.shape
        down = np.zeros((T, N), dtype=bool); down[1:] = P[1:] < P[:-1]
        if memb is not None: down &= memb
        base = {**LIVE} if memb is None else {**LIVE, "eligible": memb}
        print(f"--- {name}")
        du.row("live rule", mkt, base, start, split, mask=memb)
        du.row("entry only after a down session", mkt, {**base, "eligible": down}, start, split, mask=memb)
        up = np.zeros((T, N), dtype=bool); up[1:] = P[1:] > P[:-1]
        if memb is not None: up &= memb
        du.row("entry only after an up session (the mirror)", mkt, {**base, "eligible": up}, start, split, mask=memb)


if __name__ == "__main__":
    halloween(); entry_month(); down_day()
