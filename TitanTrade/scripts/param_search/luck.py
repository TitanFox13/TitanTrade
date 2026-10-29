"""The luck meter (Decision 068 addendum, 2026-10-29; brainstorm candidate 3).

How much of the recommended book's edge is selection luck? The master search scored 4,140 decade books (2,070 of them
hindsight-free) and 765 century books and picked a family. Four statistics, computed on the *active* return (book minus
the market, daily):
  1. Deflated Sharpe ratio (Bailey & López de Prado 2014): the probability that the chosen book's Sharpe exceeds the
     Sharpe the best of N unskilled trials would show, given the trials' Sharpe dispersion, the sample length and the
     return's skew and kurtosis. N = the pool the family was chosen from and N_eff = the pool's effective number of
     independent trials (participation ratio of the trial-correlation eigenvalues — the grid cells are near-copies).
  2. Probability of backtest overfitting (Bailey, Borwein, López de Prado & Zhu 2014, CSCV): the pool's returns in
     S = 16 blocks; for each of the 12,870 half/half splits, the book best in-sample is ranked out-of-sample; PBO =
     the share of splits where it ranks below the median. Also the IS → OOS slope and the chance the IS-best loses OOS.
  3. A stationary block bootstrap (Politis–Romano, mean block 63 sessions) of the (book, market) pair: the 5–95 % band
     of the excess CAGR and of the Sharpe difference.
  4. Power of the go/stop rule: at the measured tracking error, the years needed for the book's excess to reach
     t = 2, and the chance a true +1.4 pp/yr book fails the "≥ SPY − 2 pp/yr" leg over one quarter and one year.
Pre-registered hypotheses, written before any result:
  L1  decade: DSR ≈ 0.5 — the decade alone cannot tell the book from SPY after the search; PBO > 0.3;
  L2  century: DSR > 0.95, PBO < 0.2 — the century is where the evidence is;
  L3  the decade's bootstrap band for the excess straddles 0, the century's does not;
  L4  the return leg of the go/stop rule needs more than 10 years at this tracking error; the quarter-long test has
      less than a 60 % chance of passing even when the book is as good as the backtest.
Run: uv run --with numpy python -I scripts/param_search/luck.py   (--pbo-blocks N to change S)
"""
import itertools
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402

EULER = 0.5772156649


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def nppf(p):
    lo, hi = -12.0, 12.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if ncdf(mid) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def sharpe_daily(x):
    s = x.std(ddof=1)
    return x.mean() / s if s > 0 else 0.0


def pool(name, dd, lvl, r, bear, split, eras):
    """Every hindsight-free book of the master grid as a daily active-return row; returns (keys, matrix N × T, index of the recommended cell)."""
    n = len(r["mkt"]); core_mkt = r["mkt"]
    shocks = {k: (None if v is None else master.shock_flags(lvl, *v[:3])) for k, v in master.SHOCK.items()}
    master.volt_vol_holder[0] = master.roll_vol(core_mkt)
    vehicles = {"SPMO": r["mom"]}
    if name == "decade":   # the master search chose among three vehicles; the pool must be the pool the family was picked from
        v = datasets.alpaca("MTUM"); mt = np.array([v.get(t, np.nan) for t in dd]); vehicles["MTUM"] = mt[1:] / mt[:-1] - 1
        vehicles["both"] = 0.5 * (vehicles["MTUM"] + vehicles["SPMO"])
    m12 = {}
    for k, rm in vehicles.items():
        lvl_m = np.concatenate([[1.0], np.cumprod(1 + rm)])
        m12[k] = master.prev(np.array([np.nan] * 252 + [lvl_m[i - 21] / lvl_m[i - 252] - 1 for i in range(252, n + 1)])[1:]) > 0
    keys, rows = [], []
    for veh, w, ins, sh, vt, own in itertools.product(vehicles, master.WEIGHTS, master.INS, master.SHOCK, master.VOLT, (False, True)):
        if w == 1.0 and (veh != list(vehicles)[-1] or own): continue   # pure dip book: vehicle and own-momentum irrelevant
        master.shock_scale_holder[0] = master.SHOCK[sh][3] if master.SHOCK[sh] else 0.5
        rr = master.book(w, r["dip"], vehicles[veh], core_mkt, bear, master.INS[ins], shocks[sh], master.VOLT[vt], own, m12[veh])
        keys.append((veh, w, ins, sh, vt, own)); rows.append(rr - core_mkt)
    M = np.array(rows)
    rec = keys.index(("SPMO", 0.4, "x0.5", "-7/10/20/.5", "off", False))
    return keys, M, rec


