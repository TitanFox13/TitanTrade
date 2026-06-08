"""Pluggable market-data providers.

Each provider module implements the same interface so the system can switch
data sources without touching any consumer. Selection is by
``cfg.data_provider`` (env ``DATA_PROVIDER``); ``titantrade.market_data`` is
the facade that dispatches to the chosen one.

Providers:
  - ``native`` — Alpaca + FRED + Finnhub (default; free; ADR 040).
  - ``fmp``    — legacy Financial Modeling Prep (retained, switchable via
                 ``DATA_PROVIDER=fmp`` + a valid ``FMP_KEY``).

Interface (all take/return the shapes the connectors expect):
  get_ohlcv(ticker, cfg, days=250) -> [{date, open, high, low, close, volume}]
  get_latest_price(ticker, cfg) -> float | None
  get_daily_change_pct(ticker, cfg) -> float | None
  get_news(ticker, cfg, limit=50) -> [{title, snippet, published_at, source}]
  get_vix(cfg) -> float | None
  get_treasury_yields(cfg) -> {yield_10y, yield_2y}
  get_economic_calendar(cfg, days_ahead=7) -> [{date, event, impact, previous, estimate}]
  get_earnings_dates(tickers, cfg) -> {ticker: "YYYY-MM-DD" | None}
  get_analyst_ratings(ticker, cfg) -> {recent_grades: [...], price_target?: {...}}
  get_sector(ticker, cfg) -> str

A provider must degrade gracefully (return empty/None) rather than raise, so a
data outage never crashes the pipeline.
"""
