# TitanTrade TODO

## Phase 1.20: Executor decomposition (2026-06-07) — behavior-preserving, in progress
Branch `refactor/backend-modularization`; see Decision 036. Each step keeps 424 tests green + is committed.
- [x] Remove dead code (`calculate_shares`, `_adjust_entry_price` + its test file, `_highs`/`_lows`, `fetch_earnings_date`, dead constants, unused locals, 24 unused imports); add `ruff`+`vulture` dev extra
- [x] Extract `broker.py` (Alpaca REST client)
- [x] Extract `pricing.py` (trend regime + entry selection)
- [x] Extract `cooldown.py` + `trailing_state.py`
- [x] executor.py 3,267 → 2,496 LOC
- [ ] Extract `trade_state.py`, `alerts.py` (leaf state helpers)
- [ ] Extract `entries.py`, `positions.py`, `protection.py`, `core_allocation.py` (Tier-2: retarget moved-caller test patches)
- [ ] De-duplicate shared entry-adaptation / bracket-validation logic
- [ ] Decompose `execute_trades` (592) + `_handle_bullish_entry` (319)
- [ ] Redeploy + re-verify on server

## Phase 1.19: Execution-safety hardening (2026-06-07) — go-live blockers
From a 14-day paper-log review (see Decision 035). All six found bugs fixed:
- [x] TP1 race fixed: poll the partial sell to `filled` before sizing the breakeven stop; restore handler sizes off the live position, not the stale pre-sell qty
- [x] `place_native_stop_loss` clamps to broker-reported `available` qty as a last resort — a position is never left bare (the FCX `CRITICAL stop restore failed` case)
- [x] Pyramid adds via marketable LIMIT buy (was a market buy → 100% wash-trade reject); stop extended to cover the enlarged position after fill
- [x] Gap-down protection waits for the cancel to release held qty before the market sell (was 403-ing on `available: 0`)
- [x] Fractional bracket guard: `place_bracket_order` floors/raises; resubmit skips when sized < 1 whole share (the URI 0.19-share → 422 bug)
- [x] Committed-cash reserve: cash-reserve gate nets out pending buy-order notional so simultaneous brackets can't fill into margin/negative cash
- [x] Daily `weekday_fetch` job (13:00 UTC) so the data bundle is refreshed daily, not just weekly (was aging to 120h)
- [x] Analyst↔executor downtrend conflict (HCA) recorded as a near-miss instead of a silent per-cycle skip
- [x] 12 new tests (437 total passing); de-flaked the brittle qty-race-timeout test
- [ ] Follow-up: make Pass-2 selection trend-aware so it stops ranking downtrend names into the buy set (deferred — changes non-deterministic AI output)

## Phase 1: Core Infrastructure
- [x] Project structure and configuration
- [x] Config management (env vars, watchlist)
- [x] Logging system (structured JSON)
- [x] Retry/backoff utility (3 retries, exponential)
- [x] Data fetcher (FMP prices/news + SEC filings)
- [x] Weekly analyst (Claude integration)
- [x] Daily sentry (Gemini Flash integration)
- [x] Trade executor (Alpaca integration)
- [x] GitHub Actions workflows
- [x] State management (portfolio, thesis, trade log)

## Phase 1.5: Advanced Features
- [x] Technical indicators (RSI, MACD, Bollinger, ATR, SMA, volume)
- [x] Market context (SPY, QQQ, VIX, Treasury yields, sector rotation)
- [x] Two-pass weekly analysis (per-stock + portfolio ranking)
- [x] Three-layer daily sentry (market-wide + price-based + news-based)
- [x] Earnings calendar gate (5-day blackout)
- [x] Volatility-adjusted position sizing (ATR-based)
- [x] Drawdown circuit breaker (8% from peak)
- [x] Cash reserve enforcement (20% minimum)
- [x] Sector exposure limits (40% max)
- [x] Confidence threshold gate (>= 0.70)
- [x] Performance feedback loop (win rate, calibration, per-ticker stats)
- [x] Broker-native stop-losses (bracket orders)
- [x] Comprehensive documentation

## Phase 1.6: Infrastructure
- [x] Docker containerization (Dockerfile + docker-compose.yml + .dockerignore)
- [x] Server-based cron deployment documentation
- [x] Flutter desktop app project setup and foundation

