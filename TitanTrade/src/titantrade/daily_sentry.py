"""Module C: Daily Sentry - Multi-signal conflict detection via Gemini Flash.

Three detection layers (not just news anymore):
  1. NEWS-BASED: Does today's news contradict the weekly thesis?
  2. PRICE-BASED: Has the stock moved >3% against the thesis since entry?
  3. MARKET-WIDE: Has SPY dropped >2%? If so, flag ALL positions for review.

Runs daily at 09:00 AM and 03:30 PM EST.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from titantrade.ai_parsing import parse_ai_json, validate_sentry_signal
from titantrade.config import Config, STATE_DIR, load_config
from titantrade.cost_logger import log_cost
from titantrade.data_fetcher import fetch_news
from titantrade.logger import get_logger, log_decision
from titantrade.notifier import notify_sentry_degraded
from titantrade.retry import fetch_with_retry

log = get_logger("sentry")

# Thresholds
PRICE_MOVE_ABORT_PCT = 3.0   # "Adverse move" warning threshold (sets price_check.adverse_move)
PRICE_MOVE_HARD_ABORT_PCT = 5.0  # Catastrophic: always ABORT regardless of news
MARKET_DROP_ALERT_PCT = 2.0  # Alert if SPY drops 2%+ intraday

SENTRY_PROMPT_TEMPLATE = """\
You are a financial news conflict detector. Your job is to determine if
today's news contradicts or invalidates an existing trading thesis.

ACTIVE THESIS FOR {ticker}:
- Direction: {thesis}
- Confidence: {confidence}
- Thesis Breach Condition: {breach_condition}
- Reasoning: {reasoning}

TODAY'S NEWS HEADLINES:
{news_json}

PRICE ACTION ALERT:
{price_alert}

MARKET-WIDE ALERT:
{market_alert}

INSTRUCTIONS:
1. Compare each news headline against the thesis breach condition.
2. Check for material events: earnings surprises, executive changes,
   regulatory actions, product recalls, major lawsuits, guidance changes.
3. Consider the price action alert - a large adverse move with no news may
   indicate information leakage or institutional selling.
4. Consider the market-wide alert - broad market stress affects all positions.
5. Output your decision:
   - "ABORT" if ANY signal materially contradicts the thesis
   - "CONTINUE" if news and price action are neutral or supportive
6. Be conservative: when in doubt about material impact, lean toward ABORT.
   Preserving capital is more important than catching every move.

OUTPUT FORMAT: a JSON object with the following fields (the Gemini API will
enforce the schema; do not emit markdown fences):
  - ticker: the stock symbol you are analyzing
  - signal: "CONTINUE" or "ABORT"
  - conflicting_headlines: array of headline strings that contradict the thesis (empty if none)
  - price_concern: true if an adverse price move is a factor in your decision
  - market_concern: true if a broad-market stress is a factor in your decision
  - reasoning: a concise (2-3 sentence) explanation of your decision
