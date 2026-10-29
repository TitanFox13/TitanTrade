# Risk Management

## Philosophy

The system's job is to not lose money, and secondarily to make money. Missed opportunities are cheap; blown accounts are permanent. Every rule below is code — nothing upstream (the plan, the operator's watchlist, the monthly LLM proposal) can bypass it.

## What Protects the Book

- **Position level**: a GTC stop-limit at −12% on every whole-share overlay position (placed by the bracket, converted on fill, re-placed by the 09:35 ET coverage job if ever missing — Decision 060); a +20% target and a 60-trading-day limit evaluated at each executor run; the orphan close for any position without a plan item.
- **Portfolio level**: flat slots of 25% of the dip sleeve (10% of equity, max 3) under a 70% overlay cap, the 5% cash reserve, the drawdown breaker, the sector / correlation / earnings / macro gates, the two-signal insurance (SPY < 200-day SMA **and** sector breadth < 50% → exposure halves, no new entries; fails open when inputs are unknown) and the shock trigger (068: SPY −7% over 10 sessions within the last 20 → exposure halves, no new entries); exposure = min of the two, applied to both core legs (SPY, SPMO).
- **What no longer sells**: the LLM sentry, the intraday price check, the hedge swap and the trailing / TP1 manager — measured as net losses or untested (Decision 060, Evidence 3) and frozen under `legacy/`.

## The Eight Gates (`risk_manager.pre_trade_check`)

Evaluated in order for every NEW item (an entry that expired unfilled is simply a NEW item again at the next run); a failure of ≤ 2 gates is recorded as a near miss.

1. **Earnings blackout** — no entry within 2 calendar days of earnings (Finnhub; `earnings.DEFAULT_BLOCK_DAYS`). Binary risk that cannot be hedged.
2. **Drawdown circuit breaker** — all entries halt while equity is ≥ 8% below the recorded peak (`state/peak_portfolio.json`). **Suspect-value guard** (054): a value more than ±50% off the peak is broker data corruption, not a drawdown — entries pause for the run, the block is labelled "suspect broker data" and alerted, and `update_peak_value` refuses the spike so a glitch never trips the breaker permanently.
3. **Cash reserve** — 5% of equity stays in cash. The gate nets out the notional of pending (unfilled) buy orders (`open_buy_commitment`, 035), and the executor re-reads the account after every executed entry so an instantly filled bracket cannot be spent twice (058).
4. **Overlay cap** — overlay positions ≤ 70% of equity (`compute_overlay_headroom`, both core legs excluded). Protects the core.
5. **Position size** — the slot is `overlay_slot_pct` = `slot_pct × (1 − momentum_weight)` × equity, reduced to the cash and overlay headroom, floored to whole shares; anything below `MIN_POSITION_NOTIONAL` ($500) is blocked as dust (054). No ATR, confidence or VIX scaling (061).
6. **Sector exposure** — the trade may not push one sector above 50% of equity.
7. **Macro blackout** — no entry within 6 h of a high-impact release: FOMC, NFP / jobs, CPI, core PCE, GDP (046 whitelist).
8. **Correlation** — blocked when the average 60-day correlation with held positions exceeds 0.75 (hidden concentration across sectors). Single names only: a ticker in `sector_etfs` is a diversified basket and passes with "not applied" (Decision 070 — the sector floor was measured without the gate, which would have blocked ~1 in 5 second slots on the ETFs' real correlations).

## Broker-Side Protection

- **Brackets**: entry limit + stop-limit + take-profit, atomic, DAY. The stop-limit's limit sits 1% below the stop against slippage. `place_bracket_order` refuses fractional qty (Alpaca 422) and sizes below one share are skipped.
- **GTC stop on fill** (`entries._ensure_gtc_stop_on_fill`, 060): bracket legs are DAY orders and the stop leg sits in `held` while the TP leg is live (invisible to the open-orders query). After a fill the TP leg is cancelled (OCO takes the held stop with it), the cancel is polled to a terminal state, and a GTC stop is placed at the bracket's level.
- **Stop coverage** (`executor._ensure_coverage`, 060): one helper on every path — HOLD management at each execute run and `ensure_stop_coverage` in the 09:35 gapcheck — places a GTC stop on any whole-share HOLD position without one, at the plan item's stop (the opening bracket's level from the trade log). Off-hours the placement is deferred. Fractional positions and the core carry no stop.
- **Minimum stop distance** (`pricing.stop_too_tight`, 055): a stop < 1.5% below the entry is noise and refused.
- **Settled close** (`protection.close_position_settled`, 063): every exit cancels each resting order, waits for its terminal state (`_wait_for_order_canceled`), re-reads the position, sells at market, and on a failed sell re-places the stop at the level that was just cancelled. Target, holding-limit and orphan exits all go through it. Born from 2026-10-13: three of seven legacy orphan closes were rejected with 40310000 because the old path sold before the cancel settled, leaving FCX, HCA and LLY bare.
- **Stop placement race** (`broker.place_native_stop_loss`): on 40310000 the blocking order from `related_orders` is polled to a terminal state and the stop re-sent; with no blocking order it clamps to the broker-reported available qty.
- **Gap-down protection** (035/053/054): an unfilled stop-limit after an overnight gap → cancel, settle, market sell. The live quote is cross-checked first; a gap > 30% below the stop checks the corporate-actions feed and skips + alerts on a recent split.
- **Stop-out cooldown** (056/059): a filled sell stop starts a 72 h re-entry cooldown stamped at the fill time with the fill price (`record_stop_out_cooldowns`, idempotent). Re-entry before 72 h needs ≥ 24 h *and* a current price ≥ 1% above that exit (`cooldown_override_allowed`): of 23 early re-entries Jul–Sep 2026, the 10 that came in flat all lost, the 13 that came in ≥ 1% above kept every winner. Records without an exit price get the full 72 h.
- **Expired entries** (Decision 064): a bracket that does not fill by the close expires; the ticker keeps its NEW item while the dip signal holds and the next run places a fresh near-market bracket through the same gates. No separate resubmission scan and no attempt cap — the mechanical entry is a near-market limit that fills the same session almost always.
- **Orphan close** (`protection.close_orphaned_positions`): any non-core position without a plan item is sold at the first market-open run (positions opened before the strategy start). A name removed from the watchlist after it was bought keeps its HOLD item and exits by its own stop / target / clock (Decision 070) — a watchlist edit never force-sells.
- **Never bare**: every failure path that cancels a stop restores one.

