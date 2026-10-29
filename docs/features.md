# TitanTrade Features

## Strategy (Decisions 061–063, 068)

Every trading decision is a rule on prices; parameters are the Decision 062 plateau, read from `data/watchlist.json` → `settings.mechanical` at every run.

- **Entry**: a watchlist name closes ≥ 8% below its 90-day high while above its 150-day SMA. The watchlist is the dip universe: the 11 sector ETFs since Decision 070 (deployed 2026-10-29), with the hand-picked 15 names kept as `shadow_watchlist` — fetched, curated and backtested (`backtest-mech --shadow`), never traded. Candidates ranked deepest dip first fill the free slots (3 × 10% of equity = 25% of the 40% dip sleeve, flat sizing; `momentum_weight: 0` restores 25% slots). One bracket order at the live price + 0.3% with a −12% stop and a +20% target, through the eight gates. Whole shares only — a slot below one share is skipped.
- **Exits**: the GTC stop-limit (−12%), the +20% target and the 60-trading-day holding limit; the latter two are evaluated against the broker position at every executor run. Nothing else sells a position.
- **Core**: SPY is the dip sleeve's residual — exposure scale × 95% × (1 − momentum weight) − overlay − this run's planned slots — rebalanced within a 5% band. The core sells before entries need the cash and buys back after exits.
- **Momentum sleeve** (068): SPMO held at 60% of the investable book (exposure scale × 95% × 60%), a second core leg rebalanced inside the same band after SPY; never an orphan, no stop, outside the overlay cap and the sector gate. The index does the rotating (semi-annual).
- **Shock trigger** (068): SPY's 10-session return ≤ −7% on any of the last 20 sessions → exposure × 0.5, re-armed by each such session; stateless from the bundle's last 31 SPY closes. Exposure = min(insurance, shock); both core legs scale, new entries pause while either is on.
- **Insurance**: two-signal confirmation; exposure halves only while SPY is below its 200-day SMA *and* fewer than half of the 11 sector ETFs are above theirs. New entries pause while risk-off; held positions keep their exits. Unknown inputs fail open.
- **The plan** (`state/plan.json`, `GET /api/plan`): NEW / HOLD items with entry, stop and target, the watch list with the reason each signal was not taken, ranked candidates, insurance and breadth, the shock state, the combined exposure scale, the sleeve target, free slots, pending buys, legacy positions queued for the orphan close.
- **Legacy transition**: `state/strategy.json` records the strategy start; a position whose opening BUY predates it gets no item and is sold by the orphan close. `window_started_at` (stamped once when the sleeve is on) is the benchmark's clean window; `started_at` never moves.

## Risk Management

### Eight Entry Gates (ALL must pass)
1. **Earnings blackout**: no entry within 2 days of earnings (Finnhub calendar)
2. **Drawdown circuit breaker**: halt at 8% below the portfolio peak. A value ±50% off the peak is treated as broker data corruption (Decision 054): entries pause, Discord alert, the peak file is never written
3. **Cash reserve**: 5% minimum, net of cash committed to pending buy orders (035); the account is re-read after every executed entry in a run (058)
4. **Overlay cap**: overlay positions ≤ 70% of equity (both core legs excluded)
5. **Position size**: the slot (`slot_pct` × (1 − momentum weight) = 10% of equity), reduced to the cash and overlay headroom; anything below $500 notional is blocked as dust (054)
6. **Sector exposure**: ≤ 50% of equity in one sector after the trade (core legs excluded)
7. **Macro blackout**: no entry within 6 h of FOMC / NFP / CPI / core PCE / GDP (046)
8. **Correlation**: blocked when the average 60-day correlation with held positions exceeds 75% — single names only; a sector ETF (`sector_etfs`) passes with "not applied" (Decision 070)

A blocked entry that failed ≤ 2 gates is recorded in `state/near_misses.json` with the gate results and a market snapshot.

