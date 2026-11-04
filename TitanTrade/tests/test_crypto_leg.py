"""The bitcoin leg (Decision 097): a held crypto position at a fixed share of equity, outside the exposure rules,
re-set only outside its own band, sized in fractional units, never an orphan, never gated."""

from __future__ import annotations

from unittest.mock import patch

from titantrade.broker import place_market_buy
from titantrade.config import TradingSettings
from titantrade.core_allocation import _is_core_ticker, core_tickers, manage_core_position
from titantrade.mechanical import core_target_pct, crypto_target_pct, momentum_target_pct
from titantrade.protection import close_orphaned_positions
from titantrade.risk_manager import _core_legs


def _cfg(fake_config, **kw):
    from dataclasses import replace
    return replace(fake_config, trading=replace(fake_config.trading, momentum_weight=0.6, crypto_ticker="BTC/USD", crypto_weight=0.05, **kw))


def _run(cfg, target, cash, btc_value, btc_qty, price=80_000.0):
    pos = [{"symbol": "BTCUSD", "market_value": str(btc_value), "current_price": str(price), "qty": str(btc_qty)}] if btc_qty else []
    with patch("titantrade.core_allocation.is_market_open", return_value=True), \
         patch("titantrade.core_allocation.get_account", return_value={"portfolio_value": "100000", "cash": str(cash)}), \
         patch("titantrade.core_allocation.get_positions", return_value=pos), \
         patch("titantrade.core_allocation.get_latest_price", return_value=price), \
         patch("titantrade.core_allocation.place_market_buy") as buy, \
         patch("titantrade.core_allocation.place_market_sell") as sell, \
         patch("titantrade.notifier.send_discord"):
        trade = manage_core_position(cfg, target_pct=target, ticker="BTC/USD", band_pct=0.25, fractional=True)
    return trade, buy, sell


class TestCryptoLeg:
    def test_settings_and_the_pro_rata_slot(self, fake_config):
        t = TradingSettings(momentum_weight=0.6, crypto_ticker="BTC/USD", crypto_weight=0.05)
        assert abs(t.overlay_slot_pct - 0.25 * 0.4 * 0.95) < 1e-9
        cfg = _cfg(fake_config)
        assert "BTC/USD" in core_tickers(cfg) and "BTCUSD" in core_tickers(cfg) and _is_core_ticker("BTCUSD", cfg)
        assert "BTCUSD" in _core_legs(cfg)

    def test_targets_the_leg_is_outside_the_exposure_rules(self, fake_config):
        cfg = _cfg(fake_config)
        assert crypto_target_pct(cfg) == 0.05
        assert momentum_target_pct(cfg, 1.0) == round(0.98 * 0.6 * 0.95, 4)
        assert momentum_target_pct(cfg, 0.5) == round(0.49 * 0.6 * 0.95, 4)
        assert core_target_pct(cfg, 100_000, [], planned_new_slots=0, exposure_scale=1.0) == round(0.98 * 0.4 * 0.95, 4)

    def test_first_buy_is_fractional_to_the_target(self, fake_config, tmp_state_dir):
        trade, buy, sell = _run(_cfg(fake_config), target=0.05, cash=20_000, btc_value=0, btc_qty=0)
        assert trade["action"] == "BUY" and buy.call_args.args[:2] == ("BTC/USD", 0.0625)   # $5,000 / $80,000
        sell.assert_not_called()

    def test_inside_its_own_band_nothing_happens(self, fake_config, tmp_state_dir):
        assert _run(_cfg(fake_config), target=0.05, cash=20_000, btc_value=4_500, btc_qty=0.05625)[0] is None   # band ±$1,250
        trade, buy, _ = _run(_cfg(fake_config), target=0.05, cash=20_000, btc_value=3_500, btc_qty=0.04375)
        assert trade["action"] == "BUY" and buy.call_args.args[1] == 0.01875

    def test_over_the_band_sells_fractional(self, fake_config, tmp_state_dir):
        trade, buy, sell = _run(_cfg(fake_config), target=0.05, cash=1_000, btc_value=7_000, btc_qty=0.0875)
        assert trade["action"] == "SELL" and sell.call_args.args[:2] == ("BTC/USD", 0.025)
        buy.assert_not_called()

    def test_the_leg_is_never_an_orphan(self, fake_config, tmp_state_dir):
        with patch("titantrade.protection._load", return_value={"items": []}), \
             patch("titantrade.protection.get_positions", return_value=[{"symbol": "BTCUSD", "qty": "0.06"}]), \
             patch("titantrade.protection.close_position_settled") as close:
            assert close_orphaned_positions(_cfg(fake_config)) == []
        close.assert_not_called()

    def test_crypto_orders_are_gtc(self, fake_config):
        with patch("titantrade.broker.fetch_with_retry") as fetch:
            fetch.return_value.json.return_value = {}
            place_market_buy("BTC/USD", 0.0625, fake_config)
            place_market_buy("SPY", 10, fake_config)
        assert fetch.call_args_list[0].kwargs["json_body"]["time_in_force"] == "gtc"
        assert fetch.call_args_list[1].kwargs["json_body"]["time_in_force"] == "day"
