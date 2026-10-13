"""Pluggable market-data providers.

``native`` (Alpaca + FRED + Finnhub, ADR 040) is the one provider;
``titantrade.market_data`` is the facade consumers call. The retired FMP
provider lives in ``legacy/``.

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
