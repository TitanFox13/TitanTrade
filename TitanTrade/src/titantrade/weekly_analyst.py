"""Module B: Weekly Analyst - Two-pass deep fundamental analysis via Claude API.

Pass 1: Analyze each stock individually (fundamentals + indicators + news + filings)
Pass 2: Portfolio-aware ranking - Claude sees all 10 theses + market context +
        sector exposure + performance history and selects the top 3-5 trades.

Runs Sundays at 20:00 UTC. Produces a weekly thesis for each watchlist stock.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import anthropic

from titantrade.ai_parsing import parse_ai_json, validate_ranking, validate_thesis
from titantrade.config import Config, STATE_DIR, load_config
from titantrade.cost_logger import log_cost
from titantrade.data_fetcher import build_data_bundle, save_data_bundle
from titantrade.logger import get_logger, log_decision
from titantrade.market_context import get_stock_sector
from titantrade.performance import generate_feedback_prompt, save_thesis_to_history

log = get_logger("analyst")

# ---------------------------------------------------------------------------
# Pass 1: Individual stock analysis
# ---------------------------------------------------------------------------

PASS1_SYSTEM_PROMPT = """\
You are a senior equity research analyst at a quantitative trading firm.
Your job is to produce a structured weekly trading thesis for each stock
based on fundamental data, technical indicators, news sentiment, and SEC filings.

You have access to pre-computed technical indicators. Use them - they are more
reliable than eyeballing OHLCV numbers. Pay special attention to:
- RSI extremes (< 30 oversold, > 70 overbought)
- MACD crossovers (histogram sign change)
- Price position relative to 50-day and 200-day SMA
- Bollinger Band squeeze or breakout
- Volume trend (increasing volume confirms moves)
- Relative strength vs SPY (positive RS = outperforming market)

ADVANCED SETUPS TO WATCH FOR:
- MEAN REVERSION: If RSI < 30 AND price is within 2% of 200-SMA, this is a
  potential bounce setup. Entry at or slightly below current, stop 2-3% below
  200-SMA, target the 50-SMA or upper Bollinger. Cap confidence at 0.65-0.75.
- SENTIMENT DIVERGENCE: If news is overwhelmingly bullish but price is falling
  (or vice versa), flag it. Bullish news + falling price = possible distribution
  (institutions selling). Bearish news + rising price = accumulation.
- EARNINGS RUN-UP: If earnings are 10-15 days away with no negative thesis,
  stocks tend to drift up 2-5%. Consider a short-term BULLISH call targeting
  pre-earnings drift with an exit 1-2 days before earnings.
- ANALYST MOMENTUM: Recent upgrades/downgrades and price target changes are
  strong short-term catalysts for large caps. Cluster upgrades are very bullish.
- INSIDER ACTIVITY: Cluster insider buying is one of the strongest bullish
  signals. Heavy insider selling before earnings is a red flag.

INVERSE ETFs (HEDGE INSTRUMENTS):
If you are analyzing SH, PSQ, or SDS, these are inverse ETFs that profit when
the market falls. Treat them as BULLISH in bearish market regimes — buying SH
in a bear market is equivalent to shorting the S&P 500. Apply the same technical
analysis but understand the inverse relationship. These are hedging tools, not
long-term holds — use short_term or medium_term horizon only.

You must output ONLY valid JSON. No markdown, no commentary outside JSON.
"""

PASS1_USER_TEMPLATE = """\
Analyze the following data for {ticker} ({sector} sector).

MARKET CONTEXT (do NOT ignore this - it sets the backdrop):
{market_context}

UPCOMING MACRO EVENTS (next 7 days):
{macro_events_json}

STOCK DATA:
Recent OHLCV (last 5 trading days):
{ohlcv_json}

Technical Indicators:
{indicators_json}

Relative Strength vs SPY:
{relative_strength_json}

Analyst Ratings & Price Targets:
{analyst_json}

Insider Trading (Form 4, last 30 days):
{insider_json}

