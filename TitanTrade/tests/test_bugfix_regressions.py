"""Regression tests for the execution-safety bugs found in the 14-day log review.

Each class pins the fix for one production failure mode. All Alpaca calls are
mocked — zero real orders, zero token spend (see conftest).

Covered:
  1. TP1 partial-sell race left positions with NO stop  -> restore sizes off
     the live position; place_native_stop_loss clamps to broker-available qty.
  2. Pyramid market-buy rejected as a wash trade        -> tested in
     test_executor.py::TestPyramidIntoWinners (limit-buy mechanism).
  3. Gap-down protection 403'd on held qty              -> tested in
     test_gap_down.py (cancel settles before market sell).
  4. Fractional bracket (URI 0.19 shares) -> HTTP 422   -> here.
  5. Simultaneous brackets over-committed cash -> margin -> here + risk_manager.
  6. Stale data bundle (no daily fetch)                 -> tested in
     test_scheduler.py.
  6b. Analyst/executor downtrend conflict (HCA)         -> surfaced as near-miss.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from titantrade.broker import place_bracket_order, place_native_stop_loss
from titantrade.entries import (
    _handle_bullish_entry,
    open_buy_commitment,
    resubmit_expired_brackets,
)
from titantrade.positions import manage_trailing_stop


def _resp(data):
    r = MagicMock()
    r.json.return_value = data
    return r


# ---------------------------------------------------------------------------
# FIX 4: fractional bracket guard (production URI 0.19-share -> HTTP 422)
# ---------------------------------------------------------------------------

class TestBracketFractionalGuard:
    @patch("titantrade.broker.fetch_with_retry")
    def test_floors_fractional_qty_before_posting(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"id": "br-1", "status": "accepted"})
        place_bracket_order("AAPL", 5.9, 100.0, 95.0, 110.0, fake_config)
        body = mock_fetch.call_args.kwargs["json_body"]
        assert body["qty"] == "5.0"  # floored to whole shares

    def test_raises_when_floored_below_one_share(self, fake_config):
        # 0.19 shares (the URI bug) floors to 0 — unfillable as a bracket.
        with pytest.raises(ValueError, match="whole share"):
            place_bracket_order("URI", 0.19, 990.0, 922.0, 1046.0, fake_config)


class TestResubmitFractionalSkip:
    """End-to-end: when cash-reserve reduction sizes a resubmit below one whole
    share, skip cleanly instead of posting a fractional bracket (HTTP 422).
    """

    def _expired(self, ticker="URI"):
        return {
            "id": "exp-1", "symbol": ticker, "status": "expired",
            "order_class": "bracket", "side": "buy",
            "limit_price": "990.00", "qty": "1",
        }

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=None)
    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_positions", return_value=[])
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.get_account",
           return_value={"portfolio_value": "100000", "cash": "5100"})
    @patch("titantrade.entries.get_expired_brackets")
    def test_skips_when_sized_below_one_share(
        self, mock_expired, mock_account, mock_open, mock_pos, mock_bracket,
        mock_price, fake_config, tmp_state_dir, monkeypatch,
    ):
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Industrials")
        mock_expired.return_value = [self._expired("URI")]
        thesis_doc = {"theses": [{
            "ticker": "URI", "thesis": "BULLISH", "confidence": 0.72,
            "selected_for_trading": True, "review_action": "NEW",
            "target_entry_price": 990.0, "stop_loss_price": 922.0,
            "take_profit_price": 1046.0, "reasoning": "x",
        }]}
        # Cash 5100, portfolio 100k -> investable ~100, stock ~$990 -> <1 share.
        result = resubmit_expired_brackets(fake_config, thesis_doc, [], {})
        assert result == []
        mock_bracket.assert_not_called()  # no fractional bracket -> no 422


# ---------------------------------------------------------------------------
# FIX 1: TP1 restore sizes off the CURRENT position, never the stale qty
# ---------------------------------------------------------------------------

class TestTp1RestoreNeverLeavesBare:
    """Production FCX bug: TP1's breakeven-stop placement raced the partial
    sell's settlement, 403'd, and the restore handler re-requested the STALE
    pre-sell qty (also 403) — stranding the position with NO stop. The restore
    must re-read the live position and size the stop off that.
    """

    @patch("titantrade.positions.time.sleep", return_value=None)
    @patch("titantrade.positions._wait_for_order_canceled", return_value="filled")
    @patch("titantrade.positions.place_native_stop_loss")
    @patch("titantrade.positions.place_market_sell", return_value={"id": "tp1-sell"})
    @patch("titantrade.positions.cancel_all_orders_for_ticker", return_value=1)
    @patch("titantrade.positions.get_open_orders", return_value=[])
    @patch("titantrade.positions.get_position")
    def test_restore_uses_current_position_qty(
        self, mock_get_pos, mock_open, mock_cancel, mock_sell, mock_stop,
        mock_wait, mock_sleep, fake_config, tmp_state_dir,
    ):
        thesis = {
            "ticker": "FCX", "thesis": "BULLISH",
            "stop_loss_price": 60.0, "target_entry_price": 64.0,
            "take_profit_price": 72.0,
        }
        # entry 64, tp 72 -> TP1 trigger at 68. current 70 fires TP1.
        position = {"symbol": "FCX", "qty": "150", "avg_entry_price": "64.00",
                    "current_price": "70.00"}
        # The breakeven-stop placement fails (the race), forcing the restore
        # branch. Restore then succeeds using the re-read live qty (103).
        mock_stop.side_effect = [RuntimeError("403 insufficient qty"), {"id": "restored"}]
        mock_get_pos.return_value = {"symbol": "FCX", "qty": "103",
                                     "avg_entry_price": "64.00", "current_price": "70.00"}

        manage_trailing_stop("FCX", thesis, position, [], fake_config, stock_atr=2.0)

        # Two stop attempts: the racing breakeven (failed) + the restore.
        assert mock_stop.call_count == 2
        restore_call = mock_stop.call_args_list[1]
        # Restore sized off the CURRENT 103 shares (not the stale 150), thesis
        # stop — the position is protected, never bare.
        assert restore_call.args[0] == "FCX"
        assert float(restore_call.args[1]) == 103.0
        assert float(restore_call.args[2]) == 60.0


# ---------------------------------------------------------------------------
# FIX 5: committed-cash reserve keeps simultaneous entries out of margin
# ---------------------------------------------------------------------------

class TestOpenBuyCommitment:
    @patch("titantrade.entries.get_open_orders")
    def test_sums_pending_buy_notional(self, mock_orders, fake_config):
        mock_orders.return_value = [
            {"symbol": "GE", "side": "buy", "qty": "31", "limit_price": "318.00"},
            {"symbol": "FCX", "side": "buy", "qty": "155", "limit_price": "65.00"},
            {"symbol": "AAPL", "side": "sell", "qty": "10", "limit_price": "200.00"},
        ]
        total = open_buy_commitment(fake_config)
        assert total == pytest.approx(31 * 318.0 + 155 * 65.0)

    @patch("titantrade.entries.get_open_orders")
    def test_excludes_named_ticker(self, mock_orders, fake_config):
        mock_orders.return_value = [
            {"symbol": "GE", "side": "buy", "qty": "31", "limit_price": "318.00"},
            {"symbol": "FCX", "side": "buy", "qty": "155", "limit_price": "65.00"},
        ]
        total = open_buy_commitment(fake_config, exclude_ticker="GE")
        assert total == pytest.approx(155 * 65.0)

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=185.0)
    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_open_orders")
    def test_bullish_entry_blocked_by_committed_cash(
        self, mock_orders, mock_bracket, mock_price,
        fake_config, bullish_thesis, sample_positions, tmp_state_dir,
        monkeypatch,
    ):
        """$50k cash would normally clear the 5% reserve, but $48k is already
        committed to other pending buys -> only ~$2k free -> entry blocked.
        This is the guard against stacking brackets into negative cash."""
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Technology")
        # Minimal bundle -> "range" regime (no downtrend skip), so the entry
        # reaches the cash-reserve gate where committed cash blocks it.
        bundle = {"stocks": {"AAPL": {"technical_indicators": {"price_vs_sma": {}}, "atr_14": 3.0}}}
        mock_orders.return_value = [
            {"symbol": "NVDA", "side": "buy", "qty": "160", "limit_price": "300.00"},
        ]
        result = _handle_bullish_entry(
            ticker="AAPL", thesis=bullish_thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=sample_positions, data_bundle=bundle,
            sentry=None, cfg=fake_config,
        )
        assert result is None
        mock_bracket.assert_not_called()


# ---------------------------------------------------------------------------
# FIX 6b: analyst<->executor downtrend conflict surfaced as a near-miss
# ---------------------------------------------------------------------------

class TestDowntrendNearMiss:
    """HCA case: the weekly analyst keeps selecting a BULLISH ticker the
    technical trend gate refuses to bottom-fish. Instead of silently burning
    the selection slot every cycle, record the conflict as a near-miss so it
    surfaces on the dashboard.
    """

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=96.0)
    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_open_orders", return_value=[])
    def test_downtrend_selected_ticker_records_near_miss(
        self, mock_orders, mock_bracket, mock_price,
        fake_config, sample_positions, tmp_state_dir, monkeypatch,
    ):
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Healthcare")
        thesis = {
            "ticker": "HCA", "thesis": "BULLISH", "confidence": 0.70,
            "selected_for_trading": True, "review_action": "NEW",
            "target_entry_price": 100.0, "stop_loss_price": 94.0,
            "take_profit_price": 115.0, "reasoning": "fundamentals strong",
        }
        bundle = {"stocks": {"HCA": {"technical_indicators": {"price_vs_sma": {
            "above_sma_50": False, "above_sma_200": False,
            "golden_cross": False, "pct_from_sma_50": -5.0,
            "sma_20": 105.0, "sma_50": 110.0,
        }}, "atr_14": 2.0}}}
        result = _handle_bullish_entry(
            ticker="HCA", thesis=thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=sample_positions, data_bundle=bundle,
            sentry=None, cfg=fake_config,
        )
        assert result is None
        mock_bracket.assert_not_called()
        nm_path = tmp_state_dir / "near_misses.json"
        assert nm_path.exists()
        data = json.loads(nm_path.read_text())
        rec = data["near_misses"][-1]
        assert rec["ticker"] == "HCA"
        assert rec["failed_gates"] == ["trend_regime"]


# ---------------------------------------------------------------------------
# FIX 7: fractional-dust stops (JPM 0.13 / ANET daily 422 in the 9-day review)
# ---------------------------------------------------------------------------

class TestFractionalDustStop:
    """place_native_stop_loss must floor fractional quantities to whole shares
    (Alpaca 422s "fractional orders must be DAY orders" on ANY fractional stop,
    and the plain-stop fallback shared the same tif) and place NOTHING for
    sub-1-share dust — instead of erroring on every executor run (the JPM
    0.13-share and ANET remainders that spammed [ERROR] daily in production).
    """

    @patch("titantrade.broker.fetch_with_retry")
    def test_floors_fractional_qty_to_whole_shares(self, mock_fetch, fake_config):
        mock_fetch.return_value = _resp({"id": "stop-1", "status": "accepted"})
        place_native_stop_loss("GE", 5.7, 344.0, fake_config)
        body = mock_fetch.call_args.kwargs["json_body"]
        assert body["qty"] == "5.0"            # floored, not 5.7 -> no 422
        assert body["time_in_force"] == "gtc"  # still a persistent stop

    @patch("titantrade.broker.fetch_with_retry")
    def test_sub_one_share_dust_places_no_order(self, mock_fetch, fake_config):
        # JPM 0.13-share remainder: unstoppable dust -> no broker call, no 422.
        result = place_native_stop_loss("JPM", 0.13, 314.5, fake_config)
        assert result == {}
        mock_fetch.assert_not_called()


# ---------------------------------------------------------------------------
# FIX 8: tranche2 dip-buy reused tranche1's stop -> 422 on tight-stop theses
# ---------------------------------------------------------------------------

class TestTranche2TightStopSkip:
    """The 2-tranche entry places tranche2 at entry*0.985 but reuses tranche1's
    stop. When the stop is within ~1.5% of entry (tight-stop theses on
    high-priced/low-vol names like EQIX $1050), tranche2's lower limit lands at
    or below the stop and Alpaca 422s ("stop_price must be <= base_price -
    0.01"). tranche1 must still place; tranche2 must be skipped, not error.
    """

    def _thesis(self, entry, stop, tp):
        return {
            "ticker": "EQIX", "thesis": "BULLISH", "confidence": 0.70,
            "selected_for_trading": True, "review_action": "NEW",
            "target_entry_price": entry, "stop_loss_price": stop,
            "take_profit_price": tp, "reasoning": "tight stop",
            "thesis_breach_condition": "x",
        }

    def _bundle(self):
        # No SMA data -> "range" regime; current_price patched to None ->
        # adapt_entry_levels is a no-op, so entry/stop stay exactly as set.
        return {
            "market_context": {"vix": {"level": 16.0, "classification": "normal"}},
            "stocks": {"EQIX": {
                "atr_14": 5.0,
                "technical_indicators": {},
                "earnings": {"is_blocked": False},
            }},
        }

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=None)
    @patch("titantrade.entries._ensure_gtc_stop_on_fill", return_value=None)
    @patch("titantrade.entries.place_bracket_order", return_value={"id": "br"})
    @patch("titantrade.entries.get_open_orders", return_value=[])
    def test_skips_tranche2_when_stop_within_dip(
        self, mock_orders, mock_bracket, mock_ensure, mock_price,
        fake_config, sample_positions, monkeypatch, tmp_state_dir,
    ):
        monkeypatch.setattr(
            "titantrade.risk_manager.get_stock_sector", lambda t: "Technology")
        # entry 200, stop 197 (1.5%): tranche2 limit = 197.00, stop 197 >=
        # 196.99 -> tranche2 invalid; tranche1 (stop 197 < 199.99) valid.
        result = _handle_bullish_entry(
            ticker="EQIX", thesis=self._thesis(200.0, 197.0, 215.0),
            portfolio_value=100_000, cash_balance=60_000,
            positions=sample_positions, data_bundle=self._bundle(),
            sentry=None, cfg=fake_config,
        )
        assert result is not None
        assert mock_bracket.call_count == 1  # tranche1 only, tranche2 skipped

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=None)
    @patch("titantrade.entries._ensure_gtc_stop_on_fill", return_value=None)
    @patch("titantrade.entries.place_bracket_order", return_value={"id": "br"})
    @patch("titantrade.entries.get_open_orders", return_value=[])
    def test_places_both_tranches_when_stop_clears_dip(
        self, mock_orders, mock_bracket, mock_ensure, mock_price,
        fake_config, sample_positions, monkeypatch, tmp_state_dir,
    ):
        monkeypatch.setattr(
            "titantrade.risk_manager.get_stock_sector", lambda t: "Technology")
        # entry 200, stop 195 (2.5%): tranche2 limit 197.00, stop 195 < 196.99
        # -> tranche2 valid; both tranches place.
        result = _handle_bullish_entry(
            ticker="EQIX", thesis=self._thesis(200.0, 195.0, 230.0),
            portfolio_value=100_000, cash_balance=60_000,
            positions=sample_positions, data_bundle=self._bundle(),
            sentry=None, cfg=fake_config,
        )
        assert result is not None
        assert mock_bracket.call_count == 2  # both tranches placed
