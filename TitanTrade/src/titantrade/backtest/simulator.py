"""Portfolio simulator for backtesting. No API calls — pure state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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


@dataclass
class SimOrder:
    ticker: str
    side: str  # "buy" | "sell"
    order_type: str  # "limit" | "stop_limit" | "market"
    qty: int
    limit_price: float | None = None
    stop_price: float | None = None


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
    ):
        self.slippage_pct = slippage_pct
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
    ) -> None:
        """Process one trading day."""
        prices = {t: b["close"] for t, b in bars.items()}

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

        # 3. Check pending buy fills
        for order in list(self.pending_buys):
            if order.ticker in bars:
                bar = bars[order.ticker]
                if bar["low"] <= (order.limit_price or 0):
                    self._fill_buy(order, order.limit_price or bar["close"], date)
                    self.pending_buys.remove(order)

        # 4. Process new entries from thesis
        if new_theses:
            self._process_entries(new_theses, bars, date, sector_map or {})

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
            new_trail = round(pos.high_water_mark * (1 - self.trailing_distance_pct), 2)
            new_trail = max(new_trail, round(pos.entry_price * 1.005, 2))
            new_trail = max(new_trail, pos.stop_loss_price)

            if new_trail > pos.trailing_stop_price:
                pos.trailing_stop_price = new_trail
                pos.trailing_active = True

    def _fill_buy(self, order: SimOrder, price: float, date: str) -> None:
        # Apply slippage: buys fill slightly higher
        price = round(price * (1 + self.slippage_pct), 2)
        cost = order.qty * price
        if cost > self.cash:
            return
        self.cash -= cost
        self.positions[order.ticker] = SimPosition(
            ticker=order.ticker,
            shares=order.qty,
            entry_price=price,
            entry_date=date,
            stop_loss_price=round(price * (1 - self.stop_loss_pct), 2),
            take_profit_price=order.limit_price,  # Will be overwritten
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

        # Sector exposure check
        sector_values: dict[str, float] = {}
        for pos in self.positions.values():
            s = sector_map.get(pos.ticker, "Unknown")
            sector_values[s] = sector_values.get(s, 0) + pos.shares * bars.get(pos.ticker, {}).get("close", pos.entry_price)

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
            budget = min(pv * self.risk_per_trade, self.cash - min_cash)
            if budget <= 0:
                continue
            shares = int(budget / entry)
            if shares <= 0:
                continue

            # Sector check
            sector = sector_map.get(ticker, "Unknown")
            current_sector_val = sector_values.get(sector, 0)
            new_sector_pct = (current_sector_val + shares * entry) / pv * 100 if pv > 0 else 0
            if new_sector_pct > self.max_sector_pct:
                continue

            # Two-tranche: 60% at entry, 40% at 1.5% discount
            t1 = max(int(shares * 0.6), 1)
            t2 = shares - t1

            self.pending_buys.append(SimOrder(
                ticker=ticker, side="buy", order_type="limit",
                qty=t1, limit_price=entry, stop_price=stop,
            ))
            if t2 > 0:
                self.pending_buys.append(SimOrder(
                    ticker=ticker, side="buy", order_type="limit",
                    qty=t2, limit_price=round(entry * 0.985, 2), stop_price=stop,
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
