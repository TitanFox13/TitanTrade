"""Three ways to re-weight the sleeves (brainstorm #8, #9, #12; Decision 068 addendum, 2026-10-29), each against
the recommended book (min(insurance ×0.5, shock ×0.5) × (0.4 dip + 0.6 SPMO)). Pre-registered hypotheses:
  V1  (#8, Barroso–Santa-Clara / Daniel–Moskowitz, long-only form) scaling the momentum sleeve's share by the inverse
      of its own realised *relative* volatility (SPMO − SPY, 126 sessions; the top decile − market on the century), the
      released share going to the dip sleeve, not cash: 0 ± 0.3 pp/yr, inside the spread of a placebo (the volatility
      series shuffled in 63-session blocks), on both eras; the decade's momentum-crash years do not improve.
  I1  (#9, Moskowitz–Grinblatt) a third sleeve rotating into the top 3 of the 17 sector + industry ETFs by 12-1
      momentum, monthly, taken from SPMO: ≈ 0 or negative, correlated > 0.5 with SPMO's own excess (it is the same
      bet in a worse vehicle); the six industry ETFs were chosen in 2026 — hindsight in the sleeve's favour.
  G1  (#12) a permanent 10 % in gold (GLD), taken from SPMO or from the dip sleeve: return −0.3 … −0.5 vs the book,
      drawdown 1–2 points better, Sharpe within ±0.02 — a drawdown instrument that loses to SPY by construction.
Decade 2017 → 2026 (split 2022); V1 also on the century (split 1975). Run from TitanTrade/:
uv run --with numpy python -I scripts/param_search/sleeveweight.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import carry  # noqa: E402
import datasets  # noqa: E402
import master  # noqa: E402

INDUSTRY = ["XBI", "SMH", "ITB", "KRE", "XOP", "IBB"]
COST = 0.0005


def roll_std(x, n):
    out = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        out[i] = x[i - n:i].std() * np.sqrt(252)
    return out


def block_shuffle(x, rng, block=63):
    n = len(x); idx = np.arange(0, n, block); order = rng.permutation(len(idx))
    return np.concatenate([x[idx[k]:idx[k] + block] for k in order])[:n]


def rotation_returns(dd, syms, top=3):
    """Monthly top-N by 12-1 return over ETF closes aligned to ``dd``; daily returns net of turnover cost."""
    lv = np.array([[datasets.alpaca(s).get(t, np.nan) for s in syms] for t in dd])
    n = len(dd) - 1; r = lv[1:] / lv[:-1] - 1; out = np.zeros(n); held = None
    for i in range(n):
        d = dd[i]
        if i >= 252 and (held is None or d[:7] != dd[i - 1][:7]):
            with np.errstate(invalid="ignore"):
                mom = lv[i - 21] / lv[i - 252] - 1
            mom = np.where(np.isnan(mom), -np.inf, mom); pick = set(np.argsort(-mom)[:top].tolist())
            churn = 1 - len(pick & held) / top if held else 1.0
            out[i] -= COST * 2 * churn
            held = pick
        if held:
            rr = np.nan_to_num(r[i, list(held)]); out[i] += rr.mean()
    return out


def main():
    rng = np.random.default_rng(8)
    eps = [("2020", "2020-02-19", "2020-03-23"), ("2022", "2022-01-03", "2022-10-12"), ("2023yr", "2023-01-03", "2023-12-29"), ("2025", "2025-02-19", "2025-04-08")]
    for name, dd, lvl, r, bear, split, eras in carry.sets():
        shock = master.shock_flags(lvl, -0.07, 10, 20); e = carry.exposure(bear, shock)
        base = e * (0.4 * r["dip"] + 0.6 * r["mom"]); sb = master.score(base, r["mkt"], dd, split, eras)

        def episodes(rr):
            if name != "decade": return []
            c = np.concatenate([[1.0], np.cumprod(1 + rr)]); m = np.concatenate([[1.0], np.cumprod(1 + r["mkt"])]); out = []
            for _, a, b in eps:
                ia = next(k for k, x in enumerate(dd) if x >= a); ib = next(k for k, x in enumerate(dd) if x >= b); out.append(c[ib] / c[ia] - m[ib] / m[ia])
            return out

        def line(label, rr, extra=""):
            s = master.score(rr, r["mkt"], dd, split, eras)
            print(f"{label:52} {s['excess']:+7.2%} {s['excess'] - sb['excess']:+6.2%} {s['is']:+6.1%} {s['oos']:+6.1%} | {s['dd']:6.1%} {s['sharpe']:5.2f} | "
                  + (" ".join(f"{x:+7.1%}" for x in episodes(rr)) if name == "decade" else " ".join(f"{x:+6.1%}" for x in s["eras"])) + extra)
            return s

        print(f"\n=== sleeve weights — {name} {dd[0]} → {dd[-1]}: columns excess, gain vs book, IS, OOS | DD, Sharpe | " + ("episodes (book − market)" if name == "decade" else "eras"))
        line("recommended book 40 / 60", base)
        # V1: volatility-managed momentum share
        rel = r["mom"] - r["mkt"]; sig = master.prev(roll_std(rel, 126))
        for target in ((0.05, 0.07, 0.09) if name == "decade" else (0.08, 0.10, 0.12)):
            w = np.clip(0.6 * target / np.where(np.isnan(sig), target, sig), 0.3, 0.6)
            rr = e * ((1 - w) * r["dip"] + w * r["mom"]); s = line(f"V1 momentum share = 0.6 × {target:.0%}/σ_rel, clipped 30–60 %", rr, f" | mean share {w.mean():.0%}")
            if target == (0.07 if name == "decade" else 0.10):
                pl = []
                for _ in range(20):
                    s2 = block_shuffle(np.nan_to_num(sig, nan=target), rng); w2 = np.clip(0.6 * target / s2, 0.3, 0.6)
                    pl.append(master.score(e * ((1 - w2) * r["dip"] + w2 * r["mom"]), r["mkt"], dd, split, eras)["excess"] - sb["excess"])
                pl = np.array(pl); print(f"{'':52} placebo gain median {np.median(pl):+.2%} [{np.percentile(pl, 10):+.2%}…{np.percentile(pl, 90):+.2%}], beaten {np.mean(s['excess'] - sb['excess'] > pl):.0%}")
        if name != "decade":
            continue
        # I1: industry-momentum rotation beside SPMO
        rot = rotation_returns(dd, datasets.SECT + INDUSTRY)
        rot_x, spmo_x = rot - r["mkt"], r["mom"] - r["mkt"]
        print(f"  rotation sleeve alone vs SPY {master.score(rot, r['mkt'], dd, split)['excess']:+.2%}; correlation of its excess with SPMO's excess {np.corrcoef(rot_x, spmo_x)[0, 1]:.2f}")
        line("I1 dip 40 / SPMO 40 / rotation 20", e * (0.4 * r["dip"] + 0.4 * r["mom"] + 0.2 * rot))
        line("I1 dip 40 / SPMO 30 / rotation 30", e * (0.4 * r["dip"] + 0.3 * r["mom"] + 0.3 * rot))
        line("I1 dip 40 / rotation 60 (SPMO replaced)", e * (0.4 * r["dip"] + 0.6 * rot))
        # G1: gold
        g = datasets.alpaca("GLD"); gl = np.array([g.get(t, np.nan) for t in dd]); rg = np.nan_to_num(gl[1:] / gl[:-1] - 1)
        line("G1 dip 40 / SPMO 50 / GLD 10 (from SPMO)", e * (0.4 * r["dip"] + 0.5 * r["mom"] + 0.1 * rg))
        line("G1 dip 30 / SPMO 60 / GLD 10 (from the dip sleeve)", e * (0.3 * r["dip"] + 0.6 * r["mom"] + 0.1 * rg))
        line("G1 dip 40 / SPMO 60 + GLD 10 unscaled (gold never de-risked)", e * (0.4 * r["dip"] + 0.6 * r["mom"]) * 0.9 + 0.1 * rg)


if __name__ == "__main__":
    main()
