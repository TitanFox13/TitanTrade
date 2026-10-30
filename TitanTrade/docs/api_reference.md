# API Reference

## External APIs

### Alpaca Data API
**Purpose**: daily bars, latest quotes, corporate actions, news (curator)
**Base URL**: `https://data.alpaca.markets` (same keys as trading)

| Endpoint | Used for |
|----------|----------|
| `/v2/stocks/{symbol}/bars` | 250-day daily bars for the bundle (IEX feed); SIP for `download-history` and the benchmark's SPY series (must end ≥ 15 min in the past) |
| `/v2/stocks/{symbol}/quotes/latest` | Live price for entries, gap-down cross-check, core rebalance |
| `/v1beta1/corporate-actions` | Split check before a deep gap-down liquidation |
| `/v1beta1/news` | Headlines for the curator brief |

### FRED (St. Louis Fed)
**Purpose**: economic-release calendar for the macro gate. **Auth**: `FRED_KEY` query parameter.
`/release/dates?release_id=…` for CPI (10), jobs (50), PPI (46), GDP (53), PCE (54), retail (17). FOMC dates come from `data/fomc_dates.json`.

### Finnhub
**Purpose**: earnings dates (blackout gate), company sector, analyst recommendations (curator). **Auth**: `FINNHUB_KEY` query parameter.
`/calendar/earnings`, `/stock/profile2`, `/stock/recommendation`.

All market-data functions fail open (`[]` / `None` / `{}`) on a missing key or error; the gates that consume them skip rather than block.

### Alpaca Trading API
**Base URL**: `https://paper-api.alpaca.markets` (paper) / `https://api.alpaca.markets` (live). **Auth**: `APCA-API-KEY-ID` / `APCA-API-SECRET-KEY` headers.

| Endpoint | Method | Used for |
|----------|--------|----------|
| `/v2/account` | GET | Equity, cash, buying power |
| `/v2/positions`, `/v2/positions/{symbol}` | GET | Positions (incl. `unrealized_plpc` for the target exit) |
| `/v2/positions/{symbol}` | DELETE | Close at market (settled close) |
| `/v2/orders` | POST | Bracket entries, GTC stop-limits, market core trades |
| `/v2/orders?status=open` | GET | Open orders (the held stop leg of a bracket is **not** returned) |
| `/v2/orders?status=closed` | GET | Filled stops (cooldown scan) |
| `/v2/orders/{id}` | GET / DELETE | Poll a cancel to a terminal state; cancel |
| `/v2/clock` | GET | Market open check |
| `/v2/account/portfolio/history` | GET | Benchmark equity series (1D + 15Min) |

### Anthropic Claude
**Purpose**: the monthly universe proposal and post-mortem only. `POST https://api.anthropic.com/v1/messages`, header `x-api-key`. Model `claude-opus-4-8` (`CLAUDE_MODEL`), adaptive thinking, 16,000 max tokens, no sampling parameters. Every call is cost-logged to `state/costs.json`.

---

## TitanTrade HTTP API (FastAPI, `/api/`)

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/health` | GET | `{"status": "ok"}` |
| `/api/portfolio` | GET | Live account + positions from Alpaca |
| `/api/plan` | GET | `state/plan.json` — NEW / HOLD items, watch, candidates, insurance, shock, exposure scale, sleeve target, free slots (404 until the first signals run) |
| `/api/trades` | GET | `state/trade_log.json` |
| `/api/near-misses` | GET | `state/near_misses.json` |
| `/api/costs` | GET | `state/costs.json` |
| `/api/universe-proposal` | GET | The monthly Claude proposal (404 until the first `curate`) |
| `/api/post-mortem` | GET | The monthly post-mortem (404 until the first `curate`) |
| `/api/benchmark` | GET | Last computed metrics vs SPY |
| `/api/benchmark/refresh` | GET | Recompute now (`?days=N` or `?since=YYYY-MM-DD`) |
| `/api/fill-ledger` | GET | `{summary: {n, median_gap_pct, mean_gap_pct, worst_gap_pct, fills_known}, rows: [...]}` from `state/fill_ledger.json` (Decision 069) |
| `/api/curator-ledger` | GET | `{summary: {proposals, additions, removals, horizons: {"21": {additions: {n, median_vs_list_pp, beat_list, p_luck}, removals: {…}}, …}, verdict}, rows: [...]}` from `state/curator_ledger.json` (Decision 082) |
| `/api/settings` | GET | `{trading_mode, mechanical, live_keys_configured}` |
| `/api/settings/mode` | PUT | `{"trading_mode": "paper" \| "live"}`; 400 when live keys are missing |
| `/api/watchlist` | GET / PUT | `data/watchlist.json`; PUT body `{"watchlist": [...]}` (settings preserved) |
| `/api/scheduler` | GET | All jobs with status, next / last run |
| `/api/scheduler/{job_id}` | GET | One job + its run history (in-memory, per container) |
| `/api/scheduler/{job_id}/trigger` | POST | Run a job now (background) |
| `/api/scheduler/{job_id}/enabled` | PUT | `{"enabled": bool}` |

The API has no authentication of its own; it is reachable only through the Cloudflare tunnel at `https://trade.praguefun.cz`. Schemas of the files it serves: [data_schemas.md](data_schemas.md).
