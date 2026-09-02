# TitanTrade TODO

## Phase 1.34: September checkup — sentry price-override corroboration fix (2026-09-02) — Decision 057
Checkup of the live server (Aug 18 → Sep 1): 0 errors in 15 days, all 8 jobs green, $3.24 AI cost, every overlay position stop-protected, both images current. Clean window (`--since 2026-07-08`, 39 td): **+2.58% vs SPY +2.19%, beta 0.60, Sharpe 1.39 vs 1.27, down-capture 0.73** — still adding value, edge narrower than on Aug 18. First pullback since the hold (Aug 12 peak → Sep 1, 14 td): **−3.11% vs SPY −1.41%, down-capture 1.16** — 11 exits and 9 re-entries in 10 sessions.
- [x] **Fix — `price_concern` no longer corroborates a 3–5% ABORT**: 36 of 39 "news-confirmed" ABORTs since ADR 045 had no headlines and no market concern, and Gemini's own reasoning called each move normal volatility. The flag is circular (the prompt shows Gemini the price alert and asks whether it is a factor). `daily_sentry.check_stock()` now confirms only on `conflicting_headlines` or `market_concern`. 2 regression tests; **536 tests green**; touched files ruff-clean (2 pre-existing E402s in the test module untouched).
- [x] Stale-doc fix: `docs/agent_instructions.md`, `TitanTrade/docs/agent_instructions.md`, `TitanTrade/docs/architecture.md` still described the pre-ADR-045 "3% hard override".
- [x] **Deployed 2026-09-02** on the operator's decision (this changes live abort frequency in the 3–5% band — the sentry sensitivity the 2026-06-22 hold froze): both images rebuilt (`api` + `titantrade`), API container restarted, 8 scheduler jobs verified, well before the day's 13:00 UTC fetch.
- [ ] Watch item — analyst ADJUST stops are noise-tight: Aug 30 set HCA $413 (0.49×ATR, 1.16% below close), FCX $73.60 (1.03×), DASH $228.50 (1.16×) → all three tagged at the Sep 1 open on a −0.7% SPY day; Aug 16's JPM $354 / ANET $184 / EQIX $1,055 / URI $1,094 (1.7–2.4×ATR) all tagged Aug 19–20 on a −1.3% SPY move, then re-bought higher Aug 24–25. The system's own trail is 3.0×ATR; the ADR 055 1.5% floor covers entries only. Candidate: ATR-scaled floor on ADJUST raises (keep the existing stop when the analyst's is tighter than ~1.5×ATR). Strategy change → parked under the hold.
- [ ] Watch item — cooldown override is nearly always satisfied: "price recovered" = ≥1% above the *thesis stop*, which any 3–5% abort trivially meets, so the 72 h cooldown is effectively 24 h (EQIX: aborted $1,031.74 Aug 31 14:15, re-bought $1,032.65 Sep 1 15:13). Candidate: require recovery relative to the abort price. Parked.
- [x] Housekeeping (titanserver): unused docker images pruned at deploy (`docker image prune -a`); build cache (3 GB) left for a later `docker builder prune`.
- [ ] Benchmark caveat still applies: `benchmark_metrics.json` (90-day) carries the Jul 2–7 CRWD split artifact until ~mid-October (its −8.15% max DD, 27% vol and 1.11 down-capture are polluted); read `--since 2026-07-08`.

## Phase 1.33: Stop-out cooldown + stale-ADJUST guard + doc accuracy pass (2026-08-18) — Decision 056
Mid-August checkup (Aug 4 → Aug 18): 0 errors in 14 days, all jobs green, $3.00/2wk AI cost, equity $112.4k. Clean window (`--since 2026-07-08`, 27 td): **+4.29% vs SPY +4.16%, beta 0.53, Sharpe 3.18 vs 3.06, down-capture 0.58**. ADR 055 ABORT-guard verified live (fired 6×: DVN ×5, CRWD ×1); WMT received its first thesis. Churn down to ~$350 (one CRWD abort round-trip). The Aug 4–5 DVN sequence exposed two remaining churn paths, both now closed:
- [x] **Fix 1 — stop-outs start the cooldown**: DVN's GTC stop filled 13:34, the 14:15 run re-bought it 42 min later (broker-side fills are never "handled", so no cooldown ever started). New `record_stop_out_cooldowns` scan at the top of `execute_trades` — clock stamped at FILL time (idempotent), same override policy as aborts. `entries.py`, `cooldown.py`, `executor.py`.
- [x] **Fix 2 — stale-ADJUST guard**: the review's $43.50 ADJUST stop (computed for the old DVN position) was re-applied to the fresh $43.65 re-entry → 0.34% stop → tagged out next morning. Section 4a now skips ADJUST when `position_opened_after(ticker, generated_at)` — pyramid ADDs excluded, fails open. `trade_state.py`, `executor.py`.
- [x] **Doc accuracy pass**: retired default models (`claude-sonnet-4-20250514`, `gemini-2.0-flash`) and the FMP/SEC-API stack purged from `api_reference.md`/`deployment.md`; parameter tables and gate counts across `risk_management.md`/`features.md`/`agent_instructions.md`/`architecture.md`/CLAUDE.md updated to code-verified values (0.55 confidence floor, 5% cash, 50% sector, 2-day earnings, 6h macro, 25% position cap, 2.5% ATR budget, 3.0×ATR trail, 9 gates, weekly review not 14-day expiry).
- [x] 10 new regression tests; **534 tests green**; touched files ruff-clean.
- [x] Deployed 2026-08-18: both images rebuilt, API restarted, scheduler verified.

## Phase 1.32: August checkup — same-run ABORT guard + min stop-distance floor (2026-08-04) — Decision 055
Checkup of the live server (Jul 23 → Aug 4): 0 ERROR/CRITICAL in 12 days, all 8 jobs green, $7.80/mo API cost, every overlay position stop-protected. Performance (clean window `--since 2026-07-08`, 18 trading days): **+1.96% vs SPY +1.67%, beta 0.49, Sharpe 2.29 vs 1.74, down-capture 0.64** — first window beating SPY on both raw and risk-adjusted return. ADR 054 guards verified live (13 dust orders blocked as near-misses; split/suspect guards correctly silent).
- [x] **Fix 1 — resubmit ignores same-run ABORT**: sentry wrote LLY ABORT 14:15:04 (Jul 31), resubmission bought 12 LLY 14:15:27, abort handler sold them 14:15:45. `resubmit_expired_brackets` now skips tickers whose current sentry signal is ABORT; `_handle_bullish_entry` gets the same defensive guard. `entries.py`.
- [x] **Fix 2 — minimum stop-distance floor**: URI entered $1084.25 / stop $1081.25 (0.28%) and was noise-stopped 27 min later. New `pricing.stop_too_tight` (`MIN_STOP_DISTANCE_PCT = 1.5%`, flat not ATR-scaled) refuses fresh entries/resubmits with noise-level stops. `pricing.py`, `entries.py`.
- [x] 7 new regression tests; **524 tests green**; touched files ruff-clean.
- [x] **FANG → WMT watchlist swap applied to live server** (ADR 049 follow-through; FANG confirmed flat since Jul 27). First WMT thesis: Sunday Aug 9 analysis.
- [x] Deployed 2026-08-04: both images rebuilt (`api` + `titantrade`), API container restarted, scheduler verified.
- [ ] Abort churn watch item (hold decision stands): Jul 28 cluster (ANET/DVN/URI, ~$1–1.2k incl. re-entry slippage) was all news-confirmed or catastrophic — the graduated-severity design working; churn is now genuine-signal whipsaw, not threshold noise. Sentry override threshold remains the #1 lever when the hold ends.

## Phase 1.31: July monthly checkup — split-artifact hardening + min-notional floor (2026-07-23) — Decision 054
Month review of the live server (Jun 23 → Jul 22): all jobs firing, 0 ERROR/CRITICAL logs, $6.25/mo API cost, every position stop-protected. Performance: month −0.1% vs SPY +0.4%; 90d +5.11% vs SPY +5.20% (alpha +6.1%/yr, beta 0.83). Found the CRWD 4:1 split incident (bot sold the position at the post-split "bottom" on Jul 2; Alpaca paper adjusted the position 3 trading days late and made the account whole Jul 7 — net ≈ $0 but benchmark metrics polluted) and dust orders filling (URI 0.01 sh = $11).
- [x] **Split guard**: gap-down protection consults `GET /v2/corporate_actions/announcements` for gaps >30% below the stop; skips + alerts (`notify_split_suspected`) when a recent split explains the move; no announcement / feed error → sells as before. `protection.py`, `broker.py` (`get_recent_split_announcements`).
- [x] **Suspect account-value guard**: portfolio value ±50% off the recorded peak is treated as broker data corruption — entries blocked with a "suspect broker data" reason + deduped Discord alert, peak file never takes the glitch (`update_peak_value` refuses >+50% spikes). `risk_manager.py`.
- [x] **Min-notional floor**: `MIN_POSITION_NOTIONAL = $500` in the sizing gate — dust orders blocked as `position_size` failures, recorded as near-misses. `risk_manager.py`.
- [x] 14 new regression tests; **517 tests green**; ruff clean on touched files (incl. 7 pre-existing findings fixed).
- [x] **DEPLOYED 2026-07-23 ~09:35 UTC** (commit 76f7595): API container rebuilt + restarted; scheduler verified live (all 8 jobs registered, correct ET next-run times) — well before the day's 13:35 UTC gapcheck.
- [x] **CLI image rebuilt** (`docker compose build titantrade`) — verified: `benchmark --since 2026-07-08` runs. Clean post-artifact window (9 trading days): strategy +0.01% vs SPY +0.39%, beta 0.64, vol 10.5% (vs the polluted 27%), max DD −1.64% (vs polluted −8.15%), down-capture 0.72.
- [x] DECK 0.11-share dust: sell_to_close day market order submitted (accepted, fills at the 09:30 ET open).
- [ ] Strategy watch item (NOT for now — hold decision stands): sentry PRICE-BASED OVERRIDE churn was the month's dominant real drag (~$1.5–2k; 7 of 10 aborts overrode Gemini's own "normal volatility" read; URI whipsawed twice). Revisit the override threshold when the hold period ends.
- [ ] Benchmark caveat: ignore the Jul 2–7 phantom equity swing when reading `benchmark_metrics.json` (max DD/vol/Sharpe overstated until the window rolls off ~mid-October); prefer `--since 2026-07-08` windows.

