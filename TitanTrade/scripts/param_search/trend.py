"""Trend and carry over a century (roadmap B3, Decision 086, 2026-10-30): is a trend-following premium real on the
operator's own eras, does it diversify *this* book, and would a sleeve of it pass the bar — judged without futures
data, on AQR's published factor series, before any instrument question.

Data (the Decision 072 library, ``external/aqr/``): the AQR Time Series Momentum factor (TSMOM and its commodity /
equity / fixed-income / currency legs, monthly, 1985-01 → 2026-05 — the real trend series, Moskowitz–Ooi–Pedersen);
the Century of Factor Premia (monthly, 1926-07 → 2026-02): "All Macro Momentum" (12-1 momentum *within* the macro
asset classes — equity indices, bonds, currencies, commodities — the century-long cousin of trend, cross-sectional
not time-series), "All Macro Carry", "All Macro Multi-style" and, for reference, "All asset classes Momentum". All
are long-short, gross of costs and fees, and scaled by AQR to a volatility target; here every sleeve candidate is
rescaled to a constant 10 % annualised volatility over its own sample (the volatility of an investable managed-futures
fund such as DBMF) and shown gross and net of 2 pp/yr (fee plus implementation). The book = ``books.century()`` /
``books.decade()`` compounded to calendar months (the daily path is exact; only the sleeve blend is monthly).

Pre-registered hypotheses (written before the first run):
  T1  the premium is real and old — TSMOM 1985 → has a gross Sharpe of 0.5 … 0.9, positive in both halves (split at
      the midpoint, 2005-09) and in every decade but at most one (the 2012–2019 "trend drought" is the candidate);
      the century macro-momentum composite 1926 → is positive in all four quarter-centuries with a Sharpe of 0.4 … 0.7;
  T2  crisis alpha, with the fast / slow distinction the book already knows: trend is *positive* in the slow bears
      (1973–74, 2000–02, 2008, 2022) and ≈ 0 or negative in the fast crash (2020, 1987) and in the rebound years
      (2009, 2023); its monthly correlation with the market is −0.15 … +0.10 over the full sample and with the book's
      active return −0.10 … +0.10 — a genuinely different bet;
  T3  the sleeve bar (Decision 067's, as for options 074, quality 075, gold 079): a trend sleeve of 10 / 20 % beside
      the book — taken proportionally, from the momentum sleeve, or from the dip sleeve, sitting outside the exposure
      rules (a long-short factor is not equity exposure) — must be *better in return in both halves and every era with
      the Sharpe no lower*, on the century (macro momentum) and on 1985 → (TSMOM). Expected: it FAILS the return leg
      the way every diversifier has — Sharpe +0.03 … +0.10, drawdown 3 … 8 points shallower, return 0.3 … 1.0 pp/yr
      lower gross and 0.5 … 1.3 lower net, because a 10 %-volatility long-short factor earns less than the two equity
      sleeves it displaces in a market that compounds at 10–11 %;
  T4  carry: the macro carry composite has a long-run premium (Sharpe 0.4 … 0.7) and is *negative* in the equity
      crashes it is supposed to hedge (2008, 2020: the carry crash), with a positive correlation to the market in bears
      — not a hedge for this book; the sleeve fails T3's bar by more than trend does;
  T5  the instrument question (only if T3 passes in both constructions): a managed-futures ETF (DBMF 2019 →, KMLM
      2020 →, not in the archive) fetched on the server and compared with TSMOM over the overlap. Expected: not reached.
Drop rule: a sleeve that fails T3 is recorded as knowledge, not built — "trend and carry" join Track D closed with
numbers; passing T3 in both constructions makes T5 the next pick on the operator's go, not a deploy. No placebo for a
held asset (carry, not a signal — Decision 079's rule); the crisis table is episodes, read as such. Nothing live changes.
Run from TitanTrade/: uv run --with numpy --with openpyxl python -I scripts/param_search/trend.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import books  # noqa: E402
import datasets  # noqa: E402

TARGET_VOL = 0.10
NET_COST = 0.02
ERAS_C = [("1927-07", "1949-12"), ("1950-01", "1974-12"), ("1975-01", "1999-12"), ("2000-01", "2026-12")]
EPISODES = [("1929–32", "1929-09", "1932-06"), ("1973–74", "1973-01", "1974-09"), ("1987", "1987-09", "1987-11"), ("2000–02", "2000-04", "2002-09"),
            ("2008", "2007-11", "2009-02"), ("2009 reb", "2009-03", "2010-02"), ("2020", "2020-02", "2020-03"), ("2022", "2022-01", "2022-09"), ("2023 reb", "2023-01", "2023-12")]


# ---- monthly helpers -----------------------------------------------------------------------------------------------

def to_monthly(dates, r):
    """Daily returns (for dates[1:]) compounded into calendar months → {YYYY-MM: r}."""
    out = {}
    for d, x in zip(dates[1:], r):
        ym = d[:7]; out[ym] = (1 + out.get(ym, 0.0)) * (1 + x) - 1
    return out


def align(*series):
    keys = sorted(set.intersection(*(set(s) for s in series)))
    return keys, [np.array([s[k] for k in keys]) for s in series]


def cagr(r):
    return float(np.prod(1 + r) ** (12 / len(r)) - 1) if len(r) else 0.0


def sharpe(r):
    return float(r.mean() / r.std() * np.sqrt(12)) if r.std() else 0.0


def maxdd(r):
    c = np.cumprod(1 + r); return float((c / np.maximum.accumulate(c) - 1).min())


def window(keys, a, b):
    return np.array([a <= k <= b for k in keys])


def score(keys, r, mkt, split, eras):
    """Excess CAGR vs the market, halves at ``split``, eras, drawdown, Sharpe, worst calendar year vs the market."""
    ks = next(i for i, k in enumerate(keys) if k >= split)
    years = sorted({k[:4] for k in keys})
    yr = [cagr(r[[k[:4] == y for k in keys]]) - cagr(mkt[[k[:4] == y for k in keys]]) for y in years if sum(k[:4] == y for k in keys) == 12]
    return {"excess": cagr(r) - cagr(mkt), "is": cagr(r[:ks]) - cagr(mkt[:ks]), "oos": cagr(r[ks:]) - cagr(mkt[ks:]),
            "dd": maxdd(r), "sharpe": sharpe(r), "worst_year": min(yr) if yr else 0.0,
            "eras": [cagr(r[window(keys, a, b)]) - cagr(mkt[window(keys, a, b)]) for a, b in eras] if eras else None}


def fmt(label, s):
    eras = (" | eras " + " ".join(f"{x:+5.1%}" for x in s["eras"])) if s["eras"] else ""
    return f"{label:58} {s['excess']:+6.2%} ({s['is']:+5.1%} / {s['oos']:+5.1%}) DD {s['dd']:6.1%} Sh {s['sharpe']:5.2f} worst {s['worst_year']:+6.1%}{eras}"


def factor_line(label, keys, f, mkt, split, eras):
    halves = f"{cagr(f[:next(i for i, k in enumerate(keys) if k >= split)]):+5.1%} / {cagr(f[next(i for i, k in enumerate(keys) if k >= split):]):+5.1%}"
    era_s = " ".join(f"{cagr(f[window(keys, a, b)]):+5.1%}" for a, b in eras) if eras else ""
    corr = float(np.corrcoef(f, mkt)[0, 1])
    return f"{label:44} ann {12 * f.mean():+6.2%} vol {f.std() * np.sqrt(12):5.1%} Sharpe {sharpe(f):4.2f} CAGR {cagr(f):+5.1%} | halves {halves} | DD {maxdd(f):6.1%} | corr mkt {corr:+.2f} | eras {era_s}"


def episodes(keys, series_by_label):
    print(f"{'':44}" + "".join(f"{e[0]:>10}" for e in EPISODES))
    for label, s in series_by_label.items():
        cells = []
        for _, a, b in EPISODES:
            w = window(keys, a, b)
            cells.append(f"{float(np.prod(1 + s[w]) - 1):+9.1%}" if w.any() else f"{'—':>9}")
        print(f"{label:44}" + " ".join(cells))


def scaled(f):
    return f * (TARGET_VOL / (f.std() * np.sqrt(12)))


def sleeve_table(title, parts, mkt_m, f_m, split, eras):
    """The book and the sleeve variants, scored against the market. ``parts`` are *exact* monthly series compounded from
    the daily book (the exposure rules applied day by day): ``book``, and the book with ``w`` taken out of the momentum
    sleeve (``mom10`` / ``mom20``) or out of the dip sleeve (``dip10`` / ``dip20``); the factor (rescaled to 10 % vol,
    gross and net) is blended in monthly."""
    keys, (book, mom10, mom20, dip10, dip20, mkt, f) = align(parts["book"], parts["mom10"], parts["mom20"], parts["dip10"], parts["dip20"], mkt_m, f_m)
    print(f"\n{title}: {keys[0]} → {keys[-1]} ({len(keys)} months)")
    print(f"{'book':58} {'excess':>6} {'(IS / OOS)':>15} {'DD':>9} {'Sharpe':>8} {'worst yr':>12}")
    base = score(keys, book, mkt, split, eras); print(fmt("the book (dip 40 / mom 60, min(insurance, shock))", base))
    print(fmt("the market", score(keys, mkt, mkt, split, eras)).replace("+0.00%", " 0.00%"))
    for net in (False, True):
        g = scaled(f) - (NET_COST / 12 if net else 0.0); tag = "net 2 pp" if net else "gross"
        for w, mom_w, dip_w in ((0.10, mom10, dip10), (0.20, mom20, dip20)):
            for label, rr in ((f"trend {w:.0%} proportional, outside the rules ({tag})", (1 - w) * book + w * g),
                              (f"trend {w:.0%} from the momentum sleeve ({tag})", mom_w + w * g),
                              (f"trend {w:.0%} from the dip sleeve ({tag})", dip_w + w * g)):
                s = score(keys, rr, mkt, split, eras)
                ok = s["excess"] > base["excess"] and s["is"] > base["is"] and s["oos"] > base["oos"] and s["sharpe"] >= base["sharpe"] and (not eras or all(x > y for x, y in zip(s["eras"], base["eras"])))
                print(fmt(label, s) + f"  gain {s['excess'] - base['excess']:+.2%}" + ("  ← passes the bar" if ok else ""))
    return base


def monthly_parts(d, r_dip, r_mom, e):
    """Exact monthly series of the book and of the book minus a 10 / 20 % slice of either sleeve, from the daily path."""
    return {"book": to_monthly(d, e * (0.4 * r_dip + 0.6 * r_mom)),
            "mom10": to_monthly(d, e * (0.4 * r_dip + 0.5 * r_mom)), "mom20": to_monthly(d, e * (0.4 * r_dip + 0.4 * r_mom)),
            "dip10": to_monthly(d, e * (0.3 * r_dip + 0.6 * r_mom)), "dip20": to_monthly(d, e * (0.2 * r_dip + 0.6 * r_mom))}


def main():
    tsm = datasets.aqr_monthly("Time-Series-Momentum-Factors-Monthly.xlsx", "TSMOM Factors", lambda row: len(row) > 1 and row[1] == "TSMOM")
    cen = datasets.aqr_monthly("Century-of-Factor-Premia-Monthly.xlsx", "Century of Factor Premia", lambda row: row[0] == "Date")
    # data hygiene: a monthly long-short factor return beyond ±50 % is a file artefact, not a month; cut the series there
    for name, series in (("TSMOM", tsm["TSMOM"]), ("All Macro Momentum", cen["All Macro Momentum"]), ("All Macro Carry", cen["All Macro Carry"])):
        bad = sorted(k for k, v in series.items() if abs(v) > 0.5)
        if bad:
            print(f"data check: {name} has {len(bad)} month(s) beyond ±50 % ({bad[:3]} …) — the series is cut before the first one")
            cut = bad[0]
            for s in (tsm if name == "TSMOM" else cen).values():
                for k in [k for k in s if k >= cut]:
                    del s[k]
    tail = sorted(tsm["TSMOM"])[-3:]
    print("data check: TSMOM last months", {k: round(tsm["TSMOM"][k], 4) for k in tail})

    # ---- the books, monthly — compounded from the daily path with the exposure rules applied day by day
    c = books.century(); cd = c["d"]
    e_c = books.exposure(c["bear"], books.shock_flags(c["mkt"], -0.07, 10, 20))
    parts_c = monthly_parts(cd, c["r"]["dip"], c["r"]["mom"], e_c); m_mkt = to_monthly(cd, c["r"]["mkt"])
    b = books.decade(etfs=("SPMO",)); dd_ = b["d"]
    e_d = books.exposure(b["bear"], books.shock_flags(b["spy"], -0.07, 10, 20))
    parts_d = monthly_parts(dd_, b["r"]["sec"], b["r"]["SPMO"], e_d); d_mkt = to_monthly(dd_, b["r"]["mkt"])

    # ---- T1: the premia alone
    print("\n=== T1 — the premia alone (monthly, gross, as published; AQR's own volatility scaling)")
    keys, (f_ts, f_cm, f_eq, f_fi, f_fx, mk) = align(tsm["TSMOM"], tsm["TSMOM^CM"], tsm["TSMOM^EQ"], tsm["TSMOM^FI"], tsm["TSMOM^FX"], m_mkt)
    mid = keys[len(keys) // 2]
    decades = [(f"{y}-01", f"{y + 9}-12") for y in range(1985, 2026, 10)]
    print(f"TSMOM {keys[0]} → {keys[-1]} ({len(keys)} months; halves at {mid}; eras = decades from 1985)")
    for label, f in (("TSMOM all assets", f_ts), ("  commodities", f_cm), ("  equity indices", f_eq), ("  fixed income", f_fi), ("  currencies", f_fx)):
        print(factor_line(label, keys, f, mk, mid, decades))
    print(factor_line("the market (French VW, same months)", keys, mk, mk, mid, decades))
    keys_c, (f_mm, f_mc, f_ms, f_am, mkc) = align(cen["All Macro Momentum"], cen["All Macro Carry"], cen["All Macro Multi-style"], cen["All asset classes Momentum"], m_mkt)
    print(f"\nCentury of Factor Premia {keys_c[0]} → {keys_c[-1]} ({len(keys_c)} months; halves at 1975-01; eras = quarter-centuries)")
    for label, f in (("All Macro Momentum (trend's century cousin)", f_mm), ("All Macro Carry", f_mc), ("All Macro Multi-style", f_ms), ("All asset classes Momentum", f_am)):
        print(factor_line(label, keys_c, f, mkc, "1975-01", ERAS_C))
    print(factor_line("the market (French VW, same months)", keys_c, mkc, mkc, "1975-01", ERAS_C))

    # ---- T2: crisis alpha and correlations
    print("\n=== T2 — the episodes (compounded over the window, the factor at 10 % volatility) and the correlations")
    kk, (bk, mm_, mc_, mkt_) = align(parts_c["book"], cen["All Macro Momentum"], cen["All Macro Carry"], m_mkt)
    episodes(kk, {"the market": mkt_, "the book": bk, "macro momentum (10 % vol)": scaled(mm_), "macro carry (10 % vol)": scaled(mc_)})
    kt, (bkt, ts_, mkt_t) = align(parts_c["book"], tsm["TSMOM"], m_mkt)
    episodes(kt, {"TSMOM (10 % vol), 1985 →": scaled(ts_)})
    print(f"\ncorrelations (monthly): macro momentum vs market {np.corrcoef(mm_, mkt_)[0, 1]:+.2f}, vs the book's active return {np.corrcoef(mm_, bk - mkt_)[0, 1]:+.2f}; "
          f"macro carry vs market {np.corrcoef(mc_, mkt_)[0, 1]:+.2f}, vs active {np.corrcoef(mc_, bk - mkt_)[0, 1]:+.2f}; "
          f"TSMOM vs market {np.corrcoef(ts_, mkt_t)[0, 1]:+.2f}, vs active {np.corrcoef(ts_, bkt - mkt_t)[0, 1]:+.2f}")
    bear_m = mkt_ < -0.05
    print(f"in the market's worst months (< −5 %, {bear_m.sum()} of {len(mkt_)}): market {mkt_[bear_m].mean():+.1%}/month, the book {bk[bear_m].mean():+.1%}, macro momentum {scaled(mm_)[bear_m].mean():+.1%}, "
          f"macro carry {scaled(mc_)[bear_m].mean():+.1%}; TSMOM in its own worst months ({(mkt_t < -0.05).sum()}): {scaled(ts_)[mkt_t < -0.05].mean():+.1%}")

    # ---- T3 / T4: the sleeve bar
    sleeve_table("=== T3 — the century book with a macro-momentum sleeve (split 1975-01, eras = quarter-centuries)", parts_c, m_mkt, cen["All Macro Momentum"], "1975-01", ERAS_C)
    sleeve_table("=== T4 — the century book with a macro-carry sleeve", parts_c, m_mkt, cen["All Macro Carry"], "1975-01", ERAS_C)
    k5 = sorted(set(parts_c["book"]) & set(tsm["TSMOM"])); mid5 = k5[len(k5) // 2]
    sleeve_table(f"=== T3 — the century book from 1985 with a TSMOM sleeve (the real trend series; split {mid5}, eras = decades)", parts_c, m_mkt, tsm["TSMOM"], mid5,
                 [(f"{y}-01", f"{y + 9}-12") for y in range(1985, 2026, 10)])
    sleeve_table("=== T3 — the ETF decade (sector dip 40 / SPMO 60) with a TSMOM sleeve (split 2022-01)", parts_d, d_mkt, tsm["TSMOM"], "2022-01", None)


if __name__ == "__main__":
    main()
