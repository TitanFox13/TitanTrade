# TitanTrade

Semi-automated AI-powered equity trading system. Two components in one repo.

## Project Structure

```
TitanTrade/             Python backend (analysis, sentry, execution, API server)
titan_trade_app/        Flutter desktop app (dashboard, reads from backend API)
docs/                   Project-wide documentation
```

## Quick Commands

### Python backend (from TitanTrade/)

```bash
uv run python -m titantrade fetch        # Fetch data bundle
uv run python -m titantrade analyze      # Weekly Claude analysis (2-pass)
uv run python -m titantrade sentry       # Daily Gemini sentry (3-layer)
uv run python -m titantrade execute      # Execute trades via Alpaca
uv run python -m titantrade pricecheck   # Intraday price check (no LLM)
uv run python -m titantrade gapcheck     # Gap-down stop-limit protection
uv run python -m titantrade resubmit     # Resubmit expired brackets
uv run python -m titantrade full             # Full pipeline (fetch → analyze → sentry → execute)
uv run python -m titantrade backtest [dir]   # Run backtest on historical data
uv run python -m titantrade download-history [dir]  # Download OHLCV for backtesting
```

### Tests (zero token spend)

```bash
cd TitanTrade && uv run python -m pytest tests/ -v
```

All 185 tests mock AI (Claude, Gemini) and broker (Alpaca, FMP) calls. No real orders, no tokens.

### Flutter app (from titan_trade_app/)

```bash
flutter pub get
flutter run -d linux    # or windows, macos
```

### Docker (production deployment)

```bash
cd TitanTrade
docker compose up -d api cloudflared                    # API server + tunnel
docker compose run --rm titantrade <command>             # CLI commands
```

## Architecture

- **The Analyst** (Claude): weekly 2-pass analysis — per-stock thesis + portfolio ranking
- **The Sentry** (Gemini Flash): daily 3-layer conflict detection (market + price + news)
- **Risk Manager**: 6 programmatic gates between AI and execution
- **Executor**: Alpaca bracket orders with broker-native stops + trailing stops
- **API Server**: FastAPI serving state files, exposed at trade.praguefun.cz via Cloudflare tunnel
- **Desktop App**: Flutter Riverpod app polling the API

## Key Files

| File | Purpose |
|------|---------|
| `src/titantrade/weekly_analyst.py` | 2-pass Claude analysis |
| `src/titantrade/daily_sentry.py` | 3-layer Gemini sentry |
| `src/titantrade/executor.py` | Order execution + trailing stops + orphan/gap protection |
| `src/titantrade/risk_manager.py` | 6 risk gates |
| `src/titantrade/price_check.py` | Intraday price checks (no LLM) |
| `src/titantrade/api.py` | FastAPI HTTP server |
| `src/titantrade/indicators.py` | Pure Python RSI/MACD/Bollinger/ATR/SMA |

## Documentation Rules

This project is strict about documentation. When making changes:

1. Always read ALL `.md` files before starting work
2. Update relevant docs for every feature/change
3. Docs live at three levels: root `docs/` (project-wide), `TitanTrade/docs/` (backend), `titan_trade_app/docs/` (Flutter)
4. New features need: ADR entry in `docs/decisions.md`, feature list update in `docs/features.md`, phase tracking in `docs/todo.md`
5. Tests must mock all external calls — zero token spend, zero real orders

## State Files (TitanTrade/state/)

| File | Updated By |
|------|-----------|
| `weekly_thesis.json` | weekly_analyst (expires after 14 days) |
| `sentry_signals.json` | daily_sentry |
| `trade_log.json` | executor (append-only) |
| `near_misses.json` | executor (blocked by <=2 gates) |
| `trailing_stops.json` | executor (per-ticker HWM + trail price) |
| `pricecheck_signals.json` | price_check |
| `costs.json` | cost_logger (per-API-call tokens) |
| `portfolio.json` | manual / executor |
| `peak_portfolio.json` | risk_manager (drawdown tracking) |
