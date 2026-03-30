# Risk Management

## Philosophy

TitanTrade's risk management follows the principle: **the system's job is to not lose
money, and secondarily to make money.** Every feature exists to prevent catastrophic
losses. Missed opportunities are cheap; blown accounts are permanent.

## Three Lines of Defense

### Line 1: AI Quality Control
- **Two-pass analysis**: Pass 2 filters out low-quality ideas from Pass 1
- **Confidence threshold**: Only trades with >= 70% confidence execute
- **Performance feedback**: Claude sees its historical accuracy and self-corrects
- **Market regime awareness**: Fewer trades in bearish/crisis regimes

### Line 2: Programmatic Risk Gates
Eight hard gates between the AI and the brokerage, enforced in code:

#### Gate 1: Confidence Threshold (>= 0.70)
- Filters out weak conviction calls
- Claude's confidence is calibrated against actual outcomes
- Threshold set at 0.70 based on typical hit rates

#### Gate 2: Earnings Blackout (5 days)
- Earnings create unhedgeable binary risk
- No new entries within 5 calendar days of earnings
- FMP earnings calendar checked every data bundle build
- Even if Claude is BULLISH with 0.95 confidence, this gate blocks

#### Gate 3: Drawdown Circuit Breaker (8% from peak)
- Tracks portfolio high-water mark in `state/peak_portfolio.json`
- If portfolio drops 8%+ from peak, ALL new entries halted
- Only resets when portfolio recovers or next weekly analyst runs
- Prevents cascading losses in correlated selloffs

#### Gate 4: Cash Reserve (20% minimum)
- Always maintain 20% of portfolio in cash
- Cash provides optionality for opportunities
- Prevents going all-in even with 10 BULLISH theses
- Position sizes reduced to fit within available cash

#### Gate 5: Volatility-Adjusted Position Sizing
- Uses ATR (Average True Range) instead of fixed percentage
- Risk budget: 2% of portfolio per 1-ATR move
- High-vol stocks (TSLA): smaller position (maybe 6%)
- Low-vol stocks (JPM): larger position (maybe 12%)
- Capped at 10% regardless (hard upper limit)
- Falls back to fixed 10% if ATR unavailable

#### Gate 6: Sector Exposure Limit (40% max)
- Maps each stock to its GICS sector
- Tracks current sector exposure from Alpaca positions
- Blocks new entry if it would push sector above 40%
- Prevents tech concentration disaster (5 of 10 watchlist stocks are tech-adjacent)

#### Gate 7: Macro Event Blackout (24 hours)
- Checks FMP economic calendar for high-impact events (FOMC, CPI, jobs, GDP, PPI)
- Blocks new entries within 24 hours of a major macro event
- Macro events can move the entire market 1-3% in minutes, creating unhedgeable risk

#### Gate 8: Correlation Limit (75% average)
- Computes 60-day pairwise correlation between the new stock and all held positions
- Blocks entry if the average correlation exceeds 75%
- Prevents hidden concentration: AAPL+GOOGL+META are in different sectors but 80% correlated

### Line 3: Broker-Native Stop-Losses
- Stop-loss orders live on Alpaca's servers
- Fire in real time, 24/7, even if bot is completely offline
- Stop-limit with 1% buffer (prevents unlimited slippage)
- Every execution run checks for orphaned positions without stops
- Bracket orders ensure stop is atomically placed with entry
- **Trailing stops**: once a position gains 5%+, the stop ratchets up to trail 3% below the high-water mark
- **Gap-down protection**: if a stop-limit fails to fill due to a price gap, the position is immediately market-sold

## Daily Protection (Sentry)

### Layer 1: Market-Wide Check
- SPY drop > 2% = market stress
- All positions flagged for enhanced review
- Gemini receives this as context in its prompt

### Layer 2: Price-Based Override
- Stock moves 3%+ against thesis = hard ABORT
- This overrides Gemini's assessment (price > opinion)
- Catches pre-news institutional selling

### Layer 3: News-Based AI Check
- Gemini Flash compares headlines vs breach conditions
- Conservative default: lean toward ABORT when uncertain
- Includes price and market alerts as additional context

## Position Sizing Formula

```
ATR-Based:
  dollar_risk = portfolio_value * 0.02  (2% risk budget)
  shares = dollar_risk / ATR_14
  cap at portfolio_value * 0.10 / entry_price  (10% hard cap)

Fixed Fallback (no ATR available):
  shares = portfolio_value * 0.10 / entry_price
```

## Parameters

| Parameter | Value | Defined In | Rationale |
|-----------|-------|-----------|-----------|
| `MIN_CONFIDENCE` | 0.70 | risk_manager.py | Filters low-conviction noise |
| `MAX_DRAWDOWN_PCT` | 8.0% | risk_manager.py | Circuit breaker threshold |
| `MIN_CASH_RESERVE_PCT` | 20.0% | risk_manager.py | Maintains optionality |
| `MAX_SECTOR_EXPOSURE_PCT` | 40.0% | risk_manager.py | Prevents concentration |
| `ATR_RISK_BUDGET` | 0.02 | risk_manager.py | 2% portfolio risk per ATR |
| `stop_loss_pct` | 0.05 | watchlist.json | 5% below entry |
| `risk_per_trade` | 0.10 | watchlist.json | 10% max position |
| `PRICE_MOVE_ABORT_PCT` | 3.0% | daily_sentry.py | Adverse move threshold |
| `MARKET_DROP_ALERT_PCT` | 2.0% | daily_sentry.py | SPY stress threshold |
| `DEFAULT_BLOCK_DAYS` | 5 | earnings.py | Earnings blackout window |

## What This Prevents

| Scenario | Protection |
|----------|-----------|
| Stock drops 15% overnight | Broker-native stop-loss fires at 5% |
| Bad earnings surprise | Earnings blackout prevents entry |
| Market-wide crash | Drawdown circuit breaker halts entries |
| Sector rotation kills tech | 40% sector cap limits exposure |
| AI gives bad advice | Confidence gate + Pass 2 ranking |
| Bot goes offline | Stops live on Alpaca, no bot needed |
| Concentrated portfolio | Pass 2 enforces diversification |
| Overtrading | Cash reserve + 3-5 trade limit per week |
| Volatile stock oversized | ATR-based sizing scales down |
| Stale analysis | 14-day thesis expiry + orphan position closing |
| Stop-limit gap failure | Gap-down protection (market sell fallback) |
| Giving back open gains | Trailing stop (5% trigger, 3% trail) |
| Monitoring gap (6.5h) | Intraday price checks (no LLM cost) |
