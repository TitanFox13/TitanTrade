# Data Schemas

## 1. Watchlist (`data/watchlist.json`)

```json
{
  "watchlist": ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLB", "XLRE", "XLP", "XLU", "XLC"],
  "shadow_watchlist": ["CRWD", "ANET", "LLY", "DXCM", "HCA", "JPM", "GS", "DVN", "WMT", "URI", "GE", "DASH", "DECK", "FCX", "EQIX"],
  "settings": {
    "trading_mode": "paper",
    "mechanical": {
      "design": "070",
      "dip_pct": 0.08, "dip_lookback_days": 90, "trend_sma_days": 150,
      "max_hold_days": 60, "tp_pct": 0.2, "stop_pct": 0.12,
      "slot_pct": 0.25, "max_slots": 3,
      "insurance_sma_days": 200, "insurance_breadth": 0.5, "insurance_scale": 0.5,
      "momentum_ticker": "SPMO", "momentum_weight": 0.6,
      "shock_drop_pct": 0.07, "shock_lookback_days": 10, "shock_hold_days": 20, "shock_scale": 0.5
    }
  }
}
```

`shadow_watchlist` (Decision 070) is fetched into the bundle, curated by the monthly job and run by `backtest-mech --shadow`, never traded; `design` re-stamps the benchmark window when it changes (070 since 2026-10-29: the 11 sector ETFs as `watchlist`, the 15 names as the shadow list). `settings.mechanical` may carry any of `config.MECHANICAL_FIELDS` (the keys above plus `sector_etfs`, `core_ticker`, `core_rebalance_band_pct`, `cash_ticker` — the T-bill leg, Decision 071, `""` = off); missing keys use the `TradingSettings` defaults. `momentum_weight` sizes the SPMO sleeve and, through `TradingSettings.overlay_slot_pct` = `slot_pct × (1 − momentum_weight)`, the dip slots; `0` is the dip-only book. `TRADING_MODE` in the environment overrides `trading_mode`. `PUT /api/watchlist` rewrites `watchlist` and keeps `settings`.

## 2. Schedule (`data/schedule.json`)

`{"timezone": "America/New_York", "jobs": [{"id", "name", "command", "cron": {day_of_week?, day?, hour, minute}, "enabled"}]}`. Commands: `full`, `fetch`, `signals`, `execute`, `gapcheck`, `daily_summary`, `curate`.

## 3. Data Bundle (`state/data_bundle.json`)

```json
{
  "generated_at": "2026-10-13T13:00:12+00:00",
  "market_context": {
    "generated_at": "…",
    "spy": {"close": 778.1, "return_1d": 0.3, "return_5d": 1.2, "return_20d": 2.8, "closes": [741.2, "…", 778.1]},
    "breadth": {"sma_days": 200, "sectors_above": 5, "sectors_total": 11, "pct": 0.4545,
                "flags": {"XLK": true, "XLE": false, "…": null},
                "spy_close": 778.1, "spy_sma": 741.2, "spy_above_sma": true}
  },
  "economic_calendar": [{"date": "2026-10-15T12:30:00+00:00", "event": "CPI", "…": "…"}],
  "correlation_matrix": {"AAPL": {"MSFT": 0.71}},
  "stocks": {
    "DASH": {
      "ohlcv_recent": [{"date": "2026-10-12", "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0}],
      "atr_14": 7.85,
      "signal_inputs": {"close": 232.1, "high_lookback": 283.0, "sma_trend": 225.4, "lookback_days": 90, "trend_sma_days": 150},
      "earnings": {"next_earnings_date": "2026-11-05", "days_until_earnings": 23, "is_blocked": false},
      "sector": "Communication Services"
    }
  }
}
```

A stock that failed to fetch carries `"error"` and empty inputs; the plan treats it as no signal.

## 4. Strategy (`state/strategy.json`)

