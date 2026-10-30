"""The chaos drill (Decision 084): one executor run against a broker that lies,
refuses and vanishes. A stateful fake broker with Alpaca's share accounting (a
resting sell holds its shares, a second sell on held shares is refused with
40310000, a cancel releases them) is patched into every module that imports a
broker function by name; the HTTP layer counts any call that escapes it. After
each scenario the invariants: nothing bare, nothing doubled, no order on bad
data, only prescribed actions, the peak never learns a phantom, no call escapes.
The three findings of the first run (Decision 084) are fixed and now pass:
the account-value guard and the quote-confirmed target exit. Zero network."""
from __future__ import annotations

import json
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from titantrade.retry import HTTPError

CORE = {"SPY", "SPMO"}
PRESCRIBED = {"entry", "target", "holding_limit", "orphan_close", "gap_down_protection", "core_rebalance"}
PEAK = 100_000.0


def _err(code: int, msg: str, **extra) -> HTTPError:
    return HTTPError(403, json.dumps({"code": code, "message": msg, **extra}), "fake://alpaca", "POST")


class FakeBroker:
    """Account, positions and resting orders, with the broker's rules; anomalies are attributes."""

    def __init__(self, cash: float, positions: dict[str, tuple[float, float, float]], stops: dict[str, float]):
        self.cash = cash
        self.pos = {s: {"qty": q, "avg": avg, "mark": mark} for s, (q, avg, mark) in positions.items()}
        self.initial_positions = set(positions)
        self.orders: list[dict] = []
        self.placed: list[dict] = []          # every order this run placed
        self.sold: list[str] = []
        self.http_calls = 0
        # anomalies
        self.phantom_equity: float | None = None
        self.marks: dict[str, float] = {}      # the position mark the broker shows, when it lies
        self.quotes: dict[str, float] = {}     # the live quote, when it differs from the mark
        self.splits: dict[str, list] = {}
        self.refuse_close: dict[str, int] = {}  # market sells refused (with the shares free), per symbol, n times
        self.refuse_cancel: set[str] = set()
        self.dead = False
        for s, stop in stops.items():
            self._add_order(s, "sell", "stop_limit", self.pos[s]["qty"], stop_price=stop, limit_price=round(stop * 0.99, 2))

    # --- state helpers ---
    def _add_order(self, sym, side, typ, qty, **kw):
        o = {"id": f"o{len(self.orders) + 1}", "symbol": sym, "side": side, "type": typ, "qty": str(qty), "status": "open",
             "time_in_force": kw.pop("time_in_force", "gtc"), **{k: str(v) for k, v in kw.items()}}
        self.orders.append(o)
        return o

    def open_orders(self, sym=None):
        return [o for o in self.orders if o["status"] == "open" and (sym is None or o["symbol"] == sym)]

    def _held(self, sym):
        return sum(float(o["qty"]) for o in self.open_orders(sym) if o["side"] == "sell")

    def _mark(self, sym):
        return self.marks.get(sym, self.pos[sym]["mark"])

    def _position(self, sym):
        p = self.pos.get(sym)
        if not p or p["qty"] <= 0:
            return None
        mark, qty = self._mark(sym), p["qty"]
        return {"symbol": sym, "qty": str(qty), "qty_available": str(qty - self._held(sym)), "held_for_orders": str(self._held(sym)),
                "avg_entry_price": str(p["avg"]), "current_price": str(mark), "market_value": str(qty * mark),
                "unrealized_plpc": str(mark / p["avg"] - 1)}

    def _alive(self):
        if self.dead:
            raise ConnectionError("network down")

    # --- the broker surface ---
    def get_account(self, cfg):
        self._alive()
        equity = self.phantom_equity if self.phantom_equity is not None else self.cash + sum(p["qty"] * self._mark(s) for s, p in self.pos.items())
        return {"portfolio_value": str(equity), "cash": str(self.cash), "buying_power": str(self.cash)}

    def get_positions(self, cfg):
        self._alive()
        return [p for p in (self._position(s) for s in list(self.pos)) if p]

    def get_position(self, sym, cfg):
        self._alive()
        return self._position(sym)

    def get_open_orders(self, sym, cfg):
        self._alive()
        return [dict(o) for o in self.open_orders(sym)]

    def get_order(self, oid, cfg):
        self._alive()
        return next((dict(o) for o in self.orders if o["id"] == oid), None)

    def cancel_order(self, oid, cfg):
        self._alive()
        o = next(o for o in self.orders if o["id"] == oid)
        if oid in self.refuse_cancel:
            raise HTTPError(422, json.dumps({"code": 42210000, "message": "order is not cancelable"}), "fake://alpaca", "DELETE")
        o["status"] = "canceled"

    def cancel_all_orders_for_ticker(self, sym, cfg):
        n = 0
        for o in self.open_orders(sym):
            self.cancel_order(o["id"], cfg)
            n += 1
        return n

    def wait_for_order_canceled(self, oid, cfg, timeout_seconds=0):
        self._alive()
        st = self.get_order(oid, cfg)
        return None if st is None or st["status"] == "open" else st["status"]

    def is_market_open(self, cfg):
        self._alive()
        return True

    def get_latest_price(self, sym, cfg):
        self._alive()
        return self.quotes.get(sym, self.pos[sym]["mark"] if sym in self.pos else 60.0)

    def get_recent_split_announcements(self, sym, cfg):
        self._alive()
        return list(self.splits.get(sym, []))

    def _sell(self, sym, qty):
        held = self._held(sym)
        if held > 0:
            raise _err(40310000, f"insufficient qty available for order (requested: {qty}, available: {self.pos[sym]['qty'] - held})",
                       available=str(self.pos[sym]["qty"] - held), related_orders=[o["id"] for o in self.open_orders(sym) if o["side"] == "sell"])
        if self.refuse_close.get(sym, 0) > 0:
            self.refuse_close[sym] -= 1
            raise _err(40310000, "insufficient qty available for order", available=str(qty))
        price = self.quotes.get(sym, self.pos[sym]["mark"])   # a market sell fills at the market, not at the mark
        self.cash += qty * price
        self.pos[sym]["qty"] -= qty
        self.sold.append(sym)
        self.placed.append({"symbol": sym, "side": "sell", "type": "market", "qty": qty})
        return {"id": f"m{len(self.placed)}", "status": "filled"}

    def close_position_at_market(self, sym, cfg):
        self._alive()
        return self._sell(sym, self.pos[sym]["qty"])

    def place_market_sell(self, sym, qty, cfg):
        self._alive()
        return self._sell(sym, qty)

    def place_market_buy(self, sym, qty, cfg):
        self._alive()
        price = self.quotes.get(sym, self.pos[sym]["mark"] if sym in self.pos else 60.0)
        if qty * price > self.cash:
            raise _err(40310000, "insufficient buying power")
        self.cash -= qty * price
        p = self.pos.setdefault(sym, {"qty": 0.0, "avg": price, "mark": price})
        p["avg"] = (p["avg"] * p["qty"] + price * qty) / (p["qty"] + qty)
        p["qty"] += qty
        self.placed.append({"symbol": sym, "side": "buy", "type": "market", "qty": qty})
        return {"id": f"m{len(self.placed)}", "status": "filled"}

    def place_native_stop_loss(self, sym, qty, stop_price, cfg):
        self._alive()
        if self.pos[sym]["qty"] - self._held(sym) < qty:
            raise _err(40310000, "insufficient qty available for order", available=str(self.pos[sym]["qty"] - self._held(sym)),
                       related_orders=[o["id"] for o in self.open_orders(sym) if o["side"] == "sell"])
        o = self._add_order(sym, "sell", "stop_limit", qty, stop_price=stop_price, limit_price=round(stop_price * 0.99, 2))
        self.placed.append({"symbol": sym, "side": "sell", "type": "stop_limit", "qty": qty, "stop_price": stop_price})
        return dict(o)

    def place_limit_sell(self, sym, qty, limit_price, cfg, time_in_force="gtc"):
        self._alive()
        o = self._add_order(sym, "sell", "limit", qty, limit_price=limit_price, time_in_force=time_in_force)
        self.placed.append({"symbol": sym, "side": "sell", "type": "limit", "qty": qty})
        return dict(o)

    def place_bracket_order(self, ticker, qty, entry_limit_price, stop_loss_price, take_profit_price, cfg):
        self._alive()
        o = self._add_order(ticker, "buy", "limit", qty, limit_price=entry_limit_price, time_in_force="day")
        self.placed.append({"symbol": ticker, "side": "buy", "type": "bracket", "qty": qty})
        return dict(o)

    def fetch_with_retry(self, *a, **k):       # the cooldown scan's closed-orders page
        self._alive()
        class R:
            @staticmethod
            def json():
                return []
        return R()

    def http(self, *a, **k):                   # anything that reaches the real HTTP layer
        self.http_calls += 1
        raise ConnectionError("a real HTTP call escaped the fake broker")


