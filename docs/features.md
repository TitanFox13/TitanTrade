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
- Truncated JSON repair: salvages Gemini responses that hit token limits mid-output
- SPY change computed from price/previousClose fallback when API field missing
- Regime-aware reviews: inverse ETF positions get explicit warnings in non-bearish regimes
- Hardened retry policy: 5 attempts, jitter, 429 + `Retry-After` support, 60s timeout for AI endpoints
- Free SEC EDGAR for 8-K/10-Q/10-K/Form 4 filings (replaces paid SEC-API.io)
- `HTTPError` exception preserves broker response bodies (e.g. Alpaca error codes) for diagnostics
- Stop-loss placement is idempotent and survives Alpaca cancel races by
  polling the specific blocking order's `status` (from `related_orders`)
  until terminal — deterministic, replaces the lossy `qty_available` poll
- Market-hours-aware execution: ADJUST, orphan-close, and trailing-stop
  adjustments defer to the next market-open run rather than getting stuck
  in `pending_cancel` for hours
- Bracket math sanity check refuses invalid (stop >= entry) brackets before
  the broker rejects them — happens when ADJUSTed thesis is reused for a
  new entry
- Graduated price-ABORT severity: 3-5% needs Gemini news confirmation,
  >=5% always aborts. Reduces noise-driven churn in normal volatility.
- 72-hour re-entry cooldown after every ABORT — prevents the "sell low,
  buy higher" cycles previously observed in production
- High-impact-only macro blackout (FOMC, NFP, CPI, core PCE, GDP); 6h
  window instead of 24h; minor indicators no longer block trading
- Pass 2 target trade count scales with market regime (6 in strong_bullish
  down to 1 in crisis); the confidence-scaled sizing now correctly uses
  Pass-2's `adjusted_confidence`
- Bracket resubmission gives up after 5 chasing attempts on the same
  ticker; resumes only after the next weekly thesis refresh
- Sentry price-move check references the actual broker
  `avg_entry_price` for held positions, not the stale thesis target
- Narrower 2-day earnings blackout (was 5 days)
- Append-only state files auto-archive to `state/archive/` when they grow
  past 500 trades / 200 near-misses
- Discord alerts for "stuck in cash >70% for 3+ days" and
  "ticker round-tripped 2+ times in 7 days"
- Sentry skips tickers that aren't selected for trading — no API calls for closed positions
- Sentry records fallback ratio and fires a Discord alert when Gemini coverage degrades (>30% of checks fall back)
- Flutter dashboard shows sentry health badge (green healthy / orange degraded) from the same signal
- ADJUST flow restores the previous stop on failure so held positions are never unprotected
- Gemini structured output (`responseMimeType: application/json` + schema) + thinking disabled — valid JSON guaranteed, ~10× fewer tokens per sentry check
- Backtest A/B runner (`python -m titantrade backtest-ab`) to empirically validate confidence-scaling against the flat baseline

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
5. **Volatility-adjusted sizing**: ATR-based, targeting 2% risk per position, scaled by confidence (0.7x at 0.70 to 1.3x at 1.00)
6. **Sector exposure limit**: Max 40% of portfolio in any single sector

### Broker-Native Stop-Losses
- Bracket orders: entry + stop + take-profit submitted atomically to Alpaca
- Stop-limit orders with 1% buffer to prevent catastrophic slippage
- Stops live on Alpaca's servers, fire 24/7 even if bot is offline
- Orphan detection: every run checks held positions have a stop order
- **Bracket resubmission**: expired day-only brackets are auto-resubmitted next morning with dynamically adjusted entry prices based on current market conditions (resubmits floor to whole shares — a sub-1-share size is skipped, never sent as a fractional bracket that Alpaca rejects with HTTP 422)
- **Gap-down protection**: detects unfilled stop-limit orders after overnight gaps and immediately market-sells the unprotected position. The stale stop's cancel is polled to a terminal state *before* the market sell so the sell isn't rejected for still-held qty (Decision 035)
- **Never-bare guarantee** (Decision 035): after a partial sell (TP1), the sell is polled to `filled` before the breakeven stop is sized; `place_native_stop_loss` clamps to the broker-reported `available` qty if momentarily short. A position is never left without a stop after a partial sell or stop replace.

