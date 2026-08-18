# Deployment Guide

## Local Development

### Prerequisites
- Python 3.12+
- uv (package manager)
- API keys for: Alpaca, Anthropic (Claude), Google (Gemini), FRED (free), Finnhub (free)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/your-username/TitanTrade.git
cd TitanTrade
```

2. Install dependencies:
```bash
uv sync
```

3. Create environment file:
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. Run modules individually:
```bash
# Fetch data
uv run python -m titantrade.data_fetcher

# Run weekly analysis
uv run python -m titantrade.weekly_analyst

# Run daily sentry
uv run python -m titantrade.daily_sentry

# Execute trades (paper mode)
uv run python -m titantrade.executor
```

---

## Server Deployment (Docker)

### Prerequisites
- Docker and Docker Compose installed on your server
- API keys for all services (see Environment Variables below)
- Cloudflare tunnel token (see `CLOUDFLARE_TUNNEL_TOKEN` in Environment Variables)

### Setup

1. Clone and navigate to the project:
```bash
cd /path/to/TitanTrade
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your API keys and CLOUDFLARE_TUNNEL_TOKEN
```

3. Ensure state files exist:
```bash
# state/portfolio.json and state/trade_log.json should already be present
ls state/
```

4. Build the container:
```bash
docker compose build
```

5. Start the always-on services (API + tunnel):
```bash
docker compose up -d api cloudflared
```

6. Verify the API is reachable:
```bash
curl https://trade.praguefun.cz/api/health
# Expected: {"status": "ok"}
```

### Updating (redeploy after code changes)

```bash
git pull
docker compose build api titantrade   # BOTH images
docker compose up -d api
```

The `api` and `titantrade` images drift independently: `api` runs the always-on
server + built-in scheduler, `titantrade` runs one-off CLI commands. A deploy
that only rebuilds `api` leaves `docker compose run titantrade ...` silently on
stale code — this happened in production, where the CLI image ran a month-old
build (predating the `benchmark` command) until the Decision 054 checkup
caught it. Rebuild both, every time.

### Running CLI Commands

Cron jobs use the `titantrade` service which runs one-off commands:

```bash
docker compose run --rm titantrade fetch      # Fetch data bundle
docker compose run --rm titantrade analyze    # Run weekly Claude analysis
docker compose run --rm titantrade sentry     # Run daily sentry check
docker compose run --rm titantrade execute    # Execute trades
docker compose run --rm titantrade full       # Full pipeline: fetch -> analyze -> sentry -> execute
```

### Scheduling (built-in APScheduler — no host cron needed)

All jobs run inside the always-on `api` container via APScheduler
(Decision 028), defined in `data/schedule.json` and interpreted in
**America/New_York** so wall-clock times track US DST (Decision 039):

| Job | Time (ET) | Command |
|-----|-----------|---------|
| `weekday_fetch` | 09:00 Mon-Fri | fetch (refresh data bundle) |
| `weekday_gapcheck` | 09:35 Mon-Fri | gapcheck |
| `weekday_sentry_morning` | 10:15 Mon-Fri | sentry + execute |
| `weekday_pricecheck_midday` | 12:00 Mon-Fri | pricecheck |
| `weekday_pricecheck_afternoon` | 14:00 Mon-Fri | pricecheck |
| `weekday_sentry_preclose` | 15:30 Mon-Fri | sentry + execute |
| `daily_summary` | 16:30 Mon-Fri | Discord daily summary (+ benchmark refresh) |
| `sunday_full` | 16:00 Sun | full pipeline (fetch → analyze → sentry → execute) |

Manage via `GET /api/scheduler`, `POST /api/scheduler/{id}/trigger`,
`PUT /api/scheduler/{id}/enabled`, or the Flutter Scheduler screen.
Host-level cron (`docker compose run --rm titantrade <cmd>` lines) remains a
documented fallback but is not used in production.

### Docker Services

| Service | Role | Always-on? |
|---------|------|-----------|
| `api` | FastAPI HTTP server — serves state files to Flutter app | Yes (`restart: unless-stopped`) |
| `cloudflared` | Cloudflare tunnel — exposes `api:8000` at `trade.praguefun.cz` | Yes (`restart: unless-stopped`) |
| `titantrade` | CLI runner — used for cron jobs | No (one-off) |

- **Volumes**: `./state` and `./logs` bind-mounted so API and CLI share the same files
- **Config**: `data/watchlist.json` is baked into the image (rebuild after changes)

### Rebuilding After Changes

```bash
# After code or watchlist changes
docker compose build
docker compose up -d api  # Restart API with new image

