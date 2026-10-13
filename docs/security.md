# Security Considerations

## API Key Management

1. **Never commit API keys.** All keys come from the environment (`.env`, git-ignored, loaded by `python-dotenv`; Docker reads the same file).
2. Required: `ALPACA_PAPER_KEY` / `ALPACA_PAPER_SECRET`, `CLAUDE_KEY`. Optional: `ALPACA_LIVE_KEY` / `ALPACA_LIVE_SECRET`, `FRED_KEY`, `FINNHUB_KEY`, `DISCORD_WEBHOOK_URL`, `CLOUDFLARE_TUNNEL_TOKEN`.
3. No key is ever logged or sent to the LLM; the curator prompt carries price and trade data only.
4. Rotate keys quarterly (Alpaca dashboard, Anthropic console, FRED / Finnhub account pages).

### Dual Alpaca Credentials
- Separate paper and live key pairs; legacy `ALPACA_KEY` / `ALPACA_SECRET` are accepted as the paper fallback.
- `load_config()` selects the pair from `trading_mode`; live mode without live keys raises (fail-safe).
- Live mode is enabled via `PUT /api/settings/mode` (or `settings.trading_mode` in `data/watchlist.json`); the API refuses it when live keys are missing. `TRADING_MODE` in the environment overrides the file.

## Trading Safety

- Paper trading is the default and the current state (todo Phase 2.0 gates going live).
- Position limits are code, not configuration the LLM can reach: 25% slots, max 3, 70% overlay cap, 5% cash reserve, $500 minimum notional, 8% drawdown breaker, 50% sector cap, 75% correlation cap.
- Every entry is a bracket with a −12% stop; a GTC stop replaces the DAY leg on fill, and the stop-coverage job re-places a missing stop five minutes into every session.
- Every exit cancels the resting stop, waits for the cancel to settle, sells at market and restores the stop if the sell fails — a position is never left bare by a failed exit.
- The only LLM output the system reads is the monthly universe proposal, and it is applied by a human.

## Data Security

- `state/` holds portfolio values, positions and the trade log; it is git-ignored and bind-mounted into the containers. Keep the repository private.
- The API is read-mostly: the write paths are the watchlist, the trading mode and scheduler enable / trigger. It sits behind a Cloudflare tunnel; there is no authentication in the app itself, so access control is the tunnel's.

## Operational Security

- Retry logic with exponential backoff and `Retry-After` support on every external call; 4xx errors are not retried and keep the broker's diagnostic body (`HTTPError`).
- Discord webhook posts retry transient failures twice; a notification failure never fails the job.
- The Docker image copies `src/` and `data/` only; `legacy/` and `scripts/` never reach production.