### Trailing Stops
- Activates once a position gains 5%+ from entry price
- Trails 3% below the high-water mark (ratchets up only, never down)
- Never trails below entry price (locks in at least breakeven)
- Never trails below the original thesis stop (doesn't widen risk)
- Cancels the existing stop and replaces with a higher one each execution cycle

### Pyramiding Into Winners
- Adds to a position once per ticker when it's working (+5% gain with the trailing stop active, so combined downside is bounded)
- Adds 50% of the original notional, capped at the per-ticker concentration limit (30% of portfolio)
- Uses a **marketable limit buy**, never a market buy — a market buy placed while the protective sell stop rests on the book is rejected by Alpaca as a wash trade (Decision 035). After the add fills, the stop is extended to cover the enlarged position.

### Portfolio-Level Protection
- Peak portfolio tracking for drawdown calculation
- Sector concentration monitoring
- Cash reserve enforcement before any new entry — **nets out cash already committed to pending buy orders** so simultaneous entries can't collectively breach the reserve into margin (Decision 035)
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
| Entry (whole shares) | Bracket (limit buy + stop + TP) | Atomic submission to Alpaca |
| Entry (fractional) | Day limit buy | No bracket support for fractional; sentry provides safety net |
| Stop-loss | Native stop-limit (GTC) | Broker-side, 1% slippage buffer (whole shares only) |
| Take-profit | Native limit sell | Part of bracket or standalone |
| ABORT exit | Market sell | Immediate, after cancelling all orders |
| Bearish flip | Market sell | Exit position when thesis reverses |

### Fractional Shares
- Supported for accounts too small for whole shares (e.g., $500 starting balance)
- Position sizing snaps to whole shares when >= 1, keeps fractional (2 decimals) when < 1
- Fractional entries use day-limit buys (bracket orders don't support fractional on Alpaca)
- Fractional positions rely on sentry + price checks for downside protection (no broker-native stops)
- Minimum $1.00 notional per order (Alpaca requirement)
- As the account grows, positions automatically shift back to bracket orders

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
- **Built-in scheduler** (APScheduler): all cron jobs run inside the API container
- No host-level cron required — schedule defined in `data/schedule.json`
- **Daily data refresh**: a `weekday_fetch` job (13:00 UTC, before the morning sentry/execute) rebuilds `data_bundle.json` every weekday so trend-regime/ATR decisions never run on stale data — previously the bundle only refreshed in the weekly Sunday pipeline and aged to 120h+ by Friday (Decision 035)
- State persists via bind-mounted volumes (`./data`, `./state`, `./logs`)
- Scheduler screen in Flutter app: view status, enable/disable, manual trigger
- CLI commands still available: `docker compose run --rm titantrade <command>`

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
- **Scheduler**: View all cron jobs, status, next/last run, enable/disable toggle, manual trigger button

## Discord Notifications

### Job Alerts
- Every scheduled job sends a Discord embed on completion (green) or failure (red)
- Includes job name, result summary, and duration
- Error messages included in failure notifications (truncated to 1000 chars)
- Notification failures never crash the underlying job

### Daily Portfolio Summary
- Sent weekdays at 21:00 UTC (4 PM EST) after the last sentry run
- Includes: portfolio value, cash, open positions with P&L, trailing stop status
- Shows today's sentry signals (CONTINUE/ABORT counts) and any trades executed
- Displays current trading mode (PAPER/LIVE)

### Configuration
- Single env var: `DISCORD_WEBHOOK_URL` (optional)
- If unset, all notifications are silently skipped — no crashes, no errors
- Uses Discord embed format with color-coded status (green/red/blue)

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
- **Notifier** (15 tests): Discord embed formatting, no-op without webhook, job success/failure content, daily summary state parsing, error resilience

### Running Tests
```bash
cd TitanTrade
uv run python -m pytest tests/ -v
```
