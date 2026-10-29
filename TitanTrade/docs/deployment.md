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

Production runs on `titanserver`: the repository is checked out at `/home/TitanTrade` (repo `TitanFox13/TitanTrade` on GitHub) and the package, compose file, `data/` and `state/` are in `/home/TitanTrade/TitanTrade` — run `git` and `docker compose` from there.

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

Each build leaves ~3 GB of build cache behind; finish a deploy with `docker builder prune -a -f` (safe — it never touches images or containers), or the disk climbs ~15 points a week of deploys.

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
| `daily_summary` | 16:30 Mon–Fri | Discord summary + benchmark refresh over the strategy's window (058/059/065) |
| `sunday_full` | 16:00 Sun | fetch → signals → execute |
| `monthly_curate` | 15:00 first Sunday | Claude universe proposal + post-mortem (no orders) |

Manage via `GET /api/scheduler`, `POST /api/scheduler/{id}/trigger`, `PUT /api/scheduler/{id}/enabled`.

### Docker services

| Service | Role | Always on |
|---------|------|-----------|
| `api` | FastAPI + APScheduler | yes (`restart: unless-stopped`) |
| `cloudflared` | Tunnel exposing `api:8000` at `trade.praguefun.cz` | yes |
| `titantrade` | CLI runner | no (one-off) |

Volumes: `./state` and `./logs` on both; `./data` on `api` (watchlist edits through the API persist on the host). The `titantrade` image copies `data/` at build time — rebuild after watchlist or schedule changes. **Because `./data` is bind-mounted, a committed change to `data/watchlist.json` goes live at `git pull`, before any rebuild**: a universe or parameter change that must land together with code is committed as a staged file and copied over `watchlist.json` on the server between `docker compose stop api` and `up -d api`, after which the `titantrade` image is built so it bakes the new file, and the staged file is retired in the next commit (Decision 070, 2026-10-29). `legacy/` and `scripts/` are not copied.

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
| `HEALTHCHECK_PING_URL` | No | Dead-man's switch: GET after each successful daily summary (Decision 071); no-op if unset |
| `CLOUDFLARE_TUNNEL_TOKEN` | Docker | Tunnel for trade.praguefun.cz |
| `TRADING_MODE` | No | Overrides `settings.trading_mode` (paper / live) |
| `LOG_LEVEL` | No | Default INFO |

---

## Backups

`scripts/backup_state.sh` snapshots `state/` (trade log, plan, strategy, fill ledger, cooldowns, peak, archive) and `data/watchlist.json` into `/home/TitanTrade/backups/titantrade-state-<UTC stamp>.tar.gz`, keeping the last 30. Host cron on titanserver (Decision 071): `30 21 * * * /home/TitanTrade/TitanTrade/scripts/backup_state.sh >> /home/TitanTrade/backups/backup.log 2>&1` — after the 20:30 UTC daily summary. Restore on a host with the checkout: `tar xzf /home/TitanTrade/backups/<archive> -C /home/TitanTrade/TitanTrade` (then `docker compose up -d api`). Off-server copies: `scripts/pull_backup.sh [dest]` pulls the latest archive over ssh with the base64 pipe (`scp` fails there) into a git-ignored `backups/` folder next to the checkout — run it at every checkup from any machine with the `titanserver` alias.

## The server-down runbook (Decision 071)

**What keeps working with the server down**: the GTC stop-limits on the dip positions — until their expiry: Alpaca's aged-order policy cancels every GTC order **90 days after creation, at 16:15 ET on its `expires_at` date** (Alpaca docs, "Orders at Alpaca"). While the server runs, the 09:35 ET coverage job re-places it the next morning (an overnight gap on day 90, normally never reached because the 60-trading-day clock exits first). A standalone GTC stop is also cancelled by Alpaca ahead of a mandatory corporate action on its symbol (split, symbol change, merger) and adjusted on a forward split — the same coverage job is the backstop; bracket legs carry DNR/DNC and are not. The core legs (SPY, SPMO, SGOV) carry no stop by design.

**What stops**: new entries, the +20 % target and the 60-trading-day holding-limit exits (they are evaluated by the executor, not the broker), core rebalances, the insurance and shock de-risking, the 09:35 ET re-placement of an expired or missing stop, the daily summary — and therefore the heartbeat ping.

**The alarm**: the dead-man's switch. The API GETs `HEALTHCHECK_PING_URL` after every successful daily summary; a monitor expecting it every weekday at 16:35 ET (grace 2 h) raises the alarm when the server, the scheduler or the summary is dead. The process cannot report its own death; this is the only signal that does.

**Steps**:
1. `ssh titanserver`, `docker ps`, `docker logs titantrade-api-1 --since 24h`, `df -h /`. Restart: `docker compose up -d api`; health: `/api/health`.
2. Catch up by hand, in this order: `docker compose run --rm titantrade gapcheck` (re-places any missing or expired stop), then `fetch`, then `execute` (= signals + execute: holding-limit and target exits fire, the core legs rebalance, the exposure rules apply).
3. Host lost: restore `state/` from the latest archive on a new host, deploy per this guide, then step 2. While nothing runs, the Alpaca dashboard is the manual exit — every dip position's stop is visible there with its expiry date.
4. After the outage: check the trade log and the fill ledger for the catch-up run, and that no position older than 90 days sat without a stop.

## Monitoring

- **Logs**: `logs/` (bind-mounted); `docker compose logs api` for the scheduler. Grep `ERROR|CRITICAL|Traceback` at each checkup; expected WARNINGs are documented in the checkup notes of `docs/decisions.md`.
- **Discord**: per-job completion / failure embeds; the 16:30 ET daily summary (equity, positions, the plan, benchmark line); observability alerts (stuck in cash, churn, suspect data, split-suspect gap, cooldown override, core rebalance).
- **API**: `/api/health`, `/api/scheduler` (last result per job), `/api/plan`, `/api/benchmark`.
- **Checkup routine** (every 1–2 weeks): log sweep → scheduler job results → open positions all stop-covered (and none within a week of its GTC `expires_at`) → `compute_benchmark` over the clean window vs SPY → the fill ledger's median gap → `backtest-mech --shadow --start <window_started_at>` beside the live sleeve → `scripts/pull_backup.sh` → (live) the cash sweep APY vs SGOV's yield, switch `cash_ticker` on if the sweep lags ≥ 0.5 pp → record in `docs/decisions.md` and `docs/todo.md`.