## Phase 1.7: Trade Intelligence
- [x] All-gate evaluation in risk manager (no short-circuit, reports all failures)
- [x] Trade context snapshots (market regime, VIX, technicals, news at trade time)
- [x] Near-miss recording (blocked by <= 2 gates, saved to state/near_misses.json)
- [x] Watchlist write function (save_watchlist in config.py)
- [x] Enriched trade detail screen (context, gate results, risk flags)
- [x] Near misses screen + detail screen in Flutter app
- [x] Watchlist management screen in Flutter app (add/remove tickers)

## Phase 1.8: Statistics & Cost Tracking
- [x] Operational cost logger (state/costs.json with per-API-call token usage)
- [x] Claude token usage capture in weekly_analyst.py
- [x] Gemini token usage capture in daily_sentry.py
- [x] Cost model and provider in Flutter app
- [x] Statistics screen: open positions P&L (unrealized)
- [x] Statistics screen: closed trades P&L with BUY->SELL round-trip matching
- [x] Statistics screen: operational costs breakdown by service
- [x] Statistics screen: net P&L (trading P&L minus operational costs)

## Phase 1.9: Reliability & Testing
- [x] Pytest infrastructure (pyproject.toml, conftest.py, fixtures)
- [x] Unit tests for indicators: SMA, EMA, RSI, MACD, Bollinger, ATR, volume, price_vs_sma (31 tests)
- [x] Unit tests for AI output parsing: extract_json, parse_ai_json, validate_thesis/sentry/ranking (29 tests)
- [x] Unit tests for risk manager: all 6 gates individually + pre_trade_check integration (32 tests)
- [x] Mocked weekly analyst tests: analyze_stock, rank_and_select with canned Claude responses (5 tests)
- [x] Mocked daily sentry tests: check_stock with canned Gemini responses, price override (5 tests)
- [x] Executor tests: build_trade_context, handle_bullish_entry, near-miss recording (12 tests)
- [x] Bracket order resubmission (expired brackets auto-resubmitted with fresh risk checks)
- [x] Bracket resubmission tests (valid/invalid/already holding scenarios)
- [x] Settings screen in Flutter app (change data path, configurable refresh interval)
- [x] Dynamic refresh interval across all 7 providers (10s/15s/30s/60s/120s)
- [x] Dual Alpaca credentials (separate paper and live key pairs in .env)
- [x] Trading mode API endpoints (`GET /api/settings`, `PUT /api/settings/mode`)
- [x] Trading mode toggle in Flutter settings (SwitchListTile with confirmation dialog)
- [x] Backward compatibility for legacy `ALPACA_KEY`/`ALPACA_SECRET` env vars
- [x] Built-in APScheduler (all cron jobs run inside API container)
- [x] Schedule config in `data/schedule.json` (editable, version-controlled)
- [x] Scheduler API endpoints (list, trigger, enable/disable)
- [x] Scheduler screen in Flutter app (status, toggle, manual trigger)

## Phase 1.10: Position Protection & Monitoring
- [x] Trailing stop mechanism (5% trigger, 3% trail below HWM)
- [x] Thesis expiry: force-close orphaned positions with no active monitoring
- [x] Dynamic entry price adjustment on bracket resubmission (current price awareness)
- [x] Lightweight intraday price checks between sentry runs (zero LLM cost)
- [x] Gap-down protection: detect unfilled stop-limits and market-sell immediately
- [x] New CLI commands: `pricecheck`, `gapcheck`
- [x] FastAPI HTTP server for Flutter app to connect remotely
- [x] Cloudflare tunnel integration (docker-compose with cloudflared service)

## Phase 1.11: Strategy Improvements
- [x] Economic calendar awareness (FMP /economic_calendar + Gate 7 macro blackout)
- [x] Analyst ratings and price target consensus (FMP upgrades/downgrades)
- [x] Relative strength vs SPY (5d/20d/60d outperformance metric)
- [x] Insider trading data (Form 4 filings via SEC-API)
- [x] Pairwise correlation matrix (60-day rolling) + Gate 8 correlation limit
- [x] Sentiment divergence detection (prompt enrichment)
- [x] Mean reversion setup detection (RSI < 30 + 200-SMA proximity)
- [x] Earnings run-up strategy (10-15 days before earnings)
- [x] Two-tranche entry (60% at target + 40% at 1.5% discount)
- [x] Time-of-day entry optimization (shifted to 10:15 AM ET, after opening volatility)

