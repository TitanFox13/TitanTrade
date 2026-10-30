"""A VIX-based shock trigger (roadmap B6; Decision 078 research, 2026-10-30).

The live shock trigger is a fact about prices: SPY's 10-session return at or below −7 % on any of the last 20
sessions → exposure ×0.5 (Decision 067 addendum: a plateau of 81 cells, cuts the worst drawdown by a third at
0 … 1 pp/yr, paid back in the rebound year). B6 asks whether the market's fear gauge — the VIX, Cboe's 30-day implied
volatility, daily from 1990 — triggers *earlier or better* than the price fall itself. Decision 077 closed the VIX as
a slow second signal for the insurance (a state); this is the fast-fact mechanism, which is a different question.
Data: Cboe VIX close 1990-01 → (the Decision 072 library, `datasets.cboe("VIX")`), VIX3M 2009 → for the term
structure; the century book on 1990-02 → 2026-08 (the French market; one era, split 2008-05, three decades 1990–2000 /
2000–2010 / 2010–2026 as the sub-eras) and the ETF book on the decade 2017 → 2026-10 (split 2022). Every VIX reading
is the previous session's close (no look-ahead; the VIX is published with the close).

Variants, fixed before the first run (each as a replacement for the price rule and as a third rule in the min()):
  - level: VIX > X, X ∈ {25, 30, 35, 40}, → ×0.5 for H sessions, re-armed, H ∈ {10, 20, 40} (12 cells);
  - jump: the VIX up by ≥ J points over L sessions, J ∈ {8, 12, 16}, L ∈ {5, 10}, → ×0.5 for H ∈ {10, 20} (12 cells);
  - term structure (2009 → only, a sub-test): VIX > VIX3M (an inverted curve) → ×0.5 for H ∈ {10, 20};
  - the reference: the live price rule (−7 % / 10 / 20 / ×0.5) on the same windows, and the book with no shock rule;
  - the timing table: for every bear of the window (1990, 1997-10, 1998-08, 2000–02, 2008, 2010-05, 2011-08, 2015-08,
    2018-02, 2018-Q4, 2020, 2022, 2025) the first session each rule fired and the VIX rule's lead in sessions;
  - the placebo for the level rule at X = 30 / H = 20: the VIX series block-shuffled (63 sessions), 20 draws — a
    state rule earns its place against a random state of the same frequency.

Pre-registered hypotheses (the expected numbers were written before the first run):
  X1  the VIX level rule and the price rule fire on the same episodes: at X = 30 / H = 20 the two agree on ≥ 85 % of
      de-risked sessions over 1990 →; the VIX leads by 1 … 3 sessions in the fast crashes (1997, 1998, 2018-02, 2020,
      2025) and lags or never fires in the slow ones (2000–02 in its first year, 2022 — the VIX stayed below 37).
  X2  no VIX cell beats the price rule's cell on 1990 → by more than noise: the best level cell is within ±0.3 pp/yr
      of the price rule's excess with a drawdown within 2 points; the jump cells are noisier (±0.5) and no better;
      the term-structure rule on 2009 → ≈ the X = 25 level rule.
  X3  the VIX as a third rule in the min() costs 0.2 … 0.5 pp/yr on both windows for ≤ 1 point of drawdown — more
      de-risked sessions, the same crashes.
  X4  the level rule is inside its placebo's spread on the decade (the era wants less de-risking) and at or above the
      placebo's median on 1990 → — the fast fact carries information the random state does not, as the price rule did.
  X5  the plateau: the level cells' excess varies by < 0.5 pp/yr across X 25 … 35 and H 10 … 20 on 1990 →; X = 40 fires
      too rarely (2008 and 2020 only).

Drop rules, written first:
  - a Decision (the VIX replacing or joining the price rule) only if a VIX cell beats the price rule's cell on 1990 →
    in both halves *and* in all three decades, with its eight neighbours within 0.3 pp/yr of it (a plateau, not a
    cell), a drawdown no deeper, and the ETF decade no worse than the price rule's — the Decision 067 bar;
  - otherwise the price rule stays: it needs nothing but closes, exists on every market and every century, and the
    VIX adds nothing a 7 % fall does not already say; B6 is recorded and closed.

Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/vixshock.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402
from breadth2 import block_shuffle  # noqa: E402
from putwrite import cut, ep  # noqa: E402
from stress import known  # noqa: E402

LEVELS, HOLDS = (25.0, 30.0, 35.0, 40.0), (10, 20, 40)
JUMPS, JUMP_LOOKBACKS, JUMP_HOLDS = (8.0, 12.0, 16.0), (5, 10), (10, 20)
ERAS3 = [("1990-02-01", "2000-01-01"), ("2000-01-01", "2010-01-01"), ("2010-01-01", "2026-09-01")]
BEARS = [("1990", "1990-07-16"), ("1997-10", "1997-10-01"), ("1998-08", "1998-07-17"), ("2000-02", "2000-03-24"), ("2008", "2007-10-09"), ("2010-05", "2010-04-23"), ("2011-08", "2011-04-29"), ("2015-08", "2015-05-21"),
         ("2018-02", "2018-01-26"), ("2018-Q4", "2018-09-20"), ("2020", "2020-02-19"), ("2022", "2022-01-03"), ("2025", "2025-02-19")]
EPS = {"1990": [("2000-02", "2000-03-24", "2002-10-09"), ("2008", "2007-10-09", "2009-03-09"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12"), ("2025", "2025-02-19", "2025-04-08")],
       "decade": [("2018Q4", "2018-09-20", "2018-12-24"), ("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12"), ("2025", "2025-02-19", "2025-04-08")]}


def hold_flags(trigger, hold):
    """×0.5 for ``hold`` sessions after each trigger session, re-armed (the shock trigger's semantics)."""
    e = np.zeros(len(trigger), dtype=bool); k = 0
    for i, t in enumerate(trigger):
        if t: k = hold
        e[i] = k > 0; k = max(0, k - 1)
    return e


def price_trigger(level, thr=-0.07, look=10):
    n = len(level) - 1; ret = np.array([np.nan] * look + [level[i] / level[i - look] - 1 for i in range(look, n + 1)])[1:]
    return np.nan_to_num(master.prev(ret), nan=0.0) < thr


def main():
    rng = np.random.default_rng(78); vix = datasets.cboe("VIX"); vix3m = datasets.cboe("VIX3M")
    dec, cen = carry.sets(); _, fd, mk, rc, bear_c, _, _ = cen
    verdict = {}
    for wname, (dd, r, lvl, bear, split, eras, vstart) in {
        "1990": (lambda d, rs: (d, {"dip": rs["dip"], "mom": rs["mom"], "mkt": rs["mkt"]}, np.concatenate([[1.0], np.cumprod(1 + rs["mkt"])]), rs["bear"], "2008-05-01", ERAS3, "2009-02-02"))(*cut(fd, {"dip": rc["dip"], "mom": rc["mom"], "mkt": rc["mkt"], "bear": bear_c}, "1990-02-01", "2026-08-31")),
        "decade": (dec[1], dec[3], dec[2], dec[4], dec[5], None, dec[1][0]),
    }.items():
        core = 0.4 * r["dip"] + 0.6 * r["mom"]; m = r["mkt"]; ins = np.where(bear, 0.5, 1.0)
        v = np.nan_to_num(known(vix, dd, 0), nan=0.0); v3 = known(vix3m, dd, 0)
        ptrig = price_trigger(lvl); pshock = hold_flags(ptrig, 20)
        sc = lambda rr: master.score(rr, m, dd, split, eras)  # noqa: E731
        def book(*rules):
            e = ins.copy()
            for f in rules: e = np.minimum(e, np.where(f, 0.5, 1.0))
            return e * core
        eps = EPS[wname]
        def line(label, rr, on, pl=None):
            s = sc(rr); e = " ".join(f"{ep(rr, m, dd, a, b):+5.0%}/{ep(rr, m, dd, a, b, rebound=True):+4.0%}" for _, a, b in eps)
            print(f"{label:46} {s['excess']:+7.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['dd']:6.1%} {s['sharpe']:5.2f} | {np.mean(on):5.1%} | " + (" ".join(f"{x:+6.1%}" for x in s["eras"]) + " | " if eras else "") + e
                  + (f" | placebo {np.median(pl):+5.2%} [{np.percentile(pl, 10):+5.2%}…{np.percentile(pl, 90):+5.2%}], beaten {np.mean(s['excess'] > pl):3.0%}" if pl is not None else ""))
            return s
        print(f"\n=== {wname}: {dd[0]} → {dd[-1]}; columns: excess vs the market, IS, OOS | DD, Sharpe | de-risked share | " + ("eras | " if eras else "") + "episodes (book − market, fall / rebound year)")
        print(f"{'rule':46} {'excess':>7} {'IS':>6} {'OOS':>6} | {'DD':>6} {'Sh':>5} | {'on':>5} | " + ("   ".join(f"{a[:4]}–{b[2:4]}" for a, b in eras) + " | " if eras else "") + " ".join(f"{x[0]:>10}" for x in eps))
        s_none = line("insurance only, no shock rule", book(), ins < 1)
        s_price = line("insurance + the price rule −7 % / 10 / 20 (live)", book(pshock), (ins < 1) | pshock)
        # level cells
        cells = {}
        for X in LEVELS:
            for H in HOLDS:
                f = hold_flags(v > X, H); pl = None
                if X == 30.0 and H == 20:
                    pl = np.array([sc(book(hold_flags(block_shuffle(v, rng) > X, H)))["excess"] for _ in range(20)])
                cells[(X, H)] = line(f"VIX > {X:g} / hold {H} (replacing the price rule)", book(f), (ins < 1) | f, pl)
                if H == 20:
                    line(f"  … + the price rule (third rule)", book(pshock, f), (ins < 1) | pshock | f)
        # jump cells
        for J in JUMPS:
            for L in JUMP_LOOKBACKS:
                jump = np.concatenate([np.zeros(L, dtype=bool), (v[L:] - v[:-L]) >= J])
                for H in JUMP_HOLDS:
                    f = hold_flags(jump, H); line(f"VIX up ≥ {J:g} pts in {L} / hold {H} (replacing)", book(f), (ins < 1) | f)
        # term structure, 2009 →
        if vstart <= "2009-02-02":
            k0 = next(k for k, t in enumerate(dd[1:]) if t >= "2009-02-02")
            inv = np.nan_to_num(v > v3, nan=False); inv[:k0] = False
            for H in (10, 20):
                f = hold_flags(inv, H); line(f"VIX > VIX3M (inverted) / hold {H}, from 2009 (replacing)", book(f), (ins < 1) | f)
        # agreement and timing
        f30 = hold_flags(v > 30.0, 20); both = pshock & f30; either = pshock | f30
        print(f"  agreement at VIX > 30 / hold 20 vs the price rule: de-risked by the price rule {np.mean(pshock):.1%}, by the VIX {np.mean(f30):.1%}, both {np.mean(both):.1%} = {np.mean(both) / max(np.mean(either), 1e-9):.0%} of either")
        rows = []
        for name, start in BEARS:
            if start < dd[0] or start > dd[-1]: continue
            k0 = next(k for k, t in enumerate(dd[1:]) if t >= start); kp = next((k for k in range(k0, min(k0 + 120, len(ptrig))) if ptrig[k]), None); kv = next((k for k in range(k0, min(k0 + 120, len(v))) if v[k] > 30.0), None)
            rows.append(f"{name}: price {dd[1:][kp] if kp is not None else 'never'}, VIX>30 {dd[1:][kv] if kv is not None else 'never'}" + (f", lead {kp - kv:+d}" if kp is not None and kv is not None else ""))
        print("  first firing after the peak (lead = sessions the VIX fired before the price rule):\n    " + "\n    ".join(rows))
        # the plateau and the verdict pieces
        best = max(cells, key=lambda c: cells[c]["excess"]); bs = cells[best]
        neigh = [cells[(X, H)] for X in LEVELS for H in HOLDS if (X, H) != best and abs(LEVELS.index(X) - LEVELS.index(best[0])) <= 1 and abs(HOLDS.index(H) - HOLDS.index(best[1])) <= 1]
        spread = max(abs(n["excess"] - bs["excess"]) for n in neigh)
        print(f"  best level cell VIX > {best[0]:g} / hold {best[1]}: {bs['excess']:+.2%} ({bs['is']:+.1%} / {bs['oos']:+.1%}), DD {bs['dd']:.1%} vs the price rule {s_price['excess']:+.2%} ({s_price['is']:+.1%} / {s_price['oos']:+.1%}), DD {s_price['dd']:.1%}; neighbours within {spread:.2%}")
        verdict[wname] = dict(best=best, bs=bs, sp=s_price, spread=spread, cells=cells)
    # ---------------- the pre-registered verdict ----------------
    v90, vd = verdict["1990"], verdict["decade"]; bs, sp = v90["bs"], v90["sp"]
    ok = bs["is"] > sp["is"] and bs["oos"] > sp["oos"] and all(x > y for x, y in zip(bs["eras"], sp["eras"])) and v90["spread"] <= 0.003 and bs["dd"] >= sp["dd"]
    dbest = vd["cells"].get(v90["best"]); dok = dbest is not None and dbest["excess"] >= vd["sp"]["excess"]
    print("\n=== pre-registered verdict")
    print(f"  1990 →: best level cell VIX > {v90['best'][0]:g} / hold {v90['best'][1]} vs the price rule — both halves {'yes' if bs['is'] > sp['is'] and bs['oos'] > sp['oos'] else 'no'}, all three decades {'yes' if all(x > y for x, y in zip(bs['eras'], sp['eras'])) else 'no'}, plateau (neighbours within 0.3) {'yes' if v90['spread'] <= 0.003 else 'no'}, drawdown no deeper {'yes' if bs['dd'] >= sp['dd'] else 'no'}")
    print(f"  the same cell on the decade: {dbest['excess'] if dbest else float('nan'):+.2%} vs the price rule {vd['sp']['excess']:+.2%} → {'no worse' if dok else 'worse'}")
    print(f"  → {'DECISION PROPOSED' if ok and dok else 'NO — the price rule stays; B6 closed'}")


if __name__ == "__main__":
    main()
