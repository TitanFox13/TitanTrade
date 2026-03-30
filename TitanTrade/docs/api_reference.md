# API Reference

## External APIs Used

### 1. Financial Modeling Prep (FMP)
**Purpose**: Price data, news, market context, earnings, economic calendar
**Base URL**: `https://financialmodelingprep.com/stable`
**Auth**: API key as query parameter `?apikey={FMP_KEY}`

#### Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `/stable/historical-price-eod/full?symbol=X` | OHLCV daily candles |
| `/stable/news/stock?symbol=X` | News headlines |
| `/stable/quote?symbol=X` | Current price quote |
| `/stable/index-quote?symbol=^VIX` | VIX level |
| `/stable/profile?symbol=X` | Company profile (sector) |
| `/stable/treasury-rates` | 10Y and 2Y Treasury yields |
| `/stable/earnings-calendar` | Upcoming earnings dates |
| `/stable/economics-calendar` | Macro events (FOMC, CPI, etc.) |
| `/stable/grades?symbol=X` | Analyst upgrades/downgrades |
| `/stable/price-target-consensus?symbol=X` | Price target consensus |

#### Example: OHLCV Data
```
GET /stable/historical-price-eod/full?symbol=AAPL&from=2026-03-24&to=2026-03-29&apikey=xxx
```
Response: `[{ "date": "...", "open": ..., "high": ..., "low": ..., "close": ..., "volume": ... }]`

#### Example: News
```
GET /stable/news/stock?symbol=AAPL&limit=50&apikey=xxx
```
Response: `[{ "symbol": "AAPL", "title": "...", "text": "...", "publishedDate": "..." }]`

---

### 2. SEC-API.io
**Purpose**: Real-time SEC filing monitoring (8-K, 10-Q, 10-K)
**Base URL**: `https://efts.sec-api.io`
**Auth**: API key as query parameter `?token={SEC_API_KEY}`

#### Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `/v1/filings` | Full-text search of SEC filings |

#### Example: Recent 8-K Filings
```
POST https://efts.sec-api.io/v1/filings?token=xxx
Body: {
  "query": { "query_string": { "query": "ticker:AAPL AND formType:\"8-K\"" } },
  "from": "0",
  "size": "10",
  "sort": [{ "filedAt": { "order": "desc" } }]
}
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
- Model: `claude-sonnet-4-20250514` (default) or configurable via `CLAUDE_MODEL` env var
- Temperature: 0.3 (deterministic analysis)
- Max tokens: 4096 per stock analysis

---

### 5. Google Gemini API
**Purpose**: Daily fast sentiment conflict detection
**Base URL**: `https://generativelanguage.googleapis.com/v1beta`
**Auth**: API key as query parameter `?key={GEMINI_KEY}`

#### Endpoint Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/models/gemini-2.0-flash:generateContent` | POST | Sentiment classification |

#### Configuration
- Model: `gemini-2.0-flash`
- Temperature: 0.1 (highly deterministic for binary classification)
- Max tokens: 1024

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
