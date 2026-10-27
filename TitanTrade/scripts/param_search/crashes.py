"""Every recorded crash, peak → +3 years, for market / momentum / dip book / 50-50 blend (Decision 067 crash page).
Writes data/param_search/crashes.json and prints the depth-and-recovery tables. Run: uv run --with numpy python -I scripts/param_search/crashes.py"""
import sys, os, json; sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "param_search"))
import numpy as np, fastbt, datasets
LIVE = dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12, slot_pct=0.25, max_slots=3, insurance_sma_days=200, insurance_breadth=0.5, insurance_scale=0.5)
out = {"episodes": []}

def episode(name, dates, books, peak, years=3):
    ip = dates.index(next(d for d in dates if d >= peak)); iend = min(len(dates) - 1, ip + 252 * years)
    mkt = books["market"]; it = ip + int(np.argmin(mkt[ip:iend + 1]))
    i2 = min(len(dates) - 1, ip + 504)
    row = {"name": name, "peak": dates[ip], "trough": dates[it], "books": {}}
    for k, c in books.items():
        seg = c[ip:iend + 1] / c[ip]; dd = float((seg / np.maximum.accumulate(seg) - 1).min())
        row["books"][k] = {"at_trough": float(c[it] / c[ip] - 1), "max_dd": dd, "after_2y": float(c[i2] / c[ip] - 1), "after_3y": float(c[iend] / c[ip] - 1)}
    # weekly path for the chart, 3 years from the peak
    row["path"] = {"dates": dates[ip:iend + 1:5], **{k: [round(float(x), 4) for x in (c[ip:iend + 1:5] / c[ip])] for k, c in books.items()}}
    return row

# --- century (French): market, top momentum decile, dip on 49 industries, 50/50
ind = datasets.load("F_french_49ind_1926"); mom = datasets.french_levels("10_Portfolios_Prior_12_2_Daily.csv")
r = fastbt.run(ind, LIVE, "1927-07-01", None); d = ind.dates[ind.dates.index(r["start"]):]
dipc = r["_curve"] / r["_curve"][0]; mk = r["_spy_curve"] / r["_spy_curve"][0]
hi = np.array([mom["Hi PRIOR"].get(x, np.nan) for x in d]); hi = np.where(np.isnan(hi), np.nan, hi); hi = hi / hi[0]
rd = dipc[1:] / dipc[:-1] - 1; rh = np.nan_to_num(hi[1:] / hi[:-1] - 1); blend = np.concatenate([[1.0], np.cumprod(1 + 0.5 * rd + 0.5 * rh)])
C = {"market": mk, "momentum": hi, "dip": dipc, "blend": blend}
for name, peak in (("1929 crash (century data)", "1929-09-03"), ("1937 bear (century data)", "1937-03-10"), ("1973-74 bear (century data)", "1973-01-11"), ("1987 crash (century data)", "1987-08-25"),
                   ("2000 dot-com, election year (century data)", "2000-03-24"), ("2008 financial crisis, election year (century data)", "2007-10-09"), ("2020 covid, election year (century data)", "2020-02-19"), ("2022 bear (century data)", "2022-01-03")):
    out["episodes"].append(episode(name, d, C, peak))

# --- decade (Alpaca, investable): SPY, MTUM/SPMO 50/50 guarded, sector-dip book, curated-dip book, 50/50 sector+ETFs
cur = datasets.load("A_alpaca_names_2016"); sec = datasets.load("D_alpaca_sectors_2016"); dates = cur.dates; i0 = dates.index("2017-01-03")
_, _, spy_above, breadth = cur.pre(90, 150, 200)
CUR = fastbt.run(cur, LIVE, "2017-01-03", None)["_curve"]; SEC = fastbt.run(sec, LIVE, "2017-01-03", None)["_curve"]
dd_ = dates[i0:]; spy = cur.spy[i0:]
def etf(sym):
    v = datasets.alpaca(sym); x = np.array([v.get(t, np.nan) for t in dd_]); return x / x[0]
n = min(len(CUR), len(SEC), len(spy)); dd_ = dd_[:n]
S = {"SPY": spy[:n] / spy[0], "MTUM": etf("MTUM")[:n], "SPMO": etf("SPMO")[:n], "sec": SEC[:n] / SEC[0], "cur": CUR[:n] / CUR[0]}
rr = {k: c[1:] / c[:-1] - 1 for k, c in S.items()}
e = np.array([0.5 if (spy_above[i0 + i - 1] == 0.0 and breadth[i0 + i - 1] < 0.5) else 1.0 for i in range(1, n)])
rboth = 0.5 * rr["MTUM"] + 0.5 * rr["SPMO"]; rg = e * rboth + (1 - e) * rr["SPY"]
D = {"market": S["SPY"], "momentum": np.concatenate([[1.0], np.cumprod(1 + rg)]), "dip": S["sec"], "blend": np.concatenate([[1.0], np.cumprod(1 + 0.5 * rr["sec"] + 0.5 * rg)]), "dip_curated": S["cur"]}
for name, peak in (("2018 Q4 selloff (investable ETFs)", "2018-09-20"), ("2020 covid, election year (investable ETFs)", "2020-02-19"), ("2022 bear (investable ETFs)", "2022-01-03"), ("2025 tariff selloff (investable ETFs)", "2025-02-19")):
    out["episodes"].append(episode(name, dd_, D, peak, years=2))
json.dump(out, open(os.path.join(os.getcwd(), "data", "param_search", "crashes.json"), "w"))
for ep in out["episodes"]:
    print(f"\n{ep['name']}: peak {ep['peak']}, market trough {ep['trough']}")
    print(f"  {'book':12} {'at trough':>10} {'max DD':>8} {'after 2y':>9} {'after 3y':>9}")
    for k, v in ep["books"].items():
        print(f"  {k:12} {v['at_trough']:+10.1%} {v['max_dd']:8.1%} {v['after_2y']:+9.1%} {v['after_3y']:+9.1%}")
