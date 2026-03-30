# Important Decisions Log

## Decision 001: Dual-AI Architecture (Claude + Gemini)
**Date**: 2026-03-29
**Decision**: Use Claude for weekly deep analysis and Gemini Flash for daily sentiment checks.
**Reasoning**:
- Claude Opus/Sonnet excels at complex reasoning and structured analysis
- Gemini Flash is optimized for speed and cost on simple classification tasks
- Weekly deep dives don't need sub-second latency; daily checks do
- Cost optimization: ~$0.50/week for Claude vs ~$0.01/day for Gemini Flash
**Trade-offs**:
- Two API integrations to maintain instead of one
- Potential inconsistency between models' interpretations
- Mitigated by clear prompt engineering and structured JSON outputs

## Decision 002: Alpaca Markets as Brokerage
**Date**: 2026-03-29
**Decision**: Use Alpaca Markets API for trade execution.
**Reasoning**:
- Free paper trading with identical API to live trading
- Commission-free stock trading
- Well-documented REST and streaming APIs
- Python SDK available (`alpaca-trade-api`)
- Supports fractional shares
**Trade-offs**:
- Limited to US equities (no international markets)
- No options trading via API (stock only for now)

## Decision 003: JSON File-Based State (No Database)
**Date**: 2026-03-29
**Decision**: Use JSON files in `state/` directory for persistence instead of a database.
**Reasoning**:
- Simplicity: No database setup, connection strings, or migrations
- Portability: State files can be committed to repo or backed up easily
- Sufficient for 10-stock watchlist with daily updates
- GitHub Actions can read/write files in the repo
**Trade-offs**:
- No concurrent write safety (acceptable for single-process cron jobs)
- No query capability (acceptable for small dataset)
- Future migration to Supabase planned if scale increases

## Decision 004: GitHub Actions for Scheduling
**Date**: 2026-03-29
**Decision**: Use GitHub Actions cron workflows instead of a dedicated server.
**Reasoning**:
- Zero infrastructure cost (free tier sufficient)
- No server maintenance or uptime monitoring
- Secrets management built-in
- Easy to modify schedules via YAML
**Trade-offs**:
- GitHub Actions cron has ~5-15 minute variance on schedule
- Not suitable for intraday high-frequency strategies
- Acceptable for our weekly + daily cadence

## Decision 005: FMP API for Financial Data
**Date**: 2026-03-29
**Decision**: Use Financial Modeling Prep (FMP) API as primary data source.
**Reasoning**:
- Single API for both price data AND news headlines
- Free tier available for development
- Covers fundamentals, technicals, and news
- Good documentation and reliability
**Trade-offs**:
- Rate limits on free tier (250 requests/day)
- Paid tier needed for production ($14/month)
- News coverage may not be as comprehensive as Bloomberg

## Decision 006: SEC-API.io for Regulatory Filings
**Date**: 2026-03-29
**Decision**: Use SEC-API.io for real-time SEC filing monitoring.
**Reasoning**:
- Structured API for 8-K, 10-Q, 10-K filings
- Near real-time filing detection
- Pre-parsed filing metadata
**Trade-offs**:
- Additional API key to manage
- Paid service ($49/month for real-time)
- Could use free SEC EDGAR RSS as fallback

## Decision 009: Native Broker-Side Stop Orders (Not Software Stops)
**Date**: 2026-03-29
**Decision**: Use Alpaca's native stop and bracket orders, not software price-checking.
**Reasoning**:
- Software stop-loss (cron job checks price twice daily) has a 12+ hour gap between checks
- A stock can fall 20%+ overnight; a software stop wouldn't fire until the next run
- Alpaca native stops fire in real time at the broker level, even if our bot is completely offline
- Bracket orders (entry + stop + take-profit in one atomic submission) eliminate timing gaps
**Implementation**:
- Entry: `bracket` order type with `order_class: "bracket"`
- Stop leg: `stop_limit` with 1% buffer below stop price (avoids catastrophic slippage)
- Take-profit leg: limit sell at target (optional, only when Claude identifies clear catalyst)
- Standalone `stop_limit` GTC order as fallback if position exists without a stop
**Trade-offs**:
- Bracket orders are `time_in_force: "day"` only on Alpaca, not GTC
  - Workaround: re-submit bracket each morning if limit buy hasn't filled