News Headlines (last 7 days):
{news_json}

SEC Filings (last 24 hours):
{filings_json}

Earnings:
{earnings_json}

{performance_feedback}

INSTRUCTIONS:
1. Start with the market context. Is the broad market supportive of this trade?
   A BULLISH call into a bearish/crisis market regime needs exceptional justification.
2. Evaluate technical setup: Is price at support/resistance? RSI oversold/overbought?
   MACD momentum direction? Bollinger squeeze?
3. Assess fundamental outlook from news and filings.
4. Determine thesis: BULLISH, BEARISH, or NEUTRAL.
5. If BULLISH:
   a. target_entry_price: Set at a technically attractive level (support, SMA, etc.)
   b. stop_loss_price: {stop_loss_pct}% below entry, but also consider placing at
      a technical level (below support, below SMA, etc.)
   c. take_profit_price: Realistic upside target for the week. Aim for minimum
      2:1 reward-to-risk ratio. Set null if no clear near-term catalyst.
6. If BEARISH or NEUTRAL: set entry/stop/take_profit fields to null.
7. Define thesis_breach_condition: a specific, measurable event that invalidates
   the thesis (the daily sentry will check for this).
8. Set confidence between 0.0 and 1.0. Be honest - calibrate based on the
   performance history below. Only use >0.85 when conviction is exceptional.

9. Set hold_horizon based on the setup:
   - "short_term" (1-2 weeks): quick swing trades, momentum plays
   - "medium_term" (2-6 weeks): thesis needs time to play out, catalyst coming
   - "long_term" (6+ weeks): strong fundamental case, multi-month trend
   Choose freely — there is no forced exit. The position will be reviewed weekly.

OUTPUT FORMAT (strict JSON, no other text):
{{
  "ticker": "{ticker}",
  "sector": "{sector}",
  "thesis": "BULLISH",
  "confidence": 0.78,
  "hold_horizon": "medium_term",
  "target_entry_price": 185.50,
  "stop_loss_price": 176.23,
  "take_profit_price": 198.00,
  "thesis_breach_condition": "CEO departure or revenue guidance cut >10%",
  "key_technical_levels": {{
    "support": 183.00,
    "resistance": 192.00
  }},
  "reasoning": "Detailed multi-factor explanation here..."
}}
"""

# ---------------------------------------------------------------------------
# Pass 2: Portfolio-aware ranking and selection
# ---------------------------------------------------------------------------

PASS2_SYSTEM_PROMPT = """\
You are a portfolio manager reviewing your analyst team's individual stock theses.
Your job is to select the BEST 3-5 trades for this week, considering:
1. Individual thesis quality and conviction
2. Portfolio diversification (avoid sector concentration)
3. Market regime appropriateness
4. Risk/reward balance across the portfolio
5. Historical performance (learn from past mistakes)

You must output ONLY valid JSON. No markdown, no commentary outside JSON.
"""

PASS2_USER_TEMPLATE = """\
Your analysts have produced the following individual theses for the week:

INDIVIDUAL THESES:
{all_theses_json}

MARKET CONTEXT:
{market_context}

UPCOMING MACRO EVENTS (next 7 days):
{macro_events_json}

CURRENT PORTFOLIO HOLDINGS:
{holdings_json}

SECTOR EXPOSURE:
{sector_exposure_json}

STOCK CORRELATION MATRIX (60-day, select pairs):
{correlation_json}

{performance_feedback}

INSTRUCTIONS:
1. Review all {thesis_count} theses.
2. Select the TOP 3-5 trades for this week. Criteria:
   a. Highest conviction (confidence > 0.70 preferred)
   b. Best risk/reward ratio (take_profit distance vs stop_loss distance)
   c. Diversified across sectors (max 2 picks from same sector)
   d. Aligned with market regime (fewer BULLISH in bearish/crisis regimes)
   e. Not overlapping with existing holdings (unless adding is justified)
