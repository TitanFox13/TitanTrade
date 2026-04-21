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

## Decision 042: Poll qty_available Instead of Fixed-Sleep Retry
**Date**: 2026-04-21
**Decision**: Replace the 2-second blind sleep in `place_native_stop_loss`'s qty-race retry with an explicit poll of Alpaca's `qty_available`, waiting up to 30 seconds for the cancel to settle.
**Problem** (observed in production over 3 days of the previous fix):
- First executor run after a fresh weekly thesis fires ADJUST on 5-6 positions simultaneously.
- Several hit the qty-race retry path. The 2-second sleep was sometimes too short — Alpaca's `pending_cancel` state lasted 5-15 seconds in production despite completing in ~600 ms in isolated tests.
- Result: GS, URI, DECK, LLY, and DASH were all left **without a stop-loss** until the next executor run (~6 hours later). Logs showed `CRITICAL: {ticker} has no stop-loss order — old-stop restore also failed` for each.
- The self-heal on Run 2 was good (stops were placed), but a 6-hour unprotected window is an unacceptable risk if one of those stocks crashes overnight.
**Fix** (`executor.py`):
- New `_wait_for_qty_available(ticker, required_qty, cfg, timeout_seconds=30)` helper that polls `get_position()` every 500 ms until `qty_available >= required_qty`, or the timeout elapses.
- `place_native_stop_loss` qty-race handler now calls this poll before retrying. It gives up only after 30 s of no release — log line: `Qty for {ticker} never released within 30s — giving up on stop placement`.
- On success: `Qty for {ticker} released after {X}s — retrying stop-limit` followed by `Stop-limit for {ticker} succeeded after qty settled ({X}s)`.
- Two constants added: `QTY_SETTLE_TIMEOUT_SECONDS = 30.0`, `QTY_SETTLE_POLL_INTERVAL = 0.5`.
**Verification**:
- Unit tests updated (`TestPlaceNativeStopLoss.test_retries_on_qty_race_after_polling`, `test_qty_race_times_out_if_never_released`).
- Live test on the Alpaca paper account: `cancel_order()` followed immediately by `place_native_stop_loss()` succeeded in ~1.5 s when no race hit, and within the timeout window when a race did hit.
**Trade-offs**:
- Worst case (qty genuinely stuck, e.g. settlement problem at broker) is a 30 s wait per stop placement — up from 2 s previously. Acceptable: the previous behaviour silently gave up and left the position unprotected; we'd rather block for 30 s and log loudly if we ultimately fail.
- On happy-path (no race), there is zero additional latency — we only enter the poll on a 40310000 error.

## Decision 039: Gemini Structured Output + Thinking Disabled
**Date**: 2026-04-18
**Decision**: Switch `_call_gemini` to use Gemini's structured-output mode with a `responseSchema`, and explicitly disable the thinking-token budget on gemini-2.5-flash.
**Reasoning**:
- Gemini 2.5 Flash defaults to `thinking` mode, which consumes 500-2000 hidden tokens before producing any output. On a classification task (CONTINUE vs ABORT), this is pure cost and latency with no benefit.
- Without structured output, Gemini occasionally emits markdown-fenced JSON, prose prefixes ("Here is the result: ..."), or truncates mid-string when the token budget runs out. We had to ship a JSON-repair module to cope.
- With `responseMimeType=application/json` + `responseSchema`, Gemini enforces a valid JSON shape matching our `SENTRY_SCHEMA`. The repair path becomes a belt-and-suspenders fallback rather than a daily necessity.
**Implementation** (`src/titantrade/daily_sentry.py`):
- Added `_SENTRY_SCHEMA` constant matching the sentry signal shape (ticker, signal, conflicting_headlines, price_concern, market_concern, reasoning — all required, with signal enum-constrained to CONTINUE/ABORT).
- `generationConfig` now includes `responseMimeType: "application/json"`, `responseSchema: _SENTRY_SCHEMA`, and `thinkingConfig: {thinkingBudget: 0}`.
- Simplified the prompt's OUTPUT FORMAT section — the schema does the enforcement, so we can drop the brevity instructions that were previously fighting truncation.
**Verification**: live Gemini call on NVDA returned perfectly-valid JSON in 78 candidate tokens (vs hundreds with thinking enabled) in 1.77 s.
**Trade-offs**:
- Schema is strictly typed: `conflicting_headlines` is `array<string>`. If we ever want headline objects (title+snippet), the schema needs to change. For the current use case, strings are sufficient.
- The JSON-repair code path (`_repair_truncated_json` in `ai_parsing.py`) stays as a defensive fallback for the rare case where the schema-constrained response is somehow still malformed.

