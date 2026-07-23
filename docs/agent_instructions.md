# Agent Instructions

## Overview

TitanTrade uses two AI agents in a layered architecture. They have distinct roles,
models, and cadences — chosen to match the complexity and latency requirements of each task.

| Agent | Model | Cadence | Task |
|-------|-------|---------|------|
| The Analyst | Claude Opus/Sonnet | Weekly (Sunday 20:00 UTC) | Deep two-pass portfolio analysis |
| The Sentry | Gemini Flash | Daily (09:00 + 15:30 EST) | Fast binary conflict detection |

The Analyst sets the thesis. The Sentry watches it. They never talk to each other — their
outputs are chained via state files (`weekly_thesis.json` → `sentry_signals.json`).

For detailed prompt engineering, input schemas, and output schemas, see:
- [TitanTrade/docs/agent_instructions.md](../TitanTrade/docs/agent_instructions.md)

---

## The Analyst (Claude)

### What it does

Two-pass weekly pipeline running every Sunday before Monday market open:

- **Pass 1**: Analyzes each stock individually with full data (OHLCV, indicators, news,
  SEC filings, market context, earnings calendar, performance history). Produces a per-stock
  thesis with entry/stop/take-profit levels and a thesis breach condition.

- **Pass 2**: Sees all 10 theses simultaneously. Applies portfolio-level thinking —
  sector diversification, correlation, market regime — and selects the top 3-5 trades.

### Why two passes?

Pass 1 in isolation prevents anchoring bias (AAPL's strong thesis doesn't inflate MSFT's).
Pass 2 adds portfolio-level reasoning that per-stock analysis structurally cannot provide.
Separating concerns produces better output than a single mega-prompt.

### Core constraints

- In bearish/crisis regimes: select 0-2 trades only
- Max 2 picks from the same sector
- Minimum 2:1 reward-to-risk on every pick
- Confidence must be calibrated against past performance
- Only use >0.85 confidence with exceptional conviction

---

## The Sentry (Gemini Flash)

### What it does

Three-layer conflict detection running twice daily on active positions:

- **Layer 1 — Market-wide** (no AI): SPY drop >2% flags all positions as "market stress"
- **Layer 2 — Price-based** (no AI): Stock moved >3% against thesis → hard ABORT override
- **Layer 3 — News-based** (Gemini Flash): Compare today's headlines vs the thesis breach condition

Layer 2 is a hard programmatic override — even if Gemini says CONTINUE, a 3%+ adverse move
forces ABORT. Price doesn't lie; waiting for news confirmation costs money.

### Why three layers?

News is lagging: a stock drops 5% before the headline appears. Price catches what news misses
(insider selling, block trades). The market-wide layer catches correlated risk that per-stock
analysis misses. Each layer is independent — if one fails, others still protect.

---

## Decision Matrix

| Weekly Thesis | Selected by Pass 2? | Sentry Signal | Action |
|--------------|---------------------|---------------|--------|
| BULLISH | Yes | CONTINUE | Buy bracket order (if all 6 risk gates pass) |
| BULLISH | Yes | ABORT | Sell at market + cancel all orders |
| BULLISH | No | * | No action (filtered out) |
| BEARISH (holding) | * | * | Sell at market (thesis flipped) |
| BEARISH (not holding) | * | * | No action |
| NEUTRAL | * | * | No action |

---

## Risk Gates (ALL must pass before any BUY)

These are programmatic — the AI cannot override them.

1. Confidence >= 0.70
2. Not within 5 days of earnings
3. Portfolio drawdown < 8% from peak (values ±50% off peak are treated as broker data glitches — block + alert, Decision 054)
4. Cash reserve >= 20% after trade
5. Position size valid (ATR-adjusted, max 10%, and >= $500 notional — dust blocked, Decision 054)
6. Sector exposure < 40% after trade

---

## Logging

Every AI decision logs:
- Timestamp (ISO 8601), agent name, ticker, decision, full reasoning, confidence score
- Additional signals: price move %, SPY change %, conflicting headlines

Every blocked trade logs:
- Which gate(s) blocked it, the blocking reason, the thesis that was blocked
