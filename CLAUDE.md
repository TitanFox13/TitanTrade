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
uv run python -m titantrade fetch        # Fetch data bundle (prices, indicators, breadth, news, earnings)
uv run python -m titantrade signals      # Mechanical signals → weekly_thesis.json / sentry_signals.json / signals.json (ADR 061)
uv run python -m titantrade execute      # Execute trades via Alpaca (scheduler runs signals first)
uv run python -m titantrade gapcheck     # Gap-down stop-limit protection + place missing stops
uv run python -m titantrade resubmit     # Resubmit expired brackets
uv run python -m titantrade curate       # Monthly LLM universe proposal + post-mortem (no orders)
uv run python -m titantrade benchmark [days] # Performance vs SPY: beta/alpha/Sharpe (--since YYYY-MM-DD)
uv run python -m titantrade full             # Full pipeline (fetch → signals → execute)
uv run python -m titantrade backtest-mech [dir] [--start] [--end] [--split] [--grid]  # Mechanical strategy backtest / walk-forward
uv run python -m titantrade download-history [dir] [--days N]  # Download OHLCV (watchlist + SPY + sector ETFs)
uv run --with numpy python scripts/param_search/search.py  # Decision 062 parameter search harness (see scripts/param_search/README.md)
uv run python -m titantrade analyze      # [legacy strategy=llm] Weekly Claude analysis
uv run python -m titantrade sentry       # [legacy strategy=llm] Daily Gemini sentry
uv run python -m titantrade pricecheck   # [legacy] Intraday price check
uv run python -m titantrade backtest [dir]   # [legacy] Backtest of the LLM-era rules with synthetic theses
```

### Tests (zero token spend)

```bash
cd TitanTrade && uv run --extra test python -m pytest tests/ -v
```

`pytest` lives in the `test` optional-dependency extra, so the `--extra test` flag is required (a bare `uv run` omits it → `No module named pytest`). All 612 tests mock AI (Claude, Gemini) and broker (Alpaca, FMP) calls. No real orders, no tokens. `ruff`/`vulture` are in the `dev` extra for lint/dead-code checks.

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

- **Mechanical signals** (ADR 061, `signals.py` + `mechanical.py`): buy a watchlist name ≥10% below its 60-day high while above its 200-day SMA, 20% slots (max 3), exits at +10% / −12% stop / 40 trading days; SPY is the residual; two-signal insurance (SPY < SMA200 and sector breadth < 50% → half exposure). Writes the thesis/sentry state files the executor consumes.
- **Risk Manager**: 9 programmatic gates between the signal and execution (slot sizing under the mechanical strategy)
- **Executor**: Alpaca bracket orders with broker-native GTC stops; target/time exits evaluated at each run
- **Curator** (Claude, monthly): universe-curation proposal + post-mortem — advisory, never places orders
- **Legacy (`strategy: "llm"`, unscheduled)**: the weekly 2-pass Claude analyst and the daily Gemini sentry
- **API Server**: FastAPI serving state files, exposed at trade.praguefun.cz via Cloudflare tunnel
- **Desktop App**: Flutter Riverpod app polling the API

## Key Files

| File | Purpose |
|------|---------|
| `src/titantrade/signals.py` | Pure mechanical rules: dip-in-uptrend, breadth, two-signal insurance (shared by live + backtest) |
| `src/titantrade/mechanical.py` | Mechanical driver: thesis/sentry/signals state files, residual core target, legacy detection |
| `src/titantrade/curator.py` | Monthly LLM universe proposal + post-mortem (advisory) |
| `src/titantrade/backtest/mechanical.py` | Mechanical-strategy backtester + walk-forward |
| `src/titantrade/weekly_analyst.py` | [legacy] 2-pass Claude analysis |
| `src/titantrade/daily_sentry.py` | [legacy] 3-layer Gemini sentry |
| `src/titantrade/executor.py` | Execution **orchestrator** (`execute_trades`) — wires the modules below together |
| `src/titantrade/broker.py` | Alpaca REST client — the only module that talks to Alpaca |
| `src/titantrade/entries.py` | New-position entry + expired-bracket resubmission (all 9 risk gates) |
| `src/titantrade/positions.py` | Open-position management: ATR trailing stop, TP1, pyramiding |
| `src/titantrade/protection.py` | Pre-flight safety: orphan close + gap-down protection |
| `src/titantrade/core_allocation.py` | Always-on core (SPY) allocation + stress hedge swap |
| `src/titantrade/pricing.py` | Trend-regime classification + entry-price selection (pure) |
| `src/titantrade/cooldown.py` | Re-entry ABORT cooldown state + override policy |
| `src/titantrade/trade_state.py` | Trade log / near-miss store, state loader, trade-record builders |
| `src/titantrade/trailing_state.py` | Per-ticker trailing-stop state (HWM, trail, TP1/pyramid flags) |
| `src/titantrade/alerts.py` | Discord observability alerts (stuck-in-cash, ticker churn) |
| `src/titantrade/risk_manager.py` | 9 risk gates |
| `src/titantrade/price_check.py` | Intraday price checks (no LLM) |
| `src/titantrade/benchmark.py` | Risk-adjusted metrics vs SPY (beta/alpha/Sharpe/capture) |
| `src/titantrade/api.py` | FastAPI HTTP server |
| `src/titantrade/scheduler.py` | Built-in APScheduler (cron jobs inside API process) |
| `src/titantrade/indicators.py` | Pure Python RSI/MACD/Bollinger/ATR/SMA |
| `src/titantrade/notifier.py` | Discord webhook notifications (job alerts + daily summary) |

> **Executor decomposition complete** (ADR 036): `executor.py` was a 3,267-line god-module; it's now a **691-line orchestrator** plus the 10 focused modules above (broker/entries/positions/protection/core_allocation/pricing/cooldown/trade_state/trailing_state/alerts). Dependency flow: leaf modules → core_allocation → protection → entries/positions → executor. `executor.py` re-exports the symbols `execute_trades` calls, so `titantrade.executor.X` patch targets still resolve for orchestrator-resident callers. Behavior-preserving; 424 tests green. Run tests with `--extra test` (see below). Remaining polish (tracked in todo): de-dup shared entry-adaptation logic in `entries.py`; decompose the long `execute_trades`/`_handle_bullish_entry` functions.

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
| `weekly_thesis.json` | mechanical (every signals run; legacy: weekly_analyst) |
| `sentry_signals.json` | mechanical (CONTINUE + insurance state; legacy: daily_sentry) |
| `signals.json` | mechanical (insurance, ranked candidates, slots, legacy-to-close) |
| `strategy.json` | mechanical (strategy start timestamp — positions opened before it are legacy) |
| `universe_proposal.json`, `post_mortem.json` | curator (monthly) |
| `backtest_mechanical.json` | backtest-mech |
| `trade_log.json` | executor (append-only) |
| `near_misses.json` | executor (blocked by <=2 gates) |
| `trailing_stops.json` | executor (per-ticker HWM + trail price) |
| `pricecheck_signals.json` | price_check |
| `costs.json` | cost_logger (per-API-call tokens) |
| `portfolio.json` | manual / executor |
| `peak_portfolio.json` | risk_manager (drawdown tracking) |
| `benchmark_metrics.json` | benchmark (beta/alpha/Sharpe vs SPY; refreshed by daily_summary) |
