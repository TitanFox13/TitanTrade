"""Mechanical strategy driver (Decisions 061/062/063): data bundle → plan.

``state/plan.json`` is the executor's only strategy input:

  items   NEW  — a dip-in-uptrend signal that fits a free slot, with the entry
                 at the last close and the configured stop/target (the
                 executor re-anchors all three to the live price at order time)
          HOLD — a position opened under this strategy, carrying the stop and
                 target its opening bracket used, so stop coverage stays
                 consistent across runs
  watch   every other watchlist name with the reason it has no signal
  plus the insurance state, the ranked candidates, the free slots and the
  legacy positions awaiting close — the dashboard summary.

Positions opened before ``state/strategy.json``'s ``started_at`` are legacy:
they get no item, and the executor's orphan close sells them at the open.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from titantrade.broker import get_open_orders, get_positions
from titantrade.config import STATE_DIR, Config
from titantrade.core_allocation import _is_core_ticker
from titantrade.logger import get_logger
from titantrade.market_context import get_stock_sector
from titantrade.risk_manager import MIN_CASH_RESERVE_PCT
from titantrade.signals import evaluate_dip, insurance_state, rank_dips, shock_state
from titantrade.trade_state import _load, _opening_buy, position_opened_at

log = get_logger("mechanical")

PLAN_FILE = "plan.json"
STRATEGY_FILE = "strategy.json"


def strategy_started_at() -> str | None:
    """ISO timestamp of the first mechanical run (``state/strategy.json``)."""
    doc = _load(STRATEGY_FILE)
    ts = doc.get("started_at") if isinstance(doc, dict) else None
    return ts if isinstance(ts, str) and ts else None


def benchmark_window_start() -> str | None:
    """Start of the clean window the benchmark is judged on: the two-sleeve
    book's first run (``window_started_at``, Decision 068) when the sleeve is
    on, else the strategy start."""
    doc = _load(STRATEGY_FILE)
    if not isinstance(doc, dict):
        return None
    ts = doc.get("window_started_at") or doc.get("started_at")
    return ts if isinstance(ts, str) and ts else None


def _ensure_strategy_started(now: datetime, cfg: Config | None = None) -> str:
    """Stamp ``strategy.json`` on the first run; stamp the Decision 068 window
    the first time the momentum sleeve is on. ``started_at`` never moves —
    it is what separates mechanical positions from legacy ones."""
    doc = _load(STRATEGY_FILE)
    doc = doc if isinstance(doc, dict) else {}
    changed = False
    if not strategy_started_at():
        doc = {"strategy": "mechanical", "started_at": now.isoformat(), "decision": "061"}
        log.warning(f"Mechanical strategy started at {doc['started_at']} — positions opened before this are legacy")
        changed = True
    if cfg and cfg.trading.momentum_weight > 0 and not doc.get("window_started_at"):
        doc.update(window_started_at=now.isoformat(), design="068",
                   sleeve={"ticker": cfg.trading.momentum_ticker, "weight": cfg.trading.momentum_weight})
        log.warning(f"Two-sleeve book (Decision 068) starts at {doc['window_started_at']} — benchmark window reset")
        changed = True
    if changed:
        with open(STATE_DIR / STRATEGY_FILE, "w") as f:
            json.dump(doc, f, indent=2)
    return doc["started_at"]


def is_mechanical_position(ticker: str, started_at: str | None) -> bool:
    """True when the ticker's current position was opened under the
    mechanical strategy (its opening BUY is at/after ``started_at``)."""
    opened = position_opened_at(ticker)
    return bool(started_at and opened and opened >= started_at)


def _hold_item(ticker: str, position: dict[str, Any], cfg: Config) -> dict[str, Any]:
    """HOLD item carrying the levels the opening bracket used."""
    rec = _opening_buy(ticker) or {}
    avg = float(position.get("avg_entry_price") or 0) or float(rec.get("price") or 0)
    stop = float(rec.get("stop_price") or rec.get("stop_loss_price") or 0) or round(avg * (1 - cfg.trading.stop_pct), 2)
    target = float(rec.get("target_price") or rec.get("take_profit_price") or 0) or round(avg * (1 + cfg.trading.tp_pct), 2)
    return {
        "ticker": ticker,
        "action": "HOLD",
        "sector": get_stock_sector(ticker),
        "entry_price": avg or None,
        "stop_price": stop or None,
        "target_price": target or None,
        "opened_at": position_opened_at(ticker),
        "reason": (
            f"held — exit at +{cfg.trading.tp_pct:.0%}, the -{cfg.trading.stop_pct:.0%} stop, "
            f"or after {cfg.trading.max_hold_days} trading days"
        ),
    }


def _new_item(ticker: str, state: dict[str, Any], cfg: Config) -> dict[str, Any]:
    close = float(state["close"])
    return {
        "ticker": ticker,
        "action": "NEW",
        "sector": get_stock_sector(ticker),
        "entry_price": round(close, 2),
        "stop_price": round(close * (1 - cfg.trading.stop_pct), 2),
        "target_price": round(close * (1 + cfg.trading.tp_pct), 2),
        "dip_pct": state["dip_pct"],
        "reason": (
            f"{state['dip_pct']:.1%} below its {cfg.trading.dip_lookback_days}-day high "
            f"(${state['high']:.2f}), above its {cfg.trading.trend_sma_days}-day SMA "
            f"(${state['sma_trend']:.2f})"
        ),
    }


def _watch_entry(ticker: str, state: dict[str, Any], why: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "sector": get_stock_sector(ticker),
        "dip_pct": state.get("dip_pct"),
        "above_trend": state.get("above_trend"),
        "reason": why,
    }


def build_plan(
    cfg: Config,
    bundle: dict[str, Any],
    positions: list[dict[str, Any]],
    pending_buy_tickers: set[str],
    *,
    started_at: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """The plan for the next executor runs, from the data bundle and the book."""
    stocks = bundle.get("stocks", {}) or {}
    breadth_ctx = (bundle.get("market_context", {}) or {}).get("breadth", {}) or {}
    insurance = insurance_state(
        breadth_ctx.get("spy_above_sma"), breadth_ctx.get("pct"),
        breadth_threshold=cfg.trading.insurance_breadth, scale=cfg.trading.insurance_scale,
    )
    spy_closes = (bundle.get("market_context", {}) or {}).get("spy", {}).get("closes") or []
    shock = shock_state(
        [float(c) for c in spy_closes if c is not None],
        drop_pct=cfg.trading.shock_drop_pct, lookback=cfg.trading.shock_lookback_days,
        hold=cfg.trading.shock_hold_days, scale=cfg.trading.shock_scale,
    )
    # Exposure rules combine by min(), not multiplication (Decision 067).
    exposure_scale = min(insurance["exposure_scale"], shock["exposure_scale"])

    # The bundle bakes the lookback/SMA lengths into signal_inputs at fetch
    # time; after a parameter change the inputs are stale until the next fetch.
    sample = next((v.get("signal_inputs") for v in stocks.values() if v.get("signal_inputs")), None)
    stale = bool(sample and (sample.get("lookback_days") != cfg.trading.dip_lookback_days
                             or sample.get("trend_sma_days") != cfg.trading.trend_sma_days))
    if stale:
        log.warning(
            f"signal_inputs were computed for {sample.get('lookback_days')}d/"
            f"{sample.get('trend_sma_days')}d but settings say "
            f"{cfg.trading.dip_lookback_days}d/{cfg.trading.trend_sma_days}d — "
            f"run `titantrade fetch` to refresh them"
        )

    held = {p.get("symbol", ""): p for p in positions if float(p.get("qty") or 0) > 0}
    items: list[dict[str, Any]] = []
    watch: list[dict[str, Any]] = []
    states: dict[str, dict[str, Any]] = {}
    held_mech: list[str] = []
    legacy: list[str] = []

    for ticker in cfg.trading.watchlist:
        inputs = (stocks.get(ticker, {}) or {}).get("signal_inputs", {}) or {}
        states[ticker] = evaluate_dip(
            inputs.get("close"), inputs.get("high_lookback"), inputs.get("sma_trend"),
            dip_pct=cfg.trading.dip_pct,
        )
        pos = held.get(ticker)
        if pos and not _is_core_ticker(ticker, cfg):
            if is_mechanical_position(ticker, started_at):
                items.append(_hold_item(ticker, pos, cfg))
                held_mech.append(ticker)
            else:
                legacy.append(ticker)
    for ticker in held:
        if ticker not in cfg.trading.watchlist and not _is_core_ticker(ticker, cfg):
            legacy.append(ticker)   # removed from the watchlist → orphan close

    occupied = len(held_mech) + len({t for t in pending_buy_tickers if t not in held_mech})
    free_slots = max(0, cfg.trading.max_slots - occupied)
    ranked = [t for t in rank_dips(states) if t not in held and t not in pending_buy_tickers]
    if insurance["risk_off"]:
        chosen: list[str] = []
        why_blocked = "insurance is risk-off (SPY below its SMA and sector breadth below threshold) — no new entries"
    elif shock["active"]:
        chosen = []
        why_blocked = (
            f"shock trigger is on (SPY fell {-shock['worst_drop']:.1%} in {cfg.trading.shock_lookback_days} sessions; "
            f"{shock['sessions_left']} sessions left) — no new entries"
        )
    else:
        chosen = ranked[:free_slots]
        why_blocked = (
            f"no free slot — {occupied} of {cfg.trading.max_slots} slots held or pending"
            if free_slots == 0 else "no free slot — deeper dips took the free slot(s)"
        )

    for ticker in cfg.trading.watchlist:
        if ticker in held_mech or ticker in legacy:
            continue
        state = states[ticker]
        if ticker in chosen or ticker in pending_buy_tickers:
            # A pending bracket keeps its item so the next run can re-anchor it.
            items.append(_new_item(ticker, state, cfg))
        elif state.get("signal"):
            watch.append(_watch_entry(ticker, state, why_blocked))
        elif state.get("close") is None:
            watch.append(_watch_entry(ticker, state, "no signal inputs in the data bundle"))
        else:
            dip = state.get("dip_pct")
            why = (f"{dip:.1%} below the {cfg.trading.dip_lookback_days}-day high — no signal"
                   if dip is not None else "no signal")
            if state.get("above_trend") is False:
                why += f"; below its {cfg.trading.trend_sma_days}-day SMA"
            watch.append(_watch_entry(ticker, state, why))

    return {
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "strategy": "mechanical",
        "started_at": started_at,
        "params": {
            "dip_pct": cfg.trading.dip_pct, "dip_lookback_days": cfg.trading.dip_lookback_days,
            "trend_sma_days": cfg.trading.trend_sma_days, "slot_pct": cfg.trading.slot_pct,
            "max_slots": cfg.trading.max_slots, "tp_pct": cfg.trading.tp_pct,
            "stop_pct": cfg.trading.stop_pct, "max_hold_days": cfg.trading.max_hold_days,
            "insurance_sma_days": cfg.trading.insurance_sma_days,
            "insurance_breadth": cfg.trading.insurance_breadth,
            "insurance_scale": cfg.trading.insurance_scale,
            "momentum_ticker": cfg.trading.momentum_ticker,
            "momentum_weight": cfg.trading.momentum_weight,
            "shock_drop_pct": cfg.trading.shock_drop_pct,
            "shock_lookback_days": cfg.trading.shock_lookback_days,
            "shock_hold_days": cfg.trading.shock_hold_days,
            "shock_scale": cfg.trading.shock_scale,
        },
        "stale_inputs": stale,
        "insurance": insurance,
        "shock": shock,
        "exposure_scale": exposure_scale,
        "sleeve": {
            "ticker": cfg.trading.momentum_ticker,
            "weight": cfg.trading.momentum_weight,
            "target_pct": momentum_target_pct(cfg, exposure_scale),
        },
        "breadth": {k: v for k, v in breadth_ctx.items() if k != "flags"},
        "items": items,
        "watch": watch,
        "candidates": [
            {"ticker": t, "dip_pct": states[t].get("dip_pct"), "chosen": t in chosen} for t in ranked
        ],
        "held": held_mech,
        "legacy_to_close": legacy,
        "pending_buys": sorted(pending_buy_tickers),
        "free_slots": free_slots,
        "new_signals": len(chosen),
    }


def core_target_pct(
    cfg: Config,
    portfolio_value: float,
    positions: list[dict[str, Any]],
    *,
    planned_new_slots: int,
    exposure_scale: float,
) -> float:
    """SPY target as a fraction of equity: the residual of the dip sleeve.

    ``exposure_scale × (1 − cash reserve) × (1 − momentum_weight) − (held
    overlay + planned slots)``. Planned slots are subtracted so the core
    sells SPY *before* the entries need the cash in the same run; after an
    exit the next run buys SPY back. The momentum ETF is a core leg, not
    overlay (Decision 068).
    """
    if portfolio_value <= 0:
        return 0.0
    overlay = sum(
        abs(float(p.get("market_value") or 0))
        for p in positions
        if not _is_core_ticker(p.get("symbol", ""), cfg)
    )
    planned = planned_new_slots * cfg.trading.overlay_slot_pct * portfolio_value
    investable = exposure_scale * (1 - MIN_CASH_RESERVE_PCT / 100) * (1 - cfg.trading.momentum_weight)
    target = investable - (overlay + planned) / portfolio_value
    return max(0.0, min(1.0, round(target, 4)))


def momentum_target_pct(cfg: Config, exposure_scale: float) -> float:
    """The momentum sleeve's target share of equity (Decision 068):
    ``exposure_scale × (1 − cash reserve) × momentum_weight``."""
    return round(max(0.0, exposure_scale) * (1 - MIN_CASH_RESERVE_PCT / 100) * cfg.trading.momentum_weight, 4)


def _pending_buy_tickers(cfg: Config) -> set[str]:
    try:
        return {
            o.get("symbol", "") for o in get_open_orders(None, cfg)
            if o.get("side") == "buy" and not _is_core_ticker(o.get("symbol", ""), cfg)
        }
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Open-orders read failed (slot count may be high): {exc}")
        return set()


def refresh_plan(cfg: Config) -> dict[str, Any]:
    """Compute the plan from the data bundle and the book; write ``plan.json``."""
    now = datetime.now(timezone.utc)
    started_at = _ensure_strategy_started(now, cfg)
    bundle = _load("data_bundle.json")
    if not bundle.get("stocks"):
        log.error("No data bundle — run `titantrade fetch` first; plan left untouched")
        return {"error": "no data bundle", "items": [], "new_signals": 0, "insurance": {"risk_off": False}}

    plan = build_plan(cfg, bundle, get_positions(cfg), _pending_buy_tickers(cfg), started_at=started_at, now=now)
    with open(STATE_DIR / PLAN_FILE, "w") as f:
        json.dump(plan, f, indent=2)

    ins = plan["insurance"]
    log.info(
        f"Plan: {plan['new_signals']} new entry signal(s) "
        f"{[c['ticker'] for c in plan['candidates'] if c['chosen']]}, "
        f"{len(plan['held'])} held, {plan['free_slots']} free slot(s), "
        f"legacy to close {plan['legacy_to_close']} | risk-off "
        f"{'YES (exposure x' + str(ins['exposure_scale']) + ')' if ins['risk_off'] else 'no'} "
        f"(SPY above SMA: {ins['spy_above_sma']}, breadth {ins['sector_breadth']}) | shock "
        f"{'ON (' + str(plan['shock']['sessions_left']) + ' sessions left)' if plan['shock']['active'] else 'off'} "
        f"| exposure x{plan['exposure_scale']} | {plan['sleeve']['ticker']} target {plan['sleeve']['target_pct']:.0%}"
    )
    return plan


def main() -> None:
    from titantrade.config import load_config

    plan = refresh_plan(load_config())
    if plan.get("error"):
        print(f"Plan: {plan['error']}")
        return
    ins = plan["insurance"]
    print(f"Risk-off: {'YES' if ins['risk_off'] else 'no'} | SPY above SMA: {ins['spy_above_sma']} | sector breadth: {ins['sector_breadth']}")
    sh = plan["shock"]
    print(f"Shock trigger: {'ON (' + str(sh['sessions_left']) + ' sessions left)' if sh['active'] else 'off'} | exposure x{plan['exposure_scale']} | {plan['sleeve']['ticker']} target {plan['sleeve']['target_pct']:.0%}")
    print(f"Held: {plan['held']} | legacy to close: {plan['legacy_to_close']} | free slots: {plan['free_slots']}")
    for c in plan["candidates"]:
        print(f"  {'BUY ' if c['chosen'] else '    '} {c['ticker']:6} dip {c['dip_pct']:.1%}")


if __name__ == "__main__":
    main()