## Phase 1.12: Flexible Holding & Backtesting
- [x] Diversified watchlist: 15 stocks across 8 sectors (tech, healthcare, finance, energy, industrial, consumer, materials, real estate)
- [x] Flexible hold horizons: short_term (1-2w), medium_term (2-6w), long_term (6w+)
- [x] Weekly review pipeline: held positions get CONTINUE/ADJUST/CLOSE review, not forced expiry
- [x] Removed 14-day hard thesis expiry — replaced with weekly review cycle
- [x] CLOSE review action triggers position exit (Claude's explicit decision)
- [x] ADJUST review action updates stop/TP levels
- [x] Backtesting engine: synthetic thesis, portfolio simulator, metrics computation
- [x] Backtest CLI: `python -m titantrade backtest [data-dir]`
- [x] Historical data downloader: `python -m titantrade download-history [data-dir]`
- [x] Backtest metrics: return, alpha vs SPY, win rate, Sharpe, Sortino, max drawdown, profit factor

## Phase 1.13: Bear Market Hedging & Execution Quality
- [x] Inverse ETF hedging: SH/PSQ/SDS analyzed in bearish/crisis regimes
- [x] Slippage model in backtester (0.15% per fill, configurable)
- [x] Slippage-aware limit exits for non-urgent ABORT signals
- [x] Limit sell function for executor (reduces market order slippage)

## Phase 1.16: Reliability & Cost Reduction (2026-04-18)
- [x] Hardened retry policy: 5 attempts, 30s cap per delay, 60s timeout, full jitter
- [x] 429 rate-limit handling with `Retry-After` header support
- [x] `max_retries` now a per-call parameter (fail-fast path available)
- [x] Replaced paid SEC-API.io with free SEC EDGAR (`sec_edgar.py`)
- [x] CIK cache at `state/cik_cache.json` (one-time ~10k entry fetch)
- [x] Removed all SEC-API references (`SECAPIConfig` class, `SEC_API_KEY` env, workflow secrets, docs)
- [x] Unit tests for retry (17 tests) and EDGAR client (19 tests)
- [x] Fixed review-mode thesis validation: held positions no longer get silently
      downgraded from BULLISH to NEUTRAL for missing `target_entry_price`
- [x] Fixed Alpaca 403 on stop placement (three-layer fix):
      idempotency check in ADJUST flow, `HTTPError` class capturing response
      bodies, and qty-race retry (code 40310000 → wait 2s and retry stop-limit)
- [x] Sentry skips tickers where `selected_for_trading=False` (no more DXCM
      ghost ABORTs, fewer wasted Gemini calls)
- [x] Sentry records fallback ratio in state; Discord alert when >30% of
      checks fall back to heuristic defaults (Gemini outage visibility)
- [x] ADJUST flow restores the old stop if the replacement fails, so a
      held position is never left without a stop-loss
- [x] Orphan-close surfaces Alpaca error codes + messages in logs with a
      "will retry on next run" note
- [x] Gemini structured output mode (`responseMimeType: application/json`
      + `responseSchema`) with thinking disabled — valid JSON guaranteed,
      ~10× fewer output tokens per sentry check
- [x] Backtest A/B comparison: `run_ab_comparison()` and
      `python -m titantrade backtest-ab [dir]` to empirically validate the
      confidence-scaling curve against the flat baseline
- [x] Flutter sentry health badge: degraded state visible on the dashboard
      when fallback_ratio > 30%; green "healthy" pill otherwise
- [x] Qty-race retry now polls `qty_available` for up to 30 s instead of
      sleeping a fixed 2 s — eliminates the ~6-hour unprotected-position
      window observed in production when Alpaca's `pending_cancel` took
      longer than expected to settle

## Phase 1.18: Strategy & operational hardening (2026-05-12)
- [x] Re-entry cooldown (72h) after ABORT — stops whipsaw cycles
- [x] Narrowed macro blackout: 24h → 6h, only high-impact events (FOMC, NFP, CPI, core PCE, GDP)
- [x] `pre_trade_check` now uses `adjusted_confidence` from Pass-2 (fixed confidence-scaling bug)
- [x] Bracket resubmission capped at 5 expired attempts per ticker (price-chase guard)
- [x] Pass 2 target count scales with regime (6/5/4/3/2/1 for strong_bullish → crisis)
- [x] Sentry price-move uses broker `avg_entry_price` for held positions (not stale thesis target)
- [x] Earnings blackout narrowed 5 → 2 calendar days
- [x] State-file archival: trade_log/near_misses auto-trim to most recent N, overflow → state/archive/
- [x] Discord alert when bot is >70% cash for 3+ days
- [x] Discord alert when a ticker round-trips 2+ times in 7 days
- [x] 24 new tests (342 total passing)

## Phase 1.17: Off-hours awareness + ABORT-noise reduction (2026-05-12)
- [x] Diagnosed live: cancel orders submitted off-hours sit in `pending_cancel`
      for 10+ minutes (sometimes hours) until next market open
- [x] New `is_market_open(cfg)` using Alpaca `/v2/clock`
- [x] New `get_order(order_id, cfg)` and `_wait_for_order_canceled()` that
      polls the specific blocking order's status (from `related_orders` in
      Alpaca's 403 body), replacing the qty_available polling that didn't work
- [x] ADJUST, orphan-close, and trailing-stop adjustments now skip during
      off-hours (old stop remains protective on the book)
- [x] Bracket math sanity check in `_handle_bullish_entry` and
      `resubmit_expired_brackets`: refuse to send invalid (stop >= entry)
      brackets to Alpaca that would only get HTTP 422 anyway
- [x] Graduated price-ABORT severity: 3-5% adverse only ABORTs with Gemini
      news confirmation; >=5% adverse always ABORTs; `price_check.py`
      (no news context) only fires on the catastrophic threshold
- [x] 14 new unit tests covering all three fixes; 318 total passing

## Phase 1.15: Capital Deployment Improvements (2026-04-05)
- [x] Confidence-proportional position sizing (linear 0.7x-1.3x scaling)
- [x] `confidence_scaled_risk()` helper in risk_manager.py
- [x] Confidence param added to `volatility_adjusted_shares()` (backward compatible)
- [x] Hedge instrument regime awareness in weekly review prompt
- [x] Inverse ETF warning injected for non-bearish regimes
- [x] Tests for confidence scaling (unit + integration, 10 new tests)
- [x] ADR documentation for both changes

## Phase 1.14: Production Hardening (2026-04-04)
- [x] Gemini truncated JSON repair in ai_parsing.py (closes unterminated strings/brackets)
- [x] Sentry prompt brevity instruction (reasoning under 3 sentences)
- [x] Stop-loss order fallback: stop-limit → plain stop on 403 rejection
- [x] Sector cache initialization in executor (load_stock_sectors at startup)
- [x] SPY change fallback: compute from price/previousClose when changesPercentage missing
- [x] Live portfolio API endpoint (fetches from Alpaca instead of stale static file)

## Phase 2: Testing & Validation
- [x] Unit tests for indicators (known-good RSI/MACD values)
- [x] Unit tests for risk manager gates
- [ ] Integration tests with Alpaca paper trading
- [x] Mock API responses for offline testing
- [x] Validate AI output schema parsing (malformed JSON handling)
- [ ] End-to-end dry run with paper account
- [x] Stress test circuit breaker logic
- [ ] Test earnings blackout with real FMP data

## Phase 3: Monitoring & Alerts
- [x] Discord webhook notifications on job completion/failure
- [x] Daily portfolio summary notifications (weekday 21:00 UTC)
- [x] Error alerting (failed runs notify via Discord)
- [ ] Performance tracking dashboard (Streamlit or Grafana)
- [ ] Weekly P&L report generation

## Phase 4: Enhancements
- [ ] Supabase migration for cloud state (multi-device access)
- [ ] Backtesting engine against historical data
- [ ] Intraday price alerts via WebSocket (supplement cron)
- [ ] Options strategy module
- [ ] Tax-loss harvesting suggestions
- [ ] Portfolio rebalancing automation
- [ ] Multi-account support

## Phase 5: Desktop App (Trade Tracker)
- [x] Flutter project structure and routing (go_router)
- [x] Data models matching TitanTrade JSON schemas
- [x] File-reading providers with 30-second polling
- [x] Setup screen (data path configuration with file_picker)
- [x] Dashboard screen (portfolio overview, positions, recent trades, sentry signals)
- [x] Trade history screen with action filter
- [x] Trade detail screen (thesis + sentry context correlation)
- [x] Active theses screen (card grid with confidence bars)
- [x] Thesis detail screen (full reasoning, price levels, breach condition)
- [x] Dark theme and financial styling
- [ ] Portfolio value chart (fl_chart line chart over time)
- [ ] P&L bar chart per trade
- [x] Settings screen (change data path, refresh interval)
- [ ] Log viewer screen (raw structured JSON logs)
- [ ] Export trade history to CSV

## Known Limitations
- GitHub Actions cron has 5-15 min scheduling variance (mitigated by server deployment)
- Flutter app reads state files read-only except for watchlist management
- Flutter app requires local filesystem access (not a web app)
- FMP free tier rate limits (250/day) tight with market context + 10 stocks
- Alpaca bracket orders are day-only (not GTC), need daily resubmission
- SEC-API real-time tier is paid ($49/month)
- No intraday price monitoring between sentry runs

## Technical Debt
- None yet (greenfield project)