def dsr(active, trial_sharpes, N):
    T = len(active); sr = sharpe_daily(active)
    z = (active - active.mean()) / active.std(ddof=1); g3 = float(np.mean(z ** 3)); g4 = float(np.mean(z ** 4))
    V = float(np.var(trial_sharpes, ddof=1))
    sr0 = math.sqrt(V) * ((1 - EULER) * nppf(1 - 1 / N) + EULER * nppf(1 - 1 / (N * math.e)))
    stat = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr * sr)
    return ncdf(stat), sr, sr0, g3, g4


def n_effective(M):
    C = np.corrcoef(M); lam = np.linalg.eigvalsh(C); lam = lam[lam > 0]
    return float(lam.sum() ** 2 / (lam ** 2).sum())


def pbo(M, S=16, chunk=2000):
    N, T = M.shape; edges = np.linspace(0, T, S + 1).astype(int)
    s1 = np.array([M[:, a:b].sum(1) for a, b in zip(edges[:-1], edges[1:])]); s2 = np.array([(M[:, a:b] ** 2).sum(1) for a, b in zip(edges[:-1], edges[1:])])
    cnt = np.diff(edges).astype(float)
    combos = np.array(list(itertools.combinations(range(S), S // 2)))
    lam, is_sr, oos_sr, oos_loss = [], [], [], []
    for c0 in range(0, len(combos), chunk):
        cc = combos[c0:c0 + chunk]; mask = np.zeros((len(cc), S)); mask[np.arange(len(cc))[:, None], cc] = 1.0
        def sr_of(m):
            n_ = m @ cnt; mu = (m @ s1) / n_[:, None]; var = (m @ s2) / n_[:, None] - mu ** 2
            return mu / np.sqrt(np.maximum(var, 1e-18))
        tr, te = sr_of(mask), sr_of(1 - mask)
        best = tr.argmax(1); te_best = te[np.arange(len(cc)), best]
        rank = (te < te_best[:, None]).mean(1); w = np.clip(rank, 1 / (N + 1), N / (N + 1))
        lam.extend(np.log(w / (1 - w))); is_sr.extend(tr[np.arange(len(cc)), best]); oos_sr.extend(te_best); oos_loss.extend(te_best < 0)
    lam, is_sr, oos_sr = np.array(lam), np.array(is_sr), np.array(oos_sr)
    slope = np.polyfit(is_sr, oos_sr, 1)[0]
    return float(np.mean(lam < 0)), float(slope), float(np.mean(oos_loss)), float(np.mean(oos_sr) * math.sqrt(252)), float(np.mean(is_sr) * math.sqrt(252))


def stationary_bootstrap(rb, rm, B=1000, mean_block=63, seed=3):
    rng = np.random.default_rng(seed); T = len(rb); p = 1 / mean_block; ex, dsh = [], []
    for _ in range(B):
        idx = np.empty(T, dtype=int); i = rng.integers(T)
        for t in range(T):
            if t == 0 or rng.random() < p: i = rng.integers(T)
            else: i = (i + 1) % T
            idx[t] = i
        b, m = rb[idx], rm[idx]
        cb = np.prod(1 + b) ** (252 / T) - 1; cm = np.prod(1 + m) ** (252 / T) - 1
        ex.append(cb - cm); dsh.append((sharpe_daily(b) - sharpe_daily(m)) * math.sqrt(252))
    ex, dsh = np.array(ex), np.array(dsh)
    return np.percentile(ex, [5, 50, 95]), np.percentile(dsh, [5, 50, 95]), float(np.mean(ex > 0))


def main():
    S = int(sys.argv[sys.argv.index("--pbo-blocks") + 1]) if "--pbo-blocks" in sys.argv else 16
    for name, dd, lvl, r, bear, split, eras in carry.sets():
        keys, M, rec = pool(name, dd, lvl, r, bear, split, eras)
        active = M[rec]; book_r = active + r["mkt"]; N = len(keys); T = len(active)
        sb = master.score(book_r, r["mkt"], dd, split, eras)
        te = active.std(ddof=1) * math.sqrt(252); mu = active.mean() * 252; t_plain = mu / te * math.sqrt(T / 252)
        trial_sr = np.array([sharpe_daily(x) for x in M]); neff = n_effective(M)
        print(f"\n=== the luck meter — {name} {dd[0]} → {dd[-1]}: recommended book excess {sb['excess']:+.2%}/yr (arithmetic {mu:+.2%}), tracking error {te:.1%}/yr, "
              f"information ratio {mu / te:.2f}, t = {t_plain:.2f} on {T / 252:.0f} years (Harvey–Liu hurdle t > 3)")
        print(f"  pool: {N} hindsight-free books, effective independent trials {neff:.1f}; trial Sharpe (active, annualised) median {np.median(trial_sr) * math.sqrt(252):+.2f}, "
              f"sd {trial_sr.std(ddof=1) * math.sqrt(252):.2f}, best {trial_sr.max() * math.sqrt(252):+.2f}; the recommended book ranks {int((trial_sr > trial_sr[rec]).sum()) + 1} of {N}")
        for label, n_ in (("N = 1 (no search)", 1.0000001), (f"N = {N} (every cell)", N), (f"N_eff = {neff:.0f}", max(neff, 1.0000001))):
            p, sr, sr0, g3, g4 = dsr(active, trial_sr, n_)
            print(f"  deflated Sharpe, {label:28}: P(skill) = {p:5.1%}  (active Sharpe {sr * math.sqrt(252):+.2f}/yr vs the expected best of {n_:.0f} null trials {sr0 * math.sqrt(252):+.2f}; skew {g3:+.2f}, kurtosis {g4:.1f})")
        p_, slope, loss, oos_m, is_m = pbo(M, S)
        print(f"  probability of backtest overfitting (CSCV, S = {S}): {p_:.0%}; IS-best's OOS Sharpe mean {oos_m:+.2f} vs IS {is_m:+.2f} (slope {slope:+.2f}); IS-best loses OOS in {loss:.0%} of splits")
        ex, dsh, pos = stationary_bootstrap(book_r, r["mkt"], B=1000 if name == "decade" else 400)
        print(f"  block bootstrap (1000/400 draws, 63-session blocks): excess CAGR 5 % {ex[0]:+.1%} / median {ex[1]:+.1%} / 95 % {ex[2]:+.1%}, P(excess > 0) = {pos:.0%}; Sharpe difference 5 % {dsh[0]:+.2f} / median {dsh[1]:+.2f} / 95 % {dsh[2]:+.2f}")
        for mu_true in (0.014, 0.036):
            yrs = (2 * te / mu_true) ** 2
            q_fail = ncdf((-0.02 - mu_true) / (te / math.sqrt(0.25))); y_fail = ncdf((-0.02 - mu_true) / te)
            q_beat = 1 - ncdf((0 - mu_true) / (te / math.sqrt(0.25)))
            print(f"  go/stop power at a true {mu_true:+.1%}/yr: years to t = 2 → {yrs:.0f}; one quarter: fails '≥ SPY − 2 pp/yr' {q_fail:.0%} of the time, shows ≥ SPY only {q_beat:.0%}; one year: fails {y_fail:.0%}")
        # the drawdown leg: SPY drawdowns ≥ 10 % and the book's drawdown inside each
        m = np.concatenate([[1.0], np.cumprod(1 + r["mkt"])]); c = np.concatenate([[1.0], np.cumprod(1 + book_r)])
        peak = np.maximum.accumulate(m); ddm = m / peak - 1; eps = []; i = 0
        while i < len(ddm):
            if ddm[i] < -0.10:
                j = i
                while j < len(ddm) and ddm[j] < 0: j += 1
                lo = i + int(np.argmin(ddm[i:j])); s0 = int(np.nonzero(ddm[:i] == 0)[0].max()); eps.append((dd[s0], dd[min(lo, len(dd) - 1)], ddm[lo], c[lo] / c[s0] - 1)); i = j
            else: i += 1
        ok = sum(1 for e in eps if e[3] >= 0.7 * e[2])
        print(f"  drawdown leg: {len(eps)} SPY drawdowns ≥ 10 %; the book's fall ≤ 0.7 × SPY's in {ok} of {len(eps)}" + (": " + "; ".join(f"{a[:7]}→{b[:7]} SPY {x:.0%} book {y:.0%}" for a, b, x, y in eps) if len(eps) <= 8 else ""))


if __name__ == "__main__":
    main()