## Phase 1.30: Gap-down protection cross-checks the live quote (2026-07-02) — Decision 053
Morning-after check of the ADR 052 deploy: fix healthy (0 errors across all runs; the 19:30 pre-close run cleanly executed `DVN: SELL (ABORT)`). But spotted an Alpaca paper glitch — CRWD position marked $196 (prev-close $193) vs the real $772.6 market price (exact 4:1 phantom split on price, not share count); reported equity understated ~$9k, true equity unchanged (`last_equity` $109,046).
- [x] Root cause of the *system* risk: `check_gap_down_protection` trusted `position.current_price` and would have liquidated healthy CRWD at the 09:35 ET gapcheck on the glitched mark.
- [x] Fix: cross-check `_fetch_current_price` before the market-sell; skip when live price `>= stop_price` (stale/glitched mark); missing quote falls through to the sell (never weaken protection). `protection.py`.
- [x] 3 new regression tests (`TestGapDownLiveQuoteCrossCheck`); existing gap test mocks the quote; tidied dead imports. **503 tests green, touched files ruff-clean.**
- [x] Committed, pushed, and deployed (`docker compose build api && up -d api`) before the 13:35 UTC gapcheck.
- [ ] The CRWD mark is a transient broker artifact — expect it to re-mark at the 13:30 UTC open; confirm equity reads ~$109k again after open.

