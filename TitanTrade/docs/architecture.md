# Backend Architecture

## Overview

The backend has two faces: a CLI (one-off commands via `docker compose run`) and an always-on FastAPI server whose built-in APScheduler runs every scheduled job (`data/schedule.json`, America/New_York — Decisions 028/039). Each job reads config, calls external APIs, and writes JSON state files. The system diagram is in [docs/architecture.md](../../docs/architecture.md).

---

## Pipeline

### 1. Fetch (`data_fetcher.py`, 09:00 ET weekdays and in `full`)
- 250 daily bars per watchlist name (and per `shadow_watchlist` name, for the curator — Decision 070) from Alpaca → `signal_inputs` (last close, rolling high over `dip_lookback_days`, `trend_sma_days` SMA), ATR-14, the last 5 bars for display, a 60-day pairwise correlation matrix
- `market_context.build_market_context`: SPY close, 1/5/20-day returns and the last `shock_lookback_days + shock_hold_days + 1` closes (the shock trigger's window); `sector_breadth` — SPY and the 11 sector ETFs vs their `insurance_sma_days` SMA
- Finnhub earnings (`earnings.build_earnings_context`: next date, days away, blocked flag); FRED release calendar + `data/fomc_dates.json`
- Output: `state/data_bundle.json`

### 2. Signals (`mechanical.refresh_plan`, run by every `execute` and by `signals`)
- Reads the bundle, the broker positions and open buy orders, the trade log, and `state/strategy.json` (written on the first run; its `started_at` separates mechanical positions from legacy ones; `window_started_at` / `design` are stamped once when the momentum sleeve is on — the benchmark's clean window)
- `build_plan`: HOLD items for held mechanical positions (stop and target from the opening BUY in the trade log), including a name since removed from the watchlist (it exits by its own rules, never a forced sell — 070); the insurance state from `market_context.breadth` and the shock state (`signals.shock_state`) from `market_context.spy.closes`, combined as `exposure_scale = min(...)`; the sleeve target (`momentum_target_pct`); `signals.evaluate_dip` on every name not held or pending; candidates ranked deepest dip first fill `max_slots − held − pending` slots as NEW items (entry at the last close, stop −`stop_pct`, target +`tp_pct`); everything else goes on the watch list with its reason (no entries while risk-off or the shock is on); legacy positions are listed in `legacy_to_close`
- Warns and flags `stale_inputs` when the bundle's lookback / SMA lengths differ from the parameters in force (re-run `fetch`)
- Output: `state/plan.json`

### 3. Execute (`executor.execute_trades`, 10:15 and 15:30 ET weekdays, Sunday `full`)
1. Market-open check; sector cache; **orphan close** (`protection.close_orphaned_positions`: every non-core position without a plan item, via `close_position_settled`); **gap-down protection**
2. Load the plan and the bundle; read the account and positions. A reported account value more than 50 % off the recorded peak (`risk_manager.account_value_suspect`) is broker data corruption: the run logs, alerts and skips steps 3, 5 and the exits in 6, keeping only the stop coverage (Decision 084)
3. **Core legs**: SPY first — `mechanical.core_target_pct` = exposure scale × (1 − cash reserve) × (1 − momentum weight) − (held overlay + planned NEW slots) / equity → `core_allocation.manage_core_position(target_pct, ticker=SPY)`; then the momentum sleeve — `momentum_target_pct` = exposure scale × (1 − cash reserve) × momentum weight → the same helper with `ticker=SPMO`; then, when `cash_ticker` is set (071), the T-bill leg at `cash_target_pct` = (1 − exposure scale) × (1 − cash reserve), placed first when it must sell and last when it must buy; the account is re-read after each core trade
4. **Stop-out cooldowns**: `entries.record_stop_out_cooldowns` scans filled sell stops and stamps the 72 h cooldown with the fill price
5. **NEW items**: `entries.handle_entry` — live price → cooldown check → `pricing.entry_levels` (entry = price × 1.003, stop, target) → sanity checks → committed cash → `risk_manager.pre_trade_check` (8 gates, slot sizing) → near miss or one bracket → `_ensure_gtc_stop_on_fill`; account re-read after each entry
6. **HOLD items**: `executor._manage_held` — stop coverage at the item's stop; exit when `unrealized_plpc ≥ tp_pct` *and the live quote confirms it* (trigger `target`; a mark the market does not confirm is kept with a warning, Decision 084) or trading days held ≥ `max_hold_days` (trigger `holding_limit`), both via `close_position_settled`
7. Observability alerts (stuck in cash, ticker churn)

### 4. Gapcheck (09:35 ET weekdays)
`protection.check_gap_down_protection` then `executor.ensure_stop_coverage` (a GTC stop for any whole-share HOLD position without one).

### 5. Daily summary (16:30 ET weekdays) and curate (manual only since Decision 082; the schedule entry is disabled)
Discord summary with the plan section + benchmark refresh anchored at `mechanical.benchmark_window_start()` (`window_started_at`, else `started_at`; Decisions 065 / 068) + the fill ledger update (`fill_ledger.update_fill_ledger`: every recent BUY entry gets its session close from SIP bars, Decision 069); the Claude universe proposal (on the shadow list when there is one) and post-mortem.

---

## Module Dependency Graph

```
config.py, logger.py, retry.py
├── indicators.py        <- ATR, correlation (pure)
├── signals.py           <- dip / SMA / breadth / insurance / ranking rules (pure; shared with the backtester)
├── market_data.py       <- facade over data_providers/native.py (Alpaca + FRED + Finnhub)
├── market_context.py    <- sector cache, sector breadth, SPY context
├── earnings.py          <- earnings calendar → blackout flag
├── data_fetcher.py      <- the data bundle (uses indicators, signals, market_context, earnings)
├── broker.py            <- Alpaca REST client (the ONLY module that calls the trading API)
├── trade_state.py       <- trade log / near misses (archival), opening-buy lookups, record builders
├── pricing.py           <- entry levels, bracket sanity, ATR lookup, earnings block (pure)
├── cooldown.py          <- stop-out cooldown state + override policy
├── risk_manager.py      <- the 8 gates, drawdown breaker, overlay headroom (uses market_context)
├── alerts.py            <- stuck-in-cash / churn alerts (uses trade_state, notifier)
├── core_allocation.py   <- SPY core rebalance (uses broker, trade_state)
├── protection.py        <- settled close, orphan close, gap-down (uses broker, trade_state)
├── entries.py           <- handle_entry, stop-out scan (uses broker, pricing, cooldown, risk_manager, trade_state)
├── mechanical.py        <- plan builder + core target (uses signals, broker, trade_state, market_context, risk_manager)
├── executor.py          <- execute_trades orchestrator, stop coverage, held exits (uses all of the above)
├── curator.py           <- Claude universe proposal + post-mortem (uses market_data, cost_logger, notifier)
├── benchmark.py         <- metrics vs SPY (broker portfolio history + SIP bars)
├── fill_ledger.py       <- fill vs the backtest's price per entry (trade log + SIP bars)
├── backtest/            <- data_loader (SIP bars), mechanical (the two-sleeve book path-exact on signals.py: momentum leg, SPY residual, slots on the sleeve, min(insurance, shock), per-leg band in the executor's order — Decision 081; walk-forward)
├── notifier.py          <- Discord embeds + daily summary
├── scheduler.py         <- APScheduler jobs → the commands in __main__
└── api.py               <- FastAPI endpoints over state/ + scheduler
```

No module imports `executor`. `executor.py` re-exports the broker functions it calls, so `titantrade.executor.<name>` patch targets resolve in tests.

---

## State Files

| File | Purpose | Written by |
|------|---------|-----------|
| `data_bundle.json` | Signal inputs, ATR, correlations, market context, earnings, macro calendar | fetch |
| `plan.json` | NEW / HOLD items, watch, candidates, insurance, shock, exposure scale, sleeve target, slots, legacy positions | signals |
| `strategy.json` | `started_at` of the mechanical strategy; `window_started_at` / `design` / `dip_universe` of the current design | first signals run / any run whose configured `design` differs |
| `trade_log.json` | Every order placed (append-only, archived past 500) | executor |
| `near_misses.json` | Entries blocked by ≤ 2 gates (archived past 200) | entries |
| `portfolio.json` | Equity, cash, positions as the last run left them | executor |
| `abort_cooldown.json` | Stop-out cooldowns with exit price | entries |
| `peak_portfolio.json` | Drawdown high-water mark | risk_manager |
| `alert_state.json` | Alert dedup | alerts |
| `costs.json` | Claude token spend | cost_logger (curator) |
| `benchmark_metrics.json` | Metrics vs SPY | benchmark |
| `fill_ledger.json` | Fill vs session close per entry, median gap (069) | fill_ledger (daily summary) |
| `universe_proposal.json`, `post_mortem.json` | Monthly curation | curator |
| `backtest_mechanical.json` | Last backtest | backtest-mech |
| `sector_cache.json` | ticker → sector | market_context |

---

## Risk Control Summary

| Control | Value | Enforced in |
|---------|-------|-------------|
| Slot size / max slots | 25% of the dip sleeve = 10% of equity × 3 (flat) | risk_manager (`pre_trade_check`) |
| Overlay cap | 70% of equity, both core legs excluded (also from the sector gate) | risk_manager |
| Cash reserve | 5%, net of pending buys, re-read after each entry | risk_manager / executor |
| Min notional | $500 (dust guard, 054) | risk_manager |
| Drawdown breaker | 8% from peak; ±50% → suspect data: entries blocked and the whole run keeps only the stops (054 / 084) | risk_manager / executor |
| Earnings blackout | 2 days | earnings / risk_manager |
| Macro blackout | 6 h, high-impact only | risk_manager |
| Sector / correlation | 50% / 0.75 | risk_manager |
| Stop | −12% stop-limit, GTC after fill, one coverage helper (060) | entries / executor |
| Target / holding limit | +20% / 60 trading days, close-based | executor |
| Min stop distance | 1.5% (055) | pricing / entries |
| Settled close | cancel → terminal → sell → restore stop (063) | protection |
| Gap-down protection | quote + corporate-actions cross-check (053/054) | protection |
| Stop-out cooldown | 72 h; override ≥ 24 h and ≥ 1% above the exit (056/059) | cooldown / entries |
| Insurance | SPY < SMA200 and breadth < 50% → exposure × 0.5, no new entries | signals / mechanical |
| Shock trigger (068) | SPY −7% over 10 sessions within the last 20 → exposure × 0.5, no new entries; exposure = min(insurance, shock) | signals / mechanical |
| Core | SPY = the dip sleeve's residual (40%), SPMO = 60% of the investable book, 5% rebalance band each | mechanical / core_allocation |