3. For each thesis NOT selected, briefly explain why.
4. If the market regime is "crisis" or "strong_bearish", consider selecting
   0-2 trades only (capital preservation over opportunity).
5. You may adjust confidence scores based on portfolio context.

OUTPUT FORMAT (strict JSON):
{{
  "selected_tickers": ["AAPL", "LLY", "JPM"],
  "market_regime_assessment": "The market is in a normal/bullish regime...",
  "selections": [
    {{
      "ticker": "AAPL",
      "original_confidence": 0.78,
      "adjusted_confidence": 0.75,
      "reason_selected": "Strong technical setup at 200 SMA support, diversified sector..."
    }}
  ],
  "rejections": [
    {{
      "ticker": "NVDA",
      "reason_rejected": "Already heavy in Technology sector, lower conviction than AAPL"
    }}
  ],
  "portfolio_risk_notes": "Total exposure after trades would be 45% tech, 20% financials..."
}}
"""


REVIEW_SYSTEM_PROMPT = """\
You are a senior portfolio manager reviewing an existing position.
Decide whether to CONTINUE holding, ADJUST stops/targets, or CLOSE the position.
Consider: has the thesis played out? Is momentum still intact? Has the risk/reward changed?

You must output ONLY valid JSON. No markdown, no commentary outside JSON.
"""

REVIEW_USER_TEMPLATE = """\
Review the existing BULLISH position in {ticker} ({sector} sector).

ORIGINAL THESIS (from when the position was opened):
{original_thesis_json}

CURRENT POSITION:
  Entry price: ${entry_price}
  Current price: ${current_price}
  Unrealized P&L: {pnl_pct}%
  Days held: {days_held}
  Current hold horizon: {hold_horizon}

CURRENT MARKET REGIME: {current_regime}

{regime_warning}

UPDATED MARKET CONTEXT:
{market_context}

UPDATED TECHNICAL INDICATORS:
{indicators_json}

UPDATED NEWS (last 7 days):
{news_json}

ANALYST RATINGS:
{analyst_json}

{performance_feedback}

INSTRUCTIONS:
1. Evaluate whether the original thesis is still valid.
2. REGIME CHECK: If a regime warning is present above, weigh it heavily.
   Holding an inverse ETF in a bullish/neutral regime is a strategic
   contradiction. Default to CLOSE unless there is an exceptional
   short-term catalyst for continued market decline.
3. Check if the risk/reward has changed (e.g., price near take-profit, stop too far).
4. Consider whether the hold horizon should change (short_term / medium_term / long_term).
5. Decide:
   - CONTINUE: thesis intact, keep holding with current levels
   - ADJUST: thesis intact but stop-loss or take-profit should be updated
   - CLOSE: thesis invalidated, or target reached, or risk/reward no longer favorable

OUTPUT FORMAT (strict JSON):
{{
  "ticker": "{ticker}",
  "review_action": "CONTINUE",
  "thesis": "BULLISH",
  "confidence": 0.82,
  "hold_horizon": "medium_term",
  "stop_loss_price": null,
  "take_profit_price": null,
  "reasoning": "Position is working. Trailing stop protecting gains. Maintain hold."
}}

