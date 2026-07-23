# Insights & Lessons

## Design Insights

### Why Two Passes Instead of One Mega-Prompt
A single prompt with "analyze all 10 stocks and pick the best 3" sounds simpler
but produces worse results. In Pass 1, analyzing each stock in isolation prevents
anchoring bias (seeing AAPL's strong thesis doesn't inflate MSFT's). In Pass 2,
seeing all theses side-by-side enables portfolio-level reasoning that per-stock
analysis can't provide. The separation of concerns is the feature.

### The Feedback Loop Is the Long-Term Edge
Any system that doesn't learn from its mistakes will plateau. The performance feedback
loop is designed to solve the "Claude is always 0.75 confident" problem. By showing
Claude that its 0.75 confidence calls only win 55% of the time (for example), it can
recalibrate. The 52-week thesis archive enables seasonal pattern detection too.

### ATR-Based Sizing: Equal Risk, Not Equal Dollars
Putting $10,000 into TSLA (3% daily swings) and $10,000 into JPM (1% daily swings)
means TSLA contributes 3x the portfolio risk. ATR-based sizing equalizes: TSLA gets
fewer shares so a 1-ATR move in either stock costs the same dollar amount. This is
standard institutional practice but rarely seen in retail trading bots.

### Why Two AI Models Instead of One
Using a single model for both deep analysis and daily checks would be wasteful. Claude Opus
excels at multi-step reasoning across large data bundles but is expensive and slow for simple
yes/no decisions. Gemini Flash handles binary classification (CONTINUE/ABORT) in milliseconds
at a fraction of the cost. This mirrors how real trading desks work: senior analysts set the
thesis, junior traders monitor for breaking news.

### Why Weekly + Daily, Not Real-Time
Real-time trading requires always-on infrastructure, WebSocket connections, and sub-second
decision making. Our watchlist of blue-chip stocks doesn't need that. Weekly thesis setting
with daily validation captures 90% of the alpha while keeping infrastructure costs at zero
(GitHub Actions free tier). The 5-15 minute cron variance is irrelevant for our timeframe.

### JSON as a "Poor Man's Database"
For a 10-stock watchlist with daily updates, JSON files are more than sufficient. The entire
state fits in under 50KB. This eliminates database complexity, connection pooling, migrations,
and hosting costs. The trade-off (no concurrent writes) is irrelevant since our cron jobs
run sequentially.

### Structured AI Output is Non-Negotiable
Free-text AI responses are a debugging nightmare. By requiring strict JSON output with
defined schemas, we can:
- Validate responses programmatically
- Handle malformed output gracefully
- Log decisions in a queryable format
- Compare thesis changes week-over-week

### Stop-Loss as Insurance, Not Strategy
The 5% stop-loss exists as catastrophic loss prevention, not as a trading signal. In backtesting,
tight stop-losses often cause "whipsaw" (selling low then missing the recovery). Our stop-loss
is intentionally set wide enough to absorb normal volatility while preventing portfolio-level
damage from black swan events.

### Why Software Stop-Losses Are Dangerous
The original design checked stop-loss by comparing current price to a threshold in the cron job.
This only fires twice per day. Overnight a stock can drop 15-20% on bad earnings or macro news.
By the time the morning sentry runs, the damage is done and the "stop" fires at a much worse price
than intended. Alpaca's native `stop_limit` orders solve this: they live on Alpaca's servers and
execute the moment price triggers, 24 hours a day, regardless of whether our code is running.

### Bracket Order Nuance
Alpaca bracket orders are `time_in_force: "day"` only - they don't persist overnight as a single
unit. This means if the entry limit buy doesn't fill by market close, the whole bracket expires.
The daily pre-market workflow handles this: it checks for BULLISH positions with no pending orders
and re-submits the bracket each morning. This is intentional - it also lets Claude's Sunday thesis
adjust the entry price each morning if price has moved significantly.

## API Insights

### FMP API Quirks
- Rate limits are per-minute, not per-day on paid tiers
- News endpoint sometimes returns duplicates; deduplicate by title hash
- OHLCV data may have gaps on holidays; handle missing dates gracefully

### Alpaca Paper Trading
- Paper account resets are available but not automatic
- Paper fills are always at the last price (no slippage simulation)
- Order types supported: market, limit, stop, stop-limit

### Claude API for Financial Analysis
- System prompts significantly improve output consistency
- Temperature 0.3-0.5 works best for analytical tasks (lower = more deterministic)
- Including explicit JSON schema in the prompt reduces format errors by ~90%
- Max tokens should be generous; truncated JSON is worse than verbose JSON

### Gemini Flash for Sentiment
- Excellent at binary classification tasks
- Struggles with nuance; keep prompts simple and binary
- Response times consistently under 500ms
- Cost per request is negligible (~$0.0001)

## Operational Insights

### GitHub Actions Timing
- Cron jobs may fire 5-15 minutes late during high-demand periods
- For market-sensitive operations, build in time buffers
- Sunday 20:00 UTC gives ~12 hours before Monday market open (sufficient buffer)

### Environment Variable Management
- Never commit `.env` files
- GitHub Secrets have a 64KB limit per secret
- Use `python-dotenv` for local development, `os.environ` for production

### Logging Strategy
- Log AI reasoning in full (it's cheap storage, invaluable for debugging)
- Use structured JSON logs for machine-parseable analysis
- Rotate logs monthly to prevent unbounded growth
- Include input data hashes for reproducibility

### Broker Data Is Not Ground Truth (the CRWD Split, Decision 054)
CRWD split 4:1 on 2026-07-02. The market traded post-split (~$193) from the
open, but Alpaca paper adjusted the *position* three trading days later. In
that gap the account showed a 15-share position "crashing" 71% below its stop,
and gap-down protection sold a healthy position at the artificial bottom. The
subtle part: the ADR 053 live-quote cross-check passed, because the quote
genuinely was $193 — **a real price can still be a broker-state artifact**.
Days later the same split processing made `GET /v2/account` briefly report
$22,828 against a real ~$100k equity, tripping the drawdown breaker at a
phantom "79.1%". Lessons baked into code (Decision 054):
- Destructive actions need *corroboration across data sources*: a >30% gap now
  checks the corporate-actions feed before liquidating.
- Any single account-value observation ±50% off the recorded peak is treated
  as data corruption — alert and sit out one run; never write it into state
  (a glitched peak would trip the breaker forever).
- Phantom equity swings pollute *derived analytics* long after the event: the
  Jul 2–7 round-trip inflates benchmark drawdown/vol until it rolls out of the
  90-day window. Know your artifacts before reading your metrics.

### Dust Orders Are Pure Downside
When nearly all cash is committed, sizing that "reduces to fit" can shrink an
order to slivers (production: 0.01 URI shares = $11). Dust fills like a real
trade, pays fees like a real trade, churns like a real trade — but can't carry
a stop (Alpaca rejects stops on sub-1-share orders). A $500 minimum-notional
floor turns these into clean near-miss records instead (Decision 054).
