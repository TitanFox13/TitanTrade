"""Universe curator + post-mortem (Decision 061): the LLM's remaining jobs.

Neither touches orders. Once a month Claude proposes watchlist changes with
reasons (the operator applies them through the watchlist editor) and writes
a plain-language review of the last month's trades. Judgment at the slowest
horizon, where its reading of public text is not racing anyone.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from titantrade.config import STATE_DIR, Config
from titantrade.logger import get_logger
from titantrade.trade_state import _load

log = get_logger("titantrade.curator")

PROPOSAL_FILE = "universe_proposal.json"
POST_MORTEM_FILE = "post_mortem.json"


def _extract_json(text: str) -> dict[str, Any]:
    """First {...} block in a model reply, or {} when it isn't JSON."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def _stock_brief(ticker: str, stock: dict[str, Any]) -> dict[str, Any]:
    tech = (stock.get("technical_indicators") or {}).get("price_vs_sma", {}) or {}
    rs = stock.get("relative_strength_vs_spy") or {}
    return {
        "ticker": ticker,
        "pct_from_sma_200": tech.get("pct_from_sma_200"),
        "pct_from_sma_50": tech.get("pct_from_sma_50"),
        "relative_strength_vs_spy": rs if isinstance(rs, (int, float)) else rs.get("rs_60d", rs) if isinstance(rs, dict) else rs,
        "analyst_ratings": stock.get("analyst_ratings"),
        "earnings_days_away": (stock.get("earnings") or {}).get("days_until_earnings"),
        "headlines": [n.get("title", "") for n in (stock.get("news") or [])[:3]],
    }


def _trade_stats(trades: list[dict[str, Any]], days: int = 90) -> dict[str, dict[str, int]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    stats: dict[str, dict[str, int]] = {}
    for t in trades:
        if str(t.get("timestamp", "")) < cutoff:
            continue
        row = stats.setdefault(t.get("ticker", "?"), {"buys": 0, "sells": 0})
        row["buys" if t.get("action") == "BUY" else "sells"] += 1
    return stats


def build_universe_prompt(cfg: Config, bundle: dict[str, Any], trades: list[dict[str, Any]]) -> tuple[str, str]:
    system = (
        "You curate the stock universe for a mechanical, rules-based strategy. The rules are fixed and you "
        "do not trade: the system buys a name when it closes at least "
        f"{cfg.trading.dip_pct:.0%} below its {cfg.trading.dip_lookback_days}-day high while above its "
        f"{cfg.trading.trend_sma_days}-day average, holds up to {cfg.trading.max_hold_days} trading days, "
        f"exits at +{cfg.trading.tp_pct:.0%} or -{cfg.trading.stop_pct:.0%}. Good universe members are liquid US "
        "large caps (market cap above $10B, average volume above 1M shares) with durable businesses that "
        "tend to recover from pullbacks, across different sectors. No leveraged or inverse ETFs, no SPACs, "
        "no names with pending binary events. Propose at most 2 removals and at most 2 additions, each "
        "with a one-sentence reason, and only when the case is clear — an empty proposal is a valid "
        "answer. Reply with JSON only: {\"remove\": [{\"ticker\": str, \"reason\": str}], "
        "\"add\": [{\"ticker\": str, \"sector\": str, \"reason\": str}], \"notes\": str}."
    )
    briefs = [_stock_brief(t, bundle.get("stocks", {}).get(t, {}) or {}) for t in cfg.trading.watchlist]
    user = json.dumps({
        "as_of": bundle.get("generated_at"),
        "market_regime": (bundle.get("market_context") or {}).get("market_regime"),
        "watchlist": briefs,
        "trades_last_90_days": _trade_stats(trades),
    }, indent=1, default=str)
    return system, user


def build_post_mortem_prompt(cfg: Config, trades: list[dict[str, Any]]) -> tuple[str, str]:
    system = (
        "You write a short, plain-language monthly review of a mechanical trading strategy's trades for "
        "its operator. Do not recommend parameter changes or new rules — describe what happened: which "
        "exits were stops, targets or time limits, which names repeated, what the market did, and one or "
        "two observations worth checking in a backtest. Reply with JSON only: "
        "{\"summary\": str, \"observations\": [str]}. At most 150 words in total."
    )
    cutoff = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    recent = [
        {k: t.get(k) for k in ("timestamp", "ticker", "action", "shares", "price", "trigger")}
        for t in trades if str(t.get("timestamp", "")) >= cutoff
    ]
    return system, json.dumps({"trades": recent}, indent=1, default=str)


def _trades() -> list[dict[str, Any]]:
    doc = _load("trade_log.json")
    return doc.get("trades", []) if isinstance(doc, dict) else (doc or [])


def run_universe_review(cfg: Config) -> dict[str, Any]:
    from titantrade.weekly_analyst import _call_claude

    bundle = _load("data_bundle.json")
    system, user = build_universe_prompt(cfg, bundle, _trades())
    text = _call_claude(system, user, cfg, cost_label="Universe review (monthly)")
    proposal = _extract_json(text)
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "watchlist": list(cfg.trading.watchlist),
        "proposal": proposal,
        "raw": text if not proposal else None,
        "status": "advisory — apply through the watchlist editor",
    }
    with open(STATE_DIR / PROPOSAL_FILE, "w") as f:
        json.dump(doc, f, indent=2)
    removes = ", ".join(r.get("ticker", "?") for r in proposal.get("remove", [])) or "none"
    adds = ", ".join(a.get("ticker", "?") for a in proposal.get("add", [])) or "none"
    log.info(f"Universe proposal: remove [{removes}] add [{adds}]")
    try:
        from titantrade.notifier import send_discord

        send_discord(
            "Monthly universe review (advisory)",
            proposal.get("notes", "") or "No notes.",
            fields=[{"name": "Remove", "value": removes, "inline": True},
                    {"name": "Add", "value": adds, "inline": True}],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Universe proposal notify failed: {exc}")
    return doc


def run_post_mortem(cfg: Config) -> dict[str, Any]:
    from titantrade.weekly_analyst import _call_claude

    system, user = build_post_mortem_prompt(cfg, _trades())
    text = _call_claude(system, user, cfg, cost_label="Post-mortem (monthly)")
    review = _extract_json(text)
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review": review,
        "raw": text if not review else None,
    }
    with open(STATE_DIR / POST_MORTEM_FILE, "w") as f:
        json.dump(doc, f, indent=2)
    try:
        from titantrade.notifier import send_discord

        send_discord(
            "Monthly post-mortem",
            review.get("summary", text[:1500]),
            fields=[{"name": "Observations", "value": "\n".join(f"• {o}" for o in review.get("observations", [])) or "—"}],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Post-mortem notify failed: {exc}")
    return doc


def run_monthly_curation(cfg: Config) -> str:
    parts = []
    try:
        doc = run_universe_review(cfg)
        p = doc.get("proposal", {})
        parts.append(f"proposal: -{len(p.get('remove', []))} +{len(p.get('add', []))}")
    except Exception as exc:  # noqa: BLE001
        log.error(f"Universe review failed: {exc}")
        parts.append(f"proposal failed: {exc}")
    try:
        run_post_mortem(cfg)
        parts.append("post-mortem written")
    except Exception as exc:  # noqa: BLE001
        log.error(f"Post-mortem failed: {exc}")
        parts.append(f"post-mortem failed: {exc}")
    return "; ".join(parts)


def main() -> None:
    from titantrade.config import load_config

    print(run_monthly_curation(load_config()))


if __name__ == "__main__":
    main()