- Stop-limit (not pure stop) means we could miss a fill if stock gaps through both prices
  - Acceptable - better than unlimited downside

## Decision 007: 5% Stop-Loss and 10% Position Sizing
**Date**: 2026-03-29
**Decision**: Hard 5% stop-loss and max 10% position size.
**Reasoning**:
- 5% stop-loss limits max loss per trade to 0.5% of portfolio
- 10% position limit ensures diversification across watchlist
- Conservative enough for an automated system
- Prevents catastrophic losses from a single bad trade
**Trade-offs**:
- May get stopped out of volatile but ultimately profitable positions
- 10% limit means max 100% invested with 10 stocks (no concentration bets)
- Acceptable for a risk-managed automated system

## Decision 010: Two-Pass Analysis (Individual + Portfolio Ranking)
**Date**: 2026-03-29
**Decision**: Use two separate Claude calls per weekly cycle - one per stock, then one portfolio-level.
**Reasoning**:
- Pass 1 in isolation prevents anchoring bias between stocks
- Pass 2 adds portfolio-level thinking (diversification, correlation, regime)
- A single mega-prompt with all 10 stocks would exceed quality thresholds
- Selecting top 3-5 from 10 BULLISH calls prevents overtrading
**Trade-offs**:
- 11 Claude API calls per week instead of 1 (10 stocks + 1 ranking)
- More expensive but the quality difference is substantial
- Pass 2 may disagree with Pass 1 (this is the point - portfolio > individual)

## Decision 011: Pre-Computed Technical Indicators
**Date**: 2026-03-29
**Decision**: Compute RSI/MACD/Bollinger/ATR/SMA before sending to Claude.
**Reasoning**:
- Claude can reason about "RSI at 28" much better than about 5 OHLCV rows
- 250-day history needed for 200-SMA but only 5 days sent as OHLCV
- Indicators are deterministic - no ambiguity in computation
- ATR doubles as the position sizing input (vol-adjusted)
**Implementation**:
- Pure Python computation (no numpy/pandas dependency)
- Wilder's smoothing for RSI and ATR (standard industry method)

## Decision 012: Three-Layer Sentry (Market + Price + News)
**Date**: 2026-03-29
**Decision**: Add price-based and market-wide checks to the daily sentry.
**Reasoning**:
- News is lagging: a stock drops 5% before the headline appears
- Price catches insider selling, block trades, and other non-public information
- SPY check catches correlated risk that per-stock analysis misses
- 3% price override is a hard safety rail - even if Gemini says CONTINUE
**Trade-offs**:
- More aggressive: may force exits that recover later
- Acceptable: preserving capital is job #1

## Decision 013: Performance Feedback Loop
**Date**: 2026-03-29
**Decision**: Feed last 4 weeks of trade results back into Claude's prompt.
**Reasoning**:
- Without feedback, Claude repeats the same mistakes week after week
- Confidence calibration shows if Claude is systematically over/underconfident
- Per-ticker stats reveal blind spots (always wrong on TSLA, always right on AAPL)
- 52-week thesis archive enables long-term pattern detection
**Trade-offs**:
- Larger prompt = more tokens = higher cost
- Risk of recency bias (last 4 weeks may not represent the future)
- Mitigated by using rolling windows and bucket-based calibration

