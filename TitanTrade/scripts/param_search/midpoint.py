import json, statistics
import analyze1_lib as al
S = al.S
CANDS = {
  "live default":      dict(dip_pct=0.10, dip_lookback_days=60,  trend_sma_days=200, max_hold_days=40, tp_pct=0.10, stop_pct=0.12),
  "c1 consensus":      dict(dip_pct=0.08, dip_lookback_days=120, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.10),
  "c2 sector-best":    dict(dip_pct=0.08, dip_lookback_days=60,  trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.20),
  "MID 8/90/150/60/20/12": dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.12),
  "MID stop 0.10":     dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.10),
  "MID stop 0.15":     dict(dip_pct=0.08, dip_lookback_days=90, trend_sma_days=150, max_hold_days=60, tp_pct=0.20, stop_pct=0.15),
}
names = ["A_alpaca_names_2016", "D_alpaca_sectors_2016", "B_yahoo_names_1999", "C_yahoo_sectors_1999"]
data = {n: al.plateau(json.load(open(f"{S}/stage1_{n}.json")), "excess") for n in names}
for n in names: al.plateau(list(data[n].values()), "oos_excess")
print(f"{'candidate':24} | " + " | ".join(f"{n[:1]}: excess/plat IS/OOS tr/yr" for n in names))
for label, pt in CANDS.items():
    k = al.key(pt)
    cells = []
    for n in names:
        r = data[n].get(k)
        cells.append(f"{r['excess']*100:+5.2f}/{r['plat_excess']*100:+5.2f} {r['is_excess']*100:+5.2f}/{r['oos_excess']*100:+5.2f} {r['trades_per_year']:4.1f}" if r else "n/a")
    print(f"{label:24} | " + " | ".join(cells))
print("\nneighbourhood of MID (all 12 one-step neighbours), excess per dataset: min / median / max")
k = al.key(CANDS["MID 8/90/150/60/20/12"])
for n in names:
    vals = [data[n][m]["excess"] for m in al.neighbours(k) if m in data[n]]
    print(f"   {n:24} min {min(vals)*100:+5.2f} med {statistics.median(vals)*100:+5.2f} max {max(vals)*100:+5.2f}   (SPY CAGR {data[n][k]['spy_cagr']*100:.1f})")