def _patches(fake: FakeBroker) -> ExitStack:
    names = {
        "titantrade.executor": ["cancel_all_orders_for_ticker", "cancel_order", "get_account", "get_open_orders", "get_position",
                                "get_positions", "is_market_open", "place_limit_sell", "place_native_stop_loss", "get_latest_price"],
        "titantrade.protection": ["get_positions", "get_position", "get_open_orders", "cancel_order", "close_position_at_market",
                                  "place_market_sell", "place_native_stop_loss", "get_recent_split_announcements", "get_latest_price"],
        "titantrade.entries": ["place_bracket_order", "get_open_orders", "get_order", "get_position", "cancel_order",
                               "place_native_stop_loss", "get_latest_price", "fetch_with_retry"],
        "titantrade.core_allocation": ["get_account", "get_positions", "is_market_open", "place_market_buy", "place_market_sell", "get_latest_price"],
    }
    stack = ExitStack()
    for mod, fns in names.items():
        for fn in fns:
            stack.enter_context(patch(f"{mod}.{fn}", getattr(fake, fn)))
    stack.enter_context(patch("titantrade.protection._wait_for_order_canceled", fake.wait_for_order_canceled))
    stack.enter_context(patch("titantrade.entries._wait_for_order_canceled", fake.wait_for_order_canceled))
    stack.enter_context(patch("titantrade.executor.load_stock_sectors", lambda *a, **k: None))
    stack.enter_context(patch("titantrade.retry.httpx.Client", fake.http))
    return stack


