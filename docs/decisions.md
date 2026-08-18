# Important Decisions Log

## Decision 056: Stop-out re-entry cooldown + stale-ADJUST guard (mid-August checkup)
**Date**: 2026-08-18
**Decision**: Close the two churn paths the DVN sequence of Aug 4–5 exposed — paths the ADR 055 guards deliberately didn't cover — plus a documentation accuracy pass. Strategy selection/sizing untouched; both fixes extend existing protective mechanisms to exits they missed.

### The DVN sequence (2026-08-04 → 08-05)
DVN's GTC stop filled at the Aug 4 open (13:34 UTC, 217 sh @ $43.42). The 14:15 run **re-bought the ticker 42 minutes later** ($43.65) — no cooldown applied, because the 72h re-entry cooldown is recorded when the executor *handles* an ABORT, and a broker-side stop fill is never "handled" by anything (it executes on Alpaca's servers; broker fills don't even appear in the trade log). The 19:30 run then applied the weekly review's **ADJUST stop $43.50 — computed Sunday for the OLD position** (basis $43.57, protecting profit) — to the NEW $43.65 entry: a 0.34% stop, which tagged out the next morning. Two distinct defects: a protective exit that starts no cooldown, and analyst levels applied to a position they weren't written for.

### Fix 1 — broker-side stop-outs start the re-entry cooldown (`entries.py`, `cooldown.py`, `executor.py`)
New `entries.record_stop_out_cooldowns(cfg)`, called at the top of `execute_trades` (before resubmission/entries): scans recent closed orders for **filled sell `stop`/`stop_limit` orders** whose fill time is inside the 72h window and records each as a cooldown event. Two deliberate design points:
- **The cooldown clock is stamped at the FILL time, not now()** (`cooldown._record_stop_out_cooldown`) — the scan runs every cycle, and re-stamping would silently extend the cooldown forever. Recording the fill time makes repeated detection idempotent (equal-or-newer existing record → no-op).
- **No `after` param on the orders query** — it filters on *submitted* time, and a GTC stop is typically submitted days before it fills; fills are filtered client-side on `filled_at`.
A protective exit is a protective exit: stop-outs now share the ABORT cooldown **and its override policy** (≥24h + sentry CONTINUE + price ≥1% above stop → early re-entry on confirmed recovery), so a noise stop-out doesn't lock out a genuine recovery leg. Trailing-stop exits cool down too — re-entry after a profit-taking exit is subject to the same confirmation. Scan failures log a warning and return 0 (that run simply behaves like the pre-056 executor).

### Fix 2 — ADJUST levels don't apply to a position opened after the review (`trade_state.py`, `executor.py`)
New pure `trade_state.position_opened_after(ticker, generated_at)`: True when the ticker's latest **entry-type** BUY in the trade log (trigger `weekly_thesis`/`bracket_resubmission` — pyramid ADDs enlarge a position, they don't open one) is newer than the thesis `generated_at`. The executor's Section 4a consults it before the cancel+replace: if the position was re-opened since the review was generated, the ADJUST levels belong to a position that no longer exists — skip, keep the entry-time stop, let next Sunday's review re-sync. Fails open (missing/damaged trade log or timestamps → apply as before), since applying the analyst's levels is the long-standing default.

### Also — documentation accuracy pass
Reading the full doc tree during the August checkups surfaced rot with real foot-gun potential, now fixed: `api_reference.md`/`deployment.md` still named **retired models as defaults** (`claude-sonnet-4-20250514` — whose retirement was the ADR 050 near-liquidation — and `gemini-2.0-flash`, which 404s) and documented FMP/SEC-API as the data stack (replaced in ADRs 035/040); parameter tables across `risk_management.md`/`features.md`/`agent_instructions.md` carried pre-ADR-032/046 values (20% cash reserve → 5%, confidence ≥0.70 → 0.55 floor + sizing curve, 5-day earnings blackout → 2, 40% sector cap → 50%, 3% fixed trail → 3.0×ATR, 24h macro blackout → 6h high-impact-only, 10% position cap → 25%, 2% ATR risk budget → 2.5%); gate counts said 6 (actual: 9, with overlay-cap/macro/correlation); "14-day thesis expiry" survived in several places despite the weekly-review cycle replacing it (Phase 1.12); `risk_management.md` still described the pre-ADR-037 pyramid mechanism. Every number was verified against `config.py`/`risk_manager.py`/`earnings.py`/`daily_sentry.py` constants, not against other docs.

### Status
10 new regression tests (`TestStopOutCooldown` ×5, `TestAdjustStaleReviewGuard` ×5); **534 tests green, touched files ruff-clean**. Deployed 2026-08-18 (both images).

## Decision 055: Same-run ABORT entry guard + minimum stop-distance floor (August checkup)
**Date**: 2026-08-04
**Decision**: Two execution fixes from the August check-up of the live server (Jul 23 → Aug 4 window — 0 errors, all jobs green, first clean window beating SPY on both raw and risk-adjusted return). Both fix low-cost but structural defects observed in the 2026-07-31 logs; strategy behavior is untouched (the strategy-hold decision stands).

