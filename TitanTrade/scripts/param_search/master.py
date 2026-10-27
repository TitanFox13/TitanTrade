"""Master search (operator request, 2026-10-27): every design discussed, in one grid, scored the same way.
Decade (investable, 2017 → 2026): dip book (live rule; sectors = hindsight-free, curated = flagged) × momentum vehicle
(MTUM / SPMO / both) × dip weight 0–100% × two-signal insurance (off / ×0.5 / to cash) × shock trigger (off + 4) ×
volatility target (off / 15% / 20%) × own-momentum switch. Century (French, 1927 → 2026): the same minus the vehicle
and universe choices. De-risked capital earns 0 (no T-bill), which biases *against* every de-risking rule.
Scores: excess CAGR vs the market, IS / OOS halves, max DD, Sharpe, worst calendar year vs market, rolling-3y hit rate
(decade) or min era excess (century). Read marginal effects first, leaderboards second, walk-forward third.
Run: uv run --with numpy python -I scripts/param_search/master.py"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import datasets  # noqa: E402
import fastbt  # noqa: E402

LIVE = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12,
            slot_pct=0.25, max_slots=3, insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=1.0)
WEIGHTS = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]
INS = {"off": None, "x0.5": 0.5, "cash": 0.0}
SHOCK = {"off": None, "-7/10/20/.5": (-0.07, 10, 20, 0.5), "-7/5/10/.5": (-0.07, 5, 10, 0.5), "-5/10/20/.5": (-0.05, 10, 20, 0.5), "-7/10/20/.25": (-0.07, 10, 20, 0.25)}
VOLT = {"off": None, "15%": 0.15, "20%": 0.20}


def cagr(c):
    return fastbt.metrics(c, [])["cagr"]


def prev(a):
    return np.concatenate([[np.nan], a[:-1]])


def sma_above(x, n=200):
    out = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        out[i] = 1.0 if x[i] > x[i - n:i].mean() else 0.0
    return out


def shock_flags(level, thr, look, hold):
    n = len(level) - 1
    ret = np.array([np.nan] * look + [level[i] / level[i - look] - 1 for i in range(look, n + 1)])[1:]
    ret = prev(ret); e = np.zeros(n, dtype=bool); k = 0
    for i in range(n):
        if ret[i] < thr: k = hold
        e[i] = k > 0; k = max(0, k - 1)
    return e


def roll_vol(r, n=20):
    out = np.full(len(r), np.nan)
    c = np.concatenate([[0.0], np.cumsum(r)]); c2 = np.concatenate([[0.0], np.cumsum(r * r)])
    for i in range(n, len(r)):
        m = (c[i] - c[i - n]) / n; v = (c2[i] - c2[i - n]) / n - m * m
        out[i] = np.sqrt(max(v, 0)) * np.sqrt(252)
    return prev(out)


def book(w_dip, r_dip, r_mom, r_mkt, bear, ins, shock, volt, own, mom12_pos):
    """Daily returns of the combined book. De-risked capital earns 0."""
    n = len(r_dip); w_mom = 1 - w_dip
    rm = np.where(mom12_pos, r_mom, r_mkt) if own else r_mom
    core = w_dip * r_dip + w_mom * rm
    e = np.ones(n)
    if ins is not None:
        e = np.where(bear, ins, e)
    if shock is not None:
        e = np.where(shock, np.minimum(e, shock_scale_holder[0]), e)
    if volt is not None:
        vol = volt_vol_holder[0]; target = np.clip(volt / np.where(np.isnan(vol), volt, vol), 0, 1); e = np.minimum(e, target)
    return e * core


shock_scale_holder = [0.5]; volt_vol_holder = [None]


def score(r, r_mkt, dates, split, eras=None):
    c = np.concatenate([[1.0], np.cumprod(1 + r)]); m = np.concatenate([[1.0], np.cumprod(1 + r_mkt)])
    mm, mk = fastbt.metrics(c, []), fastbt.metrics(m, [])
    ks = next(k for k, d in enumerate(dates) if d >= split)
    out = {"excess": mm["cagr"] - mk["cagr"], "is": cagr(c[:ks + 1]) - cagr(m[:ks + 1]), "oos": cagr(c[ks:]) - cagr(m[ks:]),
           "dd": mm["max_drawdown"], "sharpe": mm["sharpe"], "mkt_dd": mk["max_drawdown"], "mkt_sharpe": mk["sharpe"]}
    years = sorted({d[:4] for d in dates}); yr = []
    for y in years:
        kk = [k for k, d in enumerate(dates) if d[:4] == y]
        if len(kk) > 60: yr.append(c[kk[-1]] / c[kk[0]] - m[kk[-1]] / m[kk[0]])
    out["worst_year"] = min(yr); out["years_pos"] = sum(1 for x in yr if x > 0) / len(yr)
    if eras:
        ex = []
        for a, b in eras:
            ia = next(k for k, d in enumerate(dates) if d >= a); ib = max(k for k, d in enumerate(dates) if d <= b)
            ex.append(cagr(c[ia:ib + 1]) - cagr(m[ia:ib + 1]))
        out["era_min"] = min(ex); out["eras"] = ex
    else:
        wins = [(c[k] / c[k - 756]) ** (1 / 3) - (m[k] / m[k - 756]) ** (1 / 3) for k in range(756, len(c), 63)]
        out["roll3_pos"] = sum(1 for x in wins if x > 0) / len(wins)
    return out


def marginals(rows, dims, key="excess"):
    print(f"\n--- marginal effects on {key}: median over every other setting (and the share of cells with Sharpe above the market)")
    for dim in dims:
        vals = sorted({r[dim] for r in rows}, key=lambda v: (isinstance(v, str), v))
        line = f"  {dim:10}"
        for v in vals:
            sub = [r for r in rows if r[dim] == v]
            line += f" | {str(v):>12}: {np.median([r[key] for r in sub]):+5.1%} (Sh>mkt {np.mean([r['sharpe'] > r['mkt_sharpe'] for r in sub]):3.0%})"
        print(line)


def leaderboard(rows, title, key, filt, n=10, extra=()):
    print(f"\n--- {title}")
    cand = [r for r in rows if filt(r)]
    cand.sort(key=lambda r: -r[key])
    for r in cand[:n]:
        print("  " + " ".join(f"{d}={r[d]}" for d in r["dims"]) + f" | excess {r['excess']:+5.1%} (IS {r['is']:+5.1%} / OOS {r['oos']:+5.1%}) DD {r['dd']:6.1%} Sharpe {r['sharpe']:4.2f} worst yr {r['worst_year']:+5.1%}" + "".join(f" {k} {r[k]:+5.1%}" if isinstance(r[k], float) and k != "roll3_pos" else f" {k} {r[k]:.0%}" if k == "roll3_pos" else "" for k in extra))
    return cand


def walk_forward(rows, label, key_train, key_test):
    best = max(rows, key=lambda r: r[key_train])
    print(f"  {label}: picked " + " ".join(f"{d}={best[d]}" for d in best["dims"]) + f" (train {best[key_train]:+.1%}) → test {best[key_test]:+.1%}; median of all designs in test {np.median([r[key_test] for r in rows]):+.1%}")


def decade():
    cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index("2017-01-03")
    _, _, spy_above, breadth = cur.pre(90, 150, 200)
    SEC = fastbt.run(sec, LIVE, "2017-01-03", None)["_curve"]; CUR = fastbt.run(cur, LIVE, "2017-01-03", None)["_curve"]; d = dates[i0:]
    def etf(sym):
        v = datasets.alpaca(sym); return np.array([v.get(t, np.nan) for t in d])
    MT, SP = etf("MTUM"), etf("SPMO"); n = min(len(SEC), len(CUR), len(MT), len(SP)); d = d[:n]; spy = cur.spy[i0:i0 + n]
    r = {"sec": SEC[1:n] / SEC[:n - 1] - 1, "cur": CUR[1:n] / CUR[:n - 1] - 1, "MTUM": MT[1:n] / MT[:n - 1] - 1, "SPMO": SP[1:n] / SP[:n - 1] - 1, "mkt": spy[1:] / spy[:-1] - 1}
    r["both"] = 0.5 * r["MTUM"] + 0.5 * r["SPMO"]
    bear = (prev(spy_above[i0:i0 + n][1:]) == 0.0) & (prev(breadth[i0:i0 + n][1:]) < 0.5)
    shocks = {k: (None if v is None else shock_flags(spy, *v[:3])) for k, v in SHOCK.items()}
    volt_vol_holder[0] = roll_vol(r["mkt"])
    def mom12(rr):
        lvl = np.concatenate([[1.0], np.cumprod(1 + rr)]); return prev(np.array([np.nan] * 252 + [lvl[i - 21] / lvl[i - 252] - 1 for i in range(252, n)])[1:] if n > 252 else np.full(n - 1, np.nan)) > 0
    m12 = {k: mom12(r[k]) for k in ("MTUM", "SPMO", "both")}
    rows = []
    for uni, veh, w, ins, sh, vt, own in itertools.product(("sec", "cur"), ("MTUM", "SPMO", "both"), WEIGHTS, INS, SHOCK, VOLT, (False, True)):
        if w == 1.0 and (veh != "both" or own):   # pure dip book: vehicle and own-momentum irrelevant
            continue
        if w == 0.0 and uni != "sec":              # pure momentum: universe irrelevant
            continue
        shock_scale_holder[0] = SHOCK[sh][3] if SHOCK[sh] else 0.5
        rr = book(w, r[uni], r[veh], r["mkt"], bear, INS[ins], shocks[sh], VOLT[vt], own, m12[veh])
        s = score(rr, r["mkt"], d, "2022-01-01")
        s.update(universe=uni, vehicle=veh, w_dip=w, insurance=ins, shock=sh, voltarget=vt, ownmom=own, dims=("universe", "vehicle", "w_dip", "insurance", "shock", "voltarget", "ownmom"))
        rows.append(s)
    print(f"=== DECADE 2017-01 → {d[-1]}: {len(rows)} books (SPY: max DD {rows[0]['mkt_dd']:.1%}, Sharpe {rows[0]['mkt_sharpe']:.2f})")
    hf = [x for x in rows if x["universe"] == "sec"]
    marginals(hf, ("w_dip", "vehicle", "insurance", "shock", "voltarget", "ownmom"), "excess")
    marginals(hf, ("w_dip", "vehicle", "insurance", "shock", "voltarget", "ownmom"), "sharpe")
    ok = lambda x: x["is"] > 0 and x["oos"] > 0 and x["dd"] >= x["mkt_dd"]  # noqa: E731
    top_ret = leaderboard(hf, "top 10 by excess return — hindsight-free, positive in both halves, drawdown no worse than SPY", "excess", ok, extra=("roll3_pos",))
    top_sh = leaderboard(hf, "top 10 by Sharpe — hindsight-free, positive in both halves", "sharpe", lambda x: x["is"] > 0 and x["oos"] > 0, extra=("roll3_pos",))
    leaderboard([x for x in rows if x["universe"] == "cur"], "top 5 with the curated list (hindsight — for reference only)", "excess", ok, n=5, extra=("roll3_pos",))
    print("\n--- walk-forward of the selection (hindsight-free books only)")
    walk_forward(hf, "pick by IS excess → OOS", "is", "oos"); walk_forward(hf, "pick by OOS excess → IS", "oos", "is")
    print(f"  share of hindsight-free books positive in both halves: {np.mean([x['is'] > 0 and x['oos'] > 0 for x in hf]):.0%}; with DD no worse than SPY: {np.mean([ok(x) for x in hf]):.0%}")
    return top_ret, top_sh


def century():
    ind = datasets.load("F_french_49ind_1926"); mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
    r0 = fastbt.run(ind, LIVE, "1927-07-01", None); d = ind.dates[ind.dates.index(r0["start"]):]
    dip = r0["_curve"]; mk = r0["_spy_curve"]; hi = np.array([mom["Hi PRIOR"].get(x, np.nan) for x in d])
    r = {"dip": dip[1:] / dip[:-1] - 1, "mom": np.nan_to_num(hi[1:] / hi[:-1] - 1), "mkt": mk[1:] / mk[:-1] - 1}
    bear = prev(sma_above(mk)[1:]) == 0.0
    shocks = {k: (None if v is None else shock_flags(mk, *v[:3])) for k, v in SHOCK.items()}
    volt_vol_holder[0] = roll_vol(r["mkt"])
    lvl = np.concatenate([[1.0], np.cumprod(1 + r["mom"])]); n = len(lvl)
    m12 = prev(np.array([np.nan] * 252 + [lvl[i - 21] / lvl[i - 252] - 1 for i in range(252, n)])[1:]) > 0
    eras = [("1927-07-01", "1950-01-01"), ("1950-01-01", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]
    rows = []
    for w, ins, sh, vt, own in itertools.product(WEIGHTS, INS, SHOCK, VOLT, (False, True)):
        if w == 1.0 and own:
            continue
        shock_scale_holder[0] = SHOCK[sh][3] if SHOCK[sh] else 0.5
        rr = book(w, r["dip"], r["mom"], r["mkt"], bear, INS[ins], shocks[sh], VOLT[vt], own, m12)
        s = score(rr, r["mkt"], d, "1975-01-01", eras); s.update(w_dip=w, insurance=ins, shock=sh, voltarget=vt, ownmom=own, dims=("w_dip", "insurance", "shock", "voltarget", "ownmom")); rows.append(s)
    print(f"\n=== CENTURY 1927-07 → {d[-1]}: {len(rows)} books (market: max DD {rows[0]['mkt_dd']:.1%}, Sharpe {rows[0]['mkt_sharpe']:.2f}); insurance = SMA200-only here; split 1975")
    marginals(rows, ("w_dip", "insurance", "shock", "voltarget", "ownmom"), "excess")
    marginals(rows, ("w_dip", "insurance", "shock", "voltarget", "ownmom"), "sharpe")
    leaderboard(rows, "top 10 by excess — positive in all four quarter-centuries, drawdown no worse than the market", "excess", lambda x: x["era_min"] > 0 and x["dd"] >= x["mkt_dd"], extra=("era_min",))
    leaderboard(rows, "top 10 by Sharpe — positive in all four quarter-centuries", "sharpe", lambda x: x["era_min"] > 0, extra=("era_min",))
    print("\n--- walk-forward of the selection")
    walk_forward(rows, "pick by 1927-74 excess → 1975-2026", "is", "oos"); walk_forward(rows, "pick by 1975-2026 excess → 1927-74", "oos", "is")
    print(f"  share positive in all four eras: {np.mean([x['era_min'] > 0 for x in rows]):.0%}; and with DD no worse than market: {np.mean([x['era_min'] > 0 and x['dd'] >= x['mkt_dd'] for x in rows]):.0%}")
    return rows


def finalists():
    """The consensus region of the grid, decade and century, with crash-episode behaviour (book minus market, peak → trough)."""
    cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index("2017-01-03")
    _, _, spy_above, breadth = cur.pre(90, 150, 200)
    SEC = fastbt.run(sec, LIVE, "2017-01-03", None)["_curve"]; CUR = fastbt.run(cur, LIVE, "2017-01-03", None)["_curve"]; d = dates[i0:]
    def etf(sym):
        v = datasets.alpaca(sym); return np.array([v.get(t, np.nan) for t in d])
    MT, SP = etf("MTUM"), etf("SPMO"); n = min(len(SEC), len(CUR), len(MT), len(SP)); d = d[:n]; spy = cur.spy[i0:i0 + n]
    r = {"sec": SEC[1:n] / SEC[:n - 1] - 1, "cur": CUR[1:n] / CUR[:n - 1] - 1, "MTUM": MT[1:n] / MT[:n - 1] - 1, "SPMO": SP[1:n] / SP[:n - 1] - 1, "mkt": spy[1:] / spy[:-1] - 1}
    r["both"] = 0.5 * r["MTUM"] + 0.5 * r["SPMO"]
    bear = (prev(spy_above[i0:i0 + n][1:]) == 0.0) & (prev(breadth[i0:i0 + n][1:]) < 0.5)
    shock = shock_flags(spy, -0.07, 10, 20); volt_vol_holder[0] = roll_vol(r["mkt"]); shock_scale_holder[0] = 0.5
    eps = [("covid", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12"), ("2025", "2025-02-19", "2025-04-08"), ("2023yr", "2023-01-03", "2023-12-29")]
    def ep(rr):
        c = np.concatenate([[1.0], np.cumprod(1 + rr)]); m = np.concatenate([[1.0], np.cumprod(1 + r["mkt"])]); out = []
        for _, a, b in eps:
            ia = next(k for k, x in enumerate(d) if x >= a); ib = next(k for k, x in enumerate(d) if x >= b); out.append(c[ib] / c[ia] - m[ib] / m[ia])
        return out
    print("=== FINALISTS, decade (hindsight-free dip sleeve on sectors; 'cur' rows = your list, for reference)")
    print(f"{'design':52} {'excess':>7} {'IS':>6} {'OOS':>6} | {'DD':>6} | {'Sharpe':>6} | {'worst yr':>8} {'roll3':>5} | " + " ".join(f"{e[0]:>7}" for e in eps))
    cands = [("live today (dip only, ins x0.5)", "sec", "both", 1.0, 0.5, False), ("dip 50 / SPMO 50, ins x0.5, shock", "sec", "SPMO", 0.5, 0.5, True), ("dip 50 / both 50, ins x0.5, shock", "sec", "both", 0.5, 0.5, True),
             ("dip 40 / SPMO 60, ins x0.5, shock", "sec", "SPMO", 0.4, 0.5, True), ("dip 40 / both 60, ins x0.5, shock", "sec", "both", 0.4, 0.5, True), ("dip 30 / SPMO 70, ins x0.5, shock", "sec", "SPMO", 0.3, 0.5, True),
             ("dip 40 / SPMO 60, ins OFF, shock", "sec", "SPMO", 0.4, None, True), ("dip 50 / SPMO 50, ins OFF, shock", "sec", "SPMO", 0.5, None, True), ("dip 50 / SPMO 50, ins x0.5, NO shock", "sec", "SPMO", 0.5, 0.5, False),
             ("SPMO only, ins x0.5, shock", "sec", "SPMO", 0.0, 0.5, True), ("SPMO only, nothing", "sec", "SPMO", 0.0, None, False),
             ("cur: dip 50 / SPMO 50, ins x0.5, shock", "cur", "SPMO", 0.5, 0.5, True), ("cur: dip 40 / SPMO 60, ins x0.5, shock", "cur", "SPMO", 0.4, 0.5, True)]
    for label, uni, veh, w, ins, sh in cands:
        rr = book(w, r[uni], r[veh], r["mkt"], bear, ins, shock if sh else None, None, False, None)
        sc = score(rr, r["mkt"], d, "2022-01-01"); e = ep(rr)
        print(f"{label:52} {sc['excess']:+7.1%} {sc['is']:+6.1%} {sc['oos']:+6.1%} | {sc['dd']:6.1%} | {sc['sharpe']:6.2f} | {sc['worst_year']:+8.1%} {sc['roll3_pos']:5.0%} | " + " ".join(f"{x:+7.1%}" for x in e))
    print(f"{'SPY':52} {'':>7} {'':>6} {'':>6} | {sc['mkt_dd']:6.1%} | {sc['mkt_sharpe']:6.2f} |")
    # century
    ind = datasets.load("F_french_49ind_1926"); mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
    r0 = fastbt.run(ind, LIVE, "1927-07-01", None); fd = ind.dates[ind.dates.index(r0["start"]):]
    dip = r0["_curve"]; mk = r0["_spy_curve"]; hi = np.array([mom["Hi PRIOR"].get(x, np.nan) for x in fd])
    rc = {"dip": dip[1:] / dip[:-1] - 1, "mom": np.nan_to_num(hi[1:] / hi[:-1] - 1), "mkt": mk[1:] / mk[:-1] - 1}
    bearc = prev(sma_above(mk)[1:]) == 0.0; shockc = shock_flags(mk, -0.07, 10, 20); volt_vol_holder[0] = roll_vol(rc["mkt"])
    eras = [("1927-07-01", "1950-01-01"), ("1950-01-01", "1975-01-01"), ("1975-01-01", "2000-01-01"), ("2000-01-01", "2026-09-01")]
    epc = [("1929", "1929-09-03", "1932-06-01"), ("1973", "1973-01-11", "1974-10-03"), ("2008", "2007-10-09", "2009-03-09"), ("2009reb", "2009-03-09", "2010-03-09")]
    def epcf(rr):
        c = np.concatenate([[1.0], np.cumprod(1 + rr)]); m = np.concatenate([[1.0], np.cumprod(1 + rc["mkt"])]); out = []
        for _, a, b in epc:
            ia = next(k for k, x in enumerate(fd) if x >= a); ib = next(k for k, x in enumerate(fd) if x >= b); out.append(c[ib] / c[ia] - m[ib] / m[ia])
        return out
    print("\n=== FINALISTS, century (dip on industries + top momentum decile; insurance = SMA200-only)")
    print(f"{'design':44} {'excess':>7} {'1927-74':>8} {'1975-26':>8} | {'DD':>6} | {'Sharpe':>6} | {'eras +':>6} {'era min':>7} | " + " ".join(f"{e[0]:>7}" for e in epc))
    for label, w, ins, sh in (("dip only, ins x0.5 (≈ live)", 1.0, 0.5, False), ("dip 50 / mom 50, ins x0.5, shock", 0.5, 0.5, True), ("dip 40 / mom 60, ins x0.5, shock", 0.4, 0.5, True), ("dip 30 / mom 70, ins x0.5, shock", 0.3, 0.5, True),
                              ("dip 40 / mom 60, ins OFF, shock", 0.4, None, True), ("dip 50 / mom 50, ins x0.5, NO shock", 0.5, 0.5, False), ("mom only, ins x0.5, shock", 0.0, 0.5, True), ("mom only, nothing", 0.0, None, False)):
        rr = book(w, rc["dip"], rc["mom"], rc["mkt"], bearc, ins, shockc if sh else None, None, False, None)
        sc = score(rr, rc["mkt"], fd, "1975-01-01", eras); e = epcf(rr)
        print(f"{label:44} {sc['excess']:+7.1%} {sc['is']:+8.1%} {sc['oos']:+8.1%} | {sc['dd']:6.1%} | {sc['sharpe']:6.2f} | {sum(1 for x in sc['eras'] if x > 0):>5}/4 {sc['era_min']:+7.1%} | " + " ".join(f"{x:+7.1%}" for x in e))
    print(f"{'market':44} {'':>7} {'':>8} {'':>8} | {sc['mkt_dd']:6.1%} | {sc['mkt_sharpe']:6.2f} |")


if __name__ == "__main__":
    if "--finalists" in sys.argv:
        finalists()
    elif "--century" in sys.argv:
        century()
    elif "--decade" in sys.argv:
        decade()
    else:
        decade(); century()
