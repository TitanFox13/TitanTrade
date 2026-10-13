"""Trade-for-trade validation of fastbt against the shipped backtester."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, "src")
from titantrade.backtest.mechanical import run_mechanical_backtest
import fastbt
D = Path("data/param_search/alpaca_hist/historical_long")
NAMES = ["CRWD","ANET","LLY","DXCM","HCA","JPM","GS","DVN","WMT","URI","GE","DASH","DECK","FCX","EQIX"]
SECT = ["XLK","XLV","XLF","XLE","XLI","XLY","XLB","XLRE","XLP","XLU","XLC"]
bars = {n: json.load(open(D / f"{n}.json")) for n in NAMES}
spy = json.load(open(D / "SPY.json")); sect = {s: json.load(open(D / f"{s}.json")) for s in SECT}
mkt = fastbt.load_dir(str(D), NAMES, SECT)
for params in [{}, {"dip_pct": 0.08, "max_hold_days": 60, "tp_pct": 0.15, "stop_pct": 0.10}, {"dip_pct": 0.12, "dip_lookback_days": 90, "trend_sma_days": 100, "insurance_scale": 0.0, "max_slots": 4, "slot_pct": 0.15}]:
    t0 = time.time(); ref = run_mechanical_backtest(bars, spy, sect, params, "2018-01-01", "2026-10-12"); t1 = time.time()
    fast = fastbt.run(mkt, params, "2018-01-01", "2026-10-12", want_trades=True); t2 = time.time()
    rt = [(t["ticker"], t["exit_date"], t["exit"], t["return"]) for t in ref["trades"]]
    ft = [(t["ticker"], t["exit_date"], t["exit"], t["return"]) for t in fast["trades"]]
    same_trades = rt == ft
    eq_ref = ref["equity_curve"][-1]; eq_fast = float(fast["_curve"][-1])
    print(f"params={params}\n   ref: {len(rt)} trades, final {eq_ref:,.2f}, maxDD {ref['metrics']['max_drawdown']:.4f}, risk-off {ref['risk_off_days']}  ({t1-t0:.1f}s)\n   fast: {len(ft)} trades, final {eq_fast:,.2f}, maxDD {fast['metrics']['max_drawdown']:.4f}, risk-off {fast['risk_off_days']}  ({t2-t1:.2f}s)\n   trades identical: {same_trades}   equity rel diff: {abs(eq_ref-eq_fast)/eq_ref:.2e}")
    if not same_trades:
        for a, b in zip(rt, ft):
            if a != b: print("   first diff:", a, b); break
        print("   ref-only:", [x for x in rt if x not in ft][:3], "fast-only:", [x for x in ft if x not in rt][:3])
