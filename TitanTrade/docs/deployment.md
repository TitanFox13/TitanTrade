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
| `monthly_curate` | disabled (Decision 082) | Claude universe proposal + post-mortem — manual `curate` only |

Manage via `GET /api/scheduler`, `POST /api/scheduler/{id}/trigger`, `PUT /api/scheduler/{id}/enabled`.

### Docker services

| Service | Role | Always on |
|---------|------|-----------|
| `api` | FastAPI + APScheduler | yes (`restart: unless-stopped`) |
| `cloudflared` | Tunnel exposing `api:8000` at `trade.praguefun.cz` | yes |
| `titantrade` | CLI runner | no (one-off) |

Volumes: `./state` and `./logs` on both; `./data` on `api` (watchlist edits through the API persist on the host). The `titantrade` image copies `data/` at build time — rebuild after watchlist or schedule changes. **Because `./data` is bind-mounted, a committed change to `data/watchlist.json` goes live at `git pull`, before any rebuild**: a universe or parameter change that must land together with code is committed as a staged file and copied over `watchlist.json` on the server between `docker compose stop api` and `up -d api`, after which the `titantrade` image is built so it bakes the new file, and the staged file is retired in the next commit (Decision 070, 2026-10-29). `legacy/` and `scripts/` are not copied.

**Health (Decision 107)**: the `api` service carries a Docker `healthcheck` — the container's Python opens `http://localhost:8000/api/health` every 60 s (10 s timeout, 3 retries, 90 s start period); the endpoint is 503 whenever the APScheduler thread is not running. The container is labelled `autoheal: "true"`, which the host's `resevolve-autoheal-1` watcher (willfarrell/autoheal, polling every 30 s, all containers on the socket with that label) acts on by restarting it. `docker ps` shows `(healthy)`; `docker inspect titantrade-api-1 --format '{{json .State.Health}}'` shows the last probes; a restart is logged by the watcher (`docker logs resevolve-autoheal-1`). A restart loses nothing persistent; a job mid-run is logged as failed and the next scheduled run takes over.

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

## The paper drill (Decision 103)

Forces the live paths a scheduled run rarely reaches, on the paper account, with the package's own functions — never on a live account. From `/home/TitanTrade/TitanTrade`, market open, away from the scheduled runs, after `scripts/backup_state.sh`:

```bash
docker exec -i -e STEP=status titantrade-api-1 uv run python - < scripts/paper_drill.py
```

Steps in order: `status` (read-only) → `renew NAME=<held>` (cancel its GTC stop; `ensure_stop_coverage` must re-place it) → `close NAME=<held>` (the settled close, trigger `drill_holding_limit`) → `targets TP=0.01` (one execute with `tp_pct` lowered: the core legs first, then every held name above the stand-in target exits through the quote-confirmed path; restored after) → `entry DIP=0.04` (one plan with `dip_pct` lowered → the bracket, the GTC stop on fill, coverage; restored, the plan refreshed) → `restamp` (the clean window restarts); then, as the second drill, `shock SHOCK=0.02` (the shock trigger forced on for one plan under the worst ten-session move: SPY and SPMO sell to half their targets, the leg and the held slots untouched; threshold restored and the plan refreshed in a `finally`) → `execute` (signals + execute by hand — the re-risk) → `restamp` again. Each step prints its log lines. Only the `close` row in `trade_log.json` carries a `drill_*` trigger; the `targets` and `entry` rows carry the live triggers and are told apart by their timestamps. 2026-11-05 15:27 – 15:33 UTC: every path held (Decision 103).

## Going live — the switch (Decision 071 / todo Phase 2.0; written 2026-11-10, run 2026-11-12 — Decision 108)

