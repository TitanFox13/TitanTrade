# Backend Architecture

## Overview

The TitanTrade backend is a Python CLI application that runs as scheduled Docker containers.
It has no HTTP server — it reads config files, calls external APIs, writes JSON state files,
and exits. All scheduling is handled by server cron.

For the full system diagram (including the Flutter app), see
[docs/architecture.md](../../docs/architecture.md).

---

## Pipeline Structure

### Weekly Pipeline (Sunday 20:00 UTC)

1. **Data Collection** (`data_fetcher.py`)
   - 250 days of OHLCV per stock (for indicator calculation)
   - Computes RSI, MACD, Bollinger, ATR, SMA crossovers
   - News headlines (7 days) with deduplication
   - SEC filings (24 hours)
   - Market context: SPY, QQQ, VIX, Treasury yields, sector rotation
   - Earnings calendar (next 60 days)
   - Output: `state/data_bundle.json`

2. **Pass 1: Individual Analysis** (`weekly_analyst.py`)
   - Claude analyzes each stock with full data + indicators + market context
   - Performance feedback injected (last 4 weeks results + confidence calibration)
   - Output: per-stock thesis with entry, stop, take-profit, breach condition

3. **Pass 2: Portfolio Ranking** (`weekly_analyst.py`)
   - Claude sees all 10 theses simultaneously
   - Selects top 3-5 trades considering sector diversification and market regime
   - Output: `state/weekly_thesis.json` with `selected_for_trading` flag per thesis

### Daily Pipeline (09:00 + 15:30 EST)

1. **Layer 1: Market Health** (`daily_sentry.py`)
   - Check if SPY dropped >2% (market-wide stress signal)

2. **Layer 2: Price-Based Check** (`daily_sentry.py`)
   - Check if any held stock moved >3% against thesis since entry
   - Hard override: forces ABORT regardless of news assessment

3. **Layer 3: News-Based Check** (`daily_sentry.py`)
   - Gemini Flash compares today's headlines vs thesis breach condition
   - Receives price and market alerts as additional context
   - Output: `state/sentry_signals.json`

4. **Risk Gates** (`risk_manager.py`)
   - Six gates must ALL pass before any new entry

5. **Execution** (`executor.py`)
   - Bracket orders with broker-side stop-losses for new entries
   - Market sells on ABORT signals
   - Auto-resubmits expired day-only brackets with fresh risk checks

---

## Module Dependency Graph

```
config.py
├── logger.py
├── retry.py
├── indicators.py           <- Pure computation, no API calls
├── market_context.py       <- SPY, VIX, sectors (uses FMP)
├── earnings.py             <- Earnings calendar (uses FMP)
├── risk_manager.py         <- All risk gates (uses indicators, market_context)
├── performance.py          <- Trade stats + feedback (reads state files)
├── data_fetcher.py         <- Master data collection (uses all above)
├── weekly_analyst.py       <- Two-pass Claude analysis (uses data_fetcher, performance)
├── daily_sentry.py         <- Three-layer sentry (uses data_fetcher, Gemini)
├── price_check.py          <- Lightweight intraday price checks (no LLM)
├── broker.py               <- Alpaca REST client (the only module that calls Alpaca)
├── pricing.py              <- Trend regime + entry-price selection (pure)
├── cooldown.py             <- ABORT re-entry cooldown state + override policy
├── trailing_state.py       <- Trailing-stop state (HWM, trail, TP1/pyramid flags)
└── executor.py             <- Execution orchestrator + entry/position/protection logic
                               (uses broker, pricing, cooldown, trailing_state, risk_manager)
```

> **In progress (ADR 036):** `executor.py` is being decomposed from a 3,267-line god-module into the
> focused modules above (behavior-preserving; tests green at each step). `broker.py`, `pricing.py`,
> `cooldown.py`, `trailing_state.py` are extracted; `trade_state.py`, `alerts.py`, `entries.py`,
> `positions.py`, `protection.py`, `core_allocation.py` are planned. `executor.py` re-exports moved
> symbols, so `from titantrade.executor import X` and `@patch("titantrade.executor.X")` still resolve.

---

## State Files

All state lives in `state/` as JSON files. No database.

| File | Purpose | Updated By |
|------|---------|------------|
| `data_bundle.json` | Full data snapshot (OHLCV, indicators, news) | data_fetcher |
| `weekly_thesis.json` | Active theses + ranking | weekly_analyst |
| `sentry_signals.json` | Latest sentry results | daily_sentry |
| `trade_log.json` | All trades (append-only) | executor |
| `near_misses.json` | Trades blocked by <=2 gates | executor |
| `costs.json` | Per-API-call token usage + estimated cost | cost_logger |
| `portfolio.json` | Initial portfolio state | manual |
| `peak_portfolio.json` | High-water mark for drawdown | risk_manager |
| `thesis_history.json` | Archived theses (52 weeks) | weekly_analyst |
| `trailing_stops.json` | Per-ticker trailing stop HWM + state | executor |
| `pricecheck_signals.json` | Latest intraday price check results | price_check |

---

## Risk Control Summary

| Control | Type | Value | Enforced In |
|---------|------|-------|-------------|
| Position sizing | ATR-based | 2% portfolio risk per ATR | risk_manager |
| Position cap | Fixed | 10% of portfolio max | risk_manager |
| Stop-loss | Broker-native | 5% below entry (stop-limit) | executor (Alpaca) |
| Confidence gate | AI quality | >= 0.70 required | risk_manager |
| Earnings blackout | Calendar | 5 days before earnings | risk_manager |
| Drawdown breaker | Portfolio | Halt at 8% from peak | risk_manager |
| Cash reserve | Portfolio | 20% minimum cash | risk_manager |
| Sector exposure | Portfolio | 40% max per sector | risk_manager |
| Thesis expiry | Time-based | 14 days max | executor |
| Pass 2 selection | AI quality | Top 3-5 only | executor |
| Price-based abort | Market | 3% adverse move | daily_sentry |
| Market-wide alert | Market | SPY -2% intraday | daily_sentry |