If review_action is ADJUST, set stop_loss_price and/or take_profit_price to the new values.
If review_action is CLOSE, set thesis to the current view (BEARISH/NEUTRAL) with reasoning.
"""


def _call_claude(system: str, user: str, cfg: Config, cost_label: str = "") -> str:
    """Make a Claude API call, log token usage, and return the raw response text."""
    client = anthropic.Anthropic(api_key=cfg.claude.key)

    message = client.messages.create(
        model=cfg.claude.model,
        max_tokens=cfg.claude.max_tokens,
        temperature=cfg.claude.temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    # Log token usage and estimated cost
    usage = message.usage
    log_cost(
        service="claude",
        model=cfg.claude.model,
        description=cost_label or "Claude API call",
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        run_type="weekly_analyst",
    )

    return message.content[0].text


def analyze_stock(
    ticker: str,
    stock_data: dict[str, Any],
    market_ctx: dict[str, Any],
    performance_text: str,
    cfg: Config,
    macro_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pass 1: Analyze a single stock with full context.

    Returns a validated thesis dict. On parse failure, returns a NEUTRAL thesis.
    """
    sector = get_stock_sector(ticker)

    prompt = PASS1_USER_TEMPLATE.format(
        ticker=ticker,
        sector=sector,
        market_context=json.dumps(market_ctx, indent=2),
        macro_events_json=json.dumps(macro_events or [], indent=2),
        ohlcv_json=json.dumps(stock_data.get("ohlcv_recent", []), indent=2),
        indicators_json=json.dumps(stock_data.get("technical_indicators", {}), indent=2),
        relative_strength_json=json.dumps(stock_data.get("relative_strength_vs_spy", {}), indent=2),
        analyst_json=json.dumps(stock_data.get("analyst_ratings", {}), indent=2),
        insider_json=json.dumps(stock_data.get("insider_trades", []), indent=2),
        news_json=json.dumps(stock_data.get("news", [])[:20], indent=2),
        filings_json=json.dumps(stock_data.get("sec_filings", []), indent=2),
        earnings_json=json.dumps(stock_data.get("earnings", {}), indent=2),
        performance_feedback=performance_text,
        stop_loss_pct=int(cfg.trading.stop_loss_pct * 100),
    )

    log.info(f"Pass 1: Analyzing {ticker} ({sector})")
    raw_response = _call_claude(PASS1_SYSTEM_PROMPT, prompt, cfg, cost_label=f"Weekly Pass 1: {ticker}")

    try:
        parsed = parse_ai_json(raw_response, context=f"Pass 1 thesis for {ticker}")
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected dict, got {type(parsed).__name__}")
        thesis = validate_thesis(parsed, ticker)
    except (ValueError, TypeError) as exc:
        log.error(f"Pass 1 parse/validation failed for {ticker}: {exc}")
        thesis = validate_thesis({"ticker": ticker, "thesis": "NEUTRAL"}, ticker)
        thesis["reasoning"] = f"Analysis failed: {exc}"

    log_decision(
        logger=log,
        agent="analyst_pass1",
        ticker=ticker,
        decision=thesis["thesis"],
        reasoning=thesis["reasoning"],
        extra={"confidence": thesis["confidence"], "sector": sector},
    )

    return thesis