Only on the operator's explicit go, outside the scheduled runs (before 14:00 UTC, or between two runs), after a clean checkup. **What only the operator can do first**: a live Alpaca account, funded (**Decision 106**: $10k works, $12.5k and up is clean, $25k only a comfort number, ≈ $7.5k the hard floor where the $500 dust gate blocks the dip slots; every Alpaca account is a margin account — limited at 1× under $2,000, Reg T from $2,000 — the pattern-day-trader rule was retired 2026-06-04, and there is no good-faith-violation concept; crypto cannot be bought with unsettled funds, so fund by wire or let an ACH deposit clear before the switch; under ≈ $12.5k consider the fractional core legs first), **crypto trading enabled** (the bitcoin leg buys BTC/USD; the crypto agreement is separate) and fractional trading on (both confirmed on the live account 2026-11-10), **the account's `max_margin_multiplier` at 1 and `no_shorting` on** (set 2026-11-10 through `PATCH /v2/account/configurations` on the operator's word — the broker then refuses any order beyond cash or any short, two locks on doors the book never opens), the W-8BEN filed, the cash programme enrolled (the `cash_ticker` leg stays off, Decision 087), the live keys written into `/home/TitanTrade/TitanTrade/.env` as `ALPACA_LIVE_KEY` / `ALPACA_LIVE_SECRET` by the operator themself (never pasted into a chat), optionally `HEALTHCHECK_PING_URL`. The market-data plan is per login, so the feed settings do not change.

The switch, from `/home/TitanTrade/TitanTrade`:

1. `scripts/backup_state.sh` — the last paper snapshot.
2. Read-only pre-check of the live account, with the live mode forced for one process: `docker exec -i -e TRADING_MODE=live -e STEP=account titantrade-api-1 uv run python - < scripts/paper_drill.py` — expect `status=ACTIVE`, `crypto_status=ACTIVE`, `trading_blocked=False` (`pattern_day_trader` reads `None` or `False` — the field is being retired with the rule), the equity and cash as funded, no positions, no orders. (The drill refuses every other step on a live account.)
3. Archive the paper state — **the LLM-era peak in `peak_portfolio.json` ($114k) would make a small live account "suspect" (±50 %, Decision 084) and block every order**: `mkdir -p state/archive/paper_2026-11-12 && mv state/{trade_log,near_misses,portfolio,abort_cooldown,peak_portfolio,alert_state,benchmark_metrics,fill_ledger,plan,data_bundle,strategy,backtest_mechanical}.json state/archive/paper_2026-11-12/` (keep `sector_cache.json` and `costs.json`; a file that does not exist is skipped).
4. `data/watchlist.json` → `settings.trading_mode: "live"` (committed as the go-live config; `TRADING_MODE` in `.env` would override it either way), then `docker compose build titantrade` (the CLI image bakes `data/`) and `docker compose up -d --force-recreate api` (the container re-reads `.env` for the live keys; `./data` is mounted). Health: `curl -s localhost:8000/api/health`; `/api/settings` must say `live`.
5. The first plan by hand: `docker compose run --rm titantrade fetch` (step 3 archived the bundle; `signals` refuses to plan without one), then `docker compose run --rm titantrade signals` — writes a fresh `strategy.json` (`started_at` = `window_started_at` = now, design 097) and the plan: exposure, the sleeve target, any NEW. No orders.
6. The first orders: let the next scheduled run (10:15 or 15:30 ET) place them, watching `docker logs -f titantrade-api-1` — expect SPY to its residual (≈ 37 % with no slot filled, ≈ 28 % with one), the bitcoin leg to 5 % **before** SPMO, SPMO toward 56 %, then any entry as a bracket with its GTC stop on fill; cash ≈ 2 %. Then the 16:30 ET summary with the four positions and the benchmark window from the switch.
7. Seed the peak once the first run is in — it is otherwise written only by an entry's gate check, and until then the suspect-value guard (Decision 084) has nothing to compare against: `docker exec -i titantrade-api-1 uv run python -` with `update_peak_value(float(get_account(load_config())["equity"]))` (`titantrade.risk_manager`, `titantrade.broker`, `titantrade.config`).
8. Record the switch as a Decision (the account's size, the first fills, the window), tick todo Phase 2.0, note the go-live date in `docs/handover.md` §2.

**Rollback**: `settings.trading_mode: "paper"`, restore the archived paper state (`mv state/archive/paper_2026-11-12/*.json state/`), `docker compose build titantrade && docker compose up -d --force-recreate api`. Open live positions are the operator's to close (the orphan close only acts on the plan's own book).

**Adding or withdrawing money**: an account value more than 50 % off the recorded peak, either way, is treated as broker data corruption — the run keeps the stops and places no order (Decision 084). Before a deposit or withdrawal of that size, between two runs: archive `state/peak_portfolio.json`, let the money settle, then seed the peak as in step 7. Smaller moves need nothing; the next run rebalances the core legs to the new equity.

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
- **Checkup routine** (every 1–2 weeks): log sweep → scheduler job results → open positions all stop-covered (and none within a week of its GTC `expires_at`) → `compute_benchmark` over the clean window vs SPY → the fill ledger's median gap → `backtest-mech --shadow --start <window_started_at>` beside the live sleeve → `scripts/pull_backup.sh` → (live) the cash sweep APY vs SGOV's yield, switch `cash_ticker` on if the sweep lags ≥ 0.5 pp → record in `docs/decisions.md` and `docs/todo.md`. What each line means, in plain words: `docs/how_to_read_a_checkup.md`.