"""


def load_weekly_thesis() -> dict[str, Any] | None:
    """Load the active weekly thesis from state."""
    path = STATE_DIR / "weekly_thesis.json"
    if not path.exists():
        log.warning("No weekly thesis found - run weekly_analyst first")
        return None

    with open(path) as f:
        thesis_doc = json.load(f)

    # Log if overdue for review (Sunday analysis may have failed)
    next_review = thesis_doc.get("next_review_at", "")
    if next_review:
        try:
            review_dt = datetime.fromisoformat(next_review)
            if datetime.now(timezone.utc) > review_dt:
                log.warning("Thesis is overdue for weekly review — sentry still running")
        except (ValueError, TypeError):
            pass

    return thesis_doc


def _fetch_current_price(ticker: str, cfg: Config) -> float | None:
    """Fetch the current price using FMP quote endpoint (lightweight, no history)."""
    url = "https://financialmodelingprep.com/stable/quote"
    params = {"symbol": ticker, "apikey": cfg.fmp.key}
    try:
        resp = fetch_with_retry("GET", url, params=params)
        data = resp.json()
        if data and isinstance(data, list) and data[0].get("price"):
            return float(data[0]["price"])
    except Exception as exc:
        log.warning(f"Quote fetch failed for {ticker}: {exc}")
    return None


def _fetch_spy_quote(cfg: Config) -> float | None:
    """Fetch SPY's daily change percentage via quote endpoint.

    FMP stable/quote returns ``changePercentage`` (no trailing "s").
    Falls back to computing from price/previousClose if the field is missing.
    """
    url = "https://financialmodelingprep.com/stable/quote"
    params = {"symbol": "SPY", "apikey": cfg.fmp.key}
    try:
        resp = fetch_with_retry("GET", url, params=params)
        data = resp.json()
        if data and isinstance(data, list):
            quote = data[0]
            # FMP stable API field is "changePercentage" (verified 2026-04-05)
            change_pct = quote.get("changePercentage")
            if change_pct is not None:
                return round(float(change_pct), 2)
            # Fallback: compute from price and previousClose
            price = quote.get("price", 0)
            prev_close = quote.get("previousClose", 0)
            if price and prev_close:
                return round((float(price) - float(prev_close)) / float(prev_close) * 100, 2)
    except Exception as exc:
        log.warning(f"SPY quote fetch failed: {exc}")
    return None


def _check_price_move(
    ticker: str,
    thesis: dict[str, Any],
    cfg: Config,
    position: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check if the stock has moved adversely since the reference entry price.

    When we hold a position, use ``avg_entry_price`` from the broker (the
    actual cost basis after both tranches filled). Otherwise fall back to
    the thesis's ``target_entry_price``. This matters because for a position
    that's been held for weeks and is up 20%, a 3% pullback from the high
    should NOT register as "down 3% from entry" — it should reference the
    real entry, not the stale Sunday thesis level.

    Uses the lightweight quote endpoint (1 API call) instead of historical bars.
    """
    direction = thesis.get("thesis", "NEUTRAL")
    # Prefer real broker avg_entry_price when we hold the position
    entry_price = None
    if position:
        try:
            entry_price = float(position.get("avg_entry_price", 0)) or None
        except (TypeError, ValueError):
            entry_price = None
    if entry_price is None:
        entry_price = thesis.get("target_entry_price")

    if not entry_price or direction == "NEUTRAL":
        return {"adverse_move": False, "move_pct": 0, "alert": "No entry price to compare"}

    current_price = _fetch_current_price(ticker, cfg)
    if current_price is None:
        return {"adverse_move": False, "move_pct": 0, "alert": "Price fetch failed"}

    move_pct = (current_price - entry_price) / entry_price * 100

    # For BULLISH thesis, a drop is adverse
    adverse = False
    if direction == "BULLISH" and move_pct <= -PRICE_MOVE_ABORT_PCT:
        adverse = True
    elif direction == "BEARISH" and move_pct >= PRICE_MOVE_ABORT_PCT:
        adverse = True

    alert = (
        f"Current price ${current_price:.2f} vs entry ${entry_price:.2f} "
        f"({move_pct:+.1f}%). {'ADVERSE MOVE DETECTED' if adverse else 'Within normal range'}"
    )

    return {
        "adverse_move": adverse,
        "move_pct": round(move_pct, 2),
        "current_price": current_price,
        "alert": alert,
    }


def _check_market_wide(cfg: Config) -> dict[str, Any]:
    """Check if the broad market (SPY) has had a significant drop.

    Uses the lightweight quote endpoint (1 call) which includes changesPercentage.
    """
    change_pct = _fetch_spy_quote(cfg)

    if change_pct is None:
        return {"market_stress": False, "spy_change_pct": 0, "alert": "SPY quote unavailable"}

    stress = change_pct <= -MARKET_DROP_ALERT_PCT
    alert = (
        f"SPY: {change_pct:+.1f}% today. "
        f"{'MARKET STRESS DETECTED' if stress else 'Market within normal range'}"
    )

    return {
        "market_stress": stress,
        "spy_change_pct": round(change_pct, 2),
        "alert": alert,
    }


# JSON schema that Gemini's structured-output mode will enforce. This
# guarantees the response is a valid JSON object with exactly these fields —
# eliminating the truncated-string parse failures we used to repair
# post-hoc. The schema shape matches ``SENTRY_DEFAULTS`` in ai_parsing.py.
_SENTRY_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "ticker": {"type": "STRING"},
        "signal": {"type": "STRING", "enum": ["CONTINUE", "ABORT"]},
        "conflicting_headlines": {"type": "ARRAY", "items": {"type": "STRING"}},
        "price_concern": {"type": "BOOLEAN"},
        "market_concern": {"type": "BOOLEAN"},
        "reasoning": {"type": "STRING"},
    },
    "required": [
        "ticker", "signal", "conflicting_headlines",
        "price_concern", "market_concern", "reasoning",
    ],
}


