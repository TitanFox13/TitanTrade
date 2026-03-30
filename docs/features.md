# TitanTrade Features

## AI Features

### Two-Pass Weekly Analysis (Claude)
- **Pass 1**: Deep per-stock analysis with fundamentals, technicals, news, and filings
- **Pass 2**: Portfolio-aware ranking that selects top 3-5 diversified trades
- Market context (SPY, VIX, sector rotation) injected into every analysis
- Performance feedback loop: Claude sees its last 4 weeks of results
- Confidence calibration: tracks if 0.80 confidence actually wins 80%

### Three-Layer Daily Sentry (Gemini Flash)
- **Layer 1 - Market-wide**: SPY drop >2% flags ALL positions
- **Layer 2 - Price-based**: 3% adverse move triggers hard ABORT override
- **Layer 3 - News-based**: Gemini Flash checks headlines vs thesis breach conditions
- Conservative default: when in doubt, ABORT (capital preservation > opportunity)

### Performance Feedback Loop
- Win/loss rate tracking per ticker and overall
- Confidence calibration buckets (does 0.80 confidence = 80% win rate?)
- Exit trigger analysis (which exit type performs best?)
- 52-week thesis archive for long-term pattern detection

## Technical Analysis

### Pre-Computed Indicators
All indicators computed from 250-day OHLCV history before sending to Claude:

| Indicator | Parameters | Purpose |
|-----------|-----------|---------|
| RSI | 14-period | Overbought/oversold detection |
| MACD | 12/26/9 | Momentum direction and crossovers |
| Bollinger Bands | 20-period, 2 std | Squeeze/breakout detection |
| ATR | 14-period | Volatility measurement + position sizing |
| SMA | 20, 50, 200 | Trend direction and support/resistance |
| Price vs SMA | All periods | Above/below key levels |
| Golden/Death Cross | 50 vs 200 SMA | Long-term trend change |
| Volume Trend | 5d vs 20d avg | Volume confirmation of moves |
| Relative Strength | 5d, 20d, 60d vs SPY | Outperformance/underperformance vs market |
| Pairwise Correlation | 60-day rolling | Cross-stock correlation for portfolio risk |

### Market Context
- SPY/QQQ trend (1d, 5d, 20d returns + full indicator suite)
- VIX level and classification (low/normal/elevated/high/extreme_fear)
- 10Y and 2Y Treasury yields
- Sector rotation (11 SPDR sector ETFs, ranked by 5-day performance)
- Market regime classification: strong_bullish, bullish, neutral, bearish, strong_bearish, crisis
- Economic calendar: FOMC, CPI, jobs, GDP, PPI events for the next 7 days

### Enhanced Data per Stock
- Analyst consensus ratings and recent upgrades/downgrades (FMP)
- Price target consensus (high, low, median)
- Insider trading: Form 4 filings from the last 30 days (SEC-API)
- Relative strength vs SPY over 5d, 20d, 60d periods
- Pairwise correlation matrix with other watchlist stocks

### AI Strategy Enhancements
- **Mean reversion detection**: RSI < 30 + price near 200-SMA = bounce setup
- **Sentiment divergence**: Bullish news + falling price = distribution warning
- **Earnings run-up**: 10-15 days before earnings with no negative thesis = drift opportunity
- **Analyst momentum**: Cluster upgrades/downgrades as directional catalysts
- **Insider signal**: Cluster insider buying as a strong bullish signal

## Risk Management

### Six Entry Gates (ALL must pass)
1. **Confidence threshold**: AI confidence >= 0.70
2. **Earnings blackout**: No entry within 5 days of earnings
3. **Drawdown circuit breaker**: Halts at 8% portfolio drawdown from peak
4. **Cash reserve**: Maintains 20% minimum cash at all times
5. **Volatility-adjusted sizing**: ATR-based, targeting 2% risk per position
6. **Sector exposure limit**: Max 40% of portfolio in any single sector

