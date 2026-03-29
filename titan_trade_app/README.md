# TitanTrade Desktop App

Desktop companion app for TitanTrade. Tracks trade circumstances and outcomes by reading
the Python backend's state files.

## Purpose

Provides a visual dashboard for:
- **Portfolio overview**: Cash balance, invested value, active positions, unrealized P&L
- **Trade tracking**: Full context for each trade (thesis, sentry signals, execution details)
- **Active theses**: Weekly AI theses with confidence scores, price levels, breach conditions
- **Sentry signals**: Latest CONTINUE/ABORT signals with reasoning
- **Near misses**: Trades blocked by 1–2 risk gates, with full context for review
- **Watchlist management**: Add or remove tracked tickers (writes to `data/watchlist.json`)
- **Statistics**: Net P&L, realized/unrealized P&L, operational costs breakdown per AI service

The app is mostly **read-only** — it observes TitanTrade's state files. The one exception
is the watchlist screen, which can add/remove tickers in `data/watchlist.json`.

## Prerequisites

- Flutter SDK 3.11+
- Desktop platform support enabled (`flutter config --enable-windows-desktop`)

## Setup

```bash
cd titan_trade_app
flutter pub get
```

## Run

```bash
flutter run -d windows   # or macos, linux
```

On first launch, the app asks you to select the TitanTrade project directory. It validates
the path by checking for `state/portfolio.json`.

## Build

```bash
flutter build windows   # or macos, linux
```

## Architecture

### State Management
- **Riverpod** (`flutter_riverpod`) for reactive state
- Providers poll JSON files at a configurable interval (default 30s, adjustable in Settings)
- Handles missing files gracefully (sentry/thesis data may not exist yet)

### Navigation
- **go_router** with a `NavigationRail` shell (desktop convention)
- Routes: `/` (dashboard), `/theses`, `/theses/:ticker`, `/trades`, `/trades/:index`, `/near-misses`, `/near-misses/:index`, `/watchlist`, `/statistics`, `/settings`

### Data Sources
All data comes from the TitanTrade `state/` directory:

| File | Content |
|------|---------|
| `portfolio.json` | Cash balance, positions |
| `trade_log.json` | All trades with trigger, reasoning |
| `weekly_thesis.json` | Active theses with confidence, prices |
| `sentry_signals.json` | Latest CONTINUE/ABORT signals |
| `near_misses.json` | Trades blocked by 1–2 risk gates |
| `costs.json` | Per-API-call token usage and estimated costs |

The app also reads from `data/`:

| File | Content |
|------|---------|
| `watchlist.json` | Tracked tickers and settings (read/write) |

### Project Structure

```
lib/
  main.dart              # Entry point, window config
  app.dart               # Shell with NavigationRail + router
  theme.dart             # Dark theme
  config/
    app_config.dart      # Data path management
  models/
    portfolio.dart       # Portfolio + Position
    trade.dart           # Trade record (with optional context + gate results)
    thesis.dart          # WeeklyThesisBundle + Thesis
    sentry_signal.dart   # SentryBundle + SentrySignal
    near_miss.dart       # NearMiss, GateResult, TradeContext, TechnicalSnapshot
    cost_record.dart     # CostRecord (AI API usage)
  providers/
    config_provider.dart     # TitanTrade directory path
    portfolio_provider.dart  # Reads portfolio.json
    trade_log_provider.dart  # Reads trade_log.json
    thesis_provider.dart     # Reads weekly_thesis.json
    sentry_provider.dart     # Reads sentry_signals.json
    near_miss_provider.dart  # Reads near_misses.json (30s polling)
    watchlist_provider.dart  # Reads/writes data/watchlist.json
    costs_provider.dart      # Reads state/costs.json (30s polling)
  screens/
    setup_screen.dart            # First-run directory picker
    dashboard_screen.dart        # Portfolio overview
    trade_history_screen.dart    # Trade list with filters
    trade_detail_screen.dart     # Single trade with full context + gate results
    theses_screen.dart           # Active theses grid
    thesis_detail_screen.dart    # Thesis detail
    near_misses_screen.dart      # Near-miss list with closeness indicators
    near_miss_detail_screen.dart # Near-miss detail (gates, thesis, context)
    watchlist_screen.dart        # Add/remove tracked tickers
    statistics_screen.dart       # P&L overview, costs, net profitability
    settings_screen.dart         # Data path + refresh interval configuration
  widgets/
    portfolio_summary_card.dart
    position_tile.dart
    trade_tile.dart
    thesis_card.dart
    sentry_badge.dart
    pnl_chip.dart
    gate_result_tile.dart  # Per-gate pass/fail row + GateResultsCard
    context_card.dart      # Market context, technicals, news at trade time
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `flutter_riverpod` | State management |
| `go_router` | Navigation/routing |
| `fl_chart` | Charts (future) |
| `intl` | Date/number formatting |
| `file_picker` | Directory selection on setup |
| `shared_preferences` | Persist data path |
| `window_manager` | Window size/title control |