def rank_and_select(
    all_theses: list[dict[str, Any]],
    market_ctx: dict[str, Any],
    holdings: list[dict[str, Any]],
    sector_exposure: dict[str, float],
    performance_text: str,
    cfg: Config,
    macro_events: list[dict[str, Any]] | None = None,
    correlation_matrix: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Pass 2: Portfolio-aware ranking of all theses.

    On parse failure, falls back to selecting all BULLISH theses.
    """
    prompt = PASS2_USER_TEMPLATE.format(
        all_theses_json=json.dumps(all_theses, indent=2),
        market_context=json.dumps(market_ctx, indent=2),
        macro_events_json=json.dumps(macro_events or [], indent=2),
        holdings_json=json.dumps(holdings, indent=2),
        sector_exposure_json=json.dumps(sector_exposure, indent=2),
        correlation_json=json.dumps(correlation_matrix or {}, indent=2),
        performance_feedback=performance_text,
        thesis_count=len(all_theses),
    )

    log.info(f"Pass 2: Ranking {len(all_theses)} theses")
    raw_response = _call_claude(PASS2_SYSTEM_PROMPT, prompt, cfg, cost_label="Weekly Pass 2: Portfolio ranking")

    try:
        parsed = parse_ai_json(raw_response, context="Pass 2 portfolio ranking")
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected dict, got {type(parsed).__name__}")
        ranking = validate_ranking(parsed)
    except (ValueError, TypeError) as exc:
        log.error(f"Pass 2 parse/validation failed: {exc} - falling back to all BULLISH")
        ranking = validate_ranking({
            "selected_tickers": [
                t["ticker"] for t in all_theses if t.get("thesis") == "BULLISH"
            ],
            "market_regime_assessment": f"Pass 2 failed ({exc}), using all BULLISH",
        })

    selected = ranking["selected_tickers"]
    log.info(f"Pass 2 selected: {selected}")

    log_decision(
        logger=log,
        agent="analyst_pass2",
        ticker="PORTFOLIO",
        decision=f"Selected {len(selected)} trades: {selected}",
        reasoning=ranking.get("market_regime_assessment", ""),
    )

    return ranking


def review_position(
    ticker: str,
    existing_thesis: dict[str, Any],
    position: dict[str, Any],
    stock_data: dict[str, Any],
    market_ctx: dict[str, Any],
    performance_text: str,
    cfg: Config,
) -> dict[str, Any]:
    """Review an existing held position. Returns a thesis with review_action set."""
    sector = get_stock_sector(ticker)
    entry_price = float(position.get("avg_entry_price", 0))
    current_price = float(position.get("current_price", 0))
    entry_date = position.get("entry_date", existing_thesis.get("generated_at", ""))

    pnl_pct = round((current_price - entry_price) / entry_price * 100, 2) if entry_price else 0
    days_held = 0
    if entry_date:
        try:
            from datetime import datetime, timezone
            entry_dt = datetime.fromisoformat(entry_date.replace("Z", "+00:00")) if "T" in entry_date else datetime.strptime(entry_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_held = (datetime.now(timezone.utc) - entry_dt).days
        except (ValueError, TypeError):
            pass

    regime = market_ctx.get("market_regime", "neutral")
    is_hedge = ticker in cfg.trading.hedge_instruments
    regime_warning = ""
    if is_hedge and regime not in ("bearish", "strong_bearish", "crisis"):
        regime_warning = (
            f"WARNING: {ticker} is an INVERSE ETF (hedge instrument) that profits "
            f"from market declines. The current market regime is '{regime}', which "
            f"does NOT support holding inverse positions. Consider CLOSING."
        )

    prompt = REVIEW_USER_TEMPLATE.format(
        ticker=ticker,
        sector=sector,
        original_thesis_json=json.dumps(existing_thesis, indent=2),
        entry_price=f"{entry_price:.2f}",
        current_price=f"{current_price:.2f}",
        pnl_pct=f"{pnl_pct:+.2f}",
        days_held=days_held,
        hold_horizon=existing_thesis.get("hold_horizon", "short_term"),
        current_regime=regime,
        regime_warning=regime_warning,
        market_context=json.dumps(market_ctx, indent=2),
        indicators_json=json.dumps(stock_data.get("technical_indicators", {}), indent=2),
        news_json=json.dumps(stock_data.get("news", [])[:15], indent=2),
        analyst_json=json.dumps(stock_data.get("analyst_ratings", {}), indent=2),
        performance_feedback=performance_text,
    )

    log.info(f"Reviewing held position: {ticker} ({pnl_pct:+.1f}%, {days_held}d held)")
    raw = _call_claude(REVIEW_SYSTEM_PROMPT, prompt, cfg, cost_label=f"Weekly Review: {ticker}")

    try:
        parsed = parse_ai_json(raw, context=f"Position review for {ticker}")
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected dict, got {type(parsed).__name__}")
        thesis = validate_thesis(parsed, ticker, is_review=True)
    except (ValueError, TypeError) as exc:
        log.error(f"Position review parse failed for {ticker}: {exc}")
        thesis = validate_thesis({
            "ticker": ticker, "thesis": "BULLISH", "review_action": "CONTINUE",
            "hold_horizon": existing_thesis.get("hold_horizon", "short_term"),
        }, ticker, is_review=True)
        thesis["reasoning"] = f"Review parse failed: {exc} — defaulting to CONTINUE"

    # Carry forward original levels if not adjusted
    if thesis["review_action"] != "ADJUST":
        thesis["target_entry_price"] = existing_thesis.get("target_entry_price")
        thesis["stop_loss_price"] = existing_thesis.get("stop_loss_price")
        thesis["take_profit_price"] = existing_thesis.get("take_profit_price")
    else:
        # For ADJUST: use new levels if provided, fall back to original
        thesis["target_entry_price"] = existing_thesis.get("target_entry_price")
        if thesis["stop_loss_price"] is None:
            thesis["stop_loss_price"] = existing_thesis.get("stop_loss_price")
        if thesis["take_profit_price"] is None:
            thesis["take_profit_price"] = existing_thesis.get("take_profit_price")

    thesis["thesis_breach_condition"] = existing_thesis.get("thesis_breach_condition", "")
    thesis["key_technical_levels"] = existing_thesis.get("key_technical_levels", {})

    log_decision(
        logger=log,
        agent="analyst_review",
        ticker=ticker,
        decision=f"{thesis['review_action']} ({thesis['hold_horizon']})",
        reasoning=thesis["reasoning"],
        extra={"confidence": thesis["confidence"], "pnl_pct": pnl_pct, "days_held": days_held},
    )

    return thesis


def _load_current_holdings(cfg: Config) -> list[dict[str, Any]]:
    """Load current Alpaca positions (or empty if unavailable)."""
    from titantrade.executor import get_positions
    try:
        return get_positions(cfg)
    except Exception:
        return []


def run_weekly_analysis(cfg: Config) -> dict[str, Any]:
    """Run the full two-pass weekly analysis pipeline."""
    log.info("=" * 60)
    log.info("Starting weekly analysis pipeline (two-pass)")
    log.info("=" * 60)

    # Step 1: Fetch all data (prices, indicators, news, filings, market, earnings)
    log.info("Step 1: Fetching data bundle")
    bundle = build_data_bundle(cfg)
    save_data_bundle(bundle)
    market_ctx = bundle.get("market_context", {})

    # Step 2: Generate performance feedback for Claude
    log.info("Step 2: Generating performance feedback")
    performance_text = generate_feedback_prompt(weeks=4)

    # Step 3: Split into held positions (review) and new candidates (analyze)
    log.info("Step 3: Pass 1 - Individual analysis + position reviews")
    macro_events = bundle.get("economic_calendar", [])
    holdings = _load_current_holdings(cfg)
    held_tickers = {p["symbol"] for p in holdings}
    positions_by_ticker = {p["symbol"]: p for p in holdings}

    # Load previous thesis for review context
    prev_thesis_doc = {}
    prev_path = STATE_DIR / "weekly_thesis.json"
    if prev_path.exists():
        with open(prev_path) as f:
            prev_thesis_doc = json.load(f)
    prev_theses = {t["ticker"]: t for t in prev_thesis_doc.get("theses", [])}

    # In bearish/crisis regimes, also analyze hedge instruments (inverse ETFs)
    regime = market_ctx.get("market_regime", "neutral")
    analysis_tickers = list(cfg.trading.watchlist)
    if regime in ("bearish", "strong_bearish", "crisis"):
        hedge_tickers = [h for h in cfg.trading.hedge_instruments if h not in analysis_tickers]
        if hedge_tickers:
            log.info(f"Bearish regime ({regime}): adding hedge instruments {hedge_tickers}")
            analysis_tickers.extend(hedge_tickers)
            # Fetch data for hedge instruments
            for h in hedge_tickers:
                if h not in bundle["stocks"]:
                    try:
                        from titantrade.data_fetcher import build_stock_data
                        bundle["stocks"][h] = build_stock_data(h, cfg)
                        bundle["stocks"][h]["earnings"] = {}
                    except Exception as exc:
                        log.warning(f"Failed to fetch hedge data for {h}: {exc}")

    all_theses: list[dict[str, Any]] = []
    for ticker in analysis_tickers:
        stock_data = bundle["stocks"].get(ticker, {})
        if stock_data.get("error"):
            log.warning(f"Skipping {ticker} due to data fetch error")
            continue

        try:
            if ticker in held_tickers and ticker in prev_theses:
                # REVIEW PATH: existing position with prior thesis
                thesis = review_position(
                    ticker, prev_theses[ticker], positions_by_ticker[ticker],
                    stock_data, market_ctx, performance_text, cfg,
                )
            else:
                # NEW CANDIDATE PATH: standard analysis
                thesis = analyze_stock(ticker, stock_data, market_ctx, performance_text, cfg, macro_events)
            all_theses.append(thesis)
        except Exception as exc:
            log.error(f"Pass 1 analysis failed for {ticker}: {exc}")

    # Step 4: Pass 2 - Portfolio-aware ranking (only ranks NEW candidates)
    log.info("Step 4: Pass 2 - Portfolio ranking and selection")
    sector_exposure: dict[str, float] = {}
    for pos in holdings:
        sym = pos.get("symbol", "")
        sector = get_stock_sector(sym)
        mv = abs(float(pos.get("market_value", 0)))
        sector_exposure[sector] = sector_exposure.get(sector, 0) + mv

    try:
        ranking = rank_and_select(
            all_theses, market_ctx, holdings, sector_exposure, performance_text, cfg,
            macro_events=macro_events,
            correlation_matrix=bundle.get("correlation_matrix", {}),
        )
        selected_tickers = set(ranking.get("selected_tickers", []))
    except Exception as exc:
        log.error(f"Pass 2 ranking failed: {exc} - using all BULLISH theses")
        ranking = {}
        selected_tickers = {t["ticker"] for t in all_theses if t.get("thesis") == "BULLISH"}

    # Step 5: Mark selection status
    for thesis in all_theses:
        if thesis.get("review_action") in ("CONTINUE", "ADJUST"):
            # Reviewed positions that are still held are automatically "selected"
            thesis["selected_for_trading"] = True
        elif thesis.get("review_action") == "CLOSE":
            thesis["selected_for_trading"] = False
        else:
            thesis["selected_for_trading"] = thesis["ticker"] in selected_tickers
        # Update confidence if Pass 2 adjusted it
        for sel in ranking.get("selections", []):
            if sel["ticker"] == thesis["ticker"]:
                thesis["adjusted_confidence"] = sel.get("adjusted_confidence", thesis.get("confidence"))

    # Step 6: Build and save weekly thesis document
    now = datetime.now(timezone.utc)
    weekly_thesis = {
        "generated_at": now.isoformat(),
        "next_review_at": (now + timedelta(days=7)).isoformat(),
        "market_regime": market_ctx.get("market_regime", "unknown"),
        "ranking": ranking,
        "theses": all_theses,
    }

    path = STATE_DIR / "weekly_thesis.json"
    with open(path, "w") as f:
        json.dump(weekly_thesis, f, indent=2)

    # Step 7: Archive to thesis history for performance tracking
    save_thesis_to_history(weekly_thesis)

    selected_count = sum(1 for t in all_theses if t.get("selected_for_trading"))
    bullish_count = sum(1 for t in all_theses if t.get("thesis") == "BULLISH")
    log.info(
        f"Weekly analysis complete: {len(all_theses)} analyzed, "
        f"{bullish_count} BULLISH, {selected_count} selected for trading"
    )

    return weekly_thesis


def main() -> None:
    """Entry point for weekly analyst."""
    cfg = load_config()
    result = run_weekly_analysis(cfg)
    selected = [t["ticker"] for t in result["theses"] if t.get("selected_for_trading")]
    regime = result.get("market_regime", "unknown")
    print(f"Market regime: {regime}")
    print(f"Selected for trading: {selected}")
    print(f"Total theses: {len(result['theses'])}")


if __name__ == "__main__":
    main()
