"""Mechanical strategy driver (Decision 061).

Replaces the weekly LLM analyst and the daily LLM sentry in the trading loop.
Turns the data bundle into the two state files the executor already consumes
(``weekly_thesis.json`` with the same schema, ``sentry_signals.json`` with
CONTINUE for every name and the insurance state as ``market_health``), so the
bracket/gate/coverage/orphan machinery runs unchanged.

What the executor then does with it:
  entries   dip-in-uptrend names (ranked deepest first, up to the free slots)
            get a BULLISH / NEW / selected thesis at the last close with a
            -stop_pct stop and a +tp_pct target → bracket via the 9 gates
  held      mechanical positions get a CONTINUE thesis carrying their
            entry-time stop/target (trade log) → stop coverage stays consistent
  legacy    positions opened before the strategy started are left out of the
            thesis → the executor's orphan close sells them at the open
  core      SPY is the residual: exposure_scale × (1 − cash reserve) − overlay
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from titantrade.broker import get_open_orders, get_positions
from titantrade.config import STATE_DIR, Config
from titantrade.core_allocation import _is_core_ticker
from titantrade.logger import get_logger
from titantrade.market_context import get_stock_sector
from titantrade.risk_manager import MIN_CASH_RESERVE_PCT
from titantrade.signals import evaluate_dip, insurance_state, rank_dips
from titantrade.trade_state import _load, _opening_buy, position_opened_at

log = get_logger("mechanical")

STRATEGY_FILE = "strategy.json"
MECHANICAL_CONFIDENCE = 0.80   # ≥ 0.80 → near-market entry (pricing._choose_entry_price)


def strategy_started_at() -> str | None:
    """ISO timestamp of the first mechanical run (``state/strategy.json``)."""
    doc = _load(STRATEGY_FILE)
    ts = doc.get("started_at") if isinstance(doc, dict) else None
    return ts if isinstance(ts, str) and ts else None


def _ensure_strategy_started(now: datetime) -> str:
    started = strategy_started_at()
    if started:
        return started
    started = now.isoformat()
    with open(STATE_DIR / STRATEGY_FILE, "w") as f:
        json.dump({"strategy": "mechanical", "started_at": started, "decision": "061"}, f, indent=2)
    log.warning(f"Mechanical strategy started at {started} — positions opened before this are legacy")
    return started


def is_mechanical_position(ticker: str, started_at: str | None) -> bool:
    """True when the ticker's current position was opened under the
    mechanical strategy (its opening BUY is at/after ``started_at``)."""
    opened = position_opened_at(ticker)
    return bool(started_at and opened and opened >= started_at)


def _held_thesis(ticker: str, position: dict[str, Any], cfg: Config, sector: str) -> dict[str, Any]:
    """CONTINUE thesis for a held mechanical position, carrying the levels its
    opening bracket used so stop coverage and resubmission stay consistent."""
    rec = _opening_buy(ticker) or {}
    avg = float(position.get("avg_entry_price") or 0) or float(rec.get("price") or 0)
    stop = float(rec.get("stop_loss_price") or 0) or round(avg * (1 - cfg.trading.stop_pct), 2)
    tp = float(rec.get("take_profit_price") or 0) or round(avg * (1 + cfg.trading.tp_pct), 2)
    return {
        "ticker": ticker,
        "sector": sector,
        "thesis": "BULLISH",
        "confidence": MECHANICAL_CONFIDENCE,
        "target_entry_price": avg or None,
        "stop_loss_price": stop or None,
        "take_profit_price": tp or None,
        "hold_horizon": f"{cfg.trading.max_hold_days} trading days",
        "selected_for_trading": True,
        "review_action": "CONTINUE",
        "reasoning": "Mechanical strategy (Decision 061): held dip position — exit at "
                     f"+{cfg.trading.tp_pct:.0%}, -{cfg.trading.stop_pct:.0%} stop, "
                     f"or after {cfg.trading.max_hold_days} trading days.",
        "thesis_breach_condition": "n/a — mechanical exits only",
        "opened_at": position_opened_at(ticker),
    }


def _candidate_thesis(ticker: str, state: dict[str, Any], cfg: Config, sector: str) -> dict[str, Any]:
    close = float(state["close"])
    return {
        "ticker": ticker,
        "sector": sector,
        "thesis": "BULLISH",
        "confidence": MECHANICAL_CONFIDENCE,
        "target_entry_price": round(close, 2),
        "stop_loss_price": round(close * (1 - cfg.trading.stop_pct), 2),
        "take_profit_price": round(close * (1 + cfg.trading.tp_pct), 2),
        "hold_horizon": f"{cfg.trading.max_hold_days} trading days",
        "selected_for_trading": True,
        "review_action": "NEW",
        "reasoning": (
            f"Mechanical strategy (Decision 061): {state['dip_pct']:.1%} below its "
            f"{cfg.trading.dip_lookback_days}-day high (${state['high']:.2f}) and above "
            f"its {cfg.trading.trend_sma_days}-day SMA (${state['sma_trend']:.2f})."
        ),
        "thesis_breach_condition": "n/a — mechanical exits only",
        "dip_pct": state["dip_pct"],
    }


def _neutral_thesis(ticker: str, state: dict[str, Any] | None, cfg: Config, sector: str, why: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "sector": sector,
        "thesis": "NEUTRAL",
        "confidence": 0.0,
        "target_entry_price": None,
        "stop_loss_price": None,
        "take_profit_price": None,
        "hold_horizon": None,
        "selected_for_trading": False,
        "review_action": "NEW",
        "reasoning": f"Mechanical strategy (Decision 061): {why}",
        "dip_pct": (state or {}).get("dip_pct"),
    }


def build_theses(
    cfg: Config,
    bundle: dict[str, Any],
    positions: list[dict[str, Any]],
    pending_buy_tickers: set[str],
    *,
    started_at: str,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Mechanical thesis list for the watchlist plus a signal summary."""
    stocks = bundle.get("stocks", {}) or {}
    breadth_ctx = (bundle.get("market_context", {}) or {}).get("breadth", {}) or {}
    insurance = insurance_state(
        breadth_ctx.get("spy_above_sma"), breadth_ctx.get("pct"),
        breadth_threshold=cfg.trading.insurance_breadth, scale=cfg.trading.insurance_scale,
    )

    # The bundle bakes the lookback/SMA lengths into signal_inputs at fetch
    # time; after a parameter change the inputs are stale until the next fetch.
    sample = next((v.get("signal_inputs") for v in stocks.values() if v.get("signal_inputs")), None)
    if sample and (sample.get("lookback_days") != cfg.trading.dip_lookback_days
                   or sample.get("trend_sma_days") != cfg.trading.trend_sma_days):
        log.warning(
            f"signal_inputs were computed for {sample.get('lookback_days')}d/"
            f"{sample.get('trend_sma_days')}d but settings say "
            f"{cfg.trading.dip_lookback_days}d/{cfg.trading.trend_sma_days}d — "
            f"run `titantrade fetch` to refresh them"
        )

    held = {p.get("symbol", ""): p for p in positions if float(p.get("qty") or 0) > 0}
    theses: list[dict[str, Any]] = []
    states: dict[str, dict[str, Any]] = {}
    held_mech: list[str] = []
    legacy: list[str] = []

    for ticker in cfg.trading.watchlist:
        sector = get_stock_sector(ticker)
        inputs = (stocks.get(ticker, {}) or {}).get("signal_inputs", {}) or {}
        state = evaluate_dip(
            inputs.get("close"), inputs.get("high_lookback"), inputs.get("sma_trend"),
            dip_pct=cfg.trading.dip_pct,
        )
        states[ticker] = state
        pos = held.get(ticker)
        if pos and not _is_core_ticker(ticker, cfg):
            if is_mechanical_position(ticker, started_at):
                theses.append(_held_thesis(ticker, pos, cfg, sector))
                held_mech.append(ticker)
            else:
                legacy.append(ticker)   # no thesis → orphan close at the open
    # Held names outside the watchlist (removed from it) are left to orphan close too.
    for ticker in held:
        if ticker not in cfg.trading.watchlist and not _is_core_ticker(ticker, cfg):
            legacy.append(ticker)

    occupied = len(held_mech) + len({t for t in pending_buy_tickers if t not in held_mech})
    free_slots = max(0, cfg.trading.max_slots - occupied)
    ranked = [t for t in rank_dips(states) if t not in held and t not in pending_buy_tickers]
    chosen: list[str] = []
    if insurance["risk_off"]:
        why_blocked = "insurance is risk-off (SPY below SMA and sector breadth below threshold) — no new entries"
    else:
        chosen = ranked[:free_slots]
        why_blocked = "no free slot — the deeper dips took the slot(s)"

    for ticker in cfg.trading.watchlist:
        if ticker in held_mech or ticker in legacy:
            continue
        state = states[ticker]
        if ticker in chosen:
            theses.append(_candidate_thesis(ticker, state, cfg, get_stock_sector(ticker)))
        elif ticker in pending_buy_tickers:
            # Keep the bracket's thesis alive so resubmission can adapt it.
            theses.append(_candidate_thesis(ticker, state, cfg, get_stock_sector(ticker)))
        elif state.get("signal"):
            theses.append(_neutral_thesis(ticker, state, cfg, get_stock_sector(ticker), why_blocked))
        elif state.get("close") is None:
            theses.append(_neutral_thesis(ticker, state, cfg, get_stock_sector(ticker), "no signal inputs in the data bundle"))
        else:
            dip = state.get("dip_pct")
            why = (
                f"{dip:.1%} below the {cfg.trading.dip_lookback_days}-day high — no dip signal"
                if dip is not None else "no dip signal"
            )
            if state.get("above_trend") is False:
                why += f"; below its {cfg.trading.trend_sma_days}-day SMA"
            theses.append(_neutral_thesis(ticker, state, cfg, get_stock_sector(ticker), why))

    summary = {
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "strategy": "mechanical",
        "started_at": started_at,
        "insurance": insurance,
        "breadth": {k: v for k, v in breadth_ctx.items() if k != "flags"},
        "candidates": [
            {"ticker": t, "dip_pct": states[t].get("dip_pct"), "chosen": t in chosen}
            for t in ranked
        ],
        "held_mechanical": held_mech,
        "legacy_to_close": legacy,
        "pending_buys": sorted(pending_buy_tickers),
        "free_slots": free_slots,
        "new_signals": len(chosen),
        "params": {
            "dip_pct": cfg.trading.dip_pct, "dip_lookback_days": cfg.trading.dip_lookback_days,
            "trend_sma_days": cfg.trading.trend_sma_days, "slot_pct": cfg.trading.slot_pct,
            "max_slots": cfg.trading.max_slots, "tp_pct": cfg.trading.tp_pct,
            "stop_pct": cfg.trading.stop_pct, "max_hold_days": cfg.trading.max_hold_days,
            "insurance_sma_days": cfg.trading.insurance_sma_days,
            "insurance_breadth": cfg.trading.insurance_breadth,
            "insurance_scale": cfg.trading.insurance_scale,
        },
    }
    return theses, summary


