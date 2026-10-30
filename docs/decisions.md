# Important Decisions Log

## Decision 086: Trend and carry over a century — the premium is real and old, it pays in the same slow bears the book's insurance pays in, and a sleeve of it buys Sharpe and drawdown with return; no sleeve, B3 closed (roadmap B3, operator: "let's do the century trend", 2026-10-30)
**Date**: 2026-10-30
**Why**: trend following is the one published family with a century behind it that the book has never held, and its claim — "crisis alpha", money made in the bears — is exactly what the book's two switches are for. Futures are not on Alpaca, so the test was always going to be knowledge first: on AQR's published factor series, judged on the operator's own eras, before any instrument. Done the Decision 062 way: hypotheses T1–T5 and the drop rule in `scripts/param_search/trend.py`, **committed before the first run** (`1809250`); `datasets.aqr_monthly` is the loader. Data: AQR's Time Series Momentum factor (TSMOM and its four legs, monthly, 1985-01 → 2026-05 — the real trend series) and the Century of Factor Premia (1926-07 → 2026-02: "All Macro Momentum", 12-1 momentum *within* the macro asset classes, the century-long cousin of trend, cross-sectional not time-series; "All Macro Carry"; the multi-style composite). All long-short, gross of costs and fees; each sleeve candidate rescaled to a constant 10 % volatility (an investable managed-futures fund's) and shown gross and net of 2 pp/yr. The book = `books.century()` / `books.decade()` with the exposure rules applied day by day, compounded to months; only the sleeve blend is monthly. One correction before any number was read: the first run compounded the daily exposure factors across a month (a de-risked month went to zero exposure, the book read +9.5 and −13 %); the monthly book is now compounded from the daily path and reproduces the known numbers (+3.9 vs +3.6 daily-scored, DD −58 %, Sharpe 0.84). **Nothing live changes.**

**T1 — the premia alone** (gross, as published; CAGR; halves; eras; drawdown; Sharpe; correlation with the market):

| series | CAGR · Sharpe | halves | eras | DD | corr. market |
|---|---|---|---|---|---|
| **TSMOM, all assets, 1985 →** | **+12.1 % · 0.98** (vol 12.5 %) | +19.0 / +5.6 | decades +18.0 / +20.4 / +10.1 / **+1.0** (2015–24, the drought) / +12.0 | −27.9 | −0.07 |
| its legs: commodities · equity indices · fixed income · currencies | 0.65 · 0.55 · 0.61 · 0.55 | all weaker in the second half | each negative in one decade | −46 … −81 | −0.12 … +0.23 |
| the market, same months | +12.0 % · 0.81 | +12.5 / +11.4 | | −50.2 | |
| **All Macro Momentum, 1927 →** (the century cousin) | **+1.9 % · 0.39** (vol 5.3 %) | +1.8 / +2.0 | **+0.1** / +3.4 / +3.5 / **+0.6** | −28.9 | −0.15 |
| All Macro Carry, 1927 → | +2.4 % · 0.56 | +2.5 / +2.4 | +0.4 / +4.4 / +3.4 / +1.4 | −32.4 | +0.12 |
| All Macro Multi-style · All asset classes Momentum | 0.87 · 0.61 | both halves + | all four eras + | −14 · −34 | −0.05 · −0.26 |
| the market, same months | +10.1 % · 0.62 | +7.4 / +12.7 | +5.3 / +9.4 / +17.4 / +8.3 | −83.9 | |

**T2 — the episodes** (compounded over the window; the factors at 10 % volatility; the book = the century book):

| | 1929–32 | 1973–74 | 1987 | 2000–02 | 2008 | 2009 rebound | 2020 | 2022 | 2023 rebound |
|---|---|---|---|---|---|---|---|---|---|
| the market | −84 | −46 | −30 | −45 | −50 | +56 | −20 | −25 | +27 |
| the book | −57 | −25 | −20 | −26 | −34 | +39 | −9 | −16 | +17 |
| macro momentum (10 % vol) | **−13** | **+18** | −10 | **+6** | **+7** | −12 | +1 | **+12** | +1 |
| macro carry (10 % vol) | **+57** | **+34** | −1 | **+34** | **−10** | +17 | **−9** | −2 | +11 |
| TSMOM (10 % vol), 1985 → | — | — | −2 | **+50** | **+24** | −12 | +8 | **+27** | −7 |

Correlations (monthly): macro momentum vs the market −0.15, **vs the book's active return +0.19**; TSMOM vs the market −0.07, **vs the book's active return +0.30**; carry vs the market +0.12, vs active −0.06. In the market's 122 worst months (< −5 %, mean −8.9 %) the book made −6.4 %, macro momentum +0.5 %, carry +0.1 %; TSMOM in its own 45 worst market months +2.2 %.

**T3 / T4 — the sleeve bar** (return better in both halves and every era, Sharpe no lower; "gain" = excess vs the book's; 10 % and 20 % sleeves taken proportionally, from the momentum sleeve or from the dip sleeve, outside the exposure rules; gross / net):

| book · sleeve | the book | best sleeve variant (gross) | its gain · Sharpe · DD | net 2 pp | verdict |
|---|---|---|---|---|---|
| **century 1927 →, macro momentum** | +3.88 (+5.5 / +2.3), DD −58.1, Sh 0.84, eras +5.5 / +5.6 / +3.2 / +1.5 | 10 % from the dip sleeve: +3.22 (+5.0 / +1.5), eras +4.7 / +5.3 / +2.3 / +0.8 | **−0.66** · 0.87 · −53.6 | −0.89 | fails — every variant −0.7 … −3.6 |
| century 1927 →, macro carry | same | 10 % from the dip sleeve: +3.38 | **−0.50** · 0.88 · −51.7 | −0.72 | fails — every variant −0.5 … −2.3; 20 % buys 14 points of drawdown for −1.0 |
| **1985 →, TSMOM** (the real trend series) | +1.90 (+4.1 / −0.2), DD −33.8, Sh 0.88, decades +3.0 / +4.6 / +0.3 / −0.2 / +2.8 | 10 % / 20 % from the dip sleeve: +1.95 / +1.96 | **+0.05 / +0.06** · 0.94 / 1.00 · −29.0 / −23.9 | −0.17 / −0.39 | fails — the return is a wash gross, lower net, and **2005–14 is −1.2 vs −0.2** (every other variant negative) |
| ETF decade 2017 →, TSMOM | +1.37 (+0.3 / +2.5), DD −15.8, Sh 1.17 | 10 % from the dip sleeve: +0.13 (−1.8 / +2.2) | **−1.24** · 1.18 · −13.8 | −1.47 | fails — trend's drought decade; every variant −1.2 … −3.5 |

**Verdict on the pre-registered rules.** **T1 holds, with the sizes off in both directions**: the real trend series is *stronger* than written (Sharpe 0.98 gross against 0.5 … 0.9; positive in both halves and in all five decades, the 2015–24 drought at +1.0 %), the century cousin *weaker* (Sharpe 0.39 against 0.4 … 0.7; positive in all four quarter-centuries but by a hair in the first and the last). **T2 holds in its main claim and fails in one**: trend made money in the slow bears (2000–02 +50, 2008 +24, 2022 +27 at 10 % volatility; 1973–74 +18 on the century cousin), lost in the rebounds (2009 −12, 2023 −7) and was flat to mildly positive in the fast crashes — but the century cousin *lost* 13 points in 1929–32, and the correlation with the book's active return is **+0.19 (century) and +0.30 (TSMOM)**, not the ±0.10 written: trend pays in the same months the book's insurance pays in. **T3 fails** in all three constructions, as written: on the century a trend sleeve costs 0.7 … 3.6 pp/yr for 4 … 9 points of drawdown and +0.02 … +0.06 of Sharpe; on 1985 → the two best cells are a wash gross (+0.05 / +0.06) with the Sharpe up to 1.00 and the drawdown 10 points shallower, and they still fail — the 2005–14 decade is a point worse and the net lines are negative; on the ETF decade every variant loses 1.2 … 3.5 pp/yr. **T4 fails** as written, and carry's crisis record was not what was written: the macro carry composite *hedged* the slow bears before 2008 (1929–32 +57, 1973–74 +34, 2000–02 +34) and crashed in 2008 (−10) and 2020 (−9); as a sleeve it buys the most drawdown of anything tested (−58 → −45 at 20 %) for a point of return. **T5 not reached.**

**Decision.** Nothing changes; B3 is closed as knowledge. Three things kept: (1) **trend is the same bet from another market** — its crisis alpha lands in the slow bears where the book's insurance already steps aside, so its correlation with the book's *active* return is +0.2 … +0.3 and its diversification is smaller than its −0.07 correlation with the market suggests; (2) a trend sleeve is a Sharpe tool, not a return tool — the fourth diversifier to say so after options (074), quality (075) and gold (079), and the one that comes closest (a wash gross on 1985 →); the book cannot lever, so Sharpe bought with return is not wanted; (3) the instrument question is moot (DBMF / KMLM would add a fee to a sleeve that already fails), and the century cousin is weaker than the futures record — a hundred years of cross-sectional macro momentum is Sharpe 0.4, not 1. **Next: the checkup ≈ 2026-11-12; the Tiingo key for B11 when the operator signs up.**

**Scripts / docs**: `scripts/param_search/trend.py` (pre-registration `1809250`, then the monthly-book correction and the run), `datasets.aqr_monthly`, the harness README row; roadmap B3 ✅ closed, Track D and C3 rows; todo Phase 2.26; one insight; handover note.

## Decision 085: The harness tidy-up — one `books.py` builds the decade and the century; the numbers must not move (roadmap Track F, operator: "do the tidy up", 2026-10-30) — **done: seven runs byte-identical, loaders equal**
**Date**: 2026-10-30
**Why**: the research harness grew one script per Decision over four days, and the recommended book's inputs — the sector dip sleeve on `fastbt`, SPMO, SPY, the two-signal insurance flags, the shock flags, and their century twins on Kenneth French's industries and momentum decile — were rebuilt inline each time. `carry.sets()` became the de-facto shared builder (eighteen scripts import it), but `master.decade()` / `century()` / `finalists()`, `rotation.decade()` / `century()`, `shorts.decade_base()` / `century_base()` and `regimes.main()` / `shock_grid()` still carry their own copies of the same twenty lines; `search.py` copies `datasets.py`'s loaders and `analyze1_lib.py`'s grid; `analyze1.py` is `analyze1_lib.py` plus a main. For the next agent, not for the numbers — which is exactly the risk: a refactor of research code is correct only if every number it ever printed is unchanged.

**What moves where** (written before the change): a new `books.py` holds the recommended-book builders — `LIVE`, the signal helpers `prev` / `sma_above` / `shock_flags`, `decade()` (the sector sleeve, the curated sleeve and the momentum ETFs on request, SPY, the insurance inputs, the dates) and `century()` (the industry sleeve, the top decile, the market), `sets()`, `exposure()`, `rf_daily()` / `align_rf()`. `carry.py` and `master.py` keep every public name as a re-export, so the eighteen `carry.sets()` importers and every `master.score` / `master.shock_flags` user are untouched. The four duplicating builders above are rewired to `books`; `search.py` imports its loaders from `datasets.py` and its grid from `analyze1_lib.py`; `analyze1.py` imports its functions from `analyze1_lib.py`. The other scripts that rebuild a window inline for their own purposes (the Decision 066 / 067 artefacts and the scripts that already use `carry.sets()` for the book) stay as they ran. Nothing in `src/` changes; the harness never reaches production, so there is no deploy.

**Acceptance, pre-registered**: the printed output of `carry.py`, `validate.py --two-sleeve`, `master.py --finalists`, `shorts.py`, `rotation.py`, `regimes.py` and `regimes.py --grid` is **byte-identical** before and after (captured before the first edit; the timing line excluded); `search.py`'s loaders for the two datasets present on this machine (A and D) yield arrays equal to `datasets.load`'s (B and C have no local files — the Yahoo wall). **Drop rule**: any difference means that script is left exactly as it was and the difference is recorded here; the tidy-up never changes a number to make a diff go away.

**Result: every number unchanged.** The seven runs are byte-identical before and after (`carry.py` 21 lines, `validate.py --two-sleeve` 17, `master.py --finalists` 32, `shorts.py` 92, `rotation.py` 98, `regimes.py` 23, `regimes.py --grid` 174 — the timing lines aside); `search.py`'s loaders for A and D produce the same Markets as `datasets.load` (2,709 sessions, the same arrays to the bit, NaNs included), the same `START` / `SPLIT`, and the same 6,000 grid points; `carry.sets is books.sets` and `master.shock_flags is books.shock_flags` (the re-exports are the same objects, not copies). Nothing had to be left as it was. The scripts are shorter by about 110 lines; `books.py` is 95. Two run-mode details found on the way: a script that imports a sibling needs the `sys.path` line to run under `-I` (added to `analyze1.py` and `search.py`), and the stage-1 result files are not on the research machine (the Yahoo wall; `analyze1.py` was checked by import, not by a run). Nothing in `src/` changed; no deploy.

**Scripts / docs**: `scripts/param_search/books.py` (new), `carry.py`, `master.py`, `rotation.py`, `shorts.py`, `regimes.py`, `search.py`, `analyze1.py`; the README rows; roadmap Track F ✅; todo Phase 2.25.

## Decision 084: The chaos drill — one executor run against a broker that lies, refuses and vanishes; nothing bare, nothing doubled (roadmap Track F, operator's go, 2026-10-30) — **run: seven guards hold, one real hole (the core legs trade on a phantom account value), one small one (a target exit on an unconfirmed mark); both fixed the same evening on the operator's go**
**Date**: 2026-10-30
**Why**: every guard in the executor was written after a production incident — the CRWD split that sold a healthy position at an artificial bottom and then showed a phantom $22,828 account (Decision 054), the FCX gap-down sell rejected with 40310000 because the cancelled stop still held the shares (Decisions 037 / 042 / 063), the bracket legs that die at the close (Decision 060), the stop that never got placed. Each guard has its own unit test; no test has ever fed the executor several anomalies in one run and checked the one property that matters for real money: **after the run every held dip position has exactly one stop at the plan's level, no order was placed on bad data, and nothing was bought or sold twice.** Written before the drill ran.

**The drill** (`tests/test_chaos.py`): a stateful fake broker — account, positions, resting orders with Alpaca's share accounting (a resting sell order holds its shares; a second sell on held shares is refused with 40310000; a cancel releases them) — patched into every module that imports a broker function by name (`executor`, `protection`, `entries`, `core_allocation`), the live quote patched alongside, and the HTTP layer patched to count any call that escapes the fake. One `execute_trades` run per scenario on a book like today's (two dip positions with stops, SPMO at 60 %, SPY, 5 % cash, a plan with their HOLD items and one NEW item), then the invariants.

**Invariants, checked after every scenario:**
- **I1 nothing bare** — every non-core position of a whole share or more has a resting sell stop at the plan item's level.
- **I2 nothing doubled** — exactly one stop per position, no buy order for a name already held or already pending, no second sale of a sold position.
- **I3 no order on bad data** — while the account value is more than 50 % off the recorded peak (either way), no core rebalance and no entry; while a position's mark disagrees with the live quote, no sale driven by the mark.
- **I4 only prescribed actions** — every trade-log row's trigger is one of entry / target / holding_limit / orphan_close / gap_down_protection / core_rebalance; cash never below zero.
- **I5 the peak file never learns a phantom** — unchanged after a suspect value.
- **I6 no call escapes the fake** — zero HTTP attempts.

**Scenarios and what I expect, from reading the code before running it:**
| # | anomaly | expected |
|---|---|---|
| S1 | the account reports equity 79 % below the peak (the July 2026 phantom) | entries blocked and the peak untouched ✓ (the Decision 054 guard); **the core legs are expected to FAIL I3**: `manage_core_position` reads the phantom value and would sell SPY / SPMO toward a collapsed target — no suspect-value guard sits on that path |
| S2 | the account reports equity 60 % *above* the peak | the peak refuses the spike ✓; **entries and core buys are expected to FAIL I3**: the breaker only trips on the downside, so a slot is sized on the phantom equity (capped by real cash) and the core legs buy toward a phantom target with real cash |
| S3 | a position's mark is a quarter of the live quote (the CRWD split mark) | gap-down protection skips on the live-quote cross-check ✓, no target exit ✓, the stop stays ✓ |
| S3b | a position's mark is 30 % *above* the live quote (a reverse-split artefact) | **expected to fire the target exit on the mark alone** (`_manage_held` reads `unrealized_plpc`, no quote cross-check) — a sale on bad data at the real price; I3 fails; a finding to decide, not an obvious guard |
| S4 | the mark and the quote both 71 % below the stop, with a split announcement / without | skip and alert ✓ / sell by gap-down protection ✓ (by design) |
| S5 | a held position's GTC stop has vanished (the 90-day expiry, a corporate action) | one stop re-placed at the plan level ✓; with a stop present none added ✓ |
| S6 | a holding-limit exit while the stop holds the shares; the broker refuses the first market sell even after the cancel settled | cancel → settle → sell refused → the stop restored ✓ (I1 holds, the position stays for the next run) |
| S7 | the broker refuses to cancel the stop | no sale (the shares stay held), the one stop stands ✓ — with a misleading "CRITICAL naked" log line expected |
| S8 | every broker call fails (network) | the run aborts or completes with zero orders ✓ |
| S9 | the plan's NEW item is already pending / already held | skipped both times ✓ |

**Drop rule**: a scenario that violates an invariant is **a finding, not a failed task** — the drill is the deliverable. Each finding is recorded here with the exact path; the scenario stays in the suite as a *strict expected failure* (so the suite is green and the gap is visible) until a fix lands **on the operator's go**; a fix is a guard that does less on bad data, never a relaxation; the expected failures above (S1 core legs, S2) would be closed by one guard at the top of `execute_trades` — on a suspect account value do nothing this run but stop coverage, and alert. S3b is a design question for the operator (confirm a target exit with the live quote, as gap-down already does). Nothing live changes from the drill itself; a fix is a deploy with its own go.

**Results** (`tests/test_chaos.py`, 12 tests: 9 pass, 3 strict expected failures; the suite 289, ruff clean). The book of the drill: DXCM 100 sh (+5 %) and URI 10 sh (+10 %) with their stops at 70.40 / 880, SPMO 400 sh at 54.8 % of equity, SPY 20 sh, cash 15.8 %, the peak file at $100,000, a plan with the two HOLD items and one NEW item (XLC). Baseline: one bracket for XLC and nothing else.

| # | result | detail |
|---|---|---|
| S1 phantom equity −79 % | entries blocked ✓, the peak untouched ✓; **core legs FAIL I3 — confirmed** | the run sold **all 20 SPY and 312 of 400 SPMO at the market** toward targets computed on $21,000. On the live book that is ≈ $43,000 of ETFs sold on a data glitch, bought back at the next run with the value corrected — two sets of costs and the gap in between |
| S2 phantom equity +60 % | the peak refused the spike ✓; **core buys FAIL I3 — confirmed** | SPY +15 and SPMO +2 bought with real cash toward targets computed on $160,000; the entry was stopped only by the dust gate (the 5 % reserve on a phantom $160,000 ate the cash), not by a suspect-value check — the breaker trips on the downside alone |
| S3 phantom low mark | ✓ | gap-down protection skipped on the live-quote cross-check, no target exit, the stop stayed |
| S3b phantom high mark | **FAIL I3 — confirmed** | DXCM sold as a "target" exit on a +37 % mark while the quote was unchanged: `_manage_held` reads `unrealized_plpc` with no quote cross-check (the sale fills at the real price — an early exit on bad data, not a loss) |
| S4 split-like gap | ✓ / ✓ | with the announcement: skipped and alerted, the stop kept; without: sold by gap-down protection |
| S5 vanished stop | ✓ | exactly one stop re-placed, at the plan's 70.40; URI's existing stop left alone |
| S6 refused sell after a settled cancel | ✓ | the stop restored at 880, the position kept for the next run, no SELL recorded |
| S7 refused cancel | ✓ | nothing sold, the one stop stands (the "CRITICAL naked" log line is misleading — the position is covered; cosmetic) |
| S8 dead network | ✓ | the run raises before any order (the scheduler marks the job failed — loud and idle, the right shape) |
| S9 pending / held name | ✓ / ✓ | not bought again; a held name with a NEW item is neither bought nor orphaned |

**Verdict.** The guards written after each incident hold where they were written: the split mark, the deep gap, the vanished stop, the 40310000 race, the refused cancel, the dead network, the duplicate entry. **The one real hole is the account value**: the suspect-value guard protects the entry gate and the peak file, and nothing else reads it — the core legs (now 60 % of the book plus the SPY residual) rebalance toward targets computed on whatever number the broker reports, in both directions. July 2026's phantom $22,828 happened before the core legs existed in their present size; under design 070 it would move about $43,000. The second, smaller finding is the target exit on an unconfirmed mark.

**Fixes built the same evening (operator: "Go, fix both")** — both guards that do *less* on bad data: (1) `risk_manager.account_value_suspect` (the breaker's ±50 % rule against the recorded peak, now in **both** directions — the breaker itself trips on an upside phantom too) is read once by `execute_trades` right after the account; when suspect the run logs an error, sends the rate-limited suspect-value alert, **skips the core legs, the entries, the target / holding exits and the stuck-in-cash alert, and still runs stop coverage** (plan levels, no account value): "on a suspect account value the run only keeps the stops". (2) `_manage_held` confirms a target exit with the live quote before selling: when the quote's gain from the entry is below the target the mark is not believed and the position is kept with a warning; a missing quote leaves the mark in charge, as before. Twenty lines; the three expected-failure markers came off and the scenarios pass (S1 and S2: no order at all, the peak untouched; S3b: not sold); the drill's executor patch list gained the quote (the drill itself caught the new call). 289 tests, ruff clean. **Deployed 2026-10-30 16:31 UTC** (commit `a3b17bd` on the server; no job running, the next at 19:30 UTC): both images rebuilt, the API restarted, cache pruned (disk 44 %), health ok, both images import `account_value_suspect`, 0 errors after the restart. No config change, no window restart; nothing about the book changes until the broker next reports a phantom — then the run keeps the stops and says so.

**Scripts / docs**: `tests/test_chaos.py` (the fake broker, nine scenarios, the invariants); `docs/features.md` (the test table), `CLAUDE.md` (the count); roadmap Track F ✅ with the findings; todo Phase 2.24.

## Decision 083: A plain-language "how to read a checkup" page for the operator (roadmap Track F, operator: "let's do the next task", 2026-10-30)
**Date**: 2026-10-30
**What**: `docs/how_to_read_a_checkup.md` — one page, everyday words, almost no numbers: the four questions a checkup answers in order (is the machine running; is the book what the rules say; did it trade only as prescribed; how is it doing against the index — reported, not judged), a table per section with "what the line means / normal / a problem", the two switches explained from their printed inputs, the prescribed reasons for every kind of trade, the benchmark line and why its band stays wide for years, the fill ledger and the shadow comparison, the go/stop rule as the only thing that ever changes anything, the expectation to hold the book against (Decision 081's restated numbers and the rebound-year cost), and a yes/no checklist at the end. Linked from `CLAUDE.md`, the deployment guide's checkup routine and the handover (the checkup is to be written so it matches the page). Nothing else changes; docs only, no deploy.

## Decision 082: The monthly curator retired — the last scheduled LLM call switched off; the curator ledger (roadmap A5) pre-registered and built the same evening, then removed unused (operator: "Retire it", 2026-10-30)
**Date**: 2026-10-30
**Why**: the one LLM call left places no orders: once a month Claude proposes up to two removals and two additions for the hand-picked list (the `shadow_watchlist` since Decision 070 — tracked, curated, never traded). Whether that call earns its keep is unmeasured. The weekly analyst it replaced had no ranking skill at its horizon (Decision 060, Evidence 2: Spearman −0.05 between confidence and the next week's return; the selected names lagged the left-out ones), and nothing known at entry predicted a trade over a century (Decision 068 addendum). The first proposal on the shadow list lands Sunday 2026-11-01; a ledger that starts with row one answers the question over the years without reconstruction. Built like the fill ledger (Decision 069): one row per proposal, outcomes filled in by the daily summary as the horizons pass, rows never edited, served by the API.

**What is measured** (written before the build): for each proposal, the total return of every proposed addition and removal from the first close after the proposal over 21 / 63 / 126 / 252 sessions, beside the equal-weight return of the list as reviewed and SPY's over the same sessions. Skill shows as additions above the list and removals below it (an addition is a claim that the name beats the list; a removal that it lags). An empty proposal is a row too (the curator declined). Horizon returns come from SIP daily bars at the session the horizon falls on; a name without bars (delisted, renamed) stays `null`.

**Pre-registered expectation and rule:**
- **H1 (the prior: no skill)** — over the first 12 proposals the median of "addition minus the list" and of "the list minus the removal" at 63 and 126 sessions sits within ±3 pp, and the share of additions beating the list is inside the coin-flip band (6 ± 3 of 12 at 126 sessions).
- **The verdict rule** — no reading under 12 proposals (a year; one or two names a month is noise), a first reading at 12 with the binomial band on the hit rate, a verdict at 24. Nothing live changes in either direction before that: a shown skill never moves the dip sleeve to single names (Decision 070 — the sector floor is the universe; any single-name list loses with the rule) and would at most keep the curator on the shadow list; no skill retires the monthly call or leaves it as the cheap helper for the operator's own list — the operator's call then.
- **The placebo at the verdict** — the same number of names drawn at random from the point-in-time S&P 500 on the same dates (the harness, `screens.load_universe`), not live code.
- **Drop rule** — informational: the ledger records; the Decision records the first reading at 12 proposals, whatever it says.

**What happened instead.** The ledger was built as pre-registered (`curator_ledger.py`, the hook in `run_universe_review`, the daily-summary step, `GET /api/curator-ledger`, five tests — commit `451f104`), and the report that offered to deploy it before Sunday's first proposal prompted the operator's question: "why do we still have AI recommendations? I thought we got rid of that." The honest answer: trading has been fully mechanical since Decision 061 — nothing a model says can reach an order — and the one call left, a monthly advisory proposal for the hand-picked list plus a written review of the month, survived Decision 070 by inertia: it was kept in 061 as the one place a model's reading of public text might still help (choosing names at the slowest horizon), and when 070 stopped trading those names it was pointed at the shadow list instead of being removed. Offered the choice — keep it a year and let the ledger judge it, or retire it now — the operator chose **retire**.

**Decision.** `monthly_curate` is disabled in `data/schedule.json` (the definition stays, `enabled: false`, so one toggle brings it back); no LLM runs on the schedule any more. The ledger is removed again (the code of `451f104` reverted — a measurement of a call that no longer happens is dead weight, Decision 063's lesson) and its pre-registration above stands as the record of what would have been measured. `curator.py` stays as the manual `curate` command (an opinion on the shadow list on demand, cost-logged, advisory) and `CLAUDE_KEY` stays required by `config.py` — a later cleanup if the command is never used. The shadow list is now static unless the operator edits it by hand; roadmap A4 (the shadow list's verdict) is unchanged — it measures the list, not the proposals. The Claude spend goes to zero. **Nothing about the book changes**: no parameter, no watchlist, no order; the schedule change is a config change deployed on this same go — **2026-10-30 16:05 UTC** (commit `0bae916` on the server): the scheduler reads the file at start, so the API was restarted with no job running (the next at 19:30 UTC), both images rebuilt, the CLI image bakes the new `data/`; after the restart `/api/scheduler` lists `monthly_curate` with no next run and the other six jobs unchanged, health ok, 0 errors.

**Scripts / docs**: `data/schedule.json`; the ledger files removed; `CLAUDE.md` (the one-LLM-call line, the `curate` command, the Curator bullet), `docs/architecture.md` (the diagram, "The LLM's place"), `docs/features.md` (the automation table), `docs/agent_instructions.md` (retired note), `docs/security.md`, `TitanTrade/docs/deployment.md` and `architecture.md` (the schedule), roadmap A5 🚫 and C4, todo Phase 2.22 and the Phase 2.9 verify item (the Nov 1 proposal no longer comes).

## Decision 081: One engine for research and live — the two-sleeve book in the package backtester (roadmap Track F, first row; operator's go, 2026-10-30) — **pre-registered, build in progress**
**Date**: 2026-10-30
**Why**: the live book has been a two-sleeve book since Decision 068 (SPMO at 60 % of the investable book, 10 % dip slots, the shock trigger, exposure = min of the two rules), but `backtest/mechanical.py` still simulates Decision 061's dip-only book at 25 % slots with the insurance alone, and every expected number (decade +1.4 vs SPY, century +3.6, DD ≈ −20 %) came from the research harness's blend (`master.book` / `carry.sets()`): a constant 40 / 60 mix of two daily-return series, rebalanced every day at no cost, with de-risked capital at 0. "Backtest what trades, trade what you backtested" (Decision 061's lesson) is therefore broken for the sleeve, the checkup's `backtest-mech --shadow` compares a dip-only book with a book that holds 60 % SPMO, and the fill ledger's "price the backtest would have paid" refers to a book nobody trades. The six gaps are listed in `docs/handover.md` section 8 (no momentum leg; slot sized on equity not the sleeve; no shock trigger and no min(); no cash leg; `download-history` does not fetch SPMO; the research side blends rather than trades). The build mirrors the live arithmetic of `mechanical.py` / `executor.py` / `core_allocation.py` without importing `Config` into the engine; `momentum_weight` 0 must leave the dip-only book untouched.

**Pre-registered, before the engine ran** (the blend's decade reference is Decision 068's: +1.36 vs SPY, IS +0.27 / OOS +2.46 at 2022-01-01, DD −20.0 vs −33.8, Sharpe 1.10, worst year −11.3, rolling 3-year windows ahead 59 %):
- **H1** the path-exact two-sleeve book on the 11 sector ETFs, 2017-01-03 → 2026-10-12, live parameters, lands **within ±0.5 pp/yr of +1.4**; the point estimate is *below* the blend, +0.9 … +1.3, for two named reasons: live, the 5 % reserve sits on the whole book (the blend's dip sleeve carries it on 40 % of the book, so the blend is ≈ 3 % more invested ≈ +0.4 pp/yr in a 15 %/yr market); and the 5 % band lets the SPMO share drift instead of being reset daily (slightly positive in a decade SPMO won, a wash otherwise).
- **H2** both halves keep the blend's sign; the first half (+0.3 in the blend) is the one that could round to zero.
- **H3** the worst drawdown is within 3 points of −20 %; the named reason it could be deeper: live, held dip positions are **not** scaled by the exposure rules (they keep their exits, only the core legs shrink), while the blend scales the whole dip sleeve by e.
- **H4** the dip-only book (`momentum_weight` 0) stays trade-for-trade and equity-to-1e-8 equal to `fastbt` on `validate.py`'s three parameter sets — the change must not move the Decision 062 floor.
- **H5** the two-sleeve engine's trade count and exit mix equal the dip-only sleeve's on the same data (same signals; a difference is the funding path, not the rule).
- Other named differences, each expected to move the number by ≤ 0.2: the blend reads the insurance and the shock one session late (`prev()`), the engine acts at the same close — as it always has for the insurance, kept for `fastbt` equality; the shock pauses entries live and in the engine, not in the blend; neither charges the core rebalances (the live book pays the spread).

**Drop rule**: a gap wider than ±0.5, a half flipping sign, or a drawdown more than 3 points deeper is **a finding, not a failure** — the engine is the deliverable. In that case the expectation stated in `docs/roadmap.md`, `CLAUDE.md` and Decision 068 is restated from the path-exact number, with the gap decomposed by diagnostic engine runs (the band → 0 = daily rebalancing; the reserve → 2 % ≈ the blend's; the shock trigger off). Nothing live changes in any case: the deploy of the CLI image is a separate go, there is no config change, `design` stays 070 and no window restarts.

**Built** (same day): `backtest/mechanical.py` now trades the live book — `momentum_bars` / `cash_bars` beside `spy_bars`; `momentum_weight` (0 = the dip-only book, every old test and `validate.py` untouched), the shock trigger (`shock_drop_pct` 0 = off) read from the last 31 closes like the plan, exposure = min(); the slot = `slot_pct × (1 − momentum_weight)` of equity (`TradingSettings.overlay_slot_pct`); fills out of SPY then the cash above the reserve (the executor's gate sizes down); every core leg rebalanced only outside the band and only with the cash above the reserve, in the executor's order (SPY, the momentum leg, the cash leg first when it shrinks and last when it grows); entries paused while either rule is on; held positions keep their exits. One deliberate non-mirror: an exit's proceeds return to SPY rather than to cash — the executor's sell-to-cash plus the same-run SPY buy-back amounts to the same thing to within the reserve's drift since the last rebalance (a slot is twice the band), and routing through SPY keeps the dip-only book trade-for-trade equal to `fastbt` (the first build routed to cash and moved the Decision 062 floor by 0.6 % of equity over eight years through the reserve top-ups, so it was reverted). Reports: exits, average and minimum exposure, risk-off and shock days, the average momentum share, core-leg trade counts; `--shadow` runs both lists under the book and each as the dip sleeve alone (the old `main` popped the sector ETFs out of the name list, so under design 070 it backtested the live list with no names — fixed); `download-history` fetches the momentum and cash tickers; `validate.py --two-sleeve` prints the table below. 277 tests (`tests/test_backtest_two_sleeve.py`, five), ruff clean.

**The gap table** (`validate.py --two-sleeve`; the 11 sector ETFs 2017-01-03 → 2026-10-12, 2,457 sessions, split 2022-01-01, live parameters, vs SPY; the blend = `carry.sets()` + `master.book`, the Decision 068 number; core trades = rebalances of the SPY / momentum leg over the decade):

| line | excess | IS / OOS | DD · Sharpe | worst yr · roll3 | trades (tp / stop / time) | SPMO share · risk-off · shock | core trades |
|---|---|---|---|---|---|---|---|
| **blend** (daily 40 / 60, free, signals one session late) | **+1.36** | +0.27 / +2.46 | −20.0 · 1.10 | −11.3 · 59 % | 61 (7 / 6 / 48) in its dip sleeve | 60 % · 13.2 % · 9.9 % | daily |
| **engine, path-exact, live parameters** | **+1.03** | **−0.27 / +2.34** | **−19.3 · 1.12** | −11.5 · 52 % | **61 (7 / 7 / 47)** | 53 % · 13.1 % · 9.9 % | 52 / 57 |
| … band 0 (every leg rebalanced daily) | +1.09 | −0.04 / +2.23 | −19.5 · 1.12 | −11.5 · 56 % | 61 (7 / 7 / 47) | 53 % | 1,918 / 2,455 |
| … reserve 2 % (≈ the blend's: 5 % of the 40 % sleeve) | +1.48 | +0.19 / +2.79 | −19.7 · 1.12 | −11.0 · 63 % | 61 (7 / 7 / 47) | 55 % | 58 / 57 |
| … band 0 and reserve 2 % | +1.56 | +0.50 / +2.63 | −20.0 · 1.12 | −11.0 · 67 % | 61 (7 / 7 / 47) | 54 % | 1,985 / 2,455 |
| … shock trigger off | +0.92 | −0.33 / +2.19 | **−23.3** · 1.09 | −11.5 · 48 % | 61 (7 / 6 / 48) | 54 % · 13.1 % · 0 | 59 / 63 |
| … insurance off (scale 1) | +2.43 | +0.99 / +3.87 | −19.3 · 1.14 | −8.8 · 93 % | 61 (7 / 7 / 47) | 55 % | 20 / 18 |
| engine, the dip sleeve alone (momentum 0, insurance ×0.5 — what `--shadow` prints) | +0.86 | +1.54 / +0.18 | −21.2 · 1.16 | −12.4 · 67 % | 61 (7 / 7 / 47) | 0 % | 60 |
| `fastbt` dip-only, `validate.py`'s three parameter sets (H4) | | | | | same trade sets, equity within 3 … 9 × 10⁻⁹ | | |

**Verdict on the pre-registered rules.** **H1 holds**: the path-exact book makes +1.03 pp/yr against the blend's +1.36 — a gap of −0.33, inside ±0.5 and inside the +0.9 … +1.3 point estimate. **H2 fails, as the named risk**: the first half reads −0.27 against the blend's +0.27; the second half +2.34 against +2.46. **H3 holds**: the drawdown is −19.3 against −20.0 (0.7 shallower, not deeper; held positions unscaled did not cost drawdown on this decade). **H4 holds** after the exit-routing revert: trade-for-trade equal, equity within 10⁻⁸. **H5 holds**: the two-sleeve engine and its own dip sleeve trade the same 61 trades with the same exits; against the blend's `fastbt` sleeve one trade differs (a `time` exit became a `stop`) because the engine pauses entries while the shock trigger is on and the blend does not — named in advance. **The gap decomposed**: the whole-book reserve is the gap and more (reserve 2 % → +1.48, +0.45; the blend is ≈ 3 % more invested), the band costs 0.06 (band 0 → +1.09), and with both removed the engine is +0.20 *above* the blend (+1.56) — the engine reads the insurance and the shock at the same close while the blend lags a session, and it does not scale the held dip positions. Two side readings that match Decisions 067 / 068 on the exact path: the shock trigger buys 4.0 points of drawdown for +0.11 pp/yr (−23.3 → −19.3), and the insurance costs 1.4 pp/yr on this decade (+2.43 without it) — the bull-decade price of the long-bear instrument.

**Decision — the drop rule applies to H2, so the decade expectation is restated from the exact path.** The two-sleeve book under design 070 is expected to make **about +1.0 pp/yr over SPY in a decade like 2017–2026 — not positive in both halves on the exact path (first half −0.3, second +2.3) — with the worst drawdown about −19 % against SPY's −34 %, Sharpe 1.12 against 0.89 and a worst relative year of −11.5**; the "+1.4, both halves positive" line was the blend's, 0.3 of which is the 5 % reserve the live book holds on the whole book and the daily free rebalancing the executor does not do. **The century +3.6 stays a blend number**, and is labelled as such from now on: its momentum leg is a frictionless French decile (not a tradeable ETF) and its insurance is the SMA alone (Decision 077's incumbent on the long windows), so an exact path there would be exact about a book nobody can trade; the engine can run it (industries as bars) if a century path is ever wanted, but it was not pre-registered and is not run here. Nothing live changes: no parameter, no config, no order; the benchmark window and `design` 070 stand. **Deployed 2026-10-30 14:57 UTC** (operator: "Deploy now"; commit `d139e6e` on the server): no job running (the next at 19:30 UTC), `git pull --ff-only` → both images built → `up -d api` (down for seconds) → cache pruned (disk 44 %) → health ok, 7 jobs registered, 0 errors after the restart; both images import the new module (the CLI image through its `uv` entrypoint); no config change, `design` 070, no window restart. Verified on the CLI image: `download-history /tmp/hist --days 400` saves 28 files (SPMO included), `backtest-mech /tmp/hist --shadow --start 2026-10-29` prints the book for both lists (2 sessions, 0 trades, SPMO share 57 %, one SPY and one SPMO core trade on the first day, −2.5 % vs SPY −1.3 % — SPMO's two red days, meaningless by construction) and each dip sleeve alone. From the next checkup the shadow line reads both lists under the same two-sleeve book plus each dip sleeve alone.

**Scripts / docs**: `src/titantrade/backtest/mechanical.py`, `__main__.py` (`download-history`, help), `tests/test_backtest_two_sleeve.py`, `tests/test_universe_switch.py` (the load assertion), `scripts/param_search/validate.py` (`--two-sleeve` → `data/param_search/two_sleeve_gap.json`), the harness README rows; `docs/features.md`, `TitanTrade/docs/architecture.md`, `CLAUDE.md`, roadmap Track F ✅ with the expectation restated in its preamble, todo Phase 2.21 and the Phase 2.9 expectation line.

## Decision 080: The de-risk destination — cash, bills, bonds and gold judged together: bills beat cash, a short Treasury beats bills on every window and check, the 10-year beats it by more but loses the inflation era and 2022, gold was 1973–74; **proposed, not applied**: the cash leg at go-live is a 1–3-year Treasury ETF rather than SGOV, the 10-year the dial (roadmap B8, operator's go, 2026-10-30)
**Date**: 2026-10-30
**Why**: when the insurance or the shock trigger halves exposure the idle half earns 0 in the research engine and on paper, and the sweep or SGOV at go-live (Decision 071). Decision 079 found gold as the parking place beat bills over 1971 → on the strength of 1973–74. B8 asked the whole question once, the Decision 062 way: hypotheses D1–D7 and the drop rule committed before the first run (`75d7049`, `scripts/param_search/destination.py`); after it, the addendum A1 — the 1975 → window without 1973–74 as a required confirmation — committed before the second (`ea40b11`, `--from1975`). Data from the library: Kenneth French's daily bill return, FRED's constant-maturity 10-year (1962 →) and 2-year (1976 →) yields turned into daily total returns by repricing a par bond (yesterday's coupon at today's yield plus the accrual), Decision 079's gold step series, and on the decade IEF, TLT, GLD and the constructed notes. The book = min(insurance ×0.5, shock ×0.5) × (0.4 dip + 0.6 momentum), the destination = the idle (1 − e) share; each asset's timing placebo = its returns block-shuffled (63 sessions, 50 draws). **Nothing live changes; the proposal is a go-live configuration value on the operator's go.**

**The destinations alone, 1971-09 → 2026-08**: bills 4.4 %/yr (no drawdown); the 2-year 4.7 (DD −6 %); the 10-year 6.2 (DD −27 %, 2020 → 2023); gold 8.6 (DD −62 %); daily correlations with the market −0.05 … 0 (D1 ✓).

**The book with the idle half in each destination** (excess vs the market; the gain vs bills; IS / OOS; DD; Sharpe; eras; episodes = book minus market, fall / rebound; the placebo's median [p10 … p90] and the share of draws beaten):

| window · destination | excess (vs bills) | IS / OOS | DD · Sharpe | eras | 1973–74 · 1980–82 · 2000–02 · 2008 · 2020 · 2022 | placebo |
|---|---|---|---|---|---|---|
| **1971 →** · cash (the engine) | +2.62 (−0.71) | +3.8 / +1.5 | −35.6 · 0.88 | +4.0 / +1.2 | +21 · −1 · +17 · +21 · +12 · +11 | |
| bills (the carry line) | **+3.34** | +4.9 / +1.9 | −34.9 · 0.91 | +5.1 / +1.5 | +25 · +3 · +20 · +22 · +12 · +11 | |
| **the 10-year** | **+4.13 (+0.79)** | **+5.6 / +2.7** | **−29.4 · 0.95** | +5.9 / +2.3 | +21 · **+11** · **+28** · **+27** · +14 · **+4** | +3.52 [+3.15 … +3.90], **94 %** |
| **the 2-year** (cash before 1976) | **+3.59 (+0.26)** | +5.1 / +2.2 | −33.0 · 0.93 | +5.3 / +1.8 | +21 · +9 · +23 · +24 · +13 · +9 | +3.32 [+3.22 … +3.49], 96 % |
| gold | +4.71 (+1.38) | +6.5 / +3.1 | −32.5 · 0.95 | +6.7 / +2.7 | **+67** · −11 · +21 · +27 · +13 · +8 | +4.14 [+3.46 … +4.75], 88 % |
| bills 50 / gold 50 · the 10-year 50 / gold 50 | +4.06 (+0.72) · +4.47 (+1.13) | +5.8 / +2.5 · +6.1 / +2.9 | −32.4 · −29.6 | | +45 · +42 in 1973–74 | 96 % · 98 % |
| the market · a permanent 10 % 10-year *sleeve* (reference) | +2.97 · +1.64 (−0.98 vs the book) | | −54.3 · −32.0 | | | |
| **1962 →** (eras 1962–75 / 1975–2000 / 2000–26) · cash · bills | +3.48 · **+4.23** | +5.9 / +1.1 · +7.1 / +1.4 | −35.6 · −34.9 | +8.5 / +3.3 / +1.2 · **+9.7** / +4.2 / +1.5 | | |
| the 10-year | **+4.89 (+0.66)** | +7.6 / +2.2 | −29.4 · 0.99 | **+9.4** / +5.3 / +2.3 | | +4.39 [+4.02 … +4.74], 94 % |
| **1975 → (without 1973–74)** · cash · bills | +2.18 · **+2.80** | +3.3 / +1.1 · +4.3 / +1.5 | −35.6 · −34.9 | +3.3 / +1.2 · +4.2 / +1.5 | | |
| **the 10-year** | **+3.73 (+0.93)** | **+5.3 / +2.3** | **−29.4 · 0.99** | **+5.3 / +2.3** | +11 · +28 · +27 · +14 · +4 | +3.06 [+2.71 … +3.57], **98 %** |
| **the 2-year** | **+3.23 (+0.43)** | +4.8 / +1.7 | −33.0 · 0.97 | +4.8 / +1.8 | +9 · +23 · +24 · +13 · +9 | +2.87 [+2.69 … +3.06], 98 % |
| gold · bills 50 / gold 50 · the 10-year 50 / gold 50 | +3.09 (+0.29) · +2.97 (+0.17) · +3.44 (+0.64) | +3.4 / +2.8 · +3.8 / +2.2 · +4.4 / +2.6 | | **not both eras** · not both · both | | 56 % · 44 % · 82 % — **none clears** |
| **the decade** (2017 →) · cash · bills | +1.36 · **+1.54** | +0.3 / +2.5 · +0.4 / +2.7 | −20.0 · −19.9 | | 2022: +10 · +10 | |
| the 2-year · the 10-year · IEF · TLT | +1.43 (−0.11) · +1.29 (−0.25) · +1.27 (−0.27) · +0.19 (−1.35) | | −21.0 · −24.0 · −23.7 · −30.9 | | 2022: +8 · +5 · +6 · +1 | 18 % · 52 % · 28 % · 12 % |
| GLD · bills 50 / GLD 50 | +3.05 (+1.51) · +2.31 (+0.78) | +1.5 / +4.6 · +1.0 / +3.7 | −23.0 · −20.9 | | | 62 % · 68 % — not cleared |

**Readings.** (1) **Bills beat cash** by 0.6 … 0.7 pp/yr on every long window — the carry line, known. (2) **A short Treasury beats bills** by +0.26 (1971 →, cash before 1976) and +0.43 (1975 →), in both halves and both eras, with the drawdown 2 … 3 points shallower than cash's, above its placebo's 90th percentile on both windows — D4's "carry with a little duration", confirmed on every pre-registered check; on the decade it is −0.11 (2022, the one losing episode: +9 vs +11). (3) **The 10-year beats bills by the most** — +0.79 / +0.93 / +0.66 on the three long windows, the drawdown 5 … 6 points shallower than cash's, the placebo cleared on all three (94 / 98 / 94 %), both halves and both eras from 1971 and from 1975: bonds rally when the book steps aside (1982 +11, 2000–02 +28, 2008 +27, 2020 +14 against +3 / +20 / +22 / +12 in bills) — and it loses where rates rise with the fall: **behind bills in 1962–75** (+9.4 vs +9.7, the inflation decade — the one era that fails the strict rule, by 0.3) and **in 2022** (+4 vs +11), and −0.25 on the decade. (4) **Gold and the mixes were 1973–74** (Decision 079 confirmed): from 1975 gold is +0.29 over bills at the placebo's median, the mixes at or below it, none ahead in both eras. (5) A permanent bond sleeve costs the book a point a year — closed, as on the decade.

**Decision — proposed, not applied.** At go-live, when the cash leg is on (the account cannot enrol in the sweep, or the sweep lags), its ticker is a **1–3-year Treasury ETF (SHY, or VGSH) rather than SGOV**: the expected pickup is +0.3 pp/yr over bills with the book's drawdown unchanged or shallower over fifty years, and −0.1 in a 2020s-type rate regime; it passed every pre-registered check on both long windows. No code — `cash_ticker` takes any ticker (Decision 071), and the leg stays off on paper (paper credits no distributions). The **10-year (IEF) is recorded as the dial**: +0.8 … +0.9 over bills historically with a 5-point-shallower drawdown, −0.3 in the 2020s and in 1962–75 — its failure mode is a rate-shock bear, which is the operator's named fear (inflation, a weaker dollar), so it is the operator's call, not the recommendation. Gold and the mixes are closed as the parking place. At go-live the checkup line becomes "the sweep APY vs SHY's yield plus the +0.3 duration pickup" and the deployment, risk-management and features pages name SHY where they name SGOV — **on the operator's go, when the live account exists**; nothing changes before. **Next: the first checkup under design 070 (≈ 2026-11-05), then the Track F cleanup** (the two-sleeve book in the package backtester).

*Operator (2026-10-30): "Leave for go-live" — the cash leg stays off on paper (no coupons are credited there, so the gain cannot show and a drill would only test the plumbing); SHY goes on at go-live on the operator's go.*

### Check 2026-10-30 — the first under design 070 (Oct 29 13:03 → Oct 30 14:08 UTC; six days early, on the operator's call)
**Ops**: 0 ERROR / 0 WARNING in the container log since the deploy; every job `completed` — Oct 29 14:15 UTC execute (0 trades), 19:30 execute (0 trades), 20:30 daily summary sent; Oct 30 13:00 fetch (bundle refreshed), 13:35 gapcheck (0 positions closed, 0 stops placed); the Oct 30 14:15 execute was pending at the read. Both images from the Oct 29 13:40 build; the server checkout at the handover commit (`2afaf99`) is behind only on docs and research scripts — no `src/` change since the deploy, nothing to deploy; disk 44 %. Backups: the 21:30 UTC cron ran (644 KB, 2 kept); the latest archive pulled off-server at 14:06 UTC (`scripts/pull_backup.sh`).

**Book** (14:07 UTC): equity $112,742 — DXCM 325 sh @ $78.08 → $84.20 (+7.8 %, 24.3 % of equity), URI 26 @ $1,065.68 → $1,183.58 (+11.1 %, 27.3 %), JPM 57 @ $336.29 → $337.67 (+0.4 %, 17.1 %), **SPMO 216 @ $142.68 → $137.77 (−3.4 %, 26.4 %)**, SPY 0, cash 5.0 %. All three dip positions carry their GTC stop-limits at the plan levels — DXCM $68.91 / limit $68.22 (placed Oct 26, expires 2027-01-22), URI $940.20 / $930.80 and JPM $297.37 / $294.40 (Oct 13, expire 2027-01-11) — 73 … 84 days from Alpaca's 90-day expiry. The 60-trading-day clocks end about Jan 8 (JPM, URI) and about Jan 21 (DXCM): **DXCM's clock and its stop's expiry fall within a day of each other** — the 09:35 ET coverage job is the backstop; a watch item.

**Plan** (the Oct 29 19:30 run): exposure ×1.0 — risk-off no (SPY above its 200-day SMA, breadth 54.5 %), shock off (worst 10-session move −2.4 %); SPMO target 57 %; 0 free slots, three HOLD items, `legacy_to_close` empty, no candidates: XLC 10.3 %, XLI 9.7 %, XLRE 8.5 % and XLU 8.2 % below their 90-day highs but under their 150-day SMA (the trend filter), the other seven with no dip. SPMO sits at 26.4 % against its 57 % target and buys only from freed cash (SPY is already 0), as designed: no SPMO trade on Oct 29–30, nothing orphaned. Trade log: 0 records since Oct 28; near misses 0 since Oct 29; no curator run yet (the first under design 070 is Sunday Nov 1, 15:00 ET).

**The numbers**: benchmark — `n_days` 0 at the Oct 29 20:30 refresh (the window opened at 13:04 that day; Oct 30 is its first full session) → "Insufficient data"; the Decision 069 wording ("too short to judge the return … excess ± band") applies from 20 trading days, about Nov 26. Fill ledger — 1 row: DXCM's Oct 27 entry, written before the ledger existed, so the bracket limit stands in (`fill_known` false), gap −0.33 % against the session close (the actual fill $78.08 was 0.6 % below the close); the first captured row comes with the first ETF entry. Shadow backtest — `backtest-mech --shadow --start 2026-10-29` on the CLI image (the 27 names downloaded into the container's /tmp, then the backtest): 2 sessions, 0 trades, the dip-only shadow book −1.1 % against SPY's −1.2 % — the first data point, meaningless by construction; the mechanics work.

**Go/stop rule (Decision 069)**: behaviour — no action in the window, nothing to judge; drawdown — no SPY drawdown in a two-session window; return — not judged under three years.

**The verify list from Decision 070**: the 15:30 ET Oct 29 execute clean ✓; SPMO inside its band, no churn ✓; DXCM / URI / JPM held with their own exits ✓; `backtest-mech --shadow` runs ✓. Still pending: the Nov 1 curator proposal naming the shadow list; the first ETF entry (gate 8 "not applied", a `fill_price`, a ledger row) — no free slot until a held name exits; the benchmark line's wording at 20 days.

**Research data archived** on titanserver under `/home/TitanTrade/archive/param_search/`: `external/sec_facts/` (119 MB, the 599 SEC filers), `alpaca_hist/quality/` (the 11 quality ETFs), and the ten new FRED files (Moody's yields and spreads, the TED spread, the three first-release stress series). Next checkup ≈ 2026-11-12, or earlier after the first ETF entry.

**Scripts / docs**: `scripts/param_search/destination.py` (pre-registration `75d7049`, the addendum `ea40b11`, then the code; `--from1975`), `bond_rets` (a constant-maturity par-bond total return from a yield series — reusable), the harness README row; roadmap B8 ✅ / C5 / D / C3; todo Phase 2.20 and the Phase 2.0 go-live item (b); one insight; handover note.

## Decision 079: Gold over a century — a gold sleeve costs return for a smoother ride in every era, as on the decade; gold as the parking place for de-risked capital looked good and was 1973–74; no sleeve, the parking-place question goes to B8 with bonds (roadmap B7, operator's go, 2026-10-30)
**Date**: 2026-10-30
**Why**: a permanent 10 % gold sleeve was tested on the decade alone (Decision 068 addendum #12: −0.3 pp/yr for +0.08 of Sharpe on a decade in which gold made 13 % a year) and not adopted for lack of long data. The Decision 072 library has datahub's monthly gold price from 1833 (monthly averages). Done the Decision 062 way: design, hypotheses G1–G5 and the drop rules committed before the first run (`2f52478`, `scripts/param_search/gold.py`); after the first run and before the second, the addendum A1–A2 with a sharpened rule for the parking place (`1636a74`, `--addendum`). The honest window is the floating era from September 1971 (gold was a fixed-price currency before, with one 69 % revaluation in 1934: $26 → $35; $41 in July 1971, $184 by December 1974, $675 in January 1980, $260 in April 2001, $4,319 in September 2026); the full century is shown with that caveat. Gold enters the century book as a daily step (each month's average known on the first session of the next); GLD daily on the ETF decade. No placebo for a sleeve (an asset held is carry, not a signal); a timing placebo for the parking place. **Nothing live changes.**

**The floating era, 1971-09 → 2026-08** (excess vs the French market; gain vs the book; IS / OOS at 1998-07; σ relative to the market; DD; Sharpe; eras 1971–2000 / 2000–26; episodes = book minus market, fall / rebound year):

| line | excess (gain) | IS / OOS | σ/σm | DD · Sharpe | eras | 1973–74 · 1980–82 · 2008 · 2020 · 2022 |
|---|---|---|---|---|---|---|
| **gold alone** (+8.6 %/yr vs the market's +11.3; monthly correlation −0.01) | −2.63 | −6.0 / +0.6 | 1.03 | **−62.1** (1980 → 2001) · 0.56 | −6.8 / +1.9 | **+186 / −47** · −29 / −51 · +87 / −59 · +37 / −74 · +19 / −7 |
| **the book** (dip 40 / mom 60, idle at 0) | **+2.62** | +3.8 / +1.5 | 0.97 | −35.6 · 0.88 | +4.0 / +1.2 | +21 / −0 · −1 / +12 · +21 / −26 · +12 / −16 · +11 / −11 |
| gold 10 from the momentum sleeve (40 / 50 / 10) | +1.94 (**−0.68**) | +2.5 / +1.4 | 0.87 | −31.3 · 0.92 | +2.6 / +1.3 | +27 / −6 · −3 / +6 · +25 / −28 · +14 / −21 · +12 / −11 |
| gold 10 from the dip sleeve (30 / 60 / 10) | +2.46 (−0.16) | +3.2 / +1.8 | 0.89 | −31.2 · 0.93 | +3.4 / +1.5 | |
| gold 20 from both (30 / 50 / 20) | +1.73 (−0.89) | +1.9 / +1.6 | 0.80 | −26.8 · 0.97 | +1.9 / +1.5 | |
| gold 10 outside the exposure rules | +2.15 (−0.47) | +2.8 / +1.5 | 0.87 | −30.7 · 0.93 | +2.8 / +1.4 | |
| *the parking place for the idle half*: bills (the carry line) | +3.34 (+0.71) | +4.9 / +1.9 | 0.97 | −34.9 · 0.91 | +5.1 / +1.5 | +25 / +2 · +3 / +12 · +22 / −26 · +12 / −16 · +11 / −11 |
| **idle in gold** | **+4.71 (+2.09)** | **+6.5 / +3.1** | 1.01 | **−32.5 · 0.95** | +6.7 / +2.7 | **+67 / +15** · −11 / +12 · +27 / −30 · +13 / −11 · +8 / −9 |
| idle in the market | +2.97 (+0.35) | +3.7 / +2.3 | 1.18 | −54.3 · 0.77 | +4.1 / +1.8 | |

The full century 1927 → (gold = cash with the 1934 jump before 1971): the book +3.63 (eras +4.6 / +5.5 / +3.3 / +1.2); gold 10 from the momentum sleeve +2.73 (−0.90; eras +4.0 / +4.3 / +1.2 / +1.3; DD −54.7 vs −58.6); from the dip sleeve +3.17 (−0.46); idle in gold +4.62 vs bills +4.15 (eras +4.4 / +8.0 / +3.5 / +2.7 vs +4.7 / +6.3 / +4.2 / +1.5 — behind bills in 1927–50 and **in 1975–2000**). The decade with GLD reproduces Decision 068 to the decimal: gold 10 from SPMO −0.32 pp/yr, Sharpe 1.18 vs 1.10, DD −18.3 vs −20.0 (G4 ✓); idle in GLD +3.05 vs bills +1.54 (+1.5 / +4.6), DD −23.0 (3 points deeper than cash).

**The sleeves — closed.** G1, G2 and G5 hold: gold alone made 8.6 % a year against the market's 11.3 with a −62 % drawdown and no correlation; every sleeve variant costs return (−0.2 … −0.9 pp/yr over 55 years, −0.3 … −0.5 on the decade) for a shallower drawdown (4 … 9 points) and a higher Sharpe (+0.04 … +0.09); none is ahead of the book in both halves. The century agrees with the decade exactly: a gold sleeve is a drawdown dial bought with return, the same shape in 1971–98 (worse) and 1998–2026 (about even) as in 2017–21 / 2022–26. Not adopted; recorded so it is not re-proposed.

**The parking place — a candidate that was one episode.** On the letter the idle half in gold passed the pre-registered bar (ahead of bills in both halves, the drawdown shallower). The addendum (A1–A2, written before it ran):

| window | gold while the book is de-risked vs overall | idle in cash · bills · gold | placebo (gold's returns block-shuffled, 50 draws) |
|---|---|---|---|
| 1971 → | **+14.6 %/yr vs +9.7** (de-risked 27 % of sessions; the market +7.2 while de-risked) | +2.62 · +3.34 (+4.9 / +1.9) · **+4.71 (+6.5 / +3.1)** | median +3.86 [+3.27 … +4.78]; idle in gold above **84 %** of draws (the bar was 90 %) |
| **1975 → (without 1973–74)** | **+7.0 %/yr vs +7.2** — no crisis property at all | +2.18 · +2.80 (+4.3 / +1.5) · +3.09 (**+3.4 / +2.8**) | median +3.11 [+2.49 … +4.13]; idle in gold above **48 %** of draws — the median |

Reading: gold earned 14.6 % a year during the book's de-risked windows over 1971 → and 7.0 % during them from 1975 → — the entire "crisis hedge" is 1973–74, when gold rose 186 % in the two years the book was half out (+67 against the market in that one episode against bills' +25). From 1975 the idle half in gold is behind bills in the first half (+3.4 vs +4.3), ahead in the second (+2.8 vs +1.5: the 2000s and 2020), and sits at the placebo's median: gold's return in the stress windows was gold's return. The 2008 lead (+27 vs +22) came in the second leg of 2008 after gold had fallen 30 % in the first; 2022 gold was flat and the idle half lost to bills. One episode, and the decade's 3-point-deeper drawdown.

**Decision.** Nothing changes. No gold sleeve: the century confirms the decade's shape. The parking place for de-risked capital is not decided here: gold as the destination is recorded as a candidate and **folded into B8**, where cash, bills, bonds and gold are judged together on the same windows with the same timing placebo and the four-era standard — the destination is one question. The live book's idle capital is cash on paper and the sweep or SGOV at go-live (Decision 071); nothing in this test moves that. **Next: B8** (bonds — and gold — as the de-risk destination, on the yields since 1954 / 1962), then the Track F cleanup; the first checkup under design 070 is due about November 5.

**Scripts / docs**: `scripts/param_search/gold.py` (pre-registration `2f52478`, the addendum `1636a74`, then the code; `--addendum`), the harness README row; roadmap B7 ✅ / B8 amended / Track D / C3; todo Phase 2.19; one insight; handover note.

## Decision 078: A VIX-based shock trigger — no version beats the −7 % price rule; the fear gauge is a state that fires three times as often and does not lead; the price rule stays (roadmap B6, operator's go, 2026-10-30)
**Date**: 2026-10-30
**Why**: the live shock trigger is a fact about prices (SPY −7 % over 10 sessions → exposure ×0.5 for 20, re-armed); B6 asked whether the VIX — the market's 30-day implied volatility, daily from 1990 — triggers earlier or better. Decision 077 had closed the VIX as a *slow* second signal for the insurance; this is the fast mechanism. Done the Decision 062 way: variants, hypotheses X1–X5 and the Decision 067 bar committed before the run (`a2eb604`, `scripts/param_search/vixshock.py`). Data: Cboe VIX close 1990 → and VIX3M 2009 → (the Decision 072 library), read at the previous close; the century book on 1990-02 → 2026-08 (one era, split 2008-05, the three decades as sub-eras) and the ETF book on 2017 → 2026-10 (split 2022). 12 level cells (VIX > 25 / 30 / 35 / 40 × hold 10 / 20 / 40), 12 jump cells (up ≥ 8 / 12 / 16 points over 5 / 10 sessions × hold 10 / 20), the inverted term structure from 2009, each replacing the price rule and the level cells also as a third rule in the min(); the block-shuffled placebo at VIX > 30 / 20; the agreement of the two rules and a first-firing timing table over thirteen bears. **Nothing live changes.**

**The result** (excess vs the market; IS / OOS; DD; de-risked share; 1990 → eras 1990–2000 / 2000–10 / 2010–26; episodes = book minus market, fall / rebound year):

| rule | 1990 → | decade |
|---|---|---|
| insurance only, no shock rule | +1.57 (+4.3 / −1.1), DD −35.6, on 23 %; 2020 +7 / −16 | +1.29 (+0.4 / +2.1), DD −24.1, 13 % |
| **insurance + the price rule −7 % / 10 / 20 (live)** | **+1.75 (+4.2 / −0.6), DD −35.6, on 25 %; eras +3.3 / +5.8 / −1.9; 2008 +21 / −26, 2020 +12 / −16, 2022 +11 / −11, 2025 −5 / +5** | **+1.36 (+0.3 / +2.5), DD −20.0, 15.5 %; 2020 +14 / −24** |
| VIX > 25, hold 10 / 20 / 40 | −0.34 / −0.87 / −1.12, on 34–45 %; 2008 rebound −45 … −51, 2020 rebound −40 … −44 | −1.26 / −1.61 / −1.90, on 28–46 % |
| VIX > 30, hold 10 / 20 / 40 | +1.08 / +0.61 / +0.13, on 27–34 %; 2020 +10 / −33 … −41 | −1.08 / −1.05 / −1.25, on 19–32 % |
| VIX > 35, hold 10 / 20 / 40 | +1.27 / +1.23 / +0.97, on 24–28 % | −0.36 / −0.20 / −0.52 |
| VIX > 40, hold 10 / 20 / 40 | **+1.74** / +1.62 / +1.33, on 24–25 %; 2020 +10 / −26; eras +3.7 / +5.7 / −2.1 | +1.14 / +0.93 / +0.08, DD −22.0 |
| VIX up ≥ 8 points in 5 / 10, hold 10 / 20 | +0.8 … +1.2, on 26–31 % | −0.1 … +0.9 |
| VIX up ≥ 12 points | +1.40 … +1.54, on 24–26 % | +0.05 … +0.84 |
| VIX up ≥ 16 points | +1.46 … +1.70, on 24 %; 2020 +10 / −16 | +0.68 … +0.90, DD −22.0 |
| VIX > VIX3M (inverted), hold 10 / 20, from 2009 | +0.63 / +0.31, on 29–33 %; 2010–26 −4.3 / −5.1 | |
| the level rule as a third rule beside the price rule (hold 20): > 25 / 30 / 35 / 40 | −0.99 / +0.59 / +1.28 / +1.44 | −1.81 / −0.98 / −0.17 / +0.60 |
| placebo at VIX > 30 / 20 (20 block-shuffled draws) | +0.38 [−0.39 … +0.88]; the VIX cell +0.61 above 75 % | −0.14 [−1.38 … +0.87]; the VIX cell −1.05 above 20 % |

**Agreement and timing.** At VIX > 30 / hold 20 the VIX de-risks 18 % of sessions against the price rule's 11 %, and the two agree on only 45 % of the sessions either is on (X1 expected ≥ 85 %): the VIX stays above 30 for months after a crash (1998–2003, 2008–09, 2020, 2022), so a level is a *state*, the same thing Decision 077 closed. First firing after the peak, thirteen bears since 1990: the VIX led in 1990 (+13 sessions), 2008 (+45 — November 2007 against January 2008, the one place it was genuinely early), 2018-02 (+3), 2010-05 and 2025 (+1); tied in 1997, 1998, 2000, 2011 and 2015; lagged in 2018-Q4 (−4), 2020 (−1) and 2022 (−2). Median lead zero; in the two latest fast crashes a session either way.

**Readings.** X2 holds: the best level cell (VIX > 40, hold 10) is +1.74 against the price rule's +1.75 on 1990 →, with the same drawdown, and worse on the decade (+1.14 vs +1.36, DD −22.0 vs −20.0); no cell beats the price rule anywhere. X5 fails in the direction that matters: the level cells are not a plateau — VIX > 25 fires a third of the time and loses 2 … 3 pp/yr against the price rule on both windows, VIX > 30 loses 1 … 2, the rebound years after 2008 and 2020 are given back twice over (−45 … −51 instead of −26) because the gauge stays elevated through the recovery; only VIX > 40, which fires about as rarely as 2008 and 2020, matches the price rule. The *jump* of 12 … 16 points over 5 … 10 sessions matches the price rule too — because it is the same event: a 7 % fall in ten sessions is what moves the VIX 15 points. X3 holds (the third rule costs 0.3 … 0.8 at the thresholds that fire, nothing at 40, and buys no drawdown). X4: the VIX state beats a random state on 1990 → (75 %) and loses to it on the decade (20 %) — it carries some information and still less than the price fall. The inverted term structure (2009 →) is the worst of the family (+0.3 … +0.6, de-risked a third of the time).

**Decision.** Nothing changes. The price rule stays, and the reason is now measured: a fear gauge is a slow-decaying state that fires three times as often as the fall it is supposed to flag, does not lead the fall by more than a session except once in 2008, and where it is made fast (a 15-point jump) it is the fall under another name. The price rule needs nothing but closes, exists on every market and every century, and the VIX adds nothing it does not already say. B6 is closed with numbers; C2's "option-implied information" row stays closed for regime use. **Next: B7** (gold over a century), the last of the cheap afternoon tests.

**Scripts / docs**: `scripts/param_search/vixshock.py` (pre-registration `a2eb604`, then the code), the harness README row; roadmap B6 ✅ closed, Track D; todo Phase 2.18; one insight; handover note.

## Decision 077: Credit stress as the insurance's second signal — the revised NFCI passes the bar, the unrevised credit spread does not reproduce it; a candidate that failed its robustness check; the insurance keeps its two signals (roadmap B5, operator's go, 2026-10-30)
**Date**: 2026-10-30
**Why**: the two-signal insurance (SPY below its 200-day SMA *and* fewer than half of the sector ETFs above theirs) halves exposure; member breadth as the second signal failed in Decision 068's addendum because a random breadth did as well on the decade. B5 asked whether a signal from a *different population* — the credit and funding markets — is a better second condition. Done the Decision 062 way: hypotheses C1–C6, the two caveats (revisions, the era) and the drop rules committed before the first run (`27457b8`, `scripts/param_search/stress.py`); after the first run and before the second, an addendum with checks S1–S3 and the drop rule for the whole of B5 (`227e040`). Data from the Decision 072 library: the Chicago Fed's NFCI and ANFCI (weekly, 1971 →), the St. Louis Fed's STLFSI4 (1993 →), the VIX (1990 →), each read one week late at the previous close; then Moody's BAA and AAA yields (monthly 1919 →, daily 1983 →, never revised) and the first-release vintages of the NFCI from the FRED archive. Book = min(insurance ×0.5, shock ×0.5) × (0.4 dip + 0.6 momentum); the incumbent on the decade is the live two-signal rule, on the long windows the SMA alone; every middle threshold against a block-shuffled placebo (20 draws). **Nothing live changes.**

**Run 1 — the stress indices as the second signal** (excess vs the market; IS / OOS; DD; de-risked share; the placebo's median and spread; episodes = book minus market, the fall / the rebound year):

| window · rule | excess (IS / OOS) | DD · Sharpe | on | placebo [p10 … p90], beaten | episodes kept / lost |
|---|---|---|---|---|---|
| **1971 → (eras 1971–2000 / 2000–26)** · incumbent, SMA alone | +2.62 (+3.8 / +1.5); eras +4.0 / +1.2 | −35.6 · 0.87 | 24.5 % | | 1973 +21 / −0, 1987 +11 / −17, 2000 +17 / −0, 2008 +21 / −26, 2020 +12 / −16, 2022 +11 / −11 |
| SMA AND NFCI > 0 | +3.11 (+3.9 / +2.3) | −39.9 · 0.86 | 11.7 % | | 1973 +21, 2008 +21, 2020 +12 / −13; 1990 +1, 2011 −4 |
| **SMA AND NFCI > 0.5** | **+3.50 (+4.3 / +2.7); eras +4.6 / +2.3** | **−37.4 · 0.88** | 9.1 % | **+2.80 [+2.53 … +3.00], beaten 100 %** | 1973 +21 / +1, 1987 +11 / −13, 2000 +15, 2008 +22, 2020 +12 / −9, 2022 +8 / −9; 1990 −4, 2011 −4 |
| SMA AND NFCI > 1 | +3.16 (+4.3 / +2.1) | −44.4 · 0.85 | 7.2 % | | 2008 only +12 |
| NFCI > 0.5 alone (no SMA) · as a third rule in the min() | +2.23 (+1.8 / +2.6) · +1.35 (+1.3 / +1.4) | −37.4 · 0.83 · −34.3 · 0.83 | 18.4 · 35.3 % | | 1973 rebound −12; 2008 rebound −33 |
| SMA AND ANFCI > 0 · > 0.5 | +3.37 (+4.1 / +2.7) · +3.23 (+3.9 / +2.6) | −35.6 · −37.4 | 12.4 · 9.6 % | > 0.5: +2.86 [+2.62 … +3.09], 95 % | |
| **1990 → (VIX, the unrevised twin)** · incumbent | +1.75 (+4.2 / −0.6) | −35.6 · 0.78 | 23.3 % | | |
| SMA AND VIX > 20 · > 25 · > 30 | +2.07 (+5.1 / −0.9) · **+1.86 (+4.7 / −0.9)** · +1.68 | −36.6 · **−42.5** · −46.5 | 18.8 · 12.0 · 6.8 % | > 25: +2.13 [+1.82 … +2.69], **beaten 15 %** | > 25: 1990 −1, 2008 +14 (vs +21), 2011 −2 |
| **1994 → (STLFSI4)** · incumbent | +1.14 (+4.3 / −2.1) | −35.6 · 0.72 | 23.9 % | | |
| SMA AND STLFSI4 > 0 · > 1 · > 2 | +1.81 · +1.76 (+5.3 / −1.8) · +1.36 | −35.6 · −37.0 · −46.3 | 18.2 · 6.8 · 2.6 % | > 1: +1.51 [+1.29 … +1.62], beaten 100 % | |
| **the decade** · live two-signal · SMA alone · no insurance | +1.36 (+0.3 / +2.5) · +2.15 · +3.03 | −20.0 all | 13.2 · 16.4 · 0 % | | |
| SMA AND NFCI > 0 · > 0.5 · > 1 | +2.85 · **+3.03 · +3.03** (never fires) | −20.0 | 1.6 · **0.0 · 0.0 %** | > 0.5: degenerate (never fires) | 2020 carried by the shock trigger either way |
| SMA AND VIX > 25 · as a third rule · SMA AND breadth AND VIX > 25 | +2.28 (+0.7 / +3.9) · −0.73 (DD −21.3) · +2.60 | | 8.7 · 21.4 · 8.1 % | > 25: +2.78 [+2.38 … +3.50], beaten 10 % | |

On the letter, SMA AND NFCI > 0.5 on 1971 → met every pre-registered condition: both halves and both eras ahead of the SMA alone, the drawdown 1.8 points deeper (the bar was 3), all twenty placebo draws beaten (a random series firing 9 % of the time earns +2.80 — fewer firings pay on that window too — and the NFCI's 9 % earns +3.50, so its *timing* carried about +0.7 of information), the VIX twin positive in sign, the decade no worse than its placebo. The information is in the rebounds: the stress gate switches the insurance off while SPY is still below its SMA once credit conditions normalise (2020's rebound year −9 vs −16, 1987's −13 vs −17, 1973's +1 vs −0), while keeping the deep bears (1973–74, 2000–02, 2008 all kept at +15 … +22). In spirit it failed two of its own checks: the VIX twin agreed by +0.1 with a drawdown 7 points deeper and no placebo beaten; and on the decade the rule never fires (the NFCI did not cross 0.5 in 2017–2026 in the current vintage, so "SMA AND NFCI > 0.5" is the no-insurance book, +3.03).

**The revision finding** (the FRED archive, ALFRED, free): the NFCI is re-estimated and its whole history revised at each release. The vintage published 2020-04-10 read the week of 2020-04-03 at **+0.07**; the current vintage reads the same week at **+0.31**; the March 2020 weeks changed sign. The first-release history (the FRED API's initial-release output, fetched on the server with the project's key, `external/fred/NFCI_initial.csv`) exists only from June 2011; the St. Louis index's from November 2022. So a threshold on the current vintage is not what anyone could have traded, and before 2011 there is no way to know what they would have seen.

**Run 2 — the unrevised twin and the real-time check** (the addendum's S1–S3; Moody's BAA − AAA read one month late; the daily spreads one day late):

| window · rule | excess (IS / OOS) | DD | on | placebo, beaten | episodes |
|---|---|---|---|---|---|
| **century 1927 →** · SMA alone | +3.63 (+5.0 / +2.2); eras +4.6 / +5.5 / +3.3 / +1.2; era DD −59 / −28 / −25 / −36 | −58.6 · 0.86 | 27.5 % | | 1929 +26, 1937 +15, 1973 +21, 2008 +21 |
| SMA AND BAA − AAA > 1.5 | +3.64 (+4.4 / +2.8); **eras +4.6 / +4.3 / +4.3 / +1.5; era DD −62 / −43 / −25 / −46** | −61.5 · 0.81 | 7.3 % | +3.45 [+3.26 … +3.61], 95 % | 1929 +23, 1937 +15, **1973 +5**, 2000 +15, **2008 +10**, 2020 +12 / −9 |
| > 1.2 · > 2.0 · alone | +3.62 · +3.62 · +2.42 | −61.7 · −62.0 · −61.5 | 11.9 · 4.6 · 17.9 % | | |
| **1971 →** · SMA alone | +2.62 (+3.8 / +1.5); era DD −27 / −36 | −35.6 | 24.5 % | | |
| **SMA AND BAA − AAA > 1.5** | **+2.74 (+3.6 / +2.0)** | **−46.3** | 2.9 % | **+2.88 [+2.57 … +3.10], beaten 35 %** | **1973 +5 (vs +21), 2008 +10 (vs +21)**, 1990 −4, 2011 −4; 2020 +12 / −9, 2022 +8 / −9 |
| > 1.2 · > 2.0 | +2.74 (+3.2 / +2.3) · +2.89 (+3.9 / +2.0) | −43.0 · −46.3 | 8.3 · 1.7 % | | |
| **1986 → daily** · SMA alone | +1.63 (+3.9 / −0.6) | −35.6 | 22.6 % | | |
| SMA AND DBAA − DAAA > 1.0 · 1.3 · 1.6 | +2.03 · +1.88 (+4.4 / −0.6) · +2.15 | −36.7 · −39.5 · −44.4 | 14.1 · 6.7 · 1.9 % | 1.3: +1.94 [+1.78 … +2.18], 25 % | 2008 +17 … +12 |
| SMA AND BAA10Y > 3.0 · 3.5 · 4.0 | +2.24 · +2.10 (+4.8 / −0.6) · +2.06 | −39.6 · −45.1 · −46.3 | 8.5 · 2.5 · 1.7 % | 3.5: +2.07 [+1.91 … +2.17], 70 % | |
| **2011-06 → (real-time NFCI)** · SMA alone | −2.21 (−3.8 / −0.6) | −27.8 | 17.3 % | | 2020 +12 / −16 |
| SMA AND NFCI current > 0 · > 0.5 | −1.48 · −1.30 | −29.5 | 1.0 · 0.0 % | | |
| SMA AND NFCI real-time > 0 · > 0.5 | −1.30 · −1.30 | −29.5 | 0.2 · 0.0 % | | the real-time NFCI's 2020 maximum **+0.07** vs the current vintage's +0.31; > 0 fired on 0.2 % of sessions in real time, 1.0 % in the current vintage |

**The verdict for the whole of B5: NO.** The unrevised spread gate does not reproduce the NFCI's result on the same window: +2.74 vs +2.62 with the first half *worse*, the drawdown **11 points deeper** (−46 vs −36), the placebo not beaten (35 %); on the century it is ahead of the SMA alone in only two of the four eras, with the 1950–75 drawdown 15 points deeper and the 2000–26 one 10 points deeper; the daily spreads say the same at every threshold. The mechanism is visible in the episodes: a credit spread confirms a bear *late* — Moody's spread crossed 1.5 points only in the autumn of 1974 and in October 2008 — so the gated insurance misses the first leg of exactly the bears the insurance exists for (1973–74 +5 instead of +21, 2008 +10 instead of +21) and keeps only the rebound benefit. The NFCI's clean early capture of 2008 and its 1973 are what the *revised* history shows; the real-time archive cannot say whether a live reader would have seen them, and where it can speak (2011 →) the real-time and current series differ by a quarter of a point in the one episode that matters.

**Decision.** Nothing changes. The insurance keeps its two signals; credit stress joins member breadth in Track D as a second signal closed with numbers. Kept: (1) a stress gate's real value is in the *rebound* (it releases the insurance earlier than the SMA does — +7 in 2020, +4 in 1987), which is the same territory the shock-release test (Decision 068 addendum) could not reach because the insurance binds there, and the same price (the crash's first leg) every time; (2) revised series are hindsight — any future rule on the NFCI, ANFCI or STLFSI4 must be designed on first-release data (`fetch` via the FRED API's initial-release output; available from 2011 / 2022) and the current vintage never used for a threshold; (3) Moody's spreads (monthly from 1919, daily from 1983, never revised) are in the library for any later credit question. The VIX as the *shock trigger* (B6, a different mechanism — a fast fact, not a slow state) is untouched by this and stays open. **Next: B6 / B7.**

**Scripts / docs**: `scripts/param_search/stress.py` (pre-registration `27457b8`, the addendum `227e040`, then the code; `--spread` for the second run), `fetch_external.py` (the Moody's and TED ids), `external/fred/{BAA,AAA,DBAA,DAAA,BAA10Y,AAA10Y,TEDRATE}.csv` and `{NFCI,ANFCI,STLFSI4}_initial.csv`; the harness README row; roadmap B5 ✅ / D; todo Phase 2.17; two insights; handover note.

## Decision 076: The quality stage 1 — our own profitability picks on free SEC data: the premium is there and concentration keeps it in-sample, the equal-weight sleeve we would trade gives it back and fails every pre-registered bar; no self-built sleeve (operator: "why not, if the data says so" → "free data first", 2026-10-30)
**Date**: 2026-10-30
**Why**: Decision 075 left one route to the quality premium — picking the most profitable companies ourselves — and the operator asked why not, if the data says it is profitable, diversifies and stands the test of time; then: free data first. Done the Decision 062 way: the design, hypotheses S1–S6 and the drop rules committed before any data was pulled (`a086fdc`, `scripts/param_search/qualpick.py`); the data all free — the S&P 500 point-in-time universe 2016 → 2026 (742 names, 94 delisted, Alpaca SIP dividend-adjusted, the daily membership mask) and every company's annual statements from the SEC's XBRL `companyfacts` API with their filing dates (`fetch_sec_facts.py` → `external/sec_facts/`, 599 of 745 tickers mapped through the SEC's current ticker file; the 146 unmapped are names acquired, renamed or delisted since 2016 — Hess, Kellogg, Juniper, Electronic Arts, Walgreens … — ineligible for picking, inside the benchmarks). Score = Fama–French operating profitability (revenue − cost of sales − SG&A − interest) / book equity from the latest 10-K *filed* before each rebalance, operating income / equity where cost of sales is not reported, net income / equity where operating income is not (banks, insurers, REITs); gross profitability / assets as the robustness definition. Top N equal-weight, rebalanced yearly (July primary, January secondary), 0.05 % a side; benchmarks SPY, the equal-weight hold of the names that could be picked (like for like), the French OP Hi 30 over the same window, 50 random lists of the same size; `screens.simulate` gained a score matrix and weights. **Nothing live changes.**

**The pipeline, honestly**: three runs. The first scored 159 of 505 members (one revenue tag per company instead of the first tag reporting each year); the second 165 (the SEC labels some filers' annual 10-K facts "Q4", and a year restated under a new tag in a later 10-K carried that later filing date, pushing whole years out of reach); the third — the one recorded — scores 303 → 455 of ~503 members per rebalance (at 2017-07: 201 with the full formula, 170 operating income / equity, 54 net income / equity, 9 unscorable; shares outstanding for 375 of 505). Point-in-time means *first reported*: each year's value from the earliest filing that carried it, whatever the tag. The bugs were coverage, not design; the design never changed.

**Verdict on the pre-registered rules: S1 fails (the top 30 % beats the equal-weight universe in the first half only), S2 fails (the top-50 is at the random lists' median out of sample), S5 fails (the sleeve costs the book 0.6 … 0.9 pp/yr) → no self-built sleeve; on the drop rule the quality door closes on free data and the paid long-history extension is not worth buying for this design.**

**S1–S3 — the construct, the concentrated picks, the random lists** (July anchor, 2017-07-03 → 2026-10-12, split 2022; excess CAGR pp/yr; IS / OOS; "→ 2025" through 2025-12-31; the January anchor in the second group):

| line (equal-weight unless stated) | vs SPY | → 2025 | vs the EW of the scored set (like for like) | Sharpe (SPY 0.87) | turnover |
|---|---|---|---|---|---|
| top 30 % by profitability (≈ 150 names) | −1.40 (+1.7 / −4.1) | −1.17 | **+1.22 (+3.4 / −0.7)** | 0.79 | 32 % / yr |
| **top 50** | −0.72 (+2.9 / −3.9) | −0.44 | **+1.90 (+4.6 / −0.4)** | 0.84 | 39 % |
| top 30 | +1.84 (+5.0 / −1.0) | +1.19 | +4.46 (+6.7 / +2.5) | 0.95 | 42 % |
| bottom 30 % (the teeth) | −3.77 (−5.2 / −2.5) | −4.88 | −1.16 (−3.5 / +1.0) | 0.65 | |
| EW of the scored set · EW of all members | −2.62 (−1.7 / −3.5) · −3.29 | −2.88 · −3.62 | 0 · −0.67 | 0.72 · 0.70 | |
| 50 random names × 50 draws (vs the EW of the scored set) | | | median −0.23 [p10 −2.04 … p90 +1.63]; the top-50 above 92 % of draws, IS above 100 %, **OOS above 50 %** | | |
| 30 random names × 50 draws | | | median −0.37 [−2.76 … +2.63]; the top-30 above 98 %, IS 100 %, OOS 82 % | | |
| **French OP Hi 30 vs the French market, same window** | **+1.47 (+2.6 / +0.5)** | | Lo 30 −3.28 (−6.0 / −0.7) | 0.91 vs 0.83 | |
| *value-weighted (reference)*: top 30 % · top 50 · top 30 · VW of the scored set | −0.25 · **+1.78 (+4.4 / −0.6)** · **+3.05 (+5.2 / +1.1)** · −0.92 | −0.10 · +1.76 · +2.95 · −0.84 | | 0.84 · 0.90 · 0.92 · 0.80 | |
| January anchor: top 50 EW · top 30 EW | −0.98 (+1.7 / −3.6) · +1.24 (+4.6 / −2.0) | −0.50 · +0.79 | +2.08 (+3.8 / +0.4) · +4.30 (+6.7 / +2.0); the top-50 above 98 % of draws (OOS 66 %), the top-30 above 100 % (OOS 92 %) | 0.84 · 0.96 | 38 · 41 % |
| January, value-weighted: top 30 % · top 50 · top 30 · VW scored set | +2.19 (+5.3 / −0.9) · **+2.65 (+3.7 / +1.6)** · **+2.99 (+3.3 / +2.6)** · +1.05 (+3.2 / −1.1) | | | 0.93 · 0.93 · 0.90 · 0.90 | |

Readings. (1) **The pipeline reproduces the construct**: our top 30 % beats the equal-weight universe by +1.2 against the French portfolio's +1.5 over the same months, with the same shape — strong to 2021, flat to negative since (the French Hi 30 itself made only +0.5 in the second half) — and the bottom 30 % loses. S1 fails on the strict both-halves rule because of the era's second half, not the pipeline. (2) **Concentration keeps the premium in-sample and loses it out of sample**: the top-50 is above every random list through 2021 and at their median since 2022; the top-30 keeps +2.0 … +2.5 out of sample (above 82–92 % of draws) but at a tracking noise where one random list in fifty does as well. (3) **Against SPY, which is what we would trade against, the equal-weight picks lose**: the equal-weight effect alone is −2.6 … −3.3 pp/yr this decade, larger than the premium, so the top-50 reads −0.7 … −1.0 vs SPY and the second half −3.6 … −3.9 — exactly the pre-registered S3 shape. (4) **Value-weighted, the picks beat SPY by 2 … 3 pp/yr** (top 50 +1.8 / +2.7, top 30 +3.0 / +3.0, three of four cells positive in both halves, Sharpe 0.90–0.93 vs 0.87–0.89) — pre-registered as a reference line, not as the bar, and it carries a confound named below.

**S4 — the 12 cells and the walk-forward** (excess vs the EW of the scored set, full / IS / OOS):

| definition | N 50 July | N 30 July | N 50 January | N 30 January | marginal |
|---|---|---|---|---|---|
| **OP** (operating profitability / equity) | +1.90 (+4.6 / −0.4) | **+4.46 (+6.7 / +2.5)** | +2.08 (+3.8 / +0.4) | +4.30 (+6.7 / +2.0) | **+3.19** |
| OIE (operating income / equity) | +0.80 (+2.4 / −0.6) | +1.04 (+2.6 / −0.3) | +0.24 (+2.0 / −1.4) | +1.60 (+2.2 / +1.0) | +0.92 |
| GPA (gross profitability / assets) | −1.51 (+4.8 / **−6.7**) | −1.84 (+7.3 / **−9.2**) | −2.53 (+2.7 / −7.3) | −3.80 (+2.0 / −9.1) | −2.18 |

N 30 +1.32 vs N 50 +0.52; the anchors equal. **The walk-forward fails**: the cell chosen by in-sample excess is GPA N 30 July (+7.3) and it is the worst cell out of sample (−9.2, against a median of −0.5); chosen by out-of-sample excess the pick is OP N 30 July (+2.5 → +6.7 in-sample). Four of twelve cells are positive in both halves, all four of them OP or OIE. The family reading: profitability over *book equity* is consistent and gross profitability over *assets* collapses after 2021 — which is the confound: a ratio with book equity underneath ranks the buyback giants first (a company that has retired most of its equity shows an enormous ratio), so "most profitable by OP / equity" this decade is in part "the mega-caps that led the market", and a weighted version of it is doubly so. The French portfolio shares the denominator across a thousand names and is less exposed; a 30-name version is not.

**S5 — the sleeve** (2017-07-03 → 2026-10-12, vs SPY, the book over the same window as the bar): the book +1.31 (+0.0 / +2.5), Sharpe 1.07, → 2025 +0.72; dip 20 / SPMO 60 / picks 20 **+0.71 (+0.1 / +1.3), Sharpe 1.05, → 2025 +0.13**; dip 40 / SPMO 40 / picks 20 +0.40 (+0.4 / +0.4), Sharpe 1.08, +0.03; the picks alone under the exposure rules −2.94 (+1.0 / −6.4). Fails: the sleeve costs 0.6 … 0.9 pp/yr for the same Sharpe.

**S6 — running it**: turnover 39–42 % a year (taxable, short-term for the churned part); a 20 % sleeve of 50 equal names is 0.4 % of equity per name — **$100 at $25k and $400 at $100k against the $500 dust floor**, so the sleeve is untradeable below ≈ $125k at N 50 and below ≈ $75k at N 30; at the $25k funding floor it could hold ten names, where the random-list spread is already wider than the premium; 20 % of the universe (146 names) could not be mapped to a filer.

**Decision.** Nothing changes. No self-built quality sleeve: on the pre-registered design the premium does not survive equal weighting against SPY, is at the random median out of sample at the primary size, the selection rule does not walk forward, the sleeve costs the book, and the account could not hold it at its funding floor. What was learned and kept: the free SEC pipeline works and is point-in-time (and now exists — `fetch_sec_facts.py`, `qualpick.annual_records`); the premium is in the data (+1.2 … +1.5 over the universe, the bottom third losing); the equal-weight effect of this decade is larger than the premium; a profitability ratio over book equity is partly a buyback-giant ranking. **What is *not* closed, and is cheap**: the value-weighted picks beat SPY by 2 … 3 pp/yr, three of four cells in both halves — a result that was a reference line here and would need its own pre-registered stage 2 with the confound answered first (the picks' excess regressed on SPMO's and on a size factor; the ranking done within size buckets or with weights capped; the GPA collapse explained; the walk-forward on the weighted cells; the sleeve with weighted picks; the dust floor at the funding level). Prior ≈ 40 % that it is quality rather than the decade's leaders; an afternoon on data in hand. The paid long-history extension stays parked and is not worth buying unless stage 2 survives. The operator's call; the roadmap's next afternoon tests (B5 / B6 / B7) are the alternative.

**Scripts / docs**: `scripts/param_search/qualpick.py` (pre-registration `a086fdc`, then the code, three runs), `fetch_sec_facts.py`, `screens.simulate(score_matrix, weights)`, the harness README rows; roadmap Track H (stage 1 ✅, stage 2 💡, the paid item's note); todo Phase 2.16; two insights; handover note. Data: `external/sec_facts/` (118 MB, free, re-fetchable in six minutes; archived on titanserver at the next checkup).

### Decision 076 addendum — the quality stage 2: the value-weighted picks were Apple, Nvidia and Lilly; no alpha survives a size control, a 5 % cap removes the gain, the sleeve fails — the quality door closes (operator: "stage 2", 2026-10-30)
`scripts/param_search/qualpick2.py` — checks T1–T6, expected numbers and drop rules **committed before the run** (`64af97c`); the stage-1 pipeline and data, nothing new fetched; `screens.simulate` weights (raw, capped at 5 % with the excess redistributed, equal). **Nothing live changes.**

**T1 — the confound measured** (each line's daily excess over SPY on SPMO's excess, the size tilt = the value-weighted minus the equal-weight hold of the scored set, and French RMW; alpha in pp/yr with its t; July | January):

| line | β SPMO | β size | β RMW | α (t) | R² | holdings |
|---|---|---|---|---|---|---|
| top 50 by OP, value-weighted raw (stage 1's line) | −0.05 \| −0.06 | +0.23 \| +0.54 | +0.16 \| +0.15 | **+1.6 (0.7) \| +0.8 (0.4)** | 0.11 \| 0.27 | top-5 share 54 % \| 60 %; 2026: NVDA 33 %, AAPL 30 %, LLY 8 % |
| top 30, value-weighted raw | −0.12 \| −0.06 | +0.24 \| +0.62 | +0.20 \| +0.16 | +3.0 (1.0) \| +1.1 (0.4) | 0.11 \| 0.26 | **top-5 share 66 % \| 72 %; AAPL 57 %, LLY 15 % \| NVDA 39 %, AAPL 34 %** |
| top 50, capped at 5 % | −0.04 \| −0.03 | −0.08 \| −0.14 | +0.21 \| +0.19 | **−1.1 (−0.5) \| −0.2 (−0.1)** | 0.11 \| 0.12 | top-5 share 25 % |
| top 50 within size quintiles, value-weighted | −0.06 \| −0.07 | +0.18 \| +0.56 | +0.21 \| +0.14 | +1.8 (0.7) \| +0.6 (0.2) | 0.10 \| 0.24 | |
| top 50 by OP / assets, value-weighted raw | −0.04 \| −0.09 | +0.24 \| +1.01 | +0.10 \| +0.10 | +1.7 (0.7) \| +1.8 (0.8) | 0.08 \| 0.53 | |
| the largest 50 by market value, no profitability (T3) | −0.14 \| −0.08 | +0.80 \| +0.86 | +0.07 \| +0.04 | −0.4 (−0.2) \| −0.5 (−0.4) | 0.63 \| 0.76 | |

No alpha survives: after SPMO and the size tilt every t is between −0.5 and +1.2 (the bar was t > 2). The picks are not momentum (β SPMO ≈ 0), they are quality-tilted (β RMW +0.1 … +0.2, the ETFs' range) and they are two or three companies: the top-30 portfolio was 57 % Apple and 15 % Lilly in July 2026, the top-50 a third Nvidia and a third Apple. As pre-registered: a profitability ratio over book equity ranks the buyback giants first.

**T2 / T3 — the confound removed by construction, and the size-only control** (excess vs SPY; IS / OOS; July | January):

| line | July | January |
|---|---|---|
| value-weighted hold of the scored set (ref) | −0.92 (−1.1 / −0.7) | +1.05 (+3.2 / −1.1) |
| **the largest 50 by market value, no profitability (T3)** | −0.08 (+0.4 / −0.5) | **+2.32 (+4.7 / +0.0)** |
| top 50 by OP, value-weighted raw · top 30 | +1.78 (+4.4 / −0.6) · +3.05 (+5.2 / +1.1) | +2.65 (+3.7 / +1.6) · +2.99 (+3.3 / +2.6) |
| **top 50 capped at 5 % · top 30 capped** | **−1.20 (+1.8 / −3.8)** · +0.49 (+3.9 / −2.5) | **−0.54 (+1.2 / −2.2)** · +0.33 (+4.4 / −3.6) |
| top 50 within size quintiles: equal-weight · value-weighted · value-weighted capped | −0.57 (+2.1 / −2.9) · **+1.97 (+1.6 / +2.3)** · −0.22 (+1.5 / −1.7) | −1.08 (+2.8 / −4.8) · +2.16 (+2.8 / +1.5) · −0.96 (+2.3 / −4.1) |
| top 50 by OP / assets: value-weighted raw · capped · equal-weight | +1.66 (+3.9 / −0.3) · −0.22 (+2.2 / −2.3) · +1.41 (+6.6 / −3.1) | +5.09 (+9.6 / +0.7) · +0.11 (+2.9 / −2.6) · +0.11 (+5.6 / −5.1) |

The cap is the whole story: every uncapped value-weighted line beats SPY and every capped one loses it out of sample (−1.7 … −4.1), the within-size and the over-assets variants included. The one clause of the drop rule the letter of the numbers meets — the within-size value-weighted top 50 positive in both halves (+1.97 / +2.16) — is the same construction uncapped (its size loading +0.18 … +0.56, its alpha t 0.7 / 0.2, its capped twin −0.22 / −0.96), so the clause is met by the giants, not by quality. The size-only control (the fifty largest names, no profitability at all) made +2.3 in the January window on its own.

**T4 — the weighted family, 24 cells** (N 30 / 50 × anchor × raw / capped / within-size × OP / OP-over-assets, excess vs SPY): marginals value-weighted raw +2.76, within-size +2.07, **capped +0.22**; OP +1.87 vs over-assets +1.65; N and anchor within a point. Ten of 24 cells positive in both halves — every one of them uncapped; no capped cell is. The walk-forward inside the family passes weakly (the in-sample-best cell, N 50 January raw over-assets +9.6, is +0.7 out of sample against a median of −0.4; by out-of-sample the pick is N 30 January within-size OP, +3.3 → +4.4 in-sample) — the family is "hold the largest profitable names uncapped", which a sleeve cannot be.

**T5 — the sleeve** (vs SPY, 2017-07-03 → 2026-10-12; the book over the same window +1.31 (+0.0 / +2.5), Sharpe 1.07, through 2025 +0.72): with the pre-named capped top 50, dip 20 / SPMO 60 / picks 20 **+0.64 (−0.1 / +1.3), Sharpe 1.05, through 2025 +0.10**; dip 40 / SPMO 40 / picks 20 +0.33, 1.08, 0.00; with the within-size value-weighted top 50 (the secondary) +1.35 (−0.0 / +2.6), 1.08, +0.63 and +1.04 (+0.3 / +1.7), 1.11, +0.52 — none better in both halves and through 2025. Fails on all four.

**T6 — the dust floor**: with capped weights the smallest of the fifty positions is 0.07 … 0.10 % of the sleeve — **$5 at $25k and $20 at $100k** against the $500 floor; a cap-weighted 50-name sleeve is untradeable at any size the account will have; turnover 39 % a year.

**Decision.** Nothing changes, and the quality question is closed on free data: the premium is real (Decision 075), the funds do not capture it (075 addendum), our equal-weight picks give it back to the equal-weight drag (076), and our value-weighted picks were the decade's leaders (this addendum). Prior 30 % that it was quality; the answer is no. The paid long-history extension is not bought. Kept: the free SEC pipeline (`fetch_sec_facts.py`, `qualpick.annual_records`, `screens.simulate` with scores and weights) for any later single-name question; and the lesson that a sleeve test must name its weighting and then show the premium is not the weighting. **Next: B5 / B6 / B7.**

**Scripts / docs**: `scripts/param_search/qualpick2.py` (pre-registration `64af97c`, then the code), the README row; roadmap Track H (stage 2 ✅ → closed, the paid item's note, Track D's quality row); todo Phase 2.16; the insight extended; handover note.

## Decision 075: Quality over a century — the premium is real, old and long-only capturable; no sleeve (no investable vehicle, and the bar missed by a hair), and the dip rule loses on quality portfolios as on any portfolio, so the fundamentals pipeline (B9) is closed (roadmap B2, operator's go, 2026-10-30)
**Date**: 2026-10-30
**Why**: "quality" (steadily profitable companies that invest conservatively) is the one documented premium the book has never held, and roadmap B9 (a fundamentals pipeline for a single-name dip universe) rests on whether profitability separates a dip from a break. Done the Decision 062 way: hypotheses Q1–Q6 and the drop rules written into `scripts/param_search/quality.py` and **committed before any code ran** (`05b4144`); loaders `datasets.french_levels(…, sub="external/french")`, `french_factors`, `aqr_qmj`. Data: Kenneth French's daily portfolios on operating profitability (OP) and investment (INV), the 25 size × profitability portfolios and the five-factor file (RMW, CMA), 1963-07 → 2026-09; AQR's Quality-Minus-Junk (US) daily 1957-07 →; QUAL on the decade. Windows: 63y 1963-07 → 2026-08 (split 1995; eras 1963–75 / 1975–2000 / 2000–26), QMJ 1957 → (split 1992), the ETF decade (split 2022, through 2025 beside full). Book = `carry.sets()` (the century book on the long window; the sector-dip / SPMO book on the decade), exposure = min(insurance ×0.5, shock ×0.5). **Nothing live changes.**

**Verdict on the pre-registered rules: Q1 and Q2 hold (the premium is real, old, defensive and capturable long-only); Q3 fails the momentum-sleeve bar on every variant (one by a hair); Q6 fails (QUAL did not beat SPY in either half) → no quality sleeve; the B9 gate is closed (the dip rule is negative on high- and low-profitability portfolios alike and the gap flips sign between halves).** The expectations were right on the premium's size and shape and wrong on two things: quality's excess is *uncorrelated* with momentum's (−0.02 full, +0.23 only in the first half) and with the dip sleeve's (−0.03) — a genuine diversifier — and the top-30 % portfolio is positive in *every* era, not just both halves.

**Q1 — the premium, long-short** (annualised mean, halves, eras; t, Sharpe; beta to the market, correlation with the momentum factor; compounded in 2000–02, the 2003 rally, 2008, the 2009 rally):

| factor | mean | halves | eras | t / Sharpe | beta / corr. mom | 2000–02 · 2003 · 2008 · 2009 |
|---|---|---|---|---|---|---|
| **RMW** profitability (1963 →) | **+3.1** | +2.5 / +3.7 | +0.4 / +3.0 / +4.3 | 3.7 / 0.47 | −0.09 / +0.05 | +139 · −15 · +30 · −2 |
| CMA investment (1963 →) | +3.0 | +4.0 / +1.9 | +4.4 / +2.8 / +2.5 | 3.9 / 0.49 | −0.13 / +0.02 | +73 · +13 · −1 · +4 |
| **QMJ** quality-minus-junk (1957 →) | **+3.7** | +3.6 / +3.8 | +3.0 / +4.1 / +3.9 | 4.3 / 0.52 | −0.19 / +0.20 | +103 · −21 · +59 · −25 |
| Mom momentum (reference) | +7.2 | +9.1 / +5.2 | +11.4 / +9.3 / +3.4 | 4.5 / 0.57 | −0.09 / 1.00 | +56 · −20 · +43 · **−55** |
| HML value (reference) | +3.7 | +5.3 / +2.1 | +5.6 / +3.8 / +2.8 | 3.2 / 0.40 | −0.10 / −0.27 | +103 · +9 · −22 · +33 |

Holds: positive in both halves and every era (RMW's 1963–75 at +0.4 is the doubtful era, as pre-registered), t 3.7–4.3, negative beta, defensive — it *made* money in 2000–02 and 2008 and gave some back in the junk rallies, and its 2009 (−25 for QMJ) is half of momentum's crash (−55). The premium is about half of momentum's and steadier.

**Q2 — the long-only form held vs the market, 63 years** (excess CAGR; IS / OOS; σ relative to the market; DD vs −54.6; Sharpe vs 0.72; worst year; eras):

| portfolio | excess | IS / OOS | σ/σm | DD | Sharpe | worst yr | eras 1963–75 / 75–2000 / 2000–26 |
|---|---|---|---|---|---|---|---|
| OP Hi 10 (top profitability decile) | +1.19 | +0.2 / +2.2 | 1.03 | −54.6 | 0.77 | −18.2 | +0.2 / −0.1 / +2.7 |
| **OP Hi 30** | **+1.22** | **+0.8 / +1.6** | 1.00 | **−49.9** | 0.79 | **−7.3** | **+1.2 / +0.9 / +1.5** |
| OP Med 40 · Lo 30 · Lo 10 | −0.07 · −2.26 · **−3.52** | | 1.00 · 1.14 · 1.37 | −60 · −74 · −85 | 0.72 · 0.54 · 0.43 | | |
| **INV Lo 30** (conservative investment) | **+2.21** | +3.0 / +1.4 | 0.99 | −54.5 | **0.85** | −16.7 | +1.2 / +2.6 / +2.3 |
| INV Lo 10 · Hi 30 · Hi 10 | +2.11 · −0.76 · −2.84 | | 1.09 · 1.13 · 1.29 | −60 · −66 · −76 | 0.78 · 0.62 · 0.48 | | |
| top momentum decile (the sleeve) | +6.12 | +8.6 / +3.7 | 1.36 | −56.4 | 0.82 | −35.0 | +11.2 / +7.5 / +2.7 |
| dip sleeve alone (reference) | +0.29 | +0.5 / +0.1 | 1.16 | −59.4 | 0.66 | −21.2 | +0.6 / −0.8 / +1.1 |

Holds, better than expected: the top 30 % by profitability beat the market by 1.2 pp/yr in every era at the market's volatility with a 5-point smaller drawdown and a −7 % worst relative year; conservative investment by 2.2; the bottom decile lost 3.5 (the test has teeth). Long-only quality is about a third of the long-short premium, as expected, and the steadiest long-only excess in the harness.

**Q3 — quality (OP Hi 30) as a sleeve beside the century book, 63 years** (quality's excess vs momentum's −0.02, vs the dip sleeve's −0.03; de-risked 27 %):

| book | excess | IS / OOS | σ/σm | DD | Sharpe | worst yr | eras |
|---|---|---|---|---|---|---|---|
| **dip 40 / mom 60 (the book)** | **+3.47** | +5.8 / +1.2 | 0.98 | −35.6 | 0.93 | −14.8 | +9.1 / +3.3 / +1.2 |
| dip 40 / mom 40 / quality 20 (from momentum) | +2.50 | +4.3 / +0.7 | 0.90 | −34.6 | 0.93 | −11.8 | +7.2 / +2.0 / +0.9 |
| dip 30 / mom 50 / quality 20 | +3.09 | +5.0 / +1.2 | 0.92 | −34.0 | 0.95 | −13.2 | +8.2 / +2.7 / +1.2 |
| **dip 20 / mom 60 / quality 20 (from the dip sleeve)** | **+3.65** | **+5.8 / +1.6** | 0.95 | −36.1 | **0.96** | −17.0 | **+9.2 / +3.5 / +1.4** |
| dip 40 / mom 0 / quality 60 (instead of momentum) | +0.45 | +1.3 / −0.4 | 0.79 | −34.1 | 0.91 | −16.7 | +3.4 / −0.7 / +0.2 |
| quality 100 % under the exposure rules | +0.73 | +1.2 / +0.2 | 0.75 | −34.0 | 0.96 | −11.1 | +3.6 / −0.4 / +0.5 |

Fails the bar (return better in both halves *and* every era, Sharpe no lower) on every variant — but one by a hair, and it is recorded: **quality in place of half the dip sleeve** is +0.18 pp/yr better over 63 years, better out of sample (+1.6 vs +1.2), better in all three eras, Sharpe 0.96 vs 0.93, and equal to the decimal in-sample (the strict inequality failed), at the price of a worse worst year (−17.0 vs −14.8) and 0.5 point more drawdown. Taking quality from momentum costs a point (momentum's +6 is the bigger premium); quality instead of momentum costs 3. The reading: quality is a second, uncorrelated, steadier diversifier of the momentum sleeve, and on the century it is at least as good as the dip sleeve's residual-plus-dips at smoothing it — the dip sleeve's job (Decision 067: "Sharpe and drawdown, not return") can be shared.

**Q4 — the live dip rule on quality portfolios, 63 years (the B9 gate)** — the rule (3 × 25 %, market residual, insurance ×0.5 from the universe's own breadth) on French portfolio universes, each vs the market and vs holding the universe equal-weight:

| universe | vs the market | vs its EW hold | EW hold vs the market | trades / yr · win · median · tp / stop / clock |
|---|---|---|---|---|
| **10 high-profitability** (size × OP4–5) | **−1.66** (−1.0 / −2.3); eras +2.4 / −3.8 / −1.5 | **−3.96** (−3.7 / −4.2) | **+2.30** (+2.7 / +1.9) | 3.4 · 66 % · +4.3 % · 20 / 30 / 167 |
| **10 low-profitability** (size × OP1–2) | **−1.63** (−0.3 / −3.0); +2.2 / −2.2 / −2.8 | −1.63 (−1.4 / −1.8) | −0.00 (+1.2 / −1.2) | 4.2 · 57 % · +2.7 % · 29 / 56 / 181 |
| all 25 size × OP | −1.70 (−1.4 / −2.0) | −3.06 | +1.36 | 5.1 · 61 % · +4.2 % |
| 10 OP deciles · 10 INV deciles | −0.51 · −0.74 | −0.41 · −1.55 | −0.10 · +0.81 | 2.5 · 66 % · 2.4 · 67 % |
| 49 industries, same window (the floor) | −0.85 (+0.1 / −1.8); +2.3 / −2.7 / −0.5 | −1.45 | +0.60 | 11.6 · 56 % · +2.0 % · 139 / 197 / 393 |
| high-OP minus low-OP, vs the market | **−0.03 (IS −0.7 / OOS +0.7; eras +0.2 / −1.6 / +1.2)** | | | |

Closed. The rule loses on profitable and unprofitable portfolios alike, the gap between them is zero and flips sign between halves and eras, and on the high-profitability portfolios the rule gives back 4 points a year against simply holding them (which beat the market by 2.3 in both halves). The portfolios' dips are rarer than the industries' (3 trades a year) and most exits are the clock, with stops outnumbering targets; 66 % winners is the diversified-basket texture, not single names — and the return still is not there. **Profitability does not separate dips from breaks at the portfolio level; like momentum (Decision 066), quality is harvested by holding, not by buying its dips.** B9 — the fundamentals pipeline, the SEC data sets, the single-name door — stays closed.

**Q5 — the crash leg** (minus the market, peak → trough / the rebound year; market absolute):

| | 1973–74 | 1987 | 2000–02 | 2008 | 2020 | 2022 |
|---|---|---|---|---|---|---|
| market | −48 / +42 | −33 / +28 | −49 / +39 | −55 / +75 | −34 / +87 | −25 / +21 |
| OP Hi 30 held | −2 / −2 | −1 / +1 | **+10 / −11** | **+9 / −9** | +2 / −5 | +0 / +9 |
| top momentum decile held | +6 / +6 | −4 / −4 | +0 / +5 | +2 / **−27** | +2 / −9 | +3 / +0 |
| dip sleeve alone | +4 / +14 | +1 / −9 | +49 / +15 | −3 / +13 | −4 / +45 | +11 / −9 |
| book (dip 40 / mom 60) | +21 / −0 | +11 / −17 | +17 / −0 | +21 / −26 | +12 / −16 | +11 / −11 |
| book with quality 20 from momentum | +20 / −2 | +11 / −17 | +20 / −4 | +22 / −25 | +12 / −15 | +11 / −10 |

Quality protects in the slow bears (+9 … +10 in 2000–02 and 2008) and gives it back in the rebound year; nothing in the fast crashes (1987, 2020). Its 2009 is −9 against momentum's −27 — the cousin that does not crash. Inside the book the difference is a point or two either way.

**Q6 — the decade, investable** (QUAL's excess vs SPMO's −0.16, vs the dip sleeve's +0.04):

| | excess vs SPY | IS / OOS | → 2025 | DD | Sharpe |
|---|---|---|---|---|---|
| **QUAL held** | **−0.73** | **−0.4 / −1.1** | −0.83 | −34.1 vs −33.8 | 0.85 vs 0.89 |
| SPMO held (reference) | +5.23 | +2.1 / +8.4 | +4.46 | −31.2 | 1.00 |
| the book | +1.36 | +0.3 / +2.5 | +0.80 | −20.0 | 1.10 |
| dip 40 / SPMO 40 / QUAL 20 | +0.44 | −0.1 / +1.0 | +0.04 | −20.4 | 1.10 |
| dip 40 / SPMO 0 / QUAL 60 | −1.55 | −0.9 / −2.2 | −1.61 | −21.3 | 1.02 |

Fails, as Decision 067 found: the one quality ETF in the library lost to SPY in both halves, so the century's +1.2 … +2.2 has no investable form in hand. In the book it costs 0.9 pp/yr for the same Sharpe — the expected shape.

**Decision.** Nothing changes. Roadmap B2 done, B9 closed, Track D's "quality / low-beta" door closed with numbers, C2 "fundamentals" closed. What was learned and kept: the quality premium is real and sixty years old, defensive (it made money in 2000–02 and 2008), half the size of momentum's and uncorrelated with both sleeves; its long-only form (the top 30 % by profitability, conservative investment) beats the market by 1–2 pp/yr in every era with a smaller drawdown; buying its dips throws that away. **What would reopen a quality sleeve, and it is cheap**: an investable vehicle that beat SPY in both decade halves — only QUAL (MSCI USA Quality) is in the library and it did not; SPHQ (S&P 500 Quality, 2005 →), JQUA, DGRW and the Dimensional / Avantis profitability-tilted funds are not fetched (Track H, one `download-history` on the server). If one of them captures the century's +1.2 … +2.2, the near-pass above (quality in place of half the dip sleeve: +0.2 pp/yr, better out of sample and in every era, Sharpe 0.96 vs 0.93, a worse worst year) becomes a pre-registered test with an instrument; without one it is knowledge. **Next pick: B5 / B6 / B7** — the cheap afternoon tests (credit stress as a second insurance signal, a VIX shock trigger, gold over a century), in that order.

**Scripts / docs**: `scripts/param_search/quality.py` (pre-registration `05b4144`, then the code), `datasets.french_levels(sub)` / `french_factors` / `aqr_qmj`, the harness README row; roadmap B2 ✅ / B9 🚫 / D closed / C2 closed / H quality ETFs; todo Phase 2.15; one insight; handover note.

### Decision 075 addendum — the quality funds as vehicles: twelve fetched and tested, none captures the premium (operator: "fetch quality funds first", 2026-10-30)
`scripts/param_search/quality_etfs.py` — **the candidate list and hypotheses V1–V3 were committed before the fetch** (`b2c914f`): every quality-labelled US equity ETF on Alpaca with SIP history from 2016 (SPHQ, QUAL, VIG, DGRW, DGRO, QDF, QDEF, QUS, FQAL, COWZ, MOAT, JQUA). Eleven fetched on titanserver with the data API only (SIP, `adjustment=all`, dividend-adjusted like the archive; `alpaca_hist/quality/`, archived as `archive/param_search/alpaca_quality/`), QUAL from the library. Decade 2017-01-03 → 2026-10-12, split 2022, each fund from its first bar (MOAT 2016-05, FQAL 2016-09, COWZ 2016-12, JQUA 2017-11), through 2025 beside full. **Nothing live changes.**

**V1a — the era**: the premium was there to capture. Over the same decade the French top-30 %-profitability portfolio beat the French market by **+1.62 pp/yr** (+2.8 / +0.5; through 2025 +2.0) and the top decile by **+3.45** (+4.1 / +2.8; +3.8), and the French market matched SPY to the decimal (15.27 vs 15.30 %/yr) — so against SPY the hindsight-free quality portfolios read +1.6 and +3.4, the decile positive in both halves.

**V1b — the funds held vs SPY** (excess CAGR; IS / OOS; through 2025; the dividend-growth family as pre-registered):

| fund | excess | IS / OOS | → 2025 | Sharpe vs 0.89 | worst yr | from |
|---|---|---|---|---|---|---|
| JQUA (JPMorgan quality factor) | +0.13 | −0.4 / +0.6 | −0.55 | 0.88 (SPY 0.84 on its window) | −6.0 | 2017-11 |
| SPHQ (S&P 500 Quality) | −0.63 | −0.9 / −0.4 | −0.67 | 0.85 | −4.5 | 2017-01 |
| QUAL (MSCI USA Quality) | −0.73 | −0.4 / −1.1 | −0.83 | 0.85 | −5.1 | |
| FQAL (Fidelity quality factor) | −0.89 | −0.2 / −1.6 | −0.81 | 0.85 | −3.8 | |
| DGRW · QUS · MOAT | −1.22 · −1.53 · −1.69 | −1.0 / −1.4 · −1.2 / −1.8 · +0.1 / −3.4 | −0.97 · −1.42 · −0.73 | 0.89 · 0.86 · 0.77 | | |
| VIG · DGRO · COWZ | −2.03 · −2.08 · −2.06 | −1.1 / −2.9 · −1.6 / −2.5 · −2.1 / −2.0 | −1.70 · −2.10 · −2.27 | 0.85 · 0.83 · 0.73 | | |
| QDEF · QDF | −3.29 · −3.85 | −5.9 / −0.6 · −6.3 / −1.3 | −3.41 · −4.13 | 0.78 · 0.71 | | |
| SPMO (the momentum sleeve, reference) | +5.23 | +2.1 / +8.4 | +4.46 | 1.00 | −7.2 | |

**0 of 12 beat SPY in both halves** (three were expected by luck alone; none happened), and all twelve are behind SPY through 2025. The pre-registered shape held: the dividend-growth family −1.2 … −3.9 (a value tilt in a growth decade), SPHQ and FQAL within ±1.5, COWZ −2.1, MOAT −1.7.

**V2 — are they quality?** Each fund's daily excess over SPY regressed on French RMW and SPMO's excess: β RMW SPHQ +0.10 (t 8.4), QUAL +0.07 (7.4), VIG +0.24 (20.2), DGRW +0.24 (24.3), DGRO +0.27 (20.4), QDF +0.16, QDEF +0.23, QUS +0.16, FQAL +0.08 (9.9), COWZ +0.19 (8.3), JQUA +0.05 (3.2), MOAT −0.03 (−2.2; a moat fund is not a profitability fund); alphas −0.2 … −3.4 %/yr, MOAT +0.5; six meet the V2 definition (loading, t, correlation with QUAL > 0.3). They *are* quality exposures — diluted: a fund tracking the top 30 % outright would load about 0.4–0.5 on RMW; these load 0.05–0.27, and multi-metric screens (return on equity, leverage, earnings variability), sector caps and fees (0.15–0.5 %) absorb the rest, with a negative alpha left over in every case but one.

**V3** not reached (no survivor). For the record, JQUA or SPHQ in place of half the dip sleeve: +0.72 vs the book's +1.36, Sharpe 1.03–1.06 vs 1.10, through 2025 ≈ 0.

**Decision.** Nothing changes; the quality door stays closed. What was learned: the quality premium was alive this decade in its hindsight-free form and no fund delivered it — **the vehicle is not the premium**, as MTUM was not SPMO (Decision 067). The only route left to the century's result is a *held* profitability sleeve built from point-in-time fundamentals (the top 30 % by operating profitability, rebalanced yearly) — the B9 data for a purpose other than the one B9 was closed for — which would meet Decision 067's objection to self-picked sleeves (fitted selection parameters, no long investable history) and is **not proposed**; recorded in Track H as what it would take. Next: B5 / B6 / B7.

*Operator, after the report (2026-10-30)*: "if the data clearly says it is profitable, diversifies and stands the test of time, why not do it" — and, on being told the implementation needs company accounts we do not have: **always look for a free version first; what exists only as paid data goes to the back of the roadmap with the other paid-data items, to be bought once and together.** Free sources probed the same day: the SEC's XBRL `companyfacts` / `frames` APIs and financial-statement data sets (every US filer, point-in-time by filing date, all filers from 2010-Q4, large filers from 2009; the tag cleaning is 1–2 days of work), the S&P 500 membership mask from 1996 (in hand); SimFin's free tier (5 years), Open Source Asset Pricing's firm-level files (no tickers without CRSP), QuantShare's old scraper — none reaches the 1990s or 2008 free. **Split accordingly**: the quality stage 1 (do 30–50 self-picked names keep the premium the French portfolio shows over the same window, vs random lists, walk-forward of the selection rule) is *ready on free data for 2010 → 2026* and listed in Track H as a 1–2 day item on the operator's call; the long-history confirmation (2000–02, 2008) needs paid fundamentals (EODHD ~€20 / month covers it with the other price needs; Sharadar is the strict point-in-time alternative) and sits in the new "needs paid data" group at the back of the roadmap. The rule itself is recorded in the roadmap's preamble and the handover.

## Decision 074: Put-writing and the collar indices — tested on 40 years of Cboe data, nothing adopted; option writing is a Sharpe tool not a return tool, and bought protection costs more than the two free signals (roadmap B1, operator's go, 2026-10-29)
**Date**: 2026-10-29
**Why**: brainstorm #32 ("sell a put at the dip level") and the collar-as-insurance idea were untestable until Decision 072 fetched Cboe's option-strategy benchmarks. Done the Decision 062 way: hypotheses O1–O5 and the drop rules written into `scripts/param_search/putwrite.py` and **committed before any code ran** (`cf51d75`); loader `datasets.cboe`. Indices (total return on the S&P 500): BXMD (buy-write, 30-delta call), BXY, CMBO, CNDR, BFLY, RXM, PPUT (long S&P + 5 % OTM put) daily from 1986-07; BXMC 1990 →; BXM 2003 →; **PUT (the cash-secured put-write) daily only from 2007** (Decision 072's "1991 →" was sparse points); WPUT 2006 →; CLL (collar 95 / 110) 2008-09 →. Windows: 40y 1986-07 → 2026-08 (split 2006-07, four decades), 20y 2007 → 2026-08 (split 2017), CLL 2008-09 → (split 2017-07), the ETF decade 2017 → 2026-10 (split 2022, through 2025 beside full). Market = Kenneth French's VW market on the long windows (the century book's market; ≈ 0.3 pp/yr from the S&P 500), SPY on the decade. Book = `carry.sets()` (the century book: dip on 49 industries 40 / top momentum decile 60; the decade book: sector dip 40 / SPMO 60), exposure = min(insurance ×0.5, shock ×0.5), idle capital at 0 unless stated. **Nothing live changes.**

**Verdict on the pre-registered rules: O2 (an option-writing sleeve) fails on every window and every weight; O3 (a put or collar as the insurance) fails on every window → no sleeve, no put insurance.** The expectations written before the run were right on the shape and wrong on two numbers: PUT did *not* keep pace with the market since 2007 (−4.0 pp/yr, not ±1), and the writing index is mildly *diversifying* (correlation −0.06 … +0.15 with the dip sleeve's excess, not +0.2 … +0.4) — which still did not rescue the return bar.

**O1 — the indices alone vs the market** (excess CAGR pp/yr; IS / OOS at the window's midpoint; σ/σm = volatility relative to the market):

| index (window) | excess | IS / OOS | σ/σm | DD vs market | Sharpe vs market | worst yr | decades 1986–96 / 96–06 / 06–16 / 16–26 |
|---|---|---|---|---|---|---|---|
| **PUT** put-write (2007 →) | **−4.01** | −1.3 / −7.0 | 0.69 | −37 vs −55 | 0.57 vs 0.63 | −21 | |
| WPUT weekly put-write (2007 →) | −6.87 | −2.3 / −11.8 | 0.62 | −29 vs −55 | 0.41 | −31 | |
| BXM at-the-money buy-write (2007 →) | −5.17 | −3.1 / −7.4 | 0.72 | −40 vs −55 | 0.48 | −26 | |
| **BXMD** 30-delta buy-write (1986 →) | **−0.43** | +1.8 / −2.6 | 0.88 | −47 vs −55 | **0.72 vs 0.67** | −18 | +1.7 / +1.9 / −0.6 / −4.7 |
| BXY 2 % OTM buy-write (1988 →) · BXMC (1990 →) | −1.08 · −1.59 | +0.9 / −3.0 · +1.0 / −4.2 | 0.90 · 0.74 | −45 · −42 | 0.70 · 0.76 | | |
| CMBO · CNDR · BFLY · RXM (1986 →) | −1.73 · −5.72 · −7.50 · −3.12 | | 0.76 · 0.44 · 0.63 · 0.64 | −43 · −20 · −55 · −31 | 0.72 · 0.69 · 0.37 · 0.72 | | all four negative in 2006–26 |
| **PPUT** protective put (1986 →) | **−3.08** | −3.2 / −2.9 | 0.75 | **−42 vs −55** | 0.64 vs 0.67 | −19 | −2.6 / −3.8 / −2.8 / −3.1 |
| **CLL** collar (2008-09 →) | **−5.69** | −8.0 / −3.3 | 0.64 | **−25 vs −46** | 0.59 vs 0.69 | −29 | |

On the ETF decade vs SPY every index loses 2.9 … 18 pp/yr (PUT −6.8, BXMD −4.4, PPUT −2.9, CLL −3.4), the two protective ones with the best Sharpes (0.98 / 0.97 vs 0.89) and half the drawdown. Readings: the published "put-write ≈ the S&P at two thirds of the volatility" was true of 1986–2006 and has not been true since — on the twenty years we have daily, PUT lagged by 4 points a year and by 7 in the last decade; the buy-write that keeps some upside (a 30-delta call) is the only writing index that kept pace over 40 years, and only in the first half; buying protection every month (PPUT) cost 3 points a year in every decade for a drawdown a quarter smaller; the collar cost 5.7 for half the drawdown.

**O2 — an option-writing sleeve beside the book** (the sleeve scaled by the exposure rules like the rest; "corr." = the index's excess over the market against the dip sleeve's / momentum's excess):

| window, OPT (corr. dip / mom) | book 40 / 60 | dip 20 / mom 60 / OPT 20 | dip 40 / mom 40 / OPT 20 | dip 0 / mom 60 / OPT 40 | OPT replacing momentum | OPT alone under the rules |
|---|---|---|---|---|---|---|
| 40y, BXMD (−0.06 / −0.16) | +1.54 (+3.7 / −0.6), DD −35.6, Sh 0.77, worst −15; decades +2.9 / +4.4 / −0.3 / −0.9 | +1.58 (+3.5 / −0.4), DD −35.2, **Sh 0.80**, worst −18; +3.3 / +3.8 / +0.7 / −1.5 | +0.62, Sh 0.79 | +1.57 (+3.3 / −0.2), DD −38.0, **Sh 0.84**, worst −22; +3.6 / +3.1 / +1.7 / −2.1 | −1.44 | −1.55, Sh 0.87, DD −31.6 |
| 20y, PUT (−0.14 / −0.10) | +0.06 (+1.2 / −1.2), DD −35.6, Sh 0.66 | −0.00 (+1.9 / −2.0), DD −32.2, Sh 0.70 | −1.14 | −0.14 (+2.5 / −3.0), DD −28.7, Sh 0.74 | −3.86 | −4.34, Sh 0.77 |
| decade, PUT (+0.15 / 0.00) | +1.36 (+0.3 / +2.5), DD −20.0, Sh 1.10; → 2025 +0.80 | −0.22 (−2.0 / +1.6), DD −19.3, Sh 1.07; −0.80 | −0.53, Sh 1.11 | −1.81 (−4.3 / +0.7), Sh 1.03 | −4.42 | −7.58 |

Fails everywhere on the pre-registered bar (return better in both halves and every era, Sharpe no lower). What the table says instead: **option writing is a Sharpe tool, not a return tool.** Over 40 years a BXMD sleeve in place of the dip sleeve is a wash on return (+1.57 vs +1.54) with the Sharpe 0.77 → 0.84 and a worse worst year (−22 vs −15); over 20 years PUT in the dip sleeve's place is flat on return with the Sharpe 0.66 → 0.70; on the decade every PUT variant costs 1.6 … 1.9 pp/yr for nothing. The surprise is the correlation: the writing index's excess is slightly *negatively* correlated with the dip sleeve's and with momentum's on the long windows, so it is a different bet, not a copy — a diversifier that does not earn its place. (Trading it needs Alpaca options approval and SPY options rolled monthly; the index assumes VWAP fills, a retail fill is worse — so the real-money version is below every number here.)

**O3 — a protective put or a collar as the insurance instead of cash** (the idle 1 − e share held in the index; "on the market" isolates the mechanism from the sleeves):

| window | on the market: rules + cash · + bills · + PPUT idle · PPUT permanent (· CLL idle · CLL permanent) | on the book: cash (the engine) · bills · the market · no insurance · PPUT idle (· CLL idle) |
|---|---|---|
| 40y (de-risked 25 %, bills 3.0 %) | −0.73 (DD −39) · −0.33 (−37) · **−0.05 (DD −49)** · −3.08 (−42) | **+1.54 (DD −35.6)** · +1.94 (−34.9) · +2.28 (−54) · +2.65 (−56) · **+2.24 (DD −48.0)**; decades +3.3 / +5.3 / −0.4 / +0.7 |
| CLL window 2008-09 → (22 %, 1.4 %) | −0.55 (−25) · −0.41 (−25) · +0.39 (−36) · −2.64 (−26) · CLL −0.24 (−34) · −5.69 (−25) | −0.80 (−27.8) · −0.66 (−27.6) · −0.24 (−46) · −0.11 (−46) · +0.15 (−36.4) · CLL −0.48 (−34.3) |
| decade (16 %, 2.5 %) | −2.27 (−21) · −2.11 (−21) · −0.26 (−25) · −2.85 (−22) · CLL −0.36 (−25) · −3.43 (−17) | +1.36 (−20.0) · +1.54 (−19.9) · +3.73 (−33) · +4.53 (−32) · **+3.45 (−22.8)**, +2.8 / +4.1, Sh 1.11 · CLL +3.35 (−23.8) |

Fails on every window on the drawdown leg (at most 2 points deeper than cash). The return side is as expected — the idle half in a protective put earns +0.7 vs cash and +0.3 vs bills over 40 years (it stays in the rebounds the cash misses) — but the drawdown is **12 points deeper over 40 years (−48 vs −36)** and 6–9 points deeper on the collar window, because a 5 % out-of-the-money put rolled monthly leaves the holder three quarters long: "idle in PPUT" is not de-risking, it is staying in with a small floor. On the decade the same line reads +3.45 vs +1.36 with the drawdown only 2.8 points deeper — the decade's known preference for less insurance (every loosening paid in 2017–2026, Decision 068 addendum) and still over the 2-point bar. **The permanent hedge is the clearest number of the day: buying a put every month for 40 years cost 3.1 pp/yr and left a −42 % drawdown; the book's two free signals cost 0.7 on the market (1.1 on the book vs no insurance) and left −39 / −36.** The rules beat the bought protection on both legs.

**O4 — the crash leg** (book minus the market, peak → trough / the rebound year after the trough; market absolute):

| | 1987 | 2000–02 | 2008 | 2020 | 2022 |
|---|---|---|---|---|---|
| market | −33 / +28 | −49 / +39 | −55 / +75 | −34 / +87 | −25 / +21 |
| **book (idle in cash)** | **+11 / −17** | **+17 / −0** | **+21 / −26** | **+12 / −16** | **+11 / −11** |
| book + BXMD 20 from the dip sleeve | +11 / −15 | +14 / −4 | +23 / −28 | +13 / −27 | +10 / −9 |
| book, idle in PPUT | +7 / −13 | +11 / +7 | +8 / −12 | +9 / −1 | +4 / −6 |
| PPUT permanently | +13 / −18 | +12 / −18 | +13 / −37 | +22 / −44 | +4 / −10 |
| CLL permanently | n/a | n/a | n/a | +19 / −50 | +8 / −10 |
| BXMD permanently | +4 / +6 | +13 / +2 | +8 / −5 | +2 / −27 | +3 / +0 |

The bought protection protects about as much as the rules in the fall (+12 … +22 vs +11 … +21) and loses far more in the rebound year (−37 / −44 in 2009 / 2020 vs −26 / −16): a put is paid for twice, in premium every month and in the rebound it is still short. Putting the idle half into the put instead of cash halves the fall protection (+4 … +11) and halves the rebound cost (−1 … −13): the same trade-off the insurance already makes, moved along the line, not improved.

**Decision.** Nothing changes. Roadmap B1 done; Track D's "put-writing" door is closed with numbers; C3 "options" is answered: no option-writing sleeve (a Sharpe tool at a return cost, below the both-halves-and-every-era bar everywhere), no put or collar insurance (deeper drawdowns than cash for the same return, and the permanent hedge loses to the free signals on both legs). What was learned and kept: the put-write index has lagged the market by 4 points a year since 2007 and the published claim is a 1986–2006 result; bought protection is paid back in the rebound year; the writing indices are mild diversifiers of both sleeves, which is worth knowing if a Sharpe-first book is ever wanted. What would reopen it: a put-writing *entry* (sell the put at the dip level and take assignment) needs single-name or SPY option chains, which the library does not hold (historicaloptiondata.com, ~$100 / year, Decision 072) — and the result here says the premium collected is not the missing return. **Next pick: B2** (quality over a century — French profitability and investment sorts, AQR QMJ).

**Scripts / docs**: `scripts/param_search/putwrite.py` (pre-registration `cf51d75`, then the code), `datasets.cboe`, the harness README row; roadmap B1 ✅ / D closed / C3 answered; todo Phase 2.14; one insight; handover note.

## Decision 073: The international book — tested, not built; the ex-US momentum premium is real, the dip rule on country ETFs is not a floor, and a blend gives back return for almost no protection (roadmap E2, operator's go, 2026-10-29)
**Date**: 2026-10-29
**Why**: the operator's second fear (a weaker US market after a political change, and a weaker dollar for a CZK-based investor) is the one risk a US-only book cannot hedge, and every number behind the live book is American. Roadmap E2 asked whether an ex-US copy of the book exists and whether blending it in helps. Done the Decision 062 way: hypotheses I1–I7 and the drop rules written into `scripts/param_search/intl.py` and **committed before any code ran** (`eb94dbc`); the ex-US book built exactly like the US one (the live dip rule on the 20 single-country ETFs, 3 × 25 % slots, ACWX as the residual and the index, insurance from the region's own breadth — ACWX below its 200-day SMA and fewer than half of the 20 countries above theirs — the shock trigger on ACWX, exposure = min); IMTM named as the book's momentum vehicle, IDMO as the alternative; decade 2017-01-03 → 2026-10-12 split 2022-01-01, every headline also through 2025-12-31; two placebos for the blend; costs as everywhere in the harness. Data: French regional daily factors 1990 → (USD), 39 ex-US ETFs 2016 → (Alpaca SIP, dividend-adjusted), FRED DEXUSEU. Loader `datasets.french_regional`. **Nothing live changes.**

**Verdict on the pre-registered rules: I1 and I2 hold, I3, I4 and I5 fail → no ex-US book, no blend, roadmap E3 closed.** The expected numbers written before the run were close on every count: the ex-US momentum premium (+3 … +8 expected, +7.4 found), the ETF (+1 … +3, IMTM +1.4 / IDMO +4.3), the give-back (2 … 4 pp/yr expected at 50–70 % US, 2.3 … 3.8 found), the drawdown gain (1 … 3 points expected, 0.8 … 1.3 found); the two misses were the dip rule on countries (0 … +1 expected, negative in the first half) and the books' correlation (0.1 … 0.3 expected, 0.58 found).

**I1 — the momentum premium by region** (Kenneth French's WML, long winners / short losers, USD, daily 1990-11 → 2026-09, split 2008; the US from the same date):

| region | ann. mean | 1990–2007 | 2008 → | t | Sharpe | 2009 | corr. with US WML |
|---|---|---|---|---|---|---|---|
| US (reference) | +5.3 | +10.0 | +1.1 | 2.1 | 0.35 | −51 | 1.00 |
| **Developed ex-US** | **+7.4** | **+8.5** | **+6.4** | **4.7** | 0.77 | −35 | +0.53 |
| Europe | +9.9 | +11.8 | +8.2 | 5.1 | 0.84 | −38 | +0.57 |
| Japan | +0.6 | +1.2 | −0.0 | 0.3 | 0.04 | −33 | +0.14 |
| Asia-Pacific ex-Japan | +10.8 | +12.5 | +9.3 | 5.6 | 0.92 | −38 | +0.20 |

Holds. The premium is positive in both halves in every developed region except Japan (the documented exception, ≈ 0 as pre-registered), stronger and steadier *outside* the US than inside it over these 36 years, with the 2009 crash everywhere. Long-short and frictionless — the investable long-only share is smaller (I2).

**I2 — an ex-US momentum ETF held outright vs its index** (excess CAGR pp/yr; IS → 2021 / OOS 2022 →; "→ 2025" = through 2025-12-31; r3 = rolling 3-year windows ahead):

| held vs index | excess | IS / OOS | → 2025 | DD vs index DD | Sharpe | worst year | r3 |
|---|---|---|---|---|---|---|---|
| ACWX vs SPY (the ex-US decade in one line) | −5.91 | −8.7 / −3.0 | −6.20 | −35.3 vs −33.8 | 0.60 | −23.3 | 0 % |
| IMTM vs ACWX | +1.39 | +2.1 / +0.7 | +1.85 | −30.7 vs −35.3 | 0.67 | −3.1 | 85 % |
| IMTM vs EFA / IEFA | +1.58 / +1.46 | +2.0 / +1.1 · +1.6 / +1.3 | | | | | |
| **IDMO vs ACWX** | **+4.34** | **+4.0 / +4.7** | +5.04 | −31.0 vs −35.3 | 0.79 | −2.8 | 100 % |
| IDMO vs EFA / IEFA | +4.53 / +4.40 | +3.9 / +5.2 · +3.5 / +5.4 | | | | | |
| SPMO vs SPY (the US sleeve, reference) | +5.23 | +2.1 / +8.4 | +4.46 | −31.2 vs −33.8 | 1.00 | −7.2 | 70 % |

Holds for both vehicles, both halves, against all three indices, through 2025 as well. IDMO (S&P Developed ex-US momentum, Invesco) beat IMTM (MSCI World ex-USA momentum) by 3 points a year — index construction, as SPMO vs MTUM in the US (Decision 067). The ex-US decade itself was the worst in the record: ACWX lost 5.9 pp/yr to SPY, 8.7 in the first half.

**I3 — the live dip rule on the 20 country ETFs** (3 × 25 %, ACWX residual, insurance ×0.5 from the region's own breadth; the sector-floor test on a new universe of baskets):

| book | vs | excess | IS / OOS | → 2025 | DD vs index | Sharpe | trades | win | median | tp / stop / clock | risk-off |
|---|---|---|---|---|---|---|---|---|---|---|---|
| country dip book | ACWX | +0.29 | **−0.9** / +1.5 | **−1.49** | −27.7 vs −35.3 | 0.66 | 78 (8.0 / yr) | 62 % | +2.8 % | 13 / 10 / 55 | 24 % |
| country dip book | EW basket of the 20 | −0.59 | **−1.4** / +0.2 | −2.53 | −27.7 vs −36.9 | | | | | | |
| EW basket of the 20 | ACWX | +0.88 | +0.5 / +1.3 | +1.04 | −36.9 vs −35.3 | 0.63 | | | | | |
| 11-sector dip book (the floor) | SPY | +0.44 | +0.6 / +0.3 | +0.55 | −25.3 vs −33.8 | 1.11 | 61 (6.3 / yr) | 79 % | +4.9 % | 7 / 6 / 48 | 13 % |

Fails. Negative in the first half both ways, negative through 2025 both ways — the full-period +0.3 is 2026 alone. The rule's texture on countries is the single-name texture, not the sector one: 62 % winners and a +2.8 % median trade against 79 % and +4.9 % on the sectors, and the insurance was on for 24 % of sessions (ACWX spent long stretches under its 200-day SMA this decade) against 13 % for SPY. A basket universe is not automatically a floor: a country ETF's "dip within an uptrend" is often a currency or a policy move, which the rule cannot tell from a dip. The drawdown is cut (−27.7 vs −35.3), as the dip sleeve always does; the return is not there. The ex-US book and its parts, each vs ACWX: the dip sleeve alone (insurance off inside, as in the book) +1.34 (+1.8 / +0.8) but −0.40 through 2025; **the pre-registered book (dip 40 / IMTM 60, min) −0.50 (−0.7 / −0.3), DD −23.0, Sharpe 0.69**; the same with IDMO +2.65 (+3.2 / +2.1), DD −17.7, Sharpe 0.95; with no insurance and no shock +1.52 (+2.1 / +0.9), DD −30.7; IMTM 100 % under min(insurance, shock) −0.62. The exposure rules cost the ex-US book ≈ 2 pp/yr (de-risked 26 % of sessions: insurance 24 %, shock 8 %) against ≈ 1.7 for the US book (15.5 %) — the price of a decade spent half below the SMA.

**I4 — do the two books bet on different things?** Daily correlations (full / IS / OOS): the books' *active* returns (each over its own index) **+0.58 / +0.66 / +0.50**; their total returns +0.75 / +0.78 / +0.72; SPY vs ACWX +0.85 / +0.89 / +0.80; the sector dip sleeve vs the country dip sleeve (active) **+0.04**; SPMO vs IMTM (active) +0.31; the US book vs IMTM held +0.76. Fails (< 0.5 expected). The reading is the lesson of the day: the *sleeves* are different bets (0.04 between the dip sleeves), but each book's active return is dominated by its exposure rules — while de-risked, active = −½ × its market — and the two markets are 0.85 correlated and de-risk at the same times. **Two books that de-risk together are one bet**: the diversification lives in the sleeves and is drowned by the insurance.

**I5 — the global blend**, US book w / ex-US book (1 − w), rebalanced daily, vs SPY (give-back = excess vs SPY minus the US book's +1.36; "vs w-bench" = excess over w SPY + (1 − w) ACWX; P1 = ACWX held in the ex-US slot; P2 = three random country ETFs re-drawn yearly, 20 draws; the crash columns are the book minus SPY, peak to trough):

| blend | vs SPY | IS / OOS | → 2025 | give-back | vs w-bench | DD | Sharpe | worst yr | r3 | covid / 2022 / 2025 |
|---|---|---|---|---|---|---|---|---|---|---|
| **US book alone (live)** | **+1.36** | +0.3 / +2.5 | +0.80 | — | +1.36 | **−20.0** | **1.10** | −11.3 | 59 % | +13.8 / +9.7 / +2.0 |
| ex-US book alone (IMTM) · with IDMO | −6.41 · −3.27 | −9.4 / −3.4 · −5.5 / −1.0 | −6.82 · −3.43 | | −0.50 · +2.65 | −23.0 · −17.7 | 0.69 · 0.95 | −28.0 · −23.6 | 0 % · 7 % | +16.3 / +8.2 / +9.2 |
| w 0.9 · P1 · P2 median [p10 … p90] | +0.62 · +0.69 · +0.67 [+0.48 … +1.13] | −0.7 / +1.9 · −0.6 / +2.0 | +0.07 · +0.16 | −0.75 · −0.68 | +1.17 · +1.24 | −19.7 · −21.3 · −21.7 | 1.09 · 1.07 · 1.08 | −11.7 · −11.3 | 48 % | +14.0 / +9.5 / +2.7 |
| w 0.8 · P1 · P2 | −0.14 · −0.00 · +0.17 [−0.23 … +0.57] | −1.6 / +1.4 · −1.5 / +1.5 | −0.67 · −0.50 | −1.50 · −1.36 | +0.98 · +1.12 | −19.5 · −22.6 · −23.2 | 1.07 · 1.04 · 1.04 | −12.2 · −11.3 | 41 % | +14.3 / +9.4 / +3.4 |
| **w 0.7** · P1 · P2 | **−0.90** · −0.70 · −0.91 [−1.88 … +0.09] | **−2.6 / +0.8** · −2.3 / +1.0 | −1.42 · −1.18 | **−2.26** · −2.06 | +0.79 · +0.99 | **−19.2** · −23.9 · −25.1 | **1.04** · 0.99 · 0.98 | −13.1 · −11.3 | 22 % | +14.5 / +9.3 / +4.1 |
| w 0.6 · P1 · P2 | −1.67 · −1.41 · −1.05 | −3.6 / +0.3 · −3.2 / +0.4 | −2.17 · −1.86 | −3.03 · −2.78 | +0.61 · +0.86 | −19.0 · −25.2 · −25.3 | 1.01 · 0.94 · 0.94 | −14.2 · −11.4 | 15 % | +14.8 / +9.1 / +4.9 |
| w 0.5 · P1 · P2 | −2.44 · −2.14 · −1.21 | −4.5 / −0.3 · −4.1 / −0.1 | −2.93 · −2.56 | −3.81 · −3.50 | +0.42 · +0.73 | −18.7 · −26.6 · −28.4 | 0.97 · 0.89 · 0.91 | −15.3 · −11.4 | 11 % | +15.0 / +9.0 / +5.6 |

Fails at every weight. The give-back is slightly *worse* than simply holding ACWX in the slot (P1) everywhere and inside or below the random-country spread (the book blend beats the draws in 25–50 % of them); the Sharpe is below the US book's at every weight; the drawdown improves by 0.3 … 1.3 points (the US book's −20 % is already the ex-US book's class); and the crash weeks gain a point or two at most (covid +14.5 vs +13.8, 2022 +9.3 vs +9.7, 2025 +4.1 vs +2.0 at w 0.7) — the pre-registered caveat exactly. **No blend of any kind is positive vs SPY in both halves** (first halves −0.0 … −4.5): the decade in which the US beat the world by 6 points a year is not a decade in which a US investor is paid for leaving.

*The decomposition, for the record (post hoc; IDMO was named in I2 as a vehicle, not as the pre-registered book):* at w 0.7 the ex-US slot filled with IMTM alone gives back −1.64 (DD −23.0), with the country dip sleeve alone −2.23 (DD −18.8), with the IDMO book −1.25 (vs SPY +0.12, −1.3 / +1.6, DD −18.6, Sharpe 1.14); **IDMO alone in a 10 % slot (w 0.9) is the one cell beside the live book: +1.22 vs SPY (−0.0 / +2.5), → 2025 +0.76, DD −20.9, Sharpe 1.12, worst year −10.7, r3 59 %** — a give-back of 0.15 pp/yr for a tenth of the book outside the US, and a first half of −0.0. The IDMO variant passes I5's arithmetic at every weight and still fails the project's both-halves bar; it is a *dial* like the momentum weight in roadmap C1 (a measured preference), not a result, and it is recorded so it is not re-discovered: if the operator ever wants ex-US exposure for the dollar's sake, the cheapest form the data supports is a slice of the momentum sleeve in an ex-US momentum ETF, pre-registered on longer data first (Tiingo, B11).

**I7 — currency.** (a) The decade in euros (DEXUSEU; EUR/USD 1.04 → 1.12, the dollar drifting −0.7 %/yr): SPY 15.3 %/yr in dollars, 14.5 in euros; ACWX 9.4 / 8.6; **the US book 16.7 / 15.8** (euro halves 16.6 / 15.0, euro drawdown −23.7, euro Sharpe 1.00); the ex-US book 8.9 / 8.1; the 70 / 30 blend 14.4 / 13.6; 50 / 50 12.9 / 12.0. Every number moves by the same drift, so the ranking is unchanged. DBEF (currency-hedged EAFE) beat EFA by +2.27 pp/yr (+0.3 / +4.3; +1.89 through 2025) — the rate differential since 2022 paid the hedge, not a currency call; roadmap E4 reference. (b) **The US market vs the regional markets across the dollar's regimes** (French value-weighted markets, CAGR in USD / in euros):

| window | US | Developed ex-US | Europe | Japan | Asia-Pacific ex-Japan |
|---|---|---|---|---|---|
| 1990-07 → 2008-01 (USD only) | +10.6 | +7.4 | +10.7 | +0.2 | +13.2 |
| 2008-01 → 2026-09 | +11.6 / +13.0 | +5.2 / +6.6 | +4.8 / +6.3 | +6.2 / +7.7 | +4.4 / +5.9 |
| 1999-01 → 2002-01, dollar up (1.18 → 0.90) | −0.2 / +9.1 | −4.1 / +4.9 | −5.8 / +3.0 | −4.6 / +4.3 | +5.4 / +15.2 |
| **2002-01 → 2008-07, dollar down (0.90 → 1.60)** | **+3.7 / −4.9** | **+12.9 / +3.5** | +12.9 / +3.5 | +8.4 / −0.6 | +19.3 / +9.3 |
| 2008-07 → 2022-09, dollar up (1.60 → 0.96) | +10.3 / +14.3 | +2.8 / +6.5 | +2.4 / +6.1 | +3.2 / +7.0 | +3.5 / +7.3 |
| 2022-09 → 2026-09, dollar down (0.96 → 1.17) | +22.6 / +16.8 | +19.4 / +14.6 | +19.8 / +14.9 | +21.5 / +16.5 | +13.1 / +8.6 |
| 1999-01 → 2026-09, the whole euro era | +9.2 / +9.2 | +6.6 / +6.7 | +6.2 / +6.4 | +6.0 / +6.2 | +8.6 / +8.8 |

The fear is real in history and bounded in size: in the dollar's 2002–08 fall a euro investor in US stocks *lost* 4.9 %/yr for six and a half years while developed ex-US made +3.5 in euros (a 8.4-point gap) — that was a weak dollar *and* a US lost decade together; in the 2022–26 dollar fall the US still won. Over the whole euro era the dollar round-tripped (1.18 → 1.13) and the US beat developed ex-US by 2.5 pp/yr in both currencies; over 1990–2026 the US won both halves (+3.2 and +6.4). CZK is not in the library; the euro is the proxy.

**Decision.** Nothing changes. Roadmap E2 is done, E3 (the second book) is closed with the numbers above, E4 is priced once and stays a go-live question (a USD/CZK hedge is a forward, which Alpaca does not offer). What was learned and kept: the ex-US momentum premium is real, old and investable (IDMO); the dip rule needs sectors, not countries; two books under the same exposure rules are one bet in the week that hurts; and the dollar risk the operator named has, in history, cost a euro investor about 8 points a year against ex-US for one six-year stretch and nothing over the full era. What reopens E3: a hindsight-free country-ETF history covering 2000–02 and 2008 (Tiingo, B11) on which the dip rule is ≥ 0 in both halves, or a pre-registered test of the IDMO dial on that data. **Next pick: B1** (put-writing and the collar indices on 40 years of Cboe data).

**Scripts / docs**: `scripts/param_search/intl.py` (pre-registration commit `eb94dbc`, then the code), `datasets.french_regional`, the harness README row; roadmap E2 ✅ / E3 🚫 / E4 priced; todo Phase 2.13; two insights. Raw output kept in the session scratchpad only (the tables above are the record).

*Operator, after the plain-language reading (2026-10-29 evening)*: the question was not a copy of the US book abroad but "an extension that requires its own big research with all our ideas, devising a strategy there, then seeing if trading the US together with, for example, the EU makes us stronger altogether". Answered: possible, but it needs data and possibly a broker we do not have, most of the catalogue fails for country-independent reasons, and the combination's value is a bet on the region's decade because two long-only equity books fall together in a crash. **Recorded as roadmap E6 and parked at the back on the operator's call ("potential, but better priorities now"); B1 started the same evening.**

## Decision 072: The external data library — everything beyond prices that the research can use, free first (operator, 2026-10-29)
**Date**: 2026-10-29
**Operator**: "we have prices but there is so much more that influences trading … think of what we want and try to find it all and store it somewhere; completely free ideally, a small amount is acceptable." Done the project's way: an inventory of what each open question needs, a probe of the free sources, one fetcher with a manifest (`scripts/param_search/fetch_external.py`), the files stored under `data/param_search/external/<source>/` (git-ignored) and archived on titanserver under `/home/TitanTrade/archive/param_search/external/` (the SEC zips excluded there — re-downloadable). 122 of 127 items on the first pass, 271 MB, no key and no payment needed for any of it.

**What we wanted, and where it is now**

| need (the question it serves) | source, span, status |
|---|---|
| **Option-writing benchmarks** — the hindsight-free answer to "sell puts at the dip" (brainstorm #32, untestable until now) | Cboe daily index histories, key-free CSV: **PUT 1991 →, BXM 2002 →, BXMD / CNDR / BFLY / RXM / PPUT / CMBO 1986 →, BXY 1988 →, BXMC 1990 →, CLL 2008 →, WPUT 2006 →** — put-write, buy-write, collar, condor, butterfly, risk-reversal and protective-put strategies on the S&P 500 as index levels for 35–40 years |
| **Volatility** — VIX for sizing / regime questions the analogues left open | Cboe VIX 1990 →, VIX9D 2011 →, VIX3M 2009 →, VIX6M 2008 →, VVIX 2006 →, SKEW 1990 →, VXN / VXD / RVX / OVX / GVZ 2009 →; FRED VIXCLS / VXVCLS / VXNCLS |
| **Rates and the risk-free leg** — the carry question, the de-risked capital, the insurance's cost by era | FRED key-free CSV: DTB3 1954 →, DFF 1954 →, DGS2 1976 →, DGS10 1962 →, DGS30 1977 →, DGS1MO 2001 →, FEDFUNDS, T10Y2Y / T10Y3M (curve), T5YIE / T10YIE (breakevens) |
| **Credit and financial stress** — a second insurance signal candidate with a different population than breadth | NFCI / ANFCI 1971 →, STLFSI4 1993 →; the ICE BofA spreads (BAMLH0A0HYM2, BAMLC0A0CM) only from 2023-10 on the key-free endpoint (licensing) |
| **Macro and recessions** — era labels, the century's regime work | USREC 1854 → (monthly), USRECD (daily), UNRATE, ICSA (weekly claims), CPIAUCSL, UMCSENT, M2SL, WALCL / TOTRESNS / RRPONTSYD (the Fed's balance sheet), DCOILWTICO, DTWEXBGS, DEXUSEU |
| **Other indices** | NASDAQCOM 1971 →; SP500 and DJIA on FRED only 10 years (the century market is French's, have) |
| **Positioning** — the "who is crowded" question | CFTC Commitments of Traders, legacy futures-only, one zip per year **1986 → 2026** (S&P / Nasdaq / bond / FX / commodity futures) |
| **Sentiment and leverage** | FINRA margin statistics (monthly xlsx); NAAIM exposure index (the page carries no direct file link — manual download, noted); AAII sentiment is behind a membership wall (walled) |
| **Long history of valuations** | Shiller `ie_data.xls`: monthly S&P price, dividends, earnings, CAPE, long rate **1871 →** |
| **Factor premia and trend over a century** — the TSMOM / trend questions without futures data | AQR data library: Century of Factor Premia (monthly, 1920s →: value, momentum, carry, defensive across asset classes), Time-Series Momentum factors (monthly 1985 →), Quality Minus Junk (daily), Betting Against Beta (daily), Value and Momentum Everywhere, Momentum Indices, Commodities for the Long Run, the Devil in HML's Details |
| **Profitability, investment, size, beta sorts over a century** — the quality question (brainstorm #33 / the fundamentals idea) on the cheap | Kenneth French daily: Portfolios formed on operating profitability, on investment, on size, 25 size × profitability, the 5-factor daily file, 10 and 30 industries, beta sorts (monthly); the variance and size × momentum daily files do not exist under those names (404) |
| **Gold** | datahub monthly 1833 → (LBMA's own JSON and FRED's series are walled / gone) |
| **Fundamentals, point in time** — a profitability filter for a single-name dip universe | SEC Financial Statement Data Sets, quarterly zips 2009q1 → (60–130 MB each; 2026q2 and q3 fetched as a format check; the full set ≈ 5 GB is fetched by the fundamentals project on demand under the SEC's fair-access policy: a User-Agent with contact, ≤ 10 requests/s) |

**Walled or gone, and what would unlock them**: Stooq (JS challenge), Yahoo (429 from both machines), LBMA (403), AAII (membership), Cboe's put/call-ratio archive (403), FRED's Wilshire 5000 and gold series (discontinued). **Free with a key the operator signs up for** (a minute each): **Tiingo** (30+ years of adjusted EOD for ETFs and names — the 1999 → sector-ETF and 15-name history Decision 062 lost when Yahoo closed; 50 symbols/hour on the free tier), Alpha Vantage (adjusted daily back to the 1990s, historical earnings dates per symbol — the earnings-gate valuation; 25 requests/day), Nasdaq Data Link (LBMA gold, some CFTC/ICI mirrors). **Paid, small**: EODHD (~€20/month: 30 years of EOD plus fundamentals for every US name — would replace Tiingo + Alpha Vantage), historicaloptiondata.com (~$100/year: EOD option chains 2004 →, the only cheap route to a real put-writing backtest on single names), Polygon (options history, $29–199/month). **Not for sale at retail**: MSCI / S&P index histories beyond 10 years (the momentum index pre-2015), OptionMetrics, Compustat.

**What this opens, in order of value**: (1) the put-writing question gets its hindsight-free answer from forty years of Cboe indices without buying option data; (2) a century of profitability / investment / size sorts lets the "quality" idea be tested the way momentum was (deciles over eras) before any fundamentals pipeline is built; (3) AQR's century of trend and carry premia lets the trend-following family be judged on the operator's own eras without futures data; (4) rates since 1954 price the carry and the insurance by era; (5) VIX, stress and positioning series are available for any future regime question — the analogue study's verdict (states describe the weather) stands until a pre-registered test says otherwise. Nothing changes live; no test was run on this data yet.

## Decision 071: Go-live readiness — backups, a dead-man's switch, the T-bill leg (off), the 90-day stop expiry, sizing at $25k, the server-down runbook (operator: "you can now do 2", 2026-10-29)
**Date**: 2026-10-29
**Why**: the research catalogue is exhausted on the data we have; what stands between the paper book and real money is operational, and no backtest covers it. Five findings and three builds. **Nothing live changed** (the code is built and tested, not deployed; the backup cron runs on the host and touches no order).

**Findings.**
1. **The GTC stops expire after 90 days.** Alpaca stamps every GTC order with `expires_at` = placement + 90 days (the book today: URI and JPM placed 2026-10-13 expire 2027-01-11, DXCM 2026-10-26 → 2027-01-22). The 60-trading-day holding limit (≈ 86 calendar days) normally exits a position first, and while the server runs the 09:35 ET stop-coverage job re-places a missing stop the next morning. The exposure is an outage: a server down past a position's clock leaves it with no stop after day 90. Added to the runbook; the stop-coverage job is the backstop, so the dead-man's switch below is what makes it one.
2. **No backup of `state/` existed** (4 MB: trade log, plan, strategy, ledger, cooldowns, peak; the only copy was the server's disk). Built: `scripts/backup_state.sh` — a daily tar of `state/` and `data/watchlist.json` to `/home/TitanTrade/backups/`, 30 kept, host cron 21:30 UTC (after the daily summary); restore = `tar xzf <archive> -C TitanTrade/`. Off-server copies remain a manual pull (`ssh titanserver 'base64 -w0 <archive>' | base64 -d`), the operator's call.
3. **Sizing at $25k works; $10k is the floor.** A 10 % slot of $25k is $2,500: at today's closes XLK 13 shares ($2,484), XLV 13 ($2,337), XLF 44, XLE 36, XLI 14 ($2,359), XLY 21, XLB 48, XLRE 59, XLP 28, XLU 58, XLC 24 — every slot ≥ 13 shares, the worst rounding 6 % under (XLV, XLI); SPMO at 57 % = 98 shares ($14,200); SGOV for an idle half = 117 shares. At $10k a slot is $1,000: 5 shares of XLK / XLV / XLI (−10 … −16 % rounding), SPMO 39 shares, the 5 % band ≈ 3 shares — coarse but whole. At $5k the $500 dust floor blocks XLK, XLV, XLI and XLC slots outright. The Phase 2.0 floor of $25k stands.
4. **A live account differs from paper in two ways the book is priced on.** Paper credits no dividends (verified, Decision 068 addendum); a live brokerage account does (cash, `DIV` activities) — the live book earns SPY's and SPMO's yield, which the price-return benchmark does not show. Whether Alpaca pays interest on idle cash in the live account is **unverified** (the sweep programme's eligibility and rate change); if it pays at or near the bill rate, the T-bill leg is unnecessary. Both are the first two items of the go-live checklist, to be answered on the live account before funding.
5. **Taxes are not in any number.** The dip sleeve's trades close inside 60 trading days and are short-term gains everywhere; the SPMO and SPY legs are long holdings whose lots the 5 % rebalance band mostly leaves alone. In the operator's jurisdiction the three-year time test can exempt the core legs' lots and never the dip sleeve's; a stop-out followed by a re-entry within the cooldown window is the shape wash-sale-type rules target. Not advice — a line for the advisor, recorded so the live decision is made with it.

**Builds (code, tested; deployed 2026-10-29 13:40 UTC on the operator's go — both images rebuilt between the 09:35 ET gapcheck and the 10:15 ET execute with no job running, API restarted, health ok, 7 jobs, config unchanged: `cash_ticker` empty, design 070; CLI image import-verified; cache pruned, disk 44 %).**
- **Heartbeat** (`scheduler._ping_heartbeat`): after a successful daily summary the API GETs `HEALTHCHECK_PING_URL` (unset = no-op; a failed ping is logged, never raised). A dead-man's-switch monitor (healthchecks.io or similar, free; schedule `35 16 * * 1-5` America/New_York, grace 2 h) then alarms when the server, the scheduler or the summary is dead — the one failure the process cannot report. Needs the operator's sign-up and the URL in `.env`, then `docker compose up -d api`.
- **The T-bill leg** (`cash_ticker`, default `""` = off): a third core leg (SGOV) sized `(1 − exposure_scale) × 95 %` — the capital the insurance or the shock trigger idles — rebalanced in the same 5 % band by `manage_core_position`; it sells *first* when the idle share shrinks (its cash funds the re-risking) and buys *last* when it grows; a core leg like SPY and SPMO (no stop, never an orphan, outside the overlay cap and the sector gate: `core_allocation.core_tickers`, `risk_manager._core_legs`); the plan carries `cash_leg {ticker, target_pct}` and the Discord plan field shows it. Worth +0.17 pp/yr decade-like and +0.5 on the century (Decision 068 addendum); invisible on paper, so it is switched on at funding only if the live account does not pay interest on cash.
- **Backups**: the script above and its cron on titanserver — **installed 2026-10-29 13:18 UTC**: `crontab` line added beside the host's other jobs, first archive `titantrade-state-20261029-1318.tar.gz` (644 KB), restored into a scratch directory and compared: `state/` and `data/watchlist.json` byte-identical. (The server layout is the repository at `/home/TitanTrade` with the package in `/home/TitanTrade/TitanTrade`; the first cron line had one directory too many and was corrected before the first run.)

**The server-down runbook** (`TitanTrade/docs/deployment.md`): what keeps working (the GTC stops on the dip positions, until day 90), what stops (entries, target and clock exits, core rebalances, the insurance and shock de-risking, stop re-placement, the summary), what the alarm is (the heartbeat), and the steps: restart the API, run `gapcheck` then `execute` by hand, or on a lost host restore `state/` from the latest archive and redeploy; positions past their clock are sold by the first execute, and the Alpaca dashboard is the manual exit while the server is down.

**The open questions, answered the same day** (operator: "the information can be found by you"; sources read, quotes checked):
- **Dividends.** Alpaca's paper-trading page: "Paper trading account does NOT simulate dividends" (the "Paper vs Live" list names dividends among what paper does not account for) — the empirical finding confirmed. On a live account a dividend arrives as a `DIV` activity with a `DIVNRA` withholding event ("the amount sent in the DIV event is without the tax DIVNRA"), i.e. credited to cash net of withholding; for a Czech resident with a W-8BEN the treaty rate is 15 %. The live book earns SPY's and SPMO's yield; the price-return benchmark does not show it. *Answered.*
- **Cash interest.** Alpaca runs a High-Yield Cash programme for Trading API accounts: "As of September 22, 2026, eligible Alpaca Trading API users can earn up to 3.56 % APY on their uninvested USD balances"; "the APY is variable and may change at any time"; enrolment is a dashboard action ("Log in to your Dashboard Overview or enroll through the Plans and Features tab"), funds sit in an FDIC bank sweep and remain usable "as buying power"; the one stated condition is "only available to Alpaca users who are classified as non-pattern day traders" (this book trades a few times a month). Eligibility for a non-US individual opening directly with Alpaca Securities is not stated on either page. *Answered up to one dashboard check at account opening: if the programme can be enrolled, the T-bill leg stays off; if not, `cash_ticker: "SGOV"` goes on.* **Why the sweep first** (operator asked): the yields are close and neither is reliably ahead (a bank rate Alpaca sets vs the bill rate the market sets, both falling in a cutting cycle); the sweep earns on *every* idle dollar including the 5 % reserve, which the leg cannot hold (the reserve must stay cash for brackets — worth about as much as the de-risked share itself), never trades, never lags a band, has no ex-date drops and keeps cash as buying power; the leg's only edges are Treasury credit over a bank sweep and availability to any account. Rule: sweep if the account can enrol, SGOV otherwise; at each checkup compare the sweep APY with SGOV's yield and switch the leg on if the sweep lags by ≥ 0.5 pp for a sustained stretch.
- **The 90-day stop expiry.** Official: "Alpaca implements an aged order policy that will automatically cancel GTC orders 90 days after creation"; the cancel job runs "on the expires_at date at 4:15 pm ET". So on day 90 a standalone GTC stop vanishes after the close and the 09:35 ET coverage job re-places it the next morning — an overnight gap, only reachable when the 60-trading-day clock (≈ 86 calendar days) has not already exited the position, i.e. during an outage. Also from the docs: a bracket's legs carry DNR/DNC ("the order will not be canceled in the event of a dividend or other corporate action"), but the standalone GTC stop placed after the fill is not a bracket leg: Alpaca "cancels open GTC orders on symbols that have an upcoming mandatory corporate action (splits, symbol change, merger)" and adjusts sell stops on forward splits — the coverage job is the backstop for both. *Answered; runbook updated.*
- **The heartbeat service.** healthchecks.io's free Hobbyist plan: 20 checks per account, cron-expression schedules with a timezone, configurable grace time; the project's monitor is one check: `35 16 * * 1-5`, `America/New_York`, grace 2 h. *Answered; the sign-up and the URL in `.env` remain the operator's.*
- **Taxes (Czech resident; not advice).** Gains on securities held more than three years are exempt (the "time test"); from 1 January 2026 the CZK 40 million cap on that exemption no longer applies to securities (it stays for crypto-assets); below the test, gains are "other income" taxed at 15 % (23 % on the part of the overall base above the higher threshold); a separate exemption applies when total gross sale proceeds in the year stay under CZK 100,000 (proceeds, not profit, all brokers together). For this book: every dip-sleeve trade is inside the test (taxable), the SPY / SPMO / SGOV lots are long holdings the 5 % band mostly leaves alone (exempt after three years, lot by lot), US dividends are withheld at 15 % under the treaty with a W-8BEN and declared with credit. *Answered to the level of a line for the advisor.*
- **Off-server backups.** `scripts/pull_backup.sh` pulls the latest archive from titanserver with the base64 pipe into a git-ignored `backups/` folder next to the checkout; run at every checkup (added to the routine). First copy pulled 2026-10-29. *Answered; no sign-up needed.*

Sources: [paper trading](https://docs.alpaca.markets/docs/paper-trading), [mandatory corporate actions](https://docs.alpaca.markets/us/docs/mandatory-corporate-actions), [orders at Alpaca — aged order policy](https://docs.alpaca.markets/docs/orders-at-alpaca), [High-Yield Cash for Trading API](https://alpaca.markets/blog/alpaca-launches-high-yield-cash-program-for-trading-api-users-enabling-growth-on-deposits/), [healthchecks.io FAQ](https://healthchecks.io/faq), [Czech taxation of shares and ETFs in 2026](https://arws.cz/en/news-at-arrows/czech-taxation-of-shares-and-etfs-in-2026), [the CZK 40m cap ends for securities](https://arws.cz/news-at-arrows/czech-full-tax-2026-exemption-on-share-sales-after-czk-40m-cap-ends), [Czech ETF tax 2026, the 3-year time test](https://financialexpertclass.com/czech-republic-etf-tax-2026-time-test/).

**Tests**: 272 (`tests/test_readiness.py`: the leg's target maths, core-leg membership for the plan and the gates, the plan field, the executor's leg order both ways and the default without a third leg; the heartbeat only when configured and never failing the summary). Ruff clean. **Docs**: deployment (backups, heartbeat, runbook), security (the env var), features, data_schemas, risk_management, backend architecture, todo Phase 2.0 (the go-live checklist rewritten around these findings).

## Decision 070: The dip sleeve moves to the 11 sector ETFs; the hand-picked list becomes a shadow list — prepared, NOT deployed (operator: "a hand-picked, non-dynamic list seems temporary", 2026-10-29)
**Date**: 2026-10-29
**Why**: the operator's fear is the right one and the day's tests made it concrete. The dip rule's edge on the curated 15 names (+4.0 pp/yr on the decade) is **2022 → 2026 only** (IS −8.4 / OOS +17.8); the same rule on the point-in-time Dow 30 lost 7.9 pp/yr in both halves and on 19 of 20 random 30-name S&P lists (median −2.7) — any list of individual large caps hands the rule single-name breaks it cannot tell from dips. The 11 sector ETFs are the one hindsight-free universe where the rule is ≥ 0 (+0.4 for the dip-only book: 61 trades, 79 % winners, 6 stops in ten years, drawdown −25 % vs the names' −38 %), and they are what every expected number of Decision 068 was computed on. In the two-sleeve book the master search priced the choice: **sectors +1.4 (IS +0.3 / OOS +2.5), worst year −11, DD −20 %; the curated list +2.5 to +2.6 with IS −3.6 to −4.5 and a −20 to −22 worst year**. The switch gives up a point a year that exists only since 2022 and gets both halves positive, half the worst year, and a universe that needs no judgment and no maintenance. The hand-picked list is not thrown away: it becomes a **shadow list** — tracked, curated, measured, not traded — so the judgment question gets a long answer without the sleeve betting on it.

**What changes (code, built and tested; config staged, not applied):**
1. **Config** (`config.py`): `shadow_watchlist` (top-level in `data/watchlist.json`, default empty) and `settings.mechanical.design` (default `"068"`). `data/watchlist.decision070.json` is the exact file to copy over `data/watchlist.json` at deploy: `watchlist` = XLK XLV XLF XLE XLI XLY XLB XLRE XLP XLU XLC, `shadow_watchlist` = the 15 names, `design` `"070"`, every parameter unchanged (a test pins it to the live file).
2. **A watchlist edit never force-sells** (`mechanical.build_plan`): a held position opened under the strategy whose name is no longer in the watchlist keeps its HOLD item (stop, target, clock) and gets no new entry; only pre-strategy positions are `legacy_to_close`. Decision 063's "removed from the watchlist → orphan close" is withdrawn. **Transition**: DXCM, URI and JPM run out through their own exits (at most 60 trading days); SPMO fills toward 57 % as they go; new entries come in on the ETFs at 10 % slots.
3. **The clean window re-stamps on a design change** (`mechanical._ensure_strategy_started`): `strategy.json` gets a new `window_started_at`, `design` and `dip_universe` whenever the configured `design` differs from the stamped one; `started_at` never moves. The benchmark window and the go/stop rule start again at the deploy.
4. **Gates on ETFs**: the correlation gate (gate 8) does not apply to a ticker in `sector_etfs` — the sector floor was measured without it, and on the ETFs' real correlations (median pairwise 0.47, 90th percentile 0.73) it would have blocked about 1 in 5 second slots and 1 in 7 third slots; a sector ETF is a diversified basket, its correlation with another is market beta, not hidden concentration. The sector gate stays (`market_context.SECTOR_ETF_SECTORS` maps each ETF to its sector without a Finnhub call; Finnhub has no profile for an ETF). The earnings gate fails open on ETFs (no earnings). Everything else — slot size, overlay cap, cash reserve, drawdown breaker, macro blackout, the bracket, the GTC stop, the settled close — is unchanged.
5. **The shadow list**: `fetch` builds the bundle for the watchlist *and* the shadow names (the plan reads only the watchlist); the **curator** curates the shadow list when there is one (`curator.curated_list`; the proposal document carries `"list": "shadow_watchlist"` and the status says so) — the LLM keeps proposing names for the human list, and nothing it proposes reaches an order; `backtest-mech --shadow` runs the rule on the shadow list over any window (`download-history` fetches it), so each checkup can put "the rule on your names" beside the live sleeve on the same clean window.

**Tests**: 266 (`tests/test_universe_switch.py`: config and the live file, HOLD survival and the legacy case, the design re-stamp once, ETF sectors without Finnhub, the correlation gate skipping an ETF and blocking a name, the bundle names, the curator on the shadow list, `--shadow`); ruff clean. **Docs**: CLAUDE.md, features, risk_management, data_schemas, backend architecture, deployment, agent_instructions, todo (Phase 2.9).

**Deployed 2026-10-29 13:03 UTC** (operator's go; commit `bacbb49` on the server): `git pull --ff-only` → `docker compose build api` → `docker compose stop api` → the staged file copied over `data/watchlist.json` → `docker compose up -d api` (down for seconds, between the 09:00 ET fetch and the 09:35 ET gapcheck, no job running) → `docker compose build titantrade` (bakes the new `data/`) → CLI image import check through its `uv` entrypoint (`fill_ledger` imports, watchlist XLK…, design 070) → `docker builder prune -a -f` (disk 44 %). API health ok, 7 jobs, `/api/fill-ledger` serving `{n: 0}`. Smoke: `fetch` built the bundle for 26 names (11 ETFs + 15 shadow names, 0 errors, breadth 54.5 %, SPY above its SMA); `signals` re-stamped `strategy.json` (`window_started_at` 2026-10-29T13:04:02Z, `design` 070, `dip_universe` the 11 ETFs; `started_at` unchanged) and wrote the first plan: **DXCM / JPM / URI HOLD at their stops (68.91 / 297.37 / 940.20), `legacy_to_close` empty, 0 free slots, no candidates** (XLI, XLRE, XLU and XLC are 8–10 % below their 90-day highs but under their 150-day SMA — the trend filter), exposure ×1.0, SPMO target 57 %. The 10:15 ET execute is the first run under the new book; it has nothing to buy until a held name exits. The staged file was retired and `data/watchlist.json` committed with the live content in the same commit as this record. Decision 069's ledger and verdict guard went live in the same deploy (first ledger row at the first 16:30 ET summary after the next entry; the benchmark line now reads "too short to judge").

**Deploy procedure as run (for the next universe or parameter change)**: `./data` is bind-mounted into the API container, so a `git pull` alone changes nothing (the staged file is not read) and a committed `watchlist.json` would switch the live list *before* the rebuild — hence the staged file. Steps: `git pull --ff-only` → `cp data/watchlist.decision070.json data/watchlist.json` → `docker compose build api titantrade && docker compose up -d api && docker builder prune -a -f` → CLI image import check → `docker compose run --rm titantrade fetch` then `signals` (the plan must show the three names as HOLD, `legacy_to_close` empty, the ETF candidates, `strategy.json` re-stamped with `design 070`) → the next scheduled execute. **Verify after**: the first ETF entry passes gate 8 with "not applied", its GTC stop and `fill_price`; DXCM / URI / JPM keep their stops and exit on their own; the Discord benchmark line restarts at the new window; the first Sunday curator proposal names the shadow list; `backtest-mech --shadow --start <window>` runs. **Expectation, hindsight-free and now the only one that applies**: +1.4 pp/yr over SPY in a decade like the last, worst drawdown ≈ −20 % vs −34 %, both halves positive, −11 in the worst relative year; century +3.6.

### Decision 070 addendum — the dip rule's parameters re-checked on the hindsight-free universes: no change (operator's pick, 2026-10-29)
`scripts/param_search/etfparams.py` (hypotheses P1–P5 in the docstring; the Decision 062 grid of 6,000 cells, plateau scoring, stage-3 walk-forward of the selection, now on **D** the 11 sector ETFs 2016 → split 2022 and **F** the 49 industries 1927 → split 1990; slots 3 × 25 % of the dip book, insurance off in the grid as in 062; C, Yahoo 1999 →, still unavailable). Nine minutes on 16 cores; grids cached in `data/param_search/etfparams_{D,F}.json`.

| | D sector ETFs | F industries |
|---|---|---|
| live cell 8 / 90 / 150 / 60 / +20 / −12 | **+2.76** (IS +2.0 / OOS +3.7), 5.8 trades/yr, 79 % winners, DD −33.3 vs −33.8, Sharpe 1.04 vs 0.90; rank 38 of 3,460 by plateau OOS | +0.27 (+0.4 / +0.0), 11 trades/yr, 54 %, Sharpe 0.58 vs 0.63; rank 4,340 of 5,909 |
| its 12 neighbours (P1) | min +0.7 / median +2.0 / max +3.6, **0 sign flips** | −0.8 / +0.1 / +0.8, 3 of 11 flip — the century is flat around zero everywhere |
| marginals (P2) | target 20 > 15 > 10 ✓, SMA 150 ✓, hold flat ✓, stop flat 10–20 (8 % worst) ✓; dip 8 % best full-period, **12 % best out of sample** (+2.0 vs +0.7); lookback 60 full / 120 OOS | target 15–20 > 10 ✓, SMA 150 ✓ (200 the worst), hold flat, stop 20 % the worst (−0.4); dip 8 % the *worst* full-period, 12 % best out of sample (+1.1 vs −0.6) |
| 062 "sector-best" 8 / 60 / 150 / 60 / +20 / −20 | +3.97 (+3.2 / +4.9), the best plateau cell on D | **−1.13 (−1.0 / −1.3)**, DD −86 vs −84 |
| walk-forward of the selection (P3) | train 2016–21 → test 2022 →: selected 8/60/150/40/20/20 **−1.63** vs live **+1.46** vs 062 sector-best +2.73 | four windows: selected −2.58 / −0.46 / +1.02 / +4.87 vs live +0.11 / +0.32 / +0.02 / +0.88 (the 1950–99 window had 25 of 6,000 cells beating the market); average selected +0.24 vs live +0.56 over the five windows |
| slot grid at the live cell, insurance ×0.5 (P4) | 3 × 25 % +0.4; 33 % slots +1.0 at any count (IS −0.4 / OOS +2.7, DD −27 vs −25); 20 % −0.3 … −0.5; 15 % −1.0 | 2 slots best (+0.6), 3 × 25 % 0.0, 5 slots −0.5; all within ±0.6 |
| cross-universe consensus by plateau OOS (P5) | the top ten are all dip 12 % / 120 d / SMA 150 / **hold 20** / target 8–10 — full-period +0.0 … +0.4 on D, +0.3 … +0.7 on F: the out-of-sample halves like them, the in-sample halves do not; live rank 788 | |

**Inside the two-sleeve book** (the number that matters; min(insurance ×0.5, shock) × (0.4 dip + 0.6 momentum)):

| dip cell | decade: excess, IS / OOS, DD, Sharpe, worst yr | century: excess, 1927–74 / 1975–, DD, Sharpe, worst yr; eras |
|---|---|---|
| **LIVE 8 / 90 / 150 / 60 / 20 / 12** | **+1.36, +0.3 / +2.5, −20.0 %, 1.10, −11.3** | **+3.63, +5.0 / +2.2, −58.6 %, 0.86, −22.2; +4.6 +5.5 +3.3 +1.2** |
| 062 sector-best 8 / 60 / 150 / 60 / 20 / 20 | +1.82, +0.8 / +2.9, −19.8 %, 1.13, −11.2 | +3.15, +4.4 / +1.8, −60.1 %, 0.83, −21.3 |
| D best by plateau OOS (8 / 120 / 200 / 60 / 20 / 15) | +1.11, −0.9 / +3.2, −20.8 %, 1.09 | +3.52, +4.6 / +2.4, −60.8 %, 0.86, **−31.3** |
| F best by plateau OOS (10 / 120 / 150 / 20 / 20 / 12) | +0.61, −0.4 / +1.6, −22.2 %, 1.06 | +4.19, +5.1 / +3.2, −59.3 %, 0.89, −20.9; all four eras ≥ +2.9 |
| consensus #1 (12 / 120 / 150 / 20 / 10 / 12) | +0.39, **−1.4** / +2.2, −21.5 %, 1.05 | +3.74, +4.6 / +2.9, −58.8 %, 0.87 |

**Reading.** P1 holds on D (a plateau, no sign flips) and is moot on F (the rule ≈ the market on industries, as known). P2 holds for the target, the trend SMA, the hold and the stop; it fails for the dip: both universes prefer a deeper dip (12 %) *out of sample* and a shallower one in sample — era-dependent, which is what the consensus ranking then rewards (its whole top ten is dip 12 / hold 20, positive in the second halves only). P3 holds on average (the selected cell +0.24 vs the live cell +0.56 over five windows; the selected cell lost the decade's test by 3 points). P4: 3 × 25 % is on the plateau; 33 % slots gain on D in the second half only. P5: the live cell is not in the OOS top region and does not need to be — **it is the only cell positive in both decade halves and in all four quarter-centuries inside the book**, which is the standard that chose it. The one neighbour worth naming is Decision 062's "sector-best" (lookback 60, stop 20 %): +0.5 better on the decade in both halves in the book, −0.5 worse on the century with a deeper drawdown — the sector ETFs rarely hit a 20 % stop, the industries over a century do. Era-dependent, so not adopted; it is the first thing to re-check when Tiingo's 1999 → sector history (roadmap B11) adds two bears on real ETFs. **Nothing changes.** Lesson for the method: a consensus by out-of-sample rank alone picks the cells the second halves liked; the selection must demand both halves on every universe, as 062 did in its final step.

## Decision 069: The go/stop rule recalibrated — behaviour and drawdown decide, return is reported, not judged (operator go, 2026-10-29)
**Date**: 2026-10-29
**Why**: the luck meter (Decision 068 addendum, `scripts/param_search/luck.py`) showed the Decision 061 rule cannot do its job. Its return leg ("≥ SPY − 2 pp/yr over a quarter of paper") fails 43 % of the time for a book exactly as good as the backtest, because the book tracks SPY with a 9 %/yr tracking error and a +1.4 pp/yr edge needs about 170 years to reach t = 2. Its drawdown leg ("≤ 0.7 × SPY's fall in any SPY drawdown ≥ 10 %") fails the design's own backtest in 3 of 5 decade drawdowns: the insurance and the shock trigger engage in the slow, deep bears (2020 −20 vs −34, 2022 −15 vs −24) and, by design, barely in a fast 10–19 % dip (2018-01, 2018-Q4, 2025: the book fell 1–2 points less than SPY). A rule the backtest fails would stop a working book at the first fast dip or green-light a broken one on a lucky quarter.

**The rule (todo Phase 2.0)** — fund ≥ $25k only when all three hold over the clean window since `window_started_at` (2026-10-27):
1. **Behaviour** — every action in the trade log is one the rules prescribe: entries only on plan NEW items at the plan's levels, exits only by stop / target / holding limit / orphan close / core rebalance, exposure halved on every session a trigger was on and never otherwise; the median gap between each entry fill and the backtest's price for that trade (the next close after the signal) is reported at every checkup. The fill-vs-backtest ledger (brainstorm #15) automates this; until it exists the check is by hand from `trade_log.json` against `plan.json`. No numeric fill threshold until 20 trades.
2. **Drawdown** — the window contains at least one SPY drawdown ≥ 10 %; in every SPY drawdown ≥ 10 % the book fell no further than SPY (peak to SPY's trough), and in any ≥ 20 % at most 0.7 × SPY's fall.
3. **Return** — not a condition. The excess over SPY is reported at every checkup with its 90 % band (live: 1.645 × tracking error / √years; the block bootstrap in `luck.py` for the research books) and is not judged under 3 years; the Phase 1.36 way of reading the window (return vs SPY as the verdict) is withdrawn.

Withdrawn from the Decision 061 rule: "a quarter of paper", "return ≥ SPY − 2 pp/yr over the window", "max DD ≤ 0.7 × SPY's in any SPY drawdown ≥ 10 %". Unchanged: the ≥ $25k funding floor, paper as the current state, every deploy and watchlist change on the operator's explicit go.

**Follow-ups**: (a) and (b) **built the same day on the operator's go** (commit below), (c) at funding, the T-bill carry item (Decision 068 addendum).
- **(a) Fill-vs-backtest ledger** (`fill_ledger.py`): `entries._ensure_gtc_stop_on_fill` now returns the bracket's `filled_avg_price` and the BUY record carries it as `fill_price` (null when the entry did not fill inside the poll window). The daily summary calls `update_fill_ledger`: every BUY entry of the last 10 days without a row gets the close of its Eastern session from SIP bars (the price `fastbt` / `backtest/mechanical` fill at — the next close after the signal) and a row in `state/fill_ledger.json` (`gap_pct` = fill / close − 1; the bracket limit stands in, flagged, when the fill was not captured); idempotent, a missing bar or a failed fetch is retried at the next summary, rows are never edited. Surfaces: `GET /api/fill-ledger` (rows + median / mean / worst), a "Fill vs backtest" field on the Discord summary (median over all rows, today's rows), the checkup routine.
- **(b) Benchmark verdict under 3 years** (`benchmark.py`): `compute_metrics` adds `tracking_error_annual_pct` and `excess_annual_pct`; `MIN_RETURN_VERDICT_DAYS` = 756; `classify` returns "Too short to judge the return (N of 756 trading days): excess +x pp/yr, 90 % band ±y — β and Sharpe describe the ride, not the edge." between 20 days and 3 years (the alpha / Sharpe verdicts only from 3 years), `format_summary_line` shows the excess ± band instead of α on such windows, the CLI report prints the annualised excess, band and tracking error. Metrics files written before this change carry no band and read "too short" without it until the next refresh.
- **Tests**: 256 (ledger maths and Eastern session date, idempotent update with missing bars and failed fetches, the API endpoint and the summary field, the fill price returned by the reconcile helper, the 3-year guard and the band, the summary line without α; the scheduler's summary tests mock the ledger update). Ruff clean. **Docs**: CLAUDE.md, features, data_schemas, api_reference, backend architecture, todo. **Deployed 2026-10-29 13:03 UTC with Decision 070** (both images); the first ledger rows appear at the first 16:30 ET summary after the next entry.

## Decision 068: The two-sleeve book — 40 % dip rule / 60 % SPMO, the shock trigger, the insurance kept (operator go, 2026-10-27)
**Date**: 2026-10-27
**Decision** (operator: "let's build your recommendations", after the Decision 067 addenda closed shorting and regime switching with evidence and left asset rotation on the list for later): the book becomes two sleeves, built as recommended by the master search.

1. **Momentum sleeve** — SPMO held at `momentum_weight` = 60 % of the investable book (`scale × 95 % × 60 %`), rebalanced inside the same 5 % band as SPY by a second core leg of `core_allocation.manage_core_position(ticker=…)`, run after SPY so SPY's sale funds it. A core leg like SPY: never an orphan, no stop, outside the overlay cap and the sector gate.
2. **Dip sleeve** — 40 %: the live rule on the live list, unchanged; a slot is 25 % *of the sleeve* = `overlay_slot_pct` 10 % of equity (3 slots = 30 %); SPY is the sleeve's residual: `scale × 95 % × 40 % − held overlay − planned slots` (`mechanical.core_target_pct`).
3. **Shock trigger** — `signals.shock_state`: SPY's 10-session return ≤ −7 % on any of the last 20 sessions → exposure × 0.5, re-armed by every such session (the researched semantics); stateless, read each run from the last 31 SPY closes the bundle now carries (`market_context.spy.closes`); fails open on a short series.
4. **Exposure** = min(insurance, shock), never the product (Decision 067); both core legs scale with it, new entries pause while either is on (the watch reason says which), held positions keep their exits.
5. **Clean window** — `strategy.json` gains `window_started_at`, `design: "068"` and the sleeve at the first run with the sleeve on; `mechanical.benchmark_window_start()` anchors the daily benchmark there (`started_at` never moves — it is what separates mechanical positions from legacy ones).

Parameters in `data/watchlist.json → settings.mechanical` (`momentum_ticker`, `momentum_weight`, `shock_drop_pct`, `shock_lookback_days`, `shock_hold_days`, `shock_scale`; defaults in `TradingSettings`); `momentum_weight: 0` is the Decision 063 book. **Expectation, hindsight-free** (the sector floor stands in for the list): +1.4 pp/yr over SPY in a decade like the last (+3.0 without the insurance), worst drawdown ≈ −20 % vs −34 %, Sharpe 1.10 vs 0.89; century +3.6 with all four quarter-centuries ahead; the price is the rebound year after a crash (−8 to −11 relative). Whatever the curated list adds is a bonus that cannot be measured.

**Transition on deploy.** The three held overlay positions (≈ 67 % of equity) exceed the new 30 % overlay budget, so the first run computes a SPY target of 0 and sells the SPY core (≈ 28 %); SPMO buys what that frees, and the rest of its 57 % target fills as positions exit at their stops, targets or clocks — no forced selling of the overlay, every held exit unchanged. New entries are sized at 10 %. The plan log line and the Discord plan field show the shock state, the combined exposure and the sleeve target.

**Not changed**: the backtester (`backtest/mechanical.py` stays the dip-only book; the two-sleeve book is researched in `scripts/param_search`), the benchmark maths (vs SPY), the curator, the eight gates' thresholds, the exits. **Tests**: 243 (shock trigger semantics; the plan under the shock and the min() rule; the window stamp; the two-sleeve targets; the SPMO leg; the executor's SPY-then-SPMO order; slot sized on the dip sleeve; both core legs outside the overlay cap and the sector gate) — `conftest.fake_config` keeps `momentum_weight = 0` so the gate and sizing tests read as written; Decision 068 tests set 0.6. **Docs**: CLAUDE.md, features, todo (Phase 2.7), architecture, data_schemas, risk_management, api_reference.

**Deployed 2026-10-27 17:32 UTC** (commit `7196d0d`, operator's go): both images rebuilt and import-verified (CLI image through its `uv run` entrypoint: `momentum_weight` 0.6, `overlay_slot_pct` 0.1), API restarted, health ok, 7 jobs, 0 errors, build cache pruned (disk 44 %). First `signals` run stamped `window_started_at = 2026-10-27T17:32:42Z`, `design 068`; the bundle from the 13:00 UTC fetch predated the deploy, so a `fetch` was run at 17:33 UTC and `signals` again: 31 SPY closes in the bundle, shock off (worst 10-session move −2.4 %), risk-off no (breadth 54.5 %), exposure ×1.0, **SPMO target 57 %**, DXCM / JPM / URI held, 0 free slots, ANET on watch at 18.2 % (slots held). Book at the 14:15 UTC run: equity $111,197 — DXCM 23 %, URI 27 %, JPM 17 %, SPY 27.6 % (40 shares), cash 5 %. **First execute under the new book, triggered 17:35 UTC** (operator's go): plan SPY target 0 % (the 67 % overlay exceeds the 40 % sleeve), SPMO target 57 % → `SELL 40 SPY @ $769.71` ($30,788, trigger `core_rebalance`), then `BUY 216 SPMO @ $142.68` ($30,819) four seconds later with the freed cash; 2 actions, 0 warnings, job `completed` in 14 s. Book after the run: equity $111,885 — DXCM 23.0 %, URI 27.3 %, JPM 17.2 %, **SPMO 27.5 %**, cash 5.0 %; SPY 0. The remaining 30 points of the SPMO target fill as the overlay positions exit. Go/stop rule: the new clean window from `window_started_at`, judged the Phase 1.36 way; the go-live gate of Phase 2.0 is unchanged (paper) — gate recalibrated two days later in Decision 069.

### Decision 068 addendum — the post-crash tilt (operator: "we know we lose the year after a crash, why not change what we do?", 2026-10-29)
The five guards of the Decision 067 addendum moved the momentum sleeve into the *index* after a crash (±0.2 pp). This test moves it into the *dip sleeve*, the part of the book that wins in rebounds (`scripts/param_search/states.py --tilt`; hypotheses in the docstring). Three triggers (the shock trigger's hold expiring; the market ≥ 20 % off its 252-session low while ≥ 10 % below its high; the market re-crossing its 200-day SMA after 60+ sessions below) × hold 126 / 252 sessions × tilt to dip 100 % or 70 %; exposure rules unchanged on top; placebo = the same number of tilt windows at random dates, 20 draws. Gain = excess over the recommended book (decade +1.4, century +3.6).

| trigger / hold / tilt | decade: gain, IS / OOS; 2020 rebound year (book −24 vs market) | century: gain, 1927–74 / 1975–; 1932 (−53) · 2009 (−26) · 2020 (−16) rebound years | placebo gain, median (decade · century) |
|---|---|---|---|
| shock expired / 126 / dip 100 % | −0.2 (−0.8 / +3.3); 2020 −35 | −0.2 (+4.8 / +1.9); −20 · −17 · −19 | +0.1 · −0.9 |
| shock expired / 252 / dip 100 % | +0.2 (+2.1 / +0.9); 2020 −16 | **−0.7** (+4.9 / +1.0); −19 · −14 · +14 | −0.6 · −1.8 |
| rebound state / 252 / dip 100 % | +0.4 (+1.1 / +2.5); 2020 −16 | −0.2 (+4.5 / +2.4); −19 · −14 · +12 | −1.1 · −2.9 |
| rebound state / 252 / dip 70 % | +0.2; 2020 −20 | −0.1 (+4.8 / +2.3); −35 · −20 · −2 | −0.5 · −1.4 |
| re-cross SMA200 / 126 / dip 100 % | +0.6 (+0.3 / +3.7), on 2 triggers | −0.4 (+4.9 / +1.6); −31 · −27 · −16 | −0.0 · −0.6 |
| re-cross SMA200 / 252 / dip 100 % | +0.1 | **−1.2** (+3.6 / +1.2) | −0.0 · −0.7 |

Reading. The tilt does what the operator expected *inside* the grinding rebounds: 1932 goes from −53 to −19 and 2009 from −26 to −14 against the market. It also beats its placebo in every century cell (−0.2 vs −0.9, −0.7 vs −1.8 …), so the triggers carry real information about when the dip sleeve is the better sleeve. And the book still ends up flat to worse — decade gains −0.4 to +0.6 inside the placebo spread, century −0.1 to −1.2 in every cell — because the tilt is on 12–52 % of the time and the dip sleeve lags the momentum sleeve everywhere except the rebound itself; the V-shaped rebounds (2020 on the decade: −24 → −35 with the 126-session tilt) take back what the grinds give. Same answer as the index guards, from the other side: **you can recognise the state after a crash, you cannot recognise its shape, and the shape is where the money is.** Not adopted. The 40 / 60 book keeps the dip sleeve's rebound protection at its fixed weight, which is what the century chose.

### Decision 068 addendum — the literature brainstorm: 30 candidates, ranked, three proposed (handover task, 2026-10-29)
Operator: "the advantage of AI is that it knows everything more than I ever can, so we should utilise that heavily." Every published family named in the handover was put against *this* book before anything ran: momentum and its crashes (Jegadeesh–Titman; Moskowitz–Grinblatt; Daniel–Moskowitz; Barroso–Santa-Clara; Moreira–Muir), trend over a century (Moskowitz–Ooi–Pedersen; Hurst–Ooi–Pedersen), value / carry / trend (Asness–Moskowitz–Pedersen; Baltas–Kosowski), tactical and protective allocation (Faber; Antonacci; Keller–Butler), quality and low beta (Novy-Marx; Frazzini–Pedersen; Blitz), sizing (Kelly; Carver; Grinold–Kahn), daily mean reversion (Chan; Connors), execution (Lou–Polk–Skouras; Heston–Korajczyk–Sadka) and backtest honesty (Harvey–Liu; Bailey–López de Prado; McLean–Pontiff). **The finding before any test: the book already holds the two families with a century behind them (cross-sectional momentum, held; a dip rule that is the investable form of short-horizon reversal), and 15 of the 30 candidates are already closed by Decisions 062–068.** What remains is small. Priors are set by McLean–Pontiff (a published anomaly keeps about half of its in-sample return after publication) and by this project's own record (sixty rules tested, two kept).

Score = expected effect (pp/yr vs SPY, hindsight-free) × probability of surviving the walk-forward and the placebo ÷ cost (1 = an afternoon's test and a few lines to build, 2 = a day, 3 = a new module). *Closed* = Section 5 of the handover / the decisions above; the row says what would be new.

| # | idea (source) | hypothesis → what it adds, which sleeve | status | data | expected | test design (+ placebo) | P × cost → score |
|---|---|---|---|---|---|---|---|
| 1 | **T-bill carry on de-risked capital** (Faber and Keller–Butler park de-risked money in bills; the engine's own 0 % rule) | capital idled by the insurance or the shock earns the bill rate (SGOV) instead of 0 → return on both legs through `exposure_scale`; also the 5 % reserve if the broker lets a T-bill ETF back a bracket | new — the 0 % was a deliberate research bias, and the live book earns 0 too | French RF daily 1927 →; decade | +0.1…+0.3 in a decade like the last (rates were 0 in 2020, the biggest de-risked stretch); +1.5…+2 in a year spent half de-risked at 4 %; 0 at the zero bound | book × (1 − e) × RF by era; no placebo (carry, not a signal); build = a third core leg; **check first that the paper account credits ETF distributions** | 0.9 × 1 → **0.27** |
| 2 | **Shock early release on a +7 % / 10-session rebound** (the trigger's mirror; Daniel–Moskowitz: the rebound after the crash is where momentum is lost; this project's "you can detect the fall") | a fast rebound *fact* ends the ×0.5 hold early and recovers part of the rebound cost; bear-market rallies bounded by the re-arm on the next −7 % → return in V-rebounds, both legs | new — the tilt and the five guards were *state* rules; this is a fact rule symmetric with the trigger | decade + century | +0.3…+0.6 decade (2018-12, 2020-03, 2025-04), 0 ± 0.3 century (1929–32 and 2008 rallies hurt), drawdown within 2 points of −20 % | release = +5 / +7 / +10 % in 10 sessions, or a 10-session high; `regimes.py --grid` machinery; eras; walk-forward; **placebo = random release days, same count, 20 draws** | 0.35 × 1 → **0.14** |
| 3 | **The luck meter** (Harvey–Liu haircut; Bailey–López de Prado deflated Sharpe and probability of backtest overfitting via combinatorial purged CV; block bootstrap; a power calculation for the go/stop rule) | the decade's +1.4 is inside the selection noise of 4,140 trials, the century's +3.6 is not; the go/stop rule's return leg cannot be decided in a quarter → decision quality, every future test | new — the master search reports IS / OOS and a walk-forward, not a deflated statistic | the master grid | decade DSR ≈ 0.5 (a coin flip), century > 0.95; the return leg of the go/stop rule needs ~15 years at this tracking error — judge the drawdown leg only | compute; a `score()` extension so every later result carries it; no placebo (it is the placebo) | 1.0 × 1 → n/a (no return; folded into every test that runs) |
| 4 | **Relative (idiosyncratic) dip** (Lo–MacKinlay: contrarian profit is idiosyncratic reversal; Blitz–Huij–Martens residual momentum, mirrored) | a name 8 % below its high *relative to SPY* reverts more than a market-wide dip, where the shock trigger already pauses entries → dip-sleeve return | new | A / D / E / F | ± 0.5 | the dip on the P / SPY ratio, same walk-forward and universes, the Decision 062 consensus standard; no placebo (a parameter variant) | 0.3 × 1 → 0.12 |
| 5 | **Gap-dip filter** (Bernard–Thomas post-earnings drift; E's median trade = the stop) | a dip made in ≤ 2 sessions is news and keeps drifting; a grinding dip reverts → fewer stop-outs in the dip sleeve | new — `dip_max` tested the *size* of the fall, not its speed | A / D / E / F (closes) | +0.3 on the live universes, +1…+3 on E (not live) | `eligible` mask on the largest 1- or 2-day drop inside the dip; plateau over thresholds, both halves; the 8–20 % band was a lucky cut — require a plateau | 0.3 × 1 → 0.12 |
| 6 | **Value sleeve** (Asness–Moskowitz–Pedersen: value and momentum correlate −0.5 everywhere) | a value ETF as a third sleeve raises the Sharpe through the negative correlation → drawdown; return negative in a bull decade | partly closed — RSP / QUAL / USMV rejected as *vehicles*; value itself untested | decade IVE / VTV / VLUE (Alpaca download), century French BE/ME portfolios (download) | decade −0.5, century +0.5…+1, Sharpe +0.02 | three-sleeve blend in `master.py`; eras; walk-forward | 0.2 × 1.5 → 0.09 |
| 7 | **Residual-momentum name sleeve** (Blitz–Huij–Martens; Gutierrez–Prinsky) | top 15 by idiosyncratic 12-1 has half the crash risk of raw momentum and a steadier premium than SPMO → momentum-sleeve return | partly closed — self-picked raw momentum failed the reverse walk-forward (067 §2) | E | +1 vs SPMO, 2026-heavy | walk-forward both ways; placebo = 15 random names; S&P 400 still missing | 0.25 × 3 → 0.08 |
| 8 | **Vol-managed sleeve weight** (Barroso–Santa-Clara; Daniel–Moskowitz dynamic momentum) | momentum's *own* realised relative volatility forecasts its crashes; shift SPMO's share to the dip sleeve when it spikes (no leverage, no cash) | mostly closed — vol target −0.7…−1.2 marginal, five guards ± 0.2, drawdown × vol states = placebo; new piece: continuous, momentum's own vol, a weight shift | century WML + deciles; decade SPMO − SPY | 0 ± 0.3 | weight = clip(target / σ); placebo = block-shuffled vol series | 0.15 × 1 → 0.08 |
| 9 | **Industry momentum beside SPMO** (Moskowitz–Grinblatt; handover §6) | top 3 of the 17 sector + industry ETFs by 12-1 adds beside SPMO | open item; the six industry ETFs were chosen in 2026 (hindsight) | decade only | ≈ 0, correlation with SPMO high | `rotation.py` with the 17-ETF universe as the sleeve beside SPMO | 0.15 × 1 → 0.08 |
| 10 | **Member breadth for the insurance** (the analogue result: breadth is one of two variables that move the forward year) | the share of S&P members above their 200-day (point-in-time) fires the insurance earlier than 11 sectors | partly closed — the threshold was noise; the population is new | E; century industries (a different population) | ± 0.3 | insurance with member breadth; eras | 0.25 × 1 → 0.08 |
| 11 | **Halloween / turn-of-the-month** (Bouman–Jacobsen; Lakonishok–Smidt) | exposure ×0.5 May–October | closed in spirit — a slow de-risking rule at 0 % cash | century | decade −0.5, century +0.5 | placebo = random six-month windows | 0.1 × 1 → 0.05 |
| 12 | **Gold 10 % permanent** (Browne's permanent portfolio; risk parity) | a zero-correlation asset cuts the drawdown | multi-asset rotation closed; a fixed sleeve untested | decade only | −0.3 return, −1 point of drawdown — loses against SPY by construction | blend | 0.2 × 1 → 0.06 |
| 13 | **Entry timing by short-term reversal** (Chan; Connors RSI(2); French 1-0 deciles) | enter the dip after one more down day | partly closed — entry-time features flip sign between halves (066) | A / D / F | +0.2 | variant; eras | 0.2 × 1 → 0.04 |
| 14 | **Execution timing** (Lou–Polk–Skouras overnight vs intraday; Heston–Korajczyk–Sadka) | the 15:30 run beats the 10:15 run by the average intraday drift | new, but the book's turnover is ~60 % of equity a year: 10 bp = 0.06 pp/yr | Alpaca 15-minute bars | +0.05 | measure 10:15 / 15:30 / close on the signal days; live note: paper fills at the last price, a live marketable limit pays the half-spread (1–3 bp here) | 0.5 × 2 → 0.01 |
| 15 | **Fill-vs-backtest ledger** (method) | the live book's distance from the backtest is one number per trade (fill vs the backtest's next close) | new; build only | live trade log | informational — the "behaves like the backtest" leg of the go/stop rule | a column in the trade record | 1.0 × 1 |
| 16 | **Curator skill ledger** (method; the analyst had no ranking skill) | the monthly LLM proposal's adds and removes have no ranking skill either | new; build only | live | informational | shadow-track every proposal vs the outcome | 1.0 × 1 |
| 17 | **Gate valuation** (Frazzini–Lamont earnings-announcement premium; Lucca–Moench pre-FOMC drift) | the earnings and macro blackouts cost more than they save | new; live data only (no historical earnings dates) | near misses, at 6 months | +0.1 | near-miss outcomes vs executed | 0.3 × 1 → 0.03 |
| 18 | Kelly / fractional Kelly for the slots (Kelly; Thorp) | — | **closed**: the dip weight 30–50 % and the slot grid bound it; Kelly on p ≈ 0.7, b = 1.67 says f* ≈ 0.6 of the sleeve — the sleeve is under-Kelly on purpose (Sharpe, drawdown) | | | | |
| 19 | Forecast-scaled sizing (Carver) | — | **closed**: trade-level features flip sign between halves (066); ATR sizing = noise (061) | | | | |
| 20 | Breadth of bets (Grinold–Kahn) | — | **closed / structural**: ~20 trades a year carry little information ratio whatever the skill; two dip universes (corr. 0.4) summed to nothing (067) | | | | |
| 21 | Momentum-crash guards (Daniel–Moskowitz) | — | **closed**: five published guards ± 0.2 (067 addendum) | | | | |
| 22 | Vol-managed book (Moreira–Muir) | — | **closed**: the vol target −0.7…−1.2; the published gain needs leverage the book cannot take | | | | |
| 23 | Time-series momentum, trend, GTAA, dual momentum, PAA (Moskowitz–Ooi–Pedersen; Hurst–Ooi–Pedersen; Faber; Antonacci; Keller–Butler) | — | **closed**: own-momentum −0.4, trend-break −1.6, GTAA −10, multi-asset rotation −5…−10, SPY > SMA switches (060 f, 067) | | | | |
| 24 | Low volatility, betting against beta, quality (Frazzini–Pedersen; Blitz; Novy-Marx) | — | **closed** as vehicles (USMV −4.8, QUAL −0.7) and as screens (066); as a fundamentals filter on the dip list: no fundamentals data | | | | |
| 25 | Daily mean-reversion overlay on the SPY residual (Chan) | — | **closed by arithmetic**: daily turnover × 0.05 % a side ≈ 25 pp/yr of cost | | | | |
| 26 | Tail hedge with puts or VIX calls (Bhansali; Spitznagel; AQR "Pathetic Protection") | — | **dropped**: no option history; the literature's cost is −3…−4 %/yr; the shock trigger does the job at ≈ 0 | | | | |
| 27 | Managed-futures sleeve (crisis alpha) | — | **dropped**: no futures on Alpaca; ETF proxies start 2019 | | | | |
| 28 | Covered calls (BXM) | — | **dropped**: gives up the bull upside, loses to SPY by construction | | | | |
| 29 | SPMO vs 30 / 30 SPMO + MTUM (handover §6) | — | a judgment on index-construction risk (~1 pp/yr this decade), not a test | | | | |
| 30 | Shock on SPMO only / insurance on the sleeve only | — | **closed**: master-search variants (067 addendum) | | | | |
| 31 | **A quality short list without hindsight: the Dow 30, point-in-time** (the Decision 065 lesson: the dip rule is "a small edge on a short list of quality names and adverse selection on a long list of anything") | the curated list's +4 comes from being a short list of large, established names, so the dip rule on the Dow 30 with its actual 2016 → 2026 membership (public, a handful of changes) reproduces part of it → a hindsight-free dip universe with a bigger edge than the sector floor, or the proof that the list's edge is luck | new — every universe tested so far was broad (500), screened, or ETFs | E (the Dow names are S&P 500 members) + a membership list from the public record | +1 … +2 if the hypothesis holds, 0 … −1 if not | both halves vs SPY and vs the equal-weight Dow, membership mask; **placebo = 20 random 30-name subsets of the point-in-time S&P 500** (is a short list of big names special, or any short list?) | 0.3 × 1 → **0.45** |
| 32 | **Cash-secured puts as the dip entry** (CBOE PUT index; Israelov–Nielsen) | selling a put struck at the dip level collects the post-fall premium and, if assigned, is the same long position → dip-sleeve return (+1 … +2 at the sleeve, the PUT index's record vs the S&P) | new | **none** — no option history in the harness; paper-only (Alpaca options level 1) | +1 … +2, unmeasurable here | cannot be tested the project's way; a paper sleeve could only be *watched*, and the luck meter says a paper window cannot judge return | untestable — recorded, not proposed |
| 33 | **The entry-time model, done properly** (the "can AI pick the trades" question; ridge / logistic on the century's ~1,100 industry dip trades) | nothing known at entry (depth, speed of the fall, market state, breadth, volatility, the industry's own momentum) predicts the trade beyond the market regime; a model trained 1927–74 and tested 1975 → does no better than shuffled labels | partly closed — 066 found entry features flip sign between halves on E (637 trades); the century has twice the trades and a placebo | F | +0.5 if anything survives | train / test by era both ways; **placebo = shuffled trade outcomes, 20 draws** | 0.15 × 1 → 0.08 |
| 34 | **Dials already measured — decisions, not tests**: momentum weight 60 → 70 (decade +2.3 vs +1.4, Sharpe 0.99 vs 1.10, DD −30 vs −20 at 70 / 30 in 067 §5; the master family runs to 70); insurance off (decade +3.0 vs +1.4, century DD −64 vs −59 %, 1973 +5 vs +21); the dip sleeve's SPY residual held in SPMO instead (≈ raising the momentum weight by the residual's share) | — | the largest return levers in the book, all trade-offs the master search priced; the operator chose Sharpe and the long-bear insurance | | | | |
| 35 | **Leverage to SPY's volatility** (the book runs ~14 % volatility at Sharpe 1.10 against SPY's 19 % at 0.89) | 1.3 × through margin at 5–6 % would add +1.5 … +2 net *if* the live book keeps its Sharpe, and scales every drawdown by the same factor | new; structural | decade / century (scaling is arithmetic) | +1.5 … +2 before the drawdown cost | nothing to test; a decision that must wait for live proof of the Sharpe, which the luck meter says takes years | recorded, not proposed |
| 36 | **Dip-entry seasonality** (Bouman–Jacobsen; the September effect) | entries opened in certain months lose; skipping them helps | new; cheap | F (1,100 trades by month) | +0.2 | by month, both eras; placebo = shuffled months | 0.1 × 1 → 0.02 |

**Ranking and the three proposed** (rows 31–36 were added on 2026-10-29 after the operator asked for more; row 31 now ranks first among the open ideas): (1) pay the de-risked half the T-bill rate — small, nearly certain, free; (2) let a fast rebound end the shock hold early — the one new fast-fact rule, cheap to test, with its placebo; (3) the luck meter — not a return idea, but it tells the operator what the +1.4 and the +3.6 are worth and reframes the go/stop rule; it rides along with whichever test runs. Candidates 4 and 5 are the next return ideas if the operator wants more dip-sleeve tests. Everything from 18 down is recorded so that it is not re-proposed. **Nothing has run; nothing live changes.**

### Decision 068 addendum — the three chosen tests: T-bill carry (build when live), shock early release (rejected), the luck meter (the decade is a coin flip, the century is not; the go/stop rule needs recalibrating) (2026-10-29)
Operator's pick from the brainstorm: all three, in order. Scripts `scripts/param_search/carry.py`, `release.py`, `luck.py`, hypotheses in each docstring before the first run; recommended book = min(insurance ×0.5, shock ×0.5) × (0.4 dip + 0.6 momentum), decade = sector dip book + SPMO 2017 → 2026-10 (split 2022), century = dip on 49 industries + top momentum decile 1927 → 2026-08 (split 1975, four eras); de-risked capital earns 0 unless stated. **Nothing live changes.**

**1. T-bill carry on de-risked capital** (`carry.py`; RF = Kenneth French's daily T-bill return): the idle half earns the bill rate instead of 0.

| book | decade: excess / IS / OOS, DD, Sharpe, worst yr | century: excess / 1927–74 / 1975–, DD, Sharpe; eras |
|---|---|---|
| recommended (idle at 0) | +1.36 / +0.27 / +2.46, −20.0 %, 1.10, −11.3 | +3.63 / +5.03 / +2.18, −58.6 %, 0.86; +4.6 / +5.5 / +3.3 / +1.2 |
| + idle capital in bills | +1.54 / +0.42 / +2.66, −19.9 %, 1.11, −11.2 | +4.15 / +5.45 / +2.80, −57.7 %, 0.89; +4.7 / +6.3 / +4.2 / +1.5 |
| + idle capital and the 5 % reserve in bills (reference, the reserve must stay spendable) | +1.68 / +0.49 / +2.89, −19.9 %, 1.12 | +4.32 / +5.55 / +3.04, −57.6 %, 0.90 |

Pickup **+0.17 pp/yr on the decade** (de-risked 15.5 % of sessions at a mean 1.9 % bill rate while de-risked; by year 2018 +0.39, 2022 +0.39, 2025 +0.31, 2020 only +0.12 because rates were 0) and **+0.52 on the century** (de-risked 30 % of sessions at 3.0 %; 1974 +3.9, 1982 +3.3, 1969–70 +2.2 / +2.5, the 1930s and 2009–15 ≈ 0). C1 and C3 confirmed (no era changes sign, drawdown unchanged); C2 slightly exceeded. **C4 confirmed on the account: the paper account has recorded no dividend activity at all** (Alpaca activities `DIV*` since 2025-10 → 0 while SPY was held through the March, June and September ex-dates; only FILL, FEE and the CRWD SPLIT appear), so a T-bill ETF on paper shows its price accrual and the ex-date drop with no cash, ≈ 0 net and invisible. **Verdict: a go-live item, not a paper build** — at funding, either the live account pays interest on cash (check Alpaca's cash programme first) or SGOV becomes a third core leg sized `(1 − exposure_scale) × 95 %`; worth about +0.2 pp/yr in a decade like this and +2 to +4 in a year spent half de-risked at today's rates. Added to the Phase 2.0 go-live checklist. The research engine keeps 0 % for selecting rules (the bias is deliberate) and `carry.py` is the honest-expectation line.

**2. Shock early release on a fast rebound** (`release.py`): a +X % move over N sessions ends the shock's ×0.5 hold early; eight release cells, the unconditional hold-10 / hold-5 cells as reference, placebo = the same number of releases at random sessions inside the holds, 20 draws.

| release rule | decade: gain vs book (+1.36), IS / OOS, DD (−20.0 %), releases; placebo median [p10…p90], share beaten | century: gain vs book (+3.63), DD (−58.6 %), 1932 rebound (−28 vs market); placebo, beaten |
|---|---|---|
| reference: hold 10 / hold 5, no release | −0.08 / +0.19; DD −21.8 / −21.5 % | +0.00 / −0.06; DD −64 / −65 %; 1932reb −44 / −43 |
| +5 % over 5 / 10 sessions | −0.26 / −0.32; DD −22.4 / −22.5 %; 7 / 7 releases; placebo +0.10 / +0.09, beaten 5 % / 0 % | −0.34 / −0.23; DD −67 / −64 %; 1932reb −49 / −48; beaten 0 % / 5 % |
| +7 % over 5 / 10 sessions | −0.07 / −0.07; DD −20.0 %; 2 / 4 releases; placebo 0.00, beaten 35 % / 10 % | −0.25 / −0.18; DD −68 / −62 %; 1932reb −50 / −42; beaten 5 % / 5 % |
| +10 % over 5 / 10 sessions | 0.00 / 0.00; 1 / 2 releases | −0.06 / −0.04; DD −60 / −59 % |
| 10- / 20-session high | −0.22 / −0.06; DD −22.4 / −20.0 %; 10 / 6 releases; placebo +0.03 / +0.12, beaten 10 % / 20 % | −0.21 / +0.06; DD −63 / −59 %; beaten 5 % / 75 % |

Every decade cell is ≤ 0 and below its placebo; every century cell is ≤ +0.06 with a worse drawdown; the rebound episodes do not move (2020 −19.6, 2018 −6.3, 2022 −10.2 / −8.3 unchanged in every cell, 2025 −6.9 → −7.6). R1 and R3 fail, R2 holds, R4 moot. **Why there was nothing to release: in every decade rebound the two-signal insurance was the binding rule** — SPY below its 200-day SMA with breadth under 50 % in 2018-12, 2020-03, 2022 and 2025-04 — and exposure = min(insurance, shock), so ending the shock hold changed nothing while the insurance held; where the release did act (bear-market rallies: 1932, 2008, 2022-06) it re-exposed the book into the next leg down. The shock trigger's own territory is the fall from *above* the SMA with breadth intact (the first days of 2020-02 and 2025-02); its hold has already expired by the time those rebounds come. **Rejected** on the pre-registered drop rule (decade gain < +0.2 in every cell, placebo not beaten). Closed door: a fast *release* rule for the shock trigger.

**3. The luck meter** (`luck.py`; statistics on the daily *active* return, book minus market; pool = every hindsight-free book of the master grid, 2,205 on the decade across the three vehicles, 765 on the century):

| statistic | decade | century |
|---|---|---|
| excess CAGR / arithmetic mean active return / tracking error / information ratio | +1.36 / **+0.72** / 9.1 %/yr / 0.08 | +3.63 / +3.08 / 9.9 %/yr / 0.31 |
| t-statistic on the whole sample (Harvey–Liu hurdle t > 3) | **0.25** on 10 years | **3.16** on 103 years |
| effective independent trials in the pool (participation ratio of the trial correlations) | 1.4 of 2,205 (the grid varies two things: how much momentum, how much de-risking) | 1.5 of 765 |
| deflated Sharpe, P(skill): no search / N_eff / every cell counted as independent | 91 % / **58 %** / 5 % | 100 % / **99.8 %** / 25 % |
| the recommended book's rank in the pool by active Sharpe | 292 of 2,205 | 112 of 765 |
| probability of backtest overfitting (CSCV, 16 blocks, 12,870 splits); IS-best's OOS Sharpe vs IS; IS-best loses OOS | 4 %; +0.45 vs +0.87 (slope −0.69); 8 % | 0 %; +0.47 vs +0.54; 0 % |
| block bootstrap of the excess CAGR, 5 % / median / 95 %; P(excess > 0); Sharpe difference 5–95 % | **−2.8 / +1.3 / +5.1; 69 %**; −0.07 … +0.42 | **+1.9 / +3.6 / +5.2; 100 %**; +0.12 … +0.33 |
| go/stop power — years to t = 2 at a true +1.4 / +3.6 pp/yr | **170 / 26** | 200 / 30 |
| one quarter at a true +1.4: fails "≥ SPY − 2 pp/yr" / shows ≥ SPY at all; one year: fails | **43 % / 53 %; 35 %** | 43 % / 53 %; 37 % |
| drawdown leg as written (book's fall ≤ 0.7 × SPY's in every SPY drawdown ≥ 10 %) | **2 of 5**: 2020 −20 vs −34 ✓, 2022 −15 vs −24 ✓; 2018-01 −9 vs −10 ✗, 2018-Q4 −18 vs −19 ✗, 2025 −17 vs −19 ✗ | 9 of 31 |

Readings. (a) **The decade proves nothing by itself**, with or without deflation: an information ratio of 0.08 and t = 0.25 — half of the +1.4 is the lower volatility (arithmetic +0.7), and the bootstrap band runs from −2.8 to +5.1. The deflation is almost beside the point: the grid was effectively one or two trials, not 2,205, so the deflated probability (58 %) equals the undeflated coin flip; counting every cell as independent (5 %) overstates the search. L1's first half holds; its second half (PBO > 0.3) does not — PBO is 4 % because the pool's ranking is stable within the decade (momentum-heavy books lead in nearly every block), which is a statement about the family, not about the decade's evidence. (b) **The century is the evidence**: t = 3.16 clears the Harvey–Liu hurdle, the bootstrap band is +1.9 to +5.2, PBO 0 %, and the deflated probability is 99.8 % at the effective trial count (25 % only if 765 near-copies are counted as independent trials, and the book is not even the pool's best — it ranks 112th, a plateau centre). L2 and L3 hold. (c) **The go/stop rule cannot be met on its return leg**: at a 9 %/yr tracking error a true +1.4 needs about 170 years to reach t = 2; over one quarter the book fails "≥ SPY − 2 pp/yr" 43 % of the time and beats SPY only 53 % of the time *when it is exactly as good as the backtest*; a year hardly helps (35 %). L4 holds. (d) **The drawdown leg as written fails the design's own backtest**: the book fell no further than SPY in all five ≥ 10 % drawdowns, but was ≤ 0.7 × SPY's fall only in the two slow, deep ones (2020, 2022) — in a 10–19 % dip the insurance and the shock trigger barely engage, by design, and the book tracks SPY. A rule the backtest fails 3 times in 5 would stop a working book at the first fast dip.

**Recommendation to the operator (their call; rule text in todo Phase 2.0):** rewrite the go/stop rule as (i) *behaves like the backtest* — the fill-vs-backtest ledger (brainstorm #15) and the plan's actions matching the rules, judged at every checkup; (ii) *drawdown* — in any SPY drawdown ≥ 10 % the book falls no further than SPY, and in any ≥ 20 % no further than 0.7 × SPY; (iii) *return* — no quarterly or yearly return test at all: the return edge is a century claim and a decade cannot confirm or refute it; report the running excess with its bootstrap band instead. The live benchmark's verdict line should say so under 3 years rather than "adding / losing value". Nothing changed yet.

### Decision 068 addendum — three more dip-sleeve tests: the Dow 30 as a quality list, the dip relative to SPY, the fast-dip filter — all three rejected (operator's pick, 2026-10-29)
`scripts/param_search/dipfilters.py` (`--dow`, `--relative`, `--gap`; hypotheses in the docstring before the first run; `fastbt.py` gained a default-off `rank_matrix` option, equivalence re-verified: same trade set, equity to 6e-9). Live rule, insurance ×0.5, decade from 2017-01-03 split 2022, century split 1990, vs SPY and vs the equal-weight hold of each universe. References in the same run: **A** curated 15 +4.0 (IS −8.4 / OOS +17.8), **D** sectors +0.4 (+0.6 / +0.3), **E** S&P 500 point-in-time 3 × 25 % −0.2 (−1.9 / +1.6), **F** industries −0.0 (+0.9 / −1.8).

**1. The Dow 30, point-in-time (brainstorm #31)** — the 2016-01-04 list and its ten changes through 2024-11 (public record); placebo = 20 random 30-name subsets of the 2016 S&P 500 under the S&P membership mask.

| universe | excess vs SPY (IS / OOS) | vs EW of the universe | DD, Sharpe | trades, win, median, stops |
|---|---|---|---|---|
| Dow 30, 3 × 25 % | **−7.9 (−7.3 / −8.5)** | −5.2 (EW Dow −2.7 vs SPY) | −31 %, 0.50 | 123, 51 %, +0.6, 34 |
| Dow 30, 5 × 15 % | −9.5 (−9.9 / −9.2) | −6.9 | −28 %, 0.44 | 196, 52 %, +0.7, 58 |
| Dow 30, insurance off | −5.5 (−5.7 / −5.4) | −2.9 | −36 %, 0.57 | 123 |
| placebo: 20 random 30-name S&P subsets | median **−2.7**, p10 −8.3, p90 −0.6, 1 of 20 positive | | | |

D1 fails (negative in both halves, below the sector floor), D2 fails the other way round — the Dow sits at the *bottom* of the placebo spread, and the placebo itself says it all: **any 30-name list of S&P names loses with this rule** (19 of 20 random lists, median −2.7). D3 holds (five slots worse). Reading: "a short list of quality names" was the wrong diagnosis of Decision 065. The dip rule's edge lives in exactly two places, the 11 diversified sector ETFs (no single-name blow-ups, 79 % winners, 6 stops in ten years) and the operator's 15 names after 2022; every list of individual large caps, the Dow included, feeds the rule single-name breaks it cannot tell from dips (51 % winners, median trade +0.6 %). **The curated list's +4 is the list, not a reproducible property of big established names.** Rejected; closed door: a hindsight-free single-name universe for the dip rule, of any size.

**2. The dip relative to SPY (brainstorm #4)** — eligibility and ranking on P / SPY, 6 / 8 / 10 %, and "both" (absolute 8 % and relative 8 %):

| universe | absolute 8 % (live) | relative 6 / 8 / 10 % | both |
|---|---|---|---|
| A curated | +4.0 (−8.4 / +17.8) | +4.0 / +3.9 / +1.4 | +4.3 (−5.8 / +15.4) |
| **D sectors** | +0.4 (+0.6 / +0.3) | **−3.8 (−3.9 / −3.6) / −5.1 (−4.7 / −5.4) / −3.5 (−3.3 / −3.7)** | −1.0 (+0.1 / −2.0), 32 trades |
| E S&P 500 PIT | −0.2 (−1.9 / +1.6), median trade −3.3 | −0.0 (−2.2 / +2.2) at every threshold, median −0.1, Sharpe 0.69 | −1.6 |
| F industries | −0.0 (+0.9 / −1.8), Sharpe 0.64 | +0.4 (+1.2 / −1.0) / +0.2 (+1.1 / −1.6) / +1.0 (+2.3 / −1.4), Sharpe 0.71–0.76 | +0.8 (+1.4 / −0.3) |

R1 fails hard on D: a sector 8 % below its high *relative to SPY* is a sector that is lagging the market — the anti-momentum trade, −4 to −5 pp/yr in both halves (Decision 066 again, from the other side). R2: the broad universe moves from −0.2 to 0.0 — the median trade improves, the book does not. R3: "both" is the best variant on A and F and still not positive in both halves anywhere hindsight-free. The rule needs a real fall in price, not a lag behind the index. Rejected.

**3. The fast-dip filter (brainstorm #5)** — exclude names with a session worse than −5 / −8 / −12 % in the last 20, or require the dip to be ≥ 5 / 10 sessions old:

| universe | live | no session < −5 / −8 / −12 % | dip ≥ 5 / ≥ 10 sessions old |
|---|---|---|---|
| A curated | +4.0 | −3.1 / +4.4 / +3.9 | +1.5 / −3.4 |
| **D sectors** | +0.4 (+0.6 / +0.3) | **0.0 / +0.4 / +0.4** (ETFs do not gap: identical trades) | −1.6 / −3.0 |
| E S&P 500 PIT, 3 × 25 % | −0.2, median −3.3, 94 stops | **+3.0 (+10.4 / −4.0)**, median +4.6, 57 stops / +2.8 (+6.1 / −0.5) / +0.3 | **+5.1 (+4.9 / +5.4)**, Sharpe 0.84 / −2.9 (+1.6 / −7.1) |
| E, 10 × 7.5 % | −4.3 | −5.5 / −6.4 / −6.4 | −3.9 / −3.9 |
| F industries | −0.0 (+0.9 / −1.8) | −0.5 / +0.1 / −0.3 | +0.5 (+1.5 / −1.4) / +0.3 (+1.1 / −1.2) |

G1 holds on the surface of E — the −5 % filter does raise the median trade from −3.3 to +4.6 and cuts stops from 94 to 57 — and fails where it counts: the gain is in-sample only (+10.4 / −4.0), it vanishes at ten slots, and it never reaches the universes that matter (D identical, F ±0.5: G2 holds). G3's "dip at least five sessions old" is the one cell positive in both halves on E (+5.1), with its neighbour at ten sessions −2.9 and the same rule negative on D and F — a single cell, the 8–20 % band of Decision 065 again. **Nothing changes the hindsight-free floor** (D and F) by more than noise, which is the drop rule. Rejected. Note for the record only: if a broad single-name universe ever became the live one, the speed of the fall is the first thing to re-examine there (median trade and stop count move the right way); for the live list and the sector floor it is irrelevant.

**Decision**: nothing changes. Three doors closed with numbers: a hindsight-free single-name list for the dip rule (any 30-name list loses, the Dow at the bottom of the placebo), the relative dip (the anti-momentum trade on sectors), and the speed-of-fall filter (nothing to filter on ETFs, in-sample only on 500 names). The dip sleeve stays the live rule on the live list with the sector floor as its hindsight-free expectation. Remaining open ideas from the catalogue are the lower-odds rows (value sleeve, residual momentum, member breadth, the entry-time model on the century); none is proposed.

### Decision 068 addendum — the rest of the catalogue: member breadth, the entry-time model, volatility-managed sleeve weight, industry rotation, gold, Halloween, entry month, a down-day entry, a value sleeve, residual momentum — none adopted (operator: "pick up the research", 2026-10-29)
Scripts `breadth2.py`, `entrymodel.py`, `sleeveweight.py`, `seasons.py`, `value.py`, `resmom.py` (hypotheses in each docstring before the first run). Recommended book = min(insurance ×0.5, shock ×0.5) × (0.4 dip + 0.6 momentum): decade +1.36 (IS +0.3 / OOS +2.5), DD −20.0 %, Sharpe 1.10; century +3.63 (+5.0 / +2.2), DD −58.6 %, Sharpe 0.86. New data: the value ETFs IVE / VTV / VLUE / IWD / RPV (Alpaca SIP, **dividend-adjusted like the archive** — a first price-only fetch shifted the SPY reference to +2.27 and was discarded; the archived series are total-return) and Kenneth French's daily book-to-market portfolios (`Portfolios_Formed_on_BE-ME_Daily.csv`).

| # | idea | result (decade / century) | verdict |
|---|---|---|---|
| 10 | **member breadth for the insurance** (S&P 500 members above their 200-day, point-in-time; 49 industries on the century) | decade: members < 50 % **+2.15 (+0.7 / +3.6)** vs the live sector breadth +1.36, Sharpe 1.16 vs 1.10, DD same, on 14.8 % vs 13.2 % of sessions, plateau over 40 / 50 / 60 %; but **a block-shuffled breadth series scores +2.7 … +2.9** (p10 +2.1), above *both* real measures, and "SMA200 only" (no breadth) is +2.15 too — in this decade any loosening of the insurance pays, which is the known era trade-off, not information. Century: industry breadth as the second signal +3.50 … +3.57 vs +3.63, inside its placebo (+3.60 [+3.34 … +3.91]) | **not adopted** — neither breadth measure carries information a random series does not; the decade's preference is for less insurance |
| 33 | **the entry-time model** (ridge on 10 entry-time features; 1,156 century trades, 199 / 623 S&P trades; placebo = shuffled outcomes) | out-of-sample rank correlation: century −0.03 (early → late) and −0.13 (late → early), S&P −0.04 / −0.05 and −0.06 / +0.01 — every one inside or below its placebo; top-half-of-predictions minus bottom-half: −0.4, −2.7, −1.9, −1.6, −2.4, +1.4 pp per trade; the univariate signs flip between eras for every feature, the market regime included (+0.07 → −0.03) | **closed**: nothing known at entry predicts the trade; "can AI pick the trades" is answered on a century with a placebo |
| 8 | **volatility-managed momentum share** (SPMO's share = 0.6 × target / σ of SPMO − SPY over 126 sessions, clipped 30–60 %, the rest to the dip sleeve; placebo = the σ series block-shuffled) | decade: targets 5 / 7 / 9 % → −0.68 / −0.17 / +0.29 vs the book, Sharpe +0.01 … +0.04, DD same, the 2023 rebound year unchanged; the 7 % cell sits inside its placebo (−0.35 [−0.68 … +0.31], beaten 55 %). **Century: 8 / 10 / 12 % → −0.05 / +0.25 / +0.38, Sharpe 0.86 → 0.88 / 0.90 / 0.90, all four eras positive, and the 10 % cell beats every placebo draw** (placebo −0.36 [−0.45 … −0.23], which already controls for the lower mean momentum share of 53 %) | **not adopted** — the Barroso–Santa-Clara effect exists in long-only form on the century (≈ +0.6 pp/yr of timing over a static book with the same mean share) and is invisible on the decade (slightly worse in both halves). Fails "both eras"; the one century-only survivor of the day. Revisit only once the decade holds a momentum crash the rule could have timed |
| 9 | **industry momentum beside SPMO** (top 3 of the 17 sector + industry ETFs by 12-1, monthly) | the rotation sleeve alone −0.76 vs SPY, correlation 0.31 with SPMO's excess; dip 40 / SPMO 40 / rotation 20 → **−1.1**; 40 / 30 / 30 → −1.7; SPMO replaced → −3.6; the six industry ETFs were chosen in 2026 | **rejected** — the same bet in a worse vehicle |
| 12 | **gold 10 %** (GLD, from SPMO / from the dip sleeve / unscaled) | return −0.32 / −0.17 / −0.09 vs the book; **DD −20.0 → −18.3 %, Sharpe 1.10 → 1.18 / 1.15 / 1.18**; IS −0.5 … −0.8, OOS +2.7 … +3.2; 2023 rebound −11.3 → −11.5 … −11.9 | **not adopted** — a drawdown instrument that costs return and loses to SPY by construction, on a decade in which gold made ~13 %/yr; no century data for gold; the in-sample half is negative |
| 11 | **Halloween** (exposure ×0.5 six months from each start month; the other eleven phases are the placebo) | decade: every phase −1.4 … −5.4, May ranks 10 of 12; century: every phase −2.5 … −4.0, May is the best phase and still −2.5 at Sharpe 0.84 < 0.86 | **rejected** — a slow de-risking rule at 0 % cash, as predicted |
| 36 | **entry month** (1,161 century trades by entry month; placebo = shuffled months) | 1927–74: largest month deviation 4.8 % vs placebo 4.0 [3.1 … 5.2]; 1975 →: 5.6 % vs 3.3 [2.5 … 4.3], driven by July (+4.7 → −2.9, flips) and November / December (+5.0 / +7.1 → +6.4 / +4.9 — the one pattern both eras share: the January effect for beaten-down names) | **not adopted** — no month is consistently bad; the Nov–Dec edge is real-looking and not actionable (the rule cannot create dips, only skip them) |
| 13 | **one more down session before the entry** (and its mirror) | A +6.8 vs +4.0; **D +1.1 (+1.2 / +0.9) vs +0.4**, 59 trades vs 61; **E −8.9 vs −0.2**, DD −58 %; F +0.2 (+0.9 / −1.1) vs −0.0; the mirror: D −2.2, F +1.0 (+2.1 / −1.1), E −7.2 | **rejected** — not both halves on F, the mirror's sign flips between D and F, and on single names it is the falling knife (E −8.9) |
| 6 | **a value sleeve** (VLUE / IVE / VTV / IWD / RPV; French "Hi 30" book-to-market on the century) | alone: decade −1.3 … −5.3 vs SPY (worst years −15 … −26); century Hi 30 +1.5 (all four eras, DD −83 %), Hi 10 +2.0 at −92 %. Correlation of value's excess with SPMO's: decade −0.03 … −0.36, **century +0.11** (long-only value carries the market like long-only momentum does). Books: decade every variant −0.4 … −1.45 vs the book with the first half negative; century −0.1 … −0.9 from SPMO (Sharpe +0.01 … +0.03), the one positive cell dip 20 / SPMO 60 / value 20 at +0.30 is −0.5 on the decade | **rejected** — the AMP diversification is a long-short property; long only, value is a drag in a bull decade and a wash over the century |
| 7 | **residual momentum** (top 15 by residual 12-1 on the point-in-time S&P 500, yearly from 2018; placebo = random 15) | **−2.8 (−2.5 / −2.9), through 2025 −6.5**, DD −37 %; top 30 −0.7; raw 12-1 momentum +10.3 (+7.7 / +12.4), SPMO +5.0, equal-weight members −4.0; placebo −4.2 [−7.7 … −1.2] — residual momentum is a random pick | **rejected** — the published "half the crash risk" is a long-short, monthly, multi-factor result; the long-only daily analogue has no premium here |

**Reading.** Ten more rows closed; the catalogue is now exhausted except for the live-data items (gate valuation, the curator ledger) and the untestable ones (puts, leverage). Two things are worth remembering: (1) **a placebo that beats both the candidate and the incumbent is a verdict on the era, not the signal** — on the decade a random breadth beat both real breadth measures because the decade rewards less insurance, full stop; (2) the only effect that beat its placebo anywhere, volatility-timing the momentum share, did so on the century alone (≈ +0.6 pp/yr of timing, Sharpe 0.86 → 0.90) and is invisible on the decade — the project's "both eras" rule keeps it out, and that is the right call for a rule whose whole value sits in crashes the decade does not contain. **Nothing changes.**

## Decision 067: "Add the strategies together" — tested; the broad dip sleeve is dead, a momentum-ETF sleeve beside the dip book is the first hindsight-free combination that beats SPY in both halves. Proposal on the table, nothing live yet
**Date**: 2026-10-27
**Operator proposal**: keep the dip rule on the curated list, add a momentum sleeve on the S&P 500 and a 10-slot dip rule on the S&P 500, "adding the strategies together and hedging this way"; any amount of backtesting authorised. Tested as a portfolio of sleeves (`scripts/param_search/combo.py`, `etf_sleeve.py`): every sleeve is a full book with its own SPY residual and the two-signal insurance, so a weighted blend of sleeve curves is the combined book with the capital split by weight; walk-forward on the two new rules first; the curated sleeve (hindsight by construction) shown beside the sector-ETF dip sleeve as its hindsight-free floor; the same combination over the century on French data.

1. **Broad dip sleeve (dip rule on the S&P 500 membership, 6–15 slots): dead.** With honest point-in-time membership every variant is negative in both halves (10 × 7.5%: −4.3 pp/yr, IS −1.9 / OOS −6.6; walk-forward picks lose both ways, 0 of 10 rules positive in either test). The +1.4 reported in Decision 065 came from a universe that was not point-in-time: without the membership mask the 742-name union makes +6.7, because it lets the rule buy names *before* they joined the index — index inclusion is itself a record of past strength, i.e. look-ahead. Names added after 2016, traded only while members: −10.1. The dip rule does not scale to a broad single-name universe under any slot count.
2. **Momentum sleeve of self-picked names: era-dependent, fails the reverse walk-forward.** Train 2017–21 → test 2022–26 passes (picked rule +14.7 in test, 29 of 36 rules positive); train 2022–26 → test 2017–21 fails (−8.9, 12 of 36 positive). A rule with three fitted parameters cannot be trusted on this decade alone.
3. **The momentum premium is reachable without fitting anything: a momentum ETF held outright.** 2017-01 → 2026-10, total return, vs SPY: MTUM +1.7 pp/yr (IS +2.2 / OOS +1.2), SPMO +5.2 (+2.1 / +8.4), both with SPY-like drawdown; for contrast USMV −4.8, QUAL −0.7, RSP −3.8 (the same verdicts the name-level screens gave low volatility and equal weight). No parameters, expense ratios already in the price, one ticker to hold.
4. **Dip and momentum diversify each other — the one part of the proposal the data confirms.** Correlation of daily excess returns: sector-dip book vs MTUM +0.05, vs SPMO +0.05, curated-dip book vs MTUM +0.14; over the century, dip-on-industries vs the top momentum decile +0.08. Mean reversion and trend are different bets.
5. **The combined book, hindsight-free** (sector-ETF dip book + MTUM/SPMO 50/50 held, insurance on both, SPY the residual inside the dip book):

| dip / ETF weight | excess vs SPY | IS 2017–21 | OOS 2022–26 | max DD (SPY −33.8%) | Sharpe (SPY 0.89) |
|---|---|---|---|---|---|
| 100 / 0 (today's design on sectors) | +0.4 | +0.6 | +0.3 | −25.3% | 1.11 |
| 70 / 30 | +1.3 | +1.2 | +1.5 | −27.4% | 1.08 |
| 50 / 50 | +1.9 | +1.5 | +2.2 | −28.9% | 1.04 |
| 30 / 70 | +2.3 | +1.8 | +2.9 | −30.3% | 0.99 |
| 0 / 100 | +2.9 | +2.0 | +3.8 | −32.4% | 0.91 |

Positive in both halves at every weight. 50 / 50 year by year: 7 of 10 years ahead, worst −11.9 (2023, a momentum-crash year); rolling 3-year windows ahead of SPY in 23 of 27 (worst −2.1, median +1.1) against 16 of 27 for the dip book alone. With the curated list instead of the sectors: +3.6 to +4.1 at every weight but IS −0.8 to −8.4 / OOS +8 to +18 — the curated list's whole advantage is 2022 → 2026. **Century** (French): dip-on-49-industries 50 / top-momentum-decile 50 = +2.9 pp/yr over 1927 → 2026, **ahead of the market in all four quarter-centuries** (+3.2 / +4.4 / +2.4 / +1.5) with max drawdown −74% vs −84%; 70 / 30 = +1.8, also all four eras. The decile is frictionless, so subtract about a point for an investable version.

**Reading.** The operator's intuition is right in structure and wrong in one part: a second sleeve that bets on *trend* does hedge a book that bets on *dips*, and the sum is the first hindsight-free design in this project that beats SPY in-sample, out-of-sample, in most years, in most rolling windows and across a century, with less drawdown than SPY. The part that does not work is a second dip rule on a broad universe. The momentum sleeve should be an ETF, not self-picked names: it has no parameters to overfit and costs a line of config to run.

**Proposal (not decided, nothing changed live):** add a momentum-ETF sleeve — MTUM and SPMO half each — at 30–50% of equity, held through, scaled by the two-signal insurance like everything else; the dip rule stays on the curated list with slot sizes reduced so overlay + sleeve + reserve ≤ 100%; SPY stays the residual. Honest expectation from the hindsight-free floor: +1.3 to +1.9 pp/yr over SPY, a quarter less drawdown, and a −10% relative year when momentum crashes; whatever the curated list adds on top is a bonus that cannot be measured. Implementation is small (a second core leg in `core_allocation` / `mechanical.core_target_pct`, two tickers in the fetch, a config field, tests) and would start a new clean window under its own go/stop rule.

### Decision 067 addendum — the master search (operator: "take everything discussed, test every possibility, let the victor emerge", 2026-10-27)
`scripts/param_search/master.py`: every design discussed in one grid, scored one way. Decade (investable, 2017 → 2026): dip book (live rule; sectors = hindsight-free, curated list = flagged) × momentum vehicle (MTUM / SPMO / both) × dip weight 0–100% in 10-point steps × two-signal insurance (off / ×0.5 / to cash) × shock trigger (off + four settings) × volatility target (off / 15% / 20%) × own-momentum switch = 4,140 books. Century (French, 1927 → 2026): the same minus vehicle and universe = 765 books. De-risked capital earns 0% (no T-bill), which biases *against* every de-risking rule. Read in order: marginal effects, constrained leaderboards, walk-forward of the selection, finalists.

**Marginal effects (median over every other setting).** Decade, hindsight-free: vehicle SPMO +0.4 vs MTUM −1.6 vs both −0.6; insurance off +0.9 vs ×0.5 −0.4 vs to-cash −3.4; shock trigger ≈ neutral on return, raises the share of books with a Sharpe above SPY from 77% to 80–88%; volatility target −0.7 to −1.2; own-momentum switch −0.4; more dip weight = less return and a higher Sharpe (share of books above SPY's Sharpe 43% at 0% dip → 100% at 80%+). Century: more momentum = more return (+4.4 at 0% dip → +0.1 at 100%), Sharpe flat for dip weights 0–40% then falling; insurance ×0.5 raises Sharpe at no return cost; shock trigger neutral on return, +Sharpe; volatility target −0.4 to −0.7; own-momentum neutral.

**Leaderboards.** Decade by return (positive in both halves, drawdown no worse than SPY): SPMO-majority books with insurance off, +4.3 to +5.2; by Sharpe: dip 50–80% / SPMO with the shock trigger, Sharpe 1.22–1.24 at a −20% drawdown and +1.9 to +2.3. Century by return (positive in all four quarter-centuries, drawdown no worse than the market): momentum-only with insurance ×0.5 and the shock trigger, +5.3, Sharpe 0.86; by Sharpe: dip 20–40% with insurance ×0.5 and the shock trigger at ×0.25, Sharpe 0.90–0.91, +3.5 to +4.3. Only 16% of hindsight-free decade books are positive in both halves; 49% of century books are positive in all four eras with a drawdown no worse than the market's. Walk-forward of the selection: decade pick-by-IS → OOS +2.5 (median design −0.2), pick-by-OOS → IS +1.1 (median −1.4); century pick-by-1927–74 → +0.9 (median +0.8), pick-by-1975–2026 → +5.2 (median +4.2). The chosen cell is never special; the *family* is.

**Finalists** (dip sleeve on sectors; insurance ×0.5 and the shock trigger combined as min(), not multiplied):

| design | decade: excess / IS / OOS, DD, Sharpe, worst yr | century: excess, eras +, DD, Sharpe; 1973 / 2008 vs market |
|---|---|---|
| live today (dip only, insurance) | +0.0 / +0.8 / −0.7, −25%, 1.08, −13 | +0.7, 2 of 4, −65%, 0.69; +20 / +18 |
| dip 50 / SPMO 50, insurance, shock | +1.2 / +0.4 / +2.0, −20%, 1.12, −12 | +3.2, 4 of 4, −59%, 0.85; +21 / +21 |
| **dip 40 / SPMO 60, insurance, shock** | **+1.4 / +0.3 / +2.5, −20%, 1.10, −11** | **+3.6, 4 of 4, −59%, 0.86; +21 / +21** |
| dip 40 / SPMO 60, no insurance, shock | +3.0 / +1.6 / +4.5, −20%, 1.14, −8 | +3.4, 4 of 4, −64%, 0.79; +5 / +9 |
| dip 50 / SPMO 50, insurance, no shock | +1.1 / +0.5 / +1.7, −24%, 1.09, −12 | +3.0, 4 of 4, −65%, 0.81; +21 / +21 |
| SPMO only, insurance, shock | +1.8 / −0.3 / +4.1, −25%, 1.01, −12 | +5.3, 4 of 4, −60%, 0.86; +22 / +23 |
| SPMO only, nothing | +5.2 / +2.1 / +8.4, −31%, 1.00, −7 | +5.1, 4 of 4, −84%, 0.71; +6 / +2 |
| SPY / market | −34%, 0.89 | −84%, 0.63 |

(With the curated list in the dip sleeve: +2.5 to +2.6 on the decade but IS −3.6 to −4.5 and a −20 to −22 worst year — the list's edge is 2022 → 2026 only, as before.) Where the insurance applies (dip 40 / SPMO 60, shock on): on the whole book, decade +0.5 … +1.4 / century DD −49%, 1973 +21; on the momentum sleeve only, decade +1.5 / century DD −54%, 1973 +15; off, decade +3.0 / century DD −64%, 1973 +5.

**What emerged.** Not a cell but a family: a momentum-majority book (dip 30–50%, SPMO 50–70%), the shock trigger on, no volatility target, no own-momentum switch. The two eras agree on all of that. The one knob they disagree on is the two-signal insurance: it costs about 1.7 pp/yr in a bull decade without a long bear and earns 15–20 points in each of 1929, 1973 and 2008 while raising the century's Sharpe from 0.79 to 0.86 — a long-bear instrument, priced like insurance. Also learned: SPMO beat MTUM by about a point a year this decade (index construction; the century cannot separate them, so holding both costs ~1 pp for diversification of that risk); the dip sleeve's job in the blend is Sharpe and drawdown, not return; and the curated list hurt 2017–21 in every combination.

**Recommended design (the operator's call, nothing live):** 40% dip book (the live rule on the live list; the sector floor is the number above), 60% SPMO (or 30 / 30 SPMO + MTUM), the shock trigger (SPY −7% over 10 sessions → exposure ×0.5 for 20), the two-signal insurance ×0.5 on the whole book as today, no volatility target, no own-momentum switch. Honest expectation, hindsight-free: +1.4 pp/yr over SPY in a decade like the last (+3.0 without the insurance), a worst drawdown near −20% against SPY's −34%, Sharpe 1.10 against 0.89; over a century +3.6 with all four quarter-centuries ahead, −59% against −84% in the worst case, +21 against the market in a 1973 or 2008, and the rebound year after any crash given back (−8 to −11 in 2019/2023-type years, −26 in a 2009).

### Decision 067 addendum — crash scenarios and regime switching (operator questions, 2026-10-27)
**"Show me what a crash would look like."** `scripts/param_search/crashes.py` runs every recorded bear from the market's peak for three years (market, momentum sleeve, dip book, 50/50), on the century data and on the investable ETFs; the page is at https://claude.ai/artifact/6NFRzmZESCaFnMcxUtvmoD (private). Two shapes: in the *slow grinds* the dip book is the only protection (2000: dip book +8% at the market's −49% trough and +43% two years after the peak; 2008: −41% vs −55%; 1973: −28% vs −48%; 2022 ETFs: −9% vs −25%) and momentum falls with the market every time; in the *fast crashes* everything falls together, the blend a few points less (1987: −29% vs −33%; 2020: −29% vs −34%; 2025: −18% vs −19%) and momentum rebounds hardest. The blend never fell further than the market in any crash. The price of the protection is the rebound year after a crash (2019: −5, 2023: −12 vs SPY, both strong up-years where the book still gained), not the crash itself.

**"Can a check tell which epoch we are in and shift the strategy?"** `regimes.py` applies seven rules to the 50/50 book, decade and century, each setting the day's exposure from the previous session's signals:

| rule | decade excess (no rule +3.5) / max DD (no rule −32.9%) | century excess (no rule +3.0) / max DD (no rule −82%) |
|---|---|---|
| R1 live two-signal ×0.5 | +2.9 / −32.9% | +2.6 / −83% |
| R2 three-state mix (bull 50/50, caution 65/35, bear dip-only) | +2.9 / −32.8% | +2.2 / −84% |
| R3 sleeve held only while its own 12-1 momentum > 0 | +3.0 / −32.9% | +2.7 / −85% |
| R4 volatility target 15% (rest cash) | +0.5 / **−16.9%** | +2.4 / −66%, but −39 vs market in the 2009 rebound |
| R5 shock trigger: SPY −7% in 10 sessions → ×0.5 for 20 sessions | +2.1 / **−20.6%**, Sharpe 1.10 vs 1.02 | **+3.0 / −64%**, Sharpe 0.78 vs 0.69 |
| R6 = R1 + R5 | +2.1 / −20.6% | +3.0 / −65% |

Every *slow* regime rule (trend, breadth, mix shift, own momentum) lands in the same place as the insurance already live: slightly less return, no less drawdown, in both eras — regimes are only knowable after the move that defines them, and momentum's crashes come in rebounds, not in bears. Two *fast* rules are different. The volatility target halves the drawdown but costs 3 pp/yr on the decade and misses rebounds badly. The **shock trigger** is the one rule that addresses a sudden crash: relative to the market from peak to trough, covid +13, 2022 +10, 2025 +1; 1929 +20, 2008 +9; cost: the rebound year (2009: −20 vs market). Robustness grid (`regimes.py --grid`, 81 cells over threshold −5/−7/−10% × lookback 5/10/20 × hold 10/20/40 × scale 0.5/0.25/0): century — 80 of 81 cells raise Sharpe, DD median −63% vs −82%, return cost median −0.4 pp; decade — the fast-and-short region (−7%, 5–10 sessions, hold 10–20, scale 0.5) costs 0.3–1.3 pp for DD −20.6% to −23.5% and Sharpe 1.08–1.11, while long holds (40) and scale 0 cost 3–6 pp. De-risked 4–11% of sessions. A plateau, not a cell; the centre (−7% / 10 / 20 / 0.5) is the tested R5.

**Proposal extended**: Decision 068, if the operator goes ahead, adds the shock trigger beside the momentum sleeve — the same `exposure_scale` mechanism the insurance uses, a second trigger (close-to-close SPY return over 10 sessions < −7% → ×0.5 for 20 sessions), evaluated at every run. Expected: the worst drawdown a third smaller than SPY's in a sudden crash at 0–1 pp/yr, paid back in the first rebound year.

### Decision 067 addendum — shorts, the current regime, a self-correcting universe (operator questions, 2026-10-27)
Three explorations asked for after the master search, run the Decision 062 way (hypotheses in each script's docstring before any result; IS / OOS; point-in-time membership; costs 0.05 % per side plus 1 %/yr borrow on short notional; judged against SPY and the equal-weight universe; through-2025 beside full). Scripts: `scripts/param_search/shorts.py`, `analogues.py`, `dynamic_universe.py`. **Outcome: all three tested, none adopted; the recommended design above stands unchanged.**

**1. Shorts — can the book stop being long-only?** (`shorts.py`)

| idea | century (French, 1927 →): excess / DD / Sharpe / worst year; 1932 momentum crash, 2009 rebound vs market | decade (ETF book, 2017 →): excess (IS / OOS) / DD / Sharpe |
|---|---|---|
| recommended book (reference) | +3.6 / −59 % / 0.86 / −22; −53, −26 | +1.3 (+0.3 / +2.4) / −20 % / 1.10 |
| + French WML long-short overlay 25 % | +4.9 / −58 % / 0.89 / −28; −85, −51 | +2.1 (−0.0 / +4.3) / −19 % / 1.06 |
| + WML 50 % | +6.1 / −65 % / 0.89 / −35; −112, −73 | +2.6 (−0.5 / +6.0) / −19 % / 0.97; through 2025 +1.8 vs +0.8, Sharpe 0.95 vs 1.08 |
| + WML 100 % | +8.2 / −77 % / 0.85 / −60; −153, −107 | +3.0 (−2.4 / +8.7) / −27 % / 0.78 |
| momentum sleeve as long Hi / short Lo decile, capital in the market | +6.0 / −63 % / 0.93 / −31; −113, −70 | n/a (the bottom decile is the hard-to-borrow end; frictionless here) |
| de-risked half short the market (−1×) through insurance + shock, instead of cash | +3.3 (3 of 4 eras, min −0.2) / **−48 %** / 0.93 / −32; 1929 **+75** vs +26, 2009 −49 vs −26 | **−1.5** (−2.0 / −1.1) / −25 % / 1.01; SH ETF actual −1.2; through 2025 −2.2 vs +0.8 |
| … through the insurance only | +3.2 (3 of 4) / −44 % / 0.86 / −31 | −1.8 (−1.8 / −1.8), rolling 3-year windows ahead 15 % |
| … through the shock trigger only | +3.2 / −63 % / 0.82 / −43 | +1.9 vs +3.0 for cash / −18.5 % vs −20.0 % / 1.14 both |

(a) The WML overlay adds return in proportion to its weight and nothing to the Sharpe ratio — it is leverage on the momentum bet the sleeve already carries, with the momentum crash doubled (1932–33 −85 to −153 vs the market) and the decade's first half turned negative. (b) Shorting the market while de-risked is the insurance's trade-off doubled: through the slow signal it earns +75 in a 1929 and halves the century's drawdown, at −3 pp/yr in a bull decade (rolling 3-year windows ahead of SPY 15–30 % of the time) and a lost quarter-century; through the fast trigger it costs ~1 pp/yr on the decade for 1.5 points of drawdown and nothing on the century. De-risked capital earning 0 is the right bias for this book. (c) **The anti-dip mirror** — the live rule on inverted prices, short a name that rallied ≥ 8 % from its 90-day low while below its 150-day SMA, as a self-financed overlay — loses on every universe once the same trades are priced as real shorts on the real path with 1 %/yr borrow: sectors **−5.0 %/yr** of equity (IS −7.9 / OOS −1.9), the point-in-time S&P 500 **−15.1 %/yr** (−15.2 / −14.9; 246 trades, 41 % winners, median trade −11 % = stopped), the 49 industries **−3.9 %/yr** over a century (it makes +260 in 1929–32, +96 in 1973, +88 in 2008 and gives it all back in 1932–33 and 2009, bleeding in between). Restricting entries to a market below its 200-day SMA halves the bleed, no more. A rally inside a downtrend continues more often than it fades. Method note: feeding 1/P to the long engine flatters a short by 1.3 (sectors) to 19 (S&P) pp/yr — a long position in 1/P has bounded losses and unbounded gains, a short the reverse — so the 1/P curve read +3.9 %/yr on the S&P where the real short loses 15. **Nothing here justifies building short support into the live system.**

**2. Which regime are we in, and what followed days like it?** (`analogues.py`) State on the SPY bars to 2026-10-12 (and the Oct 27 check): above the 200-day SMA, 12-month return +17 %, 20-day realised volatility 9.5 %, 0.1 % below the 52-week high, 11-sector breadth 45 % (54.5 % on Oct 27), SPMO leading SPY by +6.5 % over 12 months. Over the past 12 months breadth went 91 % → 36–45 % since September while SPY sat at its highs, volatility fell from 18 % (March) to 9.5 %, and the one dip (March: below the SMA, 6 % off the high, breadth 55 %) lasted a month — a narrowing market at the top. Analogues = every session with the same six coarse buckets; episodes = runs separated by more than 63 sessions; the forward 1- and 2-year market return and each design's excess over the same windows (the century's 49-industry breadth is a different population — 78 % today — so the century was also matched on the SPY-derived state):

| analogue set (century, 1927 →) | episodes | market 1y: p10 / median / share positive | market 2y | recommended book 1y excess: median / share positive (first half · second half) |
|---|---|---|---|---|
| unconditional | — | −14 / +13 / 74 % | +24 / 82 % | +2.7 / 64 % (+3.6 / 69 % · +1.7 / 58 %) |
| today with the 49-industry breadth (> 70 %), all six | 62 | −8 / +13.5 / 83 % | +21 / 89 % | +1.1 / 55 % (+3.6 / 72 % · **−2.5 / 36 %**) |
| today with breadth 50–70 % (Oct 27), all six | 26 | **−19 / +3.7 / 62 %** | +18 / 70 % | +3.8 / 70 % (+5.8 / 89 % · −3.0 / 43 %) |
| today with breadth < 50 % (Oct 12), all six | 3 (1972-10, 1986-12, 1999-11) | −12 / −7 / 0 % | −33 / 5 % | +7.1 / 100 % — three episodes, an anecdote |
| above SMA, 12-month > 15 %, breadth < 50 % | 33 | **−12 / +5.7 / 58 %** | +11 / 58 % | +3.5 / 80 % (+2.4 / 61 % · +3.7 / 84 %) |

Decade cells hold 1–3 episodes (2018-06, 2020-08, 2025-08) and say nothing. Marginals over the century: the only dimensions that move the forward distribution are breadth and the distance from the high (breadth < 50 %: 1-year p10 −26 vs −9 for > 70 %; more than 10 % off the high: p10 −27) — where the cycle is, not how calm it looks; low volatility, an uptrend and momentum leadership each leave the forward distribution where the unconditional one is. The book's relative return is 55–71 % positive in every state; it is weakest (55–59 %) in exactly the calm, broad, momentum-led bull, and nowhere does the sign flip. **Reading**: a strong, calm market at its highs with narrowing breadth has, over a century, been followed by a below-average year (median +4 to +6 vs +13, a tenth-percentile of −12 to −19) far more often than by a crash; the designs' relative performance in such states is positive on the century and not stable across halves. As pre-registered, no switching rule follows — the state is the kind the design exists for (the dip book for a grind, the sleeve for a continuation, the shock trigger for a fall). VIX from FRED was not added: the volatility bucket carries nothing the realised series doesn't.

**3. A dip universe that is not hand-picked** (`dynamic_universe.py`; live rule, insurance ×0.5; excess vs SPY (IS / OOS), DD, Sharpe):

| universe / rule | result | reading |
|---|---|---|
| 11 sectors, 3 × 25 % (the floor) | +0.4 (+0.6 / +0.3), −25 %, 1.11 | positive in both halves — still the only one |
| 17 equity ETFs (sectors + XBI SMH ITB KRE XOP IBB) | +1.5 (+3.9 / −0.8), −26 %, 1.00; through 2025 +0.7; 5 slots −1.2 | industry ETFs add 2017–21 and take it back |
| 22 multi-asset (sectors + GLD TLT IEF EEM EFA IWM VNQ DBC LQD HYG SLV) | 3 slots +0.7 (−3.4 / +4.8), −24.7 %, 1.08; 5 slots +0.9 (−1.9 / +3.7), **−23.4 %, 1.16**; through 2025 +0.4 | a point or two less drawdown, a higher Sharpe at 5 slots, and all of the excess is 2022 → (bonds and gold recovering) |
| 28 all | −0.2 / −0.8 (3 / 5 slots) | dilution |
| 11 multi-asset only | −0.3 (−5.1 / +4.6), −22.7 % | the equity sectors are the return |
| stop cooldown 60 / 120 / 250 sessions on the S&P 500 (point-in-time), 3 × 25 % | −0.2 → −4.1 → −4.7 → **−11.2**; 10 × 7.5 %: −4.3 → −4.2 → −4.0 → −5.8 | excluding a stopped name *hurts*: its re-entry (back above the SMA with a fresh dip) is a better-than-average trade |
| … on the sectors / the 49 industries | +0.4 → +1.3 (5 stops in ten years); −0.0 → +0.2, DD −66 → −63 % | nothing happens where stops are rare |
| eligibility = own 12-month return > 0, S&P 500 | 3 slots **−7.8** (−6.0 / −9.5), 10 slots −9.7; sectors −1.1; industries +0.5 (+2.2 / −1.2) | Decision 066 again: a winner's dip is its break |
| eligibility = own 12-month return < 0 (the mirror) | S&P 3 slots −0.8 (−7.0 / +5.9), 10 slots −6.2 (+1.9 / −13.7); sectors −2.5 (17 trades); industries −0.9 | flips sign between halves and slot counts — noise |
| cooldown 120 + either eligibility, S&P | −10.7 / −4.3 / −7.9 / −9.9 | no interaction to rescue |

Every ETF-universe dip variant beats the equal-weight hold of its own universe by 3–7 pp — that is the SPY residual, not the rule (the equal-weight ETF baskets lag SPY by 2–7 pp/yr). Side note for the record: the S&P 500 with the membership mask from 2017 at 3 × 25 % reads −0.2 vs SPY (the −10.0 of the Decision 065 evidence was the 2016 list from January 2016 without the mask), with a Sharpe of 0.67 against 0.89 and a −34 % drawdown — still not a universe for this rule. **No self-correcting universe rule was found**: wider ETF lists do not beat the sector floor in both halves, a long stop exclusion makes the broad universe worse, and own-momentum eligibility is either the known negative or noise.

**Decision**: nothing changes. The open item stays the operator's go / no-go on the recommended design (40 % dip book / 60 % SPMO, shock trigger, insurance ×0.5). Three ideas are closed with evidence: a long-short or short-the-market leg (not worth short support in the executor), regime recognition as a switching input (descriptive only; the state today is "late, narrow, calm"), and a rule-built dip universe (the sector ETFs remain the hindsight-free floor, the curated list the live choice).

### Decision 067 addendum — ten market types and a rotating sleeve (operator follow-up, 2026-10-27)
Operator, after the plain-language reading of the three explorations: (1) "no pattern to separate maybe ten types of market and tweak parameters or even the strategy per type? We have time, try a massive cross product"; (2) "the hand-picked names look like lucky picks — surely the hedging bit can be rotated strategically, maybe with a different strategy than dips". Scripts `scripts/param_search/states.py` (`--momcrash`), `rotation.py`; hypotheses in the docstrings before any result. **Outcome: nothing survives its placebo or its walk-forward; the recommended design already contains the rotation the operator is asking for.**

**1. State-conditional strategy — the cross product.** Eight state schemes (the live two-signal, trend × breadth, drawdown × volatility, k-means on six standardised features at K = 4 / 6 / 8 / 10 / 12 with centroids fitted on the training half only) × two action menus (M1 the book mix: dip weight 0–100 % × exposure 0 / ½ / 1 + "hold the index", 19 actions; M2 the dip rule's own parameters: 108 pre-run books × exposure ½ / 1, 216 actions, as a mixture of books) × selection per state by training-half excess × test on the other half, both directions × 20 block-shuffled placebo labellings per cell, decade and century. Gain = conditional strategy minus the best single action chosen the same way.

| scheme | decade, book mix: test gain 1st→2nd / 2nd→1st | decade, dip parameters | century, book mix | century, dip parameters | in-sample gain (actual / placebo) |
|---|---|---|---|---|---|
| live two-signal (2 states) | −4.6 / 0.0 | −3.0 / −3.7 | −3.7 / 0.0 | −2.6 / +0.3 | +0.2…+2.8 / +0.1…+1.3 |
| trend × breadth (4) | −6.2 / +0.3 | −3.0 / −3.9 | −3.7 / −0.5 | −2.7 / −1.1 | +0.2…+3.9 / +0.2…+1.9 |
| drawdown × volatility (9) | −0.3 / **+5.1** | −0.3 / +0.3 | −1.2 / 0.0 | −1.1 / +0.1 | +2.1…+5.6 / +1.2…+5.0 |
| k-means K = 4 | −5.4 / −1.6 | −1.2 / −1.8 | 0.0 / −0.2 | −1.5 / −1.3 | 0…+3.9 / +0.3…+4.3 |
| K = 6 | −2.8 / −2.5 | −2.4 / −3.4 | −1.1 / +1.0 | −0.7 / −1.0 | +1.4…+4.8 / +0.5…+4.5 |
| K = 8 | −2.8 / −0.7 | −0.1 / −3.1 | −0.1 / +1.3 | −1.2 / +0.7 | +2.9…+6.9 / +1.0…+7.3 |
| K = 10 | −4.0 / −1.2 | −1.6 / −2.0 | +0.6 / +0.9 | −1.0 / +1.3 | +2.6…+7.3 / +1.4…+6.5 |
| K = 12 | −5.6 / −4.4 | −1.3 / −1.9 | +0.2 / +1.3 | −1.8 / +0.1 | +3.7…+9.5 / +1.9…+8.3 |

In-sample, every scheme improves on the best single book and the improvement grows with the number of states — and a random labelling with the same block structure gains the same amount (the two right-hand ranges overlap at every K). Out of sample the 64 cells have a median gain of −1.2 pp/yr and a range of −6.2 to +5.1; the +5.1 (drawdown × volatility, decade, trained on 2022 → and tested on 2017–21) is −0.3 in the other direction, and the century's K = 8–12 gains of +0.9 to +1.3 in one direction are 0 to +0.6 in the other, inside the placebo spread (−3.5 … +1.4). The best single action in every training half was "momentum 100 %, exposure 1"; a state scheme's only job was to find when not to hold it, and nothing it found held up. The ten century types themselves are readable (a calm broad bull in three flavours, 55 % of days; a grinding bear, 12 %; the crash itself, 2 %; the rebound after a crash, 1 %), and exactly one of them separates the actions by a lot: the rebound after a crash (volatility 44 %, 12-month return +29 %, momentum leadership −24 %: 1932-08, 1933-06, 1938-07, 1939-09, 2009-07), where the dip book made +47 and the momentum sleeve −174 against the market in the test half. That is the momentum crash of Daniel–Moskowitz, so five published ex-ante guards were tested directly (`--momcrash`: market 24-month return < 0; that and volatility > 20 %; 12-month return < 0; up > 20 % from the 252-day low while > 10 % below the high; momentum leadership < −10 %), each moving the sleeve into the index while on: century +3.3 to +3.8 vs +3.6 for the book, Sharpe 0.86–0.87 vs 0.86, the 1932 rebound −27 to −34 instead of −53 and 2009 −17 to −23 instead of −26; decade +0.8 to +1.5 vs +1.4. The effect is real and worth about nothing to a long-only momentum ETF beside a dip book: the dip book already carries the rebound, and the guard also sits out the V-shaped rebounds where momentum led (2020: −17 either way).

**2. Rotation sleeves — "rotate the hedging bit by a rule".** Published, hindsight-free rotation families as the 60 % sleeve beside the 40 % sector dip book (insurance ×0.5, shock trigger), against the SPMO sleeve of the recommended design:

| sleeve (decade 2017 →) | alone vs SPY (IS / OOS), DD, Sharpe | in the book: excess (IS / OOS), DD, Sharpe; corr. with the dip book's excess |
|---|---|---|
| **SPMO held (recommended)** | **+5.2 (+2.1 / +8.4), −31 %, 1.00** | **+1.4 (+0.3 / +2.5), −20 %, 1.10; 0.06** |
| 11 sectors, top 3 by 12-month return skipping the last month, monthly | +0.1 (−2.0 / +2.3), −31 %, 0.89 | −1.2 (−1.5 / −0.9), −21 %, 1.03; 0.30 |
| … top 1 (one sector at a time) | +7.1 (+3.4 / +11.0), −31 %, 0.97, worst year −18 | +1.8 (+1.1 / +2.4), −21 %, 1.06; 0.24 — the one positive cell of 36, concentrated, its neighbour top 2 is +1.5 alone |
| … 36 cells (top 1–3 × 3 / 6 / 12 months × skip 0 / 1 × absolute filter) | 5 of 36 positive, 1 positive in both halves; marginals: 3-month −4.4, 6-month −2.9, 12-month +0.4; absolute filter −1.4 worse (cash at 0 %) | — |
| multi-asset top 3 by 12 / 6 months (SPY EFA EEM IWM TLT IEF GLD DBC VNQ LQD HYG) | −7.7 / −5.1, DD −26 / −19 % | −4.9 / −3.4, DD −21 / −18 % |
| Faber's GTAA 5 (10-month SMA, 20 % each) | −10.4, DD −18 % | −6.1, DD −15 % |
| **century**: 49 industries top 10 by 12-1 monthly (Moskowitz–Grinblatt) | +5.1 (+6.2 / +4.1), 4 of 4 eras, DD −76 % vs −84 %, Sharpe 0.85; top 5 +5.9; with the absolute filter +4.7, DD −62 % | dip 40 / top 10: +3.5 (+5.4 / +1.5), DD −56 %, **Sharpe 0.95**; top 5 +3.9, DD −51 %; vs the frictionless decile +3.6, −59 %, 0.86 |

Reading: rotation by trailing return *is* momentum. Over a century, rotating into the top fifth of 49 industries is as good as the frictionless top decile and investable (Sharpe 0.95 inside the book, the best century number in this project). On the decade the same rule on 11 sector ETFs is ≈ 0 (a single concentrated cell positive), correlated 0.3 with the sector dip book because it trades the same eleven instruments, while SPMO — momentum across ~100 S&P 500 names, rebalanced by the index, no parameters to fit — made +5.2 in the same years at 0.06 correlation. **The recommended design already rotates the hedging bit by a rule: the SPMO sleeve is that rotation**, done inside the index rather than across sector ETFs. Multi-asset rotation and GTAA buy their smaller drawdowns with 5–10 pp/yr — the price of bonds and commodities in 2017–26 — and are not a hedge for this book. If SPMO were ever unavailable, an industry rotation (top fifth by 12-1, monthly) is the century-backed stand-in.

**3. Rotation timing — how often, and whether a marker beats the calendar** (operator follow-up; `rotation.py --timing`). SPMO's schedule is the index's (semi-annual, March / September) and not a knob this book holds; for a rotation run in-house the frequency and the trigger were swept on the century industries (top 10 by 12-1) and the decade sectors (top 3), net of 0.05 % per side:

| timing | century: sleeve excess (IS / OOS), DD, Sharpe, turnover; book Sharpe | decade sectors: sleeve excess; book excess (SPMO: +5.2; book +1.4, Sharpe 1.10) |
|---|---|---|
| daily re-rank | +4.1 (+5.1 / +3.1), −78 %, 0.78, 1,402 %/yr; 0.90 | −0.1; −1.4 |
| **monthly** (reference) | **+5.2 (+6.2 / +4.1), −76 %, 0.85, 253 %/yr; 0.95** | +0.2; −1.2 |
| quarterly | +4.4, −77 %, 0.81, 156 %/yr; 0.93 | −1.0; −1.9 |
| semi-annual (Mar/Sep · Jun/Dec) | +4.4 · +3.9, 116 %/yr; 0.94 · 0.92 | +0.6 · +0.5; −0.7 · −0.8 |
| annual (Jan · Jul) | +2.3 · +2.2, 89 %/yr, one era lost; 0.88 · 0.86 | −4.4 · −1.4; −4.1 · −2.0 |
| **band: hold while still in the top 1.5 N, monthly check** | **+5.2 (+6.6 / +3.8), −75 %, 0.85, 146 %/yr; 0.95** | −2.0; −2.3 |
| band 2 N · 3 N | +4.3 · +3.4, 114 · 77 %/yr | −2.0 · −1.9 |
| trend-break: drop a holding below its 10-month SMA, refill from the top N | +3.6, **−65 %**, 0.94, 157 %/yr; book +2.5, **DD −46 %, Sharpe 0.97** | −6.4; −4.3 |
| monthly + re-rank the day after a market shock (−7 % in 10 sessions) | +5.1 (unchanged), 259 %/yr | +0.2 (unchanged) |

Readings. (a) Momentum in industries decays within months: monthly ≈ the rank tolerance band > quarterly ≈ semi-annual (−0.8) > annual (−3, and the January anchor loses a quarter-century); daily re-ranking only adds turnover (−1.1 after costs). (b) The one timing refinement that is free is the tolerance band: hold a name while it is still inside the top 15 of 49, refill from the top 10 — the same +5.2 at 42 % less trading. (c) A trend-break marker is the absolute-momentum filter again: −1.6 pp of return for 11 points of drawdown and the best century Sharpe in the project (0.97 in the book) — a drawdown instrument, not a return one. (d) Re-ranking after a shock changes nothing: the ranking barely moves in ten sessions. (e) On the decade the eleven sector ETFs are ≈ 0 at every frequency and worse with every marker (−2 to −6), while SPMO, rebalanced twice a year by the index across ~100 names, made +5.2 — the vehicle matters, the calendar does not. **Nothing changes**: SPMO's timing is not ours to set and the in-house alternative does not beat it on investable data; if an industry rotation were ever built, monthly with a 1.5 N band is the setting, and the trend-break marker the drawdown option.

**Decision**: nothing changes. "Ten market types" is answered by the placebo: the in-sample gain is what any labelling buys, and out of sample it is gone. "Rotate the hedging bit" is answered by Decision 068's momentum sleeve. The one durable state fact from the cross product — momentum collapses in the rebound after a crash, the dip book carries it — is already why the design holds both.

## Decision 066: Universe research — momentum is the only survivor; nothing changes live; a momentum sleeve is the operator's call
**Date**: 2026-10-27
**Question** (operator): is the return in the names rather than the rule, and can a statistical pattern find the names? Done the Decision 062 way: hypotheses written into `scripts/param_search/screens.py` before any result, point-in-time data (742 S&P 500 members 2016 → 2026 with the 94 delisted names, Kenneth French's daily portfolios 1927 →), in-sample 2017–21 / out-of-sample 2022 → 2026, every result judged against SPY *and* against the equal-weight universe (so a screen is not credited with the equal-weight effect, which was −3.9 pp/yr this decade), 0.05% per side on turnover, plateau checks over list size, window and rebalance month.

**Name-level screens, top 15, yearly, 2017 → 2026 (excess CAGR vs SPY; IS / OOS):** S1 momentum 12-1 **+8.7 (+5.0 / +12.4)**; S3 near 52-week high +2.0 (+0.3 / +3.7); S4 smooth momentum +1.6 (−2.7 / +6.0); S7 quiet winners 0.0; S2 low volatility −7.7; S5 momentum + low vol −8.4; S6 long-term reversal −1.0 (−16.3 / +8.5); S8 anti-momentum −7.4 with a −57% drawdown (the mirror loses, so the test has teeth). Top 30 halves every effect; quarterly rebalancing hurts all of them (turnover 2–4× a year).

**Momentum under pressure.** Grid over window (6-1, 12-1, 12-2) × N (10–50) × rebalance month (Jan / Apr / Jul / Oct): median excess +4 to +6 pp/yr at N = 10–15, falling to 0 at N = 50; **but the 2017–21 half is flat (−2 to +2) and the whole premium sits in 2022 → 2026**, dispersion across rebalance months is wide (12-1 N=15: −1.5 to +8.7), and the decade's best year is 2026 to date (+45 vs SPY for 12-1). Through 2025-12-31 the eight window × anchor cells read −1.1 to +8.0, median about +2. Year by year (12-1 N=15): 7 of 10 years ahead, one at −23 (2023). Regime guards do not tame it: a trend guard (sleeve only while SPY is above its 200-day SMA) *costs* 2.5 pp/yr and leaves the drawdown, the live two-signal insurance costs 0.7; over the century the trend-guarded top decile earns 1.3 pp/yr less than unguarded and draws down no less. **Century (French 12-2 deciles, value-weighted):** top decile beat the market by +5.1 pp/yr 1927 → 2026 (+1.9 / +8.9 / +7.5 / +2.7 by quarter-century), the bottom decile lost 8.6 pp/yr to it — the premium is real and old, and its drawdowns are its own.

**The dip rule and momentum are antagonistic.** The live dip rule restricted to the momentum picks: −14.1 pp/yr with 3 slots, −2.3 with 10, while simply holding the same picks made +8.7; on near-high picks −1.0 vs +2.0; on the century deciles the dip rule on the top three deciles is +0.05 vs market. Buying a momentum name's dip is buying the moment its momentum broke, and capping the win at +20% / 60 days throws away the trend. Momentum is harvested by holding.

**Trade-level features** (637 dip trades on the whole membership, 10 slots, by entry-time quintile, IS and OOS): momentum, volatility, Sharpe, dip depth, positive-day fraction and relative strength all flip sign between halves; only the market regime holds (+1.9% mean trade with SPY above its 200-day SMA, +0.05% below, 81 trades), and the design already pauses entries in risk-off. No entry filter to add.

**The operator's own list** (15 names set 2026-03-30, as percentiles of the S&P 500 cross-section that day): momentum 61st, volatility **79th**, Sharpe 65th, distance from the 52-week high 40th, positive-day fraction 75th. High-volatility, moderately high-momentum names bought below their highs. Held equal-weight since that day they made +32.1% vs SPY +23.7% at 15% vs 13% volatility — in a straight-up market, a higher-beta basket with some momentum is exactly what should have won, and it did. Not a reproducible rule; not evidence of selection skill either way on seven months.

**Decision.** Nothing changes live. The dip overlay stays what Decision 062 measured it to be (≈ market with less drawdown on hindsight-free universes). The one candidate the research produced is a **momentum sleeve**: 15 S&P 500 names by 6-1 or 12-1 month return, held equal-weight, rebalanced yearly, beside the SPY core, *without* the dip rule on those names. Honest expectation from the decade and the century: +1 to +1.5 pp/yr at a 30% sleeve with SPY-like drawdown, +3 to +5 at 100% with worse drawdown and a −20% relative year every few years; flat for stretches of five years; ~90% annual turnover. It is the operator's call whether that profile is wanted. If yes, the next step is the Decision 062 stage-3 discipline on the *selection rule* (train the window / N / anchor on one era, test on the next; a second universe — e.g. the S&P 400 — would be needed for a consensus check) before a paper sleeve is built. Scripts: `screens.py` (`--grid`, `--overlay`, `--profile`, `--trades`, `--refine`, `--s6`), `century.py` (`--regime`), `datasets.py` (`french_levels`), `fastbt.py` (`eligible` mask). All data archived under `/home/TitanTrade/archive/param_search/` on titanserver (230 MB).

## Decision 065: Reporting fixes from the October 20 check — honest benchmark on short windows, risk-off wording, watch-list reasons
**Date**: 2026-10-20
**Decision**: three small changes to what the system *says*, none to what it trades, after the operator asked for anything seen in the check to be fixed:
1. **Benchmark verdict and ratios are withheld under 20 trading days** (`benchmark.MIN_VERDICT_DAYS`). The 4-day window since the conversion printed "Adding value — positive alpha (+80.9%/yr)" on the CLI and would have put "β 1.57 | α +80.9%/yr" on the daily summary; on four daily returns those numbers are noise. `classify` now returns "Too few trading days (N of 20) for a verdict…" and `format_summary_line` shows the returns only ("4d ret −1.1% vs SPY −1.5% (too few days for ratios)").
2. **The daily benchmark refresh anchors at the strategy start** (`scheduler._run_daily_summary` passes `since = strategy.json → started_at`; 90-day fallback when no strategy start exists). The 90-day trailing window straddled the LLM pipeline and the mechanical strategy for the next three months, so the summary line and `/api/benchmark` would have judged a mix; the clean window of Decision 062 is the strategy's own history, which is also what the go/stop rule (Phase 2.0) is judged on.
3. **Wording**: the plan log line, the CLI and the Discord plan field say "risk-off no" / "risk-off YES (exposure x0.5)" instead of "insurance on" / "RISK-OFF" — "insurance on" read as if the de-risking were active. The watch-list reason for a signal with no free slot now says "no free slot — 3 of 3 slots held or pending" when the slots are occupied by positions, and "deeper dips took the free slot(s)" only when a free slot was actually taken by a deeper dip this run (CRWD at 18.5% was told the deeper dips took the slots while it was the deepest on the list).

**Tests**: 236 (short-window guard, summary-job anchoring and fallback; two existing classify tests pass a 30-day `n_days`). **Docs**: CLAUDE.md, features, data_schemas, deployment, backend architecture.

**Deployed**: 2026-10-20 09:23 UTC, commit `66b7750` — both images rebuilt and import-verified, API restarted, health ok, 7 jobs, 0 warnings. Verified on the server: a `signals` run writes the watch reason "no free slot — 3 of 3 slots held or pending" for CRWD / ANET / FCX; `benchmark --since 2026-10-13` reads "Too few trading days (4 of 20) for a verdict". The 20:30 UTC daily summary the same day is the first with the strategy-anchored benchmark line.

### Evidence — do outliers carry the strategy, and should it let winners run? (operator question, 2026-10-27)
Asked after the DASH stop-out: "the top 10% of trades make 90% of the profit — can and should we work around that?" Test: the Decision 062 engine (`scripts/param_search/fastbt.py`, now with an optional trailing stop `trail_pct`, armed once the position is above entry; default off, so `validate.py` equivalence is unchanged) with the live parameters and insurance on, varying only the exit side — target 20 / 30 / 40% / none, holding limit 60 / 120 / 250 / none, trailing 10 / 15 / 20% — on the Alpaca decade (2016-01 → 2026-10): **A** the 15 live names (chosen in 2026, i.e. with hindsight) and **D** the 11 sector ETFs (hindsight-free). Full period, in-sample / out-of-sample halves at 2022, and the profit concentration of the trade list (share of gross gains from the best decile of trades; net return without that decile). The 1999 → datasets could not be re-run: the git-ignored Yahoo files are no longer on the workstation and Yahoo rate-limits both the workstation and titanserver today (Stooq sits behind a proof-of-work browser check and was left alone). Their Decision 062 result for the same knobs stands: target 20 > 15 > 10% and holding 40–90 d flat on names *and* sectors.

| Exit design (live entry, insurance on) | A names: excess / IS / OOS, max DD, top-decile share | D sectors: excess / IS / OOS, max DD, top-decile share |
|---|---|---|
| **live: target 20%, 60 d** | +4.1 / −6.1 / +17.8, −37.9%, 28% | **+0.4 / +0.5 / +0.3, −25.3%, 28%** |
| target 40%, 60 d | +7.2 / −0.2 / +16.8, −32.8%, 37% | −0.6 / −0.3 / −0.9, −25.3%, 33% |
| no target, 60 d | +9.5 / +5.9 / +14.0, −41.3%, 38% | −0.6 / −0.3 / −0.9, −25.3%, 33% |
| target 20%, 120 d | +9.9 / +7.5 / +12.8, −32.3%, 23% | −0.7 / −0.4 / −1.2, −25.3%, 23% |
| no target, 250 d | +9.6 / +9.2 / +10.1, −30.5%, 45% | −3.4 / −3.7 / −2.9, −28.2%, 30% |
| trailing 10%, no target, no clock | +8.5 / +9.2 / +7.7, −25.2%, 51% | −3.7 / −0.7 / −7.1, −25.5%, 60% |
| trailing 15%, no target, no clock | +7.6 / +5.9 / +9.8, −26.1%, 54% | −4.2 / −2.4 / −6.2, −24.2%, 41% |
| trailing 15%, no target, 120 d | +9.4 / +6.2 / +13.3, −30.6%, 45% | −3.0 / −1.2 / −5.0, −25.3%, 32% |
| stop only (no target, no clock) | +0.9, 0.8 trades/yr | −2.1, 0.2 trades/yr |

(SPY CAGR 15.2%, max DD −33.8%; excess in pp/yr of CAGR.) **Readings.** (1) The 10/90 phenomenon is *not* present in the live design, by construction: the best decile of trades carries 28% of gross gains on both universes, the median trade is +4–5%, the best +22 / +34%, and the strategy stays profitable without its best decile (net +2.0 on both). Capping wins at +20% / 60 d turns a fat-tailed distribution into many moderate wins and bounded losses; the asymmetry that remains is on the *loss* side (a −12% stop is three times the median win), which is why a single stop-out dominates a short window. (2) Letting winners run looks excellent on the 15 names — +5 to +6 pp/yr more, half the drawdown with a trailing stop, concentration up to 45–54% — and is **worse in every variant on the hindsight-free sectors** (−0.5 to −4.4 pp/yr vs +0.4 for the live design, in-sample and out-of-sample alike). The names were picked in 2026 because they went up, so anything that holds them longer "works"; that is the universe's hindsight, not an edge, the same split Decision 062 found in stage 3. (3) The market's own outlier days are captured where they live: the SPY core (28–95% of equity) is always invested, and the insurance halves exposure on two confirmed signals instead of going to cash — chosen in Decision 062 precisely because going to cash misses the best days. **Answer given: not now, and not with a let-winners-run rule.** What would change it: the same variants on the long hindsight-free histories (sectors 1999 →, a point-in-time name universe) showing a plateau — queued for the next search, not before six months of live data, with the datasets archived on the server this time.

### Evidence addendum — more data (operator: "the more data the better", 2026-10-27)
Two universes were added to the harness the same afternoon, both key-free and hindsight-free; the Yahoo 1999 → files are still blocked (HTTP 429 from the workstation *and* titanserver, including the cookie-and-crumb flow; a patient fetcher keeps probing every 20 minutes). Loaders live in `scripts/param_search/datasets.py`; every dataset is archived on titanserver under `/home/TitanTrade/archive/param_search/`.

- **E — the S&P 500 as of 2016-01-04** (502 of 504 members with Alpaca SIP bars 2016 → 2026; the point-in-time list is the public `fja05680/sp500` membership file). Alpaca keeps bars for names delisted since (94 series end before 2026), so the universe is free of survivorship bias; the engine now settles a holding whose series ends at its last price (`delist` exit), which the previous engine silently froze.
- **F — Kenneth French's 49 industry portfolios, daily value-weighted total returns 1926 → 2026**, turned into index levels, against the market factor (Mkt-RF + RF). A century of hindsight-free, diversified "names" through 1929, 1937, 1973, 1987, 2000, 2008 and 2020; six industries have gaps in their early years.
- Engine additions (`fastbt.py`, default-off, equivalence with `backtest/mechanical.py` re-verified: same trade set, equity to 6e-9): `trail_pct`, `rank` ("deepest" | "shallowest"), `dip_max` (crash filter), delisting settlement. `exits.py` runs the exit-side, universe-shape (`--universe`) and crash-filter (`--band`) variant sets.

**F, a century of industries, live parameters:** −0.04 pp/yr vs the market (in-sample 1927–89 +0.9, out-of-sample 1990 → −1.8), Sharpe 0.64 vs 0.63, max drawdown −66% vs −84%, 11 trades/yr, 54% winners. By decade: ahead in the 1930s (+6.6), 1940s, 1960s and 2000s (+9.6); behind in the 1950s, 1990s (−5.3) and 2010s (−9.2) — the known profile, protection in bear decades and lag in long bulls, over 99 years instead of 10. Exit variants on F: +0.7 to +1.7 pp/yr in-sample for longer targets / clocks / trailing stops and −0.6 to +0.8 out-of-sample — the same mild, non-robust tilt as Decision 062's "target 20 > 15 > 10", not a plateau. The answer to the outlier question stands.

**E, 502 names, live parameters: −10.0 pp/yr** (in-sample −4.5, out-of-sample −16.3), max drawdown −58% vs −34%, 25 trades/yr, 41% winners, **median trade −12.2%** — i.e. most trades end at the stop. Not a delisting artefact (0–3 delist exits). "Deepest dip first" over 500 names above their 150-day SMA selects blow-ups from parabolic runs: on a broad single-name universe the ranking rule is adverse selection, and the curated 15-name list is what keeps the live strategy out of it. What repairs it on E: diversification — 10 × 7.5% slots +1.4 pp/yr (IS +0.9 / OOS +2.0, DD −41%), 20 × 4% −1.5; or a crash filter — dip 8–20% +1.5 (IS +1.8 / OOS +1.1, median trade +1.2%), but 8–25% −1.9 and 8–30% −0.2, so the band is a lucky cut, not a plateau. "Shallowest first" is −5.5 everywhere on E. On A / D / F the band changes nothing beyond noise (D identical: sector ETFs never dip 20% while above their SMA). **Nothing changes live.** For the next search: universe size × slot count is a real interaction (3 concentrated slots suit ≤ ~20 curated names; a 100-name universe needs more slots), and a crash filter is only worth revisiting on a broad universe with a plateau across bounds.

### Check 2026-10-27 (Oct 20 09:23 → Oct 27 13:04 UTC)
Ops: 0 ERROR / 0 tracebacks; 9 WARNINGs — 8 FRED 502s on Oct 20–21 (release-dates endpoint, retried; the Oct 21 bundle still carried the calendar incl. the FOMC meeting) and 1 "Position reduced to 325.0 shares (cash reserve)" at the DXCM entry (the gate doing its job, logged at WARNING). 27 job runs, all `completed` (incl. the Oct 25 Sunday `full`); the Oct 20 wording change is live in every plan line ("risk-off no"). Disk had grown 44% → 58%: 6.4 GB of build cache from the two image rebuilds plus two new resevolve PG 15 orphans — pruned the same day, back to 43%. Lesson for the deploy routine: each `docker compose build` leaves ~3 GB of cache; prune after deploying.

**First exit under the mechanical strategy — the broker stop, as designed.** DASH (entered Oct 13 at $192.76 × 144, stop $169.75) broke down on Oct 26: the GTC stop-limit filled in three partials 19:24–19:28 UTC at $168.74 average (limit $168.05, so 0.6% below the stop, inside the 1% buffer). Realised **−$3,459 (−12.5%)**, 3.1% of equity. The 19:30 UTC run two minutes later did everything in order: stop-out cooldown recorded with the fill price (`DASH` 72 h, override ≥ $170.42), plan found 1 free slot, the only valid signal was DXCM (15.6% below its 90-day high, above its 150-day SMA), core target 26% vs SPY 27.9% — inside the 5% band, so no SPY sale — and the slot was sized from the DASH proceeds minus the 5% reserve: 325 shares (23.2% of equity instead of 25%), bracket at $78.31 filled at once at $78.08, TP leg cancelled, GTC stop at $68.91 on the book. Why none of the deeper dips: CRWD had recovered to 7.6% below its high (no dip), ANET (20.5%) and FCX (18.4%) are below their 150-day SMA — the trend filter kept the system out of three falling names, and DASH itself is now 24% below its high and under its SMA, so the cooldown is moot. Not yet seen live: an exit through `close_position_settled` (target / holding limit / orphan).

Book (Oct 27 13:04 UTC): DXCM 23.2% (+0.6%), URI 26.5% (+5.3%), JPM 17.4% (flat), SPY 27.9% (+1.3%), cash 5.1%; all three overlay positions GTC-stopped. Equity $110,215, 3.7% below the Aug 12 peak.

Benchmark (price return): strategy window Oct 13 → Oct 26 (9 td) **−1.88% vs SPY −1.62%** (max DD −1.89% / −2.32%, beta 0.57); since Sep 29 (19 td) −1.40% vs +0.15%. Both under the 20-day verdict floor; the DASH stop is the whole gap.

## Decision 064: Expired-bracket resubmission removed — the plan already re-enters
**Date**: 2026-10-16
**Decision**: `entries.resubmit_expired_brackets`, `entries.get_expired_brackets`, `MAX_BRACKET_ATTEMPTS`, the `resubmit` CLI and scheduler command, and the `trigger` parameter of `handle_entry` are deleted (entries.py 420 → 331 lines, executor.py 393 → 379).

Found at the 2026-10-16 post-deploy check: the scan read the last 500 closed orders with no time bound, so every run re-evaluated 30 LLM-era expired brackets across 12 tickers (FANG left the watchlist in June) and logged 13 "no NEW item in the plan" lines; its 20-attempt price-chase cap counted expirations over the whole account history instead of per thesis cycle, because the weekly refresh that used to reset it no longer exists. Under the plan the step was redundant: a bracket that expires at the close is no longer an open order, the ticker keeps its NEW item while the dip signal holds, and the executor's NEW-item path places a fresh bracket at the live price at the next run — the same action resubmission took, through the same `handle_entry`, under the same eight gates. The chase cap guarded against chasing an analyst's entry level for weeks; the mechanical entry is a near-market limit (live × 1.003) that fills the same session almost always, and a dip signal that persists is by definition still a signal.

**Behaviour change**: none on fills. Trade records no longer carry the `bracket_resubmission` trigger (older records keep it; `trade_state._opening_buy` still reads both). The 13 noise lines per run are gone. **Tests**: 233 (the three resubmission tests removed; the end-to-end executor test no longer stubs the step); ruff clean. **Docs**: CLAUDE.md, features, both architecture docs, risk_management, data_schemas, api_reference, insights, todo.

**Deployed**: 2026-10-16 09:08 UTC, commit `84b36dd` — both images rebuilt, API restarted, health ok, 7 jobs, scheduler `COMMANDS` = curate / daily_summary / execute / fetch / full / gapcheck / signals, CLI image import-verified without the removed function, 0 warnings after the restart. First runs under it: the 13:35 UTC gapcheck and the 14:15 UTC execute the same day — the execute log should no longer show "Found N expired bracket orders".

### Check 2026-10-20 (Oct 16 09:08 → Oct 20 09:12 UTC)
Ops: 0 ERROR / 0 tracebacks; 1 WARNING in 4 days — a FRED 502 on attempt 1/5 at the Oct 16 fetch, absorbed by the retry. **Decision 064 verified live**: 0 "expired bracket" lines in 5 execute runs (Oct 16 ×2, the first Sunday `full` on Oct 18, Oct 19 ×2); each run reads plan → portfolio → core target → "Execution complete" in four lines. All 7 jobs `completed` (fetch ×3, gapcheck ×2 "0 closed, 0 placed", daily summary ×2 sent). Book unchanged since Oct 13: DASH 25.2% (+0.6%), URI 24.0% (−3.8%), JPM 17.2% (−0.4%), SPY 27.6% (+1.0%), cash 6.0%; all three overlay positions GTC-stopped at the plan levels; no orders, trades or near misses. Breadth rose 45.5% → 54.5% on Oct 17; SPY above its 200-day SMA; insurance stays off (full exposure). Disk 44%.

Observation, by design: CRWD and ANET have deepened to 18.5% / 18.3% below their 90-day highs (FCX 13.0%) while all three slots are held by shallower entries (JPM was an 8.4% dip). The strategy has no rotation rule — a slot frees only on a stop, a target or the 60-day clock — exactly as backtested (Decision 062). Nothing to change; noted so a later "why didn't it buy the deeper dip" has its answer. First exit through `close_position_settled` still unseen (URI is the closest, −3.8% of a −12% stop; the 60-day clock runs to mid-January).

Benchmark (price return, SPY split-adjusted): new strategy window Oct 13 → Oct 19 (4 td) **−1.07% vs SPY −1.48%** (max DD −1.87% / −1.90%); since Sep 29 (14 td, straddles the conversion) −0.59% vs +0.30%. Both are samples, not verdicts; the go/stop rule (Phase 2.0) needs a quarter.

## Decision 063: Cleanup after the conversion — the LLM pipeline frozen under `legacy/`, a plan schema, the Flutter app deleted, one settled close for every exit
**Date**: 2026-10-13
**Decision**: the operator asked for "a larger cleanup — redundant code and docs, perhaps even the architecture" after Decisions 061/062, and chose: move the old LLM code to a legacy folder rather than delete it, delete the Flutter app (unused), and rename the thesis / sentry schemas to a plain plan. The live tree now contains only what the schedule runs.

1. **Legacy freeze** (`TitanTrade/legacy/`): `weekly_analyst.py`, `daily_sentry.py`, `price_check.py`, `positions.py`, `trailing_state.py`, `performance.py`, `ai_parsing.py`, `sec_edgar.py`, the FMP provider, the full `indicators.py` (RSI / MACD / Bollinger suite), the LLM-era backtester (`engine`, `simulator`, `synthetic_thesis`, `metrics`), twelve test files written against the thesis schema, the pyramid wash-trade probe script and the analyst / sentry prompt-engineering doc. Not on the import path, not collected (`testpaths = ["tests"]`), not copied into the Docker image (`COPY src/ data/`). The last commit on which all of it ran and passed its 613 tests is tagged **`v2-llm-pipeline`** (`6e66009`). `legacy/README.md` is the index.
2. **Flutter app deleted** (`titan_trade_app/`, 5 k lines + docs). The API is the only front end; the dashboard endpoints it needed (`/api/theses`, `/api/sentry`, `/api/pricecheck`, `/api/trailing-stops`, `/api/signals`, `/api/backtest-results`, `/api/actions/*`, `/api/jobs/*`) are gone.
3. **Plan schema**: `mechanical.build_plan` writes `state/plan.json` — `items` (`NEW`: entry at the last close, stop −12%, target +20%, `dip_pct`, reason; `HOLD`: stop / target from the opening BUY in the trade log, `opened_at`), `watch` (signals not taken and names below trend, each with its reason), `candidates` (ranked, `chosen`), `insurance`, `breadth`, `params`, `stale_inputs`, `held`, `legacy_to_close`, `pending_buys`, `free_slots`, `new_signals`. `weekly_thesis.json`, `sentry_signals.json`, `signals.json`, `thesis_history.json`, `trailing_stops.json` and `pricecheck_signals.json` are no longer written; `strategy.json` stays. The executor no longer impersonates a BULLISH thesis with a fixed confidence to reach the bracket path.
4. **Modules rewritten for the plan** (live tree 6.5 k lines, was ~13 k): `config.py` (`TradingSettings` = watchlist, mode, the eleven mechanical parameters, sector ETFs, core; Gemini / FMP / `strategy` / `risk_per_trade` / `stop_loss_pct` / trailing / TP1 / pyramid / hedge gone; `REQUIRED_KEYS = {CLAUDE_KEY}`); `executor.py` (371 lines: `execute_trades`, `_ensure_coverage` / `ensure_stop_coverage`, `_manage_held`); `entries.py` (`handle_entry`: live price → cooldown → `pricing.entry_levels` → sanity → committed cash → `pre_trade_check` → one bracket → GTC stop on fill; `resubmit_expired_brackets`; the stop-out scan); `risk_manager.py` (**eight gates** — the confidence gate had nothing to read; `pre_trade_check(ticker, item, …)` sizes the slot); `pricing.py` (`entry_levels`, `near_market_entry`); `cooldown.py` (`cooldown_override_allowed(hours, price, exit)` — no sentry confirmation exists any more, so the override is 24 h + 1% above the exit); `protection.py` (plan-based orphan close, `close_position_settled`); `core_allocation.py` (residual target only; hedge swap gone); `trade_state.py` (records carry `stop_price` / `target_price`; readers accept the old `stop_loss_price` / `take_profit_price`); `data_fetcher.py` (bundle = signal inputs, ATR, correlations, SPY context, breadth, earnings, macro calendar — news, SEC filings, insider trades, ratings and the indicator suite are gone); `market_context.py` (breadth + SPY returns); `notifier.py` (plan section in the daily summary; sentry-degraded / pyramid / TP1 notices gone); `scheduler.py` (`COMMANDS` = full, fetch, signals, execute, gapcheck, resubmit, daily_summary, curate); `api.py` (18 routes); `__main__.py`; `curator.py` owns `_call_claude`; `indicators.py` = ATR + correlation.
5. **Bug fixed on the way — every exit is now the settled close.** At the first mechanical run (2026-10-13 14:15 UTC) the orphan close had to sell eight legacy positions; three of seven market sells were rejected with Alpaca 40310000 because the path cancelled the stop and sold without waiting for the cancel to settle, and FCX, HCA and LLY sat without a stop until a manual trigger of the morning job. The abort path next to it had polled the cancel to a terminal state since Decision 035. `protection.close_position_settled(ticker, cfg, trigger, reason)` — cancel each resting order, `_wait_for_order_canceled`, re-read the position, close at market, restore the stop at the cancelled level if the sell fails — now serves the orphan, target and holding-limit exits.
6. **Also found and fixed**: the daily Discord summary and the `/api/portfolio` fallback read `state/portfolio.json`, which no module had ever written (the file did not exist on the server) — the summary has been posting without equity, cash or positions. `execute_trades` now writes the snapshot at the end of every run.
7. **Trade records**: triggers are `entry`, `bracket_resubmission`, `target`, `holding_limit`, `orphan_close`, `gap_down_protection`, `core_rebalance`; BUY records carry `order_type: "bracket"`, `dip_pct`, `gate_results` (eight keys) and a context of `close`, `high_lookback`, `sma_trend`, `atr_14`, `earnings_days_away`, `sector`, `spy_return_5d`, `sector_breadth`.
8. **Config / env**: `GEMINI_KEY`, `GEMINI_MODEL`, `DATA_PROVIDER`, `FMP_KEY`, `SEC_USER_AGENT` removed; `data/watchlist.json` settings are `trading_mode` + `mechanical` only (the stale `risk_per_trade`, `stop_loss_pct`, `strategy` keys were dropped; the executor reads the parameters at every run as before).
9. **Tests**: 236 in `tests/` (new `test_executor`, `test_entries`, `test_risk_manager`, `test_protection`, `test_broker`, `test_cooldown`, `test_core_allocation`, `test_trade_state`, `test_alerts`; `test_mechanical` rewritten for the plan; `test_gap_down`, `test_notifier`, `test_scheduler`, `test_market_data`, `test_indicators`, `test_trading_mode` adapted; `test_stop_coverage` and `test_orphan_close` folded into the new files). Every Claude / Alpaca / FRED / Finnhub call mocked; ruff clean on `src/` and `tests/`. The ported scenarios keep their production anchors (EQIX $969.95 TP-leg coverage, FCX 40310000 race, DVN stop-out cooldown, the 0.19-share URI bracket guard, the DXCM committed-cash case).
10. **Docs rewritten** for one system: `CLAUDE.md`, root `docs/{architecture,features,insights,security,agent_instructions}.md`, `TitanTrade/docs/{architecture,risk_management,api_reference,data_schemas,deployment}.md`. Decisions 001–062 stay as written (history); the LLM-era design is reachable through them and the tag.

**Behaviour change**: none intended beyond item 5 and the removal of the sentry-confirmation half of the cooldown override (item 4), which had no sentry to read since Decision 061. Live parameters, the schedule and the gates' thresholds are unchanged; the clean window from Decision 062 continues.

**Deployed**: 2026-10-13 14:47 UTC, commit `9bf2754` — both images rebuilt, API restarted, health ok, 7 jobs registered, the CLI image imports `titantrade.executor` / `mechanical` through its `uv run` entrypoint. First `signals` run under the new code wrote `state/plan.json`: 3 HOLD items at the live stops (JPM 297.37 / target 404.42, URI 940.20 / 1278.71, DASH 169.75 / 231.89), 0 free slots, FCX on the watch list at an 8.3% dip (signal, no slot), insurance on (SPY above its 200-day SMA, breadth 45.5%), no legacy positions, inputs not stale. The 19:30 UTC pre-close run is the first `execute` on the plan schema; the old `weekly_thesis.json` / `sentry_signals.json` / `signals.json` / `trailing_stops.json` / `pricecheck_signals.json` / `thesis_history.json` / `cik_cache.json` / `backtest_results.json` in `state/` are now unread and can be deleted at the next checkup.

### Post-deploy check 2026-10-16 (Oct 13 14:47 → Oct 16 08:55 UTC)
Ops: 0 ERROR / 0 WARNING / 0 tracebacks in the API container log (147 lines) and in every per-module file log since the deploy; no reference to the retired thesis / sentry files anywhere. All 7 jobs registered, every run `completed`: 5 execute runs (Oct 13 19:30, Oct 14 and 15 at 14:15 / 19:30 UTC) on the plan path ("Plan: 0 new entry signal(s), 3 held, 0 free slot(s)… insurance on"), fetch ×2 (bundle 15/15 names, breadth 45.5%, SPY above its 200-day SMA, 0 earnings blackouts), gapcheck ×2 ("0 positions closed, 0 stops placed"), daily summary ×2 sent — with `state/portfolio.json` now written at 19:30 before the 20:30 summary (item 6 verified). Book: DASH 24.8%, URI 24.3%, JPM 17.1% (trimmed by the 70% overlay cap), SPY 27.7% (core target 29%, inside the band), cash 6.0%; all three overlay positions carry a GTC stop-limit at the plan level (169.75 / 940.20 / 297.37). No orders, trades or near misses since the deploy; equity $111,758, 2.4% below the Aug 12 peak. Four names show the dip signal with no free slot (FCX 12.9%, CRWD 10.6%, ANET 9.8%, DXCM 9.6%); GS / GE / DECK / EQIX are below their 150-day SMA. Not yet exercised: a target / holding-limit / orphan exit through `close_position_settled`. Disk 60% → 43% after the same-day cleanup (6 orphaned PG 15 volumes + 6.8 GB build cache, operator's go); the eight unread LLM-era state files were moved to `state/archive/legacy_2026-10-13/`.

Benchmark since Oct 13 (2 trading days — a sample, not a verdict): strategy −0.32% vs SPY −0.80%; the beta / alpha figures on two points are noise.

One finding, cosmetic today: `entries.get_expired_brackets` reads the last 500 closed orders with no time bound, so every run re-evaluates 30 LLM-era expired brackets across 12 tickers (FANG left the watchlist in June) and logs 13 "no NEW item in the plan" lines. Under the plan the step is redundant — an expired bracket's ticker keeps its NEW item and the normal entry path re-enters at the next run — and its 20-attempt cap now counts expirations over the whole history instead of per thesis cycle. Candidate fix (not shipped): drop `resubmit_expired_brackets`, `get_expired_brackets` and the `resubmit` command, or bound the query by `strategy.json → started_at`.

## Decision 062: Parameter plateau for the mechanical strategy (first search, 2016–2026 and 1999–2026)
**Date**: 2026-10-13
**Decision**: the live parameters move from the Decision 061 defaults to the centre of the plateau found by a staged search on four datasets, and the search harness is kept in the repo (`scripts/param_search/`) so the next search extends this one instead of restarting it.

| Parameter | Decision 061 default | **Decision 062** |
|---|---|---|
| dip below the lookback high | 10% | **8%** |
| lookback | 60 d | **90 d** |
| trend filter | 200-day SMA | **150-day SMA** |
| holding limit | 40 trading days | **60** |
| target | +10% | **+20%** |
| stop | −12% | −12% (unchanged) |
| slot / max slots | 20% × 3 | **25% × 3** (the 70% overlay cap trims the third slot to 20%) |
| insurance | SPY < SMA200 and sector breadth < 50% → 50% exposure | unchanged |

**Method.** `scripts/param_search/fastbt.py` is a vectorised engine with the same semantics as `backtest/mechanical.py` (validated trade-for-trade: identical trade lists and equity to 1e-9 on three parameter sets, 100× faster). Data: Alpaca SIP daily bars 2016-01 → 2026-10 for the 15 names, SPY and the 11 sector ETFs (`download-history` now uses the SIP feed; IEX history starts in 2020), and Yahoo adjusted daily closes 1993/1999 → 2026 (SPY from 1993, sectors from 1998, names from their listing dates). Four datasets: **A** Alpaca names 2016 →, **D** Alpaca sectors 2016 →, **B** Yahoo names 1999 →, **C** Yahoo sectors 1999 → (B/D/C mix hindsight: the names were chosen in 2026; the sector ETFs are the hindsight-free universe). Next-close fills, 0.05% per side, 5% cash reserve, SPY residual, weekly-equivalent daily evaluation. Stage 1: 6,000-point grid over dip (6–15%) × lookback (40–120 d) × trend SMA (100/150/200) × hold (20–90 d) × target (6–20%) × stop (8–20%), insurance off, 20% × 3; scored on full period, in-sample/out-of-sample halves (split 2022 for Alpaca, 2018 for Yahoo), recency-weighted annual excess (0.8^years), and **plateau** = median over the twelve one-step neighbours. Stage 2: insurance (SMA 150/200 × breadth 0.4/0.5/0.6 × scale 0/0.25/0.5/0.75/1) × sizing (slot 15/20/25% × 2–5 slots) around three centres. Stage 3: an honest walk-forward of the *selection procedure* — the grid is run on a training window only, the plateau-best point is selected there, and that point is run fresh on the next window.

**Stage 1 — what every dataset agreed on.** Marginal effects (mean excess CAGR vs SPY over all other settings) point the same way on all four datasets: target 20% > 15% > 10% (the strongest knob: +0.7 to +2.3 pp from 10% to 20%), dip 8% ≥ 10%, trend SMA 150 ≥ 200 ≥ 100, hold 40–90 d ≈ flat, stop 8–20% flat. Cross-dataset rank 1 by plateau out-of-sample excess: dip 8% / 120 d / SMA150 / 60 d / +20% / −10% (A +7.8 full, +6.6 in-sample / +9.3 out-of-sample; D +2.2, +0.9 / +3.8; B +7.2, +5.1 / +12.1; C +1.4, +0.9 / +2.7 — positive in all eight halves). The sector-universe full-period best differs only in lookback (60 d) and stop (20%). The live defaults: A +4.8, D +1.2 (2.9 trades/yr), B +5.1, C +1.0. The chosen midpoint (8 / 90 / 150 / 60 / 20 / 12): A +4.9 (in-sample −4.1 / out-of-sample +16.7 — the 15-name Alpaca decade is the noisiest sample), D +2.1 (+1.5 / +2.9), B +8.0 (+8.3 / +7.5), C +1.5 (+0.9 / +3.1); its twelve neighbours: D min +0.5 / median +1.6 / max +2.8, C +0.8 / +1.3 / +1.8, B +3.6 / +6.5 / +9.5, A −0.2 / +5.9 / +9.1 — a plateau, not a peak.

**Stage 2 — insurance and sizing.** Insurance is a pure trade-off on every dataset: each step of scale below 1 lowers both the excess and the drawdown, and 0.5 is the knee. On the 27-year hindsight-free sectors with the sector-best centre: insurance off +2.3 pp/yr excess at −53% max drawdown (SPY −55%); scale 0.75 → +1.2 at −45%; **scale 0.5 → +0.6 at −35%, Sharpe 0.69 vs SPY 0.53, 2008 −35% vs −55%, 2000–02 −31% vs −48%, 2022 −11% vs −25%**; scale 0 → −0.5 at −32%. With the consensus centre the same row reads −0.4 at −35%. On the Alpaca decade (three V-shaped recoveries, one bear) insurance costs more: sectors scale 0.5 → −0.3 to +0.7 at −24% (SPY −34%); names +6.1 at −31% (SPY −34%). SMA 200 ≥ 150 for the switch; breadth 0.4/0.5/0.6 is noise, 0.5 kept. Sizing: 25% slots beat 20% by 0.3–1.5 pp on every dataset at the same drawdown on sectors (slightly higher on names); 2–3 slots best on sectors, 3–4 on names.

**Stage 3 — the honest part.** Selecting the plateau-best point on a training window and running it on the next window **did not generalise on the hindsight-free sectors**: the per-window winners (always 6% dips, short holds, many trades) lost to SPY in all three sector tests (−1.4, −0.5, −1.7 pp) and were mixed on the names (+5.6, −0.7, +8.7, +4.3). The fixed cross-dataset consensus did better: sectors +1.9 (2022 → 2026), −0.4 (2009 → 2017), +2.4 (2018 → 2026), −1.0 (2014 → 2019); names +9.4, +3.6, +11.8, −1.8; the live defaults: sectors +1.5, −0.9, +1.7, −0.4. Reading: the edge on a hindsight-free universe is real but small — about +0.5 to +1 pp/yr before insurance, period-dependent (it loses in low-volatility bulls such as 2014–2019) — and it is captured by broad parameter agreement across universes and eras, not by optimisation. Any future search must be judged this way.

**What to expect live (names universe, insurance on):** return around SPY plus the names' edge over SPY (which is the operator's universe, not the system), a third less drawdown in a 2008- or 2022-type decline, lag in V-shaped recoveries, 5–8 trades a year per slot with 70–80% winners at the 20% target or the 60-day clock, and more candidates than the 10%/60-day rule produced (on the Alpaca decade the 8%/90-day/SMA150 rule is on for 4,896 name-days vs 3,458 — about 40% more, on 78% vs 63% of sessions). First live signals run under these parameters (2026-10-13 13:18 UTC): DASH (18.0% below its 90-day high) and JPM (8.4%), insurance on.

**Applied**: `data/watchlist.json` → `settings.mechanical` (no code deploy needed; the executor reads it at every run). The clean window restarts at the first run under these parameters.

## Decision 061: Mechanical strategy — the LLM leaves the trading loop (October 13 audit → conversion)
**Date**: 2026-10-13
**Decision**: after the component audit (Decision 060, Evidence 2–3) the operator opened the hold and asked for a full conversion: every trading decision becomes a rule on prices, the LLMs keep only jobs that cannot touch orders, and the strategy becomes backtestable so the coming parameter search runs on a decade of data instead of on 22 weekly samples. The live pipeline is now:

1. **Entry — buy the dip in an uptrend** (`signals.py`, the only rule in the audit that added return on a hindsight-free basket, Evidence 3(g)): a watchlist name closes ≥ `dip_pct` (10%) below its `dip_lookback_days` (60) high while above its `trend_sma_days` (200) SMA. Candidates are ranked deepest dip first and take the free slots (`max_slots` 3, `slot_pct` 20% of equity each, flat — no ATR, confidence or VIX scaling). Entries go through the unchanged bracket path and all nine gates: `mechanical.py` writes a BULLISH / NEW / `selected_for_trading` thesis at the last close with the fixed confidence 0.80 (≥ 0.80 → near-market limit), a −`stop_pct` (12%) stop and a +`tp_pct` (10%) target, so `entries._handle_bullish_entry`, resubmission, the cash-reserve/overlay/sector/earnings/macro/correlation gates and the stop-coverage helper (Decision 060) all run as before. Sizing under `strategy == "mechanical"` is the slot (`risk_manager.pre_trade_check`).
2. **Exits — three, all mechanical**: the broker stop-limit at −12% (GTC via the Decision 060 coverage), the +10% target and the `max_hold_days` (40 trading days) limit, the latter two evaluated against the broker position at every executor run (`executor._manage_held_mechanical`, close-based exactly as backtested, cancel-settle-close like the abort path). No trailing stop, TP1, pyramiding, sentry abort, price-check abort or hedge swap. A stop-out still records the 72 h cooldown (Decisions 056/059).
3. **Core — SPY is the residual**: `core_target = exposure_scale × (1 − 5% cash reserve) − (held overlay + this run's planned slots)` (`mechanical.core_target_pct`, passed to `manage_core_position(target_pct=…)`). The core sells SPY before the entries need the cash and buys it back after exits; the account is read again after the core trade so entries size on fresh cash.
4. **Insurance — two-signal confirmation at the portfolio level** (Evidence 3(f): the cheapest design, ≈ 1.5 pp/yr for a third less drawdown): exposure is scaled to `insurance_scale` (0.5) only while SPY is below its `insurance_sma_days` (200) SMA **and** the share of the 11 sector ETFs above their SMA is below `insurance_breadth` (0.5); new entries pause while risk-off, held positions keep their exits. Inputs come from the data bundle (`market_context.breadth`, computed in `market_context.sector_breadth` from 250-day ETF bars). Both inputs unknown → full exposure (fails open).
5. **Removed from the loop, kept in the repo for `strategy: "llm"` A/B runs**: the weekly Claude analyst (selection, direction, confidence, levels), the daily Gemini sentry, the intraday price checks, the trailing/TP1/pyramid manager and the SH hedge swap. None is scheduled; `TradingSettings.strategy` defaults to `"mechanical"` and is set explicitly in `data/watchlist.json`.
6. **The LLM's remaining jobs** (`curator.py`, monthly, no orders): a universe-curation proposal (≤ 2 removals, ≤ 2 additions, reasons; written to `state/universe_proposal.json`, posted to Discord, applied by the operator through the watchlist editor) and a plain-language post-mortem of the month's trades (`state/post_mortem.json`).
7. **Backtester** (`backtest/mechanical.py`): the same `signals.py` functions on daily closes, next-close fills, per-side costs, slot accounting out of SPY, cash reserve, the insurance switch and a walk-forward helper over a built-in coarse grid; `backtest-mech [dir] [--start] [--end] [--split] [--grid]`; `download-history [dir] [--days N]` now fetches the sector ETFs too. The operator's large parameter search (longer history from a free source, plateau selection, recency weighting) is the next phase.
8. **Transition**: the first mechanical run writes `state/strategy.json` (`started_at`); positions opened before it are *legacy* — they get no thesis and the executor's existing orphan close sells them at the first market-open run, after which the core rebalances to the residual target. New clean window from the deploy.
9. **Schedule** (`data/schedule.json`): Sunday `full` = fetch → signals → execute; weekdays fetch 09:00, gapcheck + stop coverage 09:35, `execute` (= signals + execute) 10:15 and 15:30, daily summary 16:30; `curate` on the first Sunday of the month 15:00. The two price-check jobs and the sentry are gone from the schedule.
10. **Go/stop rule rewritten** (todo Phase 1.36 → 2.0): fund real money only when a quarter of paper behaves like the backtest, with return within 2 pp/yr of SPY over the window and max drawdown ≤ 0.7 × SPY's in any SPY drawdown ≥ 10%. Superseded by Decision 069 (2026-10-29): behaviour and drawdown decide, return is reported.

Parameters are the defaults that the decade tests used; they are deliberately few and expected to sit on plateaus, not peaks. The dashboard keeps working unchanged: `/api/theses` now shows the mechanical theses (NEUTRAL names carry the reason there is no signal), `/api/sentry` shows CONTINUE for every held/selected name plus the insurance state under `market_health`, and two endpoints were added (`/api/signals`, `/api/universe-proposal`).

**Tests**: 24 new in `tests/test_mechanical.py` (signal rules, breadth and the two-signal insurance, thesis generation with held / legacy / pending / risk-off cases, the residual core target, slot sizing through `pre_trade_check`, target / time exits with cancel-settle, an end-to-end `execute_trades` run that turns a signal into a 227-share two-tranche bracket with a 75% core target, scheduler wiring, the backtester on synthetic series, the curator with a mocked Claude, the API). 612 total, all green; ruff clean. The legacy pipeline's tests run with `strategy="llm"` and are untouched.

**Deployed**: 2026-10-13 12:42 UTC, commit `bdc558a` — both images rebuilt, API restarted, 7 jobs registered (`sunday_full`, `monthly_curate`, `weekday_fetch`, `weekday_gapcheck`, `weekday_execute_morning`, `weekday_execute_preclose`, `daily_summary`), health ok. First `fetch` with the new bundle fields and first `signals` run at 12:43 UTC: `state/strategy.json` written (`started_at` 2026-10-13T12:43:24Z), insurance on (SPY above its 200-day SMA, sector breadth 45.5% — one signal alone does not de-risk), one entry signal (DASH, 18.0% below its 60-day high, above its 200-day SMA), 3 free slots, 8 legacy positions (CRWD, ANET, LLY, HCA, DVN, URI, FCX, EQIX) queued for the orphan close at the 14:15 UTC market-open run, after which the core rebalances to the 75% residual target and the DASH slot is placed. New clean window starts 2026-10-13.

## Decision 060: Stop coverage after a bracket fill — one helper for every path, entry-time level, gapcheck companion (October 13 checkup)
**Date**: 2026-10-13
**Decision**: a bracket's exit legs are DAY orders on Alpaca (the API offers no GTC bracket — Decisions 021/028) and die at the 20:00 UTC close, so every filled bracket needs a GTC stop of its own placed by the next run. Two paths got this wrong in different ways, found in the October 13 log sweep:
1. **The ADJUST "re-opened after the review" branch skipped every check.** The Decision 056 guard (`position_opened_after` → `continue`) correctly refused to apply Sunday's levels to a position re-entered mid-week, but it also skipped stop coverage, so the DAY legs expired and the position sat bare until the next market-open run. Production FCX: stopped Oct 1, re-bought Fri Oct 2 15:10, **no stop from Fri 20:00 to Mon Oct 5 14:15 UTC**; EQIX (Fri Oct 9 19:46 fill) none until Mon Oct 12 14:15. The 13:35 UTC gapcheck closes catastrophic gaps only. **Fix:** the branch now calls the coverage helper before `continue` — the entry-time level stays, but it is put on the book.
2. **The held-bullish path placed the thesis stop instead of the bracket's.** After a fill Alpaca keeps the stop leg in `held` while the TP leg is live, and held orders are not returned by `GET /v2/orders?status=open` — so `_manage_held_bullish` saw "TP leg but no stop", cancelled the TP (OCO took the stop with it) and placed a fresh GTC stop at the *thesis* `stop_loss_price`. For a position re-entered with an adapted bracket that is the wrong level: EQIX Oct 2 19:30, **$969.95 → $1000**, tagged Oct 8 at $998.23 (−$119) and re-bought Oct 9 at $1023.87 (+$128 re-entry gap); URI Oct 5, $987.09 → $970. **Fix:** `_coverage_stop_price` — a position opened after the current review was generated is covered at the trade-log stop of its opening BUY (`trade_state.position_entry_stop`); otherwise, and when the log has no usable level, the thesis stop as before. Same rule the ADJUST path already applies to levels (Decision 056).
3. **The gapcheck job also places missing stops.** `executor.ensure_stop_coverage` runs after `check_gap_down_protection` at 13:35 UTC (scheduler and CLI): any held whole-share overlay position with a thesis and no resting stop gets one via the same helper, so a bracket that filled after the pre-close run is covered five minutes into the session instead of at 14:15. Orphans are left to the execute run's orphan close; the core allocation carries no stop by design.

Mechanically: the "place a fresh stop" block (TP-leg recovery, off-hours deferral, TP restore on half-failure) moved verbatim from `_manage_held_bullish` into `_ensure_protective_stop`; `_ensure_coverage` wraps it with the has-stop / fractional / level checks and is the single entry point for the three callers. Behaviour on every previously covered path is unchanged except the level choice in item 2. Plumbing, not strategy — the hold (Decision 051 addendum) is untouched.

**Tests**: 9 new in `tests/test_stop_coverage.py` (entry-stop lookup skips pyramid adds and legacy records; level choice for re-opened vs older positions; the EQIX TP-leg scenario places $969.95 not $1000; the FCX ADJUST-re-opened scenario end-to-end through `execute_trades` places the entry-time stop and applies no ADJUST level; `ensure_stop_coverage` touches only bare overlay positions). 587 total, all green; touched files ruff-clean.

**Deployed**: 2026-10-13 09:29 UTC, commit `452a6e1` — both images rebuilt and import-verified, API restarted, health ok, 8 jobs registered, smoke run of `ensure_stop_coverage` placed 0 stops (market closed, every position already covered).

### October 13 checkup (2026-09-29 → 2026-10-12, 9 trading days)
Ops: 0 ERROR/CRITICAL/tracebacks in 3,029 log lines (14 d), 75 WARNINGs all expected (sentry noise/abort classifications, cooldown overrides, Decision 058 live-price floor ×3 on JPM keeping $333.15, FRED 502 ×5 absorbed by retry), 8 scheduler jobs `completed`, both images = Sep 29 12:20 build, git clean at `ef42847`. AI $3.03 Oct-to-date ($6.30 Sep). Equity $112,682; 8 overlay positions + SPY core 34.5%, all 8 GTC stop-covered at check time, cash 6.3%. Disk 62% (build cache 7.3 GB, 6 dangling PG 15 volumes 498 MB).

Decision 059 verified live: `benchmark_metrics.json` computed Oct 12 20:30 UTC has `window_end = 2026-10-12` (item 2 ✓). Override lines read "≥1% above the $X exit" (item 1 ✓): 3 allowed (FCX Oct 2 +4.2% above the $68.91 exit, EQIX Oct 2 +3.0% above $998.13, EQIX Oct 9 +2.6% above $998.23), ≥5 evaluations refused (JPM ×2 at +0.0…+0.4% above $333.08, DXCM ×3 at +0.5…+0.6% above $83.91). Both refusals were right: JPM closed Oct 12 at $334.30 (+0.4%) and the Oct 4 review dropped it; DXCM re-dipped −5% on Oct 8 before +1.8%. DASH's legacy record (no `exit_price`) fired the old-wording override ×4 Sep 30 – Oct 2; every attempt was dust-blocked ($90–99 budget behind the pending DXCM bracket). Note for the next sweep: a refused override logs only "Skipping … in re-entry cooldown (Xh since ABORT)" — infer the refusal from hours ≥ 24 + sentry CONTINUE.

Performance (`compute_benchmark(persist=False)`, windows end Oct 12; SPY = split-adjusted price return):

| Window | Strategy | SPY | Beta | Sharpe (S / SPY) | Up / down capture | Max DD (S / SPY) |
|---|---|---|---|---|---|---|
| New clean window since Decision 059 (Sep 29, 9 td) | +1.05% | **+1.82%** | 1.54 | 2.38 / 7.12 | 1.23 / 2.48 | −1.27% / −0.66% |
| Clean since 2026-07-08 (67 td) | +4.22% | +4.39% | 0.69 | 1.37 / 1.54 | 0.77 / 0.71 | −4.64% / −3.38% |
| Since the Aug 12 peak (42 td) | −1.56% | **+0.73%** | 0.83 | −0.78 / 0.51 | 0.77 / 0.99 | −4.64% / −3.06% |
| Since Decision 057 (Sep 2, 27 td) | **+2.17%** | +1.69% | 0.91 | 1.83 / 1.61 | 0.97 / 0.88 | −2.32% / −2.47% |
| Since Decision 046 (May 12, 105 td) | **+11.41%** | +5.41% | 0.85 | 1.27 / 1.09 | 1.14 / 0.95 | −8.15% / −4.49% |
| Since inception (Mar 30, 135 td) | +12.76% | **+23.12%** | 0.63 | 1.22 / 3.11 | 0.77 / 0.87 | −8.15% / −4.49% |

Churn in the new window: 5 exits (JPM Sep 30, FCX Oct 1, EQIX Oct 1, DXCM Oct 6, EQIX Oct 8), all broker stops at analyst levels, all losers, realised −$629 (FIFO on Alpaca fills); 3 of 5 re-bought within 7 days at a higher price (FCX +4.2%, EQIX +3.0%, EQIX +2.6%), re-entry gap ≈ $562. Exits + gap ≈ $1.2k ≈ 1.05% of equity ≈ the whole lag vs SPY in the window. No SPY drawdown yet (max −0.66%), so the go/stop clock (todo Phase 1.36) keeps running. Watch: CRWD $258 and ANET $206.50 analyst stops sat 1.0–1.1% below the Oct 12 close.

### Evidence — is it selection or execution? (operator question, 2026-10-13)
Counterfactual built from `thesis_history.json` and SIP daily closes (split-adjusted): **EW picks** = equal-weight, daily-chained return of every `selected_for_trading` ticker in the review in force (Sunday's list applies from Monday's close, re-selected weekly); **passive book** = 34% SPY + 60% EW picks + 6% cash, i.e. the strategy's book structure with no stops, no sentry, no trail, no sizing; **static B&H** = equal-weight buy-and-hold of every name selected at least once in the window.

| Window | Strategy | SPY | EW picks | Passive book | Static B&H |
|---|---|---|---|---|---|
| Clean since Jul 8 | +4.22% | +4.39% | +2.56% | +3.03% | +5.25% |
| Since Aug 12 | −1.56% | +0.73% | −4.61% | −2.52% | −1.63% |
| Since Sep 2 | +2.17% | +1.69% | +0.68% | +0.98% | +2.25% |
| Since Sep 29 | +1.05% | +1.82% | +1.71% | +1.64% | +2.16% |

Per-name buy-and-hold over the clean window (weeks selected): CRWD +37.6% (12), FCX +27.5% (12), ANET +16.5% (13), DXCM +16.0% (13), DVN +13.0% (11), HCA +11.7% (11), FANG +4.6% (3), DASH +2.6% (9), EQIX +1.6% (14), JPM +1.1% (12), WMT 0.0% (3), URI −1.4% (8), LLY −2.7% (10), GS −13.2% (7), GE −13.3% (9), DECK −17.6% (2).

Reading: **over the three-month clean window the analyst's basket trailed SPY by 1.8 pp (selection), and the execution layer added 1.2–1.7 pp over passively holding those picks** — the stops cut GS/GE/DECK's −13…−18% short, the trail and pyramid rode CRWD and FCX — which brought the strategy back to ≈ SPY. **The lag since the Aug 12 peak is selection:** the basket lost 4.6% while SPY gained 0.7%; execution recovered about 1 pp of that, it did not cause it. Only the two-week window since Sep 29 shows execution as the net cost (picks ≈ SPY, five stop-outs −0.6 pp). One more selection signal: holding every selected name statically beat the weekly re-selected basket by 2.7 pp over the clean window, so the analyst's weekly rotation (dropping winners, adding GS/GE) is itself a drag. Caveats: equal weight vs the bot's risk-based sizing; price return on both sides; 9–67 trading days. Implication for the hold: the next lever, if any, is on the analyst's side (selection and rotation), not the risk machinery — and it needs the same fills-first test before anything ships.

### Evidence 2 — would a bigger watchlist help? (operator question, 2026-10-13)
Test: for every weekly review since Decision 046 (22 reviews, May 10 → Oct 4), the equal-weight return of the names the analyst *selected* vs the names it *left out* over the following week (first close after the review → first close after the next), plus the top-4 vs bottom-4 by confidence, and the Spearman rank correlation between confidence and next-week return. SIP closes, split-adjusted.

| Basket (EW, re-formed weekly) | Since May 10 (22 w) | Clean since Jul 5 (14 w) |
|---|---|---|
| SPY | +5.2% | +3.6% |
| Whole 15-name watchlist | **+18.6%** | +6.0% |
| Analyst's selected names (~10/week) | +12.6% | +1.1% |
| Names the analyst left out (~5/week) | **+29.8%** | **+17.0%** |
| Top-4 by confidence | +20.6% | +4.4% |
| Bottom-4 by confidence | +20.7% | +3.7% |

Selected beat not-selected in 7 of 22 weeks (4 of 14 clean); top-4 confidence beat bottom-4 in 11 of 22; mean Spearman(confidence, next-week return) = −0.05 (sd 0.26) — zero. Reading: the *universe* was excellent (the 15 names beat SPY by 13 pp) and the *picker* subtracted from it: the analyst's confidence does not discriminate within the list at the horizon the system acts on (weekly re-selection), and the names it drops tend to be last week's losers that rebound — the weekly version of the churn mechanism. Doubling the watchlist therefore buys nothing: with no ranking skill, 10-from-30 has the same expected return as 10-from-15, the book cannot hold more positions anyway (94% invested, whole-share and $500-notional limits, $25k PDT floor for real money), and Claude cost doubles. What the numbers point at instead — *not* decided, not shipped: (a) trade the gated watchlist rather than the confidence-ranked subset (static EW of the watchlist beat the selected basket by 6 pp since May); (b) curate the universe, which is where the edge actually came from. Caveats: 22 weeks, ~5 names in the left-out group, one bull-ish regime, equal weighting, one-week horizon (the analyst frames "medium_term" — a 4-week version of the test is the fair follow-up before anything changes).

**Component split (same day, operator asked whether Sunday's analysis works at all):** the watchlist is curated by the operator (app → `save_watchlist`, Decision 049 swap), so the universe's +18.6% is the operator's, not the analyst's. By analyst output, chained EW next-week return over the same 22 reviews: direction call — BULLISH +18.8% vs NEUTRAL/BEARISH +24.4%, bullish beat non-bullish in 11 of 21 weeks (no directional skill; at 4 weeks pooled +1.9% vs +4.4%); Pass 2 ranking — SELECTED +12.6% vs BULLISH-but-not-selected +68.2% (about 2 names a week, 41 stock-weeks, so noisy, but negative at both horizons); confidence — within-week demeaned top-third +0.37%/wk vs bottom-third +0.20%/wk (≈0.3 standard errors, noise), and the week's average confidence has no relation to the next week's SPY (Spearman +0.01). What was *not* measured here and held up elsewhere: the analyst's stop levels (Decision 059 Evidence 2 found no mechanical level that beat them) and the daily sentry (Decision 057). Precise statement: the selection, ranking and confidence outputs of the Sunday review carry no detectable signal at the horizon the system trades; the return came from the operator's universe plus the mechanical layer (gates, trail, stops).

### Evidence 3 — component value audit (operator opened the hold for "heavy refinements", 2026-10-13)
Five tests on the paper account's own history and SIP bars. Nothing shipped; the operator decides.

**(a) Realised P&L by exit mechanism, overlay sells 2026-05-12 → 10-12** (FIFO on Alpaca fills at order level, CRWD lots converted ×4/÷4 at the 2026-07-02 phantom split):

| Exit mechanism | Exits | Realised | Wins | Stock vs SPY 20 td after the exit |
|---|---|---|---|---|
| Sentry −5% catastrophic rule (mechanical, measured from the thesis reference) | 19 | **−$3,037** | 1/19 | **+4.4%** (lower after in 6/18) |
| Sentry LLM price-override / news call | 7 | **−$2,229** | 0/7 | +1.6% (lower after in 2/6) |
| Intraday price-check abort | 2 | −$234 | 1/2 | — |
| Weekly review turned bearish | 1 | −$143 | 0/1 | — |
| Weekly review dropped the name (profit-taking exits) | 4 | +$3,687 | 3/4 | (CRWD split artefact, n/a) |
| Broker-side: initial stop / 3×ATR trail / TP1 (mechanical) | 93 | **+$8,356** | 50/93 | ≈ 0 (median −0.2% at 10 td, 0.0% at 20 td) |
| Total overlay realised | | +$6,717 | | |

The sentry as a whole: 26 exits, 1 win, −$5.3k ≈ 5% of equity, and the names it sold went on to beat SPY. Its −5% rule is in effect a 5% hard stop stapled on top of the 3×ATR trail, so the tight one always fires first and sells the dip. The broker-side mechanical exits are a wash on direction (stops are insurance) and the profit capture (trail + TP1) is where the realised gain came from.

**(b) Risk gate — trend_regime blocks** (65 near-miss records, 31 unique ticker-days): blocked names +3.3% vs SPY over the next 20 td (rose 21/23); executed entries over the same period +5.8% vs SPY at 20 td. Mild positive discrimination at 20 days, negative at 5 days. Inconclusive.

**(c) Mechanical selection on the same 15 names, weekly rebalanced, 2024-10-14 → 2026-10-12** (basket figures; book = 34% SPY + 60% basket):

| Rule | 2-yr return | max DD | Sharpe | beta | 2025 crash (Feb 19 → Apr 8) | crash + recovery (→ Jul 1) | live window (May 11 → Oct 12) |
|---|---|---|---|---|---|---|---|
| SPY | +33.2% | −19.0% | 0.96 | 1 | −19.0% | +0.8% | +5.2% |
| EW all 15 | **+55.3%** | −23.5% | **1.22** | 1.06 | −23.3% | +1.5% | **+17.7%** |
| EW above SMA50 (slot kept in cash otherwise) | +22.6% | **−11.2%** | 1.03 | 0.37 | **−10.8%** | −2.0% | +8.8% |
| EW above SMA200 | +19.2% | −14.2% | 0.82 | 0.49 | −13.3% | −5.9% | +10.3% |
| EW SMA20 > SMA50 (the live trend_regime gate) | +22.7% | −12.9% | 0.97 | 0.47 | −12.9% | −6.2% | +12.5% |
| Top-7 by 60-day momentum among > SMA50 | +24.7% | −20.3% | 0.72 | 0.59 | −19.5% | −10.1% | +7.0% |
| Bottom-7 by 60-day momentum among > SMA50 | +34.5% | −19.1% | 0.99 | 0.54 | −18.3% | −7.7% | +17.4% |

Momentum ranking lost to anti-momentum in every window — short-horizon mean reversion dominated this universe. Trend filters halved the crash drawdown and gave the recovery back; over two years they did not improve Sharpe over plain equal weight. Caveat: the 15 names were chosen in 2026 with hindsight, so the universe's absolute edge (+55% vs +33%) is not a forward expectation; the *relative* ranking of rules on the same names is the usable result.

**(d) Live strategy vs its own passive book, May 12 → Oct 12:** strategy +11.4%, passive book (34% SPY + 60% EW universe) +12.3%, SPY +5.4%. The active apparatus roughly broke even against holding the universe: the mechanical exits (+$8.4k) and the review's profit-taking drops (+$3.7k) paid for the sentry (−$5.3k) and the selection drag.

**Reading across (a)–(d) and Evidence 2:** every rule that sells a dip (sentry, price check, weekly drops, momentum ranking, tight analyst stops) lost; every rule that held through dips won. The only regime where dip-selling paid — a sustained decline — was Feb–Apr 2025, and the mechanical trend filter did help there, then gave it back by July. No component has shown *return* skill; the mechanical risk layer has shown *drawdown* control, and it is the only layer that can be backtested.

**(e) Can we have both — return ≥ SPY and a smaller drawdown? Same 2-year test, protection moved from the stock level to the portfolio level** (basket figures, 2024-10-14 → 2026-10-12 / 2025 crash / crash+recovery):

| Design | 2-yr return | max DD | Sharpe | crash | crash + recovery |
|---|---|---|---|---|---|
| SPY | +33.2% | −19.0% | 0.96 | −19.0% | +0.8% |
| EW all 15, no protection | +55.3% | −23.5% | 1.22 | −23.3% | +1.5% |
| Per-name SMA50 filter, slot to cash (stock-level, like today) | +22.6% | −11.2% | 1.03 | −10.8% | −2.0% |
| Per-name SMA50 filter, slots renormalised | +28.3% | −22.9% | 0.84 | −21.8% | −12.6% |
| EW all, exposure = share of names above SMA50 (partial de-risk) | +24.8% | **−10.3%** | 1.19 | −10.2% | +0.3% |
| **Breadth switch: EW all while ≥ 50% of names above SMA200, else cash** | **+34.0%** | **−16.8%** | 1.07 | −15.0% | −7.7% |
| SPY > 200-day switch, else cash (Faber) | +25.5% | −19.9% | 0.87 | −19.1% | −13.9% |
| SPY > 200-day switch, else half exposure | +40.1% | −21.2% | 1.15 | −21.1% | −6.1% |

Against SPY, "both" was achieved by exactly one design (the breadth switch: +34.0% vs +33.2%, −16.8% vs −19.0%), marginally, and only because the universe's raw +55% left room to pay the whipsaw premium. Against the unprotected universe, no protection achieved both: every one cost return. The window contains only a V-shaped crash (the worst case for any protection); over a cycle with a sustained bear, slow portfolio-level switches historically earn their premium back. Conclusion: "both" is a *horizon* question, not a false dilemma — reachable in expectation over a cycle with slow, portfolio-level de-risking (breadth / partial exposure), never within every window and never verifiable in a three-month live test; and the per-name dip-selling the live system does today is the most expensive way to buy protection (it pays the premium weekly on single-name noise). Renormalising slots into the still-trending names is the worst of both (it concentrates into the last names to fall).

**(f) Decade test of portfolio-level protection, 2016-01 → 2026-10 (SIP, dividend-adjusted, weekly signals applied next session, no leverage; operator asked for a longer window, recency weighting and a systematic search).** Four drawdowns in the window: 2018 Q4 −18.7%, 2020 −33.5%, 2022 −24.1%, 2025 −18.6%. Grid: breadth thresholds (0.4/0.5/0.6) × SMA(100/200) × de-risk level (0%/50%) × hysteresis, partial exposure, SPY-trend switches (weekly and monthly), vol-targeting (10/15/20%), two-signal confirmation; three baskets: SPY alone (signal = sector breadth), the 11 sector ETFs (hindsight-free universe), the 15 names (hindsight-picked). Recency weight 0.8^(years ago) on annual excess vs SPY. Walk-forward: rule chosen on 2016–2021, judged on 2022–2026.

SPY alone — SPY itself: CAGR 15.2%, max DD −33.8%, Sharpe 0.90:

| Rule | CAGR | max DD | Sharpe | recency-wtd excess/yr | 2020 crash | 2022 bear | 2020 recovery | 2025 recovery |
|---|---|---|---|---|---|---|---|---|
| none | 15.2% | −33.8% | 0.90 | 0 | −33.5% | −24.1% | +41.8% | +34.2% |
| confirm: 50% only if SPY < SMA200 **and** breadth < 0.5 | 13.8% | −23.4% | 1.00 | −2.1% | −23.0% | −19.3% | +23.5% | +23.6% |
| vol-target 20% (20-day, cap 100%) | 13.6% | −22.9% | 0.94 | −1.6% | −21.2% | −22.4% | +17.0% | +27.3% |
| SPY > SMA200 else 50% (weekly) | 13.5% | −23.4% | 0.99 | −2.1% | −23.0% | −17.8% | +23.5% | +23.9% |
| SPY > SMA200 else cash (weekly) | 11.3% | −18.0% | 0.95 | −4.6% | −12.0% | −11.9% | +6.8% | +13.9% |
| breadth ≥ 0.6 SMA200 else cash | 9.6% | −17.6% | 0.85 | −6.6% | −12.0% | −6.6% | −5.5% | +13.9% |
| vol-target 10% | 10.1% | −14.0% | 0.96 | −5.6% | −13.7% | −13.3% | +10.2% | +20.2% |
| SPY > SMA200 else cash (monthly, Faber) | 9.3% | −25.5% | 0.77 | −6.9% | −12.0% | −16.1% | +6.8% | +14.9% |

Rules beating SPY on both CAGR and max DD: **0 of 30** in-sample, 0 out-of-sample. Sector-ETF basket: same result (0 of 30; its unprotected CAGR is 12.5%, below SPY — equal-weight sectors lag a cap-weighted, tech-led decade). The 15 names: 14 of 20 rules beat SPY on both, in- and out-of-sample, only because the basket's raw CAGR is 28.0% (max DD −40.6%); every protection rule still cost it 3–15 pp of CAGR. Recency weighting makes protection look *worse*, not better: 2023–2026 contained two V-shaped recoveries and no sustained bear.

Reading: over a decade with four drawdowns, slow portfolio-level protection never beat buy-and-hold on return on any basket. It is insurance with a premium of **1.5–2 pp of CAGR per year for the cheapest designs** (two-signal confirmation at 50%, vol-target 20%: a third less max drawdown, higher Sharpe) and 4–7 pp for the stricter ones (half the drawdown). The premium is paid in every V-shaped recovery and earned back only in 2020/2022-type episodes. "Both" on raw return therefore needs a return source other than protection — a universe or selection edge of more than the premium — and the only basket showing one is hindsight-picked. What is achievable and testable: **≈ SPY − 1.5 pp/yr with a third less drawdown and a higher Sharpe**, or SPY's return with SPY's drawdown. Today's signal state (2026-10-12): SPY above SMA100 and SMA200, 73% of the 15 names above SMA200, **sector breadth 45% (below the 0.5 line)** — the two-signal rule would still be fully invested; a breadth-only rule would already be de-risked.

**(g) The trader's instinct, tested: "buy low" instead of "sell the dip" (operator: good traders spot opportunity when something is low; why can't we?).** Decade test 2016-01 → 2026-10: default 100% SPY; when a name closes ≥ *dip* below its 60-day high (optionally only if above its SMA200), move a 20% slot from SPY into it at the **next** close; return the slot to SPY at +*gain*, at −*stop*, or after *hold* days; 0.05% cost per side.

| Basket | dip / gain / hold / stop / trend | CAGR | max DD | Sharpe | trades | win | avg/trade |
|---|---|---|---|---|---|---|---|
| SPY buy-and-hold | — | 15.2% | −33.8% | 0.90 | | | |
| 11 sector ETFs (hindsight-free) | 12% / +10% / 40 d / −12% / above SMA200 | **16.4%** | −33.9% | 0.95 | 20 | 85% | +5.9% |
| 11 sector ETFs | 10% / hold 60 d / above SMA200 | **16.3%** | −33.0% | 0.94 | 31 | 81% | +7.6% |
| 11 sector ETFs | 8% / +8% / 30 d / −10% / above SMA200 | 15.3% | −35.4% | 0.89 | 120 | 67% | +1.9% |
| 11 sector ETFs | 5% / +5% / 20 d / −8% / above SMA200 | 14.6% | −34.8% | 0.88 | 347 | 62% | +0.9% |
| 15 names (hindsight) | 8% / +8% / 30 d / −10% / above SMA200 | 26.5% | −38.4% | 1.17 | 489 | 63% | +2.3% |
| 15 names (hindsight) | 10% / hold 120 d / no trend filter | 32.5% | −39.9% | 1.22 | 99 | 68% | +17.8% |

Reading: on a hindsight-free universe, buying a ≥ 10% dip in a name that is still above its 200-day average and holding 40–60 days beat SPY by about 1 pp/yr with the same drawdown, on 20–31 trades with 81–85% wins; shallower dips (5–8%) traded more and added nothing. Small, parameter-sensitive, but it is the first rule in the whole audit that adds *return* on a hindsight-free basket — and it is the exact inverse of what the live system does (the sentry and the −5% rule sell those dips). It is a return edge, not insurance: the drawdown stays SPY's. Combining it with the cheap portfolio-level insurance of (f) is the natural next test. Caveats: the 60-day-high/SMA200 parameters were not walk-forward selected; 20–31 trades is a thin sample; sector ETFs are the easy case (no single-name blow-ups).

**Recommendation recorded (not decided):**
1. Retire the sentry's exit authority (both the −5% reference rule and the LLM override) and the price-check abort; the resting stop + 3×ATR trail becomes the only exit. Keep Gemini only as a fact flag (earnings/binary events in the next N days → no new entry) and the market-stress input to the core hedge. Highest confidence, largest measured leak.
2. Retire the weekly analyst's selection, direction and confidence roles: hold every universe name that passes the mechanical gates, sized by ATR, no confidence scaling. Then test its one surviving job — the initial stop level — against k×ATR on the two-year backtest; if mechanical ≈ analyst, the weekly LLM leaves the trading loop.
3. Make the mechanical strategy the thing that is backtested: the existing `backtest/` engine already mirrors the live executor with synthetic theses; run it over 2024-10 → 2026-10 on the universe, compare with the live window, then iterate rules there, never live. Extend to 10+ years and a hindsight-free universe before trusting any number.
4. Reassign the LLM budget to universe curation proposals (operator approves) and natural-language post-mortems — jobs that cannot hurt orders.
5. Decide the goal before redesigning (updated after (f)): the choice is between SPY's return with SPY's drawdown, or ≈ SPY − 1.5 pp/yr with a third less drawdown via the cheapest portfolio-level insurance (two-signal confirmation at 50% exposure, or 20% vol-targeting); raw-return "both" is not on offer from protection. Original text: "beat SPY" has no evidence-backed component to stand on (the honest version is EW universe + SPY core, full drawdown); "SPY-like return with half the drawdown" is what the mechanical layer delivers (two-year: +25% vs +33%, max DD −13% vs −19%). The go/stop rule's two legs (return ≥ SPY *and* smaller drawdown) are unlikely to be met together by either design.
Not recommended: momentum ranking, a bigger watchlist for an LLM picker, loosening −5% to −7% (same mechanism), more LLM layers.

## Decision 059: Exit-anchored cooldown override + closed-session benchmark equity; ATR-scaled ADJUST floor tested and rejected (September 29 checkup)
**Date**: 2026-09-29
**Decision**: two changes and one negative result, each decided on the paper account's own fills rather than on the churn "feel" that four checkups had reported:
1. **Cooldown override measures recovery against the exit price.** The cooldown record (`state/abort_cooldown.json`) now stores `exit_price` — the mark an ABORT sold at, or the broker stop's fill price — and `cooldown_override_allowed` additionally requires the current price to be ≥ `COOLDOWN_RECOVERY_PCT` (1%) above it. The existing tests (≥ 24 h, thesis still BULLISH + selected, sentry CONTINUE, price ≥ 1% above the thesis stop) stay. Records without an exit price (written before this deploy) keep the stop-only test; they expire within 72 h. `cooldown.py`, `entries.py` (both override call sites + the stop-out scan), `executor.py` / `price_check.py` (abort handlers pass the mark), `notifier.py` (Discord line shows the exit).
2. **Benchmark: the just-closed session's equity comes from the `15Min` history.** `benchmark._append_closed_session` appends the 16:00 ET bucket of `GET /v2/account/portfolio/history?period=1D&timeframe=15Min` when its session is newer than the 1D series' last date and the point sits at/after the close; any failure or a mid-session point leaves the series unchanged. `benchmark.py`.
3. **Not shipped — ATR-scaled floor on analyst ADJUST raises** (the parked watch item from Decisions 057/058). Tested on every filled analyst ADJUST stop since May 12 and rejected; see Evidence 2.

Item 1 is the first change to re-entry behaviour since the 2026-06-22 hold; the operator authorised it on 2026-09-29 after the checkup below. Sentry thresholds, trail width (3.0×ATR), sizing, pyramiding and the analyst are untouched.

### September 29 checkup (2026-09-22 → 2026-09-28, 5 trading days)
Ops: 0 ERROR/CRITICAL/tracebacks in 30 days, all 8 scheduler jobs `completed`, public API healthy (note: port 8000 is not published on the host and the api image has no curl/wget — check via the tunnel or `/app/.venv/bin/python`), both images the Sep 22 build, AI cost $6.26 for September (Claude $5.83 / Gemini $0.43), disk 61% (build cache 7.1 GB + 4 dangling volumes, still pending the operator). Equity $111,689; 8 overlay positions + SPY core (34%), every position GTC stop-covered, cash 5.7%.

Decision 058 verified live: the ADJUST live-price floor fired twice on Sep 28 (Sunday's JPM stop $343 vs live $340.68 / $336.61 — kept $333.15; a third JPM whipsaw avoided); "Days held" real (CRWD 24 d, FCX 11 d, ANET 6 d); cash reserve 2.6% → 5.7%. **Fix 5 (SIP bars) did not close the benchmark lag**: `benchmark_metrics.json` computed Sep 28 20:30 UTC still ended Sep 25. Root cause: Alpaca stamps a session's 1D equity point at 20:00 ET = 00:00 UTC next day, so at 20:30 UTC the just-closed session has no 1D point; the SPY SIP bar was there. The `15Min` series had the 16:00 ET close ($111,611.28 vs the later 1D point $111,597.83 — after-hours drift, 0.01%). → item 2.

Performance (`compute_benchmark(persist=False)`, windows end Sep 28; SPY = split-adjusted price return, which is the right comparison for a dividend-less paper account — a real account would owe SPY ≈ 0.25 pp/quarter more):

| Window | Strategy | SPY | Beta | Alpha/yr | Sharpe (S / SPY) | Up / down capture | Max DD (S / SPY) |
|---|---|---|---|---|---|---|---|
| Clean since 2026-07-08 (57 td) | **+3.18%** | +2.71% | 0.64 | +6.5% | 1.22 / 1.09 | 0.70 / 0.61 | −4.64% / −3.38% |
| Since 2026-08-01 (39 td) | +1.19% | +1.05% | 0.77 | +2.8% | 0.70 / 0.71 | 0.77 / 0.72 | −4.64% / −3.06% |
| Since the Aug 12 peak (32 td) | −2.55% | **−0.89%** | 0.74 | −14.9% | −1.75 / −0.66 | 0.62 / 0.85 | −4.64% / −3.06% |
| Since Decision 057 (Sep 2, 17 td) | **+1.15%** | +0.06% | 0.81 | +16.3% | 1.56 / 0.13 | 0.83 / 0.61 | −2.32% / −2.47% |
| Since Decision 046 (May 12, 95 td) | **+10.30%** | +3.72% | 0.84 | +19.9% | 1.23 / 0.83 | 1.13 / 0.90 | −8.15% / −4.49% |
| Since inception (Mar 30, 125 td) | +11.64% | **+21.15%** | 0.61 | +0.2% | 1.18 / 3.02 | 0.74 / 0.82 | −8.15% / −4.49% |

Month by month (strategy / SPY): May +4.95 / +5.26, Jun +2.08 / −1.03, Jul −0.47 / +0.03, Aug +3.54 / +2.68, Sep (→ 28) −0.69 / +0.06. Reading: the past three months are a tie with SPY in a flat market; the inception gap is April (+2.1% vs +10.5%, the debugging period); the lag since the Aug 12 peak is churn — since Aug 13, 37 overlay exits netted +$660 realised (sentry aborts −$2,062 / broker stops +$1,752 / TP1 & market +$969) while **20 of the 37 were re-bought within 7 days at a higher price, a re-entry gap of $1,915 ≈ 1.7% of equity = the whole lag**; up-capture 0.62 / down-capture 0.85 in that window is the whipsaw signature. Operator decision the same day: keep the bot in paper, do not fund it, ship the data-backed churn fix, start a new clean window on the deploy date, write the go/stop rule (todo Phase 1.36).

### Evidence 1 — the override rule (item 1)
Every overlay exit since 2026-07-08 that was re-bought within 72 h (the population the override governs — before Decision 056 a stop-out had no cooldown, so early re-entries then were the same behaviour), with the re-entered shares' realised + open P&L (Alpaca fills, FIFO; n = 23, total +$1,483 of which CRWD Sep 3 alone is +$1,946):

| Rule for "recovered" | Allowed | P&L of allowed | Blocked | P&L of blocked |
|---|---|---|---|---|
| Current: ≥ 1% above the thesis stop (≈ everything) | 23 | +$1,483 | 0 | — |
| ≥ the exit price | 19 | +$1,595 | 4 | −$112 |
| **≥ exit × 1.01 (shipped)** | **13** | **+$2,250** | **10** | **−$767** |
| ≥ exit × 1.02 | 4 | +$198 | 19 | +$1,285 (blocks CRWD) |
| ≤ the exit price (buy lower only) | 4 | −$112 | 19 | +$1,595 |

The 1% rule blocks exactly the "nothing has changed" re-buys (URI +0.7%, HCA +0.3%, DVN +0.5%, CRWD −0.1%, ANET +0.2%, EQIX +0.1%, JPM +0.8%, …), every one a loser, and keeps every winner. Caveats stated plainly: n = 23, one trade dominates the allowed set, and a blocked re-entry could still have happened after the 72 h expiry at that day's price — the table assumes it does not. The threshold reuses the 1% the policy already used against the stop; only the anchor moves.

### Evidence 2 — the ATR floor (item 3, rejected)
All 35 filled analyst ADJUST stops since May 12 (origin matched to the thesis archive's `stop_loss_price` with `review_action = ADJUST`), ATR multiple measured from Friday's close and 14-day Wilder ATR at placement, outcome = what the position would have done instead over the next 5 / 10 trading days:

| Alternative to the analyst's level | k = 1.0 | k = 1.5 | k = 2.0 |
|---|---|---|---|
| Keep the previous analyst level (10 td) | −$2,762 (14 fills) | −$2,495 (29) | −$2,742 (34) |
| Clamp the raise to `close − k×ATR` (5 td / 10 td) | +$207 / −$211 | +$115 / −$1,814 | −$708 / −$3,586 |

Placed levels (88 held-position ADJUSTs): < 1×ATR 27 placed, 70% hit within 5 td; 1–1.5× 44 placed, 36%; 1.5–2× 16 placed, 38%. The tight levels are hit often and the price is back 2% above the level within 10 days in 10 of 14 (< 1×) and 11 of 15 (1–1.5×) cases — but the stocks usually fell through the wider level first, so every wider alternative exits lower. Holding with no stop at all would have been +$2.1k at k = 1.5 — not a policy. The tight exit was mildly protective; the loss was the flat re-buy that followed (Evidence 1). Watch item closed as tested-and-rejected; the analyst's ADJUST levels keep applying under the Decision 058 live-price floor only.

### Relationship to the strategy hold
The hold's trigger (a real SPY drawdown) has still not fired (max SPY DD −3.4% in the clean window). Item 1 is nonetheless a deliberate re-entry-policy change, taken because the same mechanism appeared in four consecutive checkups with per-trade evidence, and the fix was tested on those trades before shipping. Everything else the hold froze stays frozen. The operator's go/stop rule for funding is recorded in todo Phase 1.36.

### Tests, docs, deploy
578 tests green (17 new: `TestCooldownOverrideExitPrice` in `test_bugfix_regressions.py` — record shapes, the flat-rebuy refusal, the 1% boundary, the pre-059 fallback, the stop-out scan's fill price, an end-to-end `_handle_bullish_entry` block and the abort handler's mark; `TestAppendClosedSession` in `test_benchmark.py` — append, mid-session skip, no-duplicate, failure paths, DST-safe close check and an end-to-end `window_end`). Touched files ruff-clean. Docs: features, risk_management (parameter table), both architectures, deployment, insights, CLAUDE.md, todo Phase 1.36. Deploy record in todo Phase 1.36.

## Decision 058: ADJUST live-price floor, in-run cash refresh, real days-held, Discord retry, SIP benchmark bars (September 22 sweep)
**Date**: 2026-09-22
**Decision**: five independent correctness fixes surfaced by the Sep 8 → Sep 21 sweep. None changes strategy selection, sizing curves, sentry sensitivity, trail width or cooldown policy — the 2026-06-22 hold stands.
1. **ADJUST live-price floor** — Section 4a measures the analyst's new stop against the position's live mark (`pricing.adjust_stop_too_tight`, same 1.5% floor as Decision 055). A raise at/above the live price or inside the floor is *not* applied while an existing stop protects the position (WARNING + keep). With no stop on the book the level is placed anyway — unprotected is worse than tight. Missing live price → unchanged behaviour (fails open).
2. **In-run cash refresh** — Section 2 re-reads the account after every executed entry, so later tickers in the same run are sized against post-fill cash (mirrors what `resubmit_expired_brackets` already did).
3. **Real "Days held"** — the weekly review derives it from the trade log (`trade_state.position_opened_at`, the same opening-BUY lookup the Decision 056 guard uses) instead of a fallback chain that always produced 0.
4. **Discord retry** — webhook POSTs retry transport errors, 429 and 5xx twice (1 s, 2 s backoff); other 4xx are ours and are logged once.
5. **SIP benchmark bars** — `benchmark._spy_close_series` fetches SPY with `feed="sip"`; the native provider ends a SIP query ≥16 min in the past (the free plan refuses ranges reaching into the last 15 minutes), so the 20:30 UTC daily summary includes the session that just closed.

### September 22 sweep (2026-09-08 → 2026-09-21, 10 trading days)
Ops: 0 ERROR/CRITICAL/tracebacks in 3,460 log lines, all 8 scheduler jobs completed, public API healthy, both images current with the Sep 2 build (`1055865` is docs-only since), AI cost $4.61 (Claude $4.35 / Gemini $0.26; $7.80/30 d), 536 tests green. Equity $112,104; 9 overlay positions + SPY core (34%), every position covered by a GTC stop-limit with matching qty; cash 2.6% (see Finding 2). Noise only: 8 FRED 502s all retried, one Discord 503 (Finding 4), crawler 404s on the bare domain. Disk 43% → 60% — a 6.8 GB Docker build cache from a resevolve rebuild (~Sep 18) plus 3 orphaned PG 15 volumes (332 MB); not cleaned in this pass (operator's call, pattern in Decision 057 §4).

Performance (`compute_benchmark(persist=False)`, windows end Sep 21):

| Window | Strategy | SPY | Beta | Alpha/yr | Sharpe (S / SPY) | Up / down capture | Max DD (S / SPY) |
|---|---|---|---|---|---|---|---|
| Clean window since 2026-07-08 (52 td) | +3.61% | **+3.79%** | 0.68 | +5.3% | 1.44 / 1.61 | 0.81 / 0.76 | −4.64% / −3.36% |
| Since last checkup 2026-09-04 (10 td) | **+0.66%** | +0.43% | 0.90 | +6.8% | 1.34 / 0.91 | 0.90 / 0.82 | −1.91% / −2.09% |
| Since the equity peak 2026-08-12 (27 td) | −2.14% | **+0.13%** | 0.83 | −20.9% | −1.59 / 0.16 | 0.70 / 1.01 | −4.64% / −3.06% |
| Since Decision 057 deploy 2026-09-02 (12 td) | **+1.57%** | +1.10% | 0.96 | +10.9% | 2.52 / 1.86 | 0.99 / 0.85 | −2.32% / −2.47% |

The two-week window beat SPY; the Aug–Sep churn lag (~2.3 pp off the Aug 12 peak) has not closed and the clean window is marginally behind for the first time. The Sep 8–16 SPY dip was −2.1% and fully recovered by Sep 21 — **not** the genuine drawdown the hold decision waits for.

**Dip churn**: 9 exits (DXCM price-check −5.7%; GE catastrophic −6.1%; GS and FCX news-confirmed; FCX, EQIX, ANET, JPM, DVN broker stops) and 8 re-entries in 9 sessions. FIFO-realised on the exits −$1,934: FCX −$982 over two round trips (a +4.5% `strong_up` chase to $76.22 on Sep 9, −7% the next day; re-bought $71.98, sold $68.98, re-bought $69.67), JPM −$334 (stopped $343.50, re-bought $346.38 next day), GS −$308, EQIX −$241 (re-bought +2.4% higher), DXCM −$240 (re-bought +5% higher two weeks later on a fresh thesis), GE −$163, ANET −$104 (Finding 1), DVN −$43. CRWD TP1 +$481 and a pyramid add; now +15%. Cooldown overrides fired at 24.7 h / 27.6 h / 29.2 h — Decision 057 watch item 2 re-confirmed.

**Decision 057 in its first dip (tiny sample)**: the noise branch delayed three exits (DXCM, GE, GS) that all went on to breach 5% — ≈$280 worse than the old code — against the ≈$340 ANET whipsaw it avoided Sep 2–4. Net a wash; the mechanism works as designed, and a trending-down tape is where it costs.

### Finding 1 — the ADJUST stop is applied blind at Monday 14:15 UTC (third occurrence)
The Sep 13 review raised ANET's stop $181 → $191 — 4.37% / **1.29×ATR** below the $199.74 Friday close. The 14:15 UTC Monday run (`ADJUST: Replacing stop for ANET to $191.00`) placed it while ANET traded $189.82 (open, after a −5% gap); the stop-limit filled the same second at $189.91 (−$104 realised). ANET closed $187.83 that day and $205.66 on Sep 21; it was re-bought at $202.36 with 22 shares instead of 36. The same review's DVN raise ($47.75, 2.17×ATR) tagged a week later at breakeven. On Sep 21 the book carried analyst stops at 0.82×ATR (DASH, 2.9% below), 1.23× (FCX) and 1.30× (JPM) against a 3.0×ATR system trail. Section 4a had no check of the new level against anything: the off-hours guard deliberately defers Sunday's raise to Monday, and Monday applied it without looking at the price.

A stop placed at or inside noise distance of the live price is a market exit, not a stop — that is a defect, not a strategy choice, so the flat Decision 055 floor is extended to ADJUST raises measured from the live mark. The ATR-scaled floor (Decision 057 watch item 1) would also have caught DASH at 0.82×ATR; it overrides the analyst's explicit "lock gains" intent and stays parked under the hold.

| Situation at the market-open ADJUST run | Before | After (Decision 058) |
|---|---|---|
| Raise at/above the live price, existing stop on the book | cancel + place → instant fill | WARNING, existing stop kept |
| Raise < 1.5% below the live price, existing stop | cancel + place | WARNING, existing stop kept |
| Raise too tight, **no** stop on the book | place | place anyway (+ WARNING) |
| Raise ≥ 1.5% below the live price | cancel + place | cancel + place |
| No usable `current_price` on the position | cancel + place | cancel + place |

### Finding 2 — cash goes stale within a run
`execute_trades` read cash once (line ~415) and passed that value to every `_handle_bullish_entry`; `open_buy_commitment` nets only *open* orders. On Sep 21: cash $10,042 before the 14:15 run → ANET's bracket ($4,452) filled instantly and was no longer open → DXCM was sized against $10,042: "Position reduced to 50.0 shares (cash reserve)" allowed $4,454 against a 5% reserve of $5,605 that only had $1,138 of headroom left → 30 filled, cash $2,924 = **2.6%** (1.0% had tranche 2 filled). In a margin account that is the path back to the negative-cash incident Decision 035 fixed. The bullish-entry loop now re-reads the account after each executed trade, as the resubmission loop already did.

### Finding 3 — "Days held: 0" on every review since inception
`review_position` read `position.get("entry_date", existing_thesis.get("generated_at"))`; Alpaca positions have no `entry_date` and per-ticker theses no `generated_at` (only the document does), so every review prompt said "Days held: 0" and every log line `(…, 0d held)`. The trade log knows: `position_opened_at(ticker)` returns the most recent non-pyramid BUY (weekly_thesis / bracket_resubmission), which `position_opened_after` (Decision 056) now shares. The log records submissions, so an expired-then-resubmitted bracket resolves to the resubmission that filled — accurate to the session. `_days_held_from` is pure, clamps future dates to 0 and fails open to 0.

### Finding 4 — Discord was a single POST
`send_discord` posted once with a 5 s timeout; a 503 at 14:15:43 on Sep 17 lost that job's notification. Transport errors, 429 and 5xx now retry twice (`_RETRY_DELAYS_S = (1.0, 2.0)`); the final failure is logged as before and never raises into the job.

### Finding 5 — the persisted benchmark always ended one session early
`benchmark_metrics.json` computed 2026-09-21 20:30 UTC had `window_end = 2026-09-18`. The provider requested SPY daily bars from the configured IEX feed with a date-only `end`; verified on the server: `end=<date>` is inclusive and IEX does return the bar next morning, so the daily bar simply is not published by 20:30 UTC. SIP has it minutes after the close, and the paper key serves SIP history, but a SIP query whose range reaches into the last 15 minutes fails with "subscription does not permit querying recent SIP data" — so `native.get_ohlcv(..., feed="sip")` ends the range at now − 16 min (RFC-3339). Only the benchmark asks for SIP; indicator/ATR bars stay on the configured feed. SIP closes differ from IEX by cents (773.50 vs 773.52 on Sep 21) — the consolidated print is the better reference. **Verify at the Sep 22 20:30 UTC summary: `window_end` should read 2026-09-22.**

### Withdrawn — "ghost" sentry checks after a mid-week exit are the re-entry gate
The sweep initially flagged Gemini re-evaluating GE for four days after it was sold ("Catastrophic price-based ABORT for GE" ×10, executor "no position to close"). Reading the code: for a review thesis with no position the price check falls back to `target_entry_price`, and that ABORT is exactly what stops Section 2 from re-buying under the stale review thesis — with a synthetic CONTINUE, GE at −6% would have met the cooldown-override test ($290 stop + 1%) and been re-bought the next day. Left unchanged.

### Tests, docs, deploy
26 new regression tests (`TestAdjustLivePriceFloor`, `TestReviewDaysHeld`, `TestBenchmarkSpySipFeed` in `test_bugfix_regressions.py`; `TestAdjustLivePriceFloorEndToEnd` — five `execute_trades` drives incl. gap-through, inside-floor, healthy raise, no-stop and missing-price — and `TestEntryCashRefresh` in `test_executor.py`; `TestSendDiscordRetry` in `test_notifier.py`). **562 tests green**; touched files ruff-clean (four pre-existing findings in the test modules untouched). Docs: features, risk_management, both architectures, agent_instructions, deployment, CLAUDE.md, todo Phase 1.35. Deployed 2026-09-22 (both images) — see todo Phase 1.35 for the deploy record.

### Watch items carried forward (todo Phase 1.35)
1. ATR-scaled ADJUST floor (strategy) — parked; DASH 0.82×, FCX 1.23×, JPM 1.30× analyst stops live on Sep 21. → **Tested and rejected in Decision 059.**
2. Cooldown override still effectively 24–29 h — parked (Decision 057 item 2). → **Fixed in Decision 059** (recovery measured against the exit price).
3. titanserver disk 60%: `docker builder prune -a -f` (6.8 GB) + the 3 dangling PG 15 volumes (332 MB) pending the operator's go; never `docker image prune -a` here.
4. `benchmark_metrics.json` 90-day window carries the CRWD split artifact until ~mid-October; read `--since 2026-07-08`.
5. Untracked `data/historical_long/` on the server (2.5 MB, Jul 2 backtest download) — harmless; gitignore or delete.

## Decision 057: Sentry price-override corroboration excludes Gemini's `price_concern` flag (September checkup)
**Date**: 2026-09-02
**Decision**: A moderate (3–5%) adverse move is "confirmed" into an ABORT only by Gemini's `conflicting_headlines` (non-empty) or `market_concern`. Its `price_concern` flag no longer counts. This restores the behaviour Decision 045 specified — "3–5% adverse + Gemini clean → warn, do NOT override CONTINUE" — which had been effectively dead code since it shipped. Strategy selection, sizing, stops and cooldowns untouched. **Deployed 2026-09-02** (operator decision taken the same morning — see "Relationship to the strategy hold" below).

### September checkup (2026-08-18 → 2026-09-01, 10 trading days)
Ops: 0 ERROR/CRITICAL/tracebacks in 3,548 log lines, all 8 scheduler jobs completed on time, public API healthy, both images current with `67281b3`, AI cost $3.24 (Claude $2.99 / Gemini $0.25), 7 open GTC stops covering all 7 overlay positions (SPY core ~34%, cash 17% after the Sep 1 stop-outs). Only noise: transient FRED 502s, every one retried successfully.

Performance (`compute_benchmark(persist=False)`):

| Window | Strategy | SPY | Beta | Alpha/yr | Sharpe (S / SPY) | Up / down capture | Max DD (S / SPY) |
|---|---|---|---|---|---|---|---|
| Clean window since 2026-07-08 (39 td) | **+2.58%** | +2.19% | 0.60 | +8.4% | 1.39 / 1.27 | 0.82 / 0.73 | −3.11% / −3.36% |
| Since last checkup 2026-08-18 (10 td) | −0.90% | −0.75% | 0.93 | −4.8% | −1.81 / −2.41 | 1.16 / 1.17 | −2.52% / −1.24% |
| Since the equity peak 2026-08-12 (14 td) | −3.11% | −1.41% | 0.60 | −41% | −4.95 / −3.19 | 0.51 / 1.16 | −3.11% / −2.08% |

Still adding value on the clean window, but the edge narrowed from the Aug 18 reading (+4.29% vs +4.16%, Sharpe 3.18 vs 3.06), and the first pullback since the hold decision has the wrong shape: down-capture 1.16 over the 14 sessions off the peak. Short-window betas and alphas are noise, but the *mechanism* is visible in the fills — 11 exits (7 broker stop-outs, 3 sentry aborts, 1 dust) and 9 re-entries in 10 sessions on a −1.4% SPY tape. Two of the three churn paths are documented below; the third (the sentry override) is the defect this decision fixes.

### The defect
The sentry prompt shows Gemini the price-action alert that put us in the 3–5% branch, then asks it to set `price_concern: true if an adverse price move is a factor in your decision`. Gemini, honestly, says yes — it looked at the alert — while its `signal` says CONTINUE and its reasoning says "within the expected volatility range". `check_stock()` then counted that flag as "Gemini flagged a news concern" and forced ABORT. The price move confirmed itself.

Every sentry decision logged since Decision 045 shipped (2026-05-12 → 2026-09-01; 2,398 records):

| Outcome of a 3–5% adverse move where Gemini said CONTINUE | Count |
|---|---|
| Forced ABORT, "confirmed" by `price_concern` alone (no headlines, no market concern) | **36** |
| Forced ABORT, confirmed by conflicting headlines | 2 |
| Forced ABORT, confirmed by market concern | 1 |
| Left as CONTINUE (the designed noise branch) | 9 |

In all 36 cases Gemini's own reasoning called the move normal volatility / no breach. The three in the checkup window: GE 08-20 (−4.8%, 3 sh sold $344.25), URI 08-25 (−3.5%, 8 sh sold $1,056.41, −$309 realised), EQIX 08-31 (−3.1%, 10 sh sold $1,031.74, −$321 realised, then re-bought 25 h later at $1,032.65 through the cooldown override — a pure round-trip). The July checkup had already measured this pattern as the month's dominant real drag (~$1.5–2k; "7 of 10 aborts overrode Gemini's own normal-volatility read") but framed it as a threshold-tuning question parked behind the strategy hold. It isn't a threshold: the graduated policy never ran as designed. The 3-of-39 cases with a real corroborator would still ABORT after this fix.

### Fix
`daily_sentry.check_stock()`: `has_news_concern = conflicting_headlines or market_concern`. Everything else is unchanged — ≥5% still hard-ABORTs regardless of Gemini; both override branches still stamp `price_concern = True` so the executor market-sells (urgent) rather than limit-sells; the noise branch still records `price_concern = True` for operator visibility; the news-only-ABORT downgrade (Decision 034) is untouched; `price_check.py` (no LLM, ≥5% only) is unaffected. Two regression tests in `TestCheckStock` (`price_concern`-only stays CONTINUE with the "no news corroboration" reasoning; `market_concern` still confirms and keeps `price_concern = True` for the executor). **536 tests green**; touched files ruff-clean apart from two pre-existing E402s in the test module.

### Relationship to the strategy hold (2026-06-22)
This changes live abort frequency in the 3–5% band — the sentry sensitivity the hold decision froze. The checkup presented it as a defect fix with the deploy left to the operator, who chose to deploy the same morning (both images rebuilt, API restarted before the day's first job). Expected live effect: the 36-style aborts stop; a position down 3–5% with clean news rides to its broker-side stop (typically 5–7% below entry, or the analyst's ADJUST level) or to the ≥5% hard tier. In hindsight the checkup window's three price-only aborts split: URI exited ahead of a further −6% (right), GE roughly break-even (GE closed Sep 1 near the abort price), EQIX pure churn (re-bought at the abort price a day later). The July cluster (ANET/DXCM/DVN/URI) was mostly churn. Decision 045 chose stop-based exits over these; this decision makes that choice real.

### Also observed, not changed (watch items — todo Phase 1.34)
1. **Analyst ADJUST stops are noise-tight.** Measured against the Friday close and 14-day ATR at each review: Aug 30 set HCA $413 (0.49×ATR, 1.16% below close), FCX $73.60 (1.03×), DASH $228.50 (1.16×) — all three tagged at the Sep 1 open on a −0.7% SPY day. Aug 16 set JPM $354 (1.81×), ANET $184 (1.69×), EQIX $1,055 (2.14×), URI $1,094 (2.38×) — all four tagged Aug 19–20 on a −1.3% SPY move, then JPM/ANET/EQIX were re-bought higher Aug 24–25 (ANET: out $183.84, closed $202 six sessions later). The system's own trail is 3.0×ATR; the Decision 055 floor (1.5%, flat) covers entries only — HCA's raise would have failed even that. Candidate: an ATR-scaled floor on ADJUST raises (keep the existing stop when the analyst's is tighter than ~1.5×ATR). It overrides the analyst's explicit "lock gains" intent, so it is a strategy-design choice → parked under the hold.
2. **The cooldown override is nearly always satisfied.** "Price recovered" means ≥1% above the *thesis stop* — which any 3–5% abort trivially meets — so the 72 h cooldown is effectively the 24 h `COOLDOWN_OVERRIDE_MIN_HOURS` (EQIX above; 15 override log lines in 16 days). Candidate: measure recovery against the abort price instead. Parked.
3. **Stale docs fixed in this pass**: `docs/agent_instructions.md`, `TitanTrade/docs/agent_instructions.md` and `TitanTrade/docs/architecture.md` still described the pre-045 "3% hard override regardless of Gemini" — four months stale, survived the Decision 056 accuracy pass.
4. **Housekeeping (titanserver)**: disk was 78% (8.1 GB free) with 14 GB of unused docker images (98% reclaimable, other projects' included) and 3 GB build cache. The three unreferenced images (base images `nginx:alpine`, `node:22-alpine`, `python:3.12-slim`) were removed by name at deploy — only ~130 MB of real unique size; docker's "reclaimable" figure double-counts shared layers. `docker image prune -a` must not be used on this host: the CLI image is unreferenced by any container by design and would be deleted. The operator then cleared the build cache (~9.3 GB) and had the 37 anonymous orphaned volumes removed (3.6 GB; all Postgres 15 data dirs or a resevolve pgadmin volume — resevolve leftovers accumulating at ~137 MB/week). Disk 79% → 43%.
5. **Benchmark caveat still applies**: the persisted 90-day `benchmark_metrics.json` (Jun 1 → Aug 31) carries the Jul 2–7 CRWD split artifact until ~mid-October — its −8.15% max DD, 27% vol and 1.11 down-capture are polluted; read `--since 2026-07-08`.

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
