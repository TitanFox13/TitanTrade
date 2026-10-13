"""Trade log, near misses, archival, opening-buy lookups."""

from __future__ import annotations

import json

from titantrade.trade_state import (
    MAX_LIVE_TRADES, _append_trade, _build_near_miss_record, _build_trade_context,
    position_entry_stop, position_opened_at,
)

BEFORE = "2026-10-02T14:15:00+00:00"
AFTER = "2026-10-09T19:30:00+00:00"


def _log(state_dir, *records):
    (state_dir / "trade_log.json").write_text(json.dumps({"trades": list(records)}))


def _buy(ticker, ts, stop, trigger="entry", key="stop_price"):
    return {"ticker": ticker, "action": "BUY", "timestamp": ts, key: stop, "trigger": trigger, "shares": 5}


class TestOpeningBuy:
    def test_latest_entry_buy_wins_and_pyramid_adds_are_skipped(self, tmp_state_dir):
        _log(tmp_state_dir, _buy("EQIX", BEFORE, 969.95), _buy("EQIX", AFTER, 1000.0, trigger="pyramid"))
        assert position_opened_at("EQIX") == BEFORE
        assert position_entry_stop("EQIX") == 969.95

    def test_reads_pre_rename_records_and_handles_unknowns(self, tmp_state_dir):
        _log(tmp_state_dir, _buy("FCX", BEFORE, 69.6, key="stop_loss_price"), {"ticker": "GE", "action": "BUY", "timestamp": BEFORE})
        assert position_entry_stop("FCX") == 69.6
        assert position_entry_stop("GE") is None and position_entry_stop("NOPE") is None
        assert position_opened_at("NOPE") is None


class TestArchival:
    def test_trade_log_archives_overflow(self, tmp_state_dir):
        for i in range(MAX_LIVE_TRADES + 5):
            _append_trade({"id": f"t{i}", "ticker": "AAPL", "action": "BUY", "shares": 1, "price": 100.0, "timestamp": "2026-01-01T00:00:00+00:00", "trigger": "t", "reasoning": "t"})
        assert len(json.loads((tmp_state_dir / "trade_log.json").read_text())["trades"]) == MAX_LIVE_TRADES
        assert list((tmp_state_dir / "archive").glob("trade_log.*.json"))


class TestRecordBuilders:
    def test_trade_context_and_near_miss(self):
        bundle = {"market_context": {"spy": {"return_5d": 0.4}, "breadth": {"pct": 0.45}},
                  "stocks": {"AAA": {"signal_inputs": {"close": 88.0, "high_lookback": 100.0, "sma_trend": 85.0}, "atr_14": 2.1, "sector": "Technology", "earnings": {"days_until_earnings": 12}}}}
        ctx = _build_trade_context("AAA", bundle)
        assert ctx["close"] == 88.0 and ctx["sector"] == "Technology" and ctx["sector_breadth"] == 0.45 and ctx["earnings_days_away"] == 12
        nm = _build_near_miss_record({"ticker": "AAA", "dip_pct": 0.12, "entry_price": 88.0, "stop_price": 77.4, "target_price": 105.6, "reason": "dip"}, ["cash_reserve"], {"cash_reserve": {"passed": False, "detail": "x"}}, ctx)
        assert nm["ticker"] == "AAA" and nm["total_gates_failed"] == 1 and nm["context"]["close"] == 88.0
