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


# ---------------------------------------------------------------------------
# ADR 055 fix 1: resubmission skips tickers with a current-run sentry ABORT
# ---------------------------------------------------------------------------

class TestResubmitSameRunAbortSkip:
    """Production 2026-07-31: the sentry wrote LLY ABORT at 14:15:04, the
    resubmit path bought a 12-share LLY bracket at 14:15:27, and the abort
    handler market-sold it at 14:15:45 — an 18-second forced round-trip. The
    72h cooldown can't prevent this because it's recorded when the abort is
    HANDLED, which happens *after* resubmission runs — so the resubmit path
    must check the signal itself.
    """

    def _expired(self, ticker="LLY"):
        return {
            "id": "exp-1", "symbol": ticker, "status": "expired",
            "order_class": "bracket", "side": "buy",
            "limit_price": "1124.00", "qty": "12",
        }

    def _thesis_doc(self, ticker="LLY"):
        return {"theses": [{
            "ticker": ticker, "thesis": "BULLISH", "confidence": 0.75,
            "selected_for_trading": True, "review_action": "NEW",
            "target_entry_price": 1124.0, "stop_loss_price": 1092.0,
            "take_profit_price": 1272.0, "reasoning": "x",
        }]}

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=None)
    @patch("titantrade.entries._ensure_gtc_stop_on_fill", return_value=None)
    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_positions", return_value=[])
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.get_account",
           return_value={"portfolio_value": "100000", "cash": "60000"})
    @patch("titantrade.entries.get_expired_brackets")
    def test_skips_resubmit_when_current_signal_is_abort(
        self, mock_expired, mock_account, mock_open, mock_pos, mock_bracket,
        mock_ensure, mock_price, fake_config, tmp_state_dir, monkeypatch,
    ):
        from tests.conftest import write_state_file
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Healthcare")
        mock_expired.return_value = [self._expired("LLY")]
        write_state_file(tmp_state_dir, "sentry_signals.json", {
            "signals": [{"ticker": "LLY", "signal": "ABORT",
                         "reasoning": "news-confirmed -4.3% adverse move"}],
        })
        result = resubmit_expired_brackets(fake_config, self._thesis_doc(), [], {})
        assert result == []
        mock_bracket.assert_not_called()

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=None)
    @patch("titantrade.entries._ensure_gtc_stop_on_fill", return_value=None)
    @patch("titantrade.entries.place_bracket_order", return_value={"id": "br"})
    @patch("titantrade.entries.get_positions", return_value=[])
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.get_account",
           return_value={"portfolio_value": "100000", "cash": "60000"})
    @patch("titantrade.entries.get_expired_brackets")
    def test_resubmits_when_current_signal_is_continue(
        self, mock_expired, mock_account, mock_open, mock_pos, mock_bracket,
        mock_ensure, mock_price, fake_config, tmp_state_dir, monkeypatch,
    ):
        from tests.conftest import write_state_file
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Healthcare")
        mock_expired.return_value = [self._expired("LLY")]
        write_state_file(tmp_state_dir, "sentry_signals.json", {
            "signals": [{"ticker": "LLY", "signal": "CONTINUE", "reasoning": "clear"}],
        })
        result = resubmit_expired_brackets(fake_config, self._thesis_doc(), [], {})
        assert len(result) == 1
        mock_bracket.assert_called_once()

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=None)
    @patch("titantrade.entries.place_bracket_order")
    def test_bullish_entry_defends_against_abort_signal(
        self, mock_bracket, mock_price, fake_config, tmp_state_dir,
    ):
        # Unreachable from the executor loop (it dispatches ABORT first), but
        # any other caller must get the same never-enter-on-ABORT guarantee.
        result = _handle_bullish_entry(
            ticker="LLY",
            thesis={"ticker": "LLY", "thesis": "BULLISH", "confidence": 0.75,
                    "target_entry_price": 1124.0, "stop_loss_price": 1092.0,
                    "take_profit_price": 1272.0},
            portfolio_value=100_000, cash_balance=60_000, positions=[],
            data_bundle={}, sentry={"ticker": "LLY", "signal": "ABORT"},
            cfg=fake_config,
        )
        assert result is None
        mock_bracket.assert_not_called()