## Decision 008: Structured JSON Output from AI
**Date**: 2026-03-29
**Decision**: Require strict JSON output format from both AI agents.
**Reasoning**:
- Programmatically parseable without regex or NLP
- Schema validation possible
- Consistent structure across all runs
- Easier logging and comparison
**Trade-offs**:
- May reduce AI's ability to express nuance
- Requires careful prompt engineering to enforce format
- Mitigated by including "reasoning" field for free-text explanation

## Decision 014: Server-Based Deployment with Docker (Primary over GitHub Actions)
**Date**: 2026-03-29
**Decision**: Use Docker containers on a personal server with cron jobs as the primary deployment method, replacing GitHub Actions as the default.
**Reasoning**:
- Server cron is precise; GitHub Actions cron has ~5-15 minute variance
- No dependency on GitHub uptime or runner availability
- State persists locally via Docker volumes instead of git commits
- No risk of merge conflicts on state files from concurrent bot pushes
- More operational control and visibility
**Trade-offs**:
- Requires maintaining a server (uptime, security, updates)
- Must handle own monitoring and alerting for missed runs
- Mitigated by cron output logging and server-level monitoring
- GitHub Actions workflows remain in repo as a documented alternative

## Decision 015: Flutter Desktop App for Trade Tracking
**Date**: 2026-03-29
**Decision**: Add a Flutter desktop app (`titan_trade_app/`) as a companion dashboard for TitanTrade.
**Reasoning**:
- JSON log files and state files are machine-readable but not human-friendly for quick review
- Need to understand the full context behind each trade: thesis, sentry signals, execution details
- Desktop-first (Windows/macOS/Linux) since it reads local state files from the TitanTrade directory
- Flutter enables cross-platform desktop from a single codebase
**Trade-offs**:
- Adds Dart/Flutter as a second language alongside Python
- Mostly read-only: the app reads state files but can modify `data/watchlist.json`
- Requires Flutter SDK installed for development
**Architecture**:
- Riverpod for state management, go_router for navigation
- Polls JSON files every 30 seconds (state changes infrequently)
- Dark theme following financial/trading app conventions

## Decision 016: All-Gate Evaluation and Near-Miss Recording
**Date**: 2026-03-29
**Decision**: Modify `pre_trade_check` to evaluate all 6 risk gates instead of short-circuiting on first failure. Record near-misses (blocked by <= 2 gates) to `state/near_misses.json`.
**Reasoning**:
- Short-circuiting hid information: we only knew the first gate that blocked, not all of them
- Near-miss tracking reveals opportunities that were close to execution
- Understanding which gates block most often helps calibrate risk parameters
- Trade context snapshots (market regime, technicals, news) enable post-hoc analysis of why trades were/weren't made
**Trade-offs**:
- Slightly more computation per check (all gates run even when the first fails)
- Near-miss file grows over time (mitigated: only saves when <= 2 gates fail)
- Gates 4/5/6 have dependencies (position size needs cash reserve): handled by marking dependent gates as "not evaluated" when their prerequisite fails

