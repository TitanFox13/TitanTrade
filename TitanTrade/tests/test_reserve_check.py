"""The working reserve against a pending bracket (Decision 089 check, 2026-11-03).

The plan's targets leave exactly ``reserve + planned slots`` in cash once both core legs are at target. SPY may sit up
to one band (5 %) above its target without being sold, and the momentum leg buys to its target with every dollar above
the reserve — it does not net out a bracket still pending from the morning run. So the cash left for that bracket's
fill is ``reserve − SPY's in-band excess``: with a 5 % reserve and a 5 % band never negative, with a 2 % reserve up to
3 % of equity short. One scenario, two reserves; the invariant is "cash after every pending buy fills ≥ 0".
"""
from __future__ import annotations

import json
from contextlib import ExitStack
from unittest.mock import patch

import pytest

from tests.test_chaos import PEAK, FakeBroker, _cfg, _patches
from datetime import datetime, timedelta, timezone


def _book(tmp_state_dir, reserve_pct):
    """Two slots held, SPMO far under target (the Oct 2026 live shape), SPY 4 % of equity above its target (inside the
    band), one bracket from the morning run still pending. Equity $100,000."""
    now = datetime.now(timezone.utc)
    positions = {"DXCM": (100.0, 80.0, 84.0), "URI": (10.0, 1000.0, 1100.0), "SPMO": (200.0, 140.0, 137.0), "SPY": (26.0, 480.0, 500.0)}
    fake = FakeBroker(cash=100_000.0 - 8_400 - 11_000 - 27_400 - 13_000, positions=positions, stops={"DXCM": 70.4, "URI": 880.0})
    fake._add_order("XLC", "buy", "limit", 166, limit_price=60.18, time_in_force="day")
    items = [
        {"ticker": "DXCM", "action": "HOLD", "stop_price": 70.4, "target_price": 96.0},
        {"ticker": "URI", "action": "HOLD", "stop_price": 880.0, "target_price": 1200.0},
        {"ticker": "XLC", "action": "NEW", "entry_price": 60.0, "stop_price": 52.8, "target_price": 72.0, "dip_pct": 0.12, "reason": "12% below its 90-day high"},
    ]
    (tmp_state_dir / "plan.json").write_text(json.dumps({"items": items, "watch": [], "exposure_scale": 1.0, "sleeve": {"ticker": "SPMO", "target_pct": 0.57}}))
    (tmp_state_dir / "data_bundle.json").write_text(json.dumps({"generated_at": now.isoformat(), "economic_calendar": [], "correlation_matrix": {},
        "stocks": {"XLC": {"signal_inputs": {"close": 60.0, "high_lookback": 68.2, "sma_trend": 57.0}, "earnings": {"is_blocked": False}, "atr_14": 1.0}}}))
    (tmp_state_dir / "trade_log.json").write_text(json.dumps({"trades": [
        {"ticker": "DXCM", "action": "BUY", "trigger": "entry", "timestamp": (now - timedelta(days=20)).isoformat(), "stop_price": 70.4, "target_price": 96.0, "price": 80.0},
        {"ticker": "URI", "action": "BUY", "trigger": "entry", "timestamp": (now - timedelta(days=14)).isoformat(), "stop_price": 880.0, "target_price": 1200.0, "price": 1000.0},
    ]}))
    (tmp_state_dir / "peak_portfolio.json").write_text(json.dumps({"peak_value": PEAK, "updated_at": now.isoformat()}))
    return fake, items


def _run_with_reserve(fake, cfg, reserve_pct):
    from titantrade.executor import execute_trades
    with ExitStack() as stack:
        stack.enter_context(_patches(fake))
        for mod in ("titantrade.risk_manager", "titantrade.core_allocation", "titantrade.mechanical"):
            stack.enter_context(patch(f"{mod}.MIN_CASH_RESERVE_PCT", reserve_pct))
        return execute_trades(cfg)


@pytest.mark.parametrize("reserve_pct, expect_short", [(5.0, False), (2.0, True)])
def test_pending_bracket_cash_after_the_momentum_leg_buys(fake_config, tmp_state_dir, reserve_pct, expect_short):
    fake, _ = _book(tmp_state_dir, reserve_pct)
    _run_with_reserve(fake, _cfg(fake_config), reserve_pct)
    pending = sum(float(o["qty"]) * float(o["limit_price"]) for o in fake.open_orders() if o["side"] == "buy")
    spmo_buy = next(o for o in fake.placed if o["symbol"] == "SPMO" and o["side"] == "buy")
    after_fill = fake.cash - pending
    print(f"\nreserve {reserve_pct:.0f} %: SPMO bought {spmo_buy['qty']:.0f} shares, cash {fake.cash:,.0f}, pending bracket {pending:,.0f}, "
          f"cash after it fills {after_fill:+,.0f} ({after_fill / 100_000:+.1%} of equity)")
    assert fake.cash >= 0
    assert (after_fill < 0) == expect_short