def _book(tmp_state_dir, *, uri_opened_days_ago=14, drop_stop=None, pending_xlc=False, hold_xlc=False):
    """Today's shape at rest: two dip slots with stops, SPMO near its 57 % target, SPY the small residual, cash."""
    now = datetime.now(timezone.utc)
    positions = {"DXCM": (100.0, 80.0, 84.0), "URI": (10.0, 1000.0, 1100.0), "SPMO": (400.0, 140.0, 137.0), "SPY": (20.0, 480.0, 500.0)}
    if hold_xlc:
        positions["XLC"] = (160.0, 58.0, 60.0)
    fake = FakeBroker(cash=15_800.0 - (9_600.0 if hold_xlc else 0), positions=positions, stops={"DXCM": 70.4, "URI": 880.0})
    if drop_stop:
        for o in fake.open_orders(drop_stop):
            o["status"] = "canceled"          # the broker cancelled it (the 90-day expiry, a corporate action)
    if pending_xlc:
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
        {"ticker": "URI", "action": "BUY", "trigger": "entry", "timestamp": (now - timedelta(days=uri_opened_days_ago)).isoformat(), "stop_price": 880.0, "target_price": 1200.0, "price": 1000.0},
    ]}))
    (tmp_state_dir / "peak_portfolio.json").write_text(json.dumps({"peak_value": PEAK, "updated_at": now.isoformat()}))
    return fake, items


def _cfg(fake_config):
    return replace(fake_config, trading=replace(fake_config.trading, momentum_weight=0.6,
                                                watchlist=list(fake_config.trading.sector_etfs)))


def _run(fake, cfg):
    from titantrade.executor import execute_trades
    with _patches(fake):
        return execute_trades(cfg)


def _invariants(fake: FakeBroker, items, tmp_state_dir, *, suspect=False):
    stops = {}
    for o in fake.open_orders():
        if o["side"] == "sell" and o["type"] in ("stop", "stop_limit"):
            stops.setdefault(o["symbol"], []).append(float(o["stop_price"]))
    plan_stop = {i["ticker"]: i["stop_price"] for i in items if i["action"] == "HOLD"}
    for sym, p in fake.pos.items():
        if sym in CORE or p["qty"] < 1 or sym not in plan_stop:
            continue
        assert stops.get(sym, []) == [plan_stop[sym]], f"I1/I2: {sym} has stops {stops.get(sym)} vs the plan's {plan_stop[sym]}"   # nothing bare, nothing doubled
    buys = [o["symbol"] for o in fake.placed if o["side"] == "buy" and o["symbol"] not in CORE]
    assert len(set(buys)) == len(buys) and not (set(buys) & fake.initial_positions), f"I2: duplicate or held-name buys {buys}"
    assert fake.cash >= 0, "I4: cash below zero"
    triggers = {t.get("trigger") for t in json.loads((tmp_state_dir / "trade_log.json").read_text())["trades"]}
    assert triggers <= PRESCRIBED, f"I4: unprescribed trigger {triggers - PRESCRIBED}"
    assert fake.http_calls == 0, "I6: a call escaped the fake broker"
    peak = json.loads((tmp_state_dir / "peak_portfolio.json").read_text())["peak_value"]
    if suspect:
        assert peak == PEAK, "I5: the peak learned a phantom"
        assert not fake.placed, f"I3: orders placed while the account value was suspect: {fake.placed}"


# --- the scenarios -----------------------------------------------------------

def test_s0_baseline_one_bracket_and_nothing_else(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir)
    trades = _run(fake, _cfg(fake_config))
    assert [t["ticker"] for t in trades] == ["XLC"] and fake.placed == [{"symbol": "XLC", "side": "buy", "type": "bracket", "qty": 166.0}]
    _invariants(fake, items, tmp_state_dir)