## Decision 017: Operational Cost Tracking
**Date**: 2026-03-29
**Decision**: Log per-API-call token usage and estimated costs to `state/costs.json` for all AI model invocations.
**Reasoning**:
- AI model costs are a real operating expense that affects net profitability
- Token counts from Claude (`message.usage`) and Gemini (`usageMetadata`) are available in API responses
- Per-call granularity enables cost attribution to specific stocks and run types
- Estimated costs use published pricing tables (configurable in `cost_logger.py`)
**Trade-offs**:
- Cost estimates are approximate (don't account for caching, batching discounts)
- Costs file grows with every API call (acceptable: ~20 records/week)
- Pricing tables need manual updates when model pricing changes

## Decision 018: Statistics Dashboard with Net P&L
**Date**: 2026-03-29
**Decision**: Add a Statistics screen to the Flutter app showing realized P&L (closed trades), unrealized P&L (open positions), operational costs, and net P&L.
**Reasoning**:
- Trading P&L alone is misleading without accounting for operational costs (AI, data APIs)
- Round-trip matching (BUY->SELL pairs per ticker) gives accurate per-trade realized returns
- Combining realized + unrealized + costs gives the true picture of system profitability
- Per-service cost breakdown helps identify cost optimization opportunities
**Trade-offs**:
- Round-trip matching assumes one position per ticker at a time (valid given 10% position limit)
- Partial fills are matched FIFO, which may not reflect exact broker execution order
- Subscription costs (FMP, SEC-API) not yet tracked (only per-call AI costs for now)

## Decision 019: Bracket Order Resubmission
**Date**: 2026-03-29
**Decision**: Automatically resubmit expired bracket orders at the start of each execution cycle, after re-running all risk gates with current portfolio values.
**Reasoning**:
- Alpaca bracket orders use `time_in_force: "day"` (API constraint, not GTC)
- If the limit entry price isn't hit during the trading day, the bracket expires silently
- Without resubmission, a valid thesis could go unexecuted all week if the entry level is slightly below the daily trading range
- Resubmission runs the full risk gate pipeline again, so portfolio changes (drawdown, sector exposure, cash) are accounted for
**Trade-offs**:
- Resubmitted brackets also expire at end of day (by design — daily cron handles this)
- No max resubmission count per ticker (thesis expiry at 14 days provides the natural limit)
- Also available as standalone CLI command: `python -m titantrade resubmit`

## Decision 020: Test Suite with Zero AI Token Spend
**Date**: 2026-03-29
**Decision**: All tests mock AI model calls (Claude, Gemini) and broker API calls (Alpaca). Running the test suite never spends tokens or places real orders.
**Reasoning**:
- AI API calls cost money; tests run frequently during development
- Broker API calls could place real orders even on paper accounts, creating noise
- Pure logic tests (indicators, risk gates, parsing) have no external dependencies at all
- Integration tests monkeypatch `_call_claude`, `_call_gemini`, and all Alpaca functions
**Implementation**:
- `conftest.py` provides `fake_config` (dummy API keys), `tmp_state_dir` (temp state files)
- `unittest.mock.patch` used for AI and broker function mocking
- Test data uses deterministic fixtures (sample bars, bullish thesis, positions)
- 114 tests run in < 1 second

## Decision 021: Configurable Refresh Interval in Flutter App
**Date**: 2026-03-29
**Decision**: Allow users to change the polling interval (10s, 15s, 30s, 60s, 120s) from the Settings screen. All 7 stream providers observe the interval dynamically.
**Reasoning**:
- 30-second default is reasonable but some users may want faster updates during market hours or slower polling to reduce disk I/O
- Riverpod's `ref.watch` auto-disposes and recreates streams when the interval changes
- Persisted via SharedPreferences so the choice survives app restarts
**Trade-offs**:
- Very short intervals (10s) increase file system reads, though impact is negligible for JSON files

## Decision 022: Trailing Stop Mechanism
**Date**: 2026-03-30
**Decision**: Ratchet the stop-loss upward once a position gains 5%+ from entry. Trail 3% below the high-water mark.
**Reasoning**:
- Without trailing stops, a stock that runs up 12% can reverse and hit the original 5% stop, turning a winner into a loser
- The trailing stop activates after 5% gain (enough to avoid whipsaw on normal volatility)
- Trail distance of 3% is tight enough to lock in meaningful gains but wide enough to avoid premature exits
- Never trails below entry price once activated (locks in at least breakeven)
- Never trails below the original stop (doesn't widen risk)
**Trade-offs**:
- Requires cancelling and re-placing stop orders on Alpaca (brief moment with no stop during the swap)
- Only checks during execution cycles, not real-time — a flash crash between cycles could miss the trail
- High-water mark tracking adds a new state file (`trailing_stops.json`)

## Decision 023: Thesis Expiry Handling for Held Positions
**Date**: 2026-03-30
**Decision**: Force-close positions that have no active thesis monitoring them (expired or missing from current weekly analysis).
**Reasoning**:
- Previously, when a thesis expired, the system refused new entries but left existing positions as orphans
- Orphaned positions had only their original stop-loss — no sentry monitoring, no thesis-aware exit signals
- This could leave capital tied up indefinitely with no active management
**Trade-offs**:
- Forced exits may sell at a loss even if the stock would have recovered
- Acceptable: a position with no thesis is an unmanaged bet, and capital preservation > hope

## Decision 024: Dynamic Entry Price Adjustment on Resubmission
**Date**: 2026-03-30
**Decision**: When resubmitting expired bracket orders, adjust the entry price based on current market conditions instead of blindly reusing Sunday's level.
**Reasoning**:
- A static limit order that was 1% below the stock on Sunday may be 4% below by Wednesday, meaning the stock has moved away and the thesis entry point is stale
- Adjustment uses support levels from the thesis when available, otherwise a small discount below current price
- Preserves the original risk ratio (stop distance as a percentage)
- Won't chase: skips resubmission if price is >5% above original entry
- Won't enter invalidated thesis: skips if price is below original stop
**Trade-offs**:
- One extra FMP quote call per resubmission (negligible cost)
- May enter at a slightly worse price than Sunday's level — but at least it enters

## Decision 025: Lightweight Intraday Price Checks
**Date**: 2026-03-30
**Decision**: Add pure price-based checks between the 9 AM and 3:30 PM sentry runs. Zero LLM cost — only checks SPY and per-stock adverse moves.
**Reasoning**:
- The 6.5-hour gap between sentry runs left positions unmonitored during peak trading hours
- LLM-based checks every 2 hours would be wasteful — most of the sentry's value comes from the price-based Layer 2 override anyway
- The lightweight checks replicate only Layers 1 and 2 (SPY drop, adverse price move) without Layer 3 (news analysis)
- Run at 11 AM and 1 PM EST via cron — fills the gap without excessive API usage
**Trade-offs**:
- No news analysis during these checks — a breaking headline between 9 AM and 3:30 PM is not caught until the next sentry run
- Acceptable: broker-native stops cover the catastrophic case, and the price-based check catches most institutional selling

## Decision 026: Gap-Down Protection Fallback
**Date**: 2026-03-30
**Decision**: Detect unfilled stop-limit orders after overnight gaps and market-sell the unprotected position immediately.
**Reasoning**:
- Stop-limit orders can fail to fill when a stock gaps below both the stop price and limit price overnight
- This leaves the position completely unprotected — the stop triggered but the limit didn't fill
- Also catches the case where price gaps below the stop itself (stop never triggers, position sits open)
- Runs as part of the daily execution cycle and as a standalone `gapcheck` CLI command
**Trade-offs**:
- Market sell after a gap-down means selling at a potentially much worse price than the intended stop
- But the alternative is holding an unprotected position that could fall further

## Decision 027: Dual Alpaca Credentials with App-Toggled Trading Mode
**Date**: 2026-03-30
**Decision**: Store separate paper and live Alpaca credentials in `.env`. Trading mode is toggled via the Flutter app (or API), not via environment variables.
**Reasoning**:
- Users need both paper and live accounts configured simultaneously for easy switching
- Previously, switching required editing `.env` and restarting — error-prone and slow
- The API endpoint (`PUT /api/settings/mode`) persists the mode to `watchlist.json`
- `load_config()` selects the correct key pair and Alpaca endpoint based on mode
- Live keys are optional — system works paper-only if they're not set
- Legacy `ALPACA_KEY`/`ALPACA_SECRET` env vars are accepted as paper-key fallback
**Safety**:
- API refuses to enable live mode if `ALPACA_LIVE_KEY`/`ALPACA_LIVE_SECRET` are missing
- Flutter app shows a red confirmation dialog before enabling live trading
- Default state is always paper (toggle off)
**Trade-offs**:
- Four env vars instead of two for Alpaca (small complexity increase)
- Mode change requires the next CLI command to re-read config (not hot-reloaded mid-run)
- Acceptable: CLI commands are short-lived processes that load config fresh each time

## Decision 028: Built-in Scheduler (APScheduler in API Process)
**Date**: 2026-03-30
**Decision**: Run all trading cron jobs inside the always-on API container using APScheduler, instead of requiring host-level cron.
**Reasoning**:
- Host cron required manual setup on each server, error-prone, hard to monitor
- APScheduler 3.x `BackgroundScheduler` runs in the same process as FastAPI
- Jobs defined in `data/schedule.json` — editable, version-controlled
- API endpoints (`GET /api/scheduler`, `POST /api/scheduler/{id}/trigger`) let the Flutter app monitor and trigger jobs
- `coalesce=True` + `max_instances=1` + `misfire_grace_time=300` handle restarts gracefully
**Schedule**:
- Sunday 20:00 UTC: full pipeline (fetch → analyze → sentry → execute)
- Weekdays 13:35 UTC: gap-down check
- Weekdays 14:15 UTC: morning sentry + execute
- Weekdays 16:00, 18:00 UTC: price checks
- Weekdays 20:30 UTC: pre-close sentry + execute
**Trade-offs**:
- Scheduler state is in-memory (job history lost on restart) — acceptable for v1
- APScheduler 3.x is thread-based, not async — fine since trading jobs are I/O-bound and short-lived
- No market holiday awareness yet — jobs run but complete quickly with no side effects on closed days

## Decision 020: Discord Webhook Notifications
**Date**: 2026-03-30
**Decision**: Add Discord webhook notifications for job completion/failure and daily portfolio summaries.
**Reasoning**:
- Without notifications, job failures go unnoticed until the user manually checks the Flutter app
- Discord webhooks are free, simple (single HTTP POST), and push to the user's phone
- Two notification types: per-job alerts (green/red embeds) and a daily portfolio digest
**Implementation**:
- New `notifier.py` module using `httpx` (already a dependency) to POST Discord embeds
- Hooked into `scheduler.py:_execute_job()` so every job gets automatic notifications
- `daily_summary` registered as a new scheduled command (weekdays 21:00 UTC)
- `DISCORD_WEBHOOK_URL` env var is optional — if unset, all notifications are no-ops
- Notification failures are logged but never crash the underlying job
**Trade-offs**:
- Discord-specific (not a generic notification system) — simple and sufficient for v1
- Daily summary reads state files which may be stale if the last sentry failed
- No rate limiting on webhook calls — acceptable since jobs run at most ~8 times/day

## Decision 021: Fractional Shares for Small Accounts
**Date**: 2026-03-30
**Decision**: Support fractional share trading for accounts too small for whole shares.
**Reasoning**:
- Starting with ~$500, the 10% position sizing produces ~$50 per trade
- Most stocks above $50/share would get 0 shares after `int()` truncation, making them untradeable
- Alpaca supports fractional shares natively via the same API (`qty: "0.25"`)
**Implementation**:
- Position sizing uses `float` instead of `int` — snaps to whole shares when >= 1, keeps fractional when < 1
- Order routing: whole shares use bracket orders (atomic entry + stop + TP), fractional uses day-limit buys
- All position quantity reading changed from `int(float(...))` to `float(...)` for fractional holdings
- Minimum $1.00 notional check added (Alpaca requirement for fractional orders)
**Trade-offs**:
- Fractional positions have no broker-native stop-loss (Alpaca doesn't support fractional bracket/stop orders)
- The sentry's price-based ABORT (3% adverse) and intraday price checks act as the safety net instead
- Max loss on a fractional position is small ($50 at 10% sizing on a $500 account), so the risk is acceptable
- As the account grows and positions become whole shares, bracket orders automatically resume
