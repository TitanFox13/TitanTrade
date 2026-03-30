# Agent Prompt Engineering

Detailed input/output specifications for both AI agents. For the high-level overview,
decision matrix, and scheduling, see [docs/agent_instructions.md](../../docs/agent_instructions.md).

---

## Agent 1: The Analyst (Claude Opus/Sonnet)

### Pass 1: Individual Stock Analysis

Each stock gets its own Claude call. Isolation is intentional — prevents anchoring bias
between stocks.

**Input per call:**
- 5-day OHLCV (recent price action)
- Pre-computed technical indicators (RSI, MACD, Bollinger, ATR, SMA analysis)
- 7-day news headlines with deduplication
- SEC filings from last 24 hours
- Earnings calendar (upcoming date + blackout status)
- Market context (SPY/QQQ/VIX/sectors/regime)
- Performance history (last 4 weeks win rate + confidence calibration)

**Key prompt instructions:**
1. Start with market context — don't go BULLISH into a crashing market
2. Use pre-computed indicators (more reliable than eyeballing OHLCV)
3. Set entry at technically attractive levels (support, SMA, etc.)
4. Set stop-loss at technical levels too (below support, below SMA)
5. Take-profit needs minimum 2:1 reward-to-risk
6. Confidence must be calibrated against past performance
7. Only use >0.85 confidence with exceptional conviction

**Required output schema:**
```json
{
  "ticker": "AAPL",
  "sector": "Technology",
  "thesis": "BULLISH",
  "confidence": 0.78,
  "target_entry_price": 185.50,
  "stop_loss_price": 176.23,
  "take_profit_price": 198.00,
  "thesis_breach_condition": "CEO departure or revenue guidance cut >10%",
  "key_technical_levels": {
    "support": 183.00,
    "resistance": 192.00
  },
  "reasoning": "Multi-factor explanation..."
}
```

### Pass 2: Portfolio Ranking

A single Claude call that sees all 10 Pass 1 theses simultaneously.

**Input:**
- All 10 Pass 1 theses
- Market context
- Current portfolio holdings
- Sector exposure breakdown
- Performance history

**Key prompt instructions:**
1. Select TOP 3-5 trades (not all BULLISH calls)
2. Max 2 picks from the same sector
3. In bearish/crisis regimes, select 0-2 trades only
4. Consider risk/reward ratio across the portfolio as a whole
5. May adjust confidence scores based on portfolio context

**Required output schema:**
```json
{
  "selected_tickers": ["AAPL", "LLY", "JPM"],
  "market_regime_assessment": "Normal/bullish regime...",
  "selections": [
    {
      "ticker": "AAPL",
      "confidence": 0.78,
      "selection_reasoning": "Why this was included..."
    }
  ],
  "rejections": [
    {
      "ticker": "TSLA",
      "rejection_reason": "Why this was excluded..."
    }
  ],
  "portfolio_risk_notes": "Sector exposure analysis..."
}
```

---

## Agent 2: The Sentry (Gemini Flash)

### Layer 3: News-Based Check

Layers 1 and 2 are programmatic (no AI). Layer 3 is the only AI call in the sentry.

**Input per call:**
- Active thesis details (ticker, thesis direction, confidence, breach condition)
- Today's news headlines for that ticker
- Layer 1 result: SPY change % and market stress flag
- Layer 2 result: stock price change % since entry and direction

**Prompt template structure:**
1. Active thesis details + breach condition
2. Today's news headlines
3. Price action alert (current price vs entry, % move)
4. Market-wide alert (SPY change, stress flag)

**Key prompt instructions:**
- Conservative default: when in doubt, lean toward ABORT
- ABORT if any headline directly relates to the thesis breach condition
- CONTINUE only if headlines are clearly unrelated or positive for the thesis
- Keep reasoning brief and focused on the breach condition

**Required output schema:**
```json
{
  "ticker": "AAPL",
  "signal": "CONTINUE",
  "conflicting_headlines": [],
  "reasoning": "No headlines relate to CEO departure or revenue guidance..."
}
```

`signal` is strictly `"CONTINUE"` or `"ABORT"`. Any other value is treated as ABORT.

### Hard Override (Layer 2)

If Layer 2 detects a 3%+ adverse price move, the system forces ABORT regardless of
what Gemini returns. This override happens in code (`daily_sentry.py`) before the
Layer 3 result is used. Gemini still runs (its reasoning is logged), but its signal
is discarded.