### Broker-Native Stop-Losses
- Bracket orders: entry + stop + take-profit submitted atomically to Alpaca
- Stop-limit orders with 1% buffer to prevent catastrophic slippage
- Stops live on Alpaca's servers, fire 24/7 even if bot is offline
- Orphan detection: every run checks held positions have a stop order
- **Bracket resubmission**: expired day-only brackets are auto-resubmitted next morning with dynamically adjusted entry prices based on current market conditions
- **Gap-down protection**: detects unfilled stop-limit orders after overnight gaps and immediately market-sells the unprotected position

### Trailing Stops
- Activates once a position gains 5%+ from entry price
- Trails 3% below the high-water mark (ratchets up only, never down)
- Never trails below entry price (locks in at least breakeven)
- Never trails below the original thesis stop (doesn't widen risk)
- Cancels the existing stop and replaces with a higher one each execution cycle

### Portfolio-Level Protection
- Peak portfolio tracking for drawdown calculation
- Sector concentration monitoring
- Cash reserve enforcement before any new entry
- Weekly position reviews: CONTINUE, ADJUST (update levels), or CLOSE (explicit exit)
- Pass 2 selection filter (only top 3-5 new trades execute)

### Bear Market Hedging
- In bearish/crisis regimes, inverse ETFs (SH, PSQ, SDS) are added to the analysis
- Claude can recommend buying inverse ETFs to profit from market declines
- These are regular long positions — no margin or shorting mechanics required
- Hedges use short_term or medium_term horizons (not long-term holds)

### Slippage-Aware Execution
- **Entry**: Two-tranche limit orders (already slippage-minimized)
- **News-based ABORT exits**: Limit sell at 0.2% below current (reduces slippage vs market sell)
- **Price-based ABORT exits**: Market sell (urgent, price already moving)
- **Backtesting**: Configurable slippage model (default 0.15% per fill) for realistic results

### Intraday Price Checks
- Lightweight price-only checks between the 9 AM and 3:30 PM sentry runs
- Zero LLM cost — only checks SPY drops and per-stock adverse moves
- Same 3% adverse / 2% SPY thresholds as the sentry's Layer 1 and 2
- Fills the 6.5-hour gap during peak trading hours

## Execution

### Order Types
| Scenario | Order Type | Details |
|----------|-----------|---------|
| Entry | Bracket (limit buy + stop + TP) | Atomic submission to Alpaca |
| Stop-loss | Native stop-limit (GTC) | Broker-side, 1% slippage buffer |
| Take-profit | Native limit sell | Part of bracket or standalone |
| ABORT exit | Market sell | Immediate, after cancelling all orders |
| Bearish flip | Market sell | Exit position when thesis reverses |

### Safety Rails
- Duplicate prevention: checks for existing orders before placing new ones
- Position check: won't buy if already holding the ticker
- Positions refreshed after each trade for accurate sector exposure
- All trades logged with full reasoning chain

## Data Sources

### Financial Modeling Prep (FMP)
- 250-day OHLCV for indicator calculation
- News headlines with deduplication
- Earnings calendar (60-day forward look)
- Current quotes for market context

### SEC-API.io
- Real-time 8-K filing monitoring
- 10-Q and 10-K detection
- Filing descriptions for AI analysis

### Alpaca Markets
- Dual credential support: separate paper and live API key pairs
- Trading mode toggle via API (`GET/PUT /api/settings/mode`) and Flutter app
- Paper mode uses `paper-api.alpaca.markets`, live mode uses `api.alpaca.markets`
- Account info (portfolio value, buying power, cash)
- Position management
- Full order lifecycle (bracket, stop, limit, market)

## Automation

### Server Deployment (Docker) — Primary
- Docker container with Python 3.12 and uv package manager
- Server cron triggers: precise scheduling, no GitHub variance
- State persists via bind-mounted volumes (`./state`, `./logs`)
- Commands: `docker compose run --rm titantrade <command>`

### GitHub Actions Cron Jobs (Alternative)
- Weekly analyst: Sunday 20:00 UTC
- Daily sentry: Weekdays 14:00 UTC (09:00 EST) and 20:30 UTC (15:30 EST)
- State committed back to repo after each run
- Manual trigger via `workflow_dispatch`

### State Persistence
- JSON files in `state/` directory (bind-mounted in Docker)
- Trade log is append-only
- Thesis history retained for 52 weeks
- Peak portfolio value tracked for circuit breaker

## Desktop App (Trade Tracker)

### TitanTrade Desktop (Flutter)
- Cross-platform desktop app (Windows, macOS, Linux)
- Reads state files from the TitanTrade directory (mostly read-only, writes watchlist)
- Polls JSON files every 30 seconds for updates

### Screens
- **Dashboard**: Portfolio overview, active positions, recent trades, sentry signals
- **Active Theses**: Card grid with confidence bars, price levels, expiry countdown
- **Thesis Detail**: Full AI reasoning, breach conditions, sentry status
- **Trade History**: Sortable list with action filters (BUY/SELL)
- **Trade Detail**: Full context — thesis + sentry + execution details + gate results
- **Near Misses**: Trades blocked by 1–2 risk gates, with closeness indicators
- **Near Miss Detail**: Gate checklist, thesis, market context at time of near-miss
- **Watchlist**: Add/remove tracked tickers (writes to data/watchlist.json)
- **Statistics**: Net P&L, realized P&L (BUY->SELL round-trips), unrealized P&L (open positions), operational costs per AI service
- **Settings**: Server URL, refresh interval, paper/live trading mode toggle with confirmation dialog

## Operational Cost Tracking

### Per-Call AI Cost Logging
- Every Claude and Gemini API call logs token usage to `state/costs.json`
- Token counts captured from API response metadata (input + output)
- Estimated USD cost computed from published model pricing
- Labeled per stock and run type (weekly analyst / daily sentry)

### Statistics Dashboard
- **Net P&L**: Trading gains minus operational costs — the true bottom line
- **Realized P&L**: Matched BUY->SELL round-trips with per-trade profit/loss
- **Unrealized P&L**: Current paper gains/losses on open positions
- **Cost breakdown**: Per-service (Claude, Gemini) call counts, tokens, and spend
- **Recent API calls**: Last 20 calls with timestamps, descriptions, and costs

## Test Suite (Zero Token Spend)

All tests run without making real API calls to Claude, Gemini, Alpaca, or FMP.
AI and broker interactions are mocked via `unittest.mock.patch`.

### Coverage
- **Indicators** (31 tests): SMA, EMA, RSI, MACD, Bollinger Bands, ATR, volume, price vs SMA
- **AI Parsing** (29 tests): JSON extraction, markdown fence removal, trailing commas, schema validation, malformed input fallbacks
- **Risk Manager** (32 tests): All 6 gates individually, pre_trade_check integration, near-miss detection, gate dependency chains
- **Weekly Analyst** (5 tests): Mocked Claude returning valid/invalid/partial JSON
- **Daily Sentry** (5 tests): Mocked Gemini, price-based ABORT override, garbage response handling
- **Executor** (12 tests): Trade context building, bracket placement, near-miss recording, resubmission logic
- **Trailing Stops** (10 tests): Activation threshold, HWM tracking, never-below-entry, state persistence, cleanup
- **Price Check** (6 tests): SPY stress abort, per-stock adverse moves, signal file persistence
- **Gap-Down Protection** (6 tests): Gap detection, stop-limit cancellation, margin tolerance, edge cases
- **Orphan Close** (7 tests): Expired thesis, missing ticker, zero-qty positions, empty state
- **Dynamic Entry** (13 tests): Price adjustment, chase limit, invalidated thesis, risk ratio preservation
- **Strategy Features** (19 tests): Relative strength, correlation, macro blackout, correlation limit, two-tranche split

### Running Tests
```bash
cd TitanTrade
uv run python -m pytest tests/ -v
```