## Decision 040: Backtest A/B Comparison — Confidence Scaling On vs Off
**Date**: 2026-04-18
**Decision**: Expose the confidence-scaling logic as an opt-in flag in the backtest engine and add an A/B runner for empirical validation.
**Reasoning**: The confidence-proportional position-sizing change (ADR 032) was deployed to the live executor but never backtested. Without a way to compare the two regimes on historical data, we can't tell whether the 0.7×–1.3× curve actually improves risk-adjusted returns or just adds complexity.
**Implementation**:
- `src/titantrade/backtest/simulator.py`: `PortfolioSimulator` now accepts `use_confidence_scaling: bool = False`. When True, `_process_entries` calls `risk_manager.confidence_scaled_risk(self.risk_per_trade, thesis.confidence)` instead of using the flat risk fraction.
- `src/titantrade/backtest/engine.py`: `run_backtest()` accepts a matching flag, and a new `run_ab_comparison()` runs both variants back-to-back and returns a side-by-side metric table (return, alpha, Sharpe, Sortino, drawdown, win rate, profit factor, trade count).
- `src/titantrade/__main__.py`: new CLI command `backtest-ab [dir]` produces a formatted console table and writes the full result JSON to `state/backtest_ab.json`.
- Tests added to `tests/test_backtest.py` verify the flag toggles the config field and that the comparison structure is well-formed.

## Decision 041: Flutter Sentry Health Badge
**Date**: 2026-04-18
**Decision**: Surface the sentry's `failures.fallback_ratio` on the dashboard so the Gemini-degraded state is visible without digging through logs or waiting for Discord alerts.
**Implementation**:
- `titan_trade_app/lib/models/sentry_signal.dart`: new `SentryFailures` class with `fallbackCount`, `checksRun`, `fallbackRatio`, and a convenience `isDegraded` getter (mirrors server-side 30% threshold).
- `SentryBundle.fromJson` now parses an optional `failures` block.
- `titan_trade_app/lib/screens/dashboard_screen.dart`: when `failures.isDegraded`, the sentry card shows an orange warning banner with fallback counts. When healthy, a small green pill shows coverage ("Sentry healthy — 14/15 news-based checks OK").

## Decision 038: Sentry Coverage — Skip Non-Selected Tickers + Failure Observability + ADJUST Safety Net
**Date**: 2026-04-18
**Decision**: A bundle of three small correctness and observability fixes.
**Problem 1 — Ghost ABORTs for closed positions**: After a weekly review marked DXCM as CLOSE (`selected_for_trading=False`) and the orphan-close sold the position, the daily sentry kept calling Gemini for DXCM on every run because the sentry loop only filtered out NEUTRAL theses. Occasional ABORTs would fire, then the executor would log `ABORT for DXCM: no position to close` as harmless noise — but the Gemini tokens and the log spam were both wasted.
**Problem 2 — No observability when Gemini is down**: When Gemini returns 503 for all sentry calls (common during API-side outages), our code silently falls back to CONTINUE for every ticker. The news-based ABORT layer is effectively offline, but there's no alert. The operator has to spot it in log files.
**Problem 3 — ADJUST could strand a position without a stop**: The ADJUST flow `cancel_all_orders_for_ticker` → `place_native_stop_loss` has a failure window where the cancel succeeds but the new stop placement fails (e.g. network blip after the qty-race retry exhausts). The position is then held with NO stop-loss.
**Fix 1 (`daily_sentry.py`)**: skip the ticker entirely if `selected_for_trading=False`. Append a synthetic CONTINUE signal with `reasoning="Not selected for trading — sentry check skipped"` so state files remain consistent. No Gemini call, no ghost ABORT.
**Fix 2 (`daily_sentry.py` + `notifier.py`)**: at the end of each sentry run, count signals whose `reasoning` contains `"Sentry check failed"` (the exception-path fallback marker). Record `{fallback_count, checks_run, fallback_ratio}` in the state file and, when the ratio exceeds 30%, log a WARNING and fire a Discord alert via new `notify_sentry_degraded()` helper.
**Fix 3 (`executor.py` ADJUST flow)**: before cancelling the old stop, capture its `stop_price`. If the new-stop placement raises, re-create the old stop at its original price. Mirrors the pattern already in use by `manage_trailing_stop`.
**Fix 4 (`executor.py` orphan close)**: on failure, log the Alpaca error code + message (via the new `HTTPError` properties) and explicitly say "will retry on next run" so operators don't assume the position is stuck permanently.
**Tests**: 3 new sentry tests (`TestNonSelectedSkip`, `TestSentryObservability`), 2 new executor tests (`TestAdjustStopSafety`), all with mocked Gemini/Alpaca.
**Trade-offs**:
- The 30% fallback-alert threshold is a judgement call. Too low produces noisy alerts during brief Gemini hiccups; too high hides real outages. 30% balances these — the threshold is a constant and can be tuned later.
- The ADJUST restore doesn't cover the case where the original stop price is itself invalid. If we somehow had no prior stop, restore is a no-op (logged as CRITICAL).