## Phase 1.29: Two execution bugs from the 9-day log review (2026-07-01) — Decision 052
Log review of `titantrade-api-1` since the 2026-06-22 restart: system healthy (0 tracebacks, 0 CRITICAL, all scheduled jobs firing, every real position stop-protected). Found two recurring 422s.
- [x] **Bug 1 — fractional-dust stops (JPM 0.13-share, formerly ANET):** `place_native_stop_loss` hardcoded `tif="gtc"` and never floored the qty, so it 422'd (`"fractional orders must be DAY orders"`) on every run for a sub-1-share remainder — the plain-stop fallback shared the flaw. Now floors fractional → whole shares (GTC stop on the bulk) and places nothing for `<1`-share dust; executor `ADJUST` path also skips `0 < qty < 1` early. `broker.py` + `executor.py`.
- [x] **Bug 2 — tranche2 tight-stop 422 (EQIX):** tranche2 (dip-buy at `entry×0.985`) reused tranche1's stop; when the stop is within ~1.5% of entry the tranche2 limit falls below it → 422, silently dropping the second tranche. Now validates `bracket_levels_invalid(tranche2_price, stop, tp)` and skips tranche2 (keeps tranche1). `entries.py`.
- [x] 4 new regression tests (`TestFractionalDustStop`, `TestTranche2TightStopSkip`); **500 tests green, ruff clean**. Behavior-preserving for whole-share positions and normal-stop entries.
- [ ] **DEPLOY: rebuild + restart the API container** (`docker compose build api && docker compose up -d api` on titanserver) — the running image predates the fix (it already contains ADR 050/051, so a rebuild now adds only 052).
- [ ] Optional cleanup: sweep the JPM 0.13-share dust (a manual/market DAY sell) so it stops showing as an unprotected position; not required (fix already silences the error).

## Phase 1.28: Benchmark metrics — beta / alpha / Sharpe vs SPY (2026-06-22) — Decision 051
- [x] New `benchmark.py`: pure `compute_metrics` (beta, alpha, Sharpe, info ratio, correlation/R², vol, total/excess return, up/down capture, max drawdown) + `compute_benchmark` live wiring (Alpaca portfolio history + SPY closes, date-aligned) + `classify` verdict.
- [x] `broker.get_portfolio_history` (Alpaca `/v2/account/portfolio/history`).
- [x] Caught + fixed the Alpaca EOD-timestamp off-by-one (20:00 ET = 00:00 UTC next day) that yielded spurious negative betas; session date now derived in market time. Regression test added.
- [x] Surfaced via CLI (`benchmark [days] [--since]`), API (`/api/benchmark`, `/api/benchmark/refresh`), and a daily-summary Discord line (`daily_summary` refreshes `benchmark_metrics.json` first).
- [x] 20 new unit tests (hand-computable fixtures); 496 total green; ruff clean.
- [x] Evaluated live: since inception beta 0.42 / alpha +6.6%/yr (underperformance is low-beta, not negative selection); stabilized window up-cap 0.98 / down-cap 0.71 (adding value).
- [ ] **DEPLOY: rebuild + restart the API container** (`docker compose build api && docker compose up -d api`) so `/api/benchmark` and the daily-summary line go live. (Math + CLI work today; the baked image must be rebuilt for the API/scheduler paths.)
- [ ] Optional: add a beta/alpha/Sharpe card to the Flutter dashboard (reads `/api/benchmark`).
- [ ] Re-evaluate after the next genuine SPY drawdown — that's the test of whether down-capture < 1 is saving more than the sentry's whipsaw costs.