def _call_gemini(prompt: str, cfg: Config, cost_label: str = "") -> str:
    """Make a Gemini Flash API call, log token usage, and return the raw response text.

    Uses Gemini's structured-output mode (``responseMimeType=application/json``
    plus a ``responseSchema``) so the response is guaranteed valid JSON with
    the sentry fields we expect. Also disables ``thinking`` tokens, which
    on gemini-2.5-flash otherwise burn hundreds of tokens for a trivial
    classification task.
    """
    url = (
        f"https://generativelanguage.googleapis.com/v1beta"
        f"/models/{cfg.gemini.model}:generateContent"
    )
    params = {"key": cfg.gemini.key}
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": cfg.gemini.temperature,
            "maxOutputTokens": cfg.gemini.max_tokens,
            "responseMimeType": "application/json",
            "responseSchema": _SENTRY_SCHEMA,
            # thinkingBudget=0 disables chain-of-thought token usage.
            # gemini-2.5-flash defaults to "thinking" which can consume
            # hundreds of hidden tokens before producing any output.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    resp = fetch_with_retry("POST", url, params=params, json_body=body)
    data = resp.json()

    # Log token usage from Gemini response metadata
    usage_meta = data.get("usageMetadata", {})
    input_tokens = usage_meta.get("promptTokenCount", 0)
    output_tokens = usage_meta.get("candidatesTokenCount", 0)
    if input_tokens or output_tokens:
        log_cost(
            service="gemini",
            model=cfg.gemini.model,
            description=cost_label or "Gemini API call",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            run_type="daily_sentry",
        )

    return (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )


def check_stock(
    ticker: str,
    thesis: dict[str, Any],
    news: list[dict[str, Any]],
    price_check: dict[str, Any],
    market_check: dict[str, Any],
    cfg: Config,
) -> dict[str, Any]:
    """Run the full sentry check for one stock using Gemini Flash.

    On parse failure, defaults to CONTINUE (don't sell on errors).
    Price-based override can still force ABORT regardless.
    """
    prompt = SENTRY_PROMPT_TEMPLATE.format(
        ticker=ticker,
        thesis=thesis.get("thesis", "NEUTRAL"),
        confidence=thesis.get("confidence", 0),
        breach_condition=thesis.get("thesis_breach_condition", "None specified"),
        reasoning=thesis.get("reasoning", ""),
        news_json=json.dumps(news, indent=2),
        price_alert=price_check.get("alert", "No data"),
        market_alert=market_check.get("alert", "No data"),
    )

    log.info(f"Sentry checking {ticker}")
    raw_response = _call_gemini(prompt, cfg, cost_label=f"Daily sentry: {ticker}")

    try:
        parsed = parse_ai_json(raw_response, context=f"Sentry signal for {ticker}")
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected dict, got {type(parsed).__name__}")
        signal = validate_sentry_signal(parsed, ticker)
    except (ValueError, TypeError) as exc:
        log.error(f"Sentry parse/validation failed for {ticker}: {exc}")
        signal = validate_sentry_signal({"ticker": ticker}, ticker)
        signal["reasoning"] = f"Gemini parse failed: {exc} - defaulting to CONTINUE"

    # Price-based override.
    #
    # Previously: ANY adverse move >= 3% forced ABORT regardless of Gemini.
    # Production showed this was too aggressive — single-stock 3% intraday
    # moves on no news happen constantly in a normal-to-bullish market, and
    # we were churning positions on noise (DASH/DECK/LLY each round-tripped
    # multiple times in a single week).
    #
    # New policy — graduated by severity:
    #   - >= 5% adverse: catastrophic, always ABORT (regardless of news)
    #   - 3-5% adverse + Gemini flagged news concern: confirmed ABORT
    #   - 3-5% adverse + Gemini clean: WARN but don't override CONTINUE
    #     (likely noise — let our broker-side stop handle a real breakdown)
    move_pct = price_check.get("move_pct", 0) or 0
    is_adverse = price_check.get("adverse_move", False)
    is_catastrophic = move_pct <= -PRICE_MOVE_HARD_ABORT_PCT
    has_news_concern = (
        len(signal.get("conflicting_headlines") or []) > 0
        or bool(signal.get("price_concern"))
        or bool(signal.get("market_concern"))
    )

    if is_catastrophic and signal["signal"] != "ABORT":
        log.warning(
            f"Catastrophic price-based ABORT for {ticker}: "
            f"{move_pct:+.1f}% (>= {PRICE_MOVE_HARD_ABORT_PCT}% hard threshold)"
        )
        signal["signal"] = "ABORT"
        signal["price_concern"] = True
        signal["reasoning"] = (
            f"PRICE-BASED HARD ABORT: {move_pct:+.1f}% adverse move exceeds "
            f"{PRICE_MOVE_HARD_ABORT_PCT}% catastrophic threshold. "
            f"Original Gemini assessment: {signal.get('reasoning', '')}"
        )
    elif is_adverse and has_news_concern and signal["signal"] != "ABORT":
        log.warning(
            f"News-confirmed price ABORT for {ticker}: "
            f"{move_pct:+.1f}% adverse move with Gemini news concerns"
        )
        signal["signal"] = "ABORT"
        signal["price_concern"] = True
        signal["reasoning"] = (
            f"PRICE-BASED OVERRIDE: {move_pct:+.1f}% adverse move "
            f"confirmed by Gemini news/market concerns. "
            f"Original Gemini assessment: {signal.get('reasoning', '')}"
        )
    elif is_adverse and signal["signal"] != "ABORT":
        # 3-5% adverse move with NO news concern → likely noise. Don't ABORT.
        # The broker-side stop-loss (typically 5-7% below entry) still protects
        # against real breakdowns. We trade some sensitivity for less churn.
        log.warning(
            f"Adverse price move for {ticker} ({move_pct:+.1f}%) "
            f"but Gemini found no news concerns — NOT aborting (likely noise)"
        )
        signal["price_concern"] = True
        signal["reasoning"] = (
            f"PRICE NOISE WARNING: {move_pct:+.1f}% adverse move with no news "
            f"corroboration — broker-side stop will catch real breakdowns. "
            f"Original Gemini assessment: {signal.get('reasoning', '')}"
        )

    log_decision(
        logger=log,
        agent="sentry",
        ticker=ticker,
        decision=signal["signal"],
        reasoning=signal["reasoning"],
        extra={
            "conflicting_headlines": signal["conflicting_headlines"],
            "price_concern": signal["price_concern"],
            "market_concern": signal["market_concern"],
            "price_move_pct": price_check.get("move_pct", 0),
            "spy_change_pct": market_check.get("spy_change_pct", 0),
        },
    )

    return signal