`{"strategy": "mechanical", "started_at": "2026-10-13T12:43:24+00:00", "decision": "061", "window_started_at": "2026-10-28T13:04:00+00:00", "design": "070", "sleeve": {"ticker": "SPMO", "weight": 0.6}, "dip_universe": ["XLK", "…"]}` — `started_at` is written once by the first signals run and never moves: a position whose opening BUY predates it is legacy (no plan item, sold by the orphan close); a mechanical position whose name left the watchlist keeps its HOLD item (070). `window_started_at`, `design`, `sleeve` and `dip_universe` are re-stamped whenever the configured `settings.mechanical.design` differs from the stamped one (first stamped when `momentum_weight > 0`); `mechanical.benchmark_window_start()` returns it (else `started_at`) as the benchmark's clean window.

## 5. Plan (`state/plan.json`)

```json
{
  "generated_at": "2026-10-13T14:15:03+00:00",
  "strategy": "mechanical",
  "started_at": "2026-10-13T12:43:24+00:00",
  "params": {"dip_pct": 0.08, "dip_lookback_days": 90, "trend_sma_days": 150, "slot_pct": 0.25, "max_slots": 3,
             "tp_pct": 0.2, "stop_pct": 0.12, "max_hold_days": 60,
             "insurance_sma_days": 200, "insurance_breadth": 0.5, "insurance_scale": 0.5,
             "momentum_ticker": "SPMO", "momentum_weight": 0.6, "shock_drop_pct": 0.07, "shock_lookback_days": 10, "shock_hold_days": 20, "shock_scale": 0.5},
  "stale_inputs": false,
  "insurance": {"risk_off": false, "spy_above_sma": true, "sector_breadth": 0.4545, "exposure_scale": 1.0},
  "shock": {"active": false, "sessions_left": 0, "worst_drop": -0.021, "exposure_scale": 1.0, "drop_pct": 0.07, "lookback_days": 10, "hold_days": 20},
  "exposure_scale": 1.0,
  "sleeve": {"ticker": "SPMO", "weight": 0.6, "target_pct": 0.57},
  "breadth": {"sma_days": 200, "sectors_above": 5, "sectors_total": 11, "pct": 0.4545, "spy_close": 778.1, "spy_sma": 741.2, "spy_above_sma": true},
  "items": [
    {"ticker": "DASH", "action": "HOLD", "sector": "Communication Services", "entry_price": 192.9,
     "stop_price": 169.75, "target_price": 231.48, "opened_at": "2026-10-13T14:16:40+00:00",
     "reason": "held since 2026-10-13; stop 169.75, target 231.48, limit 60 trading days"},
    {"ticker": "URI", "action": "NEW", "sector": "Industrials", "entry_price": 1068.4,
     "stop_price": 940.19, "target_price": 1282.08, "dip_pct": 0.112,
     "reason": "11.2% below its 90-day high, above its 150-day SMA"}
  ],
  "watch": [{"ticker": "GS", "sector": "Financials", "dip_pct": 0.09, "above_trend": true, "reason": "signal, no free slot"}],
  "candidates": [{"ticker": "URI", "dip_pct": 0.112, "chosen": true}, {"ticker": "GS", "dip_pct": 0.09, "chosen": false}],
  "held": ["DASH", "JPM"],
  "legacy_to_close": [],
  "pending_buys": [],
  "free_slots": 1,
  "new_signals": 1
}
```

| Field | Meaning |
|-------|---------|
| `items[].action` | `NEW` — enter this run (entry = last close; the executor re-prices at the live mark × 1.003 and recomputes stop / target); `HOLD` — held mechanical position (stop / target from the opening BUY in the trade log) |
| `watch[]` | Names with a dip signal that were not taken ("no free slot — N of 3 slots held or pending", "deeper dips took the free slot(s)", risk-off) and names not in an uptrend, each with the reason |
| `candidates[]` | Every name with a signal, ranked deepest dip first, `chosen` for the ones that became NEW items |
| `stale_inputs` | True when the bundle's lookback / SMA lengths differ from `params` — re-run `fetch` |
| `insurance.exposure_scale` | 1.0, or `insurance_scale` while `risk_off` |
| `shock` | `signals.shock_state` over `market_context.spy.closes`: `active` while a −`drop_pct` move over `lookback_days` sessions happened within the last `hold_days`; `sessions_left` until it expires; `worst_drop` the worst such return in the window |
| `exposure_scale` | `min(insurance.exposure_scale, shock.exposure_scale)` — what both core legs scale by |
| `sleeve.target_pct` | `exposure_scale × 0.95 × momentum_weight` — the momentum ETF's share of equity this run |
| `cash_leg` | `{ticker, target_pct}` with `target_pct = (1 − exposure_scale) × 0.95` when `cash_ticker` is set (071), else `null` |
| `free_slots` | `max_slots − held − pending_buys` |