## Parameters

| Parameter | Value | Defined in |
|-----------|-------|-----------|
| `dip_pct` / `dip_lookback_days` / `trend_sma_days` | 0.08 / 90 / 150 | `data/watchlist.json` → `TradingSettings` (Decision 062) |
| `slot_pct` / `max_slots` | 0.25 (of the dip sleeve) / 3 | same |
| `momentum_ticker` / `momentum_weight` | SPMO / 0.6 | same |
| `shock_drop_pct` / `shock_lookback_days` / `shock_hold_days` / `shock_scale` | 0.07 / 10 / 20 / 0.5 | same |
| `tp_pct` / `stop_pct` / `max_hold_days` | 0.20 / 0.12 / 60 | same |
| `insurance_sma_days` / `insurance_breadth` / `insurance_scale` | 200 / 0.5 / 0.5 | same |
| `core_ticker` / `core_rebalance_band_pct` | SPY / 0.05 | config.py |
| `design` / `shadow_watchlist` | "070" / the 15 hand-picked names (tracked, not traded) | `data/watchlist.json` |
| `MAX_DRAWDOWN_PCT` | 8.0 | risk_manager.py |
| `SUSPECT_VALUE_DEVIATION_PCT` | 50.0 | risk_manager.py |
| `MIN_CASH_RESERVE_PCT` | 5.0 | risk_manager.py |
| `MAX_TOTAL_OVERLAY_PCT` | 0.70 | risk_manager.py |
| `MIN_POSITION_NOTIONAL` | $500 | risk_manager.py |
| `MAX_SECTOR_EXPOSURE_PCT` | 50.0 | risk_manager.py |
| `MACRO_BLACKOUT_HOURS` | 6 | risk_manager.py |
| `MAX_AVG_CORRELATION` | 0.75 | risk_manager.py |
| `DEFAULT_BLOCK_DAYS` | 2 | earnings.py |
| `NEAR_MARKET_BUFFER` | 0.003 | pricing.py |
| `MIN_STOP_DISTANCE_PCT` | 1.5 | pricing.py |
| `REENTRY_COOLDOWN_HOURS` / `COOLDOWN_OVERRIDE_MIN_HOURS` / `COOLDOWN_RECOVERY_PCT` | 72 / 24 / 1.0 | cooldown.py |

## What This Prevents

| Scenario | Protection |
|----------|-----------|
| Stock drops 15% overnight | Broker stop-limit fires at −12% |
| Bad earnings surprise | Earnings blackout |
| Market-wide crash | Insurance halves exposure; drawdown breaker halts entries |
| Sector rotation | 50% sector cap; correlation cap |
| Bot offline | Stops live on Alpaca |
| Overtrading | 3 slots, cash reserve, 72 h cooldown after a stop-out |
| Stop-limit gap failure | Gap-down protection |
| Broker glitch (split, phantom equity) | Corporate-actions check; suspect-value guard |
| Failed exit leaves a position bare | Settled close restores the stop |
| Stale plan | Plan rebuilt before every execute; orphan close for anything without an item |