### Fix 1 — bracket resubmission ignored the same-run sentry ABORT (`entries.py`)
At the Jul 31 14:15 run the sentry wrote `LLY: ABORT` (news-confirmed −4.3%) at 14:15:04; `resubmit_expired_brackets` bought a 12-share LLY bracket at 14:15:27; the abort handler then market-sold those shares at 14:15:45 — an 18-second forced round-trip (~$14 + fees). The 72h re-entry cooldown cannot prevent this: it is recorded when the abort is *handled*, which happens **after** resubmission runs in `execute_trades`. Root cause: the resubmit path (unlike the executor's per-ticker loop, which dispatches ABORT before any entry) never consulted the current signal.
**Fix**: `resubmit_expired_brackets` — which already loads `sentry_signals.json` for the cooldown override — now skips any ticker whose current signal is ABORT ("exiting, not entering"). Defense-in-depth: `_handle_bullish_entry` gets the same guard at the top (unreachable from the executor loop today, but any other caller now inherits the never-enter-on-ABORT guarantee). Skipping is always safe: if the ABORT is stale, the next sentry run (which always precedes execute in the schedule) refreshes it.

### Fix 2 — no minimum stop-distance floor (`pricing.py`, `entries.py`)
On Jul 31 19:30 URI entered at $1,084.25 with a $1,081.25 stop — **0.28%** below entry — and the GTC stop tagged out 27 minutes later on ordinary noise. The prompt tells Claude stops under 1.5× ATR get noise-stopped, but nothing in code enforced a floor; `bracket_levels_invalid` (ADR 044) only rejects stop ≥ entry. These degenerate stops typically arise when an ADJUST-review thesis (stop tightened to protect profit on a *held* position) is reused for a fresh entry after the position exits — the same artifact class as ADR 044.
**Fix**: new pure `pricing.stop_too_tight(entry, stop)` with `MIN_STOP_DISTANCE_PCT = 1.5` — refuses (skip + INFO log, same posture as `bracket_levels_invalid`) any fresh entry or resubmission whose stop sits < 1.5% below entry. Deliberately a **flat** floor, not ATR-scaled: 1× ATR exceeds the normal 3–5% thesis stop distance on high-vol names and would start refusing legitimate entries — the goal is catching degenerate artifacts (0.28%, 0.47% observed), not re-engineering stop policy. Fires only strictly below entry (at/above stays `bracket_levels_invalid`'s report). The existing tranche2 dip-buy validation (ADR 052) is unchanged.

### Also applied (ADR 049 follow-through)
The FANG → WMT watchlist swap — staged since Jun 17 — was finally applied to the live `data/watchlist.json` on titanserver in this deploy window. FANG was confirmed flat (position sold Jul 27, no open orders/trailing/cooldown state), satisfying ADR 049's "remove only when flat" rule. First WMT thesis arrives with the Sunday Aug 9 analysis.

### Status
7 new regression tests (`TestResubmitSameRunAbortSkip` ×3, `TestMinStopDistanceFloor` ×4); **524 tests green, touched files ruff-clean**. Deployed 2026-08-04 (both images rebuilt per the ADR 054 CLI-image lesson).
**Date**: 2026-07-23
**Decision**: Three robustness fixes from the July check-up of the live server — (1) gap-down protection consults the corporate-actions feed before liquidating on an implausibly deep gap, (2) the drawdown circuit breaker treats a wildly implausible broker account value as data corruption instead of a real drawdown (and refuses to record it as a peak), (3) a $500 minimum-notional floor in the position-sizing gate blocks dust orders. Strategy behavior is deliberately untouched (the strategy-hold decision stands); all three fire only in abnormal conditions.

### Why — the CRWD 4:1 split incident (2026-07-02 → 07-07)
CRWD split 4:1 with ex-date Jul 2. The market traded post-split (~$192.67) from the open, but **Alpaca paper applied the position adjustment three trading days late** (corporate-action records dated Jul 6, processed Jul 7). In the gap:
- **13:35 UTC Jul 2**: `check_gap_down_protection` saw 15 shares at $192.67 vs the (pre-split) $661 stop and market-sold at the artificial bottom. The ADR 053 live-quote cross-check *worked as designed* — the quote genuinely was $192.67 — proving a real quote can still be a split artifact. Equity showed a phantom −7.6% (Jul 2) and +9.1% snap-back (Jul 7) when Alpaca made the account whole; net damage ≈ $0, but the swing still pollutes `benchmark_metrics.json` (max DD −8.15%, vol 27%, Sharpe 0.89 are all artifacts — real numbers are milder).
- **14:15 UTC Jul 7**: mid-split-processing, `GET /v2/account` returned `portfolio_value` **$22,828** against a real ~$100k equity → circuit breaker tripped at a phantom "79.1% drawdown", blocking all entries that run. The inverse glitch would have been worse: `update_peak_value` would have written the spike into `peak_portfolio.json` and permanently tripped the breaker once real values returned.
- Separately, the month's logs showed **dust orders filling**: URI 0.01 sh ($11), ANET 0.19 sh ($35), DECK 0.18 sh — sizing shrinks to slivers when nearly all cash is committed, and the position-size gate only blocked *zero*-share orders. Dust can't carry stops (ADR 052) and just adds churn/fees.

### Implementation
- **Split guard** (`protection.py`, `broker.py`): when the (live-quote-confirmed) gap is deeper than `SPLIT_SUSPECT_GAP_PCT = 30%` below the stop — no organic large-cap overnight gap comes close; CRWD's was 71% — call the new `broker.get_recent_split_announcements(ticker)` (`GET /v2/corporate_actions/announcements`, ca_types=split, 10-day lookback). Announcement found → skip the market-sell, log + Discord alert (`notify_split_suspected`), let the broker's split processing reconcile. No announcement or feed error → sell as before (never weaken protection on missing data — same posture as ADR 053).
- **Suspect account-value guard** (`risk_manager.py`): `SUSPECT_VALUE_DEVIATION_PCT = 50%` vs the recorded peak. Below −50%: entries stay blocked (sitting out one run is cheap insurance either way) but the event is logged/alerted as *suspect broker data* (`notify_suspect_portfolio_value`, deduped to 1/30min) — not as a real crash — and the gate detail says so. Above +50%: `update_peak_value` refuses the write, preserving the peak file. Drawdown is also clamped at ≥0 so a refused spike can't report a negative drawdown.
- **Min-notional floor** (`risk_manager.py`): `MIN_POSITION_NOTIONAL = $500` checked in the sizing gate after the cash/overlay reductions; blocked orders fail `position_size` with a "below minimum notional (dust)" detail and flow into near-miss recording like any other gate failure. Covers both fresh entries and bracket resubmissions (both run `pre_trade_check`).

### Status
14 new regression tests (`TestGapDownSplitGuard` ×5, `TestSuspectPortfolioValue` ×5, `TestMinNotionalGate` ×4); **517 tests green, touched files ruff-clean** (also fixed 7 pre-existing lint findings in `protection.py`/`test_risk_manager.py`). Needs the usual deploy (`docker compose build api && docker compose up -d api` on titanserver). Note for the next checkup: judge benchmark metrics on windows starting ≥ 2026-07-08, or ignore the Jul 2–7 swing.

## Decision 053: Gap-down protection cross-checks the live quote before liquidating
**Date**: 2026-07-02
**Decision**: `check_gap_down_protection` now fetches the live market quote (`_fetch_current_price`) before firing its market-sell and skips when the live price is at/above the stop — so a stale/corrupted broker position mark can't liquidate a healthy position.

### Why
The morning after deploying ADR 052, the Alpaca paper account reported **CRWD at $196** on the position endpoint (prev-close $193) while the market-data feed showed the true price **$772.6** — an exact 4:1 ratio, i.e. a **phantom split** applied to the position's price but not its share count. Reported equity dropped ~$9k (entirely CRWD); true equity (`last_equity` $109,046) was unchanged. The sentry was unaffected (it reads the market-data feed), but `check_gap_down_protection` reads `position.current_price` and would have market-sold CRWD at the 09:35 ET gapcheck, mistaking the glitched $196 for a gap-down through the $661 stop — an unwanted liquidation of a healthy, winning position on bad broker data. This exposed a robustness gap: the destructive gap-down sale trusted a single data source.

### Implementation
- Inside the gap-detected branch, fetch `_fetch_current_price(ticker, cfg)` (local import to avoid a circular import; defensive try/except). If the live quote is present and `>= stop_price`, log and **skip** — the position mark is stale/glitched. A missing/failed quote **falls through to the sell**, so a genuine unprotected position (the FCX bare-position case) is never left bare.
- Threshold `>= stop_price`: only suppress when the live market says the stop hasn't even been reached — the tightest condition that preserves full protection for any real distress (live price below the stop still sells).

### Status
`protection.py` + 3 new regression tests (`TestGapDownLiveQuoteCrossCheck`: glitch-skip, confirmed-sell, quote-unavailable-sell); the existing gap test now mocks the quote. **503 tests green; touched files ruff-clean.** Deployed the same morning, before the 13:35 UTC gapcheck. (The CRWD mark itself is a transient Alpaca paper artifact expected to re-mark at the open — this fix guards against it and any future stale-mark misfire.)

## Decision 052: Two execution bugs from the 9-day log review — fractional-dust stops + tranche2 tight-stop 422
**Date**: 2026-07-01
**Decision**: Fix two recurring Alpaca 422s surfaced by reviewing the container logs since the 2026-06-22 restart (ADR 051 deploy). Both were low-severity (no capital at risk, 0 CRITICALs, 0 tracebacks) but one spammed a daily `[ERROR]` and the other silently dropped half of some entries.

### Bug 1 — fractional-dust stop failures (JPM 0.13-share, formerly ANET)
Every executor run tried to `ADJUST` the stop on a sub-1-share dust remainder and 422'd: `"fractional orders must be DAY orders"`. Root cause: `broker.place_native_stop_loss` hardcoded `time_in_force="gtc"` **and never floored the qty** — unlike `place_bracket_order`, which floors fractional qty to dodge this exact "0.19-share" bug. Both the stop-limit and the plain-stop fallback shared the flaw, so the fallback failed identically. A 0.13-share position can't take a stop at all (Alpaca can't place a stop on a fractional order; flooring → 0).
**Fix**: `place_native_stop_loss` now floors fractional qty to whole shares (protecting the bulk with a persistent GTC stop; the sub-share remainder is unstoppable dust) and, when the floored qty is < 1, places **nothing** and returns `{}` instead of erroring. Belt-and-suspenders: the executor `ADJUST` path skips positions with `0 < qty < 1` early, avoiding a pointless cancel+replace. Financial impact was trivial ($43 of JPM dust); the fix removes the daily error noise and makes the fractional-stop path correct for any future non-dust fractional position.

### Bug 2 — tranche2 dip-buy reused tranche1's stop → 422 on tight-stop theses (EQIX)
The 2-tranche entry places tranche2 at `entry × 0.985` (a 1.5% dip-buy) but reuses tranche1's stop. When the (adapted) stop sits within ~1.5% of entry — common for tight-stop theses on high-priced/low-vol names (EQIX: $1050.95 entry, $1045.95 stop = 0.47%) — tranche2's lower limit ($1035.19) lands at/below the stop and Alpaca 422s: `"stop_loss.stop_price must be <= base_price - 0.01"`. `bracket_levels_invalid` validated tranche1's entry against the stop but **never re-validated tranche2's lower limit**. Tranche1 still filled; tranche2 silently never placed — a partial-entry bug that under-deployed capital.
**Fix**: `entries._handle_bullish_entry` now runs `bracket_levels_invalid(tranche2_price, stop_price, tp)` before placing tranche2 and skips the dip tranche (keeping tranche1) with an INFO log instead of erroring. Buying below one's own stop is nonsensical anyway, so skipping is the correct behavior.

### Status
Both fixed in `broker.py`, `executor.py`, `entries.py`. 4 new regression tests (`test_bugfix_regressions.py::TestFractionalDustStop`, `::TestTranche2TightStopSkip`); **500 tests green, ruff clean**. Behavior-preserving for all whole-share positions and normal-stop entries. **Not yet deployed** — needs `docker compose build api && docker compose up -d api` on titanserver for the running container to pick it up (the current image predates the fix).

## Decision 051: Benchmark metrics — beta / alpha / Sharpe vs SPY
**Date**: 2026-06-22
**Decision**: Measure the strategy on **risk-adjusted** terms against SPY (beta, Jensen's alpha, Sharpe, capture ratios, tracking-error/information ratio, max drawdown), not raw return, via a new `benchmark.py` module fed by the Alpaca portfolio-equity history.

### Why
A downside-protected, sub-1-beta strategy underperforms SPY in a strong bull *by construction* — it holds cash, runs stops that clip the right tail, and keeps a partial passive core. Raw return vs SPY therefore can't answer the real question ("is it adding value, or just under-exposed?"). Beta isolates market exposure; alpha is what's left after paying for that exposure; Sharpe and up/down capture say whether the protection earns its keep. These are the numbers that decide whether the strategy can succeed or is dominated by simply holding SPY.

### Implementation
- `benchmark.py`: pure `compute_metrics(strategy_levels, spy_levels, rf_annual=0)` (population/sample stats in plain Python, no numpy) returning beta, annualized alpha, Sharpe (strategy + SPY), info ratio, correlation/R², annualized vol, total + excess return, up/down capture, and max drawdown for both. `compute_benchmark()` wires it to live data: Alpaca `/v2/account/portfolio/history` (1D equity) + SPY daily closes, aligned by trading date. `classify()` emits a one-line plain-English verdict.
- Data source: **Alpaca portfolio history**, not trade-log reconstruction — it's the true mark-to-market equity each day.
- Surfaced three ways: CLI `python -m titantrade benchmark [days] [--since YYYY-MM-DD]`; API `GET /api/benchmark` (+ `/api/benchmark/refresh`); a "Benchmark (vs SPY)" line on the daily Discord summary (the `daily_summary` job refreshes `state/benchmark_metrics.json` before sending).
- `broker.get_portfolio_history()` added (the only new Alpaca call).

### The off-by-one that would have lied to us
Alpaca stamps 1D end-of-day equity at the market close in **US/Eastern** (20:00 ET = 00:00 UTC the *next* calendar day). A naive UTC-date conversion is one day late, pairing each strategy day with the *next* session's SPY close — which produced spurious **negative** betas (−0.05 to −0.25) in the first run. Fixed by deriving the session date in market time (`America/New_York`); a regression test locks it. After the fix, betas are sensible and positive (0.42–0.89).

### Findings (paper account, verified live on the server)
- **Since strategy inception (2026-03-30, 56 trading days)**: strategy +8.7% vs SPY +18.2%. **Beta 0.42**, **alpha +6.6%/yr** (slightly positive), Sharpe 3.35 vs SPY 5.26, vol 11.5% vs 14.5%, max DD −3.7% vs −4.5%, up-capture 0.46 / down-capture 0.40. The underperformance is almost entirely the **low beta** (under-exposure in a straight-line bull), *not* negative selection — alpha was marginally positive.
- **Stabilized window (since 2026-06-01, 13 days)**: strategy +0.4% vs SPY −1.5%. **Beta 0.84**, Sharpe 0.46 vs SPY −1.44, up-capture 0.98 / **down-capture 0.71** — the ideal defensive signature (keeps the upside, eats less of the downside). Verdict: adding value.
- Annualized alphas over <20-day windows (+32%, +67%/yr) are noise in magnitude — only the **sign, Sharpe comparison, and capture ratios** are meaningful at this sample size.

### Status
Built + tested (20 new unit tests, 496 total green; ruff clean). Evaluated against the live paper account. **Not yet deployed** — the API image is baked, so beta/alpha won't appear on the daily summary or `/api/benchmark` until the container is rebuilt (`docker compose build api && docker compose up -d api`). The verdict to watch over a full cycle: is the sentry's protection (down-capture < 1) saving more than its whipsaw costs?

## Decision 050: Analyst model — retired Sonnet 4 → Opus 4.8 + adaptive thinking (URGENT prod fix)
**Date**: 2026-06-17
**Decision**: Switch the weekly analyst from `claude-sonnet-4-20250514` to `claude-opus-4-8` with adaptive thinking.

### The bug (production-breaking)
The weekly analyst was hardcoded to `claude-sonnet-4-20250514` (Claude Sonnet 4, May 2025). A Models-API probe confirmed that model now **returns 404 — it retired 2026-06-15**. The last successful weekly run was Jun 14 (the day before). **The next scheduled run is Sunday 2026-06-21 and would 404.** A failed analysis produces no `weekly_thesis.json`, which makes `protection.close_orphaned_positions` treat **every held position as an orphan and market-close it** (ADR 049 removal-safety mechanism) — i.e. left unfixed, the bug silently liquidates the entire portfolio on Sunday.

### Why Opus 4.8 (not just any current model)
The earlier structural study established the strategy's entire edge rides on the analyst's stock-picking quality (with weak signals the overlay was a net loser; the SPY core did all the work). The analyst is the single highest-leverage model in the system, and it runs only weekly — so the most capable model is the obvious choice. Cost delta is trivial: historical Claude usage was ~$3–4/mo; Opus 4.8 ($5/$25 per MTok) projects to ~$4–8/mo with adaptive thinking vs ~$2.5/mo for Sonnet 4.6 — a few dollars/month on a $109k book. `temperature` (was 0.3) is a non-loss: Opus 4.8 removed sampling params and steers via adaptive thinking + the (already detailed) prompt.

### Changes
- `config.py`: `claude.model` → `claude-opus-4-8` (default + `CLAUDE_MODEL` env fallback); `max_tokens` 8192 → 16000 (headroom for thinking tokens, still under the non-streaming ceiling); `temperature` retained for the legacy Sonnet path but no longer sent.
- `weekly_analyst._call_claude`: adds `thinking={"type":"adaptive"}` (effort defaults to `high`); **drops `temperature`** (400s on Opus 4.8/4.7); adds `refusal` stop-reason handling and **thinking-aware text extraction** (adaptive thinking can lead with thinking blocks, so `content[0]` is no longer the answer — pull the first text block).
- `cost_logger.py`: added `claude-opus-4-8` ($5/$25) and other current model prices (exact-match keys); the old table missed `claude-sonnet-4-20250514` (it fell to the $5/$15 default, which is why historical logged cost ran ~1.5× high) and had a stale Opus price.
- Prompts themselves unchanged — they're well-built; the model was the issue.

### Validation
- A minimal (~$0.001) live probe confirmed SDK `anthropic 0.86.0` + `claude-opus-4-8` + adaptive thinking works end-to-end and returns clean JSON. No SDK bump needed.
- +3 `_call_claude` unit tests (thinking-aware extraction, adaptive-thinking requested + no temperature, refusal raises). **476 tests green**; ruff clean.

### Status — DEPLOY BEFORE SUNDAY 2026-06-21
Unlike the other staged changes, this one is **urgent**: production still runs the retired model and will 404 on the next weekly run. Must rebuild + redeploy the API container (`docker compose build api && docker compose up -d api`) before the Sunday 16:00 ET `sunday_full` job. The Gemini sentry (`gemini-3.1-flash-lite`) is current — no change.

## Decision 049: Watchlist tweak — drop FANG (redundant), add WMT (defensive)
**Date**: 2026-06-17
**Decision**: Replace FANG with WMT in the watchlist. Net 15 names, now across 9 sectors (adds Consumer Staples).

### Why
A correlation/beta analysis of the 15-name list (daily returns, ~500d) found:
- The list is well-built overall — beta spans 0.30 (HCA) to 1.85 (ANET), 8 sectors, and only two redundant pairs.
- **DVN + FANG correlate 0.86** — both oil & gas E&P tracking WTI, i.e. one bet in two slots. DVN is currently held; FANG is not — so dropping **FANG** removes the redundancy with zero forced liquidation.
- The book had **no Consumer Staples / Utilities** — a gap for a strategy whose edge is downside protection. Of candidate defensives (WMT/PG/COST/SO/KO), **WMT** was the best fit: defensive (beta 0.46) and strongly diversifying (0.17 avg corr to the rest, max 0.28), but unlike pure low-vol names (SO/KO at ~0 beta) it actually trends — so the momentum overlay will *use* it rather than leave a dead slot. It gives the overlay something to rotate INTO in a risk-off instead of only cash.

### Why NOT add mega-cap tech
The always-on 30% SPY core already holds the Mag-7 (~30%+ of SPY). The overlay's job is to own what SPY *underweights*; adding NVDA/MSFT/etc. would double-bet the core and raise correlation, not diversify. The absence of Mag-7 is a deliberate complement-the-core choice, consistent with the defensive identity.

### Caveat
A watchlist change is **not backtest-validatable** — choosing names while knowing their history is survivorship bias (the trap avoided throughout this work). This is a forward design decision judged on philosophy (diversification, defensive ballast, liquidity, trendability), to be assessed on live paper performance.

### Removal safety — what happens to an untracked ticker
Verified for this change: removing a ticker doesn't orphan stale state. The weekly analyst only analyzes watchlist (+ hedge) tickers, so a removed name gets no new thesis; on the next cycle `protection.close_orphaned_positions` market-closes any held position with no thesis (`trigger="thesis_expired"`) and cleans its trailing state. Caveats: it's a *market* close (not a managed exit), and in the gap before it fires the position keeps only its standing broker stop (the sentry also iterates the watchlist, so it loses news monitoring). Rule of thumb: **remove a ticker only when it's flat, or accept a market-close of a held one.** FANG was confirmed flat (no position, 0 open orders, no trailing/cooldown state) — its only trace is an inert thesis entry that self-clears on the next Sunday run.

### Status
Applied to the **code default** (`config.py`) and the backtest `SECTOR_MAP`. **Not pushed to the live `data/watchlist.json`** — the running paper system keeps the old list until the operator updates it (via the Flutter watchlist screen or directly) in a deploy window.

## Decision 048: Widen the trailing-stop ATR multiplier 2.5 -> 3.0 (more bull, same bear)
**Date**: 2026-06-17
**Decision**: Raise `trading.trailing_atr_multiplier` from 2.5 to 3.0 (live config + backtest simulator default), to capture more upside in rallies without giving up the downside protection.

### Why this is the right (asymmetric) lever
The goal was "gain more in bull without losing the bear advantage." Symmetric levers fail this: raising the SPY core 30%→45% gained bull (+24%→+32%) but *equally* worsened the stress window (−5%→−7.6%). The trailing-stop width is **structurally asymmetric** — it only governs positions already up 5%+ (winners that activated trailing). A *loser* never activates it and exits at the fixed initial stop regardless. So widening it lets winners run further **without loosening the protective stop on losers.**

### Evidence (regime-segmented backtest, real 2021–2026 cycle incl. the 2022 −25% bear)
Downloaded 1,400 trading days (2020-11 → 2026-06) so the test spans a *real* bear, not just the prior bull-only window. Per-window return / max-drawdown:

| trailing | 2022 BEAR (SPY −25%) | 2021 bull | 2024 bull | FULL 21–26 (SPY +103%) |
|---|---|---|---|---|
| 2.5× (old) | −12.3 / DD14.9 | +17.4 / DD8.3 | +9.2 | +31.8 / DD16.8 |
| **3.0× (new)** | −12.8 / DD15.4 | +21.2 | +10.9 | +46.1 / DD16.2 |
| 3.5× | −10.3 / DD12.9 | +24.6 | +11.2 | +58.0 / DD16.6 |

- Wider trailing **improves the bull side** (full cycle +32%→+46%→+58%) and **does not hurt the bear** — the 2022 column is flat-to-better and max drawdown never rises.
- Beyond 3.5× the 2022-bear result is **completely flat** (identical at 4.5×/6.0×/"off"), proving the trailing **isn't the binding exit in a bear** — the initial stop + defensive thesis are. So widening it *cannot* increase downside risk; this is not a disguised "more beta" trade.

### Why 3.0 and not 3.5 (where the backtest scored highest)
3.5× scored best on the *full* sample (+58%), but a robustness check shows that peak is **noise, not signal**:
- **Jagged response surface** (full window, fine sweep): 2.75→+49.6, 3.0→+46.1, 3.25→+54.1, 3.5→+58.0, 3.75→+47.7, **4.0→+18.3**, 4.5→+31.7. A 0.25 step swings the result 20-40 pts and 4.0 (next to the "peak") collapses — that's a dartboard, not a plateau.
- **Split-sample argmax disagrees:** best multiplier is 3.5× full, **3.25× in 2021-23, 2.75× in 2024-26**. The peak location is an artifact of the price path, not a property of the strategy. In the recent half, 3.5× actually *underperformed* 2.75× (+41.8 vs +48.5).
- **Selection bias:** the value that maxes a backtest is the one whose number is most luck-inflated; its forward performance is systematically worse than the backtest.
- **Backtest under-penalizes width:** wider trailing gives back more open profit when a live winner reverses; the bull-heavy synthetic-signal sample barely charges for this.

Robust takeaway = the **region** (cliff below 2.5, another above ~3.75; 2.75-3.5 all "fine"), not a point. 3.0 is a round, central, conservative pick inside the good band — chosen for robustness, not because it's uniquely optimal (2.75-3.25 would be equally defensible). The *direction* (let winners run, no downside cost) is the trustworthy finding; the precise magnitude is not.

### Caveats
Still validated on synthetic technical signals, not Claude's. But the mechanism is **signal-agnostic** (it's about *how long* to hold a winner, not *which* stocks — unlike the pyramiding finding, which was signal-dependent and didn't transfer to live). The live account is **paper**, so deploying this *is* the forward test. Reversible one-line config change.

### Validation
Full suite green (473 tests, +0 — change is parametric); ruff clean. **Staged, not deployed** — production keeps running on 2.5 until the next deploy window per the operator's "don't disturb the running system" instruction.

## Decision 047: Backtest defaults to the live strategy (was silently running a broken legacy path)
**Date**: 2026-06-17
**Decision**: Make the production-faithful `strategy_v2` the default for every backtest entry point, and fix the correctness bugs in the legacy v1 path.

### The bug
A backtest over 3 years of data (2023-04 → 2026-05, 15 tickers) produced only **7 trades** with a nonsensical **0% win rate despite 21 take-profit exits**. The synthetic-thesis signal source was healthy — it generated **500 BULLISH signals (474 above the confidence gate)** — but the simulator executed almost none of them.

### Root cause (three compounding faults, all in the legacy v1 entry path)
1. **`run_backtest` defaulted to `strategy_v2=False`** — the legacy *dip-buy* strategy that the live executor no longer runs. The CLI `backtest` command, the dashboard action (`POST /api/actions/backtest`), and direct calls all inherited this default, so every backtest measured a strategy nobody trades.
2. **Dip-buy limit orders rarely fill on momentum signals.** v1 places limit buys *below* market (`close × 0.995`) and waits for a pullback, but the synthetic signals are momentum/uptrend (golden cross, MACD positive) where price keeps rising. Worse, unfilled orders **never expired** and the entry loop skips any ticker with a pending order — so one stuck order blocked that ticker permanently.
3. **`_fill_buy` set `take_profit_price` to the entry limit price** (not the thesis TP), so the rare fills instantly "took profit" at break-even → the fake 0% win rate. It also **overwrote** an existing position when the second tranche filled, silently dropping tranche-1 shares (and the cash spent on them).

### Fix
- **`strategy_v2=True` is now the default** in `run_backtest`, recorded in the result `config`, and pinned explicitly in the API action. `strategy_v2` mirrors the live executor: near-market entries, ATR trailing stops, TP1 partial exits, pyramiding, always-on SPY core.
- CLI: `backtest` runs v2 by default; **`--legacy` / `--v1`** opts into the old path (`--v2` still accepted as a no-op).
- **v1 correctness fixes** (kept reachable for the confidence-scaling A/B study): `_fill_buy` now takes the stop/TP from the thesis carried on the order (not the entry price), **accumulates** a second tranche instead of overwriting, and unfilled limit orders **expire** after `limit_order_ttl_days` (default 10) so a dip that never comes can't park a ticker forever.
- `run_ab_comparison` is pinned to `strategy_v2=False` (v2 force-enables confidence scaling, which would make the A/B arms identical).

### Validation
- Default backtest on real data: **7 → 243 trades, 63% win rate, profit factor 1.41**, max DD 15.2%. In SPY's worst drawdown window (−19%) the strategy lost only **−5%** — downside protection working as designed.
- Legacy path (`--legacy`): **7 → 161 trades, 56% win, PF 1.12** with real stop/TP exits (no more fake 0% win rate).
- Full suite green: **472 passed (+6 new)**.

### Important caveat (carried forward)
This backtest still uses **synthetic technical theses with zero LLM calls** (`synthetic_thesis.py`) and does not replay the Gemini sentry. It validates the **risk-management and execution machinery**, NOT the AI alpha — and it is **survivorship-biased** to today's watchlist. It is *not* a measure of the live strategy's "real probability of success"; only forward out-of-sample paper/live trading is, and that needs far more than the current ~24 closed trades to be meaningful.

## Decision 041: Daily log rotation + Gemini 503 model-fallback chain
**Date**: 2026-06-09
**Decision**: Two operational fixes from a post-deploy log review (~1 trading day after ADR 040).

### Fix 1 — log files now roll at UTC midnight (`logger.py`)
`get_logger` computed the date for the `{name}_{YYYY-MM-DD}.json` filename once, and loggers are cached per process — so the always-on API container piled every day's records into the file dated at process start (e.g. Jun-9 logs landed in `*_2026-06-08.json`). Data was never lost, but daily files didn't rotate, making log review confusing. New `DailyJSONFileHandler` re-points the stream to the current date's file on the first emit after midnight, preserving the one-file-per-module-per-day convention. (2 new tests.)

### Fix 2 — Gemini model-fallback chain (`daily_sentry._call_gemini`, `config.py`)
**Investigation** (the operator suspected a week-long Gemini outage): across ~10 weeks of logs there were **506 × HTTP 503 and zero 429** — i.e. purely Google-side "model overloaded" capacity errors on `gemini-2.5-flash`, never our quota/rate limit. A live multi-model probe found 2.5-flash **up (4/4)** alongside flash-lite / flash-latest / 2.5-pro; only the retired `gemini-2.0-flash` is gone (404). So it is **not an outage** — it's intermittent 503 spikes (worst sustained patch was mid-April at 44-57/day; recent days 0-23 retries with 0-2 actual check failures). A [Google AI dev-forum](https://discuss.ai.google.dev/t/frequent-503-the-model-is-overloaded-errors-on-gemini-2-5-flash/103550) search confirms 503 is a known, widespread, all-tiers capacity issue with ~5-15min recovery, and the recommended mitigation is retry + **switch to an alternate model** (separate capacity pool).
**Fix**: `_call_gemini` now tries the primary model then falls back through `cfg.gemini.fallback_models`, each with `per_model_retries` (2) bounded attempts. **Update (same day):** the primary was moved from `gemini-2.5-flash` to **`gemini-3.1-flash-lite`** — current-gen, **cheaper** ($0.25/$1.50 vs $0.30/$2.50 per 1M in/out), and verified to accept our structured-output + `thinkingBudget=0` request — with the previous 2.5-flash setup as the fallback chain (`gemini-2.5-flash` → `gemini-2.5-flash-lite` → `gemini-flash-latest`). (For reference, `gemini-3.5-flash` at $1.50/$9.00 is ~5×/3.6× the price for zero benefit on a binary classification, and 3.x "thinking" risks inflating output cost — not used.) A 503 on the primary now usually answers immediately on a different pool instead of degrading to the CONTINUE fallback. The existing 5-attempt backoff and the final fall-back-to-CONTINUE (broker stops still protect) remain as the safety net. `-latest` in the chain also future-proofs against version retirement (the 2.0-flash 404 trap). (3 new tests.)

**Why not other options**: a paid tier / Vertex doesn't fix 503 (it's not quota — affects all tiers); switching the whole sentry to another provider is disproportionate given the low real impact (retries + safe fallback already keep it functional). The model-fallback chain is free, low-risk, and directly addresses the failures.

**Validation**: full suite green (+5 tests); ruff clean. Diagnosis done against the live paper deployment + web search.

## Decision 001: Dual-AI Architecture (Claude + Gemini)
**Date**: 2026-03-29
**Decision**: Use Claude for weekly deep analysis and Gemini Flash for daily sentiment checks.
**Reasoning**:
- Claude Opus/Sonnet excels at complex reasoning and structured analysis
- Gemini Flash is optimized for speed and cost on simple classification tasks
- Weekly deep dives don't need sub-second latency; daily checks do
- Cost optimization: ~$0.50/week for Claude vs ~$0.01/day for Gemini Flash
**Trade-offs**:
- Two API integrations to maintain instead of one
- Potential inconsistency between models' interpretations
- Mitigated by clear prompt engineering and structured JSON outputs

## Decision 002: Alpaca Markets as Brokerage
**Date**: 2026-03-29
**Decision**: Use Alpaca Markets API for trade execution.
**Reasoning**:
- Free paper trading with identical API to live trading
- Commission-free stock trading
- Well-documented REST and streaming APIs
- Python SDK available (`alpaca-trade-api`)
- Supports fractional shares
**Trade-offs**:
- Limited to US equities (no international markets)
- No options trading via API (stock only for now)

## Decision 003: JSON File-Based State (No Database)
**Date**: 2026-03-29
**Decision**: Use JSON files in `state/` directory for persistence instead of a database.
**Reasoning**:
- Simplicity: No database setup, connection strings, or migrations
- Portability: State files can be committed to repo or backed up easily
- Sufficient for 10-stock watchlist with daily updates
- GitHub Actions can read/write files in the repo
**Trade-offs**:
- No concurrent write safety (acceptable for single-process cron jobs)
- No query capability (acceptable for small dataset)
- Future migration to Supabase planned if scale increases

## Decision 004: GitHub Actions for Scheduling
**Date**: 2026-03-29
**Decision**: Use GitHub Actions cron workflows instead of a dedicated server.
**Reasoning**:
- Zero infrastructure cost (free tier sufficient)
- No server maintenance or uptime monitoring
- Secrets management built-in
- Easy to modify schedules via YAML
**Trade-offs**:
- GitHub Actions cron has ~5-15 minute variance on schedule
- Not suitable for intraday high-frequency strategies
- Acceptable for our weekly + daily cadence

## Decision 005: FMP API for Financial Data
**Date**: 2026-03-29
**Decision**: Use Financial Modeling Prep (FMP) API as primary data source.
**Reasoning**:
- Single API for both price data AND news headlines
- Free tier available for development
- Covers fundamentals, technicals, and news
- Good documentation and reliability
**Trade-offs**:
- Rate limits on free tier (250 requests/day)
- Paid tier needed for production ($14/month)
- News coverage may not be as comprehensive as Bloomberg

## Decision 006: SEC-API.io for Regulatory Filings
**Date**: 2026-03-29
**Decision**: Use SEC-API.io for real-time SEC filing monitoring.
**Reasoning**:
- Structured API for 8-K, 10-Q, 10-K filings
- Near real-time filing detection
- Pre-parsed filing metadata
**Trade-offs**:
- Additional API key to manage
- Paid service ($49/month for real-time)
- Could use free SEC EDGAR RSS as fallback

## Decision 009: Native Broker-Side Stop Orders (Not Software Stops)
**Date**: 2026-03-29
**Decision**: Use Alpaca's native stop and bracket orders, not software price-checking.
**Reasoning**:
- Software stop-loss (cron job checks price twice daily) has a 12+ hour gap between checks
- A stock can fall 20%+ overnight; a software stop wouldn't fire until the next run
- Alpaca native stops fire in real time at the broker level, even if our bot is completely offline
- Bracket orders (entry + stop + take-profit in one atomic submission) eliminate timing gaps
**Implementation**:
- Entry: `bracket` order type with `order_class: "bracket"`
- Stop leg: `stop_limit` with 1% buffer below stop price (avoids catastrophic slippage)
- Take-profit leg: limit sell at target (optional, only when Claude identifies clear catalyst)
- Standalone `stop_limit` GTC order as fallback if position exists without a stop
**Trade-offs**:
- Bracket orders are `time_in_force: "day"` only on Alpaca, not GTC
  - Workaround: re-submit bracket each morning if limit buy hasn't filled
- Stop-limit (not pure stop) means we could miss a fill if stock gaps through both prices
  - Acceptable - better than unlimited downside

## Decision 007: 5% Stop-Loss and 10% Position Sizing
**Date**: 2026-03-29
**Decision**: Hard 5% stop-loss and max 10% position size.
**Reasoning**:
- 5% stop-loss limits max loss per trade to 0.5% of portfolio
- 10% position limit ensures diversification across watchlist
- Conservative enough for an automated system
- Prevents catastrophic losses from a single bad trade
**Trade-offs**:
- May get stopped out of volatile but ultimately profitable positions
- 10% limit means max 100% invested with 10 stocks (no concentration bets)
- Acceptable for a risk-managed automated system

## Decision 010: Two-Pass Analysis (Individual + Portfolio Ranking)
**Date**: 2026-03-29
**Decision**: Use two separate Claude calls per weekly cycle - one per stock, then one portfolio-level.
**Reasoning**:
- Pass 1 in isolation prevents anchoring bias between stocks
- Pass 2 adds portfolio-level thinking (diversification, correlation, regime)
- A single mega-prompt with all 10 stocks would exceed quality thresholds
- Selecting top 3-5 from 10 BULLISH calls prevents overtrading
**Trade-offs**:
- 11 Claude API calls per week instead of 1 (10 stocks + 1 ranking)
- More expensive but the quality difference is substantial
- Pass 2 may disagree with Pass 1 (this is the point - portfolio > individual)

## Decision 011: Pre-Computed Technical Indicators
**Date**: 2026-03-29
**Decision**: Compute RSI/MACD/Bollinger/ATR/SMA before sending to Claude.
**Reasoning**:
- Claude can reason about "RSI at 28" much better than about 5 OHLCV rows
- 250-day history needed for 200-SMA but only 5 days sent as OHLCV
- Indicators are deterministic - no ambiguity in computation
- ATR doubles as the position sizing input (vol-adjusted)
**Implementation**:
- Pure Python computation (no numpy/pandas dependency)
- Wilder's smoothing for RSI and ATR (standard industry method)

## Decision 012: Three-Layer Sentry (Market + Price + News)
**Date**: 2026-03-29
**Decision**: Add price-based and market-wide checks to the daily sentry.
**Reasoning**:
- News is lagging: a stock drops 5% before the headline appears
- Price catches insider selling, block trades, and other non-public information
- SPY check catches correlated risk that per-stock analysis misses
- 3% price override is a hard safety rail - even if Gemini says CONTINUE
**Trade-offs**:
- More aggressive: may force exits that recover later
- Acceptable: preserving capital is job #1

## Decision 013: Performance Feedback Loop
**Date**: 2026-03-29
**Decision**: Feed last 4 weeks of trade results back into Claude's prompt.
**Reasoning**:
- Without feedback, Claude repeats the same mistakes week after week
- Confidence calibration shows if Claude is systematically over/underconfident
- Per-ticker stats reveal blind spots (always wrong on TSLA, always right on AAPL)
- 52-week thesis archive enables long-term pattern detection
**Trade-offs**:
- Larger prompt = more tokens = higher cost
- Risk of recency bias (last 4 weeks may not represent the future)
- Mitigated by using rolling windows and bucket-based calibration

## Decision 008: Structured JSON Output from AI
**Date**: 2026-03-29
**Decision**: Require strict JSON output format from both AI agents.
**Reasoning**:
- Programmatically parseable without regex or NLP
- Schema validation possible
- Consistent structure across all runs
- Easier logging and comparison
**Trade-offs**:
- May reduce AI's ability to express nuance
- Requires careful prompt engineering to enforce format
- Mitigated by including "reasoning" field for free-text explanation

## Decision 014: Server-Based Deployment with Docker (Primary over GitHub Actions)
**Date**: 2026-03-29
**Decision**: Use Docker containers on a personal server with cron jobs as the primary deployment method, replacing GitHub Actions as the default.
**Reasoning**:
- Server cron is precise; GitHub Actions cron has ~5-15 minute variance
- No dependency on GitHub uptime or runner availability
- State persists locally via Docker volumes instead of git commits
- No risk of merge conflicts on state files from concurrent bot pushes
- More operational control and visibility
**Trade-offs**:
- Requires maintaining a server (uptime, security, updates)
- Must handle own monitoring and alerting for missed runs
- Mitigated by cron output logging and server-level monitoring
- GitHub Actions workflows remain in repo as a documented alternative

## Decision 015: Flutter Desktop App for Trade Tracking
**Date**: 2026-03-29
**Decision**: Add a Flutter desktop app (`titan_trade_app/`) as a companion dashboard for TitanTrade.
**Reasoning**:
- JSON log files and state files are machine-readable but not human-friendly for quick review
- Need to understand the full context behind each trade: thesis, sentry signals, execution details
- Desktop-first (Windows/macOS/Linux) since it reads local state files from the TitanTrade directory
- Flutter enables cross-platform desktop from a single codebase
**Trade-offs**:
- Adds Dart/Flutter as a second language alongside Python
- Mostly read-only: the app reads state files but can modify `data/watchlist.json`
- Requires Flutter SDK installed for development
**Architecture**:
- Riverpod for state management, go_router for navigation
- Polls JSON files every 30 seconds (state changes infrequently)
- Dark theme following financial/trading app conventions

## Decision 016: All-Gate Evaluation and Near-Miss Recording
**Date**: 2026-03-29
**Decision**: Modify `pre_trade_check` to evaluate all 6 risk gates instead of short-circuiting on first failure. Record near-misses (blocked by <= 2 gates) to `state/near_misses.json`.
**Reasoning**:
- Short-circuiting hid information: we only knew the first gate that blocked, not all of them
- Near-miss tracking reveals opportunities that were close to execution
- Understanding which gates block most often helps calibrate risk parameters
- Trade context snapshots (market regime, technicals, news) enable post-hoc analysis of why trades were/weren't made
**Trade-offs**:
- Slightly more computation per check (all gates run even when the first fails)
- Near-miss file grows over time (mitigated: only saves when <= 2 gates fail)
- Gates 4/5/6 have dependencies (position size needs cash reserve): handled by marking dependent gates as "not evaluated" when their prerequisite fails

## Decision 017: Operational Cost Tracking
**Date**: 2026-03-29
**Decision**: Log per-API-call token usage and estimated costs to `state/costs.json` for all AI model invocations.
**Reasoning**:
- AI model costs are a real operating expense that affects net profitability
- Token counts from Claude (`message.usage`) and Gemini (`usageMetadata`) are available in API responses
- Per-call granularity enables cost attribution to specific stocks and run types
- Estimated costs use published pricing tables (configurable in `cost_logger.py`)
**Trade-offs**:
- Cost estimates are approximate (don't account for caching, batching discounts)
- Costs file grows with every API call (acceptable: ~20 records/week)
- Pricing tables need manual updates when model pricing changes

## Decision 018: Statistics Dashboard with Net P&L
**Date**: 2026-03-29
**Decision**: Add a Statistics screen to the Flutter app showing realized P&L (closed trades), unrealized P&L (open positions), operational costs, and net P&L.
**Reasoning**:
- Trading P&L alone is misleading without accounting for operational costs (AI, data APIs)
- Round-trip matching (BUY->SELL pairs per ticker) gives accurate per-trade realized returns
- Combining realized + unrealized + costs gives the true picture of system profitability
- Per-service cost breakdown helps identify cost optimization opportunities
**Trade-offs**:
- Round-trip matching assumes one position per ticker at a time (valid given 10% position limit)
- Partial fills are matched FIFO, which may not reflect exact broker execution order
- Subscription costs (FMP, SEC-API) not yet tracked (only per-call AI costs for now)

## Decision 019: Bracket Order Resubmission
**Date**: 2026-03-29
**Decision**: Automatically resubmit expired bracket orders at the start of each execution cycle, after re-running all risk gates with current portfolio values.
**Reasoning**:
- Alpaca bracket orders use `time_in_force: "day"` (API constraint, not GTC)
- If the limit entry price isn't hit during the trading day, the bracket expires silently
- Without resubmission, a valid thesis could go unexecuted all week if the entry level is slightly below the daily trading range
- Resubmission runs the full risk gate pipeline again, so portfolio changes (drawdown, sector exposure, cash) are accounted for
**Trade-offs**:
- Resubmitted brackets also expire at end of day (by design — daily cron handles this)
- No max resubmission count per ticker (thesis expiry at 14 days provides the natural limit)
- Also available as standalone CLI command: `python -m titantrade resubmit`

## Decision 020: Test Suite with Zero AI Token Spend
**Date**: 2026-03-29
**Decision**: All tests mock AI model calls (Claude, Gemini) and broker API calls (Alpaca). Running the test suite never spends tokens or places real orders.
**Reasoning**:
- AI API calls cost money; tests run frequently during development
- Broker API calls could place real orders even on paper accounts, creating noise
- Pure logic tests (indicators, risk gates, parsing) have no external dependencies at all
- Integration tests monkeypatch `_call_claude`, `_call_gemini`, and all Alpaca functions
**Implementation**:
- `conftest.py` provides `fake_config` (dummy API keys), `tmp_state_dir` (temp state files)
- `unittest.mock.patch` used for AI and broker function mocking
- Test data uses deterministic fixtures (sample bars, bullish thesis, positions)
- 114 tests run in < 1 second

## Decision 021: Configurable Refresh Interval in Flutter App
**Date**: 2026-03-29
**Decision**: Allow users to change the polling interval (10s, 15s, 30s, 60s, 120s) from the Settings screen. All 7 stream providers observe the interval dynamically.
**Reasoning**:
- 30-second default is reasonable but some users may want faster updates during market hours or slower polling to reduce disk I/O
- Riverpod's `ref.watch` auto-disposes and recreates streams when the interval changes
- Persisted via SharedPreferences so the choice survives app restarts
**Trade-offs**:
- Very short intervals (10s) increase file system reads, though impact is negligible for JSON files

## Decision 022: Trailing Stop Mechanism
**Date**: 2026-03-30
**Decision**: Ratchet the stop-loss upward once a position gains 5%+ from entry. Trail 3% below the high-water mark.
**Reasoning**:
- Without trailing stops, a stock that runs up 12% can reverse and hit the original 5% stop, turning a winner into a loser
- The trailing stop activates after 5% gain (enough to avoid whipsaw on normal volatility)
- Trail distance of 3% is tight enough to lock in meaningful gains but wide enough to avoid premature exits
- Never trails below entry price once activated (locks in at least breakeven)
- Never trails below the original stop (doesn't widen risk)
**Trade-offs**:
- Requires cancelling and re-placing stop orders on Alpaca (brief moment with no stop during the swap)
- Only checks during execution cycles, not real-time — a flash crash between cycles could miss the trail
- High-water mark tracking adds a new state file (`trailing_stops.json`)

## Decision 023: Thesis Expiry Handling for Held Positions
**Date**: 2026-03-30
**Decision**: Force-close positions that have no active thesis monitoring them (expired or missing from current weekly analysis).
**Reasoning**:
- Previously, when a thesis expired, the system refused new entries but left existing positions as orphans
- Orphaned positions had only their original stop-loss — no sentry monitoring, no thesis-aware exit signals
- This could leave capital tied up indefinitely with no active management
**Trade-offs**:
- Forced exits may sell at a loss even if the stock would have recovered
- Acceptable: a position with no thesis is an unmanaged bet, and capital preservation > hope

## Decision 024: Dynamic Entry Price Adjustment on Resubmission
**Date**: 2026-03-30
**Decision**: When resubmitting expired bracket orders, adjust the entry price based on current market conditions instead of blindly reusing Sunday's level.
**Reasoning**:
- A static limit order that was 1% below the stock on Sunday may be 4% below by Wednesday, meaning the stock has moved away and the thesis entry point is stale
- Adjustment uses support levels from the thesis when available, otherwise a small discount below current price
- Preserves the original risk ratio (stop distance as a percentage)
- Won't chase: skips resubmission if price is >5% above original entry
- Won't enter invalidated thesis: skips if price is below original stop
**Trade-offs**:
- One extra FMP quote call per resubmission (negligible cost)
- May enter at a slightly worse price than Sunday's level — but at least it enters

## Decision 025: Lightweight Intraday Price Checks
**Date**: 2026-03-30
**Decision**: Add pure price-based checks between the 9 AM and 3:30 PM sentry runs. Zero LLM cost — only checks SPY and per-stock adverse moves.
**Reasoning**:
- The 6.5-hour gap between sentry runs left positions unmonitored during peak trading hours
- LLM-based checks every 2 hours would be wasteful — most of the sentry's value comes from the price-based Layer 2 override anyway
- The lightweight checks replicate only Layers 1 and 2 (SPY drop, adverse price move) without Layer 3 (news analysis)
- Run at 11 AM and 1 PM EST via cron — fills the gap without excessive API usage
**Trade-offs**:
- No news analysis during these checks — a breaking headline between 9 AM and 3:30 PM is not caught until the next sentry run
- Acceptable: broker-native stops cover the catastrophic case, and the price-based check catches most institutional selling

## Decision 026: Gap-Down Protection Fallback
**Date**: 2026-03-30
**Decision**: Detect unfilled stop-limit orders after overnight gaps and market-sell the unprotected position immediately.
**Reasoning**:
- Stop-limit orders can fail to fill when a stock gaps below both the stop price and limit price overnight
- This leaves the position completely unprotected — the stop triggered but the limit didn't fill
- Also catches the case where price gaps below the stop itself (stop never triggers, position sits open)
- Runs as part of the daily execution cycle and as a standalone `gapcheck` CLI command
**Trade-offs**:
- Market sell after a gap-down means selling at a potentially much worse price than the intended stop
- But the alternative is holding an unprotected position that could fall further

## Decision 027: Dual Alpaca Credentials with App-Toggled Trading Mode
**Date**: 2026-03-30
**Decision**: Store separate paper and live Alpaca credentials in `.env`. Trading mode is toggled via the Flutter app (or API), not via environment variables.
**Reasoning**:
- Users need both paper and live accounts configured simultaneously for easy switching
- Previously, switching required editing `.env` and restarting — error-prone and slow
- The API endpoint (`PUT /api/settings/mode`) persists the mode to `watchlist.json`
- `load_config()` selects the correct key pair and Alpaca endpoint based on mode
- Live keys are optional — system works paper-only if they're not set
- Legacy `ALPACA_KEY`/`ALPACA_SECRET` env vars are accepted as paper-key fallback
**Safety**:
- API refuses to enable live mode if `ALPACA_LIVE_KEY`/`ALPACA_LIVE_SECRET` are missing
- Flutter app shows a red confirmation dialog before enabling live trading
- Default state is always paper (toggle off)
**Trade-offs**:
- Four env vars instead of two for Alpaca (small complexity increase)
- Mode change requires the next CLI command to re-read config (not hot-reloaded mid-run)
- Acceptable: CLI commands are short-lived processes that load config fresh each time

## Decision 028: Built-in Scheduler (APScheduler in API Process)
**Date**: 2026-03-30
**Decision**: Run all trading cron jobs inside the always-on API container using APScheduler, instead of requiring host-level cron.
**Reasoning**:
- Host cron required manual setup on each server, error-prone, hard to monitor
- APScheduler 3.x `BackgroundScheduler` runs in the same process as FastAPI
- Jobs defined in `data/schedule.json` — editable, version-controlled
- API endpoints (`GET /api/scheduler`, `POST /api/scheduler/{id}/trigger`) let the Flutter app monitor and trigger jobs
- `coalesce=True` + `max_instances=1` + `misfire_grace_time=300` handle restarts gracefully
**Schedule**:
- Sunday 20:00 UTC: full pipeline (fetch → analyze → sentry → execute)
- Weekdays 13:35 UTC: gap-down check
- Weekdays 14:15 UTC: morning sentry + execute
- Weekdays 16:00, 18:00 UTC: price checks
- Weekdays 20:30 UTC: pre-close sentry + execute
**Trade-offs**:
- Scheduler state is in-memory (job history lost on restart) — acceptable for v1
- APScheduler 3.x is thread-based, not async — fine since trading jobs are I/O-bound and short-lived
- No market holiday awareness yet — jobs run but complete quickly with no side effects on closed days

## Decision 020: Discord Webhook Notifications
**Date**: 2026-03-30
**Decision**: Add Discord webhook notifications for job completion/failure and daily portfolio summaries.
**Reasoning**:
- Without notifications, job failures go unnoticed until the user manually checks the Flutter app
- Discord webhooks are free, simple (single HTTP POST), and push to the user's phone
- Two notification types: per-job alerts (green/red embeds) and a daily portfolio digest
**Implementation**:
- New `notifier.py` module using `httpx` (already a dependency) to POST Discord embeds
- Hooked into `scheduler.py:_execute_job()` so every job gets automatic notifications
- `daily_summary` registered as a new scheduled command (weekdays 21:00 UTC)
- `DISCORD_WEBHOOK_URL` env var is optional — if unset, all notifications are no-ops
- Notification failures are logged but never crash the underlying job
**Trade-offs**:
- Discord-specific (not a generic notification system) — simple and sufficient for v1
- Daily summary reads state files which may be stale if the last sentry failed
- No rate limiting on webhook calls — acceptable since jobs run at most ~8 times/day

## Decision 046: Strategy & Operational Hardening (10 fixes)
**Date**: 2026-05-12
**Decision**: A coordinated set of 10 fixes targeting the underlying strategic and operational issues exposed by 2-3 months of production data, where the bot underperformed SPY by ~5 percentage points cumulatively.
**Background**: The bot was technically sound (all the prior bracket / qty / market-hours bugs were addressed in ADRs 042-045) but **strategically losing**: re-entering after every ABORT, blocked by every minor macro event, ignoring Pass-2's confidence refinements, chasing prices it would never catch. Production logs showed clear "sell low, buy higher" cycles on LLY, DASH, FCX, DECK.

### Fix 1 — Re-entry cooldown after ABORT (`executor.py`)
- New `state/abort_cooldown.json` records every ABORT event with timestamp.
- `_handle_abort()` and `price_check`'s ABORT path call `_record_abort_cooldown(ticker, reason)`.
- `_is_in_cooldown(ticker)` returns True until `REENTRY_COOLDOWN_HOURS = 72` have passed.
- `_handle_bullish_entry()` and `resubmit_expired_brackets()` check cooldown before placing new orders.
- Effect: production saw LLY round-trip 3× in one week; this stops the cycle.

### Fix 2 — Narrow macro blackout to high-impact events (`risk_manager.py`)
- New `HIGH_IMPACT_MACRO_KEYWORDS` whitelist (FOMC, NFP, CPI, core PCE, GDP growth, etc.).
- `MACRO_BLACKOUT_HOURS` reduced from 24 → 6.
- Indicators like "Atlanta Fed GDPNow", "CB Employment Trends Index", "Retail Sales Ex Autos" no longer trigger the gate.
- Effect: was blocking ~50% of trading windows; now blocks only genuinely market-moving events.

### Fix 3 — `adjusted_confidence` used in `pre_trade_check` (`risk_manager.py`)
- Pass-2 sometimes raises/lowers per-stock confidence based on portfolio context. The executor was ignoring this.
- Now reads `thesis.adjusted_confidence` if present, falling back to `thesis.confidence`.
- Effect: the confidence-scaled sizing (ADR 032) now uses Claude's actual final estimate.

### Fix 4 — Bracket resubmission attempt cap (`executor.py`)
- New `MAX_BRACKET_ATTEMPTS = 5`. `resubmit_expired_brackets()` counts expired entries per ticker (from Alpaca's order history) and skips if the count exceeds the cap.
- Effect: CRWD chased its price for 10+ days in production; now gives up after 5 expirations and waits for the next weekly thesis.

### Fix 5 — Pass 2 target count scales with regime (`weekly_analyst.py`)
- New `_target_pass2_count(regime)` returns 6 / 5 / 4 / 3 / 2 / 1 for strong_bullish / bullish / neutral / bearish / strong_bearish / crisis.
- Prompt's "TOP 3-5 trades" replaced with the dynamic `{target_count}` placeholder.
- Effect: in strong_bullish we now aim for more deployment (6 picks × ~10% each ≈ 60%, leaving cash reserve room); in bearish we pull in.

### Fix 6 — Sentry price-move uses broker `avg_entry_price` (`daily_sentry.py`)
- `_check_price_move()` accepts an optional `position` parameter. When held, references `position.avg_entry_price` instead of the stale `thesis.target_entry_price`.
- `run_daily_sentry()` pre-fetches all positions and threads them in.
- Effect: for a position up 20% from broker entry, a 3% pullback is now correctly evaluated against the real cost basis rather than the unrelated Sunday thesis level.

### Fix 7 — Earnings blackout narrowed 5 → 2 days (`earnings.py`)
- `DEFAULT_BLOCK_DAYS` reduced from 5 to 2.
- Effect: stops blocking entries on stocks 3-4 days out from earnings (where setups can play out normally); still blocks tonight/tomorrow when the binary event is imminent.

### Fix 8 — State-file size cap + archival (`executor.py`)
- `_append_trade` / `_append_near_miss` now call `_archive_overflow()` which rolls oldest entries off to `state/archive/{file}.YYYYMMDD-HHMMSS.json` when the live file exceeds `MAX_LIVE_TRADES = 500` / `MAX_LIVE_NEAR_MISSES = 200`.
- Effect: trade_log.json was approaching MBs after a month of churn; now self-trimming.

### Fix 9 — Stuck-in-cash Discord alert (`notifier.py`, `executor.py`)
- New `notify_stuck_in_cash()` + `_maybe_alert_stuck_in_cash()` tracks consecutive days at ≥70% cash.
- Fires Discord alert after 3 days, suppressed for the rest of that day.
- Effect: operator knows when the bot is over-conservative without polling dashboards.

### Fix 10 — Ticker churn Discord alert (`notifier.py`, `executor.py`)
- New `notify_ticker_churn()` + `_maybe_alert_ticker_churn()` scans the last 7 days of `trade_log.json` for any ticker that's been bought+sold ≥2 times.
- Fires Discord alert once per ticker per day.
- Effect: even with the cooldown (#1) preventing same-day churn, weekly cycles get surfaced.

**Tests**: 24 new tests (342 total passing) covering cooldown lifecycle, high-impact-only blackout, adjusted_confidence wiring, attempt cap, regime-scaled targets, avg_entry_price preference, narrowed earnings, archival, and both new alerts.

**Trade-offs**:
- Re-entry cooldown (72h) means we'll miss the rare case where a stock genuinely flipped from bad-news to good-news within 3 days. Acceptable trade given the documented churn losses.
- Narrowing macro blackout could surface real risk if a "low-impact" event surprises (rare). Whitelist can be expanded if it bites.
- Higher Pass-2 target count in bullish regimes means more concentrated portfolio risk if Claude has an off week. Mitigated by the existing 40% sector cap and 8% drawdown circuit breaker.

## Decision 043: Market-Hours-Aware Order Operations + Order-Status Polling
**Date**: 2026-05-12
**Decision**: The polling approach in ADR 042 (poll `qty_available`) was diagnosed as wrong after another 2 weeks in production. Replaced with: (1) poll the **blocking order's** `status` directly using the order ID Alpaca names in `related_orders`, and (2) skip ADJUST / orphan-close / trailing-stop adjustments entirely when the market is closed.
**Problem** (verified live):
- Live test on 2026-05-12 03:54 ET (market closed) showed a stop-order cancel sat in `pending_cancel` for **10+ minutes** with no progress. `qty_available` remained at 0 the whole time, so our 30-s polling timeout fired every time.
- In production logs over the previous 2 weeks, this caused CRITICAL "no stop-loss order" errors on ANET, URI, EQIX, DECK, LLY, DASH, FCX, HCA, GS, JPM — multiple times each. Positions sat unprotected for hours.
- Root cause: the executor and weekly analyst run on UTC schedules (e.g. 09:00 UTC = 05:00 ET = pre-market). Cancels submitted off-hours get queued at the venue and don't resolve until next market open.
**Fix**:
- New `executor.is_market_open(cfg)` calls Alpaca's `/v2/clock` to check current state; assumes open on transient errors to fail safe.
- New `executor.get_order(order_id, cfg)` retrieves a single order; returns `None` on 404.
- New `executor._wait_for_order_canceled(order_id, cfg, timeout=120s)` polls the order's own `status` until it reaches a terminal state (`canceled`, `cancelled`, `filled`, `rejected`, `expired`, `done_for_day`). This is deterministic — when the order is truly canceled, qty is released.
- `place_native_stop_loss` qty-race handler now extracts `related_orders[0]` from Alpaca's 403 body and polls that specific order until terminal, then retries the stop-limit.
- `execute_trades()` calls `is_market_open()` once at the top and gates the ADJUST, orphan-close, and trailing-stop paths on it. The "no stop found — place one" safety path still fires regardless (rare, safety-critical).
- Live verified: my own test order eventually canceled at 08:00 UTC after 10+ minutes in `pending_cancel`; new `get_order()` and `is_market_open()` work cleanly against live Alpaca paper.
**Trade-offs**:
- During off-hours runs, ADJUSTed stop levels are not applied. The OLD stop remains active on the book, so the position is still protected at its prior level. The new level applies at the next market-hours executor run.
- Worst-case retry time is now 120 s (up from 30 s) when we DO try to wait for a cancel, but in practice we don't try during off-hours so this only fires during market hours where cancels complete in 1-5 s.

## Decision 044: Bracket Math Sanity Check (Bug #2)
**Date**: 2026-05-12
**Decision**: Both `_handle_bullish_entry()` and `resubmit_expired_brackets()` now sanity-check the (entry, stop, take_profit) triple before sending to Alpaca, and skip with a clear log message when the math is invalid.
**Problem**: Production logs showed repeated HTTP 422 errors from Alpaca:
```
Bracket BUY: 83.0 DECK entry=$108.76 stop=$110.29 tp=110.0
take_profit.limit_price must be > stop_loss.stop_price
```
Cause: when a thesis is reviewed with `review_action=ADJUST`, Claude raises the stop above the original entry to lock in profit on a position already in profit. The new bracket would then be `entry=$106.50, stop=$110.29` — invalid for a fresh entry. This wasted broker requests and skipped real opportunities while ADJUSTed tickers had a "phantom" entry trying to fire.
**Fix** (`executor.py`):
- `_handle_bullish_entry`: refuse if `stop_price >= entry_price - 0.01` or `take_profit <= stop_price`; logs the reason and returns `None`.
- `resubmit_expired_brackets`: identical check after `_adjust_entry_price` runs. If invalid, the thesis is interpreted as "for managing existing position, not opening a new one" and skipped.

## Decision 045: News-Confirmed Price ABORT (Bug #3)
**Date**: 2026-05-12
**Decision**: Graduated price-based ABORT severity. A moderate (3-5%) adverse move now only triggers ABORT if Gemini's news analysis also flagged a concern. Catastrophic moves (>=5%) still ABORT regardless.
**Problem**: Production logs showed excessive ABORT churn — DASH, DECK, LLY, FCX each round-tripped multiple times in a single week on small adverse moves. The previous "any 3% adverse move forces ABORT regardless of Gemini" rule was too aggressive in normal volatility, treating noise as breakdown.
**Fix**:
- New constant `PRICE_MOVE_HARD_ABORT_PCT = 5.0` in `daily_sentry.py`.
- `check_stock()` now applies three-tier severity:
  - `>= 5%` adverse → catastrophic, always ABORT (regardless of news)
  - `3-5%` adverse + Gemini flagged conflicting headlines / price_concern / market_concern → confirmed ABORT
  - `3-5%` adverse + Gemini clean → log warning, do NOT override CONTINUE (broker-side stop still protects)
- `price_check.py` (zero-LLM intraday checker): only ABORTs at `>= 5%` since it has no news context; moderate moves are logged and deferred to the next sentry pass.
**Trade-offs**:
- We accept slightly more downside on positions where price moves 3-5% without news. Our broker-side stops at 5-7% below entry catch real breakdowns; the trade-off is fewer noise-driven exits.
- Production observed 4+ aborts per week at the old threshold, most followed by re-entries within 24-48h. The churn cost (slippage + opportunity) was higher than the protection benefit at the 3% threshold.

## Decision 042: Poll qty_available Instead of Fixed-Sleep Retry
**Date**: 2026-04-21
**Decision**: Replace the 2-second blind sleep in `place_native_stop_loss`'s qty-race retry with an explicit poll of Alpaca's `qty_available`, waiting up to 30 seconds for the cancel to settle.
**Problem** (observed in production over 3 days of the previous fix):
- First executor run after a fresh weekly thesis fires ADJUST on 5-6 positions simultaneously.
- Several hit the qty-race retry path. The 2-second sleep was sometimes too short — Alpaca's `pending_cancel` state lasted 5-15 seconds in production despite completing in ~600 ms in isolated tests.
- Result: GS, URI, DECK, LLY, and DASH were all left **without a stop-loss** until the next executor run (~6 hours later). Logs showed `CRITICAL: {ticker} has no stop-loss order — old-stop restore also failed` for each.
- The self-heal on Run 2 was good (stops were placed), but a 6-hour unprotected window is an unacceptable risk if one of those stocks crashes overnight.
**Fix** (`executor.py`):
- New `_wait_for_qty_available(ticker, required_qty, cfg, timeout_seconds=30)` helper that polls `get_position()` every 500 ms until `qty_available >= required_qty`, or the timeout elapses.
- `place_native_stop_loss` qty-race handler now calls this poll before retrying. It gives up only after 30 s of no release — log line: `Qty for {ticker} never released within 30s — giving up on stop placement`.
- On success: `Qty for {ticker} released after {X}s — retrying stop-limit` followed by `Stop-limit for {ticker} succeeded after qty settled ({X}s)`.
- Two constants added: `QTY_SETTLE_TIMEOUT_SECONDS = 30.0`, `QTY_SETTLE_POLL_INTERVAL = 0.5`.
**Verification**:
- Unit tests updated (`TestPlaceNativeStopLoss.test_retries_on_qty_race_after_polling`, `test_qty_race_times_out_if_never_released`).
- Live test on the Alpaca paper account: `cancel_order()` followed immediately by `place_native_stop_loss()` succeeded in ~1.5 s when no race hit, and within the timeout window when a race did hit.
**Trade-offs**:
- Worst case (qty genuinely stuck, e.g. settlement problem at broker) is a 30 s wait per stop placement — up from 2 s previously. Acceptable: the previous behaviour silently gave up and left the position unprotected; we'd rather block for 30 s and log loudly if we ultimately fail.
- On happy-path (no race), there is zero additional latency — we only enter the poll on a 40310000 error.

## Decision 039: Gemini Structured Output + Thinking Disabled
**Date**: 2026-04-18
**Decision**: Switch `_call_gemini` to use Gemini's structured-output mode with a `responseSchema`, and explicitly disable the thinking-token budget on gemini-2.5-flash.
**Reasoning**:
- Gemini 2.5 Flash defaults to `thinking` mode, which consumes 500-2000 hidden tokens before producing any output. On a classification task (CONTINUE vs ABORT), this is pure cost and latency with no benefit.
- Without structured output, Gemini occasionally emits markdown-fenced JSON, prose prefixes ("Here is the result: ..."), or truncates mid-string when the token budget runs out. We had to ship a JSON-repair module to cope.
- With `responseMimeType=application/json` + `responseSchema`, Gemini enforces a valid JSON shape matching our `SENTRY_SCHEMA`. The repair path becomes a belt-and-suspenders fallback rather than a daily necessity.
**Implementation** (`src/titantrade/daily_sentry.py`):
- Added `_SENTRY_SCHEMA` constant matching the sentry signal shape (ticker, signal, conflicting_headlines, price_concern, market_concern, reasoning — all required, with signal enum-constrained to CONTINUE/ABORT).
- `generationConfig` now includes `responseMimeType: "application/json"`, `responseSchema: _SENTRY_SCHEMA`, and `thinkingConfig: {thinkingBudget: 0}`.
- Simplified the prompt's OUTPUT FORMAT section — the schema does the enforcement, so we can drop the brevity instructions that were previously fighting truncation.
**Verification**: live Gemini call on NVDA returned perfectly-valid JSON in 78 candidate tokens (vs hundreds with thinking enabled) in 1.77 s.
**Trade-offs**:
- Schema is strictly typed: `conflicting_headlines` is `array<string>`. If we ever want headline objects (title+snippet), the schema needs to change. For the current use case, strings are sufficient.
- The JSON-repair code path (`_repair_truncated_json` in `ai_parsing.py`) stays as a defensive fallback for the rare case where the schema-constrained response is somehow still malformed.

## Decision 040: Backtest A/B Comparison — Confidence Scaling On vs Off
**Date**: 2026-04-18
**Decision**: Expose the confidence-scaling logic as an opt-in flag in the backtest engine and add an A/B runner for empirical validation.
**Reasoning**: The confidence-proportional position-sizing change (ADR 032) was deployed to the live executor but never backtested. Without a way to compare the two regimes on historical data, we can't tell whether the 0.7×–1.3× curve actually improves risk-adjusted returns or just adds complexity.
**Implementation**:
- `src/titantrade/backtest/simulator.py`: `PortfolioSimulator` now accepts `use_confidence_scaling: bool = False`. When True, `_process_entries` calls `risk_manager.confidence_scaled_risk(self.risk_per_trade, thesis.confidence)` instead of using the flat risk fraction.
- `src/titantrade/backtest/engine.py`: `run_backtest()` accepts a matching flag, and a new `run_ab_comparison()` runs both variants back-to-back and returns a side-by-side metric table (return, alpha, Sharpe, Sortino, drawdown, win rate, profit factor, trade count).
- `src/titantrade/__main__.py`: new CLI command `backtest-ab [dir]` produces a formatted console table and writes the full result JSON to `state/backtest_ab.json`.
- Tests added to `tests/test_backtest.py` verify the flag toggles the config field and that the comparison structure is well-formed.

## Decision 041: Flutter Sentry Health Badge
**Date**: 2026-04-18
**Decision**: Surface the sentry's `failures.fallback_ratio` on the dashboard so the Gemini-degraded state is visible without digging through logs or waiting for Discord alerts.
**Implementation**:
- `titan_trade_app/lib/models/sentry_signal.dart`: new `SentryFailures` class with `fallbackCount`, `checksRun`, `fallbackRatio`, and a convenience `isDegraded` getter (mirrors server-side 30% threshold).
- `SentryBundle.fromJson` now parses an optional `failures` block.
- `titan_trade_app/lib/screens/dashboard_screen.dart`: when `failures.isDegraded`, the sentry card shows an orange warning banner with fallback counts. When healthy, a small green pill shows coverage ("Sentry healthy — 14/15 news-based checks OK").

## Decision 038: Sentry Coverage — Skip Non-Selected Tickers + Failure Observability + ADJUST Safety Net
**Date**: 2026-04-18
**Decision**: A bundle of three small correctness and observability fixes.
**Problem 1 — Ghost ABORTs for closed positions**: After a weekly review marked DXCM as CLOSE (`selected_for_trading=False`) and the orphan-close sold the position, the daily sentry kept calling Gemini for DXCM on every run because the sentry loop only filtered out NEUTRAL theses. Occasional ABORTs would fire, then the executor would log `ABORT for DXCM: no position to close` as harmless noise — but the Gemini tokens and the log spam were both wasted.
**Problem 2 — No observability when Gemini is down**: When Gemini returns 503 for all sentry calls (common during API-side outages), our code silently falls back to CONTINUE for every ticker. The news-based ABORT layer is effectively offline, but there's no alert. The operator has to spot it in log files.
**Problem 3 — ADJUST could strand a position without a stop**: The ADJUST flow `cancel_all_orders_for_ticker` → `place_native_stop_loss` has a failure window where the cancel succeeds but the new stop placement fails (e.g. network blip after the qty-race retry exhausts). The position is then held with NO stop-loss.
**Fix 1 (`daily_sentry.py`)**: skip the ticker entirely if `selected_for_trading=False`. Append a synthetic CONTINUE signal with `reasoning="Not selected for trading — sentry check skipped"` so state files remain consistent. No Gemini call, no ghost ABORT.
**Fix 2 (`daily_sentry.py` + `notifier.py`)**: at the end of each sentry run, count signals whose `reasoning` contains `"Sentry check failed"` (the exception-path fallback marker). Record `{fallback_count, checks_run, fallback_ratio}` in the state file and, when the ratio exceeds 30%, log a WARNING and fire a Discord alert via new `notify_sentry_degraded()` helper.
**Fix 3 (`executor.py` ADJUST flow)**: before cancelling the old stop, capture its `stop_price`. If the new-stop placement raises, re-create the old stop at its original price. Mirrors the pattern already in use by `manage_trailing_stop`.
**Fix 4 (`executor.py` orphan close)**: on failure, log the Alpaca error code + message (via the new `HTTPError` properties) and explicitly say "will retry on next run" so operators don't assume the position is stuck permanently.
**Tests**: 3 new sentry tests (`TestNonSelectedSkip`, `TestSentryObservability`), 2 new executor tests (`TestAdjustStopSafety`), all with mocked Gemini/Alpaca.
**Trade-offs**:
- The 30% fallback-alert threshold is a judgement call. Too low produces noisy alerts during brief Gemini hiccups; too high hides real outages. 30% balances these — the threshold is a constant and can be tuned later.
- The ADJUST restore doesn't cover the case where the original stop price is itself invalid. If we somehow had no prior stop, restore is a no-op (logged as CRITICAL).

## Decision 037: Alpaca 403 on Stop Placement — Idempotency + Qty-Race Retry + Error-Body Capture
**Date**: 2026-04-18
**Decision**: Three-layer fix for the recurring `403 Forbidden` Alpaca errors seen when placing/replacing stop-loss orders.
**Problem** (diagnosed by reproducing the error with the live Alpaca paper API):
1. The `ADJUST` review flow in `executor.py` was unconditionally cancelling and re-placing stops on every executor run (twice daily), even when the existing stop was already at the target price. Alpaca's historic order log showed 28 back-to-back "cancel→re-place at the same $64.50" cycles on FCX alone over 14 days — every one of which was a wasted request and a chance to hit a qty race.
2. Between cancel and re-place, Alpaca's `qty_available` can lag ~100-1000 ms. When we POST the new stop in that window, Alpaca returns 403 with `code:40310000` and the message `"insufficient qty available for order (requested: 121, available: 0)"`.
3. `retry.py` discarded the response body via `raise_for_status()`, so our logs just said `403 Forbidden` with no diagnostic detail.
4. The stop-limit → plain-stop fallback in `place_native_stop_loss` sent the same qty for both order types. Since the qty constraint is position-level (not order-type-level), the fallback was guaranteed to fail whenever the stop-limit failed with 40310000.
**Fix — Layer 1 (`executor.py:1269`)**: idempotency check before cancel+replace. If an existing stop for the ticker is already at (within $0.01 of) the target `stop_loss_price`, skip the entire cancel+replace sequence.
**Fix — Layer 2 (`retry.py`)**: new `HTTPError` exception class that carries the status code, raw body, parsed JSON, and convenience properties `error_code` / `error_message`. The 4xx branch now raises this instead of `httpx.HTTPStatusError`, preserving diagnostic info like Alpaca's error code.
**Fix — Layer 3 (`executor.py: place_native_stop_loss`)**: when `HTTPError.error_code == 40310000` (Alpaca insufficient qty), wait 2 s and retry the stop-limit *once*. Do not fall back to a plain stop in this case — both order types share the same qty constraint. For any other 4xx, the plain-stop fallback is retained (paper accounts occasionally reject stop-limit for specific asset types).
**Tests**: 4 new executor tests (`TestPlaceNativeStopLoss`) + 3 new retry tests (`TestHTTPErrorBodyCapture`) covering qty-race retry, body capture, and the unchanged plain-stop fallback for other errors.
**Verification**: reproduced the 403 with live API call to `POST /v2/orders` on FCX with 121 shares already held by an existing stop, confirmed Alpaca's response body matches the error-code handling, and confirmed `DELETE /v2/orders/{id}` typically releases `qty_available` within ~600 ms.
**Trade-offs**:
- Layer 1 reduces Alpaca request volume by ~28× per held position per 2-week window.
- Layer 3 adds up to one 2-second delay per stop placement in the race case. Acceptable — better than a failed placement leaving the position unprotected.
- `HTTPError` is a new exception type. Existing callers that catch `Exception` still work (it's still an `Exception`), but any code that specifically caught `httpx.HTTPStatusError` would break. None existed in the codebase.

## Decision 036: Review-Mode Thesis Validation
**Date**: 2026-04-18
**Decision**: `validate_thesis()` now distinguishes "new candidate" from "review of held position" via an `is_review` flag.
**Problem**: The validator blindly downgraded any BULLISH thesis without a `target_entry_price` to NEUTRAL. When Claude *reviewed* a held position, it correctly omitted the entry price (we already own the shares — there's no pending buy to price), but the validator interpreted that as "no way to buy" and downgraded the thesis to NEUTRAL. This produced the recurring log line `BULLISH thesis for JPM/LLY/FCX/EQIX has no entry price - downgrading to NEUTRAL` on every weekly analysis, and caused held positions to lose their BULLISH status in state, confusing downstream selection logic.
**Fix** (`src/titantrade/ai_parsing.py:208`):
- Added optional `is_review: bool = False` parameter to `validate_thesis()`
- When `is_review=True`: skip the "no entry price → NEUTRAL" downgrade, and skip the auto-fill of stop-loss from entry price (the caller carries the prior stop forward)
- When `is_review=False` (default): legacy behaviour preserved for new candidates
- Updated both `validate_thesis()` call sites inside `review_position()` in `weekly_analyst.py` to pass `is_review=True`
- Pass-1 new-candidate path in `analyze_stock()` unchanged (still needs entry price to know where to buy)
- Added 5 regression tests (`TestValidateThesisReviewMode`) locking in the new behaviour
**Trade-offs**:
- New flag is opt-in with a safe default. All existing callers that don't pass it continue to get the old behaviour, so this change is fully backward compatible.

## Decision 034: Hardened HTTP Retry Policy
**Date**: 2026-04-18
**Decision**: Rewrite `retry.py` with longer backoff, jitter, 429 handling, and per-call timeout tuning.
**Reasoning**:
- Gemini Flash frequently returns 503 (overloaded). Previous retry gave up after ~6 s of total wait — far too short for Google's load-shedding windows.
- All 15 sentry tickers retrying in lockstep created a thundering-herd effect that amplified Gemini outages.
- 429 rate-limit responses were treated as immediate failures instead of retry-with-backoff, so SEC-API rate limits (now obsolete) and any future rate-limited endpoint would fail fast.
- Over a 14-day operation window, **up to 11 of 15 sentry checks silently failed** in a single run, degrading the news-analysis safety layer without operator awareness.
**Implementation** (`src/titantrade/retry.py`):
- `MAX_RETRIES` raised 3 → 5
- Per-attempt delay capped at `MAX_DELAY = 30 s` (was unbounded 2^attempt)
- Full-jitter exponential backoff: `delay = uniform(0, min(BASE_DELAY * 2^(attempt-1), MAX_DELAY))`
- `DEFAULT_TIMEOUT` raised 30 s → 60 s (Gemini 2.5-flash can take 30–45 s under load)
- 429 responses retried and honour the `Retry-After` header
- `RETRYABLE_STATUS = {429, 500, 502, 503, 504, 529}` (529 for Anthropic overload)
- `max_retries` now a per-call parameter, so latency-sensitive Alpaca paths can fail faster if needed
- New unit tests in `tests/test_retry.py` (17 tests) covering jitter bounds, Retry-After parsing, 4xx fail-fast, 5xx retry-then-succeed, and network-error retry
**Trade-offs**:
- Worst-case retry time rises from ~6 s to ~75 s. Acceptable for AI/data endpoints but could delay Alpaca order placement if the broker itself returns 5xx. Callers that need fail-fast should pass `max_retries=1`.
- More API usage during backoff windows (5 attempts vs 3).

## Decision 035: Replace Paid SEC-API.io with Free SEC EDGAR
**Date**: 2026-04-18
**Decision**: Switch SEC filings and Form 4 insider data from api.sec-api.io to the free SEC EDGAR public API.
**Reasoning**:
- SEC-API.io credits were exhausted and the service is expensive.
- Independent evaluation (see ADR context) rated SEC filings as ~20/100 criticality — 1 of ~11 data inputs to Claude's weekly analysis.
- SEC EDGAR provides the same underlying data (8-K, 10-Q, 10-K, Form 4 metadata) for free, with a 10 req/sec global rate limit that our sequential workflow stays well under.
**Implementation** (`src/titantrade/sec_edgar.py`):
- New module with `get_cik()`, `fetch_recent_filings()`, `fetch_insider_filings()`
- Uses `https://www.sec.gov/files/company_tickers.json` for ticker→CIK lookup (full ~10k-entry map cached at `state/cik_cache.json`, fetched at most once per process)
- Uses `https://data.sec.gov/submissions/CIK{cik}.json` for each company's filings
- SEC requires a `User-Agent` with a contact email — configurable via `SEC_USER_AGENT` env var, defaults to `TitanTrade/1.0 (contact@titantrade.local)`
- `data_fetcher.fetch_sec_filings()` and `fetch_insider_trades()` keep their signatures; the `cfg` argument is now a no-op placeholder for backward compatibility
- `SECAPIConfig` marked deprecated in `config.py` (retained only for test fixtures)
- New unit tests in `tests/test_sec_edgar.py` (19 tests) covering CIK caching, URL construction, form-type filtering, limit enforcement, unknown-ticker handling, and error paths
**Trade-offs**:
- Form 4 reporting-owner (insider) names are no longer returned — they require parsing each Form 4 XML filing (one extra request each). For weekly analysis, the *timing and count* of insider activity is the primary signal, so we leave `insider_name` blank.
- Filing descriptions are simpler (EDGAR returns `primaryDocDescription` like "8-K" or "FORM 4" rather than detailed summaries). Claude can still see form type, filing date, and a direct URL.

## Decision 032: Confidence-Proportional Position Sizing
**Date**: 2026-04-05
**Decision**: Scale position size proportionally to confidence using a linear multiplier (0.7x at 0.70 confidence to 1.3x at 1.00 confidence).
**Reasoning**:
- Previously confidence was binary: blocked trades below 0.70, did nothing above
- A 0.71 and 0.95 confidence trade both got identical 10% position sizing
- Information from the AI's conviction assessment was wasted
- Higher confidence = more capital deployed; lower confidence = smaller bet
- Baseline (10% risk) is at 0.85 confidence; 0.70 gets 7%, 1.00 gets 13%
**Implementation**:
- `confidence_scaled_risk()` in `risk_manager.py`: linear interpolation
- Formula: `multiplier = 0.7 + (confidence - 0.70) * 2.0`
- Applied inside `volatility_adjusted_shares()` when confidence is provided
- Backward compatible: `confidence=None` gives identical pre-existing behavior
**Trade-offs**:
- Higher exposure on high-confidence trades increases tail risk if confidence calibration is poor
- Mitigated by existing performance feedback loop that calibrates confidence over time
- ATR cap still limits any single position to ~13% max (even at confidence=1.0)

## Decision 033: Hedge Instrument Regime Awareness in Weekly Review
**Date**: 2026-04-05
**Decision**: Add market regime context and explicit warnings to the weekly review prompt for inverse ETF positions.
**Reasoning**:
- SDS (2x inverse S&P 500) was held through a +3.4% market rally, losing 7.81%
- The review prompt never told Claude about the current market regime
- Claude only saw individual position P&L and technicals, not the strategic contradiction
- Without regime context, Claude defaulted to CONTINUE since the thesis was technically intact
**Implementation**:
- `REVIEW_USER_TEMPLATE` now includes `{current_regime}` and `{regime_warning}`
- For hedge instruments in non-bearish regimes, a warning is injected:
  "WARNING: {ticker} is an INVERSE ETF... current regime is '{regime}'... Consider CLOSING."
- New instruction: "REGIME CHECK: If a regime warning is present, weigh it heavily"
**Trade-offs**:
- May cause premature exits during temporary rallies within a broader bearish trend
- Acceptable because inverse ETFs are intended as short-term hedges, not long-term holds

## Decision 029: Gemini Truncated JSON Repair
**Date**: 2026-04-04
**Decision**: Add a JSON repair layer in `ai_parsing.py` to salvage truncated Gemini responses.
**Reasoning**:
- Gemini Flash frequently hits `maxOutputTokens` and cuts off mid-JSON string (especially in the `reasoning` field)
- This was causing ~8 parse failures per week, losing sentry signal quality
- The repair closes unterminated strings and brackets to recover the parseable fields
- Also added prompt instruction to keep reasoning under 3 sentences to reduce truncation frequency
**Trade-offs**:
- Repaired JSON may have a truncated `reasoning` field — acceptable since the `signal` field is the actionable output

## Decision 030: Live Portfolio API Endpoint
**Date**: 2026-04-04
**Decision**: The `/api/portfolio` endpoint now fetches live data from Alpaca instead of reading a static JSON file.
**Reasoning**:
- The static `portfolio.json` was never updated, causing persistent 404 errors
- The Flutter app needs real-time portfolio data (positions, P&L, buying power)
- Falls back to static file if Alpaca API is unreachable

## Decision 031: Sector Cache Initialization in Executor
**Date**: 2026-04-04
**Decision**: Call `load_stock_sectors()` at the start of `execute_trades()` to populate the in-memory sector cache.
**Reasoning**:
- The sector cache was only populated during `build_data_bundle()` (the fetch command)
- The executor runs as a separate process/invocation and had an empty cache
- All tickers mapped to "Unknown" sector, causing the 40% sector limit gate to block all entries in that phantom sector
- Now the executor loads the persistent `sector_cache.json` (or fetches from FMP if missing) before risk gate checks

## Decision 021: Fractional Shares for Small Accounts
**Date**: 2026-03-30
**Decision**: Support fractional share trading for accounts too small for whole shares.
**Reasoning**:
- Starting with ~$500, the 10% position sizing produces ~$50 per trade
- Most stocks above $50/share would get 0 shares after `int()` truncation, making them untradeable
- Alpaca supports fractional shares natively via the same API (`qty: "0.25"`)
**Implementation**:
- Position sizing uses `float` instead of `int` — snaps to whole shares when >= 1, keeps fractional when < 1
- Order routing: whole shares use bracket orders (atomic entry + stop + TP), fractional uses day-limit buys
- All position quantity reading changed from `int(float(...))` to `float(...)` for fractional holdings
- Minimum $1.00 notional check added (Alpaca requirement for fractional orders)
**Trade-offs**:
- Fractional positions have no broker-native stop-loss (Alpaca doesn't support fractional bracket/stop orders)
- The sentry's price-based ABORT (3% adverse) and intraday price checks act as the safety net instead
- Max loss on a fractional position is small ($50 at 10% sizing on a $500 account), so the risk is acceptable
- As the account grows and positions become whole shares, bracket orders automatically resume

## Decision 032: Strategic Redesign — "Always Deployed, Asymmetric Exposure"
**Date**: 2026-05-21
**Decision**: Replace the prior "dip-buy AI picks + 20% cash floor" design with a five-pillar always-deployed strategy.
**Reasoning**:
Production logs over a 3-week rising-market window showed the portfolio sitting at 83% cash for 5+ consecutive days while only realizing +1.75% (vs SPY participation potential). Root causes identified:
- `MIN_CONFIDENCE=0.70` rejected the modal 0.65 thesis confidence range
- `MIN_CASH_RESERVE_PCT=20%` reserved capital that never deployed anyway because of the downstream gates
- Day-TIF bracket entries at thesis prices below current never filled in rising markets (58 expired brackets accumulated)
- News-only sentry ABORT crystallized losses on whipsaw round-trips (GS case)
- Weekly review's discretionary CLOSE override pre-empted programmatic stops (HCA closed at -1.6% with stop 4% away)
- Fixed 3% trailing stop crystallized large winners on intraday noise

**Implementation** (all changes):
1. **Confidence sizing curve** (`risk_manager.confidence_scaled_risk`):
   - Floor: 0.55 (was 0.70). Below the floor still skips.
   - Piecewise multiplier: 0.55→0.40x, 0.70→1.00x, 0.80→1.50x, 0.90→2.00x, 0.95+→2.50x
   - High-conviction theses can take up to 25% of portfolio (was capped at ~10%)
2. **Cash floor** lowered: 20% → 5% (`MIN_CASH_RESERVE_PCT`)
3. **Sector concentration** raised: 40% → 50% (`MAX_SECTOR_EXPOSURE_PCT`)
4. **ATR-based trailing stops** (`manage_trailing_stop`):
   - Trail 2.5× ATR below HWM (was 3% fixed)
   - Fallback to 5% (was 3%) when ATR unavailable
5. **Tranched profit-taking**:
   - At 50% of upside-to-TP, sell 1/3 of position
   - Raise stop to breakeven on the remainder
   - Tracked in `trailing_stops.json` via `tp1_taken` flag
6. **News-only sentry ABORT downgrade**:
   - Gemini ABORT without adverse price move now downgrades to CONTINUE
   - Programmatic stop remains the only kill switch for losers
7. **Weekly CLOSE on losers downgraded**:
   - `close_orphaned_positions` skips CLOSE actions when position is in loss
   - ADJUST path can still tighten the stop; analyst can't preempt downside
8. **Trend-aware entries** (`compute_trend_regime`, `_choose_entry_price`):
   - strong_up regime or confidence ≥ 0.80: near-market entry (current × 1.003)
   - up regime: small breakout buffer (current × 1.001)
   - range: limit at min(thesis_target, current)
   - down regime: skip entry entirely
9. **Always-deployed core position** (`manage_core_position`):
   - 30% of portfolio in SPY by default
   - Auto-swap to SH (inverse SPY) when `market_stress` fires
   - Rebalanced market-on-open when drift exceeds ±5%pts
   - Bypasses the AI thesis path and risk gates
10. Raised price-chase cap from 5 → 20 expirations (less restrictive with trend-aware entries)

**Trade-offs**:
- Much more capital deployment = more market exposure during sell-offs (intentional — the 8% drawdown circuit breaker remains as the systemic safety)
- Bigger positions on high-conviction (up to 25%) increase single-name risk — mitigated by sector limit and the trailing stop
- Stricter sentry ABORT means we won't exit on a single news interpretation — accepts more downside per name in exchange for less whipsaw churn
- Core SPY position will dampen alpha vs pure stock-picking but guarantees market participation
**Validation**:
- 355 tests passing (was 317 before redesign), with mutation-tested coverage on critical paths
- Backtest deferred to user — historical data needs to be downloaded first (`uv run python -m titantrade download-history && uv run python -m titantrade backtest`)
- Paper-trade deployment expected before any live-money cutover

## Decision 033: Strategic Phase 2 — Pyramiding + VIX-scaling + Smarter Re-entry
**Date**: 2026-05-21
**Decision**: Layer six additional changes on top of Decision 032 to convert the deployed-capital base into an opportunity-capturing system.
**Reasoning**:
After Decision 032 fixed cash drag and over-conservative gates, the next-order issue was that we still wouldn't *ride* winners or *re-enter* after shakeouts. Per the user's "ride the wave" mandate, these six additions push the strategy from defensive-corrected to actively opportunistic.

**Implementation**:
1. **Pyramid into winners** (`maybe_pyramid_position`):
   - At +5% gain with trailing stop active, add 50% of original notional via market-buy
   - Cap at `pyramid_max_total_pct` (30%) of portfolio for any single ticker
   - Fires exactly once per position (tracked in `trailing_stops.json["pyramid_added"]`)
   - Requires: sentry CONTINUE, thesis still BULLISH, whole-share position
2. **VIX-aware risk scaling** (`risk_manager.vix_scaled_risk`):
   - VIX < 15: 1.2x sizing (calm market, lean in)
   - VIX 15-25: 1.0x (normal, linear interp from 1.2)
   - VIX 25-35: 0.85-0.7x (elevated, trim)
   - VIX 35+: 0.4x floor (defensive)
   - Applies AFTER confidence scaling, before MAX_POSITION_PCT cap
3. **RSI exhaustion check** in `compute_trend_regime`:
   - Even in strong-uptrend with golden cross, RSI > 75 downgrades to "range"
   - Prevents buying parabolic extensions
4. **Smarter re-entry after ABORT** (`cooldown_override_allowed`):
   - 72h hard cooldown bypassed when ALL of: ≥24h elapsed, thesis still BULLISH/selected, sentry CONTINUE, price ≥ 1% above stop
   - Stops the production lockout where one whipsaw = 72h locked out of recovery
5. **Resubmit-bracket alignment**: `resubmit_expired_brackets` now uses `compute_trend_regime` + `_choose_entry_price` (same as `_handle_bullish_entry`)
   - Old `_adjust_entry_price` is no longer the resubmit code path — it capped at current*0.995 and silently skipped >+5% above entry, which is why FCX never re-filled
6. **Total-overlay concentration cap** (`MAX_TOTAL_OVERLAY_PCT = 70%`):
   - New `overlay_cap` gate added between cash_reserve and position_size
   - Combined AI-pick positions can't exceed 70% of portfolio (protects the 30% SPY core allocation)
   - Pre-trade check now evaluates 9 gates (was 8)

**Trade-offs**:
- Pyramiding inherently concentrates capital in winners — by design. Risk is mitigated by requiring the trailing stop to already be active (downside bounded at breakeven on the original lot).
- VIX scaling means we'll size down meaningfully in stress periods. In a melt-up that briefly spikes VIX (e.g. >25 on a single bad day), we'll under-size; that's a deliberate trade for the systemic protection.
- Smarter re-entry can fire mid-cooldown if conditions align — slightly faster churn possible if Gemini and price oscillate. Mitigated by the 24h minimum and price > 1.01 × stop requirement.
- Overlay cap is the safety net that makes all the other risk-taking changes safe.
**Validation**:
- 382 tests passing (was 355 after Decision 032). Six pyramid tests, eight VIX-scaling tests, six cooldown-override tests, five overlay-cap tests, plus RSI/regime updates.
- Mutation-tested the pyramid ABORT-gate to confirm regression coverage.
- Backtest still deferred — same OHLCV-download prerequisite as Decision 032.

## Decision 034: Realign AI Prompts and Data Flows With New Strategy
**Date**: 2026-05-21
**Decision**: The AI prompts (Pass 1, Pass 2, weekly review, daily sentry) and supporting data flows were updated to match Decisions 032-033. The prior prompts encoded the OLD policies — "lean toward ABORT", "confidence > 0.70 preferred", "CLOSE on invalidated thesis" — and were silently fighting the new executor logic.

**Reasoning**:
After Decisions 032-033 rewired the executor's risk gates, sizing, entry style, and sentry-ABORT downgrade, the AI prompts still told the models to operate as if the old strategy were in effect. Concretely:
- Sentry prompt said "lean toward ABORT" — but the executor now downgrades news-only ABORTs to CONTINUE. Gemini was burning calls producing signals that the executor then discarded.
- Pass 1 confidence guidance was vague ("only use >0.85 when exceptional") — but confidence now directly drives sizing on a steep curve (0.4x at 0.55 → 2.5x at 0.95). Uncalibrated confidence is the single biggest leak in this design.
- Pass 2 said "confidence > 0.70 preferred" — but the new floor is 0.55, and we want sizing (not selection) to do the work.
- Weekly review prompt allowed CLOSE on losers — but the executor now downgrades that to "let the stop work", so the analyst was wasting tokens issuing CLOSE actions that get rewritten.
- News dedup was exact-title only — missing the wire syndication that inflated apparent news volume 5-10x.

**Implementation**:
1. **Sentry prompt rewrite** (`SENTRY_PROMPT_TEMPLATE` in daily_sentry.py):
   - Explicitly tells Gemini that news-only ABORT will be downgraded by the executor.
   - Lists the SPECIFIC conditions that warrant ABORT (literal breach-condition match, catastrophic price, named event causing institutional re-rating).
   - Lists what NOT to ABORT on (generic market, vague macro, sector rotation narratives, 3-5% noise without confirming news).
   - Decision asymmetry stated: "false ABORTs cost money, false CONTINUEs are caught by the stop".
2. **Position context in sentry** (`_format_position_context`, `check_stock(position=...)`):
   - Sentry now sees entry/current/unrealized-P&L/market value when called for a held position.
   - Lets Gemini reason about real trade economics, not abstract news.
3. **Pass 1 confidence calibration**:
   - Replaced vague guidance with 5 explicit bands (0.55-0.64 probe, 0.65-0.74 standard, 0.75-0.84 high, 0.85-0.94 exceptional, 0.95+ reserved) with anchor criteria for each.
   - Each band ties to the sizing multiplier the executor will apply.
   - Bad breach conditions ("negative news flow", "sector weakness") now explicitly called out; analyst must name a falsifiable event.
4. **Pass 1 stop guidance**:
   - "Use the LARGER of: stop_loss_pct% below entry, or below meaningful technical." 
   - References the new 2.5x ATR trailing — stops <1.5x ATR will be noise-stopped.
5. **Pass 2 deployment context**:
   - Tells the manager about the 70% overlay cap and 25% per-position max.
   - "Quality strictly dominates quantity" — discourages padding to hit target_count.
6. **Weekly review prompt**:
   - States the "stops are sacred" policy: CLOSE on a loser will be downgraded to ADJUST.
   - Adds an explicit ADD action for pyramid recommendations (though the auto-pyramid handles most cases).
7. **News deduplication** (`_news_dedup_key` in data_fetcher.py):
   - Aggressive normalization (lowercase, alphanumeric-only, first 60 chars) catches wire-syndicated variants while preserving genuinely-different stories.
   - Logs duplicate count when present.
8. **Data freshness warnings** (executor.py):
   - Warns when data_bundle.json is >24h old (info), errors at >48h (likely materially stale).

**Trade-offs**:
- Calibrated confidence may produce fewer 0.85+ ratings than the prior loose-anchored version. That's by design — those slots are now 2.0-2.5x sized.
- More aggressive news dedup risks over-collapsing if multiple distinct stories share a generic lead. Mitigated by the 60-char prefix (long enough to diverge on real differences).
- Position-context in sentry adds a few tokens to every Gemini call. Cost increase is trivial vs. the value of grounded decisions.
**Validation**:
- 389 tests passing (was 382 after Decision 033).
- New tests verify position-context rendering in the sentry prompt and news-dedup-key normalization edge cases.
- Existing news-only-ABORT-downgrade test continues to enforce the policy at the executor layer (defense-in-depth: prompt asks Gemini not to do it, executor catches it if Gemini does anyway).

## Decision 035: Execution-Safety Hardening — Stop Coverage, Pyramid, Cash Reserve, Data Freshness
**Date**: 2026-06-07
**Decision**: Fix six execution bugs surfaced by a 14-day paper-trading log review, three of which could leave a real-money position unprotected or over-leveraged. These are go-live blockers; the strategy logic was sound but the order-management plumbing was not.

**Context** — the production log showed:
- `CRITICAL: FCX stop restore failed` — after a TP1 partial sell, the breakeven-stop placement raced the sell's settlement, requested a stop for the stale (pre-sell) qty, 403'd, and the restore path *also* used the stale qty and failed → position left with **no stop**. The gap-down failsafe then also failed (`insufficient qty available: 0`) because it market-sold against a just-cancelled stop still holding the shares.
- `Pyramid market-buy failed … potential wash trade detected` on **every** pyramid attempt — a market buy placed while the protective sell stop rested on the book is rejected by Alpaca.
- `Bracket resubmission failed … fractional orders must be simple orders` — the cash-reserve reduction sized URI to 0.19 shares and posted it as a bracket (HTTP 422).
- `Cash: $-6,379.77`, buying power 2-3× portfolio — simultaneously-pending bracket entries each passed the 5% cash-reserve gate against the same settled cash, then collectively filled into margin.
- `Data bundle is 120h old` — the bundle was only refreshed by the weekly Sunday pipeline; trend-regime/ATR decisions ran on 5-day-old data by Friday.
- HCA was selected BULLISH by the analyst every week but blocked every cycle by the downtrend trend-gate — a silent, repeating analyst↔executor conflict.

**Implementation** (all in `executor.py` unless noted):
1. **TP1 stop-replace race** (`manage_trailing_stop`): poll the partial sell to a terminal (`filled`) state before re-reading the position to size the breakeven stop, instead of a blind `sleep(2)`. The restore-on-failure handler now re-reads the *live* position qty rather than the stale pre-sell qty.
2. **Bare-position backstop** (`place_native_stop_loss`): on a persistent `insufficient qty` (40310000) — whether or not Alpaca names a blocking order to poll — clamp the stop to the broker-reported `available` qty and retry. A stop on 103 of 121 shares beats no stop. This is the last-resort guarantee a position is never left bare.
3. **Pyramid via marketable limit buy** (`maybe_pyramid_position`): add with a LIMIT buy (`current × 1.003`, day TIF) — accepted alongside the resting stop — instead of a market buy (wash-trade reject). After the add fills, cancel+replace the protective stop to cover the full enlarged position; if the add doesn't fill in the poll window, cancel it so no surprise unprotected fill.
4. **Gap-down protection** (`check_gap_down_protection`): wait for the cancelled stop to reach a terminal state (releasing the held qty) before the protective market sell, so it no longer 403s exactly when it's needed.
5. **Fractional bracket guard**: `place_bracket_order` floors fractional qty and raises below 1 whole share; `resubmit_expired_brackets` floors `check["shares"]` and skips cleanly when there isn't room for one whole share (no more 422).
6. **Committed-cash reserve** (`risk_manager.max_investable_amount` / `pre_trade_check` + `executor.open_buy_commitment`): the cash-reserve gate now nets out the notional of already-pending buy orders, so N simultaneous brackets can't each clear the reserve against the same cash and collectively breach it into margin.
7. **Daily data refresh** (`scheduler.py` + `data/schedule.json`): added a `fetch` command and a weekday `weekday_fetch` job (13:00 UTC, before the morning sentry/execute) so the data bundle is refreshed daily, not just weekly.
8. **Analyst↔executor conflict surfaced** (`_handle_bullish_entry`): a BULLISH+selected ticker blocked by the downtrend regime is now recorded as a near-miss (synthetic `trend_regime` gate) so the disagreement is visible on the dashboard rather than silently burning a selection slot each cycle.

**Trade-offs**:
- The committed-cash reserve will, by design, decline some entries that the old gate would have allowed — that's the point (it's what prevented negative cash). It can slightly reduce deployment in cash-tight windows.
- Pyramiding now depends on a marketable limit filling within the poll window; if it doesn't, the add is cancelled and retried next cycle rather than forced. Acceptable — pyramids are opportunistic.
- The daily fetch adds one FMP data pull per weekday (no LLM/token cost).
- The downtrend near-miss is recorded each cycle the conflict persists; the existing near-miss archival cap bounds file growth. The deeper fix (making Pass-2 selection trend-aware) is left as a follow-up because it changes non-deterministic AI output.

**Validation**:
- 437 tests passing (was 425), all external calls mocked — zero real orders, zero tokens.
- New regression tests reproduce each production failure mode: stop-clamp-to-available, TP1 restore sizing off the live position, pyramid limit-buy (never market-buy) + unfilled-add cancel, gap-down cancel-settle ordering, fractional-bracket guard + resubmit skip, committed-cash reserve blocking, and the downtrend near-miss.
- Pre-existing brittle test (`test_qty_race_times_out_if_cancel_never_completes`) de-flaked by patching `_wait_for_order_canceled` instead of the global `time.time` (pytest's log capture was consuming the mocked clock).

## Decision 036: Behavior-preserving decomposition of the executor god-module
**Date**: 2026-06-07
**Decision**: Break the 3,267-line `executor.py` into cohesive single-responsibility modules and remove confirmed dead code — as a **behavior-preserving** refactor (pure code movement + extraction, zero logic changes), NOT a rewrite. An audit found the codebase is otherwise well-structured (26 of 27 modules are 80–400 LOC, 7,000+ test LOC, 424 passing); the debt was concentrated almost entirely in `executor.py`.

**Why not a rewrite**: This is a live, money-handling system being prepared for go-live. A rewrite of order-execution/risk code is exactly how subtle behavior changes cause real losses. So every step is guarded by the full test suite (must stay green) and committed independently for revertability.

**Key constraint discovered**: the test suite is deeply coupled to `executor`'s namespace (123+ `@patch("titantrade.executor.X")` targets). Mitigation: moved symbols are **re-imported into `executor.py`**, so `titantrade.executor.X` keeps resolving for callers that remain in executor (Python resolves patched names in the caller's namespace). Where a moved function's *internal* dependency is patched by a test (e.g. `place_native_stop_loss` calling `fetch_with_retry`), those specific patch strings are retargeted to the new module (`titantrade.broker.*`). `conftest.tmp_state_dir` patches `STATE_DIR` in each new state-owning module.

**Split COMPLETE** (branch `refactor/backend-modularization`, each step 424 green):
1. Dead code removed: `calculate_shares`, `_adjust_entry_price` (+ its dead `test_dynamic_entry.py`), `_highs`/`_lows`, `fetch_earnings_date`, dead constants, unused locals, 24+ unused imports (ruff). Added `ruff`+`vulture` dev extra.
2. 10 modules extracted (dependency flow leaf→orchestrator): `broker` (Alpaca client), `trade_state`, `trailing_state`, `pricing`, `cooldown`, `alerts`, `core_allocation`, `protection`, `entries`, `positions`.
3. `executor.py` is now a **691-line orchestrator** (`execute_trades`) — down from **3,267 LOC (−79%)**. No extracted module imports `executor` (clean DAG).

Test-coupling handling worked exactly as planned: re-exports preserved `titantrade.executor.X` patch targets for orchestrator-resident callers; tests exercising a moved function directly were repointed to its home module (mechanical, suite-verified). `conftest.tmp_state_dir` now patches `STATE_DIR` across all state-owning modules with `raising=False`.

**Follow-up done**: de-duplicated the shared entry-adaptation / bracket-validation / data-accessor / near-miss logic (helpers in `pricing.py` + `trade_state.py`); decomposed the worst long function — `execute_trades` 572 → 406 LOC via `_manage_held_bullish`. **Remaining (optional)**: the bearish-exit and ADJUST inline blocks in `execute_trades`, plus `_handle_bullish_entry` (259) and `resubmit_expired_brackets` (284), are cohesive sequential pipelines; further decomposition is deferred — they're safety-critical exit/stop-placement code, better split in a focused pass than rushed. Deployed through commit `68f4c62`.

**Trade-offs**: per-module test-patch retargeting is mechanical but real (the suite catches mistakes). Logger names become per-module (`titantrade.broker` etc.) — more precise log attribution, no functional change.

## Decision 037: Pyramiding correctly implemented as cancel → market-buy → re-stop (probe-driven)
**Date**: 2026-06-08
**Decision**: Replace the pyramid add mechanism with **cancel the protective stop → market-buy the add → re-place a stop covering the full enlarged position**, after a live paper probe disproved the Decision-035 assumption.

**Why**: Decision 035 fixed the "every pyramid fails as a wash trade" bug by switching the add from a market buy to a *marketable limit buy*, on the inference (from Alpaca's error text "use complex/limit/stop_limit orders") that a limit buy is accepted alongside a resting sell stop. A one-shot paper probe (`scripts/probe_pyramid_washtrade.py`, run on a live market day) **disproved this**: Alpaca rejects BOTH market and limit buys against a resting opposite-side stop with the same 40310000 wash-trade error. So the limit-buy fix never actually pyramided either — it just failed gracefully.

**Implementation** (`positions.py::maybe_pyramid_position`): read the existing protective stop; cancel it and poll to terminal (releasing the held qty); MARKET-buy the add (fastest fill → shortest unprotected window, and with the stop gone there is no opposite-side order to trip the wash-trade rule); poll the buy to `filled`; re-place a native stop covering original+added qty at the prior protective price. Every failure path (`cancel`, `buy`, `did-not-fill`, `re-stop`) restores a stop via `place_native_stop_loss` (which clamps to broker-available qty) and logs CRITICAL if even that fails.

**Trade-off accepted (user decision)**: there is now a brief (seconds, during market hours) window between dropping the old stop and placing the new one where the position is unprotected — an explicit, bounded exception to the otherwise-strict "never bare" model, taken because the user wants the pyramiding feature and the window is minimised (market buy) and guarded (restore-on-every-failure). Pyramiding only fires on a winner (+5%, trailing stop already at breakeven-or-better), so the exposure during the window is small.

**Validation**: 9 pyramid tests rewritten for the new flow; full suite green. The probe is the regression oracle — re-run it after any Alpaca-side change.

**Note**: `scripts/` is not copied into the Docker image (only the installed package is), so the probe is run via the bind-mounted `state/` dir or `docker compose run` with a mount. Add `COPY scripts ./scripts` to the Dockerfile if repeatable in-container probe runs are wanted.

Also fixed alongside (found in the live deployment logs): the ABORT exit (`_handle_abort`) now waits for order cancels to settle before closing (same held-qty race as gap-down — production ANET ABORT failure), and a `log_decision` `extra` carried a function object after the dedup rename (JSON file-handler `TypeError`), now corrected to the numeric ATR value.

## Decision 038: Bracket stop-leg never engages — on-fill GTC-stop reconciliation + bearish-exit cancel-settle
**Date**: 2026-06-08
**Decision**: Two fixes from a full sweep of the live deployment logs (root@server, paper account), driven by direct Alpaca probing rather than inference:
1. **On-fill GTC-stop reconciliation for bracket entries** (`entries.py`).
2. **Bearish-exit close uses the cancel→wait-for-terminal pattern** instead of a blind `sleep(2)` (`executor.py`).

### Finding 1 — a bracket's stop-loss leg never leaves `held` after the entry fills
Live probes on the paper account (buy-fill a bracket, then poll the legs) showed, **consistently and for both `stop` and `stop_limit` legs, day- and GTC-TIF**: when the entry fills, Alpaca activates the take-profit leg (`new`) but leaves the **stop-loss leg permanently in `held`**. `get_open_orders(status=open)` does not return `held` orders, so the executor sees "no stop." A freshly-filled position is therefore downside-unprotected until the **next** execute cycle's `_manage_held_bullish` heal cancels the (held) leg and places a standalone GTC stop — which is the *only* stop that actually rests on the book and fills (verified: those GTC stops do trigger). This is the root cause of the recurring `"<TICKER> has no stop; TP leg(s) hold all qty — cancelling TP and placing fresh stop"` WARNINGs (ANET, LLY, DXCM, DECK, EQIX, DVN) and a one-overnight coverage gap per entry. (Also confirmed live: a GTC *bracket* is accepted by Alpaca — so the old "brackets must be day-TIF" comment is outdated — but GTC does **not** fix the held-leg behaviour, so TIF was a red herring.)

**Fix (Option A, user-chosen)**: keep the atomic bracket entry, but after placing it, `entries._ensure_gtc_stop_on_fill()` polls the entry order to a terminal state within the cycle (`_ENTRY_FILL_POLL_SECONDS = 15`); on `filled`, it cancels the bracket's OCO legs (releasing the held qty), waits for them to settle, and places a standalone **GTC** stop covering the full position — a stop we can see and verify. Slow/limit fills that don't complete in the poll window fall through to the existing next-cycle `_manage_held_bullish` heal (the backstop). The take-profit leg is dropped on reconcile exactly as the heal already does (a weekly ADJUST reinstates a TP if appropriate; the stop is the safety-critical leg). Every failure path still attempts a stop via `place_native_stop_loss` (which clamps to broker-available qty) and logs CRITICAL if even that fails. Wired into all three bracket sites (`_handle_bullish_entry` tranche 1 + 2, `resubmit_expired_brackets`).

### Finding 2 — bearish exit still used the fragile blind-sleep
`execute_trades`' bearish-exit block had an off-hours guard (added after the DVN/FANG Sunday-night 403s) but the market-hours close path still did `cancel_all_orders_for_ticker(...)` + `time.sleep(2)` + `close_position_at_market`. Per ADR 042, Alpaca's `pending_cancel` can take 5–15 s to settle **even during market hours**, so the close could still 403 with code 40310000 (the just-cancelled stop still holds the shares). **Fix**: replace it with the same cancel-each → `_wait_for_order_canceled`-each → close sequence used by `_handle_abort`/gap-down (ADR 037). The existing capture-and-restore-stop-on-failure safety net is retained.

### Log sweep — everything else confirmed already-resolved
The 2-week ERROR/CRITICAL aggregation showed the remaining error classes are historical (pre-fix) and won't recur on the deployed code: data-bundle staleness (resolved by the `weekday_fetch` 13:00 job, ADR 035 — bundle now refreshed before every execute); pyramid wash-trade (ADR 037 cancel→buy→re-stop); FCX TP1/stop-restore/gap-down + fractional bracket (ADR 035); ANET ABORT (ADR 037, smoke-tested live this session). Gemini 503s are external (Google overload), retried, and fall back to CONTINUE.

**Also observed (not an error, logged for follow-up)**: the `weekday_sentry_preclose` job at 20:30 UTC runs *after* the 20:00 UTC close during summer (EDT) — so its stop management defers as off-hours, which is part of why the post-entry stop gap persists overnight. The schedule was tuned for EST; a DST-aware (or 19:30 UTC) pre-close time would let that cycle do real work in summer. Deferred — separate change.

**Trade-offs**:
- The on-fill poll adds up to 15 s per filled tranche to the entry cycle (twice-daily, not latency-sensitive). Unfilled entries return immediately on terminal/short-circuit; the common marketable entry fills in 1–3 s.
- Reconcile drops the bracket's TP leg (consistent with the pre-existing heal). Profit-taking continues via the TP1 tranche + ATR trailing stop.
- The held-leg behaviour was reproduced on **paper**; live-account behaviour may differ. The reconcile is safe either way (it only ever *adds* a verifiable GTC stop), and the next-cycle heal remains as a backstop.

**Validation**: 431 tests passing (was 426) — 5 new `TestEnsureGtcStopOnFill` cases (fill→cancel-OCO+GTC-stop, unfilled no-op, fractional skip, stop-failure-does-not-raise, empty-order no-op) plus the two bearish-exit tests retargeted to the cancel-settle primitives. A conftest autouse fixture no-ops `_ensure_gtc_stop_on_fill` for the many bracket-placement tests (it makes live broker calls); its own tests opt in via `@pytest.mark.real_stop_reconcile`. Ruff clean on changed files. The ABORT cancel-settle fix and the `_manage_held_bullish` heal were both smoke-tested end-to-end against the live paper account this session. Post-deploy, a manual `execute` ran a full live cycle clean (0 errors / 0 warnings) and the new pyramid flow fired twice (DXCM +9.4%, GS +5.5%) with no wash-trade rejects, both positions correctly re-stopped.

## Decision 039: DST-aware scheduling — interpret cron jobs in America/New_York
**Date**: 2026-06-08
**Decision**: The built-in scheduler now interprets job cron times in the schedule's top-level `timezone` (set to `America/New_York`), and the market-relative jobs are expressed in ET — so wall-clock times track US DST automatically instead of drifting an hour twice a year.
**Problem**: `data/schedule.json` carried a `"timezone": "UTC"` label but `scheduler.start_scheduler()` created `BackgroundScheduler()` with **no** timezone, and all crons were fixed UTC. With market hours shifting between EDT (13:30–20:00 UTC) and EST (14:30–21:00 UTC), the fixed-UTC times were only ever correct for one half of the year:
- `weekday_sentry_preclose` at 20:30 UTC ran **after** the 20:00 UTC summer (EDT) close → its stop management deferred as off-hours, leaving freshly-filled positions' stop gaps to persist overnight (the issue flagged in ADR 038).
- `weekday_sentry_morning` at 14:15 UTC (= 10:15 ET only in summer) would run **pre-market** in winter (14:15 UTC = 09:15 EST, before the 09:30 open).
**Fix**:
- `data/schedule.json`: `timezone` → `America/New_York`; times converted to ET — fetch 09:00, gapcheck 09:35, morning sentry+execute 10:15 (the ADR-Phase-1.11 "after opening volatility" target), price checks 12:00/14:00, **pre-close sentry+execute 15:30** (30 min before the 16:00 close, year-round), daily summary 16:30, Sunday full pipeline 16:00.
- `scheduler.py`: `_load_schedule_doc()` reads the full document; `start_scheduler()` reads `doc["timezone"]` (default `UTC`). New `_schedule_timezone` global so `_save_schedule()` (hit by the Flutter job-toggle path) preserves the tz instead of hard-coding `"UTC"`.
- **The non-obvious part (cost two iterations, verified on the deployed apscheduler 3.11.2):** APScheduler 3.11 normalizes the *scheduler's* timezone to a stdlib `zoneinfo` object, and a `CronTrigger` that **inherits** the scheduler tz then mis-computes fire times — the job fires at the right wall-clock hour but with a **UTC offset** (e.g. pre-close at `15:30:00+00:00` instead of `15:30:00-04:00`), i.e. effectively in UTC, silently defeating the whole fix. Passing the timezone **explicitly to each `CronTrigger`** computes correctly. So `start_scheduler()` and the `set_job_enabled` re-add path now build `CronTrigger(timezone=tzinfo, **cron)`. The tz is resolved via **pytz** (`_resolve_timezone`, new `pytz` dependency) — both pytz and zoneinfo work when passed explicitly, but pytz is APScheduler 3.x's best-tested path.
**Trade-offs**: jobs now fire at fixed ET wall-clock times, so their UTC instant shifts by an hour across DST boundaries (intended). Transition-day edge cases (spring-forward 02:00–03:00 gap, fall-back repeat) don't apply — no job runs near 02:00 ET. Added one small dependency (`pytz`).
**Validation**: 435 tests passing (was 431) — 4 new scheduler tests, including `test_cron_fires_in_et_not_utc` which asserts the job's `next_run_time` carries a **non-zero UTC offset** (the regression that the first iteration's tz-string-only check missed). Deployed and verified on the server: all jobs' `next_run` now show `-04:00` (EDT); `weekday_sentry_preclose` fires 15:30 ET = 19:30 UTC, before the 20:00 UTC summer close.

## Decision 040: Replace FMP with Alpaca + FRED + Finnhub
**Date**: 2026-06-08
**Decision**: Remove the paid Financial Modeling Prep (FMP, €25/mo) dependency entirely, replacing every data input with free sources behind a new unified `market_data.py` layer. The connector functions in `data_fetcher` / `market_context` / `earnings` / `daily_sentry` keep their signatures and return shapes — only the source behind them changed.

**Why**: FMP was operationally critical (it fed all price data) but not strategically irreplaceable — ~80% of its role (prices, quotes, news) maps onto Alpaca's free data API, which uses keys we already have. The remaining macro + per-ticker fundamentals have free official/proper sources. The codebase was already cleanly "connectored" (one function per data type), so the swap was low-coupling.

**Source mapping** (all verified reachable from the production server before implementing):
| Data | Source | Notes |
|---|---|---|
| OHLCV bars, latest price, daily change %, news | **Alpaca** data API (`data.alpaca.markets`, existing keys, IEX feed, free) | robust core |
| VIX, 10Y/2Y treasury, economic-release calendar | **FRED** (St. Louis Fed, free `FRED_KEY`) | official; CPI/jobs/PPI/GDP/PCE/retail release dates + a `data/fomc_dates.json` schedule for FOMC (not a FRED release) |
| Earnings dates, analyst recommendation trend, sector | **Finnhub** (free `FINNHUB_KEY`) | per-ticker enrichment |

**Implementation**:
- New `market_data.py`: `get_ohlcv` / `get_latest_price` / `get_daily_change_pct` / `get_news` (Alpaca, with cursor pagination); `get_vix` / `get_treasury_yields` / `get_economic_calendar` (FRED + FOMC file); `get_earnings_dates` / `get_analyst_ratings` / `get_sector` (Finnhub). Every function degrades to `[]`/`None`/`{}` on missing key or error — preserving FMP's prior fail-open behaviour (the macro/earnings gates already skip on missing data).
- Connectors now delegate: `fetch_ohlcv`, `fetch_news` (dedup retained), `fetch_analyst_ratings`, `fetch_economic_calendar`, `market_context._fetch_bars/_fetch_vix_level/_fetch_treasury_yield/_fetch_sector`, `earnings.fetch_all_earnings_dates`, `daily_sentry._fetch_current_price/_fetch_spy_quote`, and the backtest `download_historical_data`.
- `config.py`: `AlpacaConfig.data_base_url`/`data_feed`; new `FREDConfig`, `FinnhubConfig`; `FMP_KEY` moved from required → optional (`OPTIONAL_KEYS`), alongside `FRED_KEY`/`FINNHUB_KEY`. `FMPConfig` kept as a vestigial stub so existing fixtures/`cfg.fmp` references don't break.

**Trade-offs / what changed**:
- **Price-target consensus is dropped** — it has no free source post-FMP (Finnhub's is premium, Yahoo's is crumb-locked). Claude still receives the analyst **recommendation mix** (strong-buy/buy/hold/sell/strong-sell) from Finnhub. This is the one genuine functionality reduction.
- **Two new free keys required** (`FRED_KEY`, `FINNHUB_KEY`). Without them the macro inputs (VIX/treasury/econ-calendar) and per-ticker fundamentals (earnings/analyst/sector) are absent and their gates fail open — degraded but not broken; core price/news/quotes (Alpaca) work regardless.
- **FOMC dates** live in `data/fomc_dates.json` (FOMC isn't a FRED release). The 2026 dates there are best-effort and **must be verified against the official Fed calendar**; a wrong date only causes a spurious/missed 6h macro-blackout (gate fails open).
- Alpaca's free tier serves the **IEX** feed (not full SIP). For daily bars / EOD-style decisions this is equivalent; intraday coverage is thinner but the strategy is daily-cadence.

**Validation**: 461 tests passing (was 435) — `test_market_data.py` covers native parsing, no-key fail-open paths, facade dispatch (native↔fmp), and the retained FMP provider's parsing. Ruff clean. Verified live on the paper account end-to-end with real keys: full `fetch` produces a healthy bundle — 15 stocks with 200-SMA/RSI/ATR + 47–50 news each, VIX 21.51 (FRED), treasury 4.47/4.05 (FRED), econ calendar (CPI/PPI/FOMC/retail), analyst recommendation mix (Finnhub) — zero errors.

**Provider abstraction (per follow-up request — keep FMP code, make switching back trivial)**: the implementations live in `data_providers/native.py` (Alpaca+FRED+Finnhub) and `data_providers/fmp.py` (the original FMP fetchers, retained verbatim behind the same interface). `market_data.py` is now a thin **facade** that dispatches per `cfg.data_provider` (env `DATA_PROVIDER`, default `native`). Reverting to FMP is a one-liner: `DATA_PROVIDER=fmp` (+ a valid `FMP_KEY`), no code change. Both providers implement the identical 10-function contract documented in `data_providers/__init__.py`.

**FRED economic-calendar fix**: the blanket `/releases/dates` endpoint never surfaced near-term dates (its future entries span all ~300 FRED releases, so the next-21-day ones fall outside any reasonable limit). Fixed by querying **per-release** `/release/dates?release_id=…` for the high-impact releases (CPI=10, jobs=50, PPI=46, GDP=53, PCE=54, retail=17) — verified it returns upcoming dates (CPI 2026-06-10, PPI 06-11, etc.).

**Live status**: `FRED_KEY` + `FINNHUB_KEY` are in the server `.env`; all macro + per-ticker data confirmed flowing. FMP subscription can be cancelled.