# ---------------------------------------------------------------------------
# ADR 055 fix 2: minimum stop-distance floor (noise-level stops refused)
# ---------------------------------------------------------------------------

class TestMinStopDistanceFloor:
    """Production 2026-07-31: URI entered at $1084.25 with a $1081.25 stop —
    0.28% below entry, inside ordinary intraday noise — and the GTC stop
    tagged out 27 minutes after the fill. Entry validation must refuse stops
    closer than MIN_STOP_DISTANCE_PCT; the analyst's thesis is treated as
    position-management levels, not a fresh-entry setup.
    """

    def test_stop_too_tight_flags_noise_level_stop(self):
        from titantrade.pricing import stop_too_tight
        # The URI production case: 0.28% distance.
        assert stop_too_tight(1084.25, 1081.25) is not None
        # Just inside the floor.
        assert stop_too_tight(100.0, 98.51) is not None

    def test_stop_too_tight_accepts_normal_stops(self):
        from titantrade.pricing import stop_too_tight
        assert stop_too_tight(100.0, 98.5) is None   # exactly 1.5% passes
        assert stop_too_tight(100.0, 95.0) is None   # typical 5% stop
        assert stop_too_tight(None, 95.0) is None    # missing entry
        assert stop_too_tight(100.0, None) is None   # missing stop
        # Stop at/above entry is bracket_levels_invalid's job, not ours.
        assert stop_too_tight(100.0, 101.0) is None

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=None)
    @patch("titantrade.entries.place_bracket_order")
    def test_bullish_entry_refuses_tight_stop(
        self, mock_bracket, mock_price, fake_config, tmp_state_dir,
    ):
        result = _handle_bullish_entry(
            ticker="URI",
            thesis={"ticker": "URI", "thesis": "BULLISH", "confidence": 0.68,
                    "target_entry_price": 1085.0, "stop_loss_price": 1082.0,
                    "take_profit_price": 1250.0},
            portfolio_value=100_000, cash_balance=60_000, positions=[],
            data_bundle={}, sentry=None, cfg=fake_config,
        )
        assert result is None
        mock_bracket.assert_not_called()

    @patch("titantrade.daily_sentry._fetch_current_price", return_value=None)
    @patch("titantrade.entries._ensure_gtc_stop_on_fill", return_value=None)
    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.entries.get_positions", return_value=[])
    @patch("titantrade.entries.get_open_orders", return_value=[])
    @patch("titantrade.entries.get_account",
           return_value={"portfolio_value": "100000", "cash": "60000"})
    @patch("titantrade.entries.get_expired_brackets")
    def test_resubmit_refuses_tight_stop(
        self, mock_expired, mock_account, mock_open, mock_pos, mock_bracket,
        mock_ensure, mock_price, fake_config, tmp_state_dir, monkeypatch,
    ):
        monkeypatch.setattr("titantrade.risk_manager.get_stock_sector", lambda t: "Industrials")
        mock_expired.return_value = [{
            "id": "exp-1", "symbol": "URI", "status": "expired",
            "order_class": "bracket", "side": "buy",
            "limit_price": "1085.00", "qty": "6",
        }]
        thesis_doc = {"theses": [{
            "ticker": "URI", "thesis": "BULLISH", "confidence": 0.68,
            "selected_for_trading": True, "review_action": "NEW",
            "target_entry_price": 1085.0, "stop_loss_price": 1082.0,
            "take_profit_price": 1250.0, "reasoning": "x",
        }]}
        result = resubmit_expired_brackets(fake_config, thesis_doc, [], {})
        assert result == []
        mock_bracket.assert_not_called()


# ---------------------------------------------------------------------------
# ADR 056 fix 1: broker-side stop-outs start a re-entry cooldown
# ---------------------------------------------------------------------------

