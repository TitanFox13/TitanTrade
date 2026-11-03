"""The working cash reserve against the executor's own orders (Decisions 089 / 090, 2026-11-03).

After the guard — a core leg's buy spends only the cash above the reserve *and* above the brackets still pending from an
earlier run — the executor's orders cannot push cash below zero except through an adverse market fill on a core leg
(sized at the last price, filled a moment later). The reserve's one job is to cover that slip on the largest single buy:
day one's momentum leg, ≈ 59 % of equity, so a 2 % slip needs 1.18 % and the reserve is 2 % (`reserve.py`, V2). The
invariant in every scenario: cash after every pending buy fills ≥ 0 — on a margin account the broker would lend instead
of refusing, so the fake lends too (``margin``) and the test reads the balance.
"""
from __future__ import annotations

import json
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from tests.test_chaos import PEAK, FakeBroker, _cfg, _patches

EQUITY = 100_000.0


def _state(tmp_state_dir, items, stocks=None):
    now = datetime.now(timezone.utc)
    watch = [] if items else [{"ticker": "XLC", "reason": "no signal"}]   # an empty plan is "no plan" to the executor; a watch row makes it a plan
    (tmp_state_dir / "plan.json").write_text(json.dumps({"items": items, "watch": watch, "exposure_scale": 1.0, "sleeve": {"ticker": "SPMO", "target_pct": 0.588}}))
    (tmp_state_dir / "data_bundle.json").write_text(json.dumps({"generated_at": now.isoformat(), "economic_calendar": [], "correlation_matrix": {}, "stocks": stocks or {}}))
    (tmp_state_dir / "trade_log.json").write_text(json.dumps({"trades": [
        {"ticker": i["ticker"], "action": "BUY", "trigger": "entry", "timestamp": (now - timedelta(days=20)).isoformat(), "stop_price": i["stop_price"], "target_price": i["target_price"], "price": i["stop_price"] / 0.88}
        for i in items if i["action"] == "HOLD"]}))
    (tmp_state_dir / "peak_portfolio.json").write_text(json.dumps({"peak_value": PEAK, "updated_at": now.isoformat()}))


def _today(tmp_state_dir):
    """The Oct 2026 live shape: two slots held, the momentum leg far under target and filling, SPY 3.2 % of equity above
    its target (inside the 5 % band, so it is not sold), one bracket pending from the morning run."""
    positions = {"DXCM": (100.0, 80.0, 84.0), "URI": (10.0, 1000.0, 1100.0), "SPMO": (200.0, 140.0, 137.0), "SPY": (26.0, 480.0, 500.0)}
    fake = FakeBroker(cash=EQUITY - 8_400 - 11_000 - 27_400 - 13_000, positions=positions, stops={"DXCM": 70.4, "URI": 880.0})
    fake._add_order("XLC", "buy", "limit", 166, limit_price=60.18, time_in_force="day")
    items = [
        {"ticker": "DXCM", "action": "HOLD", "stop_price": 70.4, "target_price": 96.0},
        {"ticker": "URI", "action": "HOLD", "stop_price": 880.0, "target_price": 1200.0},
        {"ticker": "XLC", "action": "NEW", "entry_price": 60.0, "stop_price": 52.8, "target_price": 72.0, "dip_pct": 0.12, "reason": "12% below its 90-day high"},
    ]
    _state(tmp_state_dir, items, {"XLC": {"signal_inputs": {"close": 60.0, "high_lookback": 68.2, "sma_trend": 57.0}, "earnings": {"is_blocked": False}, "atr_14": 1.0}})
    return fake


def _day_one(tmp_state_dir):
    """Go-live day one: all cash, no positions, no signal; both core legs buy from nothing (the largest buys there are)."""
    fake = FakeBroker(cash=EQUITY, positions={}, stops={})
    _state(tmp_state_dir, [])
    return fake


def _run(fake, cfg, reserve_pct):
    from titantrade.executor import execute_trades
    with ExitStack() as stack:
        stack.enter_context(_patches(fake))
        for mod in ("titantrade.risk_manager", "titantrade.core_allocation", "titantrade.mechanical"):
            stack.enter_context(patch(f"{mod}.MIN_CASH_RESERVE_PCT", reserve_pct))
        execute_trades(cfg)
    pending = sum(float(o["qty"]) * float(o["limit_price"]) for o in fake.open_orders() if o["side"] == "buy")
    return fake.cash - pending


@pytest.mark.parametrize("reserve_pct, slip, expect_ok", [
    (2.0, 0.0, True),     # (a) today's shape: the guard leaves the pending bracket its cash (Decision 089's −1.2 % is gone)
    (2.0, 0.02, True),    # (b) the same with a 2 % adverse fill on the momentum leg's buy
])
def test_pending_bracket_keeps_its_cash_after_the_guard(fake_config, tmp_state_dir, reserve_pct, slip, expect_ok):
    fake = _today(tmp_state_dir)
    fake.margin = True
    fake.fill_slip = {"SPMO": slip}
    after = _run(fake, _cfg(fake_config), reserve_pct)
    spmo = next(o for o in fake.placed if o["symbol"] == "SPMO" and o["side"] == "buy")
    print(f"\ntoday's shape, reserve {reserve_pct:.0f} %, slip {slip:.0%}: SPMO bought {spmo['qty']:.0f}, cash after the pending fill {after:+,.0f} ({after / EQUITY:+.1%})")
    assert (after >= 0) == expect_ok


@pytest.mark.parametrize("reserve_pct, slip, expect_ok", [
    (2.0, 0.02, True),    # (c) the rule's case: a 2 % adverse fill on both legs from all cash stays above zero
    (2.0, 0.04, False),   # (d) the boundary: 4 % does not — the documented limit of a 2 % reserve
    (1.0, 0.02, False),   # why not 1 %: it fails the rule's own case
])
def test_day_one_from_all_cash_with_adverse_fills(fake_config, tmp_state_dir, reserve_pct, slip, expect_ok):
    fake = _day_one(tmp_state_dir)
    fake.margin = True
    fake.fill_slip = {"SPY": slip, "SPMO": slip}
    after = _run(fake, _cfg(fake_config), reserve_pct)
    bought = {o["symbol"]: o["qty"] for o in fake.placed if o["side"] == "buy"}
    print(f"\nday one, reserve {reserve_pct:.0f} %, slip {slip:.0%}: bought {bought}, cash after {after:+,.0f} ({after / EQUITY:+.1%})")
    assert set(bought) == {"SPY", "SPMO"}
    assert (after >= 0) == expect_ok
    assert after > -0.01 * EQUITY    # the overshoot is the slip on the last buy, never more than a percent of equity


def test_live_reserve_is_two_percent():
    from titantrade.risk_manager import MIN_CASH_RESERVE_PCT
    from titantrade.backtest.mechanical import DEFAULT_PARAMS
    assert MIN_CASH_RESERVE_PCT == 2.0 and DEFAULT_PARAMS["cash_reserve_pct"] == 0.02   # live and backtest are one book