def test_s1_phantom_equity_down_blocks_entries_and_spares_the_peak(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir)
    fake.phantom_equity = 21_000.0                      # 79 % below the peak (July 2026)
    _run(fake, _cfg(fake_config))
    assert not [o for o in fake.placed if o["side"] == "buy" and o["symbol"] == "XLC"], "an entry was sized on phantom equity"
    assert json.loads((tmp_state_dir / "peak_portfolio.json").read_text())["peak_value"] == PEAK
    assert fake.http_calls == 0


def test_s1_phantom_equity_down_no_order_at_all(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir)
    fake.phantom_equity = 21_000.0
    _run(fake, _cfg(fake_config))
    _invariants(fake, items, tmp_state_dir, suspect=True)


def test_s2_phantom_equity_up_no_order_at_all(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir)
    fake.phantom_equity = 160_000.0
    _run(fake, _cfg(fake_config))
    _invariants(fake, items, tmp_state_dir, suspect=True)


def test_s3_phantom_low_mark_is_not_sold(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir)
    fake.marks["DXCM"] = 21.0                          # the CRWD split mark: a quarter of the market
    fake.quotes["DXCM"] = 84.0
    _run(fake, _cfg(fake_config))
    assert "DXCM" not in fake.sold and fake.pos["DXCM"]["qty"] == 100.0
    _invariants(fake, items, tmp_state_dir)


def test_s3b_phantom_high_mark_is_not_sold(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir)
    fake.marks["DXCM"] = 110.0                         # +37 % on the mark; the market is unchanged
    fake.quotes["DXCM"] = 84.0
    _run(fake, _cfg(fake_config))
    assert "DXCM" not in fake.sold, "sold on a mark the market does not confirm"
    _invariants(fake, items, tmp_state_dir)


def test_s4_split_like_gap_skips_with_an_announcement_and_sells_without(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir)
    fake.marks["DXCM"] = fake.quotes["DXCM"] = 20.0    # 72 % below the stop, confirmed by the quote
    fake.splits["DXCM"] = [{"new_rate": 4, "old_rate": 1}]
    _run(fake, _cfg(fake_config))
    assert "DXCM" not in fake.sold
    _invariants(fake, items, tmp_state_dir)
    fake2, items2 = _book(tmp_state_dir)
    fake2.marks["DXCM"] = fake2.quotes["DXCM"] = 20.0
    trades = _run(fake2, _cfg(fake_config))
    assert "DXCM" in fake2.sold and any(t["trigger"] == "gap_down_protection" for t in trades)
    _invariants(fake2, items2, tmp_state_dir)


def test_s5_vanished_stop_is_replaced_once(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir, drop_stop="DXCM")
    _run(fake, _cfg(fake_config))
    assert [o for o in fake.placed if o["type"] == "stop_limit"] == [{"symbol": "DXCM", "side": "sell", "type": "stop_limit", "qty": 100.0, "stop_price": 70.4}]
    _invariants(fake, items, tmp_state_dir)


def test_s6_refused_sell_after_a_settled_cancel_restores_the_stop(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir, uri_opened_days_ago=100)    # past the 60-trading-day clock
    fake.refuse_close["URI"] = 1
    trades = _run(fake, _cfg(fake_config))
    assert "URI" not in fake.sold and not any(t["ticker"] == "URI" for t in trades)
    assert [o["symbol"] for o in fake.placed if o["type"] == "stop_limit"] == ["URI"]      # the restore, at the plan level
    _invariants(fake, items, tmp_state_dir)


def test_s7_refused_cancel_leaves_the_one_stop_and_sells_nothing(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir, uri_opened_days_ago=100)
    fake.refuse_cancel = {o["id"] for o in fake.open_orders("URI")}
    _run(fake, _cfg(fake_config))
    assert "URI" not in fake.sold
    _invariants(fake, items, tmp_state_dir)


def test_s8_dead_network_places_nothing(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir)
    fake.dead = True
    with pytest.raises(ConnectionError):
        _run(fake, _cfg(fake_config))
    assert fake.placed == [] and fake.sold == []


def test_s9_pending_or_held_name_is_not_bought_again(fake_config, tmp_state_dir):
    fake, items = _book(tmp_state_dir, pending_xlc=True)
    _run(fake, _cfg(fake_config))
    assert not [o for o in fake.placed if o["side"] == "buy"]
    _invariants(fake, items, tmp_state_dir)
    fake2, items2 = _book(tmp_state_dir, hold_xlc=True)
    _run(fake2, _cfg(fake_config))
    assert not [o for o in fake2.placed if o["side"] == "buy"] and "XLC" not in fake2.sold   # a NEW item for a held name: neither bought nor orphaned