def core_target_pct(
    cfg: Config,
    portfolio_value: float,
    positions: list[dict[str, Any]],
    *,
    planned_new_slots: int,
    exposure_scale: float,
) -> float:
    """SPY target as a fraction of equity: the residual after the overlay.

    ``exposure_scale × (1 − cash reserve) − (held overlay + planned slots)``.
    Planned slots are subtracted so the core sells SPY *before* the entries
    need the cash in the same run; after an exit the next run buys SPY back.
    """
    if portfolio_value <= 0:
        return 0.0
    overlay = sum(
        abs(float(p.get("market_value") or 0))
        for p in positions
        if not _is_core_ticker(p.get("symbol", ""), cfg)
    )
    planned = planned_new_slots * cfg.trading.slot_pct * portfolio_value
    investable = exposure_scale * (1 - MIN_CASH_RESERVE_PCT / 100)
    target = investable - (overlay + planned) / portfolio_value
    return max(0.0, min(1.0, round(target, 4)))


def _pending_buy_tickers(cfg: Config) -> set[str]:
    try:
        return {
            o.get("symbol", "") for o in get_open_orders(None, cfg)
            if o.get("side") == "buy" and not _is_core_ticker(o.get("symbol", ""), cfg)
        }
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Open-orders read failed (slot count may be high): {exc}")
        return set()


