# Data Schemas

## 0. Enhanced Data Bundle (`data_fetcher.py` output)

The data bundle now includes technical indicators, market context, and earnings:

```json
{
  "generated_at": "2026-03-29T20:00:00Z",
  "market_context": {
    "market_regime": "bullish",
    "vix": { "level": 16.5, "classification": "normal" },
    "treasury": { "yield_10y": 4.25, "yield_2y": 3.95 },
    "spy": {
      "return_1d": 0.3, "return_5d": 1.2, "return_20d": 2.8,
      "indicators": { "rsi_14": 55.2, "...": "..." }
    },
    "qqq": { "...": "..." },
    "sector_rotation": {
      "performance_5d": { "Technology": 1.5, "Healthcare": -0.3, "..." : "..." },
      "strongest": [["Technology", 1.5], ["Financials", 1.2]],
      "weakest": [["Utilities", -1.1], ["Real Estate", -0.8]]
    }
  },
  "stocks": {
    "AAPL": {
      "ohlcv_recent": [ "... last 5 bars ..." ],
      "technical_indicators": {
        "rsi_14": 42.5,
        "macd": { "macd_line": 0.85, "signal_line": 0.62, "histogram": 0.23 },
        "bollinger": { "upper": 192.5, "middle": 186.8, "lower": 181.1 },
        "atr_14": 3.25,
        "price_vs_sma": {
          "current_price": 185.5, "sma_20": 186.8, "sma_50": 183.2, "sma_200": 178.5,
          "above_sma_50": true, "above_sma_200": true, "golden_cross": true
        },
        "volume": { "avg_volume_5d": 52000000, "avg_volume_20d": 48000000, "volume_ratio_5d_20d": 1.08 }
      },
      "atr_14": 3.25,
      "news": [ "..." ],
      "sec_filings": [ "..." ],
      "earnings": {
        "next_earnings_date": "2026-04-25",
        "days_until_earnings": 27,
        "is_blocked": false
      }
    }
  }
}
```

---

## 1. Watchlist Configuration (`data/watchlist.json`)

