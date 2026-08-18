# Risk Management

## Philosophy

TitanTrade's risk management follows the principle: **the system's job is to not lose
money, and secondarily to make money.** Every feature exists to prevent catastrophic
losses. Missed opportunities are cheap; blown accounts are permanent.

## Three Lines of Defense

### Line 1: AI Quality Control
- **Two-pass analysis**: Pass 2 filters out low-quality ideas from Pass 1
- **Confidence threshold**: 0.55 floor; conviction scales position size, not selection
- **Performance feedback**: Claude sees its historical accuracy and self-corrects
- **Market regime awareness**: Fewer trades in bearish/crisis regimes

### Line 2: Programmatic Risk Gates
Nine hard gates between the AI and the brokerage, enforced in code:

#### Gate 1: Confidence Threshold (>= 0.55 floor, sizing-scaled)
- Filters out weak conviction calls; confidence below 0.55 skips entirely
- Above the floor, confidence drives sizing on a steep curve (0.40x at 0.55 →
  1.00x at 0.70 → 2.50x at 0.95+, Decision 032 redesign) — selection is loose,
  sizing does the work
- Claude's confidence is calibrated against actual outcomes

#### Gate 2: Earnings Blackout (2 days)
- Earnings create unhedgeable binary risk
- No new entries within 2 calendar days of earnings (narrowed from 5,
  Decision 046 — setups 3-4 days out can play out normally)
- Finnhub earnings calendar checked every data bundle build
- Even if Claude is BULLISH with 0.95 confidence, this gate blocks