## 6. Trade Log (`state/trade_log.json`)

```json
{"trades": [{
  "id": "trade_3f9a1c2e", "ticker": "URI", "action": "BUY", "shares": 26.0, "price": 1068.4, "total_value": 27778.4,
  "timestamp": "2026-10-13T14:16:41+00:00", "trigger": "entry", "reasoning": "11.2% below its 90-day high, above its 150-day SMA",
  "stop_price": 940.19, "target_price": 1282.08, "order_type": "bracket", "fill_price": 1065.0, "dip_pct": 0.112,
  "risk_flags": [], "gate_results": {"earnings": {"passed": true, "detail": "…"}, "…": "…"},
  "context": {"close": 1065.0, "high_lookback": 1199.5, "sma_trend": 1010.2, "atr_14": 24.1,
              "earnings_days_away": 12, "sector": "Industrials", "spy_return_5d": 1.2, "sector_breadth": 0.4545}
}]}
```

| `trigger` | Written by |
|-----------|-----------|
| `entry` (records before Decision 064 may carry `bracket_resubmission`) | entries (BUY); `price` is the bracket limit (live × 1.003), `fill_price` the average fill when the entry filled inside the poll window, else `null` (069) |
| `target`, `holding_limit` | executor via the settled close (SELL) |
| `orphan_close`, `gap_down_protection` | protection (SELL) |
| `core_rebalance` | core_allocation (BUY / SELL of SPY) |

Records written before Decision 063 carry `stop_loss_price` / `take_profit_price`; readers (`trade_state.position_entry_stop`, `mechanical._hold_item`) accept both spellings. Past 500 records the oldest are moved to `state/archive/trade_log.<timestamp>.json`.

`gate_results` keys: `earnings`, `drawdown`, `cash_reserve`, `overlay_cap`, `position_size`, `sector_exposure`, `macro_blackout`, `correlation`, each `{"passed": bool, "detail": str}`.

## 7. Near Misses (`state/near_misses.json`)

Entries blocked by ≤ 2 gates: `{"near_misses": [{"id": "nm_…", "timestamp", "ticker", "dip_pct", "entry_price", "stop_price", "target_price", "reason", "failed_gates": ["cash_reserve"], "gate_results": {…}, "total_gates_failed": 1, "context": {…same as the trade context…}}]}`. Archived past 200.

## 8. Cooldowns (`state/abort_cooldown.json`)

`{"DVN": {"aborted_at": "<fill time ISO>", "reason": "stop-loss exit", "exit_price": 43.42}}` — stamped by the stop-out scan at the fill time (idempotent); expires after 72 h; the override needs ≥ 24 h and a price ≥ 1% above `exit_price`.

## 9. Costs (`state/costs.json`)

`{"costs": [{"id": "cost_…", "timestamp", "service": "claude", "model": "claude-opus-4-8", "description": "Universe review", "input_tokens", "output_tokens", "estimated_cost_usd", "run_type": "curator"}]}`.

## 10. Curation (`state/universe_proposal.json`, `state/post_mortem.json`)

`{"generated_at", "watchlist": [...], "proposal": {"remove": [{"ticker", "reason"}], "add": [{"ticker", "sector", "reason"}], "notes"}, "raw", "status": "advisory — apply through the watchlist editor"}` and `{"generated_at", "review": {"summary", "observations": [...]}, "raw"}`.

## 11. Benchmark Metrics (`state/benchmark_metrics.json`)