# After .env changes — no rebuild needed
docker compose up -d api cloudflared
```

---

## GitHub Actions Deployment (Alternative)

### Repository Secrets

Add these secrets in GitHub Settings > Secrets and variables > Actions:

| Secret Name | Description |
|-------------|-------------|
| `ALPACA_KEY` | Alpaca API Key ID |
| `ALPACA_SECRET` | Alpaca API Secret Key |
| `FRED_KEY` | FRED API key (free — VIX/treasury/econ calendar) |
| `FINNHUB_KEY` | Finnhub API key (free — earnings/analyst/sector) |
| `SEC_USER_AGENT` | User-Agent string for SEC EDGAR (with contact email) |
| `CLAUDE_KEY` | Anthropic Claude API Key |
| `GEMINI_KEY` | Google Gemini API Key |

### Workflow Files

#### Weekly Analyst (`.github/workflows/weekly_run.yml`)
- **Schedule**: Sundays at 20:00 UTC
- **Steps**: Fetch data -> Run Claude analysis -> Save thesis -> Commit state

#### Daily Sentry (`.github/workflows/daily_run.yml`)
- **Schedule**: Weekdays at 14:00 UTC (09:00 EST) and 20:30 UTC (15:30 EST)
- **Steps**: Fetch news -> Compare vs thesis -> Execute if needed -> Commit state

### State Persistence via Git

After each run, GitHub Actions commits updated state files back to the repo:
```yaml
- name: Commit state changes
  run: |
    git config user.name "TitanTrade Bot"
    git config user.email "bot@titantrade.dev"
    git add state/
    git commit -m "Update state: $(date -u +%Y-%m-%dT%H:%M:%SZ)" || true
    git push
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALPACA_PAPER_KEY` / `ALPACA_PAPER_SECRET` | Yes | Alpaca paper credentials (`ALPACA_KEY`/`ALPACA_SECRET` accepted as legacy fallback) |
| `ALPACA_LIVE_KEY` / `ALPACA_LIVE_SECRET` | No | Alpaca live credentials (required only to enable live mode) |
| `CLAUDE_KEY` | Yes | Anthropic Claude API Key |
| `CLAUDE_MODEL` | No | Model override (default: `claude-opus-4-8`) |
| `GEMINI_KEY` | Yes | Google Gemini API Key |
| `GEMINI_MODEL` | No | Model override (default: `gemini-3.1-flash-lite`) |
| `FRED_KEY` | Recommended | FRED key (free) — VIX/treasury/econ calendar; gates fail open without it |
| `FINNHUB_KEY` | Recommended | Finnhub key (free) — earnings/analyst/sector; gates fail open without it |
| `SEC_USER_AGENT` | No | User-Agent for SEC EDGAR (e.g. `TitanTrade/1.0 (you@example.com)`) |
| `DISCORD_WEBHOOK_URL` | No | Discord notifications (job alerts + daily summary); no-op if unset |
| `DATA_PROVIDER` | No | `native` (default: Alpaca+FRED+Finnhub) or `fmp` (legacy, needs `FMP_KEY`) |
| `FMP_KEY` | No | Only used when `DATA_PROVIDER=fmp` |
| `CLOUDFLARE_TUNNEL_TOKEN` | Docker only | Cloudflare tunnel for trade.praguefun.cz |
| `TRADING_MODE` | No | Override watchlist setting (paper/live) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

---

## Monitoring

### Log Files
- `logs/analyst_YYYY-MM-DD.json` - Weekly analyst decisions
- `logs/sentry_YYYY-MM-DD.json` - Daily sentry signals
- `logs/executor_YYYY-MM-DD.json` - Trade execution logs
- `logs/errors_YYYY-MM-DD.json` - Error and retry logs

### Health Checks
- Check GitHub Actions run history for failures
- Monitor `state/portfolio.json` for unexpected changes
- Review `state/trade_log.json` for trade patterns

### Alerts (Discord, live)
- Per-job completion/failure embeds + daily portfolio summary at 16:30 ET
- Observability alerts: sentry degraded (>30% fallback), stuck-in-cash (≥70% for 3+ days), ticker churn (2+ round-trips/7d), split-suspected gap, suspect broker data, cooldown overrides
- Configure via the single optional `DISCORD_WEBHOOK_URL` env var
