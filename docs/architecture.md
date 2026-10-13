# TitanTrade System Architecture

TitanTrade is a mechanical equity trading system: a Python backend builds a plan from prices, pushes it through programmatic risk gates and executes it on Alpaca with broker-side stops. The FastAPI server is the only front end (Decision 063 deleted the unused Flutter dashboard).

---

## Components

### Backend (`TitanTrade/`)
Data collection, the signal rules, the plan, the risk gates, execution, the monthly LLM curation, the SPY benchmark, the HTTP API and the built-in scheduler (APScheduler inside the always-on API container, `data/schedule.json`, America/New_York). See [TitanTrade/docs/architecture.md](../TitanTrade/docs/architecture.md) for internals.

### Legacy (`TitanTrade/legacy/`)
Frozen snapshots of the LLM-era pipeline (weekly Claude analyst, Gemini sentry, trailing / TP1 / pyramid manager, intraday price checks, FMP provider, the old backtester, their tests, probe scripts and prompt docs). Not importable, not tested, not built into the Docker image. The last commit on which all of it ran is tagged `v2-llm-pipeline`.

---

## System Diagram

```
APScheduler (api container, America/New_York)
├─ 09:00 Mon–Fri   fetch          data_fetcher → state/data_bundle.json
├─ 09:35 Mon–Fri   gapcheck       protection.check_gap_down_protection + executor.ensure_stop_coverage
├─ 10:15 Mon–Fri   execute        mechanical.refresh_plan → state/plan.json → executor.execute_trades
├─ 15:30 Mon–Fri   execute        (same)
├─ 16:30 Mon–Fri   daily_summary  notifier (Discord) + benchmark refresh
├─ Sun 16:00       full           fetch → signals → execute
└─ 1st Sun 15:00   curate         curator (Claude) → universe_proposal.json, post_mortem.json

   data_bundle.json ──┐
   broker positions ──┼──► mechanical.build_plan ──► plan.json
   trade_log.json  ───┘        items  NEW  (dip signal + free slot: entry, stop −12%, target +20%)
   open buy orders ───┘               HOLD (held since the strategy start: stop + target from the trade log)
                               watch (signal but no slot / risk-off / below trend), candidates, insurance,
                               free_slots, legacy_to_close
                                          │
                                          ▼
                          executor.execute_trades (market open only for orders)
                            1  orphan close — any non-core position without a plan item (cancel → settle → sell)
                            2  gap-down protection
                            3  SPY core → residual target (scale × 95% − overlay − planned slots)
                            4  stop-out cooldown scan (broker stop fills → 72 h cooldown)
                            5  expired-bracket resubmission
                            6  NEW items → risk_manager (8 gates) → one near-market bracket → GTC stop on fill
                            7  HOLD items → stop coverage; +target / holding-limit exits (cancel → settle → sell)
                                          │
                                          ▼
                                  Alpaca (paper / live)
                                          │
                                          ▼
                     state/*.json ◄──► FastAPI /api/* at https://trade.praguefun.cz (Cloudflare tunnel)
```

---

## The Strategy

- **Entry**: a watchlist name closes ≥ 8% below its 90-day high while above its 150-day SMA. Candidates are ranked deepest dip first and take the free slots (3 × 25% of equity, flat sizing). The order is one bracket at the live price + 0.3% with a −12% stop and a +20% target; a GTC stop replaces the bracket's DAY stop leg on fill.
- **Exits**: the broker stop, the +20% target and the 60-trading-day holding limit. Nothing else sells a position.
- **Core**: SPY is the residual of the book — exposure scale × 95% minus the overlay — so the account is fully invested unless slots are in use.
- **Insurance**: exposure halves only while SPY is below its 200-day SMA *and* fewer than half of the 11 sector ETFs are above theirs. New entries pause while risk-off; held positions keep their exits.
- **Parameters** live in `data/watchlist.json` → `settings.mechanical` (Decision 062 plateau) and are read at every run.

---

## Risk Architecture

Eight programmatic gates sit between the plan and every entry: earnings blackout, drawdown circuit breaker (with the ±50% suspect-value guard), cash reserve net of pending buys, overlay cap, position size (slot ≥ $500 notional), sector exposure, macro blackout, correlation. They are enforced in code; no input can bypass them.

Around the gates: broker-side GTC stops with one coverage helper on every path (Decision 060), a 1.5% minimum stop distance (055), the settled close for every exit (063 — cancel the resting stop, wait for the terminal state, sell, restore the stop if the sell fails), gap-down protection cross-checked against the live quote and the corporate-actions feed (053/054), and a 72 h re-entry cooldown after a stop-out with an override only after 24 h at ≥ 1% above the exit (056/059).

See [TitanTrade/docs/risk_management.md](../TitanTrade/docs/risk_management.md).

---

## The LLM's Place

Claude runs once a month (`curate`) and proposes universe changes plus a post-mortem of the month's trades. The proposal is written to `state/universe_proposal.json`, posted to Discord, and applied by the operator through `PUT /api/watchlist`. It cannot place, size or close an order. See [docs/agent_instructions.md](agent_instructions.md).
