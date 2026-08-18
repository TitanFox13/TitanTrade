# API Reference

## External APIs Used

### 1. Market Data — Alpaca + FRED + Finnhub (Decision 040)

The former FMP dependency (€25/mo) was replaced with free sources behind the
`market_data.py` facade. `DATA_PROVIDER=fmp` (+ a valid `FMP_KEY`) reverts to
the retained FMP provider (`data_providers/fmp.py`) with no code change.

#### Alpaca Data API
**Purpose**: OHLCV bars, latest quotes, daily change %, news
**Base URL**: `https://data.alpaca.markets` (IEX feed, free tier; same keys as trading)

| Endpoint | Purpose |
|----------|---------|
| `/v2/stocks/{symbol}/bars` | OHLCV daily candles (250-day history) |
| `/v2/stocks/{symbol}/quotes/latest` | Current price quote |
| `/v1beta1/news` | News headlines (cursor-paginated, deduplicated) |

#### FRED (St. Louis Fed)
**Purpose**: VIX, treasury yields, economic-release calendar
**Base URL**: `https://api.stlouisfed.org/fred`
**Auth**: free `FRED_KEY` as query parameter

| Endpoint | Purpose |
|----------|---------|
| `/series/observations` | VIX level, 10Y/2Y treasury yields |
| `/release/dates?release_id=…` | Upcoming CPI (10), jobs (50), PPI (46), GDP (53), PCE (54), retail (17) release dates |

FOMC meeting dates are not a FRED release — they live in `data/fomc_dates.json`
(verified against federalreserve.gov).

#### Finnhub
**Purpose**: per-ticker earnings dates, analyst recommendation trend, sector
**Base URL**: `https://finnhub.io/api/v1`
**Auth**: free `FINNHUB_KEY` as query parameter

| Endpoint | Purpose |
|----------|---------|
| `/calendar/earnings` | Upcoming earnings dates (blackout gate) |
| `/stock/recommendation` | Analyst recommendation mix (strong-buy…strong-sell) |
| `/stock/profile2` | Company sector |

All market-data functions fail open (`[]`/`None`/`{}`) on a missing key or
error — the gates that consume them skip rather than block. Price-target
consensus was dropped with FMP (no free source).
---

### 2. SEC EDGAR (free)
**Purpose**: SEC filing monitoring (8-K, 10-Q, 10-K, Form 4)
**Base URLs**:
  - `https://www.sec.gov/files/company_tickers.json` — ticker→CIK lookup
  - `https://data.sec.gov/submissions/CIK{cik}.json` — per-company filings
**Auth**: None. A descriptive `User-Agent` header with contact email is required
(set `SEC_USER_AGENT` env var). Rate limit: 10 req/sec globally.

#### Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `/files/company_tickers.json` | Map ~10k US-listed tickers to CIKs (cached locally) |
| `/submissions/CIK{cik}.json` | All recent filings for a company, newest-first |

#### Example: Fetch GS filings
```
GET https://data.sec.gov/submissions/CIK0000886982.json
Headers: User-Agent: TitanTrade/1.0 (contact@example.com)

Response includes filings.recent with parallel arrays:
  form, filingDate, accessionNumber, primaryDocument, primaryDocDescription
```

#### Filing URL Construction
```
https://www.sec.gov/Archives/edgar/data/{cik_unpadded}/{accession_no_no_dashes}/{primary_doc}
```

---

### 3. Alpaca Markets
**Purpose**: Trade execution (paper and live)
**Base URL (Paper)**: `https://paper-api.alpaca.markets`
**Base URL (Live)**: `https://api.alpaca.markets`
**Auth**: Headers `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY`

#### Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v2/account` | GET | Account info and buying power |
| `/v2/positions` | GET | Current open positions |
| `/v2/positions/{symbol}` | GET | Position for specific stock |
| `/v2/orders` | POST | Place new order |
| `/v2/orders` | GET | List open orders |
| `/v2/orders/{id}` | DELETE | Cancel an order |

#### Example: Place Limit Buy
```
POST /v2/orders
{
  "symbol": "AAPL",
  "qty": 10,
  "side": "buy",
  "type": "limit",
  "limit_price": 185.50,
  "time_in_force": "day"
}
```

---

### 4. Anthropic Claude API
**Purpose**: Weekly deep fundamental analysis
**Base URL**: `https://api.anthropic.com/v1`
**Auth**: Header `x-api-key: {CLAUDE_KEY}`

#### Endpoint Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/messages` | POST | Send analysis prompt, receive thesis |

#### Configuration
- Model: `claude-opus-4-8` (default) or configurable via `CLAUDE_MODEL` env var (Decision 050 — the analyst is the alpha source, so it runs the most capable model)
- Adaptive thinking enabled; no `temperature` (Opus 4.8 rejects sampling params)
- Max tokens: 16000 (headroom for thinking tokens)
- Refusal stop-reason handling + thinking-aware text extraction

---

### 5. Google Gemini API
**Purpose**: Daily fast sentiment conflict detection
**Base URL**: `https://generativelanguage.googleapis.com/v1beta`
**Auth**: API key as query parameter `?key={GEMINI_KEY}`

#### Endpoint Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/models/{model}:generateContent` | POST | Sentiment classification |

#### Configuration
- Model: `gemini-3.1-flash-lite` (default; `GEMINI_MODEL` env override)
- 503-fallback chain (Decision 041): `gemini-2.5-flash` → `gemini-2.5-flash-lite` → `gemini-flash-latest`
- Structured output (`responseMimeType: application/json` + `responseSchema`), thinking budget 0 (Decision 039)
- Max tokens: 2048

---

## TitanTrade Internal API (FastAPI)

The backend exposes these endpoints at `{base_url}/api/`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check (returns `{"status": "ok"}`) |
| `/api/portfolio` | GET | Current portfolio holdings |
| `/api/trades` | GET | Trade history log |
| `/api/theses` | GET | Weekly analysis theses |
| `/api/sentry` | GET | Daily sentry signals |
| `/api/near-misses` | GET | Trades blocked by 1-2 risk gates |
| `/api/costs` | GET | API call costs and token usage |
| `/api/trailing-stops` | GET | Trailing stop state |
| `/api/pricecheck` | GET | Intraday price check signals |
| `/api/benchmark` | GET | Performance vs SPY: beta, alpha, Sharpe, capture ratios (last computed) |
| `/api/benchmark/refresh` | GET | Recompute benchmark metrics live (`?days=N`, `?since=YYYY-MM-DD`) |
| `/api/backtest-results` | GET | Latest backtest results |
| `/api/watchlist` | GET | Current watchlist |
| `/api/watchlist` | PUT | Update watchlist tickers |
| `/api/settings` | GET | Trading mode + whether live keys are configured |
| `/api/settings/mode` | PUT | Switch between `paper` and `live` trading |
| `/api/actions/analyze` | POST | Trigger weekly analysis (background job) |
| `/api/actions/download-history` | POST | Download OHLCV data (background job) |
| `/api/actions/backtest` | POST | Run backtest (background job) |
| `/api/jobs/{job_id}` | GET | Poll background job status |
| `/api/scheduler` | GET | List all scheduled jobs with status |
| `/api/scheduler/{job_id}/trigger` | POST | Manually trigger a scheduled job |
| `/api/scheduler/{job_id}/enabled` | PUT | Enable or disable a scheduled job |

## Internal Data Schemas

See `docs/data_schemas.md` for JSON schema definitions of all internal data structures.