class TestStopOutCooldown:
    """Production 2026-08-04: DVN's GTC stop filled at the open (13:34 UTC)
    and the 14:15 run re-bought the ticker 42 minutes later. ABORT exits
    record a cooldown when handled, but a protective stop fills broker-side
    with nothing of ours running — the scan closes that asymmetry. The clock
    is stamped at the FILL time so re-scanning the same fill is idempotent.
    """

    def _closed_order(self, **overrides):
        from datetime import datetime, timedelta, timezone
        base = {
            "symbol": "DVN", "side": "sell", "type": "stop_limit",
            "status": "filled",
            "filled_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "filled_avg_price": "43.42", "stop_price": "43.50",
        }
        base.update(overrides)
        return base

    @patch("titantrade.entries.fetch_with_retry")
    def test_records_cooldown_for_recent_stop_fill(
        self, mock_fetch, fake_config, tmp_state_dir,
    ):
        from titantrade.entries import record_stop_out_cooldowns
        from titantrade.cooldown import _is_in_cooldown
        mock_fetch.return_value = _resp([self._closed_order()])
        assert record_stop_out_cooldowns(fake_config) == 1
        in_cd, hours = _is_in_cooldown("DVN")
        assert in_cd
        assert 1.5 < hours < 2.5  # clock anchored at the FILL time, not now()

    @patch("titantrade.entries.fetch_with_retry")
    def test_handles_alpaca_z_suffix_timestamps(
        self, mock_fetch, fake_config, tmp_state_dir,
    ):
        from datetime import datetime, timedelta, timezone
        from titantrade.entries import record_stop_out_cooldowns
        from titantrade.cooldown import _is_in_cooldown
        z_stamp = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime(
            "%Y-%m-%dT%H:%M:%S.%f") + "Z"
        mock_fetch.return_value = _resp([self._closed_order(filled_at=z_stamp)])
        assert record_stop_out_cooldowns(fake_config) == 1
        in_cd, hours = _is_in_cooldown("DVN")
        assert in_cd and 2.5 < hours < 3.5

    @patch("titantrade.entries.fetch_with_retry")
    def test_idempotent_across_runs(self, mock_fetch, fake_config, tmp_state_dir):
        from titantrade.entries import record_stop_out_cooldowns
        from titantrade.cooldown import _is_in_cooldown
        mock_fetch.return_value = _resp([self._closed_order()])
        assert record_stop_out_cooldowns(fake_config) == 1
        # Second scan sees the same fill: no new record, clock NOT re-stamped.
        assert record_stop_out_cooldowns(fake_config) == 0
        _, hours = _is_in_cooldown("DVN")
        assert hours > 1.5  # still anchored at the original fill time

    @patch("titantrade.entries.fetch_with_retry")
    def test_ignores_old_and_non_stop_fills(
        self, mock_fetch, fake_config, tmp_state_dir,
    ):
        from datetime import datetime, timedelta, timezone
        from titantrade.entries import record_stop_out_cooldowns
        from titantrade.cooldown import _is_in_cooldown
        old_fill = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
        mock_fetch.return_value = _resp([
            self._closed_order(symbol="URI", filled_at=old_fill),   # outside window
            self._closed_order(symbol="LLY", type="market"),        # abort/TP1 sell
            self._closed_order(symbol="GE", side="buy"),            # buy-side stop
            self._closed_order(symbol="FCX", status="canceled", filled_at=None),
        ])
        assert record_stop_out_cooldowns(fake_config) == 0
        for ticker in ("URI", "LLY", "GE", "FCX"):
            assert _is_in_cooldown(ticker) == (False, 0.0)

    @patch("titantrade.entries.fetch_with_retry", side_effect=RuntimeError("api down"))
    def test_scan_failure_returns_zero_never_raises(
        self, mock_fetch, fake_config, tmp_state_dir,
    ):
        from titantrade.entries import record_stop_out_cooldowns
        assert record_stop_out_cooldowns(fake_config) == 0


