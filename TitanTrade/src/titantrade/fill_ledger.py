"""Fill-vs-backtest ledger (Decision 069, behaviour leg).

One number per entry: the price the live book paid against the price the
backtest would have paid for the same trade — the close of the session the
order filled in, which is the next close after the signal (``fastbt`` and
``backtest/mechanical`` both fill there). The daily summary appends a row
once that session's close is published; the median gap over the clean
window is the behaviour leg's number. Rows are never edited.
"""
from __future__ import annotations

import json
import statistics
from datetime import date, datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from titantrade.config import STATE_DIR
from titantrade.logger import get_logger
from titantrade.market_data import get_ohlcv

log = get_logger(__name__)

LEDGER_FILE = "fill_ledger.json"
# An entry older than this without a row is left alone: its session's bar is
# outside the short fetch, and a row that old would not reach the summary anyway.
LOOKBACK_DAYS = 10
_ET = ZoneInfo("America/New_York")


def session_date(timestamp: str) -> str:
    """The Eastern session an ISO-8601 UTC timestamp falls in (YYYY-MM-DD)."""
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(_ET).strftime("%Y-%m-%d")


def fill_gap_pct(fill_price: float, backtest_close: float) -> float:
    """Fill against the backtest's price, in %; positive = the live book paid more."""
    return round((fill_price / backtest_close - 1) * 100, 3)


def load_ledger() -> dict[str, Any]:
    path = STATE_DIR / LEDGER_FILE
    if not path.exists():
        return {"rows": []}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"rows": []}
    data.setdefault("rows", [])
    return data


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    gaps = [float(r["gap_pct"]) for r in rows if r.get("gap_pct") is not None]
    if not gaps:
        return {"n": 0}
    return {
        "n": len(gaps),
        "median_gap_pct": round(statistics.median(gaps), 3),
        "mean_gap_pct": round(statistics.fmean(gaps), 3),
        "worst_gap_pct": round(max(gaps), 3),
        "fills_known": sum(1 for r in rows if r.get("fill_known")),
    }


def update_fill_ledger(cfg: Any, bars_for: Callable[..., list[dict[str, Any]]] = get_ohlcv) -> int:
    """Append a row for every recent BUY entry whose session close is published. Idempotent; returns rows added."""
    ledger = load_ledger()
    done = {r.get("trade_id") for r in ledger["rows"]}
    path = STATE_DIR / "trade_log.json"
    trades = json.loads(path.read_text()).get("trades", []) if path.exists() else []
    today = datetime.now(_ET).date()
    added = 0
    for t in trades:
        if t.get("action") != "BUY" or t.get("trigger") != "entry" or t.get("id") in done or not t.get("timestamp"):
            continue
        session = session_date(t["timestamp"])
        if (today - date.fromisoformat(session)).days > LOOKBACK_DAYS:
            continue
        try:
            closes = {b["date"]: float(b["close"]) for b in bars_for(t["ticker"], cfg, days=LOOKBACK_DAYS + 5, feed="sip")}
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Fill ledger: bars for {t['ticker']} unavailable ({exc}) — retried at the next summary")
            continue
        close = closes.get(session)
        if not close:
            continue  # the session's bar is not published yet; the next summary retries
        fill = t.get("fill_price")
        known = isinstance(fill, (int, float)) and fill > 0
        price = float(fill) if known else float(t.get("price") or 0)
        if price <= 0:
            continue
        ledger["rows"].append({
            "trade_id": t.get("id"), "ticker": t["ticker"], "date": session,
            "fill_price": price, "fill_known": known, "backtest_close": close, "gap_pct": fill_gap_pct(price, close),
        })
        added += 1
        log.info(f"Fill ledger: {t['ticker']} {session} fill {price:.2f} vs close {close:.2f} ({fill_gap_pct(price, close):+.2f}%)"
                 + ("" if known else " [bracket limit, fill not captured]"))
    if added:
        with open(STATE_DIR / LEDGER_FILE, "w") as f:
            json.dump(ledger, f, indent=2)
    return added
