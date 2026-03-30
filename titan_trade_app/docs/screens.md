# Screens Reference

## Dashboard (`/`)

Portfolio overview at a glance.

- Portfolio summary card: total value, cash balance, invested value, unrealized P&L
- Active positions list with per-position P&L and stop-loss distance
- Recent trades (last 5) with action badges
- Latest sentry signals for held positions

---

## Active Theses (`/theses`)

Card grid showing all theses from the current weekly analysis cycle.

- Confidence bar per thesis
- Entry / stop / take-profit price levels
- Days until thesis expiry
- BULLISH / BEARISH / NEUTRAL badge
- Selected-for-trading indicator

---

## Thesis Detail (`/theses/:ticker`)

Full breakdown of a single thesis.

- Full AI reasoning text
- Thesis breach condition
- Technical levels (support, resistance)
- Sentry status for this ticker
- Earnings blackout status

---

## Trade History (`/trades`)

Sortable list of all executed trades.

- Filter by action: ALL / BUY / SELL
- Trade tile: ticker, action badge, shares, price, timestamp, trigger type

---

## Trade Detail (`/trades/:index`)

Full context for a single trade.

- Thesis at time of trade (direction, confidence, reasoning)
- Sentry signal that preceded the trade
- Execution details (order type, shares, price, total value)
- Gate results: per-gate pass/fail checklist with detail strings
- Market context snapshot (regime, VIX, SPY return, technicals, news headlines)

---

## Near Misses (`/near-misses`)

Trades that were blocked by exactly 1 or 2 risk gates.

- Closeness indicator (1 gate blocked vs 2 gates blocked)
- Ticker, thesis direction, confidence
- Which gates failed

Useful for understanding opportunities that were almost taken.

---

## Near Miss Detail (`/near-misses/:index`)

Full breakdown of a single near miss.

- Gate checklist: all 6 gates with pass/fail and detail strings
- Thesis at time of near miss
- Market context snapshot at the moment the trade was blocked

---

## Watchlist (`/watchlist`)

The only screen that writes to the backend.

- Current list of tracked tickers
- Add ticker (validates format before saving)
- Remove ticker
- Writes immediately to `data/watchlist.json` — picked up by the backend on next run

---

## Statistics (`/statistics`)

True profitability view accounting for operational costs.

- **Net P&L**: Trading gains minus all AI operational costs
- **Realized P&L**: Matched BUY→SELL round-trips, per-trade profit/loss
- **Unrealized P&L**: Current paper gains/losses on open positions
- **Cost breakdown**: Per-service (Claude, Gemini) call counts, tokens, estimated spend
- **Recent API calls**: Last 20 calls with timestamps, descriptions, and costs

Round-trip matching assumes one position per ticker at a time (valid given 10% position limit).
Partial fills are matched FIFO.

---

## Settings (`/settings`)

- **Server URL**: Change the TitanTrade backend URL — validates via `GET /api/health` before saving
- **Refresh interval**: 10s / 15s / 30s / 60s / 120s — controls all 7 polling providers

Both settings are persisted via `SharedPreferences`.

---

## Setup (`/setup`)

First-run only. Text field for entering the server URL (e.g. `https://trade.praguefun.cz`).
Validates by hitting `GET /api/health` before saving.