```json
{
  "watchlist": ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "BRK.B", "LLY", "JPM"],
  "settings": {
    "risk_per_trade": 0.10,
    "trading_mode": "paper",
    "stop_loss_pct": 0.05
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `watchlist` | string[] | Ticker symbols to track |
| `settings.risk_per_trade` | float | Max % of portfolio per position (0.10 = 10%) |
| `settings.trading_mode` | string | "paper" or "live" |
| `settings.stop_loss_pct` | float | Stop-loss % below entry (0.05 = 5%) |

---

## 2. Data Bundle (`data_fetcher.py` output)

```json
{
  "generated_at": "2026-03-29T20:00:00Z",
  "stocks": {
    "AAPL": {
      "ohlcv": [
        {
          "date": "2026-03-28",
          "open": 185.00,
          "high": 187.50,
          "low": 184.20,
          "close": 186.80,
          "volume": 52000000
        }
      ],
      "news": [
        {
          "title": "Apple Reports Strong Q1 Services Revenue",
          "snippet": "Apple's services segment grew 18% year-over-year...",
          "published_at": "2026-03-27T14:30:00Z",
          "source": "Reuters"
        }
      ],
      "sec_filings": [
        {
          "form_type": "8-K",
          "filed_at": "2026-03-28T16:00:00Z",
          "description": "Results of Operations and Financial Condition",
          "url": "https://www.sec.gov/..."
        }
      ]
    }
  }
}
```

---

## 3. Weekly Thesis (`state/weekly_thesis.json`)

```json
{
  "generated_at": "2026-03-29T20:00:00Z",
  "expires_at": "2026-04-12T20:00:00Z",
  "theses": [
    {
      "ticker": "AAPL",
      "thesis": "BULLISH",
      "confidence": 0.78,
      "target_entry_price": 185.50,
      "stop_loss_price": 176.23,
      "take_profit_price": 198.00,
      "thesis_breach_condition": "CEO departure or revenue guidance cut >10%",
      "reasoning": "Strong iPhone 16 cycle, services revenue acceleration..."
    }
  ]
}
```

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `thesis` | string | BULLISH / BEARISH / NEUTRAL | Weekly directional call |
| `confidence` | float | 0.0 - 1.0 | AI confidence level |
| `target_entry_price` | float / null | | Limit order price for entry (null if not BULLISH) |
| `stop_loss_price` | float / null | | Native broker stop-loss price (null if not BULLISH) |
| `take_profit_price` | float / null | | Broker-side take-profit limit (null if no clear catalyst) |
| `thesis_breach_condition` | string | | Event that invalidates thesis |
| `reasoning` | string | | Full AI reasoning text |

---

## 4. Sentry Signal (`daily_sentry.py` output)

```json
{
  "generated_at": "2026-03-29T09:00:00Z",
  "run_type": "pre_market",
  "signals": [
    {
      "ticker": "AAPL",
      "signal": "CONTINUE",
      "conflicting_headlines": [],
      "reasoning": "No material news contradicting bullish thesis"
    }
  ]
}
```

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `signal` | string | CONTINUE / ABORT | Whether to proceed with thesis |
| `conflicting_headlines` | string[] | | Headlines that triggered ABORT |

---

## 5. Portfolio State (`state/portfolio.json`)

```json
{
  "last_updated": "2026-03-29T15:30:00Z",
  "cash_balance": 100000.00,
  "positions": [
    {
      "ticker": "AAPL",
      "shares": 50,
      "entry_price": 185.50,
      "entry_date": "2026-03-24",
      "current_price": 186.80,
      "stop_loss_price": 176.23,
      "unrealized_pnl": 65.00
    }
  ]
}
```

---

## 6. Trade Log (`state/trade_log.json`)

```json
{
  "trades": [
    {
      "id": "trade_001",
      "ticker": "AAPL",
      "action": "BUY",
      "shares": 50,
      "price": 185.50,
      "total_value": 9275.00,
      "timestamp": "2026-03-24T09:35:00Z",
      "trigger": "weekly_thesis",
      "thesis_id": "thesis_2026_w13",
      "reasoning": "Bullish thesis with 78% confidence, entry at target price"
    }
  ]
}
```

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `action` | string | BUY / SELL | Trade direction |
| `trigger` | string | weekly_thesis / sentry_abort / stop_loss | What triggered the trade |
| `confidence` | float / null | 0.0 - 1.0 | AI confidence (BUY trades only) |
| `stop_loss_price` | float / null | | Broker stop-loss price (BUY trades only) |
| `take_profit_price` | float / null | | Broker take-profit price (BUY trades only) |
| `risk_flags` | string[] | | Warnings from risk gates |
| `gate_results` | object / null | | Per-gate pass/fail results (see below) |
| `context` | object / null | | Market/technical snapshot at trade time (see below) |

### Gate Results Object

Each key is a gate name (`confidence`, `earnings`, `drawdown`, `cash_reserve`, `overlay_cap`, `position_size`, `sector_exposure`, `macro_blackout`, `correlation`). Min-notional (dust) blocks report under `position_size`; suspect broker-data blocks report under `drawdown` (Decision 054):

```json
{
  "confidence": { "passed": true, "detail": "Confidence 0.78 >= 0.70" },
  "earnings": { "passed": true, "detail": "Not in earnings blackout" },
  "drawdown": { "passed": true, "detail": "Drawdown 2.1% within limit" },
  "cash_reserve": { "passed": true, "detail": "$68,000 available after reserve" },
  "position_size": { "passed": true, "detail": "53 shares (9.8% of portfolio)" },
  "sector_exposure": { "passed": true, "detail": "Sector at 15.2%" }
}
```

### Trade Context Object

```json
{
  "market_regime": "bullish",
  "vix_level": 16.5,
  "vix_classification": "normal",
  "spy_return_1d": 0.3,
  "technicals": {
    "rsi_14": 42.5,
    "macd_histogram": 0.23,
    "atr_14": 3.25,
    "price_vs_sma_50": "above",
    "price_vs_sma_200": "above"
  },
  "sentry_signal": "CONTINUE",
  "sentry_reasoning": "No material news contradicting thesis",
  "recent_news": ["Apple Reports Strong Q1...", "iPhone 16 demand..."],
  "earnings_days_away": 27,
  "sector": "Technology"
}
```

---

## 7. Near Misses (`state/near_misses.json`)

Trades that were blocked by 2 or fewer risk gates. Helps identify opportunities
that were close to execution.

```json
{
  "near_misses": [
    {
      "id": "nm_abc123",
      "timestamp": "2026-03-29T14:05:00Z",
      "ticker": "AAPL",
      "confidence": 0.78,
      "thesis": "BULLISH",
      "target_entry_price": 185.50,
      "stop_loss_price": 176.23,
      "take_profit_price": 198.00,
      "reasoning": "Strong iPhone cycle...",
      "failed_gates": ["earnings"],
      "gate_results": { "...same structure as above..." },
      "total_gates_failed": 1,
      "context": { "...same structure as trade context..." }
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `failed_gates` | string[] | Names of gates that blocked the trade |
| `gate_results` | object | Per-gate pass/fail with detail strings |
| `total_gates_failed` | int | 1 or 2 (only recorded if <= 2) |
| `context` | object | Market/technical snapshot at time of near miss |

---

## 8. Operational Costs (`state/costs.json`)

Tracks per-API-call token usage and estimated costs for AI model inference.

```json
{
  "costs": [
    {
      "id": "cost_abc12345",
      "timestamp": "2026-03-29T20:05:00Z",
      "service": "claude",
      "model": "claude-opus-4-8",
      "description": "Weekly Pass 1: AAPL",
      "input_tokens": 4800,
      "output_tokens": 1200,
      "estimated_cost_usd": 0.03240,
      "run_type": "weekly_analyst"
    },
    {
      "id": "cost_def67890",
      "timestamp": "2026-03-30T13:00:00Z",
      "service": "gemini",
      "model": "gemini-3.1-flash-lite",
      "description": "Daily sentry: AAPL",
      "input_tokens": 2100,
      "output_tokens": 350,
      "estimated_cost_usd": 0.00035,
      "run_type": "daily_sentry"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `service` | string | "claude" or "gemini" |
| `model` | string | Model identifier used for the call |
| `description` | string | Human-readable label for the call |
| `input_tokens` | int | Prompt/input token count |
| `output_tokens` | int | Completion/output token count |
| `estimated_cost_usd` | float | Estimated cost based on published pricing |
| `run_type` | string | "weekly_analyst" or "daily_sentry" |

## 9. Benchmark Metrics (`state/benchmark_metrics.json`)

Risk-adjusted performance of the strategy vs SPY. Written by `benchmark.py`
(refreshed by the `daily_summary` job; recomputable via the `benchmark` CLI or
`/api/benchmark/refresh`). Computed from the Alpaca portfolio-equity history
aligned to SPY daily closes by trading date.

```json
{
  "insufficient_data": false,
  "n_days": 13,
  "beta": 0.841,
  "alpha_annual_pct": 32.46,
  "sharpe_strategy": 0.46,
  "sharpe_spy": -1.44,
  "info_ratio": 3.97,
  "correlation": 0.883,
  "r_squared": 0.78,
  "vol_strategy_annual_pct": 18.72,
  "vol_spy_annual_pct": 19.66,
  "total_return_strategy_pct": 0.36,
  "total_return_spy_pct": -1.54,
  "excess_return_pct": 1.9,
  "up_capture": 0.98,
  "down_capture": 0.71,
  "up_days": 7,
  "down_days": 6,
  "max_drawdown_strategy_pct": -3.68,
  "max_drawdown_spy_pct": -4.46,
  "rf_annual_pct": 0.0,
  "window_start": "2026-06-01",
  "window_end": "2026-06-18",
  "since": "2026-06-01",
  "lookback_days": null,
  "computed_at": "2026-06-22T16:30:00Z",
  "verdict": "Adding value — positive alpha AND higher risk-adjusted return than SPY."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `n_days` | int | Number of daily returns in the window |
| `beta` | float\|null | Realized exposure to SPY (cov/var of daily returns); null if SPY had zero variance |
| `alpha_annual_pct` | float\|null | Jensen's alpha, annualized — return after paying for beta. Magnitude is noisy on short windows |
| `sharpe_strategy` / `sharpe_spy` | float\|null | Annualized return / volatility, strategy vs SPY |
| `info_ratio` | float\|null | Active return ÷ tracking error (annualized) |
| `up_capture` / `down_capture` | float\|null | Avg strategy move ÷ avg SPY move on SPY-up / SPY-down days; `down < up` is defensive |
| `max_drawdown_strategy_pct` / `max_drawdown_spy_pct` | float | Largest peak-to-trough decline over the window (≤ 0) |
| `window_start` / `window_end` | string | First / last aligned trading date |
| `since` / `lookback_days` | string\|null / int\|null | Window anchor (one or the other) |
| `verdict` | string | One-line plain-English classification |