# ---------------------------------------------------------------------------
# ADR 056 fix 2: ADJUST levels don't apply to a position opened after review
# ---------------------------------------------------------------------------

class TestAdjustStaleReviewGuard:
    """Production 2026-08-04/05: the analyst's ADJUST stop ($43.50, computed
    Sunday for the OLD 217-share DVN position) was re-applied to a NEW
    position entered at $43.65 after the old one stopped out — a 0.34% stop
    that tagged out the next morning. ``position_opened_after`` is the guard
    the executor's Section 4a now consults before applying ADJUST levels
    (inline-pattern wiring, same as TestAdjustStopSafety).
    """

    GEN = "2026-08-16T20:07:00+00:00"

    def _buy(self, ticker, ts, trigger="weekly_thesis"):
        return {"ticker": ticker, "action": "BUY", "trigger": trigger,
                "timestamp": ts, "shares": 10, "price": 43.65}

    def _write_log(self, state_dir, *records):
        from tests.conftest import write_state_file
        write_state_file(state_dir, "trade_log.json", {"trades": list(records)})

    def test_true_when_position_reopened_after_review(self, tmp_state_dir):
        from titantrade.trade_state import position_opened_after
        self._write_log(tmp_state_dir, self._buy("DVN", "2026-08-17T14:15:00+00:00"))
        assert position_opened_after("DVN", self.GEN) is True

    def test_false_when_position_predates_review(self, tmp_state_dir):
        from titantrade.trade_state import position_opened_after
        self._write_log(tmp_state_dir, self._buy("DVN", "2026-08-14T14:15:00+00:00"))
        assert position_opened_after("DVN", self.GEN) is False

    def test_pyramid_add_does_not_count_as_reopen(self, tmp_state_dir):
        from titantrade.trade_state import position_opened_after
        # Entry predates the review; a pyramid ADD after it merely enlarged
        # the reviewed position — the ADJUST levels still apply.
        self._write_log(
            tmp_state_dir,
            self._buy("GE", "2026-08-10T14:15:00+00:00"),
            self._buy("GE", "2026-08-17T19:30:00+00:00", trigger="pyramid"),
        )
        assert position_opened_after("GE", self.GEN) is False

    def test_fails_open_on_missing_data(self, tmp_state_dir):
        from titantrade.trade_state import position_opened_after
        # No trade log at all -> can't tell -> apply ADJUST as before.
        assert position_opened_after("DVN", self.GEN) is False
        # No generated_at -> same.
        self._write_log(tmp_state_dir, self._buy("DVN", "2026-08-17T14:15:00+00:00"))
        assert position_opened_after("DVN", None) is False
        assert position_opened_after("DVN", "not-a-timestamp") is False

    def test_fails_open_on_malformed_buy_timestamp(self, tmp_state_dir):
        from titantrade.trade_state import position_opened_after
        self._write_log(tmp_state_dir, self._buy("DVN", "garbage"))
        assert position_opened_after("DVN", self.GEN) is False


# ---------------------------------------------------------------------------
# ADR 058 fix 1: ADJUST stop measured against the LIVE price (Decision 055 floor)
# ---------------------------------------------------------------------------

