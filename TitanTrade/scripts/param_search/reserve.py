"""The working cash reserve — the smallest number that can never borrow (Decision 090 research, 2026-11-03).

The operator's rule: "we never want to borrow from the broker" — cash never below zero — and "find the optimal number
of cash to hold". Decision 089 found that with the core legs' buys netting out pending brackets (the guard, built in
the same Decision), the executor's own orders cannot push cash negative *except* through one path: a market buy of a
core leg is sized at the last price and fills at the market a moment later, so an adverse fill spends more than the
sizing allowed, by the slip × the order. Everything else rounds down (whole shares), fills at or under its limit (the
entry brackets) or adds cash (every sell). So after the guard the reserve has one job — to cover the slip on the
largest single market buy — and "optimal" is the smallest whole percent that does it, since the return cost of idle
cash is linear (Decision 081: 5 % → 2 % was +0.45 pp/yr on the decade).

Pre-registered hypotheses (the expected numbers were written before the first run):
  V1  the package engine on the decade (the live book, path-exact) at a reserve of 0 / 1 / 2 / 3 / 5 %: the excess
      over SPY is linear, ≈ +0.15 pp/yr per point — ≈ +1.78 / +1.63 / +1.48 / +1.33 / +1.03 — the drawdown ≈ 0.13 points
      deeper per point less reserve, the Sharpe within 0.02, the trade list unchanged (the reserve sizes the core legs,
      not the dip slots).
  V2  the largest single market buy the executor can place is the momentum leg on day one (from all cash, after SPY's
      buy): 0.6 × (1 − reserve) ≈ 59 % of equity; the next largest is the re-risking buy when a switch releases
      (29 %); an entry is a limit order (no slip). A 2 % adverse fill on day one needs 1.18 % of equity of cover, on a
      re-risking buy 0.59 %. The rule: the reserve = the smallest whole percent that covers a 2 % adverse fill on the
      largest single buy → **2 %** (1 % would cover 1.7 %, 0 % nothing). The Oct 1987 open is the reference for "2 %":
      liquid ETFs at 10:15 / 15:30 ET slip basis points on an ordinary day, a few percent on a crash day.
  V3  the drill (`tests/test_reserve_check.py`, written with the guard): at the chosen reserve, cash after every
      pending buy fills stays ≥ 0 in (a) today's live shape — two slots held, the momentum leg filling, SPY inside
      its band above target, a bracket pending from the morning; (b) the same with a 2 % adverse fill on the momentum
      leg's buy; (c) go-live day one from all cash with 2 % adverse fills on both core legs; and (d) the boundary: a
      4 % adverse fill on day one goes negative at 2 % (the documented limit). At 1 % the day-one case (c) fails.
What would make it the Decision: the reserve is set to V2's number if V3 (a)–(c) hold there — expected 2 % — else the
next whole percent up; the gain foregone against 1 % and 0 % is recorded as the price of never borrowing, not taken.
The guard (the core buy capped at cash − reserve − pending buys) ships with it; the backtester's default reserve
follows the live constant so backtest and live stay one book.

Run from TitanTrade/: uv run --with numpy python scripts/param_search/reserve.py   (without -I: it imports the package)
"""
import sys

sys.path.insert(0, "src"); sys.path.insert(0, "scripts/param_search")
import numpy as np  # noqa: E402

import carry  # noqa: E402
import master  # noqa: E402
import validate  # noqa: E402  (loads the decade: SPY, the 11 sector ETFs)
from titantrade.backtest.mechanical import run_mechanical_backtest  # noqa: E402

GRID = [0.0, 0.01, 0.02, 0.03, 0.05]
SLIPS = [0.005, 0.01, 0.02, 0.035]


def main():
    _, dd, lvl, r, bear, split, _ = carry.sets()[0]
    spmo = validate.json.load(open(validate.D / "SPMO.json"))
    live = dict(master.LIVE, insurance_scale=0.5, momentum_weight=0.6, shock_drop_pct=0.07, shock_lookback_days=10, shock_hold_days=20, shock_scale=0.5)
    dates = [d for d in sorted(b["date"] for b in validate.spy) if dd[0] <= d <= dd[-1]]
    spy_c = {b["date"]: float(b["close"]) for b in validate.spy}; m = np.array([spy_c[d] for d in dates]); r_mkt = m[1:] / m[:-1] - 1
    print(f"=== V1 — the live book on the decade {dd[0]} → {dd[-1]} at each working reserve (path-exact engine, vs SPY)")
    print(f"  {'reserve':8} {'excess':>7} {'IS':>7} {'OOS':>7} | {'DD':>6} {'Sharpe':>6} {'worst':>6} {'roll3':>5} | {'trades':>6} {'SPMO':>5} | gain vs 5 %")
    rows = {}
    for res in GRID:
        out = run_mechanical_backtest(validate.sect, validate.spy, validate.sect, {**live, "cash_reserve_pct": res}, dd[0], dd[-1], momentum_bars=spmo)
        c = np.array(out["equity_curve"]); rr = c[1:] / c[:-1] - 1
        s = master.score(rr, r_mkt, dates, split); rows[res] = (s, out)
    base = rows[0.05][0]
    for res in GRID:
        s, out = rows[res]
        print(f"  {res:8.0%} {s['excess']:+7.2%} {s['is']:+7.2%} {s['oos']:+7.2%} | {s['dd']:6.1%} {s['sharpe']:6.2f} {s['worst_year']:+6.1%} {s['roll3_pos']:5.0%} | {out['metrics']['trades']:6} {out['avg_momentum_share']:5.0%} | {s['excess'] - base['excess']:+.2%}")
    slope = np.polyfit([x * 100 for x in GRID], [rows[x][0]["excess"] for x in GRID], 1)[0]
    print(f"  slope: {slope:+.3%} of excess per point of reserve; the trade lists {'agree' if len({rows[x][1]['metrics']['trades'] for x in GRID}) == 1 else 'DIFFER'} across the grid")
    print("\n=== V2 — the cover an adverse market fill needs (slip × the largest single buy), vs each reserve")
    buys = {"day one, the momentum leg (from all cash, after SPY's buy)": lambda res: 0.6 * (1 - res),
            "re-risking when a switch releases (×0.5 → ×1)": lambda res: 0.5 * 0.6 * (1 - res),
            "the SPY leg after an exit (one slot's cash back)": lambda res: 0.10}
    print(f"  {'buy':62} {'size':>5} | " + " ".join(f"{'slip ' + f'{s:.1%}':>10}" for s in SLIPS))
    for label, size in buys.items():
        print(f"  {label:62} {size(0.02):5.0%} | " + " ".join(f"{size(0.02) * s:10.2%}" for s in SLIPS))
    print("  a reserve covers a cell when it is at least that number; the rule: the smallest whole percent ≥ the day-one cell at a 2 % slip "
          f"= {0.6 * 0.98 * 0.02:.2%} → {int(np.ceil(0.6 * 0.98 * 0.02 * 100))} %")
    print("\n=== V3 is the drill: tests/test_reserve_check.py (run with: uv run --extra test python -m pytest tests/test_reserve_check.py -q -s)")


if __name__ == "__main__":
    main()
