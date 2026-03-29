# TitanTrade TODO

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
- [ ] Slack/Discord webhook notifications on ABORT signals
- [ ] Daily portfolio summary notifications
- [ ] Error alerting (failed runs, API outages)
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
