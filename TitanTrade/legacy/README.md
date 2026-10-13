# Legacy: the LLM-era pipeline (frozen 2026-10-13, Decision 063)

Frozen snapshots of the modules that the mechanical strategy (Decisions 061/062) replaced.
They are **not on the import path, not maintained, and not collected by the test suite**;
their imports reference module layouts that no longer exist, so they do not run as-is.

If any of this is ever needed again, the last commit on which the whole LLM pipeline ran
and passed its 613 tests is tagged **`v2-llm-pipeline`**: `git checkout v2-llm-pipeline`.
The design is recorded in `docs/decisions.md` (Decisions 001–060) and the audit that
retired it in Decision 060.

| File | What it was |
|---|---|
| `titantrade/weekly_analyst.py` | Claude two-pass weekly analysis (per-stock theses + portfolio ranking); `_call_claude` lives on in `curator.py` |
| `titantrade/daily_sentry.py` | Gemini three-layer daily sentry (market / price / news → CONTINUE or ABORT) |
| `titantrade/price_check.py` | Intraday price-move checks (no LLM) |
| `titantrade/positions.py`, `trailing_state.py` | ATR trailing stop, TP1 partial exit, pyramiding |
| `titantrade/performance.py` | Analyst performance-feedback loop (thesis history hit rates) |
| `titantrade/ai_parsing.py` | JSON/response parsing for the LLM calls |
| `titantrade/sec_edgar.py` | SEC EDGAR filings and insider-trade fetches (fed the analyst prompt) |
| `titantrade/fmp_provider.py` | Financial Modeling Prep data provider (replaced by Alpaca + FRED + Finnhub, Decision 040) |
| `titantrade/indicators.py` | The full indicator suite (RSI / MACD / Bollinger / volume / relative strength); the live module keeps ATR + correlation only |
| `titantrade/backtest/*` | The LLM-era backtester (synthetic theses + simulator mirroring trailing/TP1/pyramid) |
| `tests/*` | Their tests, plus the executor / regression / risk-manager suites written against the thesis schema |
| `scripts/probe_pyramid_washtrade.py` | The Decision 037 live probe that proved Alpaca rejects buys against a resting stop |
| `docs/agent_prompt_engineering.md` | Prompt engineering for the analyst and the sentry (input / output schemas) |
