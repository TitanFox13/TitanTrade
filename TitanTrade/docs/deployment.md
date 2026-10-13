# Deployment Guide

## Local Development

**Prerequisites**: Python 3.12+, `uv`, API keys for Alpaca (paper), Anthropic (Claude), and optionally FRED and Finnhub (free).

```bash
cd TitanTrade
uv sync
cp .env.example .env            # fill in the keys
uv run python -m titantrade fetch
uv run python -m titantrade signals
uv run python -m titantrade execute   # paper mode by default
uv run --extra test python -m pytest tests/ -q
```

## Server Deployment (Docker)

Production runs on `titanserver` in `/home/TitanTrade/TitanTrade` (repo `TitanFox13/TitanTrade` on GitHub).

**Prerequisites**: Docker + Compose, `.env` with the keys below and `CLOUDFLARE_TUNNEL_TOKEN`.

```bash
cd /home/TitanTrade/TitanTrade
cp .env.example .env            # first time only
docker compose build
docker compose up -d api cloudflared
curl https://trade.praguefun.cz/api/health     # {"status": "ok"}
```

### Updating (every code change)

```bash
git pull
docker compose build api titantrade   # BOTH images
docker compose up -d api
```

The `api` and `titantrade` images drift independently: `api` runs the server + scheduler, `titantrade` runs one-off CLI commands. Rebuilding only `api` leaves `docker compose run titantrade …` on stale code (this happened in production). Verify the CLI image through its entrypoint — a bare `/app/.venv/bin/python` inside it cannot import the package:

```bash
docker run --rm --env-file .env --entrypoint uv titantrade-titantrade run python -c "import titantrade.executor"
```

### Running CLI commands

```bash
docker compose run --rm titantrade fetch
docker compose run --rm titantrade signals
docker compose run --rm titantrade execute
docker compose run --rm titantrade full
docker compose run --rm titantrade benchmark 30
```

Or trigger a scheduler job inside the running API container:

```bash
docker exec titantrade-api-1 /app/.venv/bin/python -c "import urllib.request; print(urllib.request.urlopen(urllib.request.Request('http://localhost:8000/api/scheduler/weekday_execute_morning/trigger', method='POST')).read())"
```

### Scheduling (built-in APScheduler)

All jobs run inside the `api` container (Decision 028), from `data/schedule.json`, interpreted in **America/New_York** (Decision 039):

| Job | Time (ET) | Command |
|-----|-----------|---------|
| `weekday_fetch` | 09:00 Mon–Fri | fetch |
| `weekday_gapcheck` | 09:35 Mon–Fri | gapcheck + stop coverage (060) |
| `weekday_execute_morning` | 10:15 Mon–Fri | signals + execute |
| `weekday_execute_preclose` | 15:30 Mon–Fri | signals + execute |
| `daily_summary` | 16:30 Mon–Fri | Discord summary + benchmark refresh (058/059) |
| `sunday_full` | 16:00 Sun | fetch → signals → execute |
| `monthly_curate` | 15:00 first Sunday | Claude universe proposal + post-mortem (no orders) |

Manage via `GET /api/scheduler`, `POST /api/scheduler/{id}/trigger`, `PUT /api/scheduler/{id}/enabled`.

### Docker services

| Service | Role | Always on |
|---------|------|-----------|
| `api` | FastAPI + APScheduler | yes (`restart: unless-stopped`) |
| `cloudflared` | Tunnel exposing `api:8000` at `trade.praguefun.cz` | yes |
| `titantrade` | CLI runner | no (one-off) |

Volumes: `./state` and `./logs` on both; `./data` on `api` (watchlist edits through the API persist on the host). The `titantrade` image copies `data/` at build time — rebuild after watchlist or schedule changes. `legacy/` and `scripts/` are not copied.

### Housekeeping on titanserver
- Never `docker image prune -a` (it removes the base images the compose build relies on); `docker builder prune` and removing dangling images are fine.
- Six dangling PostgreSQL volumes and the build cache were pending cleanup at the October 2026 checkup; they belong to retired services and need the operator's go.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALPACA_PAPER_KEY` / `ALPACA_PAPER_SECRET` | Yes | Paper credentials (`ALPACA_KEY` / `ALPACA_SECRET` accepted as a legacy fallback) |
| `ALPACA_LIVE_KEY` / `ALPACA_LIVE_SECRET` | No | Live credentials — required only to enable live mode |
| `ALPACA_BASE_URL` | No | Override the trading endpoint (defaults by mode) |
| `CLAUDE_KEY` | Yes | Anthropic key (curator) |
| `CLAUDE_MODEL` | No | Default `claude-opus-4-8` |
| `FRED_KEY` | Recommended | Macro calendar; the macro gate fails open without it |
| `FINNHUB_KEY` | Recommended | Earnings + sectors; the earnings gate fails open without it |
| `DISCORD_WEBHOOK_URL` | No | Job alerts + daily summary; no-op if unset |
| `CLOUDFLARE_TUNNEL_TOKEN` | Docker | Tunnel for trade.praguefun.cz |
| `TRADING_MODE` | No | Overrides `settings.trading_mode` (paper / live) |
| `LOG_LEVEL` | No | Default INFO |

---

## Monitoring

- **Logs**: `logs/` (bind-mounted); `docker compose logs api` for the scheduler. Grep `ERROR|CRITICAL|Traceback` at each checkup; expected WARNINGs are documented in the checkup notes of `docs/decisions.md`.
- **Discord**: per-job completion / failure embeds; the 16:30 ET daily summary (equity, positions, the plan, benchmark line); observability alerts (stuck in cash, churn, suspect data, split-suspect gap, cooldown override, core rebalance).
- **API**: `/api/health`, `/api/scheduler` (last result per job), `/api/plan`, `/api/benchmark`.
- **Checkup routine** (every 1–2 weeks): log sweep → scheduler job results → open positions all stop-covered → `compute_benchmark` over the clean window vs SPY → record in `docs/decisions.md` and `docs/todo.md`.