## Decision 037: Alpaca 403 on Stop Placement — Idempotency + Qty-Race Retry + Error-Body Capture
**Date**: 2026-04-18
**Decision**: Three-layer fix for the recurring `403 Forbidden` Alpaca errors seen when placing/replacing stop-loss orders.
**Problem** (diagnosed by reproducing the error with the live Alpaca paper API):
1. The `ADJUST` review flow in `executor.py` was unconditionally cancelling and re-placing stops on every executor run (twice daily), even when the existing stop was already at the target price. Alpaca's historic order log showed 28 back-to-back "cancel→re-place at the same $64.50" cycles on FCX alone over 14 days — every one of which was a wasted request and a chance to hit a qty race.
2. Between cancel and re-place, Alpaca's `qty_available` can lag ~100-1000 ms. When we POST the new stop in that window, Alpaca returns 403 with `code:40310000` and the message `"insufficient qty available for order (requested: 121, available: 0)"`.
3. `retry.py` discarded the response body via `raise_for_status()`, so our logs just said `403 Forbidden` with no diagnostic detail.
4. The stop-limit → plain-stop fallback in `place_native_stop_loss` sent the same qty for both order types. Since the qty constraint is position-level (not order-type-level), the fallback was guaranteed to fail whenever the stop-limit failed with 40310000.
**Fix — Layer 1 (`executor.py:1269`)**: idempotency check before cancel+replace. If an existing stop for the ticker is already at (within $0.01 of) the target `stop_loss_price`, skip the entire cancel+replace sequence.
**Fix — Layer 2 (`retry.py`)**: new `HTTPError` exception class that carries the status code, raw body, parsed JSON, and convenience properties `error_code` / `error_message`. The 4xx branch now raises this instead of `httpx.HTTPStatusError`, preserving diagnostic info like Alpaca's error code.
**Fix — Layer 3 (`executor.py: place_native_stop_loss`)**: when `HTTPError.error_code == 40310000` (Alpaca insufficient qty), wait 2 s and retry the stop-limit *once*. Do not fall back to a plain stop in this case — both order types share the same qty constraint. For any other 4xx, the plain-stop fallback is retained (paper accounts occasionally reject stop-limit for specific asset types).
**Tests**: 4 new executor tests (`TestPlaceNativeStopLoss`) + 3 new retry tests (`TestHTTPErrorBodyCapture`) covering qty-race retry, body capture, and the unchanged plain-stop fallback for other errors.
**Verification**: reproduced the 403 with live API call to `POST /v2/orders` on FCX with 121 shares already held by an existing stop, confirmed Alpaca's response body matches the error-code handling, and confirmed `DELETE /v2/orders/{id}` typically releases `qty_available` within ~600 ms.
**Trade-offs**:
- Layer 1 reduces Alpaca request volume by ~28× per held position per 2-week window.
- Layer 3 adds up to one 2-second delay per stop placement in the race case. Acceptable — better than a failed placement leaving the position unprotected.
- `HTTPError` is a new exception type. Existing callers that catch `Exception` still work (it's still an `Exception`), but any code that specifically caught `httpx.HTTPStatusError` would break. None existed in the codebase.

## Decision 036: Review-Mode Thesis Validation
**Date**: 2026-04-18
**Decision**: `validate_thesis()` now distinguishes "new candidate" from "review of held position" via an `is_review` flag.
**Problem**: The validator blindly downgraded any BULLISH thesis without a `target_entry_price` to NEUTRAL. When Claude *reviewed* a held position, it correctly omitted the entry price (we already own the shares — there's no pending buy to price), but the validator interpreted that as "no way to buy" and downgraded the thesis to NEUTRAL. This produced the recurring log line `BULLISH thesis for JPM/LLY/FCX/EQIX has no entry price - downgrading to NEUTRAL` on every weekly analysis, and caused held positions to lose their BULLISH status in state, confusing downstream selection logic.
**Fix** (`src/titantrade/ai_parsing.py:208`):
- Added optional `is_review: bool = False` parameter to `validate_thesis()`
- When `is_review=True`: skip the "no entry price → NEUTRAL" downgrade, and skip the auto-fill of stop-loss from entry price (the caller carries the prior stop forward)
- When `is_review=False` (default): legacy behaviour preserved for new candidates
- Updated both `validate_thesis()` call sites inside `review_position()` in `weekly_analyst.py` to pass `is_review=True`
- Pass-1 new-candidate path in `analyze_stock()` unchanged (still needs entry price to know where to buy)
- Added 5 regression tests (`TestValidateThesisReviewMode`) locking in the new behaviour
**Trade-offs**:
- New flag is opt-in with a safe default. All existing callers that don't pass it continue to get the old behaviour, so this change is fully backward compatible.

## Decision 034: Hardened HTTP Retry Policy
**Date**: 2026-04-18
**Decision**: Rewrite `retry.py` with longer backoff, jitter, 429 handling, and per-call timeout tuning.
**Reasoning**:
- Gemini Flash frequently returns 503 (overloaded). Previous retry gave up after ~6 s of total wait — far too short for Google's load-shedding windows.
- All 15 sentry tickers retrying in lockstep created a thundering-herd effect that amplified Gemini outages.
- 429 rate-limit responses were treated as immediate failures instead of retry-with-backoff, so SEC-API rate limits (now obsolete) and any future rate-limited endpoint would fail fast.
- Over a 14-day operation window, **up to 11 of 15 sentry checks silently failed** in a single run, degrading the news-analysis safety layer without operator awareness.
**Implementation** (`src/titantrade/retry.py`):
- `MAX_RETRIES` raised 3 → 5
- Per-attempt delay capped at `MAX_DELAY = 30 s` (was unbounded 2^attempt)
- Full-jitter exponential backoff: `delay = uniform(0, min(BASE_DELAY * 2^(attempt-1), MAX_DELAY))`
- `DEFAULT_TIMEOUT` raised 30 s → 60 s (Gemini 2.5-flash can take 30–45 s under load)
- 429 responses retried and honour the `Retry-After` header
- `RETRYABLE_STATUS = {429, 500, 502, 503, 504, 529}` (529 for Anthropic overload)
- `max_retries` now a per-call parameter, so latency-sensitive Alpaca paths can fail faster if needed
- New unit tests in `tests/test_retry.py` (17 tests) covering jitter bounds, Retry-After parsing, 4xx fail-fast, 5xx retry-then-succeed, and network-error retry
**Trade-offs**:
- Worst-case retry time rises from ~6 s to ~75 s. Acceptable for AI/data endpoints but could delay Alpaca order placement if the broker itself returns 5xx. Callers that need fail-fast should pass `max_retries=1`.
- More API usage during backoff windows (5 attempts vs 3).

## Decision 035: Replace Paid SEC-API.io with Free SEC EDGAR
**Date**: 2026-04-18
**Decision**: Switch SEC filings and Form 4 insider data from api.sec-api.io to the free SEC EDGAR public API.
**Reasoning**:
- SEC-API.io credits were exhausted and the service is expensive.
- Independent evaluation (see ADR context) rated SEC filings as ~20/100 criticality — 1 of ~11 data inputs to Claude's weekly analysis.
- SEC EDGAR provides the same underlying data (8-K, 10-Q, 10-K, Form 4 metadata) for free, with a 10 req/sec global rate limit that our sequential workflow stays well under.
**Implementation** (`src/titantrade/sec_edgar.py`):
- New module with `get_cik()`, `fetch_recent_filings()`, `fetch_insider_filings()`
- Uses `https://www.sec.gov/files/company_tickers.json` for ticker→CIK lookup (full ~10k-entry map cached at `state/cik_cache.json`, fetched at most once per process)
- Uses `https://data.sec.gov/submissions/CIK{cik}.json` for each company's filings
- SEC requires a `User-Agent` with a contact email — configurable via `SEC_USER_AGENT` env var, defaults to `TitanTrade/1.0 (contact@titantrade.local)`
- `data_fetcher.fetch_sec_filings()` and `fetch_insider_trades()` keep their signatures; the `cfg` argument is now a no-op placeholder for backward compatibility
- `SECAPIConfig` marked deprecated in `config.py` (retained only for test fixtures)
- New unit tests in `tests/test_sec_edgar.py` (19 tests) covering CIK caching, URL construction, form-type filtering, limit enforcement, unknown-ticker handling, and error paths
**Trade-offs**:
- Form 4 reporting-owner (insider) names are no longer returned — they require parsing each Form 4 XML filing (one extra request each). For weekly analysis, the *timing and count* of insider activity is the primary signal, so we leave `insider_name` blank.
- Filing descriptions are simpler (EDGAR returns `primaryDocDescription` like "8-K" or "FORM 4" rather than detailed summaries). Claude can still see form type, filing date, and a direct URL.

## Decision 032: Confidence-Proportional Position Sizing
**Date**: 2026-04-05
**Decision**: Scale position size proportionally to confidence using a linear multiplier (0.7x at 0.70 confidence to 1.3x at 1.00 confidence).
**Reasoning**:
- Previously confidence was binary: blocked trades below 0.70, did nothing above
- A 0.71 and 0.95 confidence trade both got identical 10% position sizing
- Information from the AI's conviction assessment was wasted
- Higher confidence = more capital deployed; lower confidence = smaller bet
- Baseline (10% risk) is at 0.85 confidence; 0.70 gets 7%, 1.00 gets 13%
**Implementation**:
- `confidence_scaled_risk()` in `risk_manager.py`: linear interpolation
- Formula: `multiplier = 0.7 + (confidence - 0.70) * 2.0`
- Applied inside `volatility_adjusted_shares()` when confidence is provided
- Backward compatible: `confidence=None` gives identical pre-existing behavior
**Trade-offs**:
- Higher exposure on high-confidence trades increases tail risk if confidence calibration is poor
- Mitigated by existing performance feedback loop that calibrates confidence over time
- ATR cap still limits any single position to ~13% max (even at confidence=1.0)

## Decision 033: Hedge Instrument Regime Awareness in Weekly Review
**Date**: 2026-04-05
**Decision**: Add market regime context and explicit warnings to the weekly review prompt for inverse ETF positions.
**Reasoning**:
- SDS (2x inverse S&P 500) was held through a +3.4% market rally, losing 7.81%
- The review prompt never told Claude about the current market regime
- Claude only saw individual position P&L and technicals, not the strategic contradiction
- Without regime context, Claude defaulted to CONTINUE since the thesis was technically intact
**Implementation**:
- `REVIEW_USER_TEMPLATE` now includes `{current_regime}` and `{regime_warning}`
- For hedge instruments in non-bearish regimes, a warning is injected:
  "WARNING: {ticker} is an INVERSE ETF... current regime is '{regime}'... Consider CLOSING."
- New instruction: "REGIME CHECK: If a regime warning is present, weigh it heavily"
**Trade-offs**:
- May cause premature exits during temporary rallies within a broader bearish trend
- Acceptable because inverse ETFs are intended as short-term hedges, not long-term holds

## Decision 029: Gemini Truncated JSON Repair
**Date**: 2026-04-04
**Decision**: Add a JSON repair layer in `ai_parsing.py` to salvage truncated Gemini responses.
**Reasoning**:
- Gemini Flash frequently hits `maxOutputTokens` and cuts off mid-JSON string (especially in the `reasoning` field)
- This was causing ~8 parse failures per week, losing sentry signal quality
- The repair closes unterminated strings and brackets to recover the parseable fields
- Also added prompt instruction to keep reasoning under 3 sentences to reduce truncation frequency
**Trade-offs**:
- Repaired JSON may have a truncated `reasoning` field — acceptable since the `signal` field is the actionable output

## Decision 030: Live Portfolio API Endpoint
**Date**: 2026-04-04
**Decision**: The `/api/portfolio` endpoint now fetches live data from Alpaca instead of reading a static JSON file.
**Reasoning**:
- The static `portfolio.json` was never updated, causing persistent 404 errors
- The Flutter app needs real-time portfolio data (positions, P&L, buying power)
- Falls back to static file if Alpaca API is unreachable

## Decision 031: Sector Cache Initialization in Executor
**Date**: 2026-04-04
**Decision**: Call `load_stock_sectors()` at the start of `execute_trades()` to populate the in-memory sector cache.
**Reasoning**:
- The sector cache was only populated during `build_data_bundle()` (the fetch command)
- The executor runs as a separate process/invocation and had an empty cache
- All tickers mapped to "Unknown" sector, causing the 40% sector limit gate to block all entries in that phantom sector
- Now the executor loads the persistent `sector_cache.json` (or fetches from FMP if missing) before risk gate checks

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
