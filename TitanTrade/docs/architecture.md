# TitanTrade Architecture

## System Overview

TitanTrade is a semi-automated trading system with a **two-tier AI architecture**
and **six-layer risk management**:

1. **The Analyst (Weekly)** - Two-pass deep analysis via Claude Opus/Sonnet
2. **The Sentry (Daily)** - Three-signal conflict detection via Gemini Flash
3. **Risk Manager** - Six programmatic gates between AI and execution

```
                    +------------------+
                    |  Server (Docker)  |
                    |  (Cron Triggers)  |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
     Sunday 20:00 UTC              Daily 09:00 & 15:30
              |                             |
    +---------v----------+       +----------v---------+
    | weekly_analyst.py   |       | daily_sentry.py    |
    | Pass 1: Per-stock   |       | Layer 1: SPY check |
    | Pass 2: Portfolio   |       | Layer 2: Price move|
    |   ranking (top 3-5) |       | Layer 3: News/AI   |
    +--------+------------+       +----------+---------+
             |                               |
             |  weekly_thesis.json           |  sentry_signals.json
             +------------+------------------+
                          |
                +---------v----------+
                |   risk_manager.py   |
                | Gate 1: Confidence  |
                | Gate 2: Earnings    |
                | Gate 3: Drawdown    |
                | Gate 4: Cash reserve|
                | Gate 5: Vol sizing  |
                | Gate 6: Sector limit|
                +--------+-----------+
                         |
                +---------v----------+
                |    executor.py      |
                | Bracket orders      |
                | Native stop-losses  |
                +--------+-----------+
                         |
                +--------v----------+
                |   Alpaca Markets   |
                |  (Paper/Live)      |
                +--------+----------+
                         |
                +--------v----------+
                |  state/*.json      |
                |  (JSON files)      |
                +--------+----------+
                         |
                +--------v----------+
                | TitanTrade Desktop |
                | (Flutter app)      |
                +--------------------+
```

## Data Flow

### Weekly Pipeline (Sunday 20:00 UTC)

1. **Data Collection** (`data_fetcher.py`)
   - 250 days of OHLCV per stock (for indicator calculation)
   - Computes RSI, MACD, Bollinger, ATR, SMA crossovers
   - News headlines (7 days)
   - SEC filings (24 hours)
   - Market context: SPY, QQQ, VIX, Treasury yields, sector rotation
   - Earnings calendar (next 60 days)

2. **Pass 1: Individual Analysis** (`weekly_analyst.py`)
   - Claude analyzes each stock with full data + indicators + market context
   - Performance feedback injected (last 4 weeks results + confidence calibration)
   - Output: per-stock thesis with entry, stop, take-profit, breach condition

3. **Pass 2: Portfolio Ranking** (`weekly_analyst.py`)
   - Claude sees ALL 10 theses simultaneously
   - Considers sector diversification, correlation, market regime
   - Selects TOP 3-5 trades for the week
   - Output: `selected_for_trading` flag on each thesis

### Daily Pipeline (09:00 + 15:30 EST)

1. **Layer 1: Market Health** (`daily_sentry.py`)
   - Check if SPY dropped >2% (market-wide stress signal)
   - If stressed, ALL positions flagged for review

2. **Layer 2: Price-Based Check** (`daily_sentry.py`)
   - Check if stock moved >3% against thesis since entry
   - Hard override: forces ABORT regardless of news assessment

3. **Layer 3: News-Based Check** (`daily_sentry.py`)
   - Gemini Flash compares today's headlines vs thesis breach condition
   - Receives price and market alerts as additional context

4. **Risk Gates** (`risk_manager.py`)
   - Six gates must ALL pass before any new entry

5. **Execution** (`executor.py`)
   - Bracket orders with native broker-side stop-losses
   - Market sells on ABORT signals

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
└── executor.py             <- Trade execution (uses risk_manager, Alpaca API)
```

## State Management

JSON files in `state/`:

| File | Purpose | Updated By |
|------|---------|------------|
| `data_bundle.json` | Full data snapshot | data_fetcher |
| `weekly_thesis.json` | Active theses + ranking | weekly_analyst |
| `sentry_signals.json` | Latest sentry results | daily_sentry |
| `trade_log.json` | All trades (append-only) | executor |
| `portfolio.json` | Initial portfolio state | manual |
| `peak_portfolio.json` | High-water mark for drawdown | risk_manager |
| `thesis_history.json` | Archived theses (52 weeks) | weekly_analyst |

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
