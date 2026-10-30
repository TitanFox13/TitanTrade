# Agent Instructions — the Curator

Since Decision 061 the LLM is out of the trading loop. One Claude job remains, and it cannot touch an order.

| Agent | Model | Cadence | Task |
|-------|-------|---------|------|
| The Curator | Claude Opus 4.8 (`CLAUDE_MODEL`, adaptive thinking) | First Sunday of the month, 15:00 ET (`monthly_curate`) | Universe-curation proposal + plain-language post-mortem |

Why this split: the October 2026 audit (Decision 060, Evidence 2–3) found that the analyst's selection, direction and confidence outputs carried no signal at the horizon the system trades, while the operator's universe and the mechanical layer produced the return. Universe curation is the one place where the LLM's breadth of knowledge is still worth a monthly call.

---

## Universe proposal (`curator.run_universe_review`)

**Input** (`build_universe_prompt`): the list under review — the `shadow_watchlist` (the operator's hand-picked names, tracked but not traded, Decision 070) when there is one, else the watchlist — with a brief per name — sector, dip state from the data bundle (close vs lookback high and trend SMA), ATR, 90-day trade statistics from the trade log (entries, exits, wins), and, on the scheduled run, recent headlines and the analyst-recommendation mix fetched at prompt time (`enrich=True`).

**Prompt constraints**: at most 2 removals and 2 additions, each with a one-line reason; liquid US large caps only; JSON only — `{"remove": [{"ticker", "reason"}], "add": [{"ticker", "sector", "reason"}], "notes"}`.

**Output**: `state/universe_proposal.json` (`generated_at`, `watchlist` = the list reviewed, `list` = `"shadow_watchlist"` or `"watchlist"`, `proposal`, `raw`, `status: "advisory — apply through the watchlist editor"`), a Discord embed, and `GET /api/universe-proposal`. The operator applies accepted changes with `PUT /api/watchlist`; nothing is applied automatically.

**Scored**: every proposal gets a row in the curator ledger (Decision 082, `curator_ledger.py`): its additions and removals against the list's equal-weight return and SPY at 21 / 63 / 126 / 252 sessions, filled by the daily summary; `GET /api/curator-ledger`. No reading under 12 proposals, a verdict at 24 — whether the monthly call earns its keep.

## Post-mortem (`curator.run_post_mortem`)

**Input** (`build_post_mortem_prompt`): the last 90 days of trade records (ticker, action, trigger, price, timestamp, reasoning).

**Output**: `state/post_mortem.json` (`generated_at`, `review: {summary, observations}`, `raw`), `GET /api/post-mortem`.

## Plumbing

- `_call_claude(system, user, cfg, cost_label)` is the only Claude client; every call is logged to `state/costs.json` with `run_type: "curator"`.
- `_extract_json` tolerates prose around the JSON object and markdown fences.
- A failed call fails the job (Discord failure embed) and leaves the previous proposal in place; the trading loop does not depend on it.
- Tests mock `titantrade.curator._call_claude`; no real tokens are spent.
