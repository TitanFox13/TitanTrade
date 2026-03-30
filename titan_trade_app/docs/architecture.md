# Desktop App Architecture

For the full system context (how the app fits into TitanTrade), see
[docs/architecture.md](../../docs/architecture.md).

---

## State Management

**Riverpod** (`flutter_riverpod`) is used throughout.

All data providers are stream providers that poll the TitanTrade HTTP API at a configurable
interval (default 30s). The interval is persisted via `SharedPreferences` and observed by all
7 providers — changing it in Settings takes effect immediately across the whole app via
`ref.watch`.

Providers handle 404 responses and network errors gracefully (sentry/thesis data may not
exist yet on a fresh deployment).

---

## Navigation

**go_router** with a `NavigationRail` shell (desktop convention).

| Route | Screen |
|-------|--------|
| `/` | Dashboard |
| `/theses` | Active Theses grid |
| `/theses/:ticker` | Thesis Detail |
| `/trades` | Trade History |
| `/trades/:index` | Trade Detail |
| `/near-misses` | Near Misses |
| `/near-misses/:index` | Near Miss Detail |
| `/watchlist` | Watchlist Management |
| `/statistics` | Statistics / P&L |
| `/settings` | Settings |
| `/setup` | First-run directory picker |

---

## Data Sources

All data comes from the TitanTrade HTTP API. On first run the app asks for the server URL
and validates it by hitting `GET /api/health`.

### Read endpoints

| Endpoint | Content |
|----------|---------|
| `GET /api/portfolio` | Cash balance, open positions |
| `GET /api/trades` | All trades with trigger and reasoning |
| `GET /api/theses` | Active theses with confidence, prices, breach conditions |
| `GET /api/sentry` | Latest CONTINUE/ABORT signals |
| `GET /api/near-misses` | Trades blocked by 1–2 risk gates |
| `GET /api/costs` | Per-API-call token usage and estimated costs |
| `GET /api/watchlist` | Tracked tickers and settings |

### Write endpoint

| Endpoint | Purpose |
|----------|---------|
| `PUT /api/watchlist` | Update the tracked tickers list |

---

## Project Structure

```
lib/
  main.dart                    # Entry point, window config
  app.dart                     # Shell with NavigationRail + router
  theme.dart                   # Dark theme
  config/
    app_config.dart            # Data path management (SharedPreferences)
  models/
    portfolio.dart             # Portfolio + Position
    trade.dart                 # Trade record (with optional context + gate results)
    thesis.dart                # WeeklyThesisBundle + Thesis
    sentry_signal.dart         # SentryBundle + SentrySignal
    near_miss.dart             # NearMiss, GateResult, TradeContext, TechnicalSnapshot
    cost_record.dart           # CostRecord (AI API usage + estimated cost)
  providers/
    config_provider.dart       # TitanTrade directory path
    portfolio_provider.dart    # Reads portfolio.json
    trade_log_provider.dart    # Reads trade_log.json
    thesis_provider.dart       # Reads weekly_thesis.json
    sentry_provider.dart       # Reads sentry_signals.json
    near_miss_provider.dart    # Reads near_misses.json (polled)
    watchlist_provider.dart    # Reads/writes data/watchlist.json
    costs_provider.dart        # Reads state/costs.json (polled)
  screens/
    setup_screen.dart
    dashboard_screen.dart
    trade_history_screen.dart
    trade_detail_screen.dart
    theses_screen.dart
    thesis_detail_screen.dart
    near_misses_screen.dart
    near_miss_detail_screen.dart
    watchlist_screen.dart
    statistics_screen.dart
    settings_screen.dart
  widgets/
    portfolio_summary_card.dart
    position_tile.dart
    trade_tile.dart
    thesis_card.dart
    sentry_badge.dart
    pnl_chip.dart
    gate_result_tile.dart      # Per-gate pass/fail row + GateResultsCard
    context_card.dart          # Market context, technicals, news at trade time
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `flutter_riverpod` | Reactive state management |
| `go_router` | Declarative routing |
| `fl_chart` | Charts (future use) |
| `intl` | Date/number formatting |
| `file_picker` | Directory selection on setup |
| `shared_preferences` | Persist data path + refresh interval |
| `window_manager` | Window size and title control |