#### Gate 3: Drawdown Circuit Breaker (8% from peak)
- Tracks portfolio high-water mark in `state/peak_portfolio.json`
- If portfolio drops 8%+ from peak, ALL new entries halted
- Only resets when portfolio recovers or next weekly analyst runs
- Prevents cascading losses in correlated selloffs
- **Suspect-value guard** (Decision 054): a reported portfolio value more than ±50% off the recorded peak is treated as broker data corruption, not market reality (production: Alpaca paper returned $22,828 against a real ~$100k equity mid-way through CRWD's split processing, tripping the breaker at a phantom "79.1%"). Entries still pause for the run (fail-safe), but the block is labeled "suspect broker data" and alerted via Discord (deduped), and `update_peak_value` refuses to record a >+50% spike — a glitch written into the peak file would permanently trip the breaker once real values returned

#### Gate 4: Cash Reserve (5% minimum, net of pending commitments)
- Always maintain 5% of portfolio in cash (lowered from 20% — see Decision 032; cash is transit, not a destination)
- Position sizes reduced to fit within available cash
- **Committed-cash netting** (Decision 035): the gate subtracts the notional of already-pending (unfilled) BUY orders before checking the reserve. Entry brackets are day-limit orders that don't consume cash until they fill, so raw settled cash overstates what's free — without this, N simultaneously-pending brackets each passed the reserve against the same cash and then collectively filled into margin (production: cash hit −$6,379, buying power 2-3× portfolio). `open_buy_commitment()` sums pending buy notional; `max_investable_amount(pv, cash, committed_cash)` and `pre_trade_check(..., committed_cash=...)` net it out.

#### Gate 5: Volatility-Adjusted Position Sizing
- Uses ATR (Average True Range) instead of fixed percentage
- Risk budget: 2.5% of portfolio per 1-ATR move
- High-vol stocks: smaller position; low-vol stocks: larger position
- Confidence- and VIX-scaled (Decisions 032/033), capped at 25% of the
  portfolio regardless (hard upper limit)
- Falls back to the fixed `risk_per_trade` fraction (10%) if ATR unavailable
- **Minimum notional floor** (Decision 054): after the cash-reserve and overlay-cap reductions, an order below `MIN_POSITION_NOTIONAL` ($500) is blocked as dust. Production filled URI 0.01 sh ($11) and ANET 0.19 sh ($35) when nearly all cash was committed — positions that can't carry stops (Alpaca rejects stops on sub-1-share orders) and only generate churn and fees. Blocked dust fails the `position_size` gate and is recorded as a near-miss like any other gate failure

#### Gate 6: Sector Exposure Limit (50% max)
- Maps each stock to its GICS sector
- Tracks current sector exposure from Alpaca positions
- Blocks new entry if it would push sector above 50% (raised from 40%,
  Decision 032 — allow tighter concentration when conviction warrants)
- Prevents a single-sector concentration disaster

#### Gate 7: Macro Event Blackout (6 hours, high-impact only)
- Checks the FRED economic calendar (+ `data/fomc_dates.json`) for
  high-impact events only: FOMC, NFP/jobs, CPI, core PCE, GDP (Decision 046
  whitelist — minor indicators no longer block trading)
- Blocks new entries within 6 hours of a whitelisted event (was 24h)
- Macro events can move the entire market 1-3% in minutes, creating unhedgeable risk

#### Gate 8: Correlation Limit (75% average)
- Computes 60-day pairwise correlation between the new stock and all held positions
- Blocks entry if the average correlation exceeds 75%
- Prevents hidden concentration: AAPL+GOOGL+META are in different sectors but 80% correlated

#### Gate 9: Total Overlay Cap (70%)
- Combined AI-pick (overlay) positions can't exceed 70% of the portfolio
  (Decision 033) — protects the always-on ~30% SPY core allocation
- Evaluated between the cash-reserve and position-size gates; the safety net
  that makes the confidence-scaled sizing (up to 25% per name) safe

### Line 3: Broker-Native Stop-Losses
- Stop-loss orders live on Alpaca's servers
- Fire in real time, 24/7, even if bot is completely offline
- Stop-limit with 1% buffer (prevents unlimited slippage)
- Every execution run checks for orphaned positions without stops
- Bracket orders ensure stop is atomically placed with entry
- **Trailing stops**: once a position gains 5%+, the stop ratchets up to trail 3.0×ATR below the high-water mark (Decision 033; widened 2.5→3.0 in Decision 048 — more bull capture, no added bear risk), falling back to a 5% trail when ATR is unavailable
- **Gap-down protection**: if a stop-limit fails to fill due to a price gap, the position is immediately market-sold. The cancel of the stale stop-limit is polled to a terminal state *before* the protective market sell so the sell isn't rejected for held qty (Decision 035).
- **Never-bare guarantee** (Decision 035): on a partial sell (TP1), the sell is polled to `filled` before the breakeven stop is sized, and `place_native_stop_loss` clamps to the broker-reported `available` qty if its intended qty is momentarily short. The combination ensures a position is never left without a stop after a partial sell or stop cancel+replace.
- **Minimum stop-distance floor** (Decision 055): a fresh entry or bracket resubmission is refused when the thesis stop sits < 1.5% below the (adapted) entry — inside intraday noise, a guaranteed immediate stop-out (production: URI entered with a 0.28% stop, tagged out 27 minutes later). Flat floor by design — an ATR-scaled floor would exceed normal stop distances on high-vol names and refuse legitimate entries.
- **Same-run ABORT entry guard** (Decision 055): bracket resubmission and the bullish-entry path skip any ticker whose *current* sentry signal is ABORT. The 72h re-entry cooldown starts when the abort is handled — which happens after resubmission runs — so without this check a resubmitted bracket could fill seconds before the abort handler market-sells it (the LLY 18-second round-trip).
- **Pyramiding** uses cancel → market-buy → re-stop (Decision 037): a live probe proved Alpaca rejects BOTH market and limit buys against a resting protective stop (wash-trade rule), so the add drops the stop, market-buys (fastest fill = shortest unprotected window), then re-places a stop covering the enlarged position. Every failure path restores a stop.
- **Stop-out re-entry cooldown** (Decision 056): a broker-side protective-stop fill now starts the same 72h re-entry cooldown an ABORT does (clock stamped at the fill time; same sentry-confirmed override policy). Without it, a stopped-out ticker could be re-bought minutes later — production DVN re-entered 42 minutes after its stop fired.
- **Stale-ADJUST guard** (Decision 056): weekly-review ADJUST levels are not applied to a position opened *after* the review was generated — they were computed for a position that no longer exists (the DVN $43.50-stop-on-a-$43.65-entry case). The entry-time stop is kept until the next review re-syncs.

## Daily Protection (Sentry)

### Layer 1: Market-Wide Check
- SPY drop > 2% = market stress
- All positions flagged for enhanced review
- Gemini receives this as context in its prompt

### Layer 2: Price-Based Override (graduated, Decision 045)
- >= 5% adverse move = catastrophic, always ABORT (regardless of news)
- 3-5% adverse move ABORTs only with Gemini news confirmation; without it the
  move is logged as noise and the broker-side stop remains the protection
- Catches pre-news institutional selling without whipsawing on normal volatility

### Layer 3: News-Based AI Check
- Gemini Flash compares headlines vs breach conditions
- Decision asymmetry (Decision 034 prompts): false ABORTs cost money, false
  CONTINUEs are caught by the broker-side stop — a news-only ABORT without an
  adverse price move is downgraded to CONTINUE by the executor
- Includes price, market, and held-position P&L context

## Position Sizing Formula

```
ATR-Based:
  dollar_risk = portfolio_value * 0.025  (2.5% risk budget)
  shares = dollar_risk / ATR_14
  scaled by confidence (0.40x-2.50x) and VIX (0.40x-1.20x)
  cap at portfolio_value * 0.25 / entry_price  (25% hard cap)

Fixed Fallback (no ATR available):
  shares = portfolio_value * 0.10 / entry_price  (risk_per_trade)
```

## Parameters

| Parameter | Value | Defined In | Rationale |
|-----------|-------|-----------|-----------|
| `MIN_CONFIDENCE` | 0.55 | risk_manager.py | Probe floor; sizing curve does the work above it |
| `MAX_DRAWDOWN_PCT` | 8.0% | risk_manager.py | Circuit breaker threshold |
| `MIN_CASH_RESERVE_PCT` | 5.0% | risk_manager.py | Cash is transit, not a destination (Decision 032) |
| `MAX_SECTOR_EXPOSURE_PCT` | 50.0% | risk_manager.py | Prevents concentration |
| `MAX_POSITION_PCT` | 0.25 | risk_manager.py | Hard per-name cap (high-conviction max) |
| `MAX_TOTAL_OVERLAY_PCT` | 0.70 | risk_manager.py | Protects the ~30% SPY core |
| `MIN_POSITION_NOTIONAL` | $500 | risk_manager.py | Dust guard (Decision 054) |
| `MAX_AVG_CORRELATION` | 0.75 | risk_manager.py | Hidden-concentration guard |
| `MACRO_BLACKOUT_HOURS` | 6 | risk_manager.py | High-impact events only |
| `ATR_RISK_BUDGET` | 0.025 | risk_manager.py | 2.5% portfolio risk per ATR |
| `trailing_atr_multiplier` | 3.0 | config.py | Trail width below HWM (Decision 048) |
| `MIN_STOP_DISTANCE_PCT` | 1.5% | pricing.py | Noise-level stop floor (Decision 055) |
| `REENTRY_COOLDOWN_HOURS` | 72 | cooldown.py | Post-exit whipsaw guard (ABORTs + stop-outs, Decision 056) |
| `stop_loss_pct` | 0.05 | watchlist.json | Default 5% below entry |
| `risk_per_trade` | 0.10 | watchlist.json | Fallback sizing fraction |
| `PRICE_MOVE_ABORT_PCT` | 3.0% | daily_sentry.py | Adverse-move threshold (news-confirmed band) |
| `PRICE_MOVE_HARD_ABORT_PCT` | 5.0% | daily_sentry.py | Catastrophic always-ABORT threshold |
| `MARKET_DROP_ALERT_PCT` | 2.0% | daily_sentry.py | SPY stress threshold |
| `DEFAULT_BLOCK_DAYS` | 2 | earnings.py | Earnings blackout window |

## What This Prevents

| Scenario | Protection |
|----------|-----------|
| Stock drops 15% overnight | Broker-native stop-loss fires at the thesis stop |
| Bad earnings surprise | Earnings blackout prevents entry |
| Market-wide crash | Drawdown circuit breaker halts entries |
| Sector rotation kills tech | 50% sector cap limits exposure |
| AI gives bad advice | Confidence gate + Pass 2 ranking |
| Bot goes offline | Stops live on Alpaca, no bot needed |
| Concentrated portfolio | Pass 2 enforces diversification |
| Overtrading | Cash reserve + 3-5 trade limit per week |
| Volatile stock oversized | ATR-based sizing scales down |
| Stale analysis | Weekly review cycle + orphan position closing |
| Stop-limit gap failure | Gap-down protection (market sell fallback) |
| Giving back open gains | Trailing stop (5% trigger, 3.0×ATR trail) |
| Monitoring gap (6.5h) | Intraday price checks (no LLM cost) |