class TestAdjustLivePriceFloor:
    """Production 2026-09-14: the Sunday review raised ANET's stop $181 → $191
    (1.29×ATR below the $199.74 Friday close). The Monday 14:15 UTC run placed
    it while ANET traded $189.82 — the fresh stop-limit filled the same second
    at $189.91; ANET closed $205 a week later. Section 4a now measures the
    analyst's level against the live mark (``pricing.adjust_stop_too_tight``)
    and keeps the existing stop when the raise is at/inside the 1.5% floor.
    End-to-end wiring is covered in test_executor.TestAdjustLivePriceFloorEndToEnd.
    """

    def test_stop_at_or_above_live_price_is_refused(self):
        from titantrade.pricing import adjust_stop_too_tight
        reason = adjust_stop_too_tight(189.82, 191.0)
        assert reason and "at/above the live price" in reason
        assert adjust_stop_too_tight(191.0, 191.0)  # equal counts too

    def test_stop_inside_floor_is_refused(self):
        from titantrade.pricing import adjust_stop_too_tight
        reason = adjust_stop_too_tight(200.0, 198.0)  # 1.0% below
        assert reason and "1.00% below the live price" in reason

    def test_stop_at_or_beyond_floor_is_accepted(self):
        from titantrade.pricing import adjust_stop_too_tight
        assert adjust_stop_too_tight(200.0, 197.0) is None    # exactly 1.5%
        assert adjust_stop_too_tight(200.0, 190.0) is None
        assert adjust_stop_too_tight(199.74, 181.0) is None   # ANET's pre-review stop

    def test_fails_open_without_prices(self):
        from titantrade.pricing import adjust_stop_too_tight
        assert adjust_stop_too_tight(None, 191.0) is None
        assert adjust_stop_too_tight(189.82, None) is None
        assert adjust_stop_too_tight(0, 191.0) is None
        assert adjust_stop_too_tight(189.82, 0) is None

    def test_position_live_price_helper(self):
        from titantrade.executor import _position_live_price
        assert _position_live_price({"current_price": "189.82"}) == 189.82
        assert _position_live_price({"current_price": 205.0}) == 205.0
        assert _position_live_price({"current_price": "0"}) is None
        assert _position_live_price({"current_price": "n/a"}) is None
        assert _position_live_price({}) is None
        assert _position_live_price(None) is None


# ---------------------------------------------------------------------------
# ADR 058 fix 2: weekly review "Days held" comes from the trade log, not 0
# ---------------------------------------------------------------------------

class TestReviewDaysHeld:
    """Production: every weekly review logged ``(…, 0d held)`` and every review
    prompt said "Days held: 0" — broker positions carry no entry date and
    per-ticker theses no ``generated_at``, so the fallback chain always yielded
    0. ``trade_state.position_opened_at`` resolves the opening BUY instead.
    """

    def _buy(self, ticker, ts, trigger="weekly_thesis"):
        return {"ticker": ticker, "action": "BUY", "trigger": trigger,
                "timestamp": ts, "shares": 10, "price": 200.0}

    def _write_log(self, state_dir, *records):
        from tests.conftest import write_state_file
        write_state_file(state_dir, "trade_log.json", {"trades": list(records)})

    def test_latest_entry_buy_wins_and_pyramid_is_skipped(self, tmp_state_dir):
        from titantrade.trade_state import position_opened_at
        self._write_log(
            tmp_state_dir,
            self._buy("ANET", "2026-09-01T14:15:00+00:00"),
            {"ticker": "ANET", "action": "SELL", "timestamp": "2026-09-14T14:15:38+00:00"},
            self._buy("ANET", "2026-09-21T14:15:00+00:00", trigger="bracket_resubmission"),
            self._buy("ANET", "2026-09-22T19:30:00+00:00", trigger="pyramid"),
            self._buy("CRWD", "2026-09-23T14:15:00+00:00"),
        )
        assert position_opened_at("ANET") == "2026-09-21T14:15:00+00:00"
        assert position_opened_at("CRWD") == "2026-09-23T14:15:00+00:00"

    def test_none_when_unknown(self, tmp_state_dir):
        from titantrade.trade_state import position_opened_at
        assert position_opened_at("ANET") is None            # no log at all
        self._write_log(tmp_state_dir, {"ticker": "ANET", "action": "BUY", "timestamp": ""})
        assert position_opened_at("ANET") is None            # empty timestamp
        assert position_opened_at("ZZZ") is None             # never traded

    def test_position_opened_after_still_agrees(self, tmp_state_dir):
        # The ADR 056 guard now shares the lookup — behaviour must be unchanged.
        from titantrade.trade_state import position_opened_after
        self._write_log(tmp_state_dir, self._buy("DVN", "2026-08-17T14:15:00+00:00"))
        assert position_opened_after("DVN", "2026-08-16T20:07:00+00:00") is True
        assert position_opened_after("DVN", "2026-08-18T20:07:00+00:00") is False
        assert position_opened_after("DVN", None) is False

    def test_days_held_from(self):
        from datetime import datetime, timezone
        from titantrade.weekly_analyst import _days_held_from
        now = datetime(2026, 9, 20, 20, 0, tzinfo=timezone.utc)
        assert _days_held_from("2026-09-13T14:15:00+00:00", now) == 7
        assert _days_held_from("2026-09-13T14:15:00Z", now) == 7
        assert _days_held_from("2026-09-13T14:15:00", now) == 7       # naive → UTC
        assert _days_held_from("2026-09-01", now) == 19                # date-only
        assert _days_held_from("2026-09-25T00:00:00+00:00", now) == 0  # future → clamp
        assert _days_held_from(None, now) == 0
        assert _days_held_from("", now) == 0
        assert _days_held_from("garbage", now) == 0

    def test_review_prompt_carries_real_days_held(self, tmp_state_dir, fake_config):
        from datetime import datetime, timedelta, timezone
        from titantrade import weekly_analyst as wa
        opened = (datetime.now(timezone.utc) - timedelta(days=7, hours=2)).isoformat()
        self._write_log(tmp_state_dir, self._buy("ANET", opened))
        captured: dict[str, str] = {}

        def _fake_claude(system, prompt, cfg, cost_label=""):
            captured["prompt"] = prompt
            return json.dumps({
                "ticker": "ANET", "thesis": "BULLISH", "confidence": 0.7,
                "review_action": "CONTINUE", "stop_loss_price": 181.0,
                "take_profit_price": 221.0, "target_entry_price": 199.0,
                "thesis_breach_condition": "x", "reasoning": "y",
            })

        with patch("titantrade.weekly_analyst._call_claude", side_effect=_fake_claude):
            wa.review_position(
                "ANET",
                {"ticker": "ANET", "thesis": "BULLISH", "confidence": 0.7,
                 "stop_loss_price": 181.0, "take_profit_price": 221.0},
                {"symbol": "ANET", "avg_entry_price": "192.8", "current_price": "199.74"},
                {}, {"market_regime": "neutral"}, "", fake_config,
            )
        assert "Days held: 7" in captured["prompt"]


