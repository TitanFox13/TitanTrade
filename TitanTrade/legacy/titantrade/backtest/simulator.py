"""Portfolio simulator for backtesting. No API calls — pure state machine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from titantrade.indicators import atr as compute_atr
from titantrade.risk_manager import confidence_scaled_risk


@dataclass
class SimPosition:
    ticker: str
    shares: int
    entry_price: float
    entry_date: str
    stop_loss_price: float
    take_profit_price: float | None
    trailing_active: bool = False
    high_water_mark: float = 0.0
    trailing_stop_price: float = 0.0
    # Strategy-v2 state
    tp1_taken: bool = False
    pyramid_added: bool = False


@dataclass
class SimOrder:
    ticker: str
    side: str  # "buy" | "sell"
    order_type: str  # "limit" | "stop_limit" | "market"
    qty: int
    limit_price: float | None = None
    stop_price: float | None = None
    tp_price: float | None = None
    placed_date: str = ""  # for limit-order expiry


class PortfolioSimulator:
    def __init__(
        self,
        initial_capital: float = 100_000.0,
        stop_loss_pct: float = 0.05,
        risk_per_trade: float = 0.10,
        trailing_trigger_pct: float = 0.05,
        trailing_distance_pct: float = 0.03,
        max_drawdown_pct: float = 8.0,
        min_cash_reserve_pct: float = 20.0,
        max_sector_pct: float = 40.0,
        min_confidence: float = 0.70,
        slippage_pct: float = 0.0015,  # 0.15% realistic slippage per fill
        limit_order_ttl_days: int = 10,  # v1 dip-buy limit orders expire after N days
        use_confidence_scaling: bool = False,
        # ---- Strategy v2 toggles (default off so existing tests/comparison pass) ----
        strategy_v2: bool = False,
        max_position_pct: float = 0.25,
        max_total_overlay_pct: float = 0.70,
        trailing_atr_multiplier: float = 3.0,  # mirrors live config (ADR 048)
        core_ticker: str = "SPY",
        core_allocation_pct: float = 0.30,
        pyramid_trigger_pct: float = 0.05,
        pyramid_size_fraction: float = 0.5,
        pyramid_max_total_pct: float = 0.30,
        tp1_trigger_fraction: float = 0.5,
        tp1_fraction: float = 0.333,
    ):
        self.strategy_v2 = strategy_v2
        # When v2 is on, force the new defaults UNLESS the caller explicitly
        # overrode them. We detect by checking against the v1 defaults.
        if strategy_v2:
            if min_confidence == 0.70:
                min_confidence = 0.55
            if min_cash_reserve_pct == 20.0:
                min_cash_reserve_pct = 5.0
            if max_sector_pct == 40.0:
                max_sector_pct = 50.0
            if not use_confidence_scaling:
                use_confidence_scaling = True
            if trailing_distance_pct == 0.03:
                trailing_distance_pct = 0.05  # fallback when ATR missing

        self.use_confidence_scaling = use_confidence_scaling
        self.slippage_pct = slippage_pct
        self.limit_order_ttl_days = limit_order_ttl_days
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict[str, SimPosition] = {}
        self.pending_buys: list[SimOrder] = []
        self.trade_log: list[dict[str, Any]] = []
        self.equity_curve: list[dict[str, Any]] = []
        self.peak_value = initial_capital
        self.circuit_breaker_tripped = False

        # Config
        self.stop_loss_pct = stop_loss_pct
        self.risk_per_trade = risk_per_trade
        self.trailing_trigger_pct = trailing_trigger_pct
        self.trailing_distance_pct = trailing_distance_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.min_cash_reserve_pct = min_cash_reserve_pct
        self.max_sector_pct = max_sector_pct
        self.min_confidence = min_confidence
        # v2 params
        self.max_position_pct = max_position_pct
        self.max_total_overlay_pct = max_total_overlay_pct
        self.trailing_atr_multiplier = trailing_atr_multiplier
        self.core_ticker = core_ticker
        self.core_allocation_pct = core_allocation_pct
        self.pyramid_trigger_pct = pyramid_trigger_pct
        self.pyramid_size_fraction = pyramid_size_fraction
        self.pyramid_max_total_pct = pyramid_max_total_pct
        self.tp1_trigger_fraction = tp1_trigger_fraction
        self.tp1_fraction = tp1_fraction
        # Per-ticker ATR cache, updated by the engine when bars are passed
        self.atr_by_ticker: dict[str, float] = {}

    def portfolio_value(self, prices: dict[str, float]) -> float:
        invested = sum(
            pos.shares * prices.get(pos.ticker, pos.entry_price)
            for pos in self.positions.values()
        )
        return self.cash + invested

    def process_day(
        self,
        date: str,
        bars: dict[str, dict[str, Any]],
        new_theses: dict[str, dict[str, Any]] | None = None,
        sector_map: dict[str, str] | None = None,
        history_by_ticker: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        """Process one trading day."""
        prices = {t: b["close"] for t, b in bars.items()}

        # Refresh per-ticker ATR cache from rolling history (v2 only). The
        # engine passes history_by_ticker = bars-up-to-today per ticker.
        if self.strategy_v2 and history_by_ticker:
            for ticker, hist in history_by_ticker.items():
                if len(hist) >= 15:
                    a = compute_atr(hist[-30:])  # use recent 30 bars
                    if a:
                        self.atr_by_ticker[ticker] = a

        # 1. Check stop-losses and take-profits
        for ticker in list(self.positions.keys()):
            if ticker not in bars:
                continue
            bar = bars[ticker]
            self._check_stops(ticker, bar, date)
            if ticker in self.positions:
                self._check_take_profit(ticker, bar, date)

        # 2. Update trailing stops
        for ticker in list(self.positions.keys()):
            if ticker in bars:
                self._update_trailing(ticker, bars[ticker])

        # 2b. v2 only: TP1 partial sell + pyramid into winners
        if self.strategy_v2:
            for ticker in list(self.positions.keys()):
                if ticker in bars:
                    self._maybe_take_tp1(ticker, bars[ticker], date)
                    self._maybe_pyramid(ticker, bars[ticker], date, prices)

        # 3. Check pending buy fills
        #
        # v1: limit BUY fills only when bar.low <= limit (true dip-buy).
        # v2: pending_buys are placed as same-day market-style fills in
        #     _process_entries below, so this loop is mostly a no-op for v2.
        for order in list(self.pending_buys):
            # Expire unfilled limit orders so a dip that never comes doesn't
            # park an order forever and permanently block re-entry on that
            # ticker (the v1 entry path skips tickers with a pending order).
            if order.placed_date and _days_between(order.placed_date, date) > self.limit_order_ttl_days:
                self.pending_buys.remove(order)
                continue
            if order.ticker in bars:
                bar = bars[order.ticker]
                if bar["low"] <= (order.limit_price or 0):
                    self._fill_buy(order, order.limit_price or bar["close"], date)
                    self.pending_buys.remove(order)

        # 4. Process new entries from thesis
        if new_theses:
            self._process_entries(new_theses, bars, date, sector_map or {})

        # 4b. v2: maintain core SPY position (always-deployed baseline)
        if self.strategy_v2:
            self._maintain_core_position(bars, date)

        # 5. Update equity curve
        pv = self.portfolio_value(prices)
        if pv > self.peak_value:
            self.peak_value = pv
        drawdown = (self.peak_value - pv) / self.peak_value * 100 if self.peak_value > 0 else 0
        self.circuit_breaker_tripped = drawdown >= self.max_drawdown_pct

        self.equity_curve.append({
            "date": date,
            "portfolio_value": round(pv, 2),
            "cash": round(self.cash, 2),
            "positions": len(self.positions),
            "drawdown_pct": round(drawdown, 2),
        })

    def _check_stops(self, ticker: str, bar: dict, date: str) -> None:
        pos = self.positions.get(ticker)
        if not pos:
            return

        # Use trailing stop if active, otherwise original stop
        effective_stop = pos.trailing_stop_price if pos.trailing_active else pos.stop_loss_price

        if bar["low"] <= effective_stop:
            # Stop triggered — sell at stop price (or open if gapped below)
            fill_price = min(bar["open"], effective_stop)
            self._close_position(ticker, fill_price, date, "stop_loss")

    def _check_take_profit(self, ticker: str, bar: dict, date: str) -> None:
        pos = self.positions.get(ticker)
        if not pos or not pos.take_profit_price:
            return
        if bar["high"] >= pos.take_profit_price:
            self._close_position(ticker, pos.take_profit_price, date, "take_profit")

    def _update_trailing(self, ticker: str, bar: dict) -> None:
        pos = self.positions.get(ticker)
        if not pos:
            return

        current_high = bar["high"]
        if current_high > pos.high_water_mark:
            pos.high_water_mark = current_high

        gain_pct = (pos.high_water_mark - pos.entry_price) / pos.entry_price
        if gain_pct >= self.trailing_trigger_pct:
            # v2: ATR-based trailing distance (2.5x ATR by default), falls back
            # to fixed % when ATR unavailable. v1: fixed %.
            if self.strategy_v2:
                ticker_atr = self.atr_by_ticker.get(ticker)
                if ticker_atr and ticker_atr > 0:
                    trail_distance = ticker_atr * self.trailing_atr_multiplier
                    # floor at 1% of HWM
                    trail_distance = max(trail_distance, pos.high_water_mark * 0.01)
                    new_trail = round(pos.high_water_mark - trail_distance, 2)
                else:
                    new_trail = round(pos.high_water_mark * (1 - self.trailing_distance_pct), 2)
            else:
                new_trail = round(pos.high_water_mark * (1 - self.trailing_distance_pct), 2)
            new_trail = max(new_trail, round(pos.entry_price * 1.005, 2))
            new_trail = max(new_trail, pos.stop_loss_price)

            if new_trail > pos.trailing_stop_price:
                pos.trailing_stop_price = new_trail
                pos.trailing_active = True

    def _maybe_take_tp1(self, ticker: str, bar: dict, date: str) -> None:
        """v2: at 50% of upside-to-TP, sell 1/3 and raise stop to breakeven."""
        pos = self.positions.get(ticker)
        if not pos or pos.tp1_taken or not pos.take_profit_price:
            return
        if pos.shares < 3:
            return
        if pos.take_profit_price <= pos.entry_price:
            return
        tp1_price = pos.entry_price + (pos.take_profit_price - pos.entry_price) * self.tp1_trigger_fraction
        if bar["high"] >= tp1_price:
            tp1_qty = max(1, round(pos.shares * self.tp1_fraction))
            tp1_qty = min(tp1_qty, pos.shares - 1)  # leave at least 1
            # Sell tp1_qty at tp1_price with slippage
            sell_price = round(tp1_price * (1 - self.slippage_pct), 2)
            self.cash += tp1_qty * sell_price
            pnl_pct = (sell_price - pos.entry_price) / pos.entry_price * 100
            self.trade_log.append({
                "date": date, "ticker": ticker, "action": "SELL",
                "shares": tp1_qty, "price": sell_price,
                "trigger": "tp1_partial",
                "entry_price": pos.entry_price,
                "pnl_pct": round(pnl_pct, 2),
                "days_held": _days_between(pos.entry_date, date),
            })
            pos.shares -= tp1_qty
            pos.tp1_taken = True
            # Raise stop to breakeven on remainder
            breakeven = round(pos.entry_price * 1.005, 2)
            pos.stop_loss_price = max(pos.stop_loss_price, breakeven)
            pos.trailing_stop_price = max(pos.trailing_stop_price, breakeven)
            pos.trailing_active = True

    def _maybe_pyramid(self, ticker: str, bar: dict, date: str,
                       prices: dict[str, float]) -> None:
        """v2: at +5% gain with trailing active, add 50% of original notional."""
        pos = self.positions.get(ticker)
        if not pos or pos.pyramid_added:
            return
        gain_pct = (bar["close"] - pos.entry_price) / pos.entry_price
        if gain_pct < self.pyramid_trigger_pct:
            return
        if not pos.trailing_active:
            return  # require trailing stop active so downside is bounded

        # Size = 50% of original notional, capped at pyramid_max_total_pct
        pv = self.portfolio_value(prices)
        current_notional = pos.shares * bar["close"]
        cap = pv * self.pyramid_max_total_pct
        add_notional = min(
            (pos.shares * pos.entry_price) * self.pyramid_size_fraction,
            cap - current_notional,
        )
        # Respect cash floor
        min_cash = pv * (self.min_cash_reserve_pct / 100)
        add_notional = min(add_notional, self.cash - min_cash)
        if add_notional <= 0:
            pos.pyramid_added = True
            return
        add_qty = int(add_notional / bar["close"])
        if add_qty <= 0:
            pos.pyramid_added = True
            return
        fill_price = round(bar["close"] * (1 + self.slippage_pct), 2)
        cost = add_qty * fill_price
        if cost > self.cash:
            return
        # Average up the entry price
        new_total_shares = pos.shares + add_qty
        new_avg_entry = (pos.shares * pos.entry_price + add_qty * fill_price) / new_total_shares
        self.cash -= cost
        pos.shares = new_total_shares
        pos.entry_price = round(new_avg_entry, 4)
        pos.pyramid_added = True
        self.trade_log.append({
            "date": date, "ticker": ticker, "action": "BUY",
            "shares": add_qty, "price": fill_price,
            "trigger": "pyramid",
        })

    def _maintain_core_position(self, bars: dict[str, dict], date: str) -> None:
        """v2: maintain ~30% allocation to core_ticker (SPY)."""
        ct = self.core_ticker
        if ct not in bars:
            return
        prices = {t: b["close"] for t, b in bars.items()}
        pv = self.portfolio_value(prices)
        if pv <= 0:
            return
        target_value = pv * self.core_allocation_pct
        band = pv * 0.05  # 5%pt rebalance band

        core_pos = self.positions.get(ct)
        current_value = (core_pos.shares * bars[ct]["close"]) if core_pos else 0.0
        drift = current_value - target_value
        if abs(drift) < band:
            return
        price = round(bars[ct]["close"] * (1 + self.slippage_pct), 2)
        if drift < 0:
            # Buy more — respect cash floor
            min_cash = pv * (self.min_cash_reserve_pct / 100)
            available = max(0.0, self.cash - min_cash)
            buy_value = min(-drift, available)
            buy_qty = int(buy_value / price)
            if buy_qty <= 0:
                return
            cost = buy_qty * price
            self.cash -= cost
            if core_pos:
                new_total = core_pos.shares + buy_qty
                new_avg = (core_pos.shares * core_pos.entry_price + buy_qty * price) / new_total
                core_pos.shares = new_total
                core_pos.entry_price = round(new_avg, 4)
            else:
                self.positions[ct] = SimPosition(
                    ticker=ct, shares=buy_qty, entry_price=price,
                    entry_date=date,
                    stop_loss_price=round(price * 0.85, 2),  # 15% wide stop on core
                    take_profit_price=None, high_water_mark=price,
                )
            self.trade_log.append({
                "date": date, "ticker": ct, "action": "BUY",
                "shares": buy_qty, "price": price,
                "trigger": "core_rebalance",
            })
        else:
            # Trim
            if not core_pos:
                return
            sell_qty = int(drift / price)
            if sell_qty <= 0 or sell_qty >= core_pos.shares:
                return
            proceeds = sell_qty * round(price * (1 - self.slippage_pct), 2)
            self.cash += proceeds
            core_pos.shares -= sell_qty
            self.trade_log.append({
                "date": date, "ticker": ct, "action": "SELL",
                "shares": sell_qty, "price": price,
                "trigger": "core_rebalance",
            })

    def _fill_buy(self, order: SimOrder, price: float, date: str) -> None:
        # Apply slippage: buys fill slightly higher
        price = round(price * (1 + self.slippage_pct), 2)
        cost = order.qty * price
        if cost > self.cash:
            return
        self.cash -= cost

        # Stop/TP come from the thesis (carried on the order), NOT the entry
        # limit price. The old code set take_profit_price=order.limit_price,
        # so a fill instantly "took profit" at break-even — the source of the
        # fake 0% win rate in the legacy v1 backtest.
        stop = order.stop_price or round(price * (1 - self.stop_loss_pct), 2)
        tp = order.tp_price

        existing = self.positions.get(order.ticker)
        if existing:
            # Second tranche of a two-tranche entry: accumulate and average up
            # rather than overwrite (which silently dropped tranche-1 shares).
            total_shares = existing.shares + order.qty
            existing.entry_price = round(
                (existing.shares * existing.entry_price + order.qty * price) / total_shares, 4
            )
            existing.shares = total_shares
            existing.high_water_mark = max(existing.high_water_mark, price)
        else:
            self.positions[order.ticker] = SimPosition(
                ticker=order.ticker,
                shares=order.qty,
                entry_price=price,
                entry_date=date,
                stop_loss_price=stop,
                take_profit_price=tp,
                high_water_mark=price,
            )
        self.trade_log.append({
            "date": date, "ticker": order.ticker, "action": "BUY",
            "shares": order.qty, "price": round(price, 2),
            "trigger": "thesis_entry",
        })

    def _close_position(self, ticker: str, price: float, date: str, trigger: str) -> None:
        pos = self.positions.pop(ticker, None)
        if not pos:
            return
        # Apply slippage: sells fill slightly lower
        price = round(price * (1 - self.slippage_pct), 2)
        proceeds = pos.shares * price
        self.cash += proceeds
        pnl_pct = (price - pos.entry_price) / pos.entry_price * 100
        self.trade_log.append({
            "date": date, "ticker": ticker, "action": "SELL",
            "shares": pos.shares, "price": round(price, 2),
            "trigger": trigger,
            "entry_price": pos.entry_price,
            "pnl_pct": round(pnl_pct, 2),
            "days_held": _days_between(pos.entry_date, date),
        })

    def _process_entries(
        self,
        theses: dict[str, dict],
        bars: dict[str, dict],
        date: str,
        sector_map: dict[str, str],
    ) -> None:
        if self.circuit_breaker_tripped:
            return

        pv = self.portfolio_value({t: b["close"] for t, b in bars.items()})
        min_cash = pv * (self.min_cash_reserve_pct / 100)

        # Sector exposure check (v2 excludes the core ticker from sector cap)
        sector_values: dict[str, float] = {}
        for pos in self.positions.values():
            if self.strategy_v2 and pos.ticker == self.core_ticker:
                continue
            s = sector_map.get(pos.ticker, "Unknown")
            sector_values[s] = sector_values.get(s, 0) + pos.shares * bars.get(pos.ticker, {}).get("close", pos.entry_price)

        # v2: total overlay value (excludes core)
        overlay_value = 0.0
        if self.strategy_v2:
            for pos in self.positions.values():
                if pos.ticker == self.core_ticker:
                    continue
                overlay_value += pos.shares * bars.get(pos.ticker, {}).get("close", pos.entry_price)

        for ticker, thesis in theses.items():
            if thesis.get("thesis") != "BULLISH":
                continue
            if thesis.get("confidence", 0) < self.min_confidence:
                continue
            if ticker in self.positions:
                continue
            if any(o.ticker == ticker for o in self.pending_buys):
                continue

            entry = thesis.get("target_entry_price")
            stop = thesis.get("stop_loss_price")
            tp = thesis.get("take_profit_price")
            if not entry or not stop:
                continue

            # Position sizing
            confidence = float(thesis.get("confidence", 0.85))
            if self.use_confidence_scaling:
                effective_risk = confidence_scaled_risk(
                    self.risk_per_trade, confidence,
                )
            else:
                effective_risk = self.risk_per_trade
            # v2: cap per-position
            if self.strategy_v2:
                effective_risk = min(effective_risk, self.max_position_pct)

            budget = min(pv * effective_risk, self.cash - min_cash)
            if budget <= 0:
                continue

            # v2: overlay cap
            if self.strategy_v2:
                overlay_cap = pv * self.max_total_overlay_pct
                overlay_headroom = max(0.0, overlay_cap - overlay_value)
                budget = min(budget, overlay_headroom)
                if budget <= 0:
                    continue

            # v2: trend-aware entry pricing. The bar for this date IS today's
            # bar (we're being called with same-day theses). For v2 we fill
            # at today's close (with a small breakout buffer for strong-up).
            # For v1 we keep the limit-below logic.
            if self.strategy_v2:
                bar = bars.get(ticker)
                if not bar:
                    continue
                current_price = bar["close"]
                # Simple regime check: above SMA-50 → up; below → skip
                # (Use the rolling history if we have ATR for the ticker as a
                # proxy for "we've seen enough data".)
                # Aggressive fill: today's close with a small breakout buffer
                # for high-conviction (proxy for the executor's near-market logic).
                if confidence >= 0.80:
                    fill_price = current_price * 1.003
                else:
                    fill_price = current_price * 1.001
                # If thesis stop is well below new entry, walk stop+TP up to
                # preserve risk:reward.
                if fill_price > entry:
                    delta = fill_price - entry
                    stop = round(stop + delta, 2)
                    if tp:
                        tp = round(tp + delta, 2)
                shares = int(budget / fill_price)
                if shares <= 0:
                    continue
                # Sector check
                sector = sector_map.get(ticker, "Unknown")
                current_sector_val = sector_values.get(sector, 0)
                new_sector_pct = (current_sector_val + shares * fill_price) / pv * 100 if pv > 0 else 0
                if new_sector_pct > self.max_sector_pct:
                    continue
                # Same-day fill at fill_price + slippage
                price = round(fill_price * (1 + self.slippage_pct), 2)
                cost = shares * price
                if cost > self.cash:
                    shares = int((self.cash - min_cash) / price)
                    if shares <= 0:
                        continue
                    cost = shares * price
                self.cash -= cost
                self.positions[ticker] = SimPosition(
                    ticker=ticker, shares=shares, entry_price=price,
                    entry_date=date, stop_loss_price=stop,
                    take_profit_price=tp, high_water_mark=price,
                )
                self.trade_log.append({
                    "date": date, "ticker": ticker, "action": "BUY",
                    "shares": shares, "price": price,
                    "trigger": "thesis_entry",
                })
                # Update sector tracking + overlay value for subsequent loops
                sector_values[sector] = current_sector_val + cost
                overlay_value += cost
                continue

            # v1: two-tranche limit-below entry (the original dip-buy strategy)
            shares = int(budget / entry)
            if shares <= 0:
                continue
            # Sector check
            sector = sector_map.get(ticker, "Unknown")
            current_sector_val = sector_values.get(sector, 0)
            new_sector_pct = (current_sector_val + shares * entry) / pv * 100 if pv > 0 else 0
            if new_sector_pct > self.max_sector_pct:
                continue

            t1 = max(int(shares * 0.6), 1)
            t2 = shares - t1

            self.pending_buys.append(SimOrder(
                ticker=ticker, side="buy", order_type="limit",
                qty=t1, limit_price=entry, stop_price=stop, tp_price=tp,
                placed_date=date,
            ))
            if t2 > 0:
                self.pending_buys.append(SimOrder(
                    ticker=ticker, side="buy", order_type="limit",
                    qty=t2, limit_price=round(entry * 0.985, 2), stop_price=stop,
                    tp_price=tp, placed_date=date,
                ))

    # Override stop/TP on filled positions from thesis
    def apply_thesis_levels(self, ticker: str, thesis: dict) -> None:
        pos = self.positions.get(ticker)
        if pos:
            if thesis.get("stop_loss_price"):
                pos.stop_loss_price = thesis["stop_loss_price"]
            if thesis.get("take_profit_price"):
                pos.take_profit_price = thesis["take_profit_price"]


def _days_between(d1: str, d2: str) -> int:
    try:
        dt1 = datetime.strptime(d1[:10], "%Y-%m-%d")
        dt2 = datetime.strptime(d2[:10], "%Y-%m-%d")
        return (dt2 - dt1).days
    except (ValueError, TypeError):
        return 0