### Broker-Side Protection
- **Bracket entries** (entry limit + stop-limit + take-profit, atomic); the stop-limit carries a 1% buffer against slippage
- **GTC stop on fill**: bracket legs are DAY orders and the stop leg sits in `held` while the TP leg is live, so after a fill the TP leg is cancelled and a GTC stop placed at the bracket's level (060)
- **Stop coverage** (`_ensure_coverage`, 060): one helper puts a GTC stop on any bare whole-share plan position from every path — HOLD management at each execute run and the 09:35 ET gapcheck job (`ensure_stop_coverage`); the level is the plan item's stop (the opening bracket's stop from the trade log)
- **Minimum stop distance** (055): an entry whose stop sits < 1.5% below the entry is refused
- **Settled close** (063): every exit — target, holding limit, orphan close — cancels each resting order, polls the cancel to a terminal state, re-reads the position, sells at market, and restores the stop if the sell fails. Introduced after three of seven legacy orphan closes were rejected with Alpaca 40310000 on 2026-10-13 and left positions bare
- **Gap-down protection** (gapcheck, 035/053/054): an unfilled stop-limit after an overnight gap → cancel, settle, market-sell; the live quote is cross-checked first, and a gap > 30% below the stop is checked against the corporate-actions feed so a split is never sold as a crash
- **Stop-out cooldown** (056/059): a broker stop fill starts a 72 h re-entry cooldown stamped at the fill time with the fill price; re-entry before 72 h needs ≥ 24 h *and* a price ≥ 1% above that exit (`cooldown_override_allowed`) — the flat re-buy was the churn
- **Orphan close**: any non-core position without a plan item is sold at the first market-open run; a position opened under the strategy whose name was since removed from the watchlist is *not* one — it keeps its HOLD item and exits by its own stop, target or clock (Decision 070)
- **Expired entries**: a bracket that does not fill by the close expires with its legs; while the signal holds the ticker keeps its NEW item and the next run places a fresh bracket at the live price through the same gates (Decision 064 removed the separate resubmission scan)
- **Never bare**: every failure path that cancels a stop restores one

### Portfolio-Level
- Peak tracking for the drawdown breaker (`state/peak_portfolio.json`)
- Sector and correlation concentration gates; cash reserve net of pending commitments
- Two-signal insurance and the shock trigger (min) scale both core legs and pause entries
- Flat sizing: no ATR, confidence or VIX scaling (Decision 061 — measured as noise)

## Execution

| Scenario | Order | Details |
|----------|-------|---------|
| Entry | Bracket (limit buy + stop-limit + limit sell), DAY | Limit at live × 1.003; stop −12%, target +20% from the entry |
| Stop after fill | Stop-limit, GTC | Replaces the bracket's stop leg; clamps to the broker-reported available qty on a race |
| Target / holding-limit / orphan exit | Market sell | After cancel-settle of the resting stop; stop restored on failure |
| Gap-down exit | Market sell | After cancel-settle; quote + corporate-actions cross-check |
| Core rebalance | Market buy / sell | Toward the residual target, keeping the cash reserve; capped at held qty |

Safety rails: no entry while the ticker has open orders or is held; positions and cash re-read after each trade; every trade logged with the plan reason, levels, gate results and a market snapshot.

## Data Sources