# ---------------------------------------------------------------------------
# ADR 058 fix 4b: benchmark fetches SPY from the SIP feed (today's bar present)
# ---------------------------------------------------------------------------

class TestBenchmarkSpySipFeed:
    """Production: ``benchmark_metrics.json`` computed at 20:30 UTC always
    ended one session early because IEX's daily bar for the session is not
    published yet at that time (SIP has it minutes after the close). The
    free plan refuses SIP queries reaching into the last 15 minutes, so the
    SIP path uses a timestamp end bound ≥16 min in the past.
    """

    class _Resp:
        def json(self):
            return {"bars": [], "next_page_token": None}

    def test_native_sip_uses_lagged_timestamp_end(self, fake_config):
        from datetime import datetime, timezone
        from titantrade.data_providers import native
        seen: dict = {}

        def _fake(method, url, headers=None, params=None, **kw):
            seen.update(params)
            return self._Resp()

        with patch("titantrade.data_providers.native.fetch_with_retry", side_effect=_fake):
            native.get_ohlcv("SPY", fake_config, days=10, feed="sip")
        assert seen["feed"] == "sip"
        end = datetime.strptime(seen["end"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        lag_min = (datetime.now(timezone.utc) - end).total_seconds() / 60
        assert 15.5 <= lag_min <= 20

    def test_native_default_feed_keeps_date_end(self, fake_config):
        from datetime import datetime, timezone
        from titantrade.data_providers import native
        seen: dict = {}

        def _fake(method, url, headers=None, params=None, **kw):
            seen.update(params)
            return self._Resp()

        with patch("titantrade.data_providers.native.fetch_with_retry", side_effect=_fake):
            native.get_ohlcv("SPY", fake_config, days=10)
        assert seen["feed"] == fake_config.alpaca.data_feed
        assert seen["end"] == datetime.now(timezone.utc).date().isoformat()

    def test_benchmark_requests_sip(self, fake_config):
        from titantrade.benchmark import _spy_close_series
        with patch("titantrade.market_data.get_ohlcv", return_value=[]) as m:
            _spy_close_series(fake_config, days=5)
        assert m.call_args.kwargs.get("feed") == "sip"

    def test_fmp_provider_accepts_feed_kwarg(self, fake_config):
        # market_data passes ``feed`` provider-agnostically; FMP must tolerate it.
        import inspect
        from titantrade.data_providers import fmp
        assert "feed" in inspect.signature(fmp.get_ohlcv).parameters


# ---------------------------------------------------------------------------
# ADR 059 fix 1: the cooldown override measures "recovered" against the EXIT
# price, not only the thesis stop
# ---------------------------------------------------------------------------

class TestCooldownOverrideExitPrice:
    """Measured against the thesis stop alone, "recovered" was satisfied by
    nearly every exit (both a 3–5% abort and a stop-out leave the price above
    the stop), so the 72h cooldown was effectively 24h and the system re-bought
    the same names at the same price a day later. Of the 23 override-population
    re-entries Jul 8 → Sep 28 2026, the 10 that came in < 1% above the exit all
    lost (−$767); the 13 ≥ 1% above kept every winner (+$2,250). The cooldown
    record now carries the exit price and the override requires the current
    price ≥ exit × (1 + COOLDOWN_RECOVERY_PCT). Records without one (pre-059)
    keep the thesis-stop test only.
    """

    def _thesis(self, **overrides):
        base = {
            "ticker": "JPM", "thesis": "BULLISH",
            "selected_for_trading": True,
            "stop_loss_price": 330.0,
        }
        base.update(overrides)
        return base

    def test_abort_record_stores_exit_price(self, tmp_state_dir):
        from titantrade.cooldown import _record_abort_cooldown, cooldown_exit_price
        _record_abort_cooldown("JPM", "sentry abort", exit_price=342.89)
        assert cooldown_exit_price("JPM") == pytest.approx(342.89)
        saved = json.loads((tmp_state_dir / "abort_cooldown.json").read_text())
        assert saved["JPM"]["exit_price"] == pytest.approx(342.89)

    def test_abort_record_without_price_stores_none(self, tmp_state_dir):
        from titantrade.cooldown import _record_abort_cooldown, cooldown_exit_price
        _record_abort_cooldown("JPM", "sentry abort")            # legacy call shape
        _record_abort_cooldown("GE", "sentry abort", exit_price=0)  # unusable mark
        assert cooldown_exit_price("JPM") is None
        assert cooldown_exit_price("GE") is None
        assert cooldown_exit_price("NOPE") is None

    def test_stop_out_record_stores_exit_price(self, tmp_state_dir):
        from datetime import datetime, timedelta, timezone
        from titantrade.cooldown import _record_stop_out_cooldown, cooldown_exit_price
        filled = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        assert _record_stop_out_cooldown("DASH", filled, "stop-loss exit", exit_price=187.35)
        assert cooldown_exit_price("DASH") == pytest.approx(187.35)

    def test_flat_rebuy_above_stop_is_refused(self):
        from titantrade.cooldown import cooldown_override_allowed
        # Sold at $342.89; price now $343.50 — above the stop ($330 × 1.01)
        # but only 0.2% above where we exited. Under the old rule this was a
        # "recovery"; it is the JPM Sep 15 → 16 round trip (−$84).
        assert cooldown_override_allowed(
            "JPM", self._thesis(), {"signal": "CONTINUE"},
            hours_since_abort=28, current_price=343.50, exit_price=342.89,
        ) is False

    def test_recovered_one_pct_above_exit_is_allowed(self):
        from titantrade.cooldown import cooldown_override_allowed, COOLDOWN_RECOVERY_PCT
        assert COOLDOWN_RECOVERY_PCT == 1.0
        assert cooldown_override_allowed(
            "JPM", self._thesis(), {"signal": "CONTINUE"},
            hours_since_abort=28, current_price=342.89 * 1.01, exit_price=342.89,
        ) is True
        assert cooldown_override_allowed(
            "JPM", self._thesis(), {"signal": "CONTINUE"},
            hours_since_abort=28, current_price=342.89 * 1.0099, exit_price=342.89,
        ) is False

    def test_without_exit_price_keeps_thesis_stop_test(self):
        from titantrade.cooldown import cooldown_override_allowed
        # Pre-059 record: no exit price → the old behaviour, unchanged.
        assert cooldown_override_allowed(
            "JPM", self._thesis(), {"signal": "CONTINUE"},
            hours_since_abort=28, current_price=343.50, exit_price=None,
        ) is True

    def test_stop_test_still_applies_above_exit(self):
        from titantrade.cooldown import cooldown_override_allowed
        # 5% above the exit but still below stop × 1.01 → not recovered.
        assert cooldown_override_allowed(
            "JPM", self._thesis(stop_loss_price=340.0), {"signal": "CONTINUE"},
            hours_since_abort=28, current_price=336.0, exit_price=320.0,
        ) is False

    @patch("titantrade.entries.fetch_with_retry")
    def test_stop_out_scan_records_fill_price(self, mock_fetch, fake_config, tmp_state_dir):
        from datetime import datetime, timedelta, timezone
        from titantrade.entries import record_stop_out_cooldowns
        from titantrade.cooldown import cooldown_exit_price
        mock_fetch.return_value = _resp([{
            "symbol": "DVN", "side": "sell", "type": "stop_limit", "status": "filled",
            "filled_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "filled_avg_price": "43.42", "stop_price": "43.50",
        }])
        assert record_stop_out_cooldowns(fake_config) == 1
        assert cooldown_exit_price("DVN") == pytest.approx(43.42)

    @patch("titantrade.entries.place_bracket_order")
    @patch("titantrade.daily_sentry._fetch_current_price", return_value=343.50)
    def test_bullish_entry_blocks_flat_rebuy(
        self, mock_price, mock_bracket, fake_config, tmp_state_dir,
    ):
        """End to end: 28h after a $342.89 exit, sentry CONTINUE, price $343.50
        (above the stop, 0.2% above the exit) → the entry is still skipped."""
        import datetime as dt
        from titantrade.cooldown import _record_abort_cooldown
        _record_abort_cooldown("JPM", "sentry abort", exit_price=342.89)
        saved = json.loads((tmp_state_dir / "abort_cooldown.json").read_text())
        saved["JPM"]["aborted_at"] = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=28)
        ).isoformat()
        (tmp_state_dir / "abort_cooldown.json").write_text(json.dumps(saved))
        thesis = self._thesis(
            confidence=0.8, target_entry_price=345.0, take_profit_price=380.0,
        )
        result = _handle_bullish_entry(
            ticker="JPM", thesis=thesis,
            portfolio_value=100_000, cash_balance=50_000,
            positions=[], data_bundle={"stocks": {}},
            sentry={"signal": "CONTINUE"}, cfg=fake_config,
        )
        assert result is None
        mock_bracket.assert_not_called()

    @patch("titantrade.executor.get_open_orders", return_value=[])
    @patch("titantrade.executor.get_position")
    @patch("titantrade.executor.close_position_at_market")
    def test_abort_handler_records_exit_mark(
        self, mock_close, mock_pos, mock_orders, fake_config, tmp_state_dir,
    ):
        from titantrade.cooldown import cooldown_exit_price
        from titantrade.executor import _handle_abort
        mock_pos.return_value = {"symbol": "DASH", "qty": "4", "current_price": "179.26"}
        _handle_abort(
            "DASH", {"signal": "ABORT", "price_concern": True, "reasoning": "-5.1%"},
            fake_config,
        )
        assert cooldown_exit_price("DASH") == pytest.approx(179.26)
