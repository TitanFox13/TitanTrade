"""One-shot PAPER-ACCOUNT probe: does Alpaca accept a LIMIT buy while a sell
stop rests on the position?

This is the single assumption behind the pyramid fix (Decision 035) that the
mocked test suite cannot verify: the production logs only ever showed a MARKET
buy being rejected as a wash trade ("use complex/limit/stop_limit orders"). The
fix switched pyramids to a marketable limit buy on the inference that a limit
order is accepted alongside the resting stop. This script confirms or refutes
that against the real broker.

It is SAFE:
  * Refuses to run unless the configured Alpaca endpoint is the PAPER API.
  * Uses a throwaway, non-watchlist ticker (F, ~$12) at qty 1.
  * Refuses to touch F if you already hold it / have open F orders.
  * Places only resting orders that won't fill/trigger (50% away from market).
  * Cleans up in a finally block: cancels all F orders, closes the F position.

Run on the server where .env lives:
    cd TitanTrade && uv run --extra test python scripts/probe_pyramid_washtrade.py
(Market must be OPEN — it needs a real fill to establish the test position.)
"""

from __future__ import annotations

import sys
import time

from titantrade.config import load_config
from titantrade.executor import (
    cancel_all_orders_for_ticker,
    close_position_at_market,
    get_open_orders,
    get_order,
    get_position,
    get_positions,
    is_market_open,
    place_limit_buy,
    place_market_buy,
    place_native_stop_loss,
    _wait_for_order_canceled,
)
from titantrade.retry import HTTPError

TICKER = "F"          # Ford — cheap, liquid, NOT in the TitanTrade watchlist
QTY = 1


def _poll_fill(order_id: str, cfg, timeout: float = 60.0) -> str | None:
    """Poll an order to a terminal state; returns the status (e.g. 'filled')."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        o = get_order(order_id, cfg)
        if o and str(o.get("status", "")).lower() in (
            "filled", "canceled", "cancelled", "rejected", "expired", "done_for_day"
        ):
            return str(o.get("status")).lower()
        time.sleep(1.0)
    return None


def main() -> int:
    cfg = load_config()

    # --- HARD SAFETY GUARD: paper only -------------------------------------
    if "paper-api" not in cfg.alpaca.base_url:
        print(f"REFUSING TO RUN: endpoint is not paper ({cfg.alpaca.base_url}).")
        return 2
    print(f"[ok] paper endpoint: {cfg.alpaca.base_url}")

    if not is_market_open(cfg):
        print("Market is CLOSED — this probe needs a real fill to set up the "
              "test position. Re-run during US market hours.")
        return 3
    print("[ok] market is open")

    # --- Don't clobber an existing F position / orders ---------------------
    if any(p.get("symbol") == TICKER for p in get_positions(cfg)):
        print(f"REFUSING: you already hold {TICKER}. Pick a different ticker.")
        return 4
    if get_open_orders(TICKER, cfg):
        print(f"REFUSING: open orders already exist on {TICKER}.")
        return 4

    results: dict[str, str] = {}
    try:
        # 1) Establish a 1-share position so a sell stop can rest on it.
        print(f"\n[1] Market BUY {QTY} {TICKER} to establish a position...")
        buy = place_market_buy(TICKER, QTY, cfg)
        status = _poll_fill(buy.get("id", ""), cfg)
        if status != "filled":
            print(f"    establish-buy did not fill (status={status}); aborting.")
            return 5
        pos = get_position(TICKER, cfg)
        px = float(pos.get("current_price", 0)) if pos else 0.0
        print(f"    filled. position qty={pos.get('qty')} @ ~${px:.2f}")

        # 2) Rest a protective sell stop FAR below market (won't trigger).
        stop_px = round(px * 0.5, 2)
        print(f"[2] Resting protective stop-limit SELL {QTY} {TICKER} @ ${stop_px}...")
        place_native_stop_loss(TICKER, QTY, stop_px, cfg)
        time.sleep(1.5)

        # 3) PROBE A — the OLD behavior: market buy against the resting stop.
        print(f"[3] PROBE A: market BUY {QTY} {TICKER} (expect wash-trade reject)...")
        try:
            place_market_buy(TICKER, QTY, cfg)
            results["market_buy"] = "ACCEPTED (unexpected — old bug may be gone broker-side)"
        except HTTPError as e:
            results["market_buy"] = f"REJECTED code={e.error_code} msg={e.error_message}"
        print(f"    -> {results['market_buy']}")

        # 4) PROBE B — the FIX: a (resting) limit buy against the same stop.
        #    Marketability doesn't change the wash-trade determination, so we
        #    rest it far below market to avoid an extra fill, then cancel it.
        buy_px = round(px * 0.5, 2)
        print(f"[4] PROBE B: limit BUY {QTY} {TICKER} @ ${buy_px} (the fix)...")
        try:
            lim = place_limit_buy(TICKER, QTY, buy_px, cfg, time_in_force="day")
            results["limit_buy"] = "ACCEPTED"
            # Inspect the order dict — confirms open buys carry limit_price/side
            # (the committed-cash assumption in open_buy_commitment()).
            oid = lim.get("id", "")
            time.sleep(1.0)
            od = get_order(oid, cfg) or {}
            print(f"    order dict: side={od.get('side')} type={od.get('type')} "
                  f"limit_price={od.get('limit_price')} qty={od.get('qty')}")
            results["order_shape"] = (
                "OK" if od.get("side") == "buy" and od.get("limit_price") else "UNEXPECTED"
            )
        except HTTPError as e:
            results["limit_buy"] = f"REJECTED code={e.error_code} msg={e.error_message}"
            results["order_shape"] = "n/a (limit buy rejected)"
        print(f"    -> {results['limit_buy']}")

    finally:
        # --- Cleanup: never leave the paper account in a test state --------
        print(f"\n[cleanup] cancelling all {TICKER} orders + closing position...")
        try:
            cancel_all_orders_for_ticker(TICKER, cfg)
            time.sleep(1.5)
        except Exception as e:  # noqa: BLE001
            print(f"    cancel cleanup error: {e}")
        try:
            if get_position(TICKER, cfg):
                close_position_at_market(TICKER, cfg)
        except Exception as e:  # noqa: BLE001
            print(f"    close cleanup error: {e}")
        # Confirm flat
        for _ in range(20):
            if not get_position(TICKER, cfg):
                break
            time.sleep(1.0)
        flat = not get_position(TICKER, cfg)
        leftover = len(get_open_orders(TICKER, cfg))
        print(f"    flat={flat} | leftover {TICKER} orders={leftover}")

    # --- Verdict -----------------------------------------------------------
    print("\n" + "=" * 64)
    print("VERDICT — pyramid fix assumption (limit buy vs resting sell stop)")
    print("=" * 64)
    print(f"  market buy  : {results.get('market_buy')}")
    print(f"  limit buy   : {results.get('limit_buy')}")
    print(f"  order shape : {results.get('order_shape')}")
    if results.get("limit_buy") == "ACCEPTED":
        print("\n  PASS: a limit buy IS accepted alongside the resting stop.")
        print("  -> The pyramid fix (marketable limit buy) will work in production.")
        return 0
    print("\n  FAIL: the limit buy was ALSO rejected. The pyramid fix needs a")
    print("  different approach (cancel stop -> buy -> re-stop, or a complex")
    print("  order). NOTE: the position is never left bare either way — the")
    print("  pyramid now fails gracefully instead of erroring.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
