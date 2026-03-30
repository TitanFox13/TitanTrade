# Deployment Guide

## Local Development

### Prerequisites
- Python 3.12+
- uv (package manager)
- API keys for: Alpaca, FMP, SEC-API, Anthropic (Claude), Google (Gemini)

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

### Running CLI Commands

Cron jobs use the `titantrade` service which runs one-off commands:

```bash
docker compose run --rm titantrade fetch      # Fetch data bundle
docker compose run --rm titantrade analyze    # Run weekly Claude analysis
docker compose run --rm titantrade sentry     # Run daily sentry check
docker compose run --rm titantrade execute    # Execute trades
docker compose run --rm titantrade full       # Full pipeline: fetch -> analyze -> sentry -> execute
```

### Cron Schedule (Server)

Add these to your server's crontab (`crontab -e`):

```crontab
# Weekly analyst: Sunday 20:00 UTC
0 20 * * 0 cd /path/to/TitanTrade && docker compose run --rm titantrade full >> /var/log/titantrade-weekly.log 2>&1

# Daily sentry + execute pre-market: Weekdays 14:00 UTC (09:00 EST)
0 14 * * 1-5 cd /path/to/TitanTrade && docker compose run --rm titantrade sentry && docker compose run --rm titantrade execute >> /var/log/titantrade-daily.log 2>&1

# Daily sentry + execute pre-close: Weekdays 20:30 UTC (15:30 EST)
30 20 * * 1-5 cd /path/to/TitanTrade && docker compose run --rm titantrade sentry && docker compose run --rm titantrade execute >> /var/log/titantrade-daily.log 2>&1
```

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
| `FMP_KEY` | Financial Modeling Prep API Key |
| `SEC_API_KEY` | SEC-API.io API Token |
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
| `ALPACA_KEY` | Yes | Alpaca API Key ID |
| `ALPACA_SECRET` | Yes | Alpaca API Secret Key |
| `ALPACA_BASE_URL` | No | Override API base URL (default: paper) |
| `FMP_KEY` | Yes | Financial Modeling Prep API Key |
| `SEC_API_KEY` | Yes | SEC-API.io API Token |
| `CLAUDE_KEY` | Yes | Anthropic Claude API Key |
| `CLAUDE_MODEL` | No | Model override (default: claude-sonnet-4-6-20250514) |
| `GEMINI_KEY` | Yes | Google Gemini API Key |
| `GEMINI_MODEL` | No | Model override (default: gemini-2.0-flash) |
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

### Alerts (Future)
- Slack webhook on ABORT signals
- Email on execution errors
- Daily portfolio summary notification
