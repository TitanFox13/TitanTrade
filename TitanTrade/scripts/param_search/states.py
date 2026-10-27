"""State-conditional strategy — can N market types each pick their own strategy or parameters? (operator, 2026-10-27)

The operator's question: split history into up to ten kinds of market and let each kind choose its own book
(dip / momentum / index / cash mix and exposure) or its own dip parameters; does the choice hold on unseen data?

Pre-registered hypotheses, written before any result:
  H1  In-sample, every state scheme improves on the best single book — more states, more improvement — because a
      per-state choice fits noise (the placebo below shows how much a random labelling gains).
  H2  Out of sample the conditional choice does not beat the unconditional best book by more than the placebo does,
      in either direction of the walk-forward, decade or century. (Decision 067 addendum: slow regime rules add nothing.)
  H3  If anything survives it is the coarse live split (trend × breadth) choosing exposure, i.e. the insurance that exists.
Schemes: live two-signal (2 states); trend × breadth (4); drawdown × volatility (9); k-means on six standardised
features (trend distance, 12-month return, 20-day vol, distance from the 52-week high, breadth, momentum leadership),
K = 4 / 6 / 8 / 10 / 12, centroids fitted on the training half only. Actions: M1 the book mix — dip weight 0–100 % ×
exposure 0 / 0.5 / 1 (de-risked capital earns 0) + "hold the index"; M2 the dip rule's own parameters — 108 books
(dip 6–12 % × target 15–30 % × stop 8–16 % × hold 40–90 d) × exposure 0.5 / 1, as a mixture of pre-run books (the
position state does not carry across a switch; a first-order test — if nothing survives here, the path-exact version
cannot do better in expectation). Selection: per state, the action with the highest mean daily excess over the market
in the training half; test = the other half; both directions. Placebo: 20 block-shuffled labellings (63-day blocks)
per scheme — the gain a labelling with no information produces. Decade (sector dip book + SPMO, 2017 →, split 2022),
century (dip on 49 industries + top momentum decile, 1927 →, split 1975). Costs are inside the books; switching cost
on top is ignored (favours the conditional strategies). Run: uv run --with numpy python -I scripts/param_search/states.py
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402
import master  # noqa: E402

LIVE = master.LIVE
FEATS = ("trend", "ret12", "vol20", "dd52", "breadth", "lead")
PARAM_GRID = list(itertools.product((0.06, 0.08, 0.10, 0.12), (0.15, 0.20, 0.30), (0.08, 0.12, 0.16), (40, 60, 90)))


def sma(x, n):
    out = np.full(len(x), np.nan); c = np.concatenate([[0.0], np.cumsum(x)]); out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def features(level, sectors, lead_level):
    """Continuous state features from the close of each session (T rows); NaN until the history exists."""
    T = len(level); r = np.concatenate([[np.nan], level[1:] / level[:-1] - 1])
    s200 = sma(level, 200); trend = level / s200 - 1
    ret12 = np.full(T, np.nan); ret12[252:] = level[252:] / level[:-252] - 1
    vol = np.full(T, np.nan)
    for i in range(20, T):
        vol[i] = r[i - 19:i + 1].std() * np.sqrt(252)
    dd = np.full(T, np.nan)
    for i in range(252, T):
        dd[i] = level[i] / level[i - 251:i + 1].max() - 1
    K = sectors.shape[1]; above = np.full((T, K), np.nan)
    for k in range(K):
        col = sectors[:, k]; ok = ~np.isnan(col); v = col[ok]
        if len(v) > 200:
            a = np.full(len(v), np.nan); a[200:] = (v[200:] > sma(v, 200)[200:]).astype(float); above[ok, k] = a
    with np.errstate(all="ignore"):
        br = np.nanmean(above, axis=1)
    lead = np.full(T, np.nan); lead[252:] = (lead_level[252:] / lead_level[:-252] - 1) - ret12[252:]
    return {"trend": trend, "ret12": ret12, "vol20": vol, "dd52": dd, "breadth": br, "lead": lead}


def kmeans(X, K, seed=0, restarts=5, iters=100):
    rng = np.random.default_rng(seed); best = None
    for _ in range(restarts):
        C = X[rng.choice(len(X), K, replace=False)]
        for _ in range(iters):
            lab = np.argmin(((X[:, None, :] - C[None, :, :]) ** 2).sum(axis=2), axis=1)
            newC = np.array([X[lab == k].mean(axis=0) if (lab == k).any() else C[k] for k in range(K)])
            if np.allclose(newC, C):
                break
            C = newC
        inertia = ((X - C[lab]) ** 2).sum()
        if best is None or inertia < best[0]:
            best = (inertia, C)
    return best[1]


def assign(X, C):
    return np.argmin(((X[:, None, :] - C[None, :, :]) ** 2).sum(axis=2), axis=1)


def schemes(F, train):
    """Label sequences (one per scheme), each an int array over the return days; fitted on `train` (bool mask) only."""
    out = {}
    out["live two-signal (2)"] = ((F["trend"] < 0) & (F["breadth"] < 0.5)).astype(int)
    out["trend x breadth (4)"] = (F["trend"] < 0).astype(int) * 2 + (F["breadth"] < 0.5).astype(int)
    ddb = np.digitize(-F["dd52"], [0.03, 0.10]); vb = np.digitize(F["vol20"], [0.12, 0.20])
    out["drawdown x vol (9)"] = ddb * 3 + vb
    X = np.column_stack([F[k] for k in FEATS]); mu = X[train].mean(axis=0); sd = X[train].std(axis=0); Z = (X - mu) / sd
    for K in (4, 6, 8, 10, 12):
        C = kmeans(Z[train], K); out[f"k-means K={K}"] = assign(Z, C)
    return out


def placebo(labels, rng, block=63):
    n = len(labels); blocks = [labels[i:i + block] for i in range(0, n, block)]
    order = rng.permutation(len(blocks)); return np.concatenate([blocks[i] for i in order])[:n]


def cagr_excess(r, r_mkt):
    n = len(r); c = np.prod(1 + r); m = np.prod(1 + r_mkt)
    return (c ** (252 / n) - 1) - (m ** (252 / n) - 1)


def conditional(actions, labels, r_mkt, train, test):
    """Per-state best action on `train` (mean daily excess), applied on `test`; returns (test return series, choice map)."""
    ex = {a: rr - r_mkt for a, rr in actions.items()}
    best_all = max(actions, key=lambda a: ex[a][train].mean())
    choice = {}
    r = np.zeros(len(r_mkt))
    for s in np.unique(labels):
        m_tr = train & (labels == s)
        choice[s] = max(actions, key=lambda a: ex[a][m_tr].mean()) if m_tr.sum() >= 60 else best_all
        r[labels == s] = actions[choice[s]][labels == s]
    return r, choice, best_all


def evaluate(label, actions, labs, r_mkt, train, test, rng, n_placebo=20):
    r_c, choice, best = conditional(actions, labs, r_mkt, train, test)
    r_u = actions[best]
    u_tr, u_te = cagr_excess(r_u[train], r_mkt[train]), cagr_excess(r_u[test], r_mkt[test])
    c_tr, c_te = cagr_excess(r_c[train], r_mkt[train]), cagr_excess(r_c[test], r_mkt[test])
    gains = []
    for _ in range(n_placebo):
        pl = placebo(labs, rng); r_p, _, _ = conditional(actions, pl, r_mkt, train, test)
        gains.append((cagr_excess(r_p[train], r_mkt[train]) - u_tr, cagr_excess(r_p[test], r_mkt[test]) - u_te))
    g = np.array(gains)
    dd_c = fastbt.metrics(np.concatenate([[1.0], np.cumprod(1 + r_c[test])]), [])["max_drawdown"]
    dd_u = fastbt.metrics(np.concatenate([[1.0], np.cumprod(1 + r_u[test])]), [])["max_drawdown"]
    print(f"  {label:24} | best single {str(best):28} train {u_tr:+5.1%} test {u_te:+5.1%} | conditional train {c_tr:+5.1%} ({c_tr - u_tr:+5.1%}) test {c_te:+5.1%} (**{c_te - u_te:+5.1%}**) | "
          f"placebo gain train med {np.median(g[:, 0]):+5.1%} test med {np.median(g[:, 1]):+5.1%} [{np.percentile(g[:, 1], 10):+5.1%} … {np.percentile(g[:, 1], 90):+5.1%}] | test DD {dd_c:5.0%} vs {dd_u:5.0%}")
    return choice, c_te - u_te, np.median(g[:, 1])


def run_universe(name, dates, r, F, split, dip_books):
    n = len(r["mkt"]); ks = next(k for k, d in enumerate(dates) if d >= split)
    Fp = {k: master.prev(v[1:]) for k, v in F.items()}                  # state from the previous close, aligned to returns
    valid = np.all([~np.isnan(Fp[k]) for k in FEATS], axis=0)
    first = np.zeros(n, dtype=bool); first[:ks] = True; second = ~first
    # ---- M1 actions: dip weight × exposure, plus the index
    M1 = {}
    for w in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        for e in (0.0, 0.5, 1.0):
            M1[f"dip {w:.0%} e {e:.1f}"] = e * (w * r["dip"] + (1 - w) * r["mom"])
    M1["index"] = r["mkt"].copy()
    # ---- M2 actions: the dip parameter books × exposure
    M2 = {f"{k} e {e:.1f}": e * v for k, v in dip_books.items() for e in (0.5, 1.0)}
    rng = np.random.default_rng(1)
    for direction, train, test in (("train first half → test second", first & valid, second & valid), ("train second half → test first", second & valid, first & valid)):
        S = schemes({k: Fp[k] for k in FEATS}, train)
        for menu_name, menu in (("M1 book mix (19 actions)", M1), ("M2 dip parameters × exposure (216 actions)", M2)):
            print(f"\n=== {name}: {direction}; actions = {menu_name}; numbers = excess CAGR vs the market; gain = conditional − best single action")
            results = {}
            for sname, labs in S.items():
                labs = np.where(valid, labs, -1)
                results[sname] = evaluate(sname, menu, labs, r["mkt"], train, test, rng)
            if menu_name.startswith("M1") and direction.startswith("train first"):
                show_clusters(name, dates, S["k-means K=10"], Fp, r, M1, results["k-means K=10"][0], train, test, valid)
    return


def show_clusters(name, dates, labs, Fp, r, M1, choice, train, test, valid):
    print(f"\n--- {name}: the ten k-means market types (centroids fitted on the training half), what each chose and how it did")
    print(f"{'type':4} {'days':>6} {'trend':>6} {'ret12':>6} {'vol20':>6} {'dd52':>6} {'brdth':>6} {'lead':>6} | {'mkt/yr train':>12} {'test':>6} | {'chosen action':20} {'train excess':>12} {'test':>6} | {'dip100 test':>11} {'mom100 test':>11} example dates")
    for s in range(10):
        m = (labs == s) & valid
        if m.sum() < 60:
            continue
        f = {k: np.nanmean(Fp[k][m]) for k in FEATS}
        def ann(x, mask):
            return (np.prod(1 + x[mask]) ** (252 / max(mask.sum(), 1)) - 1) if mask.sum() else float("nan")
        a = choice.get(s, "n/a"); ra = M1.get(a, r["mkt"])
        idx = np.nonzero(m)[0]; ex = []; last = -999
        for i in idx:
            if i - last > 250:
                ex.append(dates[i + 1][:7]); last = i
        print(f"{s:4d} {m.sum():6d} {f['trend']:+6.1%} {f['ret12']:+6.1%} {f['vol20']:6.1%} {f['dd52']:+6.1%} {f['breadth']:6.0%} {f['lead']:+6.1%} | {ann(r['mkt'], m & train):+12.1%} {ann(r['mkt'], m & test):+6.1%} | {a:20} "
              f"{ann(ra, m & train) - ann(r['mkt'], m & train):+12.1%} {ann(ra, m & test) - ann(r['mkt'], m & test):+6.1%} | {ann(M1['dip 100% e 1.0'], m & test) - ann(r['mkt'], m & test):+11.1%} {ann(M1['dip 0% e 1.0'], m & test) - ann(r['mkt'], m & test):+11.1%} {' '.join(ex[:8])}")


def dip_param_books(mkt, start):
    books = {}
    for dp, tp, st, hd in PARAM_GRID:
        p = dict(LIVE, dip_pct=dp, tp_pct=tp, stop_pct=st, max_hold_days=hd)
        c = fastbt.run(mkt, p, start, None)["_curve"]; books[f"d{dp:.0%} t{tp:.0%} s{st:.0%} h{hd}"] = c[1:] / c[:-1] - 1
    return books


def main():
    # ---- decade
    cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index("2017-01-03")
    SEC = fastbt.run(sec, LIVE, "2017-01-03", None)["_curve"]; d = dates[i0:]
    v = datasets.alpaca("SPMO"); SP = np.array([v.get(t, np.nan) for t in d]); n = min(len(SEC), len(SP)); d = d[:n]; spy = cur.spy[i0:i0 + n]
    r = {"dip": SEC[1:n] / SEC[:n - 1] - 1, "mom": SP[1:n] / SP[:n - 1] - 1, "mkt": spy[1:] / spy[:-1] - 1}
    full_sp = np.array([v.get(t, np.nan) for t in dates]); full_sp = np.where(np.isnan(full_sp), np.nanmean(full_sp), full_sp)
    Ffull = features(cur.spy, sec.sectors, full_sp); F = {k: x[i0:i0 + n] for k, x in Ffull.items()}
    books = {k: b[:n - 1] for k, b in dip_param_books(sec, "2017-01-03").items()}
    print(f"DECADE 2017-01 → {d[-1]}: sector dip book (raw) + SPMO; {len(books)} parameter books pre-run")
    run_universe("decade", d, r, F, "2022-01-01", books)
    # ---- century
    ind = datasets.load("F_french_49ind_1926"); mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
    r0 = fastbt.run(ind, LIVE, "1927-07-01", None); fd = ind.dates[ind.dates.index(r0["start"]):]
    dip = r0["_curve"]; mk = r0["_spy_curve"]; hi = np.array([mom["Hi PRIOR"].get(x, np.nan) for x in fd])
    hi_f = hi.copy()
    for i in range(1, len(hi_f)):
        if np.isnan(hi_f[i]): hi_f[i] = hi_f[i - 1]
    rc = {"dip": dip[1:] / dip[:-1] - 1, "mom": np.nan_to_num(hi[1:] / hi[:-1] - 1), "mkt": mk[1:] / mk[:-1] - 1}
    j0 = ind.dates.index(fd[0]); Fc = features(mk, ind.sectors[j0:j0 + len(fd)], hi_f)
    booksc = {k: b[:len(fd) - 1] for k, b in dip_param_books(ind, "1927-07-01").items()}
    print(f"\n\nCENTURY 1927-07 → {fd[-1]}: dip on 49 industries (raw) + top momentum decile; {len(booksc)} parameter books pre-run")
    run_universe("century", fd, rc, Fc, "1975-01-01", booksc)


if __name__ == "__main__" and "--momcrash" not in sys.argv:
    main()


def momcrash():
    """The one state the clusters single out — the rebound after a crash, where momentum collapses (Daniel–Moskowitz):
    simple ex-ante rules that move the momentum sleeve into the index, on the recommended book, decade and century, both halves.
      G1  market 24-month return < 0 (the published bear-state flag)
      G2  G1 and 20-day vol > 20 %
      G3  market 12-month return < 0
      G4  market up > 20 % from its 252-day low while still > 10 % below its 252-day high (the rebound itself)
      G5  momentum leadership (sleeve 12m − market 12m) < −10 %
    Pre-registered expectation: G1/G3 are the slow bear flags already shown to add nothing; G4 may catch 2009 and 1933 at the
    cost of 2020-type V-rebounds where momentum led; nothing both halves, both eras."""
    sets = []
    cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index("2017-01-03")
    _, _, spy_above, breadth = cur.pre(90, 150, 200)
    SEC = fastbt.run(sec, LIVE, "2017-01-03", None)["_curve"]; d = dates[i0:]
    v = datasets.alpaca("SPMO"); SP = np.array([v.get(t, np.nan) for t in d]); n = min(len(SEC), len(SP)); d = d[:n]; spy = cur.spy[i0:i0 + n]
    bear = (master.prev(spy_above[i0:i0 + n][1:]) == 0.0) & (master.prev(breadth[i0:i0 + n][1:]) < 0.5)
    sets.append(("decade", d, cur.spy, i0, {"dip": SEC[1:n] / SEC[:n - 1] - 1, "mom": SP[1:n] / SP[:n - 1] - 1, "mkt": spy[1:] / spy[:-1] - 1}, bear, "2022-01-01", None))
    ind = datasets.load("F_french_49ind_1926"); mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
    r0 = fastbt.run(ind, LIVE, "1927-07-01", None); fd = ind.dates[ind.dates.index(r0["start"]):]
    dip = r0["_curve"]; mk = r0["_spy_curve"]; hi = np.array([mom["Hi PRIOR"].get(x, np.nan) for x in fd])
    sets.append(("century", fd, mk, 0, {"dip": dip[1:] / dip[:-1] - 1, "mom": np.nan_to_num(hi[1:] / hi[:-1] - 1), "mkt": mk[1:] / mk[:-1] - 1}, master.prev(master.sma_above(mk)[1:]) == 0.0, "1975-01-01",
                 [("1927-07-01", "1950-01-01"), ("1950-01-01", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]))
    for name, dd, level_full, off, r, bear, split, eras in sets:
        n = len(r["mkt"]); T = n + 1; lvl = level_full[off:off + T]
        def back(k):   # trailing k-session return of the level, aligned to returns and lagged one session
            x = np.full(T, np.nan); x[k:] = lvl[k:] / lvl[:-k] - 1; return master.prev(x[1:])
        r24, r12 = back(504), back(252)
        lo = np.full(T, np.nan); hi_ = np.full(T, np.nan)
        for i in range(252, T):
            lo[i] = lvl[i] / lvl[i - 251:i + 1].min() - 1; hi_[i] = lvl[i] / lvl[i - 251:i + 1].max() - 1
        lo, hi_ = master.prev(lo[1:]), master.prev(hi_[1:])
        vol = master.roll_vol(r["mkt"])
        moml = np.concatenate([[1.0], np.cumprod(1 + r["mom"])]); lead = master.prev((np.concatenate([[np.nan] * 252, moml[252:] / moml[:-252] - 1]) - np.concatenate([[np.nan] * 252, lvl[252:] / lvl[:-252] - 1]))[1:])
        shock = master.shock_flags(lvl, -0.07, 10, 20)
        guards = {"none (recommended book)": np.zeros(n, dtype=bool), "G1 market 24m < 0": r24 < 0, "G2 G1 and vol20 > 20%": (r24 < 0) & (vol > 0.20),
                  "G3 market 12m < 0": r12 < 0, "G4 rebound: >20% off the low, >10% below the high": (lo > 0.20) & (hi_ < -0.10), "G5 leadership < -10%": lead < -0.10}
        print(f"\n=== momentum-crash guards on the recommended book (dip 40 / mom 60, ins x0.5, shock) — {name}; guard on → the sleeve holds the index")
        print(f"{'guard':50} {'excess':>7} {'IS':>6} {'OOS':>6} | {'DD':>6} {'Sharpe':>6} | {'worst yr':>8} {'eras+/roll3':>11} | time on | 2009-type rebound (book − market, 12 m from the low)")
        for g, flag in guards.items():
            flag = np.nan_to_num(flag.astype(float)).astype(bool)
            rm = np.where(flag, r["mkt"], r["mom"])
            rr = master.book(0.4, r["dip"], rm, r["mkt"], bear, 0.5, shock, None, False, None)
            s = master.score(rr, r["mkt"], dd, split, eras)
            c = np.concatenate([[1.0], np.cumprod(1 + rr)]); m = np.concatenate([[1.0], np.cumprod(1 + r["mkt"])])
            eps = [("2009-03-09", "2010-03-09"), ("1932-06-01", "1933-06-01"), ("2020-03-23", "2021-03-23")] if name == "century" else [("2020-03-23", "2021-03-23"), ("2022-10-12", "2023-10-12"), ("2025-04-08", "2026-04-08")]
            ep = []
            for a, b in eps:
                if a < dd[0] or b > dd[-1]:
                    ep.append(float("nan")); continue
                ia = next(k for k, x in enumerate(dd) if x >= a); ib = next(k for k, x in enumerate(dd) if x >= b); ep.append(c[ib] / c[ia] - m[ib] / m[ia])
            tail = f"{sum(1 for x in s['eras'] if x > 0)}/4 min {s['era_min']:+5.1%}" if eras else f"roll3 {s['roll3_pos']:3.0%}"
            print(f"{g:50} {s['excess']:+7.1%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['dd']:6.1%} {s['sharpe']:6.2f} | {s['worst_year']:+8.1%} {tail:>11} | {np.mean(flag):5.0%}   | " + " ".join(f"{x:+6.1%}" for x in ep) + ("  (2009, 1932, 2020)" if name == "century" else "  (2020, 2022, 2025)"))


if __name__ == "__main__" and "--momcrash" in sys.argv:
    momcrash()