```json
{
  "insufficient_data": false, "n_days": 13, "beta": 0.841, "alpha_annual_pct": 32.46,
  "sharpe_strategy": 0.46, "sharpe_spy": -1.44, "info_ratio": 3.97, "tracking_error_annual_pct": 9.1, "excess_annual_pct": 4.0, "correlation": 0.883, "r_squared": 0.78,
  "vol_strategy_annual_pct": 18.72, "vol_spy_annual_pct": 19.66,
  "total_return_strategy_pct": 0.36, "total_return_spy_pct": -1.54, "excess_return_pct": 1.9,
  "up_capture": 0.98, "down_capture": 0.71, "up_days": 7, "down_days": 6,
  "max_drawdown_strategy_pct": -3.68, "max_drawdown_spy_pct": -4.46, "rf_annual_pct": 0.0,
  "window_start": "2026-06-01", "window_end": "2026-06-18", "since": "2026-06-01", "lookback_days": null,
  "computed_at": "2026-06-22T16:30:00Z", "verdict": "Adding value — positive alpha AND higher risk-adjusted return than SPY."
}
```

`verdict` reads "Too few trading days (N of 20)…" and the daily-summary line shows returns only while `n_days` < 20 (Decision 065); while `n_days` < 756 (3 years) it reads "Too short to judge the return (N of 756 trading days): excess ±x pp/yr, 90% band ±y…" and the summary line shows `excess_annual_pct` ± the band (1.645 × `tracking_error_annual_pct` / √years) instead of alpha (Decision 069). Beta = cov / var of daily returns vs SPY; alpha = Jensen's, annualized; `down_capture < up_capture` is the defensive signature; drawdowns ≤ 0. Equity comes from Alpaca's portfolio history (the just-closed session appended from the 15Min series), SPY from SIP daily closes, aligned by trading date.

## 11b. Fill Ledger (`state/fill_ledger.json`, Decision 069)

```json
{"rows": [{"trade_id": "trade_3f9a1c2e", "ticker": "URI", "date": "2026-10-13", "fill_price": 1065.0, "fill_known": true,
           "backtest_close": 1060.0, "gap_pct": 0.472}]}
```

One row per BUY entry, appended by the daily summary once the session's SIP bar is published (entries up to 10 days old are retried; rows are never edited). `date` is the Eastern session of the order; `fill_price` is the trade's `fill_price` when captured (`fill_known` true), else the bracket limit; `backtest_close` is that session's close, the price the backtest fills at; `gap_pct` = fill / close − 1 in %, positive = paid more. `GET /api/fill-ledger` adds `summary` (`n`, `median_gap_pct`, `mean_gap_pct`, `worst_gap_pct`, `fills_known`).

## 11c. Curator Ledger (`state/curator_ledger.json`, Decision 082)

```json
{"rows": [{"proposal_id": "2026-11-01T19:00:12+00:00", "date": "2026-11-01", "list": "shadow_watchlist",
           "members": ["CRWD", "…"], "adds": ["MSFT"], "removes": ["DVN"],
           "outcomes": {"21": {"date": "2026-12-02", "spy": 1.8, "list_ew": 2.1, "adds": {"MSFT": 3.4}, "removes": {"DVN": -0.7}}}}]}
```

One row per monthly proposal (an empty proposal too), appended by `run_universe_review`. `outcomes` is keyed by the horizon in sessions (21 / 63 / 126 / 252): each holds the session the horizon fell on and the total return in % from the first close after the proposal for SPY, the equal weight of `members` and every addition and removal (`null` for a name without bars); filled by the daily summary once the session's SIP bar is published, never edited after. `GET /api/curator-ledger` adds `summary` (`proposals`, `additions`, `removals`, per horizon the additions-minus-list and list-minus-removals medians in pp with the hit rate and its chance by luck, `verdict` — "No reading under 12 proposals" until then).

## 12. Other

- `state/portfolio.json`: `{"last_updated", "portfolio_value", "cash", "positions": [{"symbol", "qty", "avg_entry_price", "current_price", "market_value", "unrealized_plpc"}]}` — written at the end of every execute run; the daily summary and `/api/portfolio` (when Alpaca is unreachable) read it.
- `state/peak_portfolio.json`: `{"peak_value": float, "updated_at"}` — never written with a value > 150% of the previous peak (suspect-value guard).
- `state/alert_state.json`: dedup timestamps for the observability alerts and `stuck_in_cash_since`.
- `state/backtest_mechanical.json`: `{"summary", "trades", "walk_forward"?}` from `backtest-mech`.
- `state/sector_cache.json`: ticker → sector (Finnhub), refreshed when a name is missing.
