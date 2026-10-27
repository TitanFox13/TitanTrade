"""The SPY core as the residual of the book."""

from __future__ import annotations

from unittest.mock import patch

from titantrade.core_allocation import _is_core_ticker, manage_core_position


def _run(cfg, target, cash, spy_value, spy_qty, price=500.0, market_open=True):
    with patch("titantrade.core_allocation.is_market_open", return_value=market_open), \
         patch("titantrade.core_allocation.get_account", return_value={"portfolio_value": "100000", "cash": str(cash)}), \
         patch("titantrade.core_allocation.get_positions", return_value=[{"symbol": "SPY", "market_value": str(spy_value), "current_price": str(price), "qty": str(spy_qty)}] if spy_qty else []), \
         patch("titantrade.core_allocation.get_latest_price", return_value=price), \
         patch("titantrade.core_allocation.place_market_buy") as buy, \
         patch("titantrade.core_allocation.place_market_sell") as sell, \
         patch("titantrade.notifier.send_discord"):
        trade = manage_core_position(cfg, target_pct=target)
    return trade, buy, sell


class TestCore:
    def test_is_core_ticker(self, fake_config):
        assert _is_core_ticker("SPY", fake_config) and _is_core_ticker("SPMO", fake_config) and not _is_core_ticker("AAA", fake_config)

    def test_momentum_leg_buys_toward_its_target(self, fake_config, tmp_state_dir):
        with patch("titantrade.core_allocation.is_market_open", return_value=True), \
             patch("titantrade.core_allocation.get_account", return_value={"portfolio_value": "100000", "cash": "70000"}), \
             patch("titantrade.core_allocation.get_positions", return_value=[{"symbol": "SPY", "market_value": "30000", "current_price": "500", "qty": "60"}]), \
             patch("titantrade.core_allocation.get_latest_price", return_value=100.0) as price, \
             patch("titantrade.core_allocation.place_market_buy") as buy, \
             patch("titantrade.notifier.send_discord"):
            trade = manage_core_position(fake_config, target_pct=0.5, ticker="SPMO")
        price.assert_called_once_with("SPMO", fake_config)
        assert trade["ticker"] == "SPMO" and trade["action"] == "BUY" and buy.call_args.args[:2] == ("SPMO", 500.0)

    def test_buys_toward_target_with_spendable_cash(self, fake_config, tmp_state_dir):
        trade, buy, sell = _run(fake_config, target=0.75, cash=40_000, spy_value=40_000, spy_qty=80)
        assert trade["action"] == "BUY" and buy.call_args.args[1] == 70.0    # $35k spendable / $500
        sell.assert_not_called()

    def test_sells_down_to_the_residual_target(self, fake_config, tmp_state_dir):
        trade, buy, sell = _run(fake_config, target=0.25, cash=5_000, spy_value=60_000, spy_qty=120)
        assert trade["action"] == "SELL" and sell.call_args.args[1] == 70.0   # $35k over / $500
        buy.assert_not_called()

    def test_within_band_and_off_hours_do_nothing(self, fake_config, tmp_state_dir):
        assert _run(fake_config, target=0.50, cash=10_000, spy_value=48_000, spy_qty=96)[0] is None
        assert _run(fake_config, target=0.90, cash=50_000, spy_value=10_000, spy_qty=20, market_open=False)[0] is None

    def test_no_cash_means_wait(self, fake_config, tmp_state_dir):
        trade, buy, _ = _run(fake_config, target=0.90, cash=4_000, spy_value=10_000, spy_qty=20)
        assert trade is None
        buy.assert_not_called()