def refresh_mechanical_signals(cfg: Config) -> dict[str, Any]:
    """Compute signals from the data bundle and write the executor's inputs.

    Writes ``weekly_thesis.json``, ``sentry_signals.json`` and ``signals.json``
    (the dashboard summary). Returns the summary.
    """
    now = datetime.now(timezone.utc)
    started_at = _ensure_strategy_started(now)
    bundle = _load("data_bundle.json")
    if not bundle.get("stocks"):
        log.error("No data bundle — run `titantrade fetch` first; leaving thesis untouched")
        return {"error": "no data bundle", "new_signals": 0, "risk_off": False}

    positions = get_positions(cfg)
    pending = _pending_buy_tickers(cfg)
    theses, summary = build_theses(cfg, bundle, positions, pending, started_at=started_at, now=now)

    thesis_doc = {
        "generated_at": now.isoformat(),
        "next_review_at": (now + timedelta(days=2)).isoformat(),
        "strategy": "mechanical",
        "market_regime": (bundle.get("market_context", {}) or {}).get("market_regime"),
        "insurance": summary["insurance"],
        "ranking": [c["ticker"] for c in summary["candidates"]],
        "theses": theses,
    }
    sentry_doc = {
        "generated_at": now.isoformat(),
        "run_type": "mechanical",
        "market_health": {
            "market_stress": False,            # no hedge swap in the mechanical strategy
            "risk_off": summary["insurance"]["risk_off"],
            "exposure_scale": summary["insurance"]["exposure_scale"],
            "spy_above_sma": summary["insurance"]["spy_above_sma"],
            "sector_breadth": summary["insurance"]["sector_breadth"],
        },
        "signals": [
            {
                "ticker": t["ticker"],
                "signal": "CONTINUE",
                "price_concern": False,
                "news_concern": False,
                "reasoning": "Mechanical strategy (Decision 061): no sentry exits — the stop, the target and the holding period are the only exits.",
            }
            for t in theses if t.get("selected_for_trading")
        ],
        "failures": {"fallback_count": 0, "checks_run": 0, "fallback_ratio": 0.0},
    }
    for name, doc in (("weekly_thesis.json", thesis_doc), ("sentry_signals.json", sentry_doc), ("signals.json", summary)):
        with open(STATE_DIR / name, "w") as f:
            json.dump(doc, f, indent=2)

    ins = summary["insurance"]
    log.info(
        f"Mechanical signals: {summary['new_signals']} new entry signal(s) "
        f"{[c['ticker'] for c in summary['candidates'] if c['chosen']]}, "
        f"{len(summary['held_mechanical'])} held, {summary['free_slots']} free slot(s), "
        f"legacy to close {summary['legacy_to_close']} | insurance "
        f"{'RISK-OFF' if ins['risk_off'] else 'on'} (SPY above SMA: {ins['spy_above_sma']}, "
        f"breadth {ins['sector_breadth']})"
    )
    summary["risk_off"] = ins["risk_off"]
    return summary


def main() -> None:
    from titantrade.config import load_config

    summary = refresh_mechanical_signals(load_config())
    if summary.get("error"):
        print(f"Signals: {summary['error']}")
        return
    ins = summary["insurance"]
    print(f"Insurance: {'RISK-OFF' if ins['risk_off'] else 'on'} | SPY above SMA: {ins['spy_above_sma']} | sector breadth: {ins['sector_breadth']}")
    print(f"Held (mechanical): {summary['held_mechanical']} | legacy to close: {summary['legacy_to_close']} | free slots: {summary['free_slots']}")
    for c in summary["candidates"]:
        print(f"  {'BUY ' if c['chosen'] else '    '} {c['ticker']:6} dip {c['dip_pct']:.1%}")


if __name__ == "__main__":
    main()
