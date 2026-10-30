# TitanTrade

Mechanical equity trading system on Alpaca: two sleeves — a dip-in-uptrend overlay on the 11 sector ETFs with broker-side stops on top of a SPY residual (40%; Decision 070 — the hand-picked 15 names are the tracked-only `shadow_watchlist`) and a momentum ETF held (SPMO, 60%) — with a two-signal insurance and a shock trigger scaling exposure, tuned on 10–99 years of history (Decisions 061–063, 068). Paper account; going live is gated (todo Phase 2.0). No LLM runs on the schedule (Decision 082 retired the monthly curator); `curate` remains a manual, advisory command that places no orders.

## Project Structure

```
TitanTrade/                 Python backend: data, signals, plan, risk gates, execution, API + scheduler
TitanTrade/scripts/         Parameter-search harness (Decision 062)
TitanTrade/legacy/          Frozen LLM-era modules, tests, scripts and docs — not importable (git tag v2-llm-pipeline)
docs/                       Project-wide documentation (handover, roadmap, decisions, features, todo, architecture, insights)
```

The Flutter desktop app was deleted in Decision 063 (unused). The HTTP API is the only front end.

## Quick Commands (from TitanTrade/)

```bash
uv run python -m titantrade fetch        # Data bundle: 250-day bars → signal inputs, ATR, correlations, sector breadth, earnings, macro calendar
uv run python -m titantrade signals      # Build state/plan.json from the bundle + broker positions (no orders)
uv run python -m titantrade execute      # Execute the plan via Alpaca (the scheduler runs signals first)
uv run python -m titantrade full         # fetch → signals → execute
uv run python -m titantrade gapcheck     # Gap-down protection + stop coverage for bare plan positions
uv run python -m titantrade curate       # Manual Claude universe proposal + post-mortem (advisory, no orders; off the schedule since Decision 082)
uv run python -m titantrade benchmark [days] [--since YYYY-MM-DD]   # Beta / alpha / Sharpe / capture vs SPY
uv run python -m titantrade backtest-mech [dir] [--start] [--end] [--split] [--grid] [--shadow]   # The two-sleeve book path-exact on daily closes (Decision 081); --shadow adds the shadow list, each list also as the dip sleeve alone
uv run python -m titantrade download-history [dir] [--days N]       # SIP daily bars: watchlist + shadow list + SPY + 11 sector ETFs + SPMO (+ the cash ticker)
uv run --with numpy python scripts/param_search/search.py           # Parameter search (scripts/param_search/README.md)
```

### Tests (zero token spend)

```bash
cd TitanTrade && uv run --extra test python -m pytest tests/ -q
```

`pytest` lives in the `test` extra, so `--extra test` is required. `addopts` suppresses the summary line — read the exit code or use `-v`. All 277 tests mock Claude, Alpaca, FRED and Finnhub: no orders, no tokens. Lint with `uv run --extra dev ruff check src/titantrade tests` (`vulture` is in the same extra). `legacy/tests` is not collected (`testpaths = ["tests"]`).

### Docker (production)

```bash
cd TitanTrade
docker compose up -d api cloudflared            # API server + scheduler + tunnel
docker compose run --rm titantrade <command>    # one-off CLI commands
```

Deploy = `git pull && docker compose build api titantrade && docker compose up -d api` — both images, every time (the CLI image drifts otherwise).

## Architecture

- **Data** (`data_fetcher.py`, `market_context.py`): 250-day Alpaca bars per name → `signal_inputs` (close, lookback high, trend SMA), ATR-14, 60-day correlations; SPY returns + sector breadth; Finnhub earnings; FRED macro calendar → `state/data_bundle.json`.
- **Signals** (`signals.py` pure rules; `mechanical.py` builds the plan): dip-in-uptrend entries ranked deepest first into free slots, two-signal insurance and the shock trigger (exposure = min of both; entries pause while either is on), the sleeve target, held positions with their stop and target → `state/plan.json`.
- **Risk Manager** (`risk_manager.py`): 8 programmatic gates between the plan and the broker; flat slot sizing (25% of the dip sleeve = 10% of equity) trimmed by cash and the overlay cap; both core legs sit outside the cap and the sector gate.
- **Executor** (`executor.py` with `entries.py`, `protection.py`, `core_allocation.py`): orphan close → gap check → residual SPY core, then the SPMO sleeve → stop-out cooldowns → NEW entries (one near-market bracket, GTC stop on fill) → HOLD management (stop coverage, +target / holding-limit exits through a cancel-settle-close).
- **Curator** (`curator.py`, Claude, manual only since Decision 082): universe proposal + post-mortem, advisory, no scheduled run.
- **API + scheduler** (`api.py`, `scheduler.py`): FastAPI serving the state files at trade.praguefun.cz (Cloudflare tunnel); APScheduler jobs from `data/schedule.json` run inside the API container.
- **Benchmark** (`benchmark.py`): beta / alpha / Sharpe / capture vs SPY over the clean window (`strategy.json → window_started_at`, else `started_at`), refreshed by the daily summary; ratios and the verdict are withheld under 20 trading days; under 3 years the verdict reports the annualised excess with its 90% band and judges nothing (Decision 069).