- **Alpaca Data API** (free, same keys as trading): 250-day daily bars (IEX feed for the bundle; SIP for `download-history` and the benchmark's SPY series), latest quotes, corporate actions, news for the curator
- **FRED** (free key): economic-release calendar for the macro gate (+ `data/fomc_dates.json` for FOMC)
- **Finnhub** (free key): earnings calendar (blackout gate), company sector, analyst recommendations for the curator
- All market-data calls fail open (`[]` / `None` / `{}`) on a missing key or error; the gates that consume them skip rather than block
- **Alpaca Markets**: paper and live credentials, account, positions, full order lifecycle; mode toggle via `PUT /api/settings/mode`

## Automation

Built-in APScheduler in the API container (`data/schedule.json`, America/New_York — Decisions 028/039). No host cron.

| Job | Time (ET) | Command |
|-----|-----------|---------|
| `weekday_fetch` | 09:00 Mon–Fri | fetch |
| `weekday_gapcheck` | 09:35 Mon–Fri | gapcheck (+ stop coverage) |
| `weekday_execute_morning` | 10:15 Mon–Fri | execute (= signals + execute) |
| `weekday_execute_preclose` | 15:30 Mon–Fri | execute |
| `daily_summary` | 16:30 Mon–Fri | Discord summary + benchmark refresh |
| `sunday_full` | 16:00 Sun | full |
| `monthly_curate` | 15:00 first Sunday | curate |

Managed via `GET /api/scheduler`, `POST /api/scheduler/{id}/trigger`, `PUT /api/scheduler/{id}/enabled`. Job history is kept in memory per container (`GET /api/scheduler/{id}`).

## Discord Notifications

- Per-job completion / failure embeds (duration, result summary, error text); transient webhook failures retried twice (058)
- Daily summary at 16:30 ET: equity, cash, positions with P&L, the plan (risk-off yes/no with the SPY-SMA and breadth inputs, shock on/off, the sleeve target, held names, free slots, today's signals), trading mode, benchmark line
- Observability alerts: stuck in cash (≥ 70% for 3+ days), ticker churn (2+ round-trips in 7 days), split-suspected gap, suspect broker data, cooldown override, core rebalance
- One optional env var, `DISCORD_WEBHOOK_URL`; unset → silently skipped

## Operational Cost Tracking

`state/costs.json` logs every Claude call (tokens in / out, estimated USD, `run_type: "curator"`); `GET /api/costs`. Trading itself costs no tokens.

## Benchmark Metrics (vs SPY)

- Beta, Jensen's alpha (annualized), Sharpe for both series, information ratio, up / down capture, correlation / R², volatility, total and excess return, max drawdown, a one-line verdict
- Source: Alpaca portfolio-equity history (with the just-closed session appended from the 15Min history, 059) aligned to SPY SIP daily closes (058)
- CLI `benchmark [days] [--since]`, `GET /api/benchmark`, `GET /api/benchmark/refresh?days=N|since=…`, a line on the daily summary. The daily refresh anchors at the strategy start (`strategy.json → started_at`, Decision 065) so the window never straddles two strategies; under 20 trading days the verdict and the ratios are withheld and only the returns are shown; under 3 years (756 trading days) the verdict reads "too short to judge the return" with the annualised excess and its 90% band (1.645 × tracking error / √years) and the summary line shows that band in place of alpha (Decision 069)

## Fill-vs-Backtest Ledger (Decision 069)

- `state/fill_ledger.json`: one row per BUY entry — the fill price (captured from the bracket's `filled_avg_price` when the entry fills inside the poll window, else the bracket limit, flagged) against the close of the session it filled in, the price the backtest would have paid; `gap_pct` positive = the live book paid more
- Appended by the daily summary once the session's SIP bar is published (entries up to 10 days old are retried); rows are never edited; `GET /api/fill-ledger` serves the rows with the median / mean / worst gap; the Discord summary shows the median and today's rows
- The behaviour leg of the go/stop rule reads the median gap at every checkup

## Backtesting & Parameter Search

- `backtest-mech`: the same `signals.py` rules on daily closes, next-close fills, per-side costs, slot accounting out of SPY, cash reserve, the insurance switch, a walk-forward helper and a coarse built-in grid → `state/backtest_mechanical.json`
- `download-history [dir] [--days N]`: SIP daily bars for the watchlist, SPY and the 11 sector ETFs
- `scripts/param_search/`: the Decision 062 harness — a vectorised engine validated trade-for-trade against the backtester, a 6,000-point grid, insurance × sizing stage, walk-forward of the selection procedure, plateau scoring; the Decision 066 / 067 research scripts (screens, century, sleeves, master grid, regimes, crashes, shorts, analogues, dynamic universe) on the same engine. Data (git-ignored) in `data/param_search/`

## HTTP API

`/api/health`, `/api/portfolio`, `/api/plan`, `/api/trades`, `/api/near-misses`, `/api/costs`, `/api/universe-proposal`, `/api/post-mortem`, `/api/benchmark`, `/api/benchmark/refresh`, `/api/fill-ledger`, `/api/settings`, `PUT /api/settings/mode`, `/api/watchlist` (GET / PUT), `/api/scheduler`, `/api/scheduler/{id}`, `POST /api/scheduler/{id}/trigger`, `PUT /api/scheduler/{id}/enabled`. See [TitanTrade/docs/api_reference.md](../TitanTrade/docs/api_reference.md).

## Test Suite (zero token spend)

266 tests in `TitanTrade/tests/`, every external call mocked (`unittest.mock.patch`):

| File | Covers |
|------|--------|
| `test_mechanical.py` | signal rules, insurance, shock trigger, plan building (hold / new / watch / legacy / pending / risk-off / shock / stale inputs), `refresh_plan` + window stamp, residual core and sleeve targets, backtester, curator, API |
| `test_executor.py` | stop coverage (TP-leg scenario, fractional, off-hours, gapcheck companion), target / holding-limit exits, end-to-end `execute_trades`, the SPY-then-SPMO core legs |
| `test_entries.py` | `handle_entry` (levels, sizing, near miss, committed cash, cooldown + override), stop-out scan, GTC stop on fill |
| `test_risk_manager.py` | each gate, slot sizing, dust, suspect value, macro whitelist, correlation |
| `test_protection.py`, `test_gap_down.py` | orphan close, settled close with stop restore, gap-down protection |
| `test_broker.py` | stop placement races, bracket whole-share guard, market hours, cancel polling |
| `test_core_allocation.py`, `test_cooldown.py`, `test_trade_state.py`, `test_alerts.py` | core rebalance, cooldown records + override, trade log / archival / record builders, observability alerts |
| `test_scheduler.py`, `test_api_settings.py`, `test_trading_mode.py`, `test_notifier.py` | scheduler wiring and API, settings endpoints, credential selection, Discord embeds + daily summary |
| `test_market_data.py`, `test_benchmark.py`, `test_indicators.py`, `test_retry.py`, `test_logger.py` | data facade, benchmark maths incl. the 3-year return guard, ATR, retry policy, logging |
| `test_universe_switch.py` | shadow list and design in config, the staged Decision 070 file, HOLD survival of a removed name, the window re-stamp, ETF sectors, the correlation gate on ETFs, the curator on the shadow list, `--shadow` |
| `test_fill_ledger.py` | gap maths, Eastern session date, idempotent update with missing bars, the API endpoint and the summary field |

```bash
cd TitanTrade && uv run --extra test python -m pytest tests/ -q
```
