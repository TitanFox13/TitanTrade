"""A value sleeve beside the dip and momentum sleeves (brainstorm #6; Decision 068 addendum, 2026-10-29).

Asness, Moskowitz and Pedersen: value and momentum are negatively correlated everywhere (about −0.5 in their
long-short form), so a value sleeve is the classic diversifier of a momentum book. Here value is long only and
investable: on the decade the value ETFs (IVE S&P 500 value, VTV, VLUE MSCI value factor, IWD Russell 1000 value,
RPV pure value; Alpaca SIP, dividend-adjusted like the rest), on the century Kenneth French's value-weighted
"Hi 30" book-to-market portfolio (1926 →), with "Lo 30" (growth) as its mirror. Pre-registered hypotheses:
  VA1  value alone lags SPY by 3–5 pp/yr on the decade (every vehicle) and beats the market by +1 … +3 on the century
       with its own drawdowns (1929–32, 2008);
  VA2  the correlation of value's daily excess with SPMO's excess is negative on both eras (≤ −0.3), and with the dip
       sleeve's excess near 0;
  VA3  a 20 % value sleeve taken from SPMO costs 0.5–1.5 pp/yr on the decade and is ±0.5 on the century with a Sharpe
       within +0.03 — not positive in both decade halves, so not adopted;
  VA4  the same sleeve taken from the dip sleeve has a worse drawdown than taken from SPMO (the dip sleeve is the
       book's drawdown piece).
Run from TitanTrade/: uv run --with numpy python -I scripts/param_search/value.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402

VEHICLES = ["VLUE", "IVE", "VTV", "IWD", "RPV"]


def rets(series, dd):
    lv = np.array([series.get(t, np.nan) for t in dd]); return np.nan_to_num(lv[1:] / lv[:-1] - 1)


def main():
    for name, dd, lvl, r, bear, split, eras in carry.sets():
        shock = master.shock_flags(lvl, -0.07, 10, 20); e = carry.exposure(bear, shock)
        base = e * (0.4 * r["dip"] + 0.6 * r["mom"]); sb = master.score(base, r["mkt"], dd, split, eras)
        if name == "decade":
            vals = {v: rets(datasets.alpaca(v), dd) for v in VEHICLES}
        else:
            beme = datasets.french_levels("Portfolios_Formed_on_BE-ME_Daily.csv")
            vals = {"Hi 30 (value)": rets(beme["Hi 30"], dd), "Lo 30 (growth)": rets(beme["Lo 30"], dd), "Hi 10 (deep value)": rets(beme["Hi 10"], dd)}

        def line(label, rr):
            s = master.score(rr, r["mkt"], dd, split, eras)
            print(f"{label:56} {s['excess']:+7.2%} {s['excess'] - sb['excess']:+6.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['dd']:6.1%} {s['sharpe']:5.2f} | {s['worst_year']:+6.1%}"
                  + ("" if not eras else " | " + " ".join(f"{x:+6.1%}" for x in s["eras"])))
            return s

        print(f"\n=== value sleeve — {name} {dd[0]} → {dd[-1]}: columns excess vs market, gain vs the book, IS, OOS | DD, Sharpe | worst year" + (" | eras" if eras else ""))
        print("--- the vehicles alone, and the correlation of their daily excess with SPMO's / the dip sleeve's excess")
        mx, dx = r["mom"] - r["mkt"], r["dip"] - r["mkt"]
        for v, rv in vals.items():
            s = line(f"{v} alone", rv); vx = rv - r["mkt"]
            print(f"{'':56} corr with momentum excess {np.corrcoef(vx, mx)[0, 1]:+.2f}, with dip excess {np.corrcoef(vx, dx)[0, 1]:+.2f}")
        print("--- books")
        line("recommended book 40 / 60", base)
        first = next(iter(vals))
        for v, rv in vals.items():
            if name == "century" and v.startswith("Lo"):
                continue
            line(f"dip 40 / SPMO 40 / {v} 20", e * (0.4 * r["dip"] + 0.4 * r["mom"] + 0.2 * rv))
        rv = vals[first]
        line(f"dip 40 / SPMO 50 / {first} 10", e * (0.4 * r["dip"] + 0.5 * r["mom"] + 0.1 * rv))
        line(f"dip 30 / SPMO 50 / {first} 20", e * (0.3 * r["dip"] + 0.5 * r["mom"] + 0.2 * rv))
        line(f"dip 20 / SPMO 60 / {first} 20 (from the dip sleeve)", e * (0.2 * r["dip"] + 0.6 * r["mom"] + 0.2 * rv))
        line(f"dip 40 / SPMO 30 / {first} 30", e * (0.4 * r["dip"] + 0.3 * r["mom"] + 0.3 * rv))


if __name__ == "__main__":
    main()
