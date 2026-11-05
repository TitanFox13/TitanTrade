"""The paper drill (Decision 103, 2026-11-05): force, on the paper account, the live paths no scheduled run had
exercised — against the real broker, with the package's own functions, one step per invocation.

Run INSIDE the api container (it has the live data mount and the keys), during market hours, between the scheduled runs:
    docker exec -i -e STEP=<step> titantrade-api-1 uv run python - < scripts/paper_drill.py
Steps, in the order run:
  status    positions, cash, open orders, the plan's held list (read-only; any time)
  renew     cancel a held name's GTC stop, then `ensure_stop_coverage` must put it back — the 90-day expiry path
  close     `close_position_settled` on NAME (default JPM): cancel the stop → settle → market sell → record (the
            holding-limit / target exit path, trigger tagged drill_*)
  targets   tp_pct → TP (default 0.05) for ONE execute run so the held legacy names up more than that exit through
            the quote-confirmed target path (Decision 084); the core legs run first in the same call; tp_pct restored
  entry     dip_pct → DIP (default 0.04) → refresh_plan → execute (SPY nets the planned slot, the leg and the sleeve
            fill, the bracket goes out) → the GTC stop on fill checked → dip_pct restored → refresh_plan
  restamp   strategy.json → window_started_at = now (the clean window restarts after the drill)
  shock     shock_drop_pct → SHOCK (default 0.02, under the worst ten-session move) for ONE plan: the shock trigger fires,
            exposure ×0.5, SPY and SPMO sell to half their targets, the bitcoin leg and the held slot untouched (the
            de-risk path, Decision 068); the threshold restored, the plan refreshed (shock off). Second drill, 2026-11-05.
  execute   refresh_plan → execute_trades — a scheduled signals + execute run by hand (after `shock`: the re-risk, SPY and
            SPMO bought back to their full targets)
Every config edit is restored in a finally; the state is backed up by scripts/backup_state.sh before the first step.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

from titantrade.broker import cancel_order, get_account, get_open_orders, get_positions, is_market_open
from titantrade.config import STATE_DIR, load_config

STEP = os.environ.get("STEP", "status"); NAME = os.environ.get("NAME", "JPM"); WATCHLIST = "data/watchlist.json"


def say(*a):
    print(f"[drill {datetime.now(timezone.utc).strftime('%H:%M:%S')}Z]", *a, flush=True)


def set_setting(key, value):
    w = json.load(open(WATCHLIST)); old = w["settings"]["mechanical"][key]; w["settings"]["mechanical"][key] = value
    json.dump(w, open(WATCHLIST, "w"), indent=2); open(WATCHLIST, "a").write("\n"); say(f"{key}: {old} → {value}"); return old


def status(cfg):
    a = get_account(cfg); pv = float(a["portfolio_value"]); say(f"market open: {is_market_open(cfg)} | equity {pv:,.0f} cash {float(a['cash']):,.0f}")
    for p in get_positions(cfg):
        say(f"  {p['symbol']:6} qty {p['qty']:>12} mv {float(p['market_value']):>10,.0f} ({float(p['market_value']) / pv:5.1%}) pl {float(p.get('unrealized_plpc') or 0):+.1%}")
    for o in get_open_orders(None, cfg):
        say(f"  order {o['symbol']} {o['side']} {o['type']} qty {o.get('qty')} stop {o.get('stop_price')} limit {o.get('limit_price')} {o.get('time_in_force')} {o.get('status')}")
    plan = json.load(open(STATE_DIR / "plan.json")); say(f"plan {plan['generated_at'][:16]} held {plan.get('held')} free slots {plan.get('free_slots')} NEW {[i['ticker'] for i in plan.get('items', []) if i.get('action') == 'NEW']}")


def main():
    cfg = load_config(); say(f"step {STEP}")
    if STEP == "status":
        status(cfg)
    elif STEP == "renew":
        from titantrade.executor import ensure_stop_coverage
        stops = [o for o in get_open_orders(NAME, cfg) if o.get("side") == "sell" and "stop" in (o.get("type") or "")]
        say(f"{NAME} stop orders before: {[(o['id'][:8], o.get('stop_price'), o.get('status')) for o in stops]}")
        for o in stops:
            cancel_order(o["id"], cfg); say(f"cancelled {o['id'][:8]} (the expiry stand-in)")
        time.sleep(6); say(f"{NAME} orders after the cancel: {[(o['type'], o.get('status')) for o in get_open_orders(NAME, cfg)]}")
        placed = ensure_stop_coverage(cfg); say(f"ensure_stop_coverage placed {placed}")
        say(f"{NAME} orders now: {[(o['type'], o.get('stop_price'), o.get('limit_price'), o.get('time_in_force'), o.get('status')) for o in get_open_orders(NAME, cfg)]}")
    elif STEP == "close":
        from titantrade.protection import close_position_settled
        trade = close_position_settled(NAME, cfg, trigger="drill_holding_limit", reason=f"paper drill (Decision 103): the settled-close exit path on {NAME}")
        say(f"trade: {trade}"); status(cfg)
    elif STEP == "targets":
        from titantrade.executor import execute_trades
        old = set_setting("tp_pct", float(os.environ.get("TP", "0.05")))
        try:
            executed = execute_trades(load_config()); say(f"executed {len(executed)}: " + "; ".join(f"{t.get('ticker')} {t.get('action')} {t.get('shares')} @ {t.get('price')} [{t.get('trigger')}]" for t in executed))
        finally:
            set_setting("tp_pct", old)
        status(load_config())
    elif STEP == "entry":
        from titantrade.executor import ensure_stop_coverage, execute_trades
        from titantrade.mechanical import refresh_plan
        old = set_setting("dip_pct", float(os.environ.get("DIP", "0.04")))
        try:
            plan = refresh_plan(load_config()); new = [i["ticker"] for i in plan.get("items", []) if i.get("action") == "NEW"]; say(f"plan NEW items with the relaxed dip: {new}")
            executed = execute_trades(load_config()); say(f"executed {len(executed)}: " + "; ".join(f"{t.get('ticker')} {t.get('action')} {t.get('shares')} @ {t.get('price')} [{t.get('trigger')}]" for t in executed))
            time.sleep(90)
            for t in new:
                say(f"{t} orders after the fill: {[(o['type'], o.get('stop_price'), o.get('limit_price'), o.get('time_in_force'), o.get('status')) for o in get_open_orders(t, cfg)]}")
            say(f"ensure_stop_coverage placed {ensure_stop_coverage(load_config())}")
        finally:
            set_setting("dip_pct", old); refresh_plan(load_config())
        status(load_config())
    elif STEP == "shock":
        from titantrade.executor import execute_trades
        from titantrade.mechanical import refresh_plan
        old = set_setting("shock_drop_pct", float(os.environ.get("SHOCK", "0.02")))
        try:
            plan = refresh_plan(load_config()); sh = plan.get("shock", {}); say(f"shock active {sh.get('active')} (worst {sh.get('worst_drop')}, {sh.get('sessions_left')} sessions left) exposure x{plan.get('exposure_scale')} NEW {[i['ticker'] for i in plan.get('items', []) if i.get('action') == 'NEW']}")
            executed = execute_trades(load_config()); say(f"executed {len(executed)}: " + "; ".join(f"{t.get('ticker')} {t.get('action')} {t.get('shares')} @ {t.get('price')} [{t.get('trigger')}]" for t in executed))
            time.sleep(15); status(load_config())
        finally:
            set_setting("shock_drop_pct", old); plan = refresh_plan(load_config()); say(f"plan refreshed: shock active {plan.get('shock', {}).get('active')} exposure x{plan.get('exposure_scale')}")
    elif STEP == "execute":
        from titantrade.executor import execute_trades
        from titantrade.mechanical import refresh_plan
        plan = refresh_plan(load_config()); say(f"plan: exposure x{plan.get('exposure_scale')} held {plan.get('held')} NEW {[i['ticker'] for i in plan.get('items', []) if i.get('action') == 'NEW']}")
        executed = execute_trades(load_config()); say(f"executed {len(executed)}: " + "; ".join(f"{t.get('ticker')} {t.get('action')} {t.get('shares')} @ {t.get('price')} [{t.get('trigger')}]" for t in executed))
        time.sleep(15); status(load_config())
    elif STEP == "restamp":
        p = STATE_DIR / "strategy.json"; s = json.load(open(p)); old = s.get("window_started_at"); s["window_started_at"] = datetime.now(timezone.utc).isoformat()
        json.dump(s, open(p, "w"), indent=2); say(f"window_started_at {old} → {s['window_started_at']} (design {s.get('design')})")
    else:
        say("unknown step"); sys.exit(2)


if __name__ == "__main__":
    main()