## Phase 1.27: Analyst model — retired Sonnet 4 → Opus 4.8 + adaptive thinking (2026-06-17) — Decision 050
🔴 **URGENT — deploy before Sunday 2026-06-21.**
- [x] Found prod-breaking bug: analyst model `claude-sonnet-4-20250514` **404s (retired 2026-06-15)**; confirmed via Models API. Next weekly run (Sun Jun 21) would 404 → no thesis → orphan-close liquidates ALL positions.
- [x] Switched to `claude-opus-4-8` + adaptive thinking (analyst is the alpha source; cost delta ~$2-5/mo, trivial). Dropped `temperature` (400s on Opus); added refusal handling + thinking-aware text extraction; `max_tokens` 8192→16000.
- [x] Fixed `cost_logger` pricing (added opus-4-8 $5/$25 + current Claude/Gemini; retired-Sonnet entry was missing → historical logged cost ran ~1.5× high on the $5/$15 default).
- [x] Validated end-to-end with a ~$0.001 live probe (SDK 0.86 + opus-4-8 + adaptive thinking OK). +3 unit tests; 476 green; ruff clean. Prompts unchanged (they're solid).
- [ ] **DEPLOY: rebuild + restart the API container** (`docker compose build api && docker compose up -d api`) before the Sun 16:00 ET `sunday_full` job. This is the one change that can't wait for a convenient window.

## Phase 1.26: Watchlist tweak — FANG -> WMT (2026-06-17) — Decision 049
- [x] Beta/correlation analysis of the 15 names: well-built (beta 0.30–1.85, 8 sectors), only two redundant pairs (DVN+FANG 0.86, JPM+GS 0.79).
- [x] Dropped **FANG** (redundant with held DVN, and not currently held → no forced sell); added **WMT** (Consumer Staples, beta 0.46, 0.17 avg corr — defensive ballast that still trends, so the momentum overlay will use it). Now 15 names / 9 sectors.
- [x] Decided NOT to add mega-cap tech — the 30% SPY core already holds Mag-7; overlay should complement the core, not duplicate it.
- [x] Applied to `config.py` default + backtest `SECTOR_MAP`; ADR 049.
- [x] **Applied to the live server 2026-08-04** (Phase 1.32 deploy window; FANG confirmed flat since Jul 27). Watchlist changes can't be backtested (survivorship); judge WMT on forward paper performance.

## Phase 1.25: Widen trailing ATR multiplier 2.5 -> 3.0 (2026-06-17) — Decision 048
Goal: more upside in rallies without losing the downside protection. Trailing width is the asymmetric lever (only affects winners; losers exit at the unchanged initial stop).
- [x] Downloaded a real 2021-2026 dataset (1400 bars incl. the 2022 −25% bear) so the test spans a full cycle, not just a bull.
- [x] Regime test: wider trailing improves bull (full cycle +32%→+58% at 3.5×) and the 2022 bear is flat-to-better with no rise in max drawdown. Beyond 3.5× the bear column is identical → trailing isn't the binding exit in a bear, so it can't add downside risk.
- [x] Chose **3.0** (conservative), not 3.5: 3.5 was a path-dependent peak (4.5× reverted). Trust the direction, not the magnitude.
- [x] Applied to live config (`config.py`) + backtest simulator default; ADR 048; 473 tests green; ruff clean.
- [ ] **Staged, NOT deployed** — production stays on 2.5 until a deploy window. Account is paper, so deploying = the forward test. Watch live trailing behavior + bull capture after deploy.

## Phase 1.24: Backtest defaults to the live strategy (2026-06-17) — Decision 047
A backtest of the 3-yr data produced only 7 trades / fake 0% win rate. Signal source was fine (500 BULLISH signals); the engine defaulted to the legacy v1 dip-buy path production no longer runs.
- [x] Root-caused: `run_backtest` defaulted to `strategy_v2=False` (legacy dip-buy); v1 limit orders rarely fill on momentum signals + never expired (stuck order blocks ticker); `_fill_buy` set TP to the entry price (→ instant break-even "take profit") and overwrote tranche-1 on the second fill.
- [x] `strategy_v2=True` is now the default (CLI `backtest`, dashboard action, direct calls); recorded in result `config`; `--legacy`/`--v1` opts into the old path.
- [x] v1 correctness fixes: stop/TP carried from the thesis on the order, second tranche accumulates (no overwrite), unfilled limit orders expire after `limit_order_ttl_days` (10).
- [x] `run_ab_comparison` pinned to v1 (v2 force-enables confidence scaling → identical A/B arms).
- [x] Verified on real data: default 7 → **243 trades, 63% win, PF 1.41**; stress window (SPY −19%) only **−5%**; legacy 7 → **161 trades, 56% win** with real P&L. **472 tests green (+6)**.
- [ ] Backtest measures risk/execution mechanics only (synthetic theses, no LLM, survivorship-biased to today's watchlist) — NOT the AI alpha or "real probability of success". Forward paper track remains the only clean read.
- [x] `run_backtest(sim_overrides=...)` pass-through added so mechanical knobs (trailing ATR mult, core %, pyramid/TP1, sizing, cash reserve) are A/B-able. Recorded in result config. (+1 test, 473 total.)
- [x] Structural study run (Decisions-pending). Key findings on the synthetic-signal/bull-window backtest: (1) **pyramiding is value-destructive** — pyramid OFF beats ON on return/Sortino/maxDD/PF (PF 1.90 vs 1.41); TP1 helps. (2) trailing-ATR has a **fragility cliff below 2.5×** (whipsaw); current 2.5 sits on the knee, 3.0 lowers maxDD. (3) the **SPY core does ~all the work — the stock-picking overlay is a net loser standalone (−10%, PF 0.40)**, i.e. the whole edge rides on Claude's signal quality vs a technical baseline. (4) defensive profile is **consistent across regimes** (positive every year, contained DD, −5% vs SPY −19% in the 2025 correction).
- [x] **Investigated pyramiding on LIVE trades** (5 adds: GE/GS/FCX helped, DXCM/DVN hurt). Net **+$56 on $18k deployed (+0.3%) — a wash**, 3/5 positive. Does NOT confirm the backtest's "pyramid hurts" — the backtest pyramids into noise (synthetic signals), live pyramids into Claude's picks. **Decision: keep pyramiding on**; backtest mechanical findings don't transfer to the AI signal source. (n=5, all still open/unrealized <3wk → preliminary; revisit at ~15-20 adds with realized exits.)
- [ ] Revisit pyramiding once ~15-20 live adds exist with realized exits; watch concentration risk (backtest showed +2pt maxDD from pyramiding).

## Phase 1.23: Post-deploy log review fixes (2026-06-09) — Decision 041
- [x] Log files roll at UTC midnight (`DailyJSONFileHandler`) — long-running container no longer piles all days into the process-start-dated file.
- [x] Gemini 503 investigation: 506 × 503 / 0 × 429 over ~10wk = Google-side "model overloaded" capacity (not an outage, not quota). Live probe: 2.5-flash up; only retired 2.0-flash 404s.
- [x] Gemini model-fallback chain (2.5-flash → flash-lite → flash-latest), bounded retries; existing CONTINUE-fallback safety net retained.
- [x] +5 tests (logger rotation, Gemini fallback chain). Full suite green.

## Phase 1.22: Replace FMP with free sources (2026-06-08) — Decision 040
Drop the €25/mo Financial Modeling Prep dependency.
- [x] New `market_data.py` unified layer: Alpaca (bars/quotes/news), FRED (VIX/treasury/econ-calendar), Finnhub (earnings/analyst/sector). All fail-open.
- [x] Rewire connectors (data_fetcher, market_context, earnings, daily_sentry, backtest downloader) to delegate; signatures + return shapes unchanged.
- [x] `config.py`: Alpaca data URL, FRED/Finnhub configs; FMP_KEY → optional.
- [x] `data/fomc_dates.json` for FOMC (not a FRED release) — ⚠️ 2026 dates best-effort, verify against federalreserve.gov.
- [x] 20 new `test_market_data.py` cases (455 total); ruff clean.
- [x] FRED_KEY + FINNHUB_KEY added to server `.env` (live); full bundle verified flowing (VIX 21.51, CPI/FOMC calendar, analyst mix, earnings).
- [x] Pluggable providers (Decision 040 follow-up): `data_providers/{native,fmp}.py` + `market_data.py` facade; revert anytime with `DATA_PROVIDER=fmp`. FMP code retained.
- [x] FRED econ-calendar fixed (per-release `/release/dates`); events stamped with ET release times (FOMC 14:00, data 08:30) so the macro-blackout 6h window aligns — caught + fixed in E2E that date-only FRED dates broke the FOMC blackout.
- [x] FOMC 2026 dates verified against federalreserve.gov (all 8 correct).
- [x] End-to-end verified token-free: `fetch` (healthy bundle), risk gates (VIX scaling, macro blackout fires on timed FOMC, earnings blackout), `pricecheck` (9 positions via Alpaca quotes), `gapcheck` — zero errors. 461 tests green.
- [ ] Price-target consensus dropped (no free source) — Claude still gets the recommendation mix.
- [ ] **User action**: cancel the FMP subscription (nothing uses it now).
- [ ] Optional: a live `analyze`/`sentry` AI round-trip (spends tokens) to confirm the AI steps consume the new bundle — deferred per the no-token preference; data feeding them is verified well-formed.

## Phase 1.21: Live-log error sweep — bracket stop reconciliation + bearish-exit (2026-06-08)
From a full sweep of the deployed paper-account logs (see Decision 038), driven by direct Alpaca probing.
- [x] Root-caused via live probe: a bracket's stop-loss leg never leaves `held` after the entry fills (only the TP activates) — for both `stop`/`stop_limit` and day/GTC TIF. The real protection is the standalone GTC stop placed by the next-cycle heal.
- [x] On-fill GTC-stop reconciliation (`entries._ensure_gtc_stop_on_fill`): poll the entry to terminal within the cycle; on fill, cancel the OCO legs and place a visible GTC stop. Wired into all 3 bracket sites (tranche 1+2, resubmit). Slow fills fall through to the next-cycle heal.
- [x] Bearish-exit close uses cancel→`_wait_for_order_canceled`→close (was `cancel_all` + blind `sleep(2)`) — same ADR-037 pattern as ABORT/gap-down; fixes the DVN/FANG 403s if a market-hours cancel takes >2s.
- [x] Confirmed remaining log errors are historical/already-fixed (data staleness → daily fetch; pyramid → ADR 037; FCX/fractional → ADR 035; ANET ABORT → ADR 037, smoke-tested live).
- [x] 431 tests passing (was 426); ruff clean on changed files; ABORT fix + `_manage_held_bullish` heal smoke-tested end-to-end on the live paper account.
- [x] DST-aware scheduling (Decision 039): scheduler now interprets crons in `America/New_York`; all market-relative jobs converted to ET (pre-close now 15:30 ET = before the close year-round; morning 10:15 ET no longer runs pre-market in winter). 434 tests.
- [x] Deployed to server (commit `f054cf8`) + verified: full live `execute` cycle ran clean (0 errors/warnings), new pyramid flow fired twice correctly.

## Phase 1.20: Executor decomposition (2026-06-07) — behavior-preserving
Branch `refactor/backend-modularization`; see Decision 036. Each step kept 424 tests green + is committed.
- [x] Remove dead code (`calculate_shares`, `_adjust_entry_price` + its test file, `_highs`/`_lows`, `fetch_earnings_date`, dead constants, unused locals, 24+ unused imports); add `ruff`+`vulture` dev extra
- [x] Extract all 10 modules: `broker`, `trade_state`, `trailing_state`, `pricing`, `cooldown`, `alerts`, `core_allocation`, `protection`, `entries`, `positions`
- [x] **executor.py 3,267 → 691 LOC (−79%)** — now a pure orchestrator; clean dependency DAG (no module imports executor)
- [x] Test patch-target retargeting (re-export for orchestrator callers; home-module for direct tests); conftest STATE_DIR loop with `raising=False`
- [x] De-duplicate shared entry-adaptation / bracket-validation / data-accessor / near-miss logic (pricing.py + trade_state.py helpers)
- [x] Decompose worst function: `execute_trades` 572 → 406 via `_manage_held_bullish`
- [x] Redeploy + re-verify on server (commit `68f4c62`)
- [ ] Optional further decomposition (cohesive, safety-critical — do fresh, not rushed): bearish-exit + ADJUST inline blocks in `execute_trades`; `_handle_bullish_entry` (259 LOC); `resubmit_expired_brackets` (284 LOC)

## Phase 1.19: Execution-safety hardening (2026-06-07) — go-live blockers
From a 14-day paper-log review (see Decision 035). All six found bugs fixed:
- [x] TP1 race fixed: poll the partial sell to `filled` before sizing the breakeven stop; restore handler sizes off the live position, not the stale pre-sell qty
- [x] `place_native_stop_loss` clamps to broker-reported `available` qty as a last resort — a position is never left bare (the FCX `CRITICAL stop restore failed` case)
- [x] Pyramid adds via marketable LIMIT buy (was a market buy → 100% wash-trade reject); stop extended to cover the enlarged position after fill
- [x] Gap-down protection waits for the cancel to release held qty before the market sell (was 403-ing on `available: 0`)
- [x] Fractional bracket guard: `place_bracket_order` floors/raises; resubmit skips when sized < 1 whole share (the URI 0.19-share → 422 bug)
- [x] Committed-cash reserve: cash-reserve gate nets out pending buy-order notional so simultaneous brackets can't fill into margin/negative cash
- [x] Daily `weekday_fetch` job (13:00 UTC) so the data bundle is refreshed daily, not just weekly (was aging to 120h)
- [x] Analyst↔executor downtrend conflict (HCA) recorded as a near-miss instead of a silent per-cycle skip
- [x] 12 new tests (437 total passing); de-flaked the brittle qty-race-timeout test
- [ ] Follow-up: make Pass-2 selection trend-aware so it stops ranking downtrend names into the buy set (deferred — changes non-deterministic AI output)

## Phase 1: Core Infrastructure
- [x] Project structure and configuration
- [x] Config management (env vars, watchlist)
- [x] Logging system (structured JSON)
- [x] Retry/backoff utility (3 retries, exponential)
- [x] Data fetcher (FMP prices/news + SEC filings)
- [x] Weekly analyst (Claude integration)
- [x] Daily sentry (Gemini Flash integration)
- [x] Trade executor (Alpaca integration)
- [x] GitHub Actions workflows
- [x] State management (portfolio, thesis, trade log)

## Phase 1.5: Advanced Features
- [x] Technical indicators (RSI, MACD, Bollinger, ATR, SMA, volume)
- [x] Market context (SPY, QQQ, VIX, Treasury yields, sector rotation)
- [x] Two-pass weekly analysis (per-stock + portfolio ranking)
- [x] Three-layer daily sentry (market-wide + price-based + news-based)
- [x] Earnings calendar gate (5-day blackout)
- [x] Volatility-adjusted position sizing (ATR-based)
- [x] Drawdown circuit breaker (8% from peak)
- [x] Cash reserve enforcement (20% minimum)
- [x] Sector exposure limits (40% max)
- [x] Confidence threshold gate (>= 0.70)
- [x] Performance feedback loop (win rate, calibration, per-ticker stats)
- [x] Broker-native stop-losses (bracket orders)
- [x] Comprehensive documentation

## Phase 1.6: Infrastructure
- [x] Docker containerization (Dockerfile + docker-compose.yml + .dockerignore)
- [x] Server-based cron deployment documentation
- [x] Flutter desktop app project setup and foundation

## Phase 1.7: Trade Intelligence
- [x] All-gate evaluation in risk manager (no short-circuit, reports all failures)
- [x] Trade context snapshots (market regime, VIX, technicals, news at trade time)
- [x] Near-miss recording (blocked by <= 2 gates, saved to state/near_misses.json)
- [x] Watchlist write function (save_watchlist in config.py)
- [x] Enriched trade detail screen (context, gate results, risk flags)
- [x] Near misses screen + detail screen in Flutter app
- [x] Watchlist management screen in Flutter app (add/remove tickers)

## Phase 1.8: Statistics & Cost Tracking
- [x] Operational cost logger (state/costs.json with per-API-call token usage)
- [x] Claude token usage capture in weekly_analyst.py
- [x] Gemini token usage capture in daily_sentry.py
- [x] Cost model and provider in Flutter app
- [x] Statistics screen: open positions P&L (unrealized)
- [x] Statistics screen: closed trades P&L with BUY->SELL round-trip matching
- [x] Statistics screen: operational costs breakdown by service
- [x] Statistics screen: net P&L (trading P&L minus operational costs)

## Phase 1.9: Reliability & Testing
- [x] Pytest infrastructure (pyproject.toml, conftest.py, fixtures)
- [x] Unit tests for indicators: SMA, EMA, RSI, MACD, Bollinger, ATR, volume, price_vs_sma (31 tests)
- [x] Unit tests for AI output parsing: extract_json, parse_ai_json, validate_thesis/sentry/ranking (29 tests)
- [x] Unit tests for risk manager: all 6 gates individually + pre_trade_check integration (32 tests)
- [x] Mocked weekly analyst tests: analyze_stock, rank_and_select with canned Claude responses (5 tests)
- [x] Mocked daily sentry tests: check_stock with canned Gemini responses, price override (5 tests)
- [x] Executor tests: build_trade_context, handle_bullish_entry, near-miss recording (12 tests)
- [x] Bracket order resubmission (expired brackets auto-resubmitted with fresh risk checks)
- [x] Bracket resubmission tests (valid/invalid/already holding scenarios)
- [x] Settings screen in Flutter app (change data path, configurable refresh interval)
- [x] Dynamic refresh interval across all 7 providers (10s/15s/30s/60s/120s)
- [x] Dual Alpaca credentials (separate paper and live key pairs in .env)
- [x] Trading mode API endpoints (`GET /api/settings`, `PUT /api/settings/mode`)
- [x] Trading mode toggle in Flutter settings (SwitchListTile with confirmation dialog)
- [x] Backward compatibility for legacy `ALPACA_KEY`/`ALPACA_SECRET` env vars
- [x] Built-in APScheduler (all cron jobs run inside API container)
- [x] Schedule config in `data/schedule.json` (editable, version-controlled)
- [x] Scheduler API endpoints (list, trigger, enable/disable)
- [x] Scheduler screen in Flutter app (status, toggle, manual trigger)

## Phase 1.10: Position Protection & Monitoring
- [x] Trailing stop mechanism (5% trigger, 3% trail below HWM)
- [x] Thesis expiry: force-close orphaned positions with no active monitoring
- [x] Dynamic entry price adjustment on bracket resubmission (current price awareness)
- [x] Lightweight intraday price checks between sentry runs (zero LLM cost)
- [x] Gap-down protection: detect unfilled stop-limits and market-sell immediately
- [x] New CLI commands: `pricecheck`, `gapcheck`
- [x] FastAPI HTTP server for Flutter app to connect remotely
- [x] Cloudflare tunnel integration (docker-compose with cloudflared service)

## Phase 1.11: Strategy Improvements
- [x] Economic calendar awareness (FMP /economic_calendar + Gate 7 macro blackout)
- [x] Analyst ratings and price target consensus (FMP upgrades/downgrades)
- [x] Relative strength vs SPY (5d/20d/60d outperformance metric)
- [x] Insider trading data (Form 4 filings via SEC-API)
- [x] Pairwise correlation matrix (60-day rolling) + Gate 8 correlation limit
- [x] Sentiment divergence detection (prompt enrichment)
- [x] Mean reversion setup detection (RSI < 30 + 200-SMA proximity)
- [x] Earnings run-up strategy (10-15 days before earnings)
- [x] Two-tranche entry (60% at target + 40% at 1.5% discount)
- [x] Time-of-day entry optimization (shifted to 10:15 AM ET, after opening volatility)

## Phase 1.12: Flexible Holding & Backtesting
- [x] Diversified watchlist: 15 stocks across 8 sectors (tech, healthcare, finance, energy, industrial, consumer, materials, real estate)
- [x] Flexible hold horizons: short_term (1-2w), medium_term (2-6w), long_term (6w+)
- [x] Weekly review pipeline: held positions get CONTINUE/ADJUST/CLOSE review, not forced expiry
- [x] Removed 14-day hard thesis expiry — replaced with weekly review cycle
- [x] CLOSE review action triggers position exit (Claude's explicit decision)
- [x] ADJUST review action updates stop/TP levels
- [x] Backtesting engine: synthetic thesis, portfolio simulator, metrics computation
- [x] Backtest CLI: `python -m titantrade backtest [data-dir]`
- [x] Historical data downloader: `python -m titantrade download-history [data-dir]`
- [x] Backtest metrics: return, alpha vs SPY, win rate, Sharpe, Sortino, max drawdown, profit factor

## Phase 1.13: Bear Market Hedging & Execution Quality
- [x] Inverse ETF hedging: SH/PSQ/SDS analyzed in bearish/crisis regimes
- [x] Slippage model in backtester (0.15% per fill, configurable)
- [x] Slippage-aware limit exits for non-urgent ABORT signals
- [x] Limit sell function for executor (reduces market order slippage)

## Phase 1.16: Reliability & Cost Reduction (2026-04-18)
- [x] Hardened retry policy: 5 attempts, 30s cap per delay, 60s timeout, full jitter
- [x] 429 rate-limit handling with `Retry-After` header support
- [x] `max_retries` now a per-call parameter (fail-fast path available)
- [x] Replaced paid SEC-API.io with free SEC EDGAR (`sec_edgar.py`)
- [x] CIK cache at `state/cik_cache.json` (one-time ~10k entry fetch)
- [x] Removed all SEC-API references (`SECAPIConfig` class, `SEC_API_KEY` env, workflow secrets, docs)
- [x] Unit tests for retry (17 tests) and EDGAR client (19 tests)
- [x] Fixed review-mode thesis validation: held positions no longer get silently
      downgraded from BULLISH to NEUTRAL for missing `target_entry_price`
- [x] Fixed Alpaca 403 on stop placement (three-layer fix):
      idempotency check in ADJUST flow, `HTTPError` class capturing response
      bodies, and qty-race retry (code 40310000 → wait 2s and retry stop-limit)
- [x] Sentry skips tickers where `selected_for_trading=False` (no more DXCM
      ghost ABORTs, fewer wasted Gemini calls)
- [x] Sentry records fallback ratio in state; Discord alert when >30% of
      checks fall back to heuristic defaults (Gemini outage visibility)
- [x] ADJUST flow restores the old stop if the replacement fails, so a
      held position is never left without a stop-loss
- [x] Orphan-close surfaces Alpaca error codes + messages in logs with a
      "will retry on next run" note
- [x] Gemini structured output mode (`responseMimeType: application/json`
      + `responseSchema`) with thinking disabled — valid JSON guaranteed,
      ~10× fewer output tokens per sentry check
- [x] Backtest A/B comparison: `run_ab_comparison()` and
      `python -m titantrade backtest-ab [dir]` to empirically validate the
      confidence-scaling curve against the flat baseline
- [x] Flutter sentry health badge: degraded state visible on the dashboard
      when fallback_ratio > 30%; green "healthy" pill otherwise
- [x] Qty-race retry now polls `qty_available` for up to 30 s instead of
      sleeping a fixed 2 s — eliminates the ~6-hour unprotected-position
      window observed in production when Alpaca's `pending_cancel` took
      longer than expected to settle

## Phase 1.18: Strategy & operational hardening (2026-05-12)
- [x] Re-entry cooldown (72h) after ABORT — stops whipsaw cycles
- [x] Narrowed macro blackout: 24h → 6h, only high-impact events (FOMC, NFP, CPI, core PCE, GDP)
- [x] `pre_trade_check` now uses `adjusted_confidence` from Pass-2 (fixed confidence-scaling bug)
- [x] Bracket resubmission capped at 5 expired attempts per ticker (price-chase guard)
- [x] Pass 2 target count scales with regime (6/5/4/3/2/1 for strong_bullish → crisis)
- [x] Sentry price-move uses broker `avg_entry_price` for held positions (not stale thesis target)
- [x] Earnings blackout narrowed 5 → 2 calendar days
- [x] State-file archival: trade_log/near_misses auto-trim to most recent N, overflow → state/archive/
- [x] Discord alert when bot is >70% cash for 3+ days
- [x] Discord alert when a ticker round-trips 2+ times in 7 days
- [x] 24 new tests (342 total passing)

## Phase 1.17: Off-hours awareness + ABORT-noise reduction (2026-05-12)
- [x] Diagnosed live: cancel orders submitted off-hours sit in `pending_cancel`
      for 10+ minutes (sometimes hours) until next market open
- [x] New `is_market_open(cfg)` using Alpaca `/v2/clock`
- [x] New `get_order(order_id, cfg)` and `_wait_for_order_canceled()` that
      polls the specific blocking order's status (from `related_orders` in
      Alpaca's 403 body), replacing the qty_available polling that didn't work
- [x] ADJUST, orphan-close, and trailing-stop adjustments now skip during
      off-hours (old stop remains protective on the book)
- [x] Bracket math sanity check in `_handle_bullish_entry` and
      `resubmit_expired_brackets`: refuse to send invalid (stop >= entry)
      brackets to Alpaca that would only get HTTP 422 anyway
- [x] Graduated price-ABORT severity: 3-5% adverse only ABORTs with Gemini
      news confirmation; >=5% adverse always ABORTs; `price_check.py`
      (no news context) only fires on the catastrophic threshold
- [x] 14 new unit tests covering all three fixes; 318 total passing

## Phase 1.15: Capital Deployment Improvements (2026-04-05)
- [x] Confidence-proportional position sizing (linear 0.7x-1.3x scaling)
- [x] `confidence_scaled_risk()` helper in risk_manager.py
- [x] Confidence param added to `volatility_adjusted_shares()` (backward compatible)
- [x] Hedge instrument regime awareness in weekly review prompt
- [x] Inverse ETF warning injected for non-bearish regimes
- [x] Tests for confidence scaling (unit + integration, 10 new tests)
- [x] ADR documentation for both changes

## Phase 1.14: Production Hardening (2026-04-04)
- [x] Gemini truncated JSON repair in ai_parsing.py (closes unterminated strings/brackets)
- [x] Sentry prompt brevity instruction (reasoning under 3 sentences)
- [x] Stop-loss order fallback: stop-limit → plain stop on 403 rejection
- [x] Sector cache initialization in executor (load_stock_sectors at startup)
- [x] SPY change fallback: compute from price/previousClose when changesPercentage missing
- [x] Live portfolio API endpoint (fetches from Alpaca instead of stale static file)

## Phase 2: Testing & Validation
- [x] Unit tests for indicators (known-good RSI/MACD values)
- [x] Unit tests for risk manager gates
- [ ] Integration tests with Alpaca paper trading
- [x] Mock API responses for offline testing
- [x] Validate AI output schema parsing (malformed JSON handling)
- [ ] End-to-end dry run with paper account
- [x] Stress test circuit breaker logic
- [ ] Test earnings blackout with real FMP data

## Phase 3: Monitoring & Alerts
- [x] Discord webhook notifications on job completion/failure
- [x] Daily portfolio summary notifications (weekday 21:00 UTC)
- [x] Error alerting (failed runs notify via Discord)
- [ ] Performance tracking dashboard (Streamlit or Grafana)
- [ ] Weekly P&L report generation

## Phase 4: Enhancements
- [ ] Supabase migration for cloud state (multi-device access)
- [ ] Backtesting engine against historical data
- [ ] Intraday price alerts via WebSocket (supplement cron)
- [ ] Options strategy module
- [ ] Tax-loss harvesting suggestions
- [ ] Portfolio rebalancing automation
- [ ] Multi-account support

## Phase 5: Desktop App (Trade Tracker)
- [x] Flutter project structure and routing (go_router)
- [x] Data models matching TitanTrade JSON schemas
- [x] File-reading providers with 30-second polling
- [x] Setup screen (data path configuration with file_picker)
- [x] Dashboard screen (portfolio overview, positions, recent trades, sentry signals)
- [x] Trade history screen with action filter
- [x] Trade detail screen (thesis + sentry context correlation)
- [x] Active theses screen (card grid with confidence bars)
- [x] Thesis detail screen (full reasoning, price levels, breach condition)
- [x] Dark theme and financial styling
- [ ] Portfolio value chart (fl_chart line chart over time)
- [ ] P&L bar chart per trade
- [x] Settings screen (change data path, refresh interval)
- [ ] Log viewer screen (raw structured JSON logs)
- [ ] Export trade history to CSV

## Known Limitations
- GitHub Actions cron has 5-15 min scheduling variance (mitigated by server deployment)
- Flutter app reads state files read-only except for watchlist management
- Flutter app requires local filesystem access (not a web app)
- FMP free tier rate limits (250/day) tight with market context + 10 stocks
- Alpaca bracket orders are day-only (not GTC), need daily resubmission
- SEC-API real-time tier is paid ($49/month)
- No intraday price monitoring between sentry runs

## Technical Debt
- None yet (greenfield project)
