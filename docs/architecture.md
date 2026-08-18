# TitanTrade System Architecture

TitanTrade is a semi-automated equity trading system with two components: a Python backend
that runs AI-driven analysis and executes trades, and a Flutter desktop app that provides
a visual dashboard over the backend's state files.

---

## Components

### TitanTrade Backend (`TitanTrade/`)
Python backend responsible for all data collection, AI analysis, risk management, and
trade execution. Runs on a scheduled cadence via APScheduler inside the always-on
Docker API container (`data/schedule.json`, ET times).

See [TitanTrade/docs/architecture.md](../TitanTrade/docs/architecture.md) for internals.

### TitanTrade Desktop (`titan_trade_app/`)
Flutter desktop app that reads the backend's JSON state files and presents them as a
visual dashboard. Mostly read-only — the one write path is watchlist management.

See [titan_trade_app/docs/architecture.md](../titan_trade_app/docs/architecture.md) for internals.

---

## System Diagram

```
                    +------------------+
                    |  Server (Docker)  |
                    |  (Cron Triggers)  |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
     Sunday 16:00 ET               Daily 10:15 & 15:30 ET
              |                             |
    +---------v----------+       +----------v---------+
    | weekly_analyst.py   |       | daily_sentry.py    |
    | Pass 1: Per-stock   |       | Layer 1: SPY check |
    | Pass 2: Portfolio   |       | Layer 2: Price move|
    |   ranking (top 3-5) |       | Layer 3: News/AI   |
    +--------+------------+       +----------+---------+
             |                               |
             |  weekly_thesis.json           |  sentry_signals.json
             +------------+------------------+
                          |
                +---------v----------+
                |   risk_manager.py   |
                | Gate 1: Confidence  |
                | Gate 2: Earnings    |
                | Gate 3: Drawdown    |
                | Gate 4: Cash reserve|
                | Gate 5: Vol sizing  |
                | Gate 6: Sector limit|
                +--------+-----------+
                         |
                +---------v----------+
                |    executor.py      |
                | Bracket orders      |
                | Native stop-losses  |
                +--------+-----------+
                         |
                +--------v----------+
                |   Alpaca Markets   |
                |  (Paper/Live)      |
                +--------+----------+
                         |
                +--------v----------+
                |  state/*.json      |
                |  (JSON files)      |
                +--------+----------+
                         |
                +--------v----------+
                | TitanTrade Desktop |
                | (Flutter app)      |
                +--------------------+
```

---

## Component Boundary

The two components communicate over HTTP. The backend exposes a REST API; the app polls it.

| Direction | What | Endpoint |
|-----------|------|----------|
| Backend → App | Portfolio, trades, theses, sentry, near misses, costs | `GET /api/*` |
| App → Backend | Watchlist edits | `PUT /api/watchlist` |

The app polls all endpoints at a configurable interval (default 30s). The API is served
by the backend's FastAPI server, exposed publicly at `https://trade.praguefun.cz` via
a Cloudflare tunnel.

---

## AI Agents

Two AI models run in distinct roles:

| Agent | Model | Cadence | Role |
|-------|-------|---------|------|
| The Analyst | Claude Opus 4.8 (adaptive thinking) | Weekly (Sunday) | Deep two-pass portfolio analysis |
| The Sentry | Gemini Flash Lite (3.1, structured output) | Daily (×2) | Fast binary conflict detection |

See [docs/agent_instructions.md](agent_instructions.md) for agent design and behavior.

---

## Risk Architecture

Nine programmatic gates sit between every AI recommendation and actual trade execution
(confidence, earnings, drawdown, cash reserve, overlay cap, position size, sector
exposure, macro blackout, correlation). No AI output can bypass them — they are
enforced in code, not in prompts.

The gates also defend against *bad broker data*, not just bad AI output (Decision 054):
orders below a $500 minimum notional are blocked as dust, account values ±50% off the
recorded peak are treated as data corruption rather than real drawdowns, and gap-down
liquidations deeper than 30% below the stop are cross-checked against the corporate-actions
feed so a stock split is never sold as a crash.

Entry validation additionally refuses degenerate setups (Decision 055): a stop closer
than 1.5% to the entry (a noise-level stop that would tag out within minutes), and any
entry or bracket resubmission for a ticker whose current sentry signal is ABORT (the
executor is about to exit it — entering first just forces a same-minute round-trip).

Protective exits are symmetric (Decision 056): a broker-side stop-loss fill starts the
same 72h re-entry cooldown an ABORT does (with the same sentry-confirmed override), and
weekly-review ADJUST levels are never applied to a position opened after the review was
generated — they were computed for a position that no longer exists.

See [TitanTrade/docs/risk_management.md](../TitanTrade/docs/risk_management.md) for details.