def run_daily_sentry(cfg: Config) -> dict[str, Any]:
    """Run the daily sentry check for all watchlist stocks.

    Three detection layers:
    1. Market-wide health check (SPY)
    2. Per-stock price move check
    3. Per-stock news vs thesis check (Gemini Flash)
    """
    log.info("=" * 60)
    log.info("Starting daily sentry run")
    log.info("=" * 60)

    # Load active thesis
    thesis_doc = load_weekly_thesis()
    if thesis_doc is None:
        return {"signals": [], "error": "No valid weekly thesis"}

    # Index theses by ticker
    theses_by_ticker = {
        t["ticker"]: t for t in thesis_doc.get("theses", [])
    }

    # Layer 1: Market-wide check (run once, applies to all)
    log.info("Layer 1: Market-wide health check")
    market_check = _check_market_wide(cfg)
    if market_check["market_stress"]:
        log.warning(
            f"MARKET STRESS: SPY {market_check['spy_change_pct']:+.1f}% - "
            f"all positions flagged for review"
        )

    # Pull current positions so the price-move check can use the real
    # broker avg_entry_price for held positions instead of the stale Sunday
    # thesis target.
    try:
        from titantrade.executor import get_positions
        positions_by_ticker: dict[str, dict[str, Any]] = {
            p.get("symbol", ""): p for p in get_positions(cfg)
        }
    except Exception as exc:  # noqa: BLE001 — sentry must run regardless
        log.warning(f"Could not fetch positions for sentry: {exc}")
        positions_by_ticker = {}

    signals: list[dict[str, Any]] = []

    for ticker in cfg.trading.watchlist:
        thesis = theses_by_ticker.get(ticker)
        if thesis is None:
            log.info(f"No thesis for {ticker} - skipping")
            continue

        # Skip NEUTRAL stocks (nothing to protect)
        if thesis.get("thesis") == "NEUTRAL":
            signals.append({
                "ticker": ticker,
                "signal": "CONTINUE",
                "conflicting_headlines": [],
                "price_concern": False,
                "market_concern": False,
                "reasoning": "Thesis is NEUTRAL - no action needed",
            })
            continue

        # Skip tickers we're not actively trading. This covers two cases:
        #   1. Pass-2 portfolio ranking didn't select this candidate.
        #   2. A prior weekly review set review_action=CLOSE and the position
        #      was already closed by orphan_close — we don't want the sentry
        #      to keep generating ghost ABORTs for a ticker we don't hold.
        if not thesis.get("selected_for_trading", True):
            signals.append({
                "ticker": ticker,
                "signal": "CONTINUE",
                "conflicting_headlines": [],
                "price_concern": False,
                "market_concern": False,
                "reasoning": "Not selected for trading — sentry check skipped",
            })
            continue

        # Layer 2: Price-based check (uses broker avg_entry_price when held)
        log.info(f"Layer 2: Price check for {ticker}")
        price_check = _check_price_move(
            ticker, thesis, cfg, position=positions_by_ticker.get(ticker),
        )

        # Layer 3: News-based check (Gemini)
        try:
            news = fetch_news(ticker, cfg, limit=20)
            signal = check_stock(ticker, thesis, news, price_check, market_check, cfg)
            signals.append(signal)
        except Exception as exc:
            log.error(f"Sentry check failed for {ticker}: {exc}")
            # On failure: default to CONTINUE for BULLISH (don't sell on errors),
            # but if price has moved adversely, force ABORT even on error
            fallback_signal = "ABORT" if price_check.get("adverse_move") else "CONTINUE"
            signals.append({
                "ticker": ticker,
                "signal": fallback_signal,
                "conflicting_headlines": [],
                "price_concern": price_check.get("adverse_move", False),
                "market_concern": market_check.get("market_stress", False),
                "reasoning": f"Sentry check failed: {exc} - fallback to {fallback_signal}",
            })

    # Determine run type
    now = datetime.now(timezone.utc)
    hour = now.hour
    run_type = "pre_market" if hour < 16 else "pre_close"

    # Count fallback signals: sentry calls that failed and defaulted via the
    # exception path. These leave a tell-tale string in `reasoning`.
    fallback_count = sum(
        1 for s in signals
        if "Sentry check failed" in str(s.get("reasoning", ""))
    )
    # Sentry checks that actually ran Gemini (skipped NEUTRAL/non-selected
    # tickers produce synthetic CONTINUE signals but no LLM call). The simplest
    # proxy is "not a skip-placeholder reasoning".
    ran_count = sum(
        1 for s in signals
        if s.get("reasoning") not in (
            "Thesis is NEUTRAL - no action needed",
            "Not selected for trading — sentry check skipped",
        )
    )
    fallback_ratio = (fallback_count / ran_count) if ran_count else 0.0

    result = {
        "generated_at": now.isoformat(),
        "run_type": run_type,
        "market_health": market_check,
        "signals": signals,
        "failures": {
            "fallback_count": fallback_count,
            "checks_run": ran_count,
            "fallback_ratio": round(fallback_ratio, 3),
        },
    }

    # Save
    path = STATE_DIR / "sentry_signals.json"
    with open(path, "w") as f:
        json.dump(result, f, indent=2)

    abort_count = sum(1 for s in signals if s.get("signal") == "ABORT")
    log.info(
        f"Sentry complete: {len(signals)} checked, {abort_count} ABORT signals | "
        f"Market: SPY {market_check.get('spy_change_pct', 0):+.1f}%"
    )

    # Alert on degraded sentry coverage: if Gemini is down we silently fall
    # back to CONTINUE for most tickers, which removes the news-based safety
    # layer. Warn loudly (and Discord-alert) when >30% of checks fail.
    if fallback_ratio > 0.30 and ran_count >= 3:
        msg = (
            f"Sentry DEGRADED: {fallback_count}/{ran_count} checks fell back "
            f"to heuristic defaults ({fallback_ratio:.0%}). News-based "
            f"ABORT detection is partially offline."
        )
        log.warning(msg)
        try:
            notify_sentry_degraded(fallback_count, ran_count, run_type)
        except Exception as exc:
            log.warning(f"Discord alert failed: {exc}")

    return result


def main() -> None:
    """Entry point for daily sentry."""
    cfg = load_config()
    result = run_daily_sentry(cfg)

    market = result.get("market_health", {})
    signals = result.get("signals", [])
    abort_count = sum(1 for s in signals if s.get("signal") == "ABORT")

    print(f"Market: SPY {market.get('spy_change_pct', 0):+.1f}%  "
          f"{'STRESS' if market.get('market_stress') else 'OK'}")
    print(f"Checked: {len(signals)} stocks | ABORT: {abort_count}")

    for s in signals:
        if s.get("signal") == "ABORT":
            print(f"  ABORT {s['ticker']}: {s.get('reasoning', '')[:80]}")


if __name__ == "__main__":
    main()
