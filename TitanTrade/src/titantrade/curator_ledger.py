"""The curator ledger (Decision 082, roadmap A5): does the monthly LLM
proposal have any skill?

One row per proposal — the list reviewed, its members, the additions and the
removals — written by ``run_universe_review``; an empty proposal is a row too.
The daily summary fills in each name's return from the first close after the
proposal over 21 / 63 / 126 / 252 sessions, beside the list's equal-weight
return and SPY's. Skill shows as additions above the list and removals below
it. Rows are never edited once a horizon is filled; nothing is read under 12
proposals (the verdict rule is in Decision 082).
"""
from __future__ import annotations

import json
import math
import statistics
from datetime import date, datetime, timezone
from typing import Any, Callable

from titantrade.config import STATE_DIR
from titantrade.fill_ledger import session_date
from titantrade.logger import get_logger
from titantrade.market_data import get_ohlcv
from titantrade.signals import trading_days_between

log = get_logger(__name__)

LEDGER_FILE = "curator_ledger.json"
HORIZONS = (21, 63, 126, 252)      # sessions after the first close following the proposal
MIN_PROPOSALS_FOR_READING = 12
BENCHMARK = "SPY"


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


def _save(ledger: dict[str, Any]) -> None:
    with open(STATE_DIR / LEDGER_FILE, "w") as f:
        json.dump(ledger, f, indent=2)


def record_proposal(doc: dict[str, Any]) -> bool:
    """Append the proposal's row (idempotent by its timestamp). Returns True when added."""
    pid = doc.get("generated_at")
    if not pid:
        return False
    ledger = load_ledger()
    if any(r.get("proposal_id") == pid for r in ledger["rows"]):
        return False
    p = doc.get("proposal") or {}
    ledger["rows"].append({
        "proposal_id": pid, "date": session_date(pid), "list": doc.get("list"),
        "members": list(doc.get("watchlist") or []),
        "adds": [a["ticker"] for a in p.get("add", []) if a.get("ticker")],
        "removes": [r["ticker"] for r in p.get("remove", []) if r.get("ticker")],
        "outcomes": {},
    })
    _save(ledger)
    return True


def horizon_return(closes: dict[str, float], after: str, h: int) -> tuple[float, str] | None:
    """Return in % from the first session after ``after`` to ``h`` sessions later, with that session's date;
    None while the horizon's bar is not there yet."""
    dates = sorted(d for d in closes if d > after)
    if len(dates) <= h or not closes[dates[0]]:
        return None
    return round((closes[dates[h]] / closes[dates[0]] - 1) * 100, 2), dates[h]


def update_curator_ledger(cfg: Any, bars_for: Callable[..., list[dict[str, Any]]] = get_ohlcv) -> int:
    """Fill every horizon whose session has passed, from SIP bars. Idempotent; a missing bar or a failed fetch
    is retried at the next summary. Returns the number of horizons filled."""
    ledger = load_ledger()
    now = datetime.now(timezone.utc)
    cache: dict[str, dict[str, float] | None] = {}
    filled = 0
    for row in ledger["rows"]:
        due = [h for h in HORIZONS if str(h) not in row["outcomes"] and trading_days_between(row["date"], now) > h]
        if not due:
            continue
        days = (now.date() - date.fromisoformat(row["date"])).days + 10
        for t in {BENCHMARK, *row["members"], *row["adds"], *row["removes"]}:
            if t not in cache:
                try:
                    cache[t] = {b["date"]: float(b["close"]) for b in bars_for(t, cfg, days=days, feed="sip")}
                except Exception as exc:  # noqa: BLE001
                    log.warning(f"Curator ledger: bars for {t} unavailable ({exc}) — retried at the next summary")
                    cache[t] = None

        def ret(t: str, h: int) -> float | None:
            r = horizon_return(cache[t], row["date"], h) if cache.get(t) else None
            return r[0] if r else None

        for h in due:
            spy = horizon_return(cache[BENCHMARK], row["date"], h) if cache.get(BENCHMARK) else None
            if spy is None:
                continue   # the horizon's session is not published yet (or SPY failed): the next summary retries
            members = [x for x in (ret(t, h) for t in row["members"]) if x is not None]
            row["outcomes"][str(h)] = {
                "date": spy[1], "spy": spy[0],
                "list_ew": round(statistics.fmean(members), 2) if members else None,
                "adds": {t: ret(t, h) for t in row["adds"]},
                "removes": {t: ret(t, h) for t in row["removes"]},
            }
            filled += 1
            log.info(f"Curator ledger: {row['date']} proposal at {h} sessions — list {row['outcomes'][str(h)]['list_ew']}%, "
                     f"adds {row['outcomes'][str(h)]['adds']}, removes {row['outcomes'][str(h)]['removes']}")
    if filled:
        _save(ledger)
    return filled


def _p_luck(k: int, n: int) -> float:
    """P(at least k of n by a coin flip)."""
    return round(sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n, 3) if n else 1.0


def _stat(excess: list[float]) -> dict[str, Any]:
    if not excess:
        return {"n": 0}
    beat = sum(1 for x in excess if x > 0)
    return {"n": len(excess), "median_vs_list_pp": round(statistics.median(excess), 2), "beat_list": beat, "p_luck": _p_luck(beat, len(excess))}


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per horizon: additions minus the list and the list minus removals (pp), the hit rate and its chance by luck."""
    out: dict[str, Any] = {"proposals": len(rows), "additions": sum(len(r["adds"]) for r in rows),
                           "removals": sum(len(r["removes"]) for r in rows), "min_for_reading": MIN_PROPOSALS_FOR_READING, "horizons": {}}
    for h in HORIZONS:
        adds, removes = [], []
        for r in rows:
            o = r.get("outcomes", {}).get(str(h))
            if not o or o.get("list_ew") is None:
                continue
            adds += [v - o["list_ew"] for v in o["adds"].values() if v is not None]
            removes += [o["list_ew"] - v for v in o["removes"].values() if v is not None]
        out["horizons"][str(h)] = {"additions": _stat(adds), "removals": _stat(removes)}
    if len(rows) < MIN_PROPOSALS_FOR_READING:
        out["verdict"] = f"No reading under {MIN_PROPOSALS_FOR_READING} proposals ({len(rows)} so far)."
    else:
        h = next((str(x) for x in (126, 63, 21, 252) if out["horizons"][str(x)]["additions"].get("n")), None)
        a = out["horizons"][h]["additions"] if h else {}
        out["verdict"] = (f"Reading at {len(rows)} proposals, {h} sessions: additions beat the list {a['beat_list']} of {a['n']} "
                          f"(median {a['median_vs_list_pp']:+.1f} pp; chance of at least that by luck {a['p_luck']:.0%}). No verdict before 24."
                          if h else f"Reading at {len(rows)} proposals: no horizon filled yet.")
    return out