## Key Files

| File | Purpose |
|------|---------|
| `src/titantrade/signals.py` | Pure rules shared by live and backtest: dip state, SMA, breadth, insurance, ranking, trading-day count |
| `src/titantrade/mechanical.py` | `build_plan` / `refresh_plan` (plan.json), `core_target_pct`, strategy start + legacy-position detection |
| `src/titantrade/executor.py` | `execute_trades` orchestrator, stop coverage (`_ensure_coverage`, `ensure_stop_coverage`), held-position exits |
| `src/titantrade/entries.py` | `handle_entry` (gates → one bracket → GTC stop on fill), stop-out cooldown scan |
| `src/titantrade/risk_manager.py` | The 8 gates (`pre_trade_check`), drawdown breaker + suspect-value guard, overlay headroom |
| `src/titantrade/protection.py` | `close_position_settled` (cancel → settle → sell → restore stop on failure), plan-based orphan close, gap-down protection |
| `src/titantrade/core_allocation.py` | SPY core rebalance to a target share of equity |
| `src/titantrade/broker.py` | Alpaca REST client — the only module that talks to Alpaca |
| `src/titantrade/pricing.py` | Near-market entry + stop / target levels, bracket sanity checks, ATR lookup, earnings block |
| `src/titantrade/cooldown.py` | 72 h re-entry cooldown after a stop-out; override after 24 h at ≥ 1% above the exit |
| `src/titantrade/trade_state.py` | Trade log + near-miss store (archival), opening-buy lookups, record builders |
| `src/titantrade/fill_ledger.py` | Fill-vs-backtest ledger (Decision 069): each entry's fill against the session close the backtest would have paid; appended by the daily summary |
| `src/titantrade/alerts.py` | Discord alerts: stuck in cash, ticker churn |
| `src/titantrade/data_fetcher.py`, `market_context.py` | Data bundle; sector cache, sector breadth, SPY context |
| `src/titantrade/curator.py` | Claude universe proposal + post-mortem (`_call_claude`, cost-logged) — manual `curate` only, off the schedule (082) |
| `src/titantrade/backtest/mechanical.py` | Backtester + walk-forward on the same `signals.py` rules, with the live book's accounting (SPMO leg, SPY residual, 10 % slots, min(insurance, shock), per-leg band — Decision 081) |
| `src/titantrade/benchmark.py` | Risk-adjusted metrics vs SPY |
| `src/titantrade/api.py`, `scheduler.py` | FastAPI server; APScheduler jobs |
| `src/titantrade/notifier.py` | Discord job alerts + daily summary (plan section) |
| `src/titantrade/config.py` | `.env` + `data/watchlist.json` → `Config`; `TradingSettings` holds the strategy parameters |
| `src/titantrade/indicators.py` | ATR + pairwise correlation (pure) |

Dependency flow: leaf modules (broker, trade_state, pricing, cooldown, signals, market_data) → core_allocation → protection → entries → mechanical / executor. No module imports `executor`; `executor.py` re-exports the broker names it calls, so `titantrade.executor.X` patch targets resolve.

## Documentation Rules

1. Read ALL `.md` files before starting work (root `docs/`, `TitanTrade/docs/`, this file); **start with `docs/handover.md`** (the latest handover: state, working conventions, the first task) and `docs/roadmap.md` (the living plan — move an item's status there whenever a Decision changes it)
2. Update the relevant docs with every change, in the same commit
3. New behaviour needs: a Decision in `docs/decisions.md`, the feature list in `docs/features.md`, a phase in `docs/todo.md`
4. Tests must mock every external call — zero token spend, zero real orders
5. `TitanTrade/legacy/` is frozen: never edit, import or document it as live

## State Files (TitanTrade/state/)

| File | Written by |
|------|-----------|
| `data_bundle.json` | fetch |
| `plan.json` | signals (`mechanical.refresh_plan`, run before every execute) |
| `strategy.json` | first signals run (`started_at`; positions opened earlier are legacy and get closed); `window_started_at` / `design` / `dip_universe` re-stamped whenever the configured `design` changes (benchmark window) |
| `trade_log.json`, `near_misses.json` | executor (append-only; overflow archived to `state/archive/`) |
| `portfolio.json` | executor (equity / cash / positions snapshot at the end of each run; read by the daily summary and the API fallback) |
| `abort_cooldown.json` | entries (stop-out cooldowns with the exit price) |
| `peak_portfolio.json` | risk_manager (drawdown breaker high-water mark) |
| `alert_state.json` | alerts (dedup of observability alerts) |
| `costs.json` | cost_logger (curator token spend) |
| `sector_cache.json` | market_context (ticker → sector, Finnhub) |
| `benchmark_metrics.json` | benchmark (refreshed by daily_summary) |
| `fill_ledger.json` | fill_ledger (daily_summary; one row per entry, never edited) |
| `universe_proposal.json`, `post_mortem.json` | curate (manual only since Decision 082) |
| `backtest_mechanical.json` | backtest-mech |
