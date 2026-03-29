# Agent Instructions

## Overview

TitanTrade uses two AI agents in a layered architecture. The Analyst does deep weekly
work with rich context. The Sentry does fast daily checks with focused prompts.

---

## Agent 1: The Analyst (Claude Opus/Sonnet)

### Role
Senior equity research analyst + portfolio manager. Two-pass weekly pipeline.

### Schedule
Every Sunday at 20:00 UTC (before Monday market open).

### Pass 1: Individual Stock Analysis

Each stock gets its own Claude call with:

**Input:**
- 5-day OHLCV (recent price action)
- Pre-computed technical indicators (RSI, MACD, Bollinger, ATR, SMA analysis)
- 7-day news headlines with deduplication
- SEC filings from last 24 hours
- Earnings calendar (upcoming date + blackout status)
- Market context (SPY/QQQ/VIX/sectors/regime)
- Performance history (last 4 weeks win rate + confidence calibration)

**Key Prompt Instructions:**
1. Start with market context - don't go BULLISH into a crashing market
2. Use pre-computed indicators (they're more reliable than eyeballing OHLCV)
3. Set entry at technically attractive levels (support, SMA, etc.)
4. Set stop-loss at technical levels too (below support, below SMA)
5. Take-profit needs minimum 2:1 reward-to-risk
6. Confidence must be calibrated against past performance
7. Only use >0.85 confidence with exceptional conviction

**Output:**
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

A second Claude call sees ALL 10 theses simultaneously.

**Input:**
- All 10 Pass 1 theses
- Market context
- Current portfolio holdings
- Sector exposure breakdown
- Performance history

**Key Prompt Instructions:**
1. Select TOP 3-5 trades (not all BULLISH calls)
2. Max 2 picks from the same sector
3. In bearish/crisis regimes, select 0-2 trades only
4. Consider risk/reward ratio across the portfolio
5. May adjust confidence scores based on portfolio context

**Output:**
```json
{
  "selected_tickers": ["AAPL", "LLY", "JPM"],
  "market_regime_assessment": "Normal/bullish regime...",
  "selections": [...],
  "rejections": [...],
  "portfolio_risk_notes": "Exposure analysis..."
}
```

### Why Two Passes?
- Pass 1 in isolation prevents anchoring bias between stocks
- Pass 2 adds portfolio-level thinking that per-stock analysis can't provide
- Separating concerns produces better results than one mega-prompt

---

## Agent 2: The Sentry (Gemini Flash)

### Role
Fast reactive conflict detector with three signal layers.

### Schedule
- Pre-market: 09:00 AM EST daily (14:00 UTC)
- Pre-close: 03:30 PM EST daily (20:30 UTC)

### Detection Layers

**Layer 1 - Market-Wide (no AI needed):**
- Check if SPY dropped >2% from previous close
- If yes, ALL positions flagged in the prompt as "market stress"

**Layer 2 - Price-Based (no AI needed):**
- Check if stock moved >3% against thesis since entry
- Hard override: forces ABORT regardless of Layer 3 assessment
- Catches institutional selling that precedes news

**Layer 3 - News-Based (Gemini Flash):**
- Compare today's headlines against thesis breach condition
- Receives Layer 1 and Layer 2 alerts as additional context
- Binary output: CONTINUE or ABORT

### Prompt Template
The sentry prompt now includes three alert sections:
1. Active thesis details + breach condition
2. Today's news headlines
3. **Price action alert** (current price vs entry, % move)
4. **Market-wide alert** (SPY change, stress flag)

### Why Three Layers?
- News is lagging: a stock drops 5% before the headline appears
- Price catches what news misses (insider selling, block trades)
- Market-wide catches correlated risk that per-stock analysis misses
- Each layer is independent: if one fails, others still protect

### Hard Safety Override
If Layer 2 detects a 3%+ adverse move, the system forces ABORT even if
Gemini says CONTINUE. This is a hard programmatic override because:
- Price doesn't lie; the move already happened
- Waiting for news confirmation costs more money
- Capital preservation > thesis attachment

---

## Decision Matrix (Updated)

| Weekly Thesis | Selected? | Sentry Signal | Action |
|--------------|-----------|---------------|--------|
| BULLISH | Yes | CONTINUE | Buy bracket order (if all 6 gates pass) |
| BULLISH | Yes | ABORT | Sell at market + cancel all orders |
| BULLISH | No | * | No action (filtered by Pass 2) |
| BEARISH (holding) | * | * | Sell at market (thesis flipped) |
| BEARISH (not holding) | * | * | No action |
| NEUTRAL | * | * | No action |

### Risk Gates (must ALL pass for any BUY)
1. Confidence >= 0.70
2. Not within 5 days of earnings
3. Portfolio drawdown < 8% from peak
4. Cash reserve >= 20% after trade
5. Position size valid (ATR-adjusted)
6. Sector exposure < 40% after trade

---

## Logging Requirements

Every AI decision produces a log entry with:
- Timestamp (ISO 8601)
- Agent name (analyst_pass1 / analyst_pass2 / sentry)
- Ticker symbol
- Decision made
- Full reasoning text
- Confidence score
- Additional signals (price move %, SPY change %, conflicting headlines)

Every blocked trade produces a log entry with:
- Which gate blocked it
- The blocking reason
- The thesis that was blocked
