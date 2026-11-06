# TitanTrade TODO

## Open items — the index (2026-11-03, Decision 088)
What is actually open, by where it waits; the phases below are the record and keep their boxes. Newest phase first.
- **The operator**: nothing pending from research (the momentum sleeve outside the switches read out 2026-11-05 → Decision 104 / 2.44: not adopted, V2 the knob if ever wanted; a fast de-risk layer tested 2026-11-06 → Decision 105 / 2.45: speed worth nothing, the sensitive trigger a decade artefact — nothing changes; the hourly gap-and-coverage safety net of 103 is their call); the go-live checklist (2.0) stays theirs — **they raised going live 2026-11-05**; the agreed order: the paper drill (2.43, done) → a clean checkup → live at the floor size → scale after the first selloff; ~~a European slice~~ priced and dropped by the operator 2026-11-05 (101 addendum).
- **Verify at the next checkup**: **Decision 103's list (2.43 — the 20:30 UTC summary's four positions, the fill ledger's XLE row, the 09:35 ET job on XLE, the benchmark window from 2026-11-05 16:13 UTC)**; seen in the drill 2026-11-05 15:29 UTC and closed — the BTC BUY before the SPMO BUY, the leg at 5.0 %, the momentum target 56 %, a 9.5 % slot, the window re-stamped, cash 2.3 % with no order outside a band (2.37 / 2.42 / 2.30); the pre-drill list, kept for the record: Decision 102 deployed 2026-11-05 10:23 UTC (the leg ahead of SPMO — the bitcoin BUY before any SPMO BUY at the first legacy exit, the leg near 5 %); Decision 097 deployed 2026-11-04 15:31 UTC (its first run 20:30 UTC bought 0.000164 BTC — see 2.41) — the "BTC/USD target 5.0 %" line, one BUY of ≈ 0.06 BTC (trigger `core_rebalance`), BTCUSD in the summary's positions, no orphan-close / gap-check / stop-coverage line naming it, `window_started_at` re-stamped (design 097), the momentum target 56 %, a 9.5 % slot (2.37); the 2 % reserve live since 2026-11-03 12:36 UTC (2.30, Decision 090) — the momentum target 59 % in the "Core target" log line, no order outside a band, no "insufficient buying power".
- **Live time**: the checkup ≈ 2026-11-12, written in the order of `docs/how_to_read_a_checkup.md` (Phases 2.26, 2.23) — verify: ~~the first ETF entry~~ (seen in the drill: XLE, 2.43) and its fill-ledger row, the benchmark wording at 20 trading days (2.9), SPMO rebalanced only outside its 5 % band and no orphan-close attempt on it (2.7), ~~a settled-close exit seen live (2.2)~~ (seen in the drill: JPM, DXCM, URI), no "SUSPECT ACCOUNT VALUE" / "target not confirmed" line without a real glitch (Decision 084), ~~DXCM's clock against its stop's expiry~~ (moot — DXCM left in the drill); the go/stop rule needs a ≥ 10 % SPY drawdown (2.0).
- **The operator**: the go-live checklist (2.0 — fund ≥ $25k, W-8BEN, enrol the cash programme and leave `cash_ticker` off (Decision 087), the healthchecks URL (2.10), the tax line); ~~the free Tiingo and Alpha Vantage keys~~ (received 2026-11-04); the WARNING → INFO cosmetic done 2026-11-03 and deployed 2026-11-04; rotation closed (Decision 091).
- **Housekeeping at the next checkup**: `external/sec_facts/` and `alpaca_hist/quality/` archived on titanserver if not yet (2.16), plus `external/tiingo/`, `external/alphavantage/`, `external/fed/`, `external/bls/`, `etfparams_G.json`, `momweight.json` (handover §7); `git pull --ff-only` on the server (done 2026-11-05 after Decision 103 — docs and the drill script, nothing to deploy); titanserver disk and build cache (1.36).
- **Research**: the ideas block (handover §8) is running, one idea at a time on the operator's go — idea 1, the macro gate on history → Decision 094 (2.34: the gate stays; the gate-7 doc lines amended to the code), idea 2 the crypto sleeve → Decisions 095 / 096 (2.35 / 2.36: the full programme on 1,150 coins — nothing beats holding bitcoin, the weight a loss budget; a bet, recommended against — **taken by the operator at 5 % → Decision 097 built, 2.37, deploy on their go**), idea 3 selling volatility → Decision 098 (2.38: no sleeve, the option family closed), idea 4 positioning / leverage → Decision 099 (2.39: closed), idea 5 execution timing → Decision 100 (2.40: nothing changes); **the §8 ideas block is complete**; E6 → Decision 101 (2.41: no second book); **the research roadmap is empty** — what is open is the operator's: ~~the bitcoin leg's queue order~~ (Decision 102, verified in the drill 103), ~~a European slice~~ (dropped); the B track is complete (B10 → Decision 093, B11 → 092); B11's H3 landed the same afternoon (no change); E6 at the back (roadmap); the 2.1 "next search" boxes predate the sector universe (Decision 070) and Track D's closed doors.
- **Phases 1.37 and earlier** (the LLM-era book) keep their open boxes as history; the conversion (Decisions 061–063) superseded them.

## Phase 2.45: A fast de-risk layer — "within a minute" tested on the 15-minute bars, nothing changes (2026-11-06) — Decision 105
Operator, the morning after SPY's −4.4 % session: "wouldn't we achieve better results if we just saw the market falling within a minute?" → the descriptive count said no → "Yes, run it".
- [x] `scripts/param_search/intraday.py` pre-registered (`036b26e`; the part-2 addendum `368f3ab` before its run) and run: the core book 0.4 SPY / 0.6 SPMO from the 15-minute bars 2017 →, the live switches, a fast halving at −2 … −5 % × four restores, the watcher alone by depth × hold, the live shock rule read intraday; costs, placebo, luck meter, the big falls; part 2 the daily-close twin on the decade and the century.
- [x] On top of the rules: −2 % +0.4 (t 0.4, noise), −3 / −5 % 0.0, the shock rule read intraday −0.6 (fifteen intraday triggers, false alarms in 2022 / 2024 / 2025-03). Instead of the rules: −3 % / 20 alone +3.45 vs the live switches on the decade (t 1.9) — half the insurance dropped (+1.7), the rest a more sensitive trigger; its close-based twin +4.83 vs +4.73 (speed = 0); on the century −0.36 vs live (eras −1.6 −0.7 +1.0 0.0), DD −70 vs −59, every big bear deeper but 2020 (1973–74 −44 vs −27, 2008 −43 vs −34).
- [x] Rule fails (the century) → **nothing changes; the schedule stays at two runs a day**. Decision 105, roadmap C2 row, README row, handover §5. Open for the operator: the hourly gap-and-coverage safety net (103).

## Phase 2.44: The momentum sleeve outside the switches — read out, not adopted (2026-11-05) — Decision 104
Operator, after the drill's forced shock sold SPMO to 28 %: "back test check what would happen if we moved momentum to 60% at the expense of our protection". Momentum is already 60 % of the investable book (091's curve); the question is the switches on it.
- [x] `scripts/param_search/momexempt.py` pre-registered (`6deb951`) and run: V0 live, V1 momentum outside both switches, V2 outside the insurance only, V3 outside the shock only, V4 no switches; the block-shuffled placebo on the momentum leg; the luck meter on V1 − V0; the big falls.
- [x] Decade: V1 +3.46 vs the live +1.36 (+2.1, t 1.6, P(excess > 0) 99 % — real for the decade), DD −27.1 vs −20.0 (2020), Sharpe level. Century: V1 +3.68 vs +3.63 (+0.05, P 56 %, a coin flip), DD −74.2 vs −58.6, Sharpe 0.76 vs 0.86, the 1927–50 era +3.4 vs +4.6; 1929–32 / 1973–74 / 1987 / 2008 each 10–16 points deeper. Placebo: the switches' timing on momentum real on the century (+1.4, 12 DD points over random), worse than random on the decade. V2 (shock kept on momentum): +0.9 on the decade at −20.0, the century's return unchanged, DD −62.1.
- [x] Rule fails (the century's first half, first era and Sharpe) → **nothing changes; the protection stays on the momentum sleeve**; V2 recorded as the C1 knob. Decision 104, roadmap C1 row, README row, handover §5. Operator: "Keep it" — closed.

## Phase 2.43: The paper drill — every unexercised live path forced on the paper account, no bug, the transition over (2026-11-05) — Decision 103
Operator: "test everything we can so that we can speed this up", "its just a dev account … Run it as soon as you can". Run 15:27 – 15:33 UTC inside the api container, market open, the state backed up first.
- [x] `scripts/paper_drill.py` (`e5abc66`, committed before the run): status / renew / close / targets / entry / restamp — the package's own functions, every parameter edit restored in a `finally`.
- [x] renew: JPM's GTC stop cancelled → `ensure_stop_coverage` re-placed it at 297.37 / 294.40 gtc (the 90-day path).
- [x] close: JPM through `close_position_settled` — cancel, settle, market sell filled 57 @ 344.35.
- [x] targets (`tp_pct` 0.01 for one run, URI having slipped to +1.4 %): the bitcoin leg bought to 5.0 % **before** SPMO (102 verified), then DXCM (+11.5 %) and URI (+1.4 %) exited through the quote-confirmed target path (325 @ 87.01, 26 @ 1,080.82).
- [x] entry (`dip_pct` 0.04 for one plan): XLE NEW → SPY netted the slot (40 @ 746.82), SPMO to 56 %, the bracket 160 XLE filled @ 64.24 (9.5 %, all gates passed), the stop leg swapped for a GTC stop-limit 56.70 / 56.13 on fill, coverage placed 0; dip restored, plan refreshed (XLE held, 2 free slots).
- [x] restamp: `window_started_at` 2026-11-05T15:32:43 UTC (design 097). The book: bitcoin 5.0 %, SPMO 55.8 %, SPY 27.5 %, XLE 9.5 %, cash 2.3 %.
- [x] Findings: no bug; the trade log's `price` on market exits and core trades is the mark at order time, not the fill (0.02 … 0.09 %; the entry row and the fill ledger carry the real fill) — left as is; the transition squeeze of 102 is moot.
- [ ] **Verify** (20:30 UTC today, then the checkup ≈ 2026-11-12): the daily summary's four positions, the fill ledger's XLE row (64.24 vs the session close), the 09:35 ET job on XLE placing nothing, no orphan-close line on the core legs, the benchmark window from 16:13 UTC.
- [x] **The round trip (addendum, 16:11 – 16:13 UTC, `c162c0c`)**: `shock` with `shock_drop_pct` 0.02 for one plan → shock ON (12 sessions left), exposure ×0.5 → SPY sold 26 (27.5 → 9.6 %), SPMO sold 239 (55.8 → 28.0 %), the bitcoin leg and XLE untouched; threshold restored, plan refreshed (shock off) → `execute` → SPY bought 26, SPMO 240 → back on design (5.0 / 55.9 / 27.5 / 9.5, cash 2.1 %); cost ≈ $20 on $100k of turnover; the window re-stamped 16:13:01 UTC.
- [ ] Left to time: Alpaca's own 90-day cancellation, the insurance (data-driven), the T-bill leg (off), the selloff itself (A3).

## Phase 2.42: The bitcoin leg ahead of the momentum sleeve — built and tested, deploy pending (2026-11-05) — Decision 102
Operator: "Yes, move it" after the leg's first run bought $13 (no free cash: the legacy names hold 70 %, the SPY residual's target is 0, SPMO 28 points under target ran first). Nothing live until the deploy.
- [x] `executor.py`: the leg inserted right after SPY, before the momentum sleeve (after the T-bill leg when it sells first); `tests/test_crypto_leg.py::TestLegOrder` asserts SPY → BTC/USD (0.05, band 0.25, fractional) → SPMO (0.5586); the live-config test now asserts design 097 with the leg (it had been failing since the 097 config commit); 303 tests, lint clean.
- [x] Docs: Decision 102; CLAUDE.md, architecture (package), how_to_read_a_checkup, handover §2; the index.
- [x] **Deployed 2026-11-05 10:23 UTC** ("Deploy now"; `35de598`, both images, checks ok). Verify at the first run after a legacy exit: the bitcoin BUY before any SPMO BUY in the log, the leg near 5 % of equity.

## Phase 2.41: E6 — the European programme run, no second book; the research roadmap empty (2026-11-05) — Decision 101
Operator: "Start E6". Hypotheses F1–F6 and the drop rule committed before the run (`bca956e`, `europe.py`; one formatting fix after W1 and W2's F3 / F4 had printed); the French daily momentum sorts (Prior 250-20 — the 12-2 ones are monthly) and the `EUROPE` Tiingo list (ten country ETFs 1996 →, IEV / EZU / VGK / FEZ / EFA / IDMO / HEDJ) fetched into the library. Nothing live changed.
- [x] **F1**: Europe's market −4.1 pp/yr vs the US 1990 → (−8.7 / +4.8 / −7.7 by era; −3.2 in euros, +4.1 in 1999–2008). **F2**: BIG HiPRIOR +3.24 vs Europe, t 2.4, P(excess > 0) 99 % — the one solid number; IDMO vs VGK 2012 → +0.5.
- [x] **F3**: the live dip rule on the ten countries −0.07 vs the basket, the 36-cell grid 0 / 36 ≥ 0 in both halves → no European dip floor, E3 stays closed. **F4**: the switches −1.2 (French) / −1.5 (basket) pp/yr for a 20-point shallower fall, inside their placebo bands — a Sharpe, not a return.
- [x] **F5**: the European book +0.72 vs its market on W1 (t 0.03), +0.18 on W2, −3.4 vs the US market. **F6**: 70 / 30 Sharpe 0.80 → 0.85, worst year −14.8 → −12.1, give-back 1.2 pp/yr in both halves; the European book +0.6 over plain European exposure in the slot; active correlation 0.39. **The rule fails (a) and (b) → no second book**; roadmap E6 ✅ closed, E3 note; README rows; handover §8 item 6 ✅ — the research roadmap is empty.
- [x] **E6 dropped** (operator, 2026-11-05): the held international-momentum leg costs 0.1 … 0.5 pp/yr at every size on both windows for a slightly softer worst year — recommended against, declined (101 addendum).
- [ ] **The bitcoin leg's first run (2.37 addendum, 2026-11-04 20:30 UTC)**: the window re-stamped to design 097 and the leg bought **0.000164 BTC ($13)**, not ≈ 0.07 — no free cash: the three legacy names hold 70 % of equity, the SPY residual's target is 0 (nothing to sell), SPMO sits 28 points under its 56 % target and absorbs every dollar the legacy exits free before the leg's turn. The bet stays unfunded until January unless the leg is moved ahead of SPMO → **operator: "Yes, move it" → Decision 102 (2.42)**.

## Phase 2.40: Execution timing — roadmap C5 run, nothing changes; the ideas block complete (2026-11-04) — Decision 100
Operator: "Run idea 5" (against the recommendation to skip). Hypotheses X1–X4 and the drop rule committed before the run (`b414da5`, `exectiming.py`); 15-minute bars for 28 symbols fetched on titanserver with the project's keys (`fetch_15min.py`, ~20 min sequential — give it a worker pool next time) and carried over with the base64 trick (scp breaks on the server's login-shell output); 315 MB in `external/alpaca_15min/`, archived at the source. Nothing live changed.
- [x] **X1**: the 10:15 fill +8 bp over the close on the ETFs (−0.05 pp/yr), −8 bp on the names (+0.13); every band straddles zero. **X2**: the broker-side stop +3.45 % per event on the ETFs (written 0.5 … 1.5), +1.43 on the names; the whipsaw 1 of 48 / 2 of 45 (written 10 … 30 %). **X3**: the resting target −0.47 % per event on the ETFs, −1.72 on the names (written 0 … 1).
- [x] **X4**: the live mechanics vs the close-filled backtest −0.045 pp/yr on the ETFs (written ±0.2), +0.54 on the names (all first half, the band including zero); 10:15 vs 15:30 +0.02 on the ETFs with the halves of opposite sign → **the rule fails, nothing changes**; the C5 row closed; README rows; handover §8 item 5 ✅, the block complete.

## Phase 2.39: Positioning and leverage as a regime input — roadmap C2 run, closed (2026-11-04) — Decision 099
Hypotheses R1–R3 and Decision 077's drop rule committed before the run (`46d9434`, `positioning.py`); the data was in the library (CFTC zips 1986 →, FINRA margin 1997 →); NAAIM / AAII out (no feed / walled). Nothing live changed.
- [x] **R1 / R2**: on the century book 1989 → the gates (SMA AND state) read +1.6 … +2.2 vs the incumbent's +1.82 with a 5 … 14-point deeper drawdown (2008's de-risking removed) and sit inside or below their placebo bands; the warnings (SMA OR state) cost 0.6 … 1.6 pp/yr inside their bands; the second half never beats the incumbent; margin shrinking as a warning equals its placebo to the decimal.
- [x] **R3**: the decade's gates +2.5 … +3.0 vs +1.36 = the insurance switched off (placebo medians the same); the warnings −2.3 … +1.2. **The rule fails for all eight** → no third signal; the C2 rows closed; README row; handover §8 item 4 ✅.

## Phase 2.38: Selling volatility as a sleeve — roadmap C3 run, no sleeve (2026-11-04) — Decision 098
Hypotheses V1–V3 and the drop rule committed before the run (`26520e4`, `volsell.py`); VPD / VPN joined the Cboe set, SVXY / XIV / VXX the Tiingo set. Nothing live changed.
- [x] **V1**: VPD −0.6 pp/yr vs the market over 19 years at 1.2× its volatility (written 0.6 … 1.0), DD −62 vs −53, t 0.1; VPN −2.8; the XIV → SVXY splice −11 %/yr at 3.2× with a −93 % day; VXX −68 %/yr.
- [x] **V2**: a 10 % sleeve moves the book +0.44 (19y, noise: t −0.1) / −0.22 (decade), Sharpe ±0.03, DD ±0.8; the product −0.8 pp/yr and 9 points of drawdown on the decade; the premium's excess is uncorrelated with the dip sleeve's (0.00, written +0.2 … +0.5). **V3**: VPD −46 % in 2008, −47 % in 2020 (written −20 … −40), −16 % in 2018-02; the product −96 % in two weeks.
- [x] **The rule**: passes on the ETP window only, fails on 19y and the decade → **no sleeve**; roadmap row closed; README rows; handover §8 item 3 ✅.

## Phase 2.37: The bitcoin leg — 5 % held in BTC/USD, built and tested, deploy pending (2026-11-04) — Decision 097
Operator: "okay im definitely taking the bet" → the decade table and the forecasts → "alright lets go 5%"; stops and the stock protections asked for and declined on the evidence (the trend family placebo-level, a 12 % stop fires 4× a year, vol scaling cuts nothing; 0.7 points of book drawdown to protect). Nothing live until the deploy.
- [x] **Code**: `crypto_ticker` / `crypto_weight` / `crypto_band_pct` in `TradingSettings` and `MECHANICAL_FIELDS`; `overlay_slot_pct` × (1 − weight); `core_tickers` with both symbol forms and `position_symbol`; `manage_core_position(band_pct, fractional)` with a $10 dust floor; `crypto_target_pct` outside the exposure scale, the sleeves' targets × (1 − weight); the executor runs the leg last with its own band; `_core_legs` for the gates; crypto market orders gtc; the crypto quote endpoint; the plan's `crypto_leg` and the summary line.
- [x] **Tests**: `tests/test_crypto_leg.py` (7) — 302 tests, lint clean. **Config**: `watchlist.json` design 097, BTC/USD, 0.05, 0.25 (ships with the commit; live only when deployed).
- [x] **Docs**: Decision 097; features, risk_management, architecture (package), data_schemas, how_to_read_a_checkup, CLAUDE.md, handover §0 / §2 / §7; roadmap C3; the verify list in the index.
- [x] **Deployed 2026-11-04 15:31 UTC** ("Deploy now"; `83ed062`, both images, health ok, import check reads 097 / BTC/USD / 0.05 / 0.25 / slot 9.5 %). The first run under 097 is the 15:30 ET execute the same day; verify its three core trades and the window re-stamp at the next checkup.

## Phase 2.36: The crypto programme — every coin, every approach, the weight as a curve (2026-11-04) — Decision 096
Operator: "we are talking about adding a whole new instrument … you look at just one coin … why just 2 %? … we can do stocks on Alpaca and crypto somewhere else." Screens, universe rules, placebos and hypotheses P1–P7 committed before the run (`650c1cd`, `cryptobook.py`; one window fix after a smoke test on partial data, `09cc35b`); `fetch_crypto.py --all` pulled 495 Coinbase USD pairs (91 delisted) and 775 Binance USDT pairs, key-free. Nothing live changed.
- [x] **P1**: the equal-weight market of coins +12 %/yr (CB) / +3.5 (BN) with a −91 % drawdown and −24 … −29 %/yr since 2022; bitcoin +50 / +36; ether −8 %/yr since 2022; the top-2 beats bitcoin in one half only → the vehicle is bitcoin alone.
- [x] **P2**: the trend family (8 rules, the median) inside its shuffled-months band on all six series, both venues — a history with no trend gives the same drawdown cut. **P3**: 17 of 18 cross-sectional cells lose to the basket; the one gain (BN top-5 by 6m, +6.9) is inside the random-picks band in each half; top-3 cells lose 17 … 43; the mirror loses less than the winners.
- [x] **P4**: the dip rule on coins −15 (CB) / −30 (BN) vs the basket. **P5**: volatility scaling cuts no drawdown and costs 6 pp/yr of the sleeve. **P6**: inside vs outside the switches ±0.2.
- [x] **P7**: the curve is a straight line — bitcoin held, live-like, +4.4 / +3.1 at 5 % (DD −20.7), +6.8 / +4.8 at 10 % (−23.1), +11.2 / +8.2 at 20 % (−30.8); the worst relative year never below the book's own to 25 %; t < 2 everywhere; band rebalancing keeps the blend's numbers (the written "50 … 80 %" was wrong).
- [x] **The operator's call**: taken at 5 % ("alright lets go 5%") after the decade table and the forecasts; no stops or timing (asked, declined on the evidence) → Phase 2.37 / Decision 097.
- [x] Roadmap C3 row; README rows (`cryptobook.py`, `fetch_crypto.py`) and the library bullet; handover §0 / §7 / §8; venue fees checked (Alpaca 0.25 / 0.15, Coinbase Advanced 0.60 / 0.40, Kraken Pro 0.80 / 0.40, Binance 0.10).

## Phase 2.35: A small crypto sleeve beside the book — roadmap C3 priced, a bet put to the operator (2026-11-04) — Decision 095
Hypotheses C1–C4 and the drop rule committed before the run (`a593da2`, `crypto.py`); Coinbase's daily candles for BTC / ETH / LTC fetched into the library (`fetch_crypto.py`, key-free). Nothing live changed.
- [x] **C1**: bitcoin held at 5 % adds +2.96 pp/yr to the decade book (2 %: +1.19; 10 %: +5.86), the drawdown 0.3 deeper (written 2 … 4), the worst relative year 4.9 better (written up to 3 worse); 91 % of it in the first half; t 1.1, P(excess > 0) 70 → 93 %.
- [x] **C2**: timing keeps the return (sma200 108 %, mom12 103 % of held) but the drawdown cut (18 / 3 points) sits inside the month-shuffled placebo's band (any average cuts a 68 %-vol series' drawdown: median +20); the timed sleeves fail drop-rule (c). Inside vs outside the exposure rules within ±0.3.
- [x] **C3**: the hindsight-free basket +0.7 over bitcoin with a deeper drawdown; ETH alone +4.7 (hindsight). **C4**: without 2017 the gain falls 62 % — and still adds in both halves, so drop-rule (d) passes.
- [ ] **The operator's call**: the held sleeve clears the pre-registered rule at 2 % and 5 % → a proposal by the rule, **recommended against** (a conviction bet on one asset's next decade, not a rule on prices; one bubble-shaped sample). If wanted: 2 % held outside the exposure rules, a held leg like `cash_ticker` (071), `BTC/USD` on Alpaca, 0.25 %/side, a day's build.
- [x] Roadmap C3 row ✅; README rows (`crypto.py`, `fetch_crypto.py`) and the library bullet; handover §0 / §7 / §8.

## Phase 2.34: The macro gate on history — roadmap A6's macro half run, the gate stays (2026-11-04) — Decision 094
Hypotheses M1–M3, which events count and the drop rule committed before the run (`97e3ab1`, `macrogate.py`); the Fed's FOMC pages 1999 → and the BLS yearly release schedules 2000 → fetched into the external library (`--only=fed,bls`, 50 pages). Nothing live changed.
- [x] **M1**: the gate as specified (no fill on the event session or the one before; FOMC + payrolls) +0.22 pp/yr on the sector ETFs 1999 → (inside the placebo band −0.26 … +0.41), −1.23 on the 15 names (inside −4.0 … +1.5 — blocking an eighth of the sessions on a three-slot book is ±3 whichever sessions); the documented gate (+CPI) +0.34 / −0.58; the live footprint (FOMC mornings only) +0.12 / −0.11.
- [x] **M2**: the blocked entries no worse on the sectors (24 trades, median +4.4 % vs +4.7 %) and better on the names (75 trades, +7.2 % vs +3.7 %, fewer stops); the placebo leg holds on both. **M3**: live the gate fires only on the morning run of a decision day — the keyword list matches FOMC and payrolls alone, the 08:30 releases never meet a run.
- [x] **The operator's call** ("run the docs", same day): `features.md`, `risk_management.md` and `TitanTrade/docs/architecture.md` gate 7 amended to what the code does — the morning run on an FOMC decision day; no code change.
- [x] Roadmap A6 and the Track H row; README row and the library bullet; handover §8 item 1 ✅ and §7's archive list.

## Phase 2.33: The earnings gate on history — roadmap B10 run, the gate stays (2026-11-04) — Decision 093
Hypotheses E1–E3 and the drop rule committed before the run (`ee22dab`, `earningsgate.py`); the entry-session fix made before E2 was read. Nothing live changed; the B track is complete.
- [x] **E1**: the live 2-day gate +0.01 pp/yr on the 15 names 1999 → (1.7 % of sessions, 2 of 417 entries); the through gate +0.04; the old 5-day gate −1.66 (four trades fewer — path noise on a three-slot book).
- [x] **E2**: the eight entries the live gate would have blocked ran at a median +20 % vs +4 % for the rest (12 % vs 37 % stopped) — eight trades; the placebo band of random windows is ±1 pp/yr and the live gate sits inside it. **E3**: the live book (sector ETFs) never meets the gate.
- [x] Roadmap B10 ✅, the running order; handover note.

## Phase 2.32: The book on real ETFs 1999 → — roadmap B11 run on the operator's Tiingo key, knowledge (2026-11-04) — Decision 092
Operator: the two free keys ("tingo: … alpha: …"), stored in the git-ignored `.env`. `fetch_keyed.py` pulled 36 Tiingo histories and the 15 names' earnings from Alpha Vantage within the free limits; `datasets.tiingo`, universes G / H; hypotheses H1–H5 committed before the run (`270c6e9`, `longhist.py`). Nothing live changed.
- [x] **H1 holds and beats its own range**: the sector floor +2.05 pp/yr over 27 years with the switches off (written +0 … +1), both halves positive, the rebound-year losses never came; the switches cost the sleeve 1.2 pp/yr and take 2007–09 from −53 to −36 %.
- [x] **H2 holds on return and robustness** (the book +2.32, both halves and all three eras positive, DD −42.6 vs −55.2), misses on the dot-com fall (−42 vs −48, the momentum splice −49) and on t (0.78, not > 2 — the century stays the evidence). The two bears belong to the two sleeves.
- [x] **H4** the 15 names +9.4 (hindsight); **H5** Tiingo ≈ Alpaca to 0.01 %/day with the named exceptions (SPMO 56 days, XLF's 2016 spin-off, the March-2020 closes); the decade segment +1.55 vs +1.36.
- [x] **H3 holds, no change**: the live cell 9th of 3,301 cells on G by plateau OOS, no neighbour flips sign, the knob directions hold, the walk-forward's per-window winner loses to the fixed cell by 1.2 pp/yr, the three-universe consensus cell is one step away in two knobs and gains +0.13 / +0.33 inside the book (under 0.5); the slot tilt toward 3 × 33 % seen on D repeats on G, the century tilts the other way — below the bar.
- [x] Roadmap B11 ✅, Track H rows ✅, the C1 vol-managed row; README rows; one insight; handover note.
- [x] **Next**: B10 — run the same afternoon → Decision 093 (Phase 2.33).

## Phase 2.31: The operator's calls on the open dials; the momentum weight as a curve (2026-11-03) — Decision 091
Operator: "just spmo" · "going live i will give you instructions when we have no other tasks left in the roadmap" · "7 close it" · "make informational" · the momentum weight "as a continuous graph".
- [x] SPMO alone (the MTUM split closed); rotation closed; the go-live order stands until the roadmap is empty; the slot-trimming flags log at INFO (`entries.py`, one line, tests green).
- [x] `momweight.py`: the blend on both windows in steps of 5 %, the exact book on the decade in steps of 10 % → `data/param_search/momweight.json` and the chart shown to the operator; roadmap C1 rows; Decision 091.
- [x] **The momentum weight**: "Keep 60 %" (operator, same day, with the curve in hand). The log-line change deployed 2026-11-04 11:55 UTC (`040872c`, both images).

## Phase 2.30: The working cash reserve set to 2 % with the core-buy guard — built, tested, deployed (2026-11-03) — Decision 090
Operator: "we never want to borrow from the broker. So find the optimal number of cash to hold and then do the code changes necessary to make this work". Hypotheses V1–V3 and the rule committed before the first run (`66a43e3`, `reserve.py`); results in Decision 090.
- [x] **V1 holds**: the return cost is linear, −0.143 pp/yr per point of reserve (0 % +1.72, 1 % +1.63, 2 % +1.48, 3 % +1.32, 5 % +1.03), DD 0.15 deeper per point, Sharpe flat, the same 61 trades.
- [x] **V2 → 2 %**: a 2 % adverse fill on the largest single buy (day one's momentum leg, 59 % of equity) needs 1.18 % of cover → the smallest whole percent is 2.
- [x] **V3 holds**: the drill at 2 % — today's shape +$2,125 after the pending fill (089's −$1,163 gone), with a 2 % adverse fill +$1,563, day one from all cash with 2 % fills on both legs +$856; the boundary 4 % → −$277; 1 % → −$123. Chaos S0–S9 unchanged.
- [x] **Code**: `MIN_CASH_RESERVE_PCT` 2.0; `manage_core_position(…, committed_cash)` with the executor passing `open_buy_commitment`; the backtester's default reserve follows the constant; the fake broker's `fill_slip` / `margin`; five 0.95 → 0.98 expectations; 295 tests, lint clean.
- [x] Docs: Decision 090; roadmap C5 row, the book line and the expectation (≈ +1.5); features, risk_management, security, data_schemas, how_to_read_a_checkup, architecture, handover, CLAUDE.md.
- [x] **Deployed 2026-11-03 12:36 UTC** (operator: "Deploy now"; `3247603`, both images, CLI import check ok, health ok, 7 jobs). Verify at the next run: the log's "Core target" line shows the momentum target 59 %, no order outside the bands, no "insufficient buying power". The clean window is not re-stamped (design still 070) unless the operator asks.

## Phase 2.29: The working cash reserve 5 % → 2 % — checked, proposed, not applied (2026-11-03) — Decision 089
Operator: "why do we even hold cash?" → "Yes, check it". The reserve traced to its three uses, Decision 081's reserve-2 % number re-run (+1.48 vs +1.03), one chaos-drill scenario at both levels (`tests/test_reserve_check.py`). Nothing changed.
- [x] **Found**: the core legs' buys are capped at cash − reserve but not net of a pending bracket; with SPY inside its band above target, a 2 % reserve leaves the bracket's fill up to 3 % of equity short (the drill: −1.2 %), a 5 % reserve never (the reserve equals the band). The Decision 055 bug's shape through the other door.
- [x] ~~**On the operator's go, in this order**~~ (go given the same day → Decision 090, Phase 2.30): (1) the guard — the core buy capped at cash − reserve − pending buys (`open_buy_commitment` passed from the executor), the drill test flipped to the invariant; (2) `MIN_CASH_RESERVE_PCT` 5 → 2 (a parameter: targets restated to momentum 58.8 % / dip sleeve 39.2 %, the clean window noted), worth ≈ +0.45 pp/yr on the decade, ≈ +0.35 net at go-live.
- [x] Roadmap C5 row; CLAUDE.md test count 291; handover note.

## Phase 2.28: Track F housekeeping — the luck meter in `master.score`, `docs/todo.md` reordered (2026-11-03) — Decision 088
Operator: "do all the ready to run". No `src/` change, no deploy.
- [x] `master.score(…, luck_draws=N)` adds `t`, `psr` (the probabilistic Sharpe ratio), `band` (the excess CAGR's 5 / 50 / 95 % by stationary block bootstrap) and `p_pos`; `master.luck_line(s)` prints them; `sharpe_daily` / `ncdf` / `stationary_bootstrap` moved from `luck.py` verbatim (its output byte-identical before and after); the pool-level statistics (deflated Sharpe at N, PBO) stay in `luck.py`. `rates.py` is the first script to print the line; older scripts untouched (their outputs stay reproducible).
- [x] This file reordered: the open-items index at the top, then every phase newest first (2.28 → 2.0, 1.37 → 1.5, 1), then the original build plan's Phases 1–5 and the two closing sections; every non-blank line kept; the stale "Next" boxes of Phases 2.4 → 2.19 ticked with the Decision each ran into.

## Phase 2.27: Rates by era — roadmap B4 run, the cash programme alone at go-live (2026-11-03) — Decision 087
Operator: "do all the ready to run". Hypotheses R1–R7 and the rule committed before the first run (`2ea35b9`, `rates.py`); the rate-level series corrected after the first run (French's daily bill return is rounded to 0.01 % per day — three values across the decade; the level now comes from FRED's daily bill from 1954 and French's monthly file before); results in Decision 087. Nothing live changed.
- [x] **R1 / R3 / R5 hold**: the rate by era 0.85 / 3.54 / 6.80 / 1.93 %; the pickup by era +0.10 / +0.78 / +0.94 / +0.33 (century +0.52, decade +0.17 — Decision 068 reproduced); the leg is worth 0.15 pp/yr per point of bill rate on the century's 15 % idle share, 0.08 on the decade's 7.8 %.
- [x] **R2 rejected in its direction**: the book was de-risked at rates 1.1 … 1.5 points *above* the era's mean in 1950–2000 (rate-shock bears) and below it in 2008 / 2020; at the average over the century. Two kinds of bear.
- [x] **R6**: the two switches cost about a point a year since 1975 at a zero rate, half a point in bills; earned their keep only in 1927–50; on for the drawdown as before. The hypothesis had misread Decision 068's +1.6 (that was the insurance off with the shock on — reproduced as +1.67).
- [x] **R7 decides**: the cash programme alone +0.45 pp/yr at today's 4.05 % bill (the reserve included); SGOV / SHY on top +0.03 / +0.06 — under the pre-registered 0.1 → **the programme alone, the `cash_ticker` leg off; SHY only if the programme is unavailable**. Phase 2.0's checklist and Phase 2.20's go-live box updated.
- [x] Roadmap B4 ✅, the C5 go-live row, the running order; `fetch_external.py` lists the monthly French factors file; README row; one insight; handover note.

## Phase 2.26: Trend and carry over a century — roadmap B3 run, no sleeve (2026-10-30) — Decision 086
Operator: "let's do the century trend". Hypotheses T1–T5 and the drop rule committed before the first run (`1809250`, `trend.py`); the monthly book construction corrected before any number was read; results in Decision 086. Nothing live changed.
- [x] **T1 holds, sizes off both ways**: TSMOM 1985 → Sharpe 0.98 gross (stronger than written), positive in both halves and all five decades (2015–24 +1.0 %); the century macro-momentum cousin Sharpe 0.39 (weaker), positive in all four eras by a hair; carry Sharpe 0.56.
- [x] **T2 mostly holds**: trend pays in the slow bears (2000–02 +50, 2008 +24, 2022 +27; 1973–74 +18 on the cousin), loses the rebounds, flat in the fast crashes; **but** the cousin lost 13 in 1929–32 and the correlation with the book's *active* return is +0.19 / +0.30 — the same bet from another market.
- [x] **T3 fails** in all three constructions (century −0.7 … −3.6; 1985 → a wash gross, worse in one decade, negative net; ETF decade −1.2 … −3.5) for 4 … 10 points of drawdown and +0.02 … +0.12 Sharpe. **T4 fails**; carry hedged the slow bears before 2008 (+57 / +34 / +34) and crashed in 2008 / 2020. **T5 not reached.**
- [x] Roadmap B3 ✅ closed, Track D row, C3 futures row; README row; `datasets.aqr_monthly`; one insight; handover note.
- [ ] **Next**: the checkup ≈ 2026-11-12; B11 when the Tiingo key exists.

## Phase 2.25: The harness tidy-up — `books.py` (2026-10-30) — Decision 085
Operator: "do the tidy up". What moves where and the acceptance (byte-identical outputs of seven script runs captured before the first edit; loader equality for `search.py`) committed before the change. No `src/` change, no deploy.
- [x] `books.py` (LIVE, prev / sma_above / shock_flags, decade(), century(), sets(), exposure(), rf_daily / align_rf); `carry.py` and `master.py` re-export every public name (the same objects); `master` / `rotation` / `shorts` / `regimes` builders rewired; `search.py` ← `datasets` + `analyze1_lib`; `analyze1.py` ← `analyze1_lib`; the `sys.path` line added where a script now imports a sibling (for `-I`).
- [x] The seven diffs: all byte-identical; the loader check: equal to the bit, same grid; nothing left as it was; README rows; Decision 085 result; roadmap F ✅. About 110 lines fewer.

## Phase 2.24: The chaos drill — the executor against a lying broker (2026-10-30) — Decision 084
Operator's go ("Go, chaos test"). Scenarios S1–S9, invariants I1–I6, the expected outcome per scenario (S1 core legs and S2 expected to fail I3; S3b a design question) and the drop rule committed before the build (the Decision 084 stub).
- [x] `tests/test_chaos.py`: the stateful fake broker with Alpaca's share accounting, patched into executor / protection / entries / core_allocation and the quote, the HTTP layer counted; one `execute_trades` per scenario; the invariants. 12 tests (9 pass, 3 strict expected failures), suite 289, ruff clean.
- [x] Run and recorded in Decision 084: seven guards hold; **S1 / S2** — the core legs rebalance on a phantom account value in both directions (−79 %: all SPY and 312 of 400 SPMO sold at the market); **S3b** — a target exit fires on an unconfirmed mark. Each stays a strict expected failure until its fix lands.
- [x] **Fixed (operator: "Go, fix both")**: (1) `risk_manager.account_value_suspect` (±50 % off the peak, both directions; the breaker trips on the upside too) read once at the top of `execute_trades` — when suspect: error log + the rate-limited alert, the core legs, the entries, the target / holding exits and the stuck-in-cash alert skipped, stop coverage kept; (2) `_manage_held` confirms a target exit with the live quote and keeps the position with a warning when the market does not agree. The three markers off, all nine scenarios pass; 289 tests, ruff clean.
- [x] **Deployed 2026-10-30 16:31 UTC** (both images, no config change, no window restart, no job running; health ok, both images import the guard, 0 errors after the restart). **Verify at the next checkup**: no "SUSPECT ACCOUNT VALUE" line unless the broker glitched; no "target not confirmed by the market" line unless a mark was off; the 19:30 / 20:30 UTC jobs of Oct 30 ran clean after the day's four restarts.

## Phase 2.23: The "how to read a checkup" page (2026-10-30) — Decision 083
Operator: "let's do the next task" after Decision 082. Docs only, no deploy.
- [x] `docs/how_to_read_a_checkup.md`: the four questions in order, a table per section (meaning / normal / a problem), the switches from their inputs, the prescribed reasons per trade, the benchmark band, the fill ledger, the shadow comparison, the go/stop rule, the expectation (081), the checklist; linked from CLAUDE.md, deployment's checkup routine and the handover.
- [ ] At the next checkup (≈ 2026-11-12): write the record in the page's order and wording, and fix the page where the record needed something it does not cover.

## Phase 2.22: The monthly curator retired; the curator ledger built and removed (2026-10-30) — Decision 082
Operator's go on A5 ("Go, A5"): the ledger pre-registered (`81ec4be`) and built (`451f104`, five tests). Then, asked whether to keep the monthly call for the ledger to judge or retire it, the operator chose **retire** — the last scheduled LLM call goes.
- [x] `monthly_curate` disabled in `data/schedule.json` (definition kept, one toggle brings it back); the ledger code reverted; `curate` stays a manual advisory command; `CLAUDE_KEY` still required by config (later cleanup if never used).
- [x] Docs: CLAUDE.md, architecture (both), features, agent_instructions, security, deployment; roadmap A5 🚫, C4, A1's verify list; the Phase 2.9 verify item.
- [x] **Deployed 2026-10-30 16:05 UTC on the same go** (config + code: pull → build both → restart the API with no job running → prune, disk 44 %): `/api/scheduler` lists `monthly_curate` with no next run and the other six jobs unchanged, health ok, 0 errors, the CLI image bakes the disabled flag. **Verify at the next checkup**: no curate run on Nov 1, no Claude cost line after Oct 30, the daily summary and the executes unchanged.

## Phase 2.21: The two-sleeve book in the package backtester — roadmap Track F, first row (2026-10-30) — Decision 081
Operator's go ("Go", 2026-10-30, after the takeover report). Hypotheses H1–H5 and the drop rule committed before the engine ran (`3c2339c`, the Decision 081 stub); the build follows `docs/handover.md` section 8; results in Decision 081. Nothing live changes; the CLI-image deploy is a separate go.
- [x] Engine: `momentum_bars` / `cash_bars`, `momentum_weight` (0 = the old book), the shock trigger and min(), the slot on the dip sleeve, the 5 % band per core leg in the executor's order with only the cash above the reserve, `shock_days`, `min_exposure`, the average SPMO share and the core-leg trade counts; exits return to SPY (the executor's sell-to-cash plus same-run buy-back, equal to within the reserve's drift — routing to cash moved the Decision 062 floor by 0.6 % of equity and was reverted).
- [x] `params_from_config` passes the new fields; `main` loads the momentum ticker (fails plainly when missing) and prints the sleeve line; `--shadow` runs both lists under the two-sleeve book and each dip sleeve alone (the old `main` backtested the live list with no names under design 070 — fixed); `download-history` fetches the momentum and cash tickers.
- [x] Tests (`tests/test_backtest_two_sleeve.py`, five, synthetic bars; 277 total); `validate.py` keeps the dip-only equality (same trades, equity within 10⁻⁸ on the three sets) and gains `--two-sleeve`; ruff clean.
- [x] **The gap**: path-exact +1.03 vs the blend's +1.36 (H1 ✓ inside ±0.5), first half −0.27 vs +0.27 (**H2 ✗**, the named risk), DD −19.3 vs −20.0 (H3 ✓), 61 trades either way (H5 ✓); the reserve on the whole book explains the gap and more (+0.45), the band 0.06. **Expectation restated** (drop rule): ≈ +1.0 pp/yr vs SPY decade-like, not both halves positive on the exact path, DD ≈ −19 %; the century stays a labelled blend number. Features / architecture / CLAUDE.md / README / roadmap F ✅ and its preamble.
- [x] **Deployed 2026-10-30 14:57 UTC** (operator's go; both images, no config change, no window restart, no job running; health ok, 7 jobs, 0 errors; CLI image import-checked). `backtest-mech --shadow --start 2026-10-29` on the CLI image prints the book for both lists (2 sessions, 0 trades, SPMO share 57 %) and each dip sleeve alone. **Verify at the next checkup**: the shadow line shows both lists under the two-sleeve book; the 19:30 UTC execute and the 20:30 summary ran clean after the restart.

## Phase 2.20: The de-risk destination — roadmap B8 run, a short Treasury proposed for the go-live cash leg (2026-10-30) — Decision 080
Operator's go. Hypotheses D1–D7 committed before the first run (`75d7049`), the addendum A1 (the 1975 window) before the second (`ea40b11`); results in Decision 080. Nothing live changed; the proposal is a go-live configuration value on the operator's go.
- [x] **Bills beat cash** by 0.6 … 0.7 pp/yr on every long window (the carry line, Decision 068 addendum).
- [x] **The 2-year Treasury beats bills on every pre-registered check**: +0.26 (1971 →, cash before 1976) and +0.43 (1975 →), both halves, both eras, drawdown 2–3 points shallower than cash's, the placebo's 90th percentile cleared on both windows; −0.11 on the decade (2022: +9 vs +11).
- [x] **The 10-year beats bills by the most and fails the strict rule by one era**: +0.79 / +0.93 / +0.66 on 1971 → / 1975 → / 1962 →, DD 5–6 points shallower, the placebo cleared on all three (94 / 98 / 94 %), both halves and eras from 1971 and 1975; behind bills in 1962–75 (by 0.3) and in 2022 (+4 vs +11), −0.25 on the decade. A dial: its failure mode is the rate-shock bear, the operator's named fear.
- [x] **Gold and the mixes were 1973–74**: from 1975 gold +0.29 over bills at the placebo's median (56 %), the mixes at or below it; closed. A permanent 10 % bond sleeve −1 pp/yr vs the book: closed.
- [x] Roadmap B8 ✅, C5 / D / C3; the Phase 2.0 go-live item (b) amended; README; one insight; handover note.
- [ ] **At go-live (operator's go; "leave for go-live" decided 2026-10-30 — the leg stays off on paper; Decision 087: the leg stays off at go-live too if the cash programme is available — its increment over the programme is +0.03 … +0.06 pp/yr)**: `cash_ticker` = SHY (or VGSH) rather than SGOV when the leg is on; the checkup line compares the sweep APY with SHY's yield plus the +0.3 duration pickup; deployment, risk-management and features pages name SHY where they name SGOV. IEF recorded as the dial.
- [x] **Next**: ~~the first checkup under design 070~~ ran 2026-10-30 (Check 2026-10-30 in decisions.md; the research data archived on titanserver). **Then the Track F cleanup — picked by the operator 2026-10-30 as the next agent's first task; `docs/handover.md` (rewritten the same day, with the paste prompt in its section 0) is the brief.**

## Phase 2.19: Gold over a century — roadmap B7 run, no sleeve, the parking place to B8 (2026-10-30) — Decision 079
Operator's go. Hypotheses G1–G5 committed before the first run (`2f52478`), the addendum A1–A2 before the second (`1636a74`); results in Decision 079. Nothing live changed.
- [x] **The sleeves fail, as pre-registered**: on 1971 → every gold sleeve costs 0.2 … 0.9 pp/yr against the book (−0.68 for 10 % from SPMO) for 4 … 9 points less drawdown and +0.04 … +0.09 of Sharpe, not both halves; the decade (GLD) reproduces Decision 068 exactly (−0.32, Sharpe 1.18 vs 1.10, DD −18.3). Gold alone 8.6 %/yr vs 11.3, DD −62, correlation −0.01.
- [x] **The parking place was 1973–74**: the idle half in gold +4.71 vs bills +3.34 on 1971 → passed the letter of the bar; gold earned 14.6 %/yr in the de-risked windows over 1971 → and 7.0 (vs 7.2 overall) from 1975; from 1975 it is behind bills in the first half (+3.4 vs +4.3) and at the timing placebo's median (48 % of draws); 1971 → above 84 % of draws (the bar 90 %). A candidate, folded into B8.
- [x] Roadmap B7 ✅, B8 amended (cash / bills / bonds / gold together, the next pick), Track D and C3; README row; one insight; handover note.
- [x] ~~**Next**: B8~~ (run 2026-10-30 → Decision 080) — the de-risk destination judged together (Treasury yields 1954 / 1962 → as a total-return series; gold's step series; the timing placebo; the eras) — on the operator's go; then the first checkup under design 070 (≈ 2026-11-05) and the Track F cleanup.

## Phase 2.18: A VIX-based shock trigger — roadmap B6 run, the price rule stays (2026-10-30) — Decision 078
Operator's go. Variants, hypotheses X1–X5 and the Decision 067 bar committed before the run (`a2eb604`, `vixshock.py`); results in Decision 078. Nothing live changed.
- [x] **No VIX cell beats the price rule**: 1990 → the best level cell (VIX > 40 / hold 10) +1.74 vs the price rule +1.75, same drawdown, neighbours within 0.5 (no plateau), worse on the decade (+1.14 vs +1.36, DD −22.0 vs −20.0); VIX > 25 / 30 lose 1 … 3 pp/yr on both windows (they fire 27–45 % of sessions and give the 2008 / 2020 rebounds back twice over); the jump cells of 12 … 16 points match the price rule because they are the same event; the inverted term structure is the worst of the family.
- [x] **Timing**: median lead zero sessions over thirteen bears (2008 +45 the one early call; 2020 −1, 2022 −2); the VIX > 30 rule agrees with the price rule on only 45 % of de-risked sessions.
- [x] Roadmap B6 ✅ closed, Track D; README row; one insight; handover note. The shock trigger stays the −7 % / 10 / 20 price rule.
- [x] ~~**Next**: B7~~ (run 2026-10-30 → Decision 079) — gold over a century (datahub monthly 1833 → against the French market), on the operator's go.

## Phase 2.17: Credit stress as the insurance's second signal — roadmap B5 run, a candidate that failed its robustness check (2026-10-30) — Decision 077
Operator's go. Hypotheses C1–C6 and the caveats committed before the first run (`27457b8`), the addendum S1–S3 before the second (`227e040`); results in Decision 077. Nothing live changed.
- [x] **Run 1** — SMA AND NFCI > 0.5 on 1971 →: +3.50 vs the SMA alone +2.62, both halves and both eras, DD −37.4 vs −35.6, all 20 placebo draws beaten (a random 9 % firing earns +2.80); the gain is in the rebounds (2020 −9 vs −16); ANFCI similar; STLFSI4 (1994 →) +1.76 vs +1.14, placebo beaten; **the VIX twin +1.86 vs +1.75 with DD −42.5 and the placebo not beaten**; on the decade the rule never fires (= the no-insurance book +3.03).
- [x] **The revision finding** — ALFRED: the NFCI's 2020-04-03 week read +0.07 in real time, +0.31 today; first-release histories fetched via the FRED API on the server (NFCI / ANFCI from 2011-06, STLFSI4 from 2022-11; `external/fred/*_initial.csv`); Moody's BAA / AAA (monthly 1919 →), DBAA / DAAA / BAA10Y / AAA10Y (daily) and TEDRATE added to the library and the fetcher.
- [x] **Run 2 fails** — the unrevised Moody's spread gate on 1971 →: +2.74 (+3.6 / +2.0) vs +2.62 (+3.8 / +1.5), DD −46.3 vs −35.6, placebo beaten 35 %; century: two of four eras ahead, era drawdowns 15 and 10 points deeper; daily spreads the same at every threshold; a spread confirms a bear late (1973–74 +5 vs +21, 2008 +10 vs +21). Real-time NFCI 2011 →: max +0.07 in 2020, the > 0.5 rule never fires in either vintage.
- [x] Roadmap B5 ✅ → closed, Track D row, B6 note; README row; two insights; handover note. **The insurance keeps its two signals.**
- [x] ~~**Next**: B6 / B7~~ (run 2026-10-30 → Decisions 078 / 079): B6 (a VIX-based shock trigger, the fast-fact mechanism) / B7 (gold over a century), on the operator's go.

## Phase 2.16: The quality stage 1 — our own profitability picks on free SEC data, no sleeve (2026-10-30) — Decision 076
Operator: "if the data says it is profitable, diversifies and stands the test of time, why not" → free data first → go. Design, hypotheses S1–S6 and drop rules committed before any data (`a086fdc`); results in Decision 076. Nothing live changed.
- [x] **Data, free**: the SEC's XBRL `companyfacts` API for the S&P 500 point-in-time universe (`fetch_sec_facts.py`, 599 of 745 tickers mapped — the SEC's ticker file lists live tickers only; 118 MB; to be archived on titanserver at the next checkup); three pipeline bugs found and fixed before the recorded run (one tag per company → the first tag per year; the SEC's "Q4" label on annual facts; a restated year under a new tag carrying a later filing date); the net-income fallback for filers without cost of sales or operating income. Coverage 303 → 455 of ~503 members per rebalance.
- [x] **S1 fails (strictly)** — our top 30 % beats the equal-weight universe +1.2 (+3.4 / −0.7) against the French +1.5 (+2.6 / +0.5) over the same months: the pipeline reproduces the construct; the second half is the era's.
- [x] **S2 fails** — the top-50 equal-weight +1.9 (+4.6 / −0.4) vs the universe: above 92 % of random lists over the decade, at their median since 2022; the top-30 +4.5 (+6.7 / +2.5) keeps it at a noise where one random list in fifty does as well.
- [x] **S3** — equal-weight picks lose to SPY (−0.7 … −1.0; the equal-weight effect −2.6 … −3.3 outweighs the premium); **value-weighted they beat SPY +1.8 … +3.0, three of four cells in both halves** (a reference line, with the book-equity / buyback-giant confound).
- [x] **S4 fails** — the cell picked in-sample (gross profitability, N 30) is the worst out of sample (+7.3 → −9.2); the OP family is consistent (4 of 12 cells positive in both halves, all OP / OIE).
- [x] **S5 fails** — the sleeve costs the book 0.6 … 0.9 pp/yr for the same Sharpe. **S6** — 39–42 % turnover; $100 / $400 per name at $25k / $100k against the $500 dust floor.
- [x] Roadmap Track H: stage 1 ✅, stage 2 (the value-weighted picks, confound first) 💡, the paid long-history item not worth buying unless stage 2 survives; README rows; `screens.simulate(score_matrix, weights)`; two insights.
- [x] **Stage 2 run the same day (operator: "stage 2"; `qualpick2.py`, checks T1–T6 committed first, `64af97c`)**: the weighted picks were Apple, Nvidia and Lilly (top-5 share 54–72 %; the top-30 57 % Apple in 2026); after SPMO and a size tilt no alpha survives (t −0.5 … +1.2); capped at 5 % every variant loses out of sample (−1.7 … −4.1 vs SPY), the within-size and over-assets constructions included; the fifty largest names alone made +2.3 in the January window; the sleeve fails on all four variants; the smallest cap-weighted position $5 at $25k. **The quality question is closed on free data; the paid extension is not bought.**
- [x] ~~**Next**: B5 / B6 / B7~~ (run 2026-10-30 → Decisions 077 / 078 / 079) — credit stress as a second insurance signal, a VIX shock trigger, gold over a century — on the operator's go.
- [ ] At the next checkup: archive `data/param_search/external/sec_facts/` (118 MB) and `alpaca_hist/quality/` on titanserver beside the other research data.

## Phase 2.15: Quality over a century — roadmap B2 run, no sleeve, B9 closed (2026-10-30) — Decision 075
The next pick after B1, on the operator's go. Hypotheses Q1–Q6 and the drop rules committed before the run (`05b4144`, `scripts/param_search/quality.py`); results and tables in Decision 075. Nothing live changed.
- [x] **Q1 holds** — RMW +3.1 pp/yr, CMA +3.0, QMJ +3.7 (t 3.7–4.3), positive in both halves and every era, defensive (+103 … +139 % in 2000–02, +30 … +59 in 2008), beta −0.1 … −0.2, uncorrelated with momentum except in the first half.
- [x] **Q2 holds** — the top 30 % by profitability held beat the market +1.2 pp/yr in every era at the market's volatility with a 5-point smaller drawdown; conservative investment +2.2; the bottom decile −3.5.
- [x] **Q3 fails the bar** — quality from momentum costs 1 pp/yr, instead of momentum 3; quality in place of half the dip sleeve +0.2 better, better OOS and in every era, Sharpe 0.96 vs 0.93, equal in-sample (a hair short), worse worst year.
- [x] **Q4 fails, B9 closed** — the dip rule on the 10 most profitable portfolios −1.7 vs the market and −4.0 vs holding them; on the least profitable −1.6; the gap 0, flipping between halves and eras. Quality is harvested by holding.
- [x] **Q6 fails** — QUAL −0.7 vs SPY (−0.4 / −1.1); no investable vehicle in the library.
- [x] Roadmap B2 ✅, B9 🚫, Track D and C2 closed, Track H: quality ETFs (SPHQ / JQUA / DGRW) as the cheap reopening condition; README row; three loaders; one insight.
- [x] **Addendum — the quality funds as vehicles (same day, operator's pick)**: eleven funds fetched on titanserver (data API only, SIP, `adjustment=all`, archived), the list and hypotheses V1–V3 committed before the fetch (`b2c914f`, `quality_etfs.py`). **0 of 12 beat SPY in both halves** (JQUA +0.1, SPHQ −0.6, QUAL −0.7, FQAL −0.9, the dividend family −1.2 … −3.9, all behind through 2025) while the French top-30 % / top-decile portfolios beat SPY by +1.6 / +3.4 over the same decade (the French market = SPY to the decimal); the funds load on RMW (0.05–0.27, a quarter to half of the real tilt) with negative alphas. The vehicle is not the premium; door closed; a self-built held profitability sleeve from point-in-time fundamentals is the only route left, recorded in Track H, not proposed.
- [x] **The data rule (operator, 2026-10-30)**: free first, always; paid-only data → the "needs paid data" group at the back of the roadmap, bought once and together. Free fundamentals found: the SEC's XBRL APIs / data sets, every US filer from 2010-Q4, point-in-time by filing date (probed; cleaning = 1–2 days); nothing free before 2009 (SimFin 5 years, OSAP no tickers). Quality stage 1 = ready on free data 2010 → (Track H, operator's call); its 2000–02 / 2008 confirmation = paid (EODHD / Sharadar), parked in the paid group with the option chains, B10 / B11 (free keys first) and the MSCI histories.
- [x] ~~**Next**: B5 / B6 / B7~~ (run 2026-10-30 → Decisions 077 / 078 / 079) — credit stress as a second insurance signal, a VIX shock trigger, gold over a century — on the operator's go.

## Phase 2.14: Put-writing and the collar indices — roadmap B1 run, nothing adopted (2026-10-29) — Decision 074
The next pick after E2, on the operator's go. Hypotheses O1–O5 and the drop rules committed before the run (`cf51d75`, `scripts/param_search/putwrite.py`); results and tables in Decision 074. Nothing live changed.
- [x] **O1** — the put-write index (daily only from 2007) lagged the market by 4.0 pp/yr (−7 since 2017); the 30-delta buy-write kept pace over 40 years in the first half only; the protective put cost 3.1 pp/yr in every decade for a quarter less drawdown, the collar 5.7 for half; on the decade every index loses 2.9–18 pp/yr to SPY.
- [x] **O2 fails** — an option-writing sleeve is a Sharpe tool, not a return tool: BXMD in the dip sleeve's place over 40 years +1.57 vs +1.54 at Sharpe 0.84 vs 0.77 and a worse worst year; on the decade −1.6 … −1.9 pp/yr for nothing; the writing index is a mild diversifier (correlation −0.06 … +0.15 with the sleeves) that does not earn its place.
- [x] **O3 fails** — the idle half in a protective put: +0.3 vs bills over 40 years with the drawdown 12 points deeper (−48 vs −36); on the decade +3.45 vs +1.36 at −22.8 vs −20.0 (the era's preference for less insurance; still over the 2-point bar); the permanent put costs 3.1 pp/yr for −42 % against the free signals' 0.7 for −39 %.
- [x] **O4** — the bought protection protects as much as the rules in the fall and loses far more in the rebound year (2009 −37, 2020 −44 vs −26 / −16).
- [x] Roadmap B1 ✅, Track D "put-writing" closed with numbers, C3 "options" answered; README row; `datasets.cboe`; one insight.
- [x] ~~**Next**: B2~~ (run 2026-10-30 → Decision 075) — quality over a century (French profitability / investment sorts, AQR QMJ), on the operator's go.

## Phase 2.13: The international book — roadmap E2 run, no book, no blend (2026-10-29) — Decision 073
The handover's first task, on the operator's go. Hypotheses I1–I7 and the drop rules committed before the run (`eb94dbc`, `scripts/param_search/intl.py`); results and tables in Decision 073. Nothing live changed.
- [x] **I1 holds** — French regional WML 1990 →: Developed ex-US +7.4 pp/yr (t 4.7, both halves), Europe +9.9, Asia-Pacific ex-Japan +10.8, Japan +0.6 (none, as pre-registered); the premium is stronger ex-US than in the US (+5.3) over the same 36 years.
- [x] **I2 holds** — IDMO held +4.3 vs ACWX (+4.0 / +4.7), IMTM +1.4 (+2.1 / +0.7), both halves, all three indices, through 2025 too.
- [x] **I3 fails** — the dip rule on the 20 country ETFs: −0.9 in the first half vs ACWX, −1.4 vs the equal-weight basket, −1.5 / −2.5 through 2025; 62 % winners and a +2.8 % median trade (sectors 79 % / +4.9 %); insurance on 24 % of sessions. Countries are not a sector floor.
- [x] **I4 fails** — the books' active returns correlate 0.58 although the dip sleeves correlate 0.04: the exposure rules dominate the active return and both markets de-risk together.
- [x] **I5 fails** — every blend gives back 0.7–3.8 pp/yr vs SPY, no better than ACWX held in the slot, inside the random-country spread; DD gain ≤ 1.3 points, crash weeks ±1–2 points; no blend positive vs SPY in both halves. Post hoc: IDMO alone in a 10 % slot is the one cell beside the live book (+1.22 vs +1.36, DD −20.9, Sharpe 1.12) — a C1-style dial, recorded, not proposed.
- [x] **I7 knowledge** — in euros the decade's ranking is unchanged (dollar drift −0.7 %/yr); 2002–08: US stocks −4.9 %/yr in euros vs developed ex-US +3.5 (the fear, in history); 1999–2026 the dollar round-tripped and the US won by 2.5 pp/yr in both currencies; DBEF beat EFA +2.3 (the rate differential, E4 reference).
- [x] Roadmap: E2 ✅, E3 🚫 (reopened only by Tiingo's longer country-ETF history, B11, or a pre-registered IDMO-dial test), E4 priced; README row; `datasets.french_regional`; todo 2.12 order corrected (E2 was always first after the risk statement).
- [x] ~~**Next**: B1~~ (run 2026-10-29 → Decision 074) — put-writing and the collar indices on 40 years of Cboe data (roadmap B1), on the operator's go.

## Phase 2.12: The roadmap (2026-10-29)
Operator: "build some roadmap and store it … see if the new data reopens closed decisions … dive into the freedom areas … run strategies on other markets too." Written as `docs/roadmap.md` (tracks A live evidence, B tests the new data unlocks, C the freedom areas, D closed doors the data reopens, E other markets, F method, G toward real money) with a status mark per item; the first international data fetched the same day (French regional factors / momentum 1990 →, 39 region / country ETFs 2016 →, archived on titanserver). Updated whenever an item moves; results stay in `docs/decisions.md`.
- [x] ~~Next in the roadmap's own order~~ (all run 2026-10-29 / 30 → Decisions 073–079) (revised 2026-10-29 after the operator's risk statement: the international track first), each on the operator's go: E2 the international book (run 2026-10-29 → Decision 073, Phase 2.13) → B1 put-writing on the Cboe indices → B2 quality over a century → B5 / B6 / B7 afternoon tests.

## Phase 2.11: The external data library (2026-10-29) — Decision 072
Operator: find and store everything beyond prices that could matter, free first. `scripts/param_search/fetch_external.py` → `data/param_search/external/` (271 MB, 122 of 127 items, manifest), archived on titanserver (`archive/param_search/external/`, SEC zips excluded).
- [x] Fetched: Cboe option-writing benchmarks 1986 → and the VIX family; FRED rates / curve / stress / macro / recessions since 1954; CFTC positioning 1986 →; Shiller 1871 →; AQR century of factor premia, TSMOM, QMJ, BAB, VME; French profitability / investment / size / 5-factor / industry daily sorts; FINRA margin; gold monthly; two SEC statement quarters.
- [x] Walled / gone recorded: Stooq, Yahoo, LBMA, AAII, Cboe put/call archive, FRED Wilshire + gold; NAAIM needs a manual download.
- [ ] **Operator (free keys, a minute each)**: Tiingo (the 1999 → ETF and name history), Alpha Vantage (historical earnings dates for the gate valuation); optional small spend: EODHD (~€20/mo) or historicaloptiondata.com (~$100/yr) if the put-writing question goes beyond the Cboe indices.
- [x] ~~**Next tests this unlocks (each pre-registered, operator's call)**~~ (all run → Decisions 073–080, 086, 087; the keyed B10 / B11 wait on the keys): (1) put-writing vs the S&P on 40 years of Cboe indices (PUT / BXM / PPUT / CLL inside the book); (2) a century of profitability deciles vs momentum (the quality question before any fundamentals pipeline); (3) AQR trend / carry premia on the operator's eras; (4) rates by era for the carry and insurance pricing.

## Phase 2.10: Go-live readiness — backups, heartbeat, the T-bill leg, the runbook (2026-10-29) — Decision 071
Operator: "you can now do 2" (the readiness track). Findings and builds in Decision 071; nothing live changed, code not deployed.
- [x] Found: Alpaca GTC stops expire after 90 days (`expires_at` on the book: Jan 11 / Jan 22); no backup of `state/` existed; $25k sizes every ETF slot at ≥ 13 shares, $10k is the floor; paper credits no dividends and live cash interest is unverified; taxes are in no number.
- [x] Built: `scripts/backup_state.sh` + host cron 21:30 UTC on titanserver (30 archives kept; installed 13:18 UTC, first archive restore-checked byte-identical); `HEALTHCHECK_PING_URL` heartbeat after the daily summary; the T-bill leg `cash_ticker` (off) as a third core leg with sell-first / buy-last ordering; the server-down runbook in deployment.md. 272 tests, ruff clean.
- [x] **Deployed 2026-10-29 13:40 UTC** (both images, no config change; the heartbeat is a no-op until `HEALTHCHECK_PING_URL` is set, the T-bill leg off until `cash_ticker` is set). The backup cron was live on the host since 13:18 UTC.
- [ ] Go-live checklist items (a)–(e) in Phase 2.0 need the operator (live account and funding, the cash-sweep enrolment, the healthchecks.io URL in `.env` + API restart, the advisor line).

## Phase 2.9: The dip sleeve on the sector ETFs, the hand-picked list as a shadow list — prepared, NOT deployed (2026-10-29) — Decision 070
Operator: a hand-picked, static list "seems temporary"; the day's tests showed any single-name list loses with the dip rule and the curated list's edge is 2022 → only. Built on the operator's go, deploy pending the operator's explicit go.
- [x] Code: `shadow_watchlist` + `design` in config; a held name removed from the watchlist keeps its HOLD item (no forced sell); the clean window re-stamps on a design change (`strategy.json` `design` / `dip_universe`); sector ETFs carry their own sector and skip the correlation gate; the bundle, the curator and `backtest-mech --shadow` know the shadow list. 266 tests, ruff clean.
- [x] Config staged as `data/watchlist.decision070.json` until the deploy (`./data` is bind-mounted into the API container, so a committed change goes live on `git pull`); copied over on the server during the deploy and now committed as `data/watchlist.json`.
- [x] **Deployed 2026-10-29 13:03 UTC** (operator's go): pull → build api → stop api → watchlist swapped → up api (seconds, no job running) → build titantrade → CLI import check → prune (disk 44 %); health ok, 7 jobs; `fetch` 26 names 0 errors; `signals`: DXCM / JPM / URI HOLD at their stops, `legacy_to_close` [], 0 free slots, no ETF signal today (four ETFs 8–10 % off their highs but under SMA150), window re-stamped `design 070` at 13:04:02 UTC. Staged file retired; `data/watchlist.json` now carries the live content. Decision 069 (ledger, verdict guard) went live in the same deploy.
- [x] First execute under design 070 (2026-10-29 14:15 UTC): completed, DXCM / JPM / URI HOLD, nothing orphaned, 0 free slots, no SPY (overlay above the sleeve).
- [x] **Checked 2026-10-30 (the first checkup under design 070, six days early)**: the 15:30 ET Oct 29 execute ran clean (0 trades, nothing orphaned, SPMO untouched at 26.4 % of its 57 % target — it fills only from freed cash); 0 ERROR / 0 WARNING since the deploy, every job completed; all three dip positions GTC-stopped at the plan levels, 73–84 days from expiry; `backtest-mech --shadow --start 2026-10-29` runs on the CLI image (2 sessions, 0 trades); the backup pulled; the new research data archived on titanserver. Record: the Check 2026-10-30 section in decisions.md.
- [ ] **Still to verify**: the benchmark line's "too short to judge" wording from 20 trading days (≈ Nov 26; `n_days` was 0 at the Oct 29 refresh); the first ETF entry (gate 8 "not applied", GTC stop, `fill_price`, a ledger row) — no free slot until DXCM / URI / JPM exit; ~~the Nov 1 curator proposal names the shadow list~~ (the curator was retired 2026-10-30, Decision 082); DXCM / URI / JPM exit only by stop / target / clock. **Watch**: DXCM's 60-trading-day clock (≈ Jan 21) and its stop's 90-day expiry (Jan 22) fall within a day of each other — the 09:35 ET coverage job is the backstop. Next checkup ≈ 2026-11-12.
- [ ] Expectation (hindsight-free, now the only one): ~~+1.4 pp/yr vs SPY decade-like, DD ≈ −20 % vs −34 %, both halves positive, worst relative year −11~~ **restated 2026-10-30 on the exact path (Decision 081): ≈ +1.0 pp/yr vs SPY decade-like (first half −0.3, second +2.3), DD ≈ −19 % vs −34 %, worst relative year −11.5**; century +3.6 (a blend of research series). Go/stop rule = Decision 069 on the new window.
- [x] **Parameters re-checked on the ETF universe (2026-10-29, `etfparams.py`, Decision 070 addendum): no change** — the live cell is the only one positive in both decade halves and all four eras inside the book; the 062 sector-best (lookback 60, stop 20 %) is +0.5 on the decade and −0.5 on the century (era-dependent); the walk-forward's selected cells average +0.24 vs the live cell's +0.56 over five windows. Re-check with Tiingo's 1999 → ETFs (roadmap B11).

## Phase 2.8: Literature brainstorm → three tests run → go/stop rule needs recalibrating (2026-10-29) — Decision 068 addenda
Handover task: 30 candidates drawn from the systematic-trading literature, each with hypothesis, data, expected effect, test design and placebo, ranked by effect × survival probability ÷ cost (the table is the Decision 068 addendum "the literature brainstorm"). 15 of the 30 were already closed by Decisions 062–068; the book already holds the two families with a century behind them. Operator chose all three proposals; results in the addendum "the three chosen tests". Nothing live changed.
- [x] **T-bill carry on de-risked capital** (`scripts/param_search/carry.py`): +0.17 pp/yr on the decade, +0.52 on the century, no verdict flipped, drawdown unchanged. The paper account has recorded **no dividend activity at all** (SPY held through three ex-dates), so a T-bill ETF on paper is invisible → **go-live item, not a paper build**: at funding check whether the live account pays interest on cash; if not, SGOV as a third core leg sized `(1 − exposure_scale) × 95 %` (added to Phase 2.0).
- [x] **Shock early release on a +X % / N-session rebound** (`release.py`): **rejected** — every decade cell ≤ 0 and below its placebo, every century cell ≤ +0.06 with a worse drawdown; in every decade rebound the two-signal insurance was the binding rule, so the release had nothing to release, and where it acted (1932, 2008, 2022-06 bear rallies) it re-exposed into the next leg down. Closed door: a fast release for the shock trigger.
- [x] **The luck meter** (`luck.py`): decade t = 0.25, information ratio 0.08, bootstrap band −2.8 … +5.1 (a coin flip, deflated or not; half the +1.4 is lower volatility); century t = 3.16 (clears Harvey–Liu), bootstrap +1.9 … +5.2, PBO 0 %. Go/stop power: a true +1.4 pp/yr needs ~170 years to reach t = 2; a quarter fails "≥ SPY − 2 pp/yr" 43 % of the time; the drawdown leg as written (≤ 0.7 × SPY in every ≥ 10 % drawdown) fails the design's own backtest in 3 of 5 drawdowns.
- [x] **Go/stop rule recalibrated — operator's go, Decision 069 (2026-10-29)**: behaviour and drawdown decide, return is reported with its band and never judged under 3 years; rule text in Phase 2.0, code follow-ups (ledger, verdict wording) listed there, each on a go.
- [x] **Three more dip-sleeve tests run on the operator's pick (2026-10-29, `dipfilters.py`), all rejected**: the point-in-time Dow 30 as a hindsight-free quality list (−7.9 both halves; 19 of 20 random 30-name S&P lists lose too, median −2.7 — the curated list's +4 is the list, not "quality"); the dip relative to SPY (−4 to −5 on sectors: the anti-momentum trade; not both halves anywhere hindsight-free); the fast-dip filter (identical trades on ETFs, in-sample only on the S&P 500, one lucky cell). Closed doors recorded in the addendum. Catalogue rows 31–36 added (puts untestable, leverage and the dials recorded).
- [x] **Round three (operator: "pick up the research", 2026-10-29) — ten more rows run, none adopted** (`breadth2.py`, `entrymodel.py`, `sleeveweight.py`, `seasons.py`, `value.py`, `resmom.py`; results in the addendum "the rest of the catalogue"): member breadth (a random breadth beats both real ones on the decade — the era wants less insurance), the entry-time model (nothing predicts a trade, placebo-tested on 1,156 century trades), vol-managed momentum share (century-only +0.6 of timing, invisible on the decade — the one effect to remember), industry rotation beside SPMO (−1.1), gold 10 % (Sharpe +0.08 for −0.3 return on a gold decade), Halloween (negative in every phase), entry month (only Nov–Dec, not actionable), down-day entry (falling knife on single names), value sleeve (a drag long-only), residual momentum (a random pick). The catalogue is exhausted except the live-data items (gate valuation, curator ledger) and the untestable ones (puts, leverage).

## Phase 2.7: The two-sleeve book — Decision 068 build (2026-10-27)
Operator's go on the master-search recommendation. Built and tested locally; deploy pending the operator's explicit go (it changes the paper book).
- [x] Config: `momentum_ticker` SPMO / `momentum_weight` 0.6, `shock_drop_pct` 0.07 / `shock_lookback_days` 10 / `shock_hold_days` 20 / `shock_scale` 0.5, `overlay_slot_pct` = 10 % of equity; all in `MECHANICAL_FIELDS` and `data/watchlist.json`.
- [x] Fetch: the last 31 SPY closes in the bundle (`market_context.spy.closes`) for the stateless shock trigger.
- [x] Plan: `signals.shock_state`; `exposure_scale = min(insurance, shock)`; entries paused while either is on; `sleeve {ticker, weight, target_pct}`, `shock`, `exposure_scale` in `plan.json`; `core_target_pct` on the dip sleeve, `momentum_target_pct`; `strategy.json` gets `window_started_at` / `design 068` once; `benchmark_window_start()` anchors the daily benchmark.
- [x] Executor: SPY leg then SPMO leg (`manage_core_position(ticker=…)`); `_is_core_ticker` covers both; overlay cap and sector gate exclude both; gate 5 sizes on the dip sleeve.
- [x] 243 tests, ruff clean; docs updated (decisions, features, CLAUDE.md, architecture, data_schemas, risk_management, api_reference).
- [x] **Deployed 2026-10-27 17:32 UTC** (commit `7196d0d`): both images, CLI import check ok, health ok, 7 jobs, 0 errors; `signals` stamped the window (`window_started_at` 17:32:42 UTC); `fetch` + `signals` again so the bundle carries the 31 SPY closes (shock off, worst −2.4 %); first plan: SPMO target 57 %, exposure ×1.0, 3 held, 0 free.
- [x] **First execute 2026-10-27 17:35 UTC** (triggered on the operator's go): SELL 40 SPY @ $769.71 → BUY 216 SPMO @ $142.68 (27.5 % of equity), 2 actions, 0 warnings; book DXCM 23 % / URI 27 % / JPM 17 % / SPMO 27.5 % / cash 5 %, SPY 0.
- [ ] **Watch**: the 19:30 UTC run and the next days — SPMO stays inside its band (no churn), the Discord daily summary's plan field shows shock / exposure / sleeve target, no orphan-close attempt on SPMO, the benchmark line anchors at `window_started_at`; as DXCM / JPM / URI exit, SPMO fills toward 57 % and new entries come in at 10 % slots.
- [ ] **Verify at the next checkup**: SPMO rebalances only outside the 5 % band; no orphan-close attempt on SPMO; the benchmark line anchors at `window_started_at`; the first shock or risk-off event scales both legs and pauses entries.
- [x] **Post-crash tilt tested 2026-10-29** (`states.py --tilt`, Decision 068 addendum): tilting the momentum sleeve into the dip sleeve after a crash (3 triggers × 2 holds × 2 tilts, placebo) fixes 1932 / 2009 inside the rebound, beats the placebo on the century, and still nets −0.1 to −1.2 pp/yr over a century and within noise on the decade — the shape of the rebound is unknowable on the day. Not adopted.
- [x] ~~**Kept for later (operator)**~~ (closed by the operator 2026-11-03, Decision 091 — rotation is momentum in a worse vehicle, Decision 067 addendum): asset rotation as a sleeve (Decision 067 addendum: industry rotation top-10 by 12-1 monthly ≈ the momentum decile over a century; the stand-in if SPMO were unavailable).

## Phase 2.6: Three explorations — shorts, the current regime, a self-correcting universe (2026-10-27) — Decision 067 addendum
Operator asked for three more ideas after the master search; all three run with pre-registered hypotheses (`scripts/param_search/shorts.py`, `analogues.py`, `dynamic_universe.py`), none adopted, the recommended design unchanged.
- [x] **Shorts**: French WML overlay = leverage on the momentum bet (century +1.2 pp per 25 % of weight, Sharpe flat, 1932 crash doubled; decade Sharpe 1.10 → 0.97); short the market instead of cash = the insurance's trade-off doubled (century DD −59 → −48 % and 1929 +75, decade −3 pp/yr, rolling windows ahead 15–30 %); shock-only short −1 pp for 1.5 points of DD; **anti-dip mirror loses on every universe as a real short** (sectors −5, S&P −15, industries −4 %/yr of equity; the 1/P trick flatters shorts by up to 19 pp/yr). No short support to build.
- [x] **Regime analogues**: today = above SMA200, 12m +17 %, vol 9.5 %, at the high, breadth 45–55 %, momentum leading — "late, narrow, calm"; over the century the only state variables that move the forward year are breadth and the distance from the high; analogues (26–33 episodes) show a below-average forward year (median +4 to +6 vs +13, p10 −12 to −19) rather than a crash; the book's excess is positive in those states on the century but not stable across halves; decade cells hold 1–3 episodes. Descriptive only — no switching rule, as pre-registered. VIX not needed.
- [x] **Dynamic universe**: 17 / 22 / 28-ETF universes do not beat the sector floor in both halves (multi-asset 5 slots: +0.9, DD −23 %, Sharpe 1.16, all of it 2022 →); stop cooldown 60–250 sessions makes the S&P worse (−0.2 → −11.2) and nothing elsewhere; own-12-month eligibility > 0 = −8 to −10 on the S&P, the mirror = noise. Sector ETFs stay the hindsight-free floor.
- [x] **"Ten market types" cross product** (`states.py`): 8 state schemes (live two-signal, trend × breadth, drawdown × vol, k-means K = 4–12) × 2 action menus (book mix 19 / dip parameters 216) × walk-forward both ways × 20 placebo labellings, decade + century. In-sample gains +0.2…+9.5 = the placebo's; out-of-sample median −1.2, no cell survives both directions. The one state that matters (the rebound after a crash, where momentum collapses) tested with five published guards (`--momcrash`): ±0.2 pp, nothing. No state-conditional rule.
- [x] **Rotation sleeves** (`rotation.py`): 36 sector-rotation cells (1 positive both halves, concentrated), multi-asset / GTAA −5 to −10 pp/yr for their drawdown; century industry rotation top-10 by 12-1 = +5.1, 4/4 eras, Sharpe 0.95 in the book (best century number) — rotation is momentum, and SPMO already is that rotation inside the index at 0.06 correlation to the dip book. Nothing to add to Decision 068; industry rotation = the stand-in if SPMO were unavailable.
- [x] **Rotation timing** (`rotation.py --timing`): SPMO's schedule is the index's (semi-annual); in-house industry rotation over the century: monthly ≈ rank band 1.5 N (+5.2, 42 % less turnover) > quarterly / semi-annual (+4.4) > annual (+2.3); daily −1.1 (costs); trend-break marker −1.6 pp for 11 points less drawdown (book Sharpe 0.97); shock re-rank nothing; decade sectors ≈ 0 at every frequency, worse with every marker. Nothing to change in Decision 068.
- [x] Operator's go on Decision 068 given the same day → Phase 2.7.

## Phase 2.5: "Add the strategies together" — portfolio-of-sleeves research (2026-10-27) — Decision 067
- [x] Broad dip sleeve on the S&P 500: dead with point-in-time membership (−4 to −5 pp/yr every variant, both halves); the earlier +1.4 was look-ahead through future index members. Self-picked momentum names fail the reverse walk-forward.
- [x] Momentum ETFs held outright beat SPY in both halves (MTUM +1.7, SPMO +5.2); dip and momentum excess returns uncorrelated (+0.05 decade, +0.08 century); sector-dip 50 / momentum-ETF 50 = +1.9 (IS +1.5 / OOS +2.2), DD −28.9% vs −33.8%, 23 of 27 rolling 3-year windows ahead; century 50/50 ahead in all four eras.
- [x] **Master search run 2026-10-27** (`master.py`): 4,140 decade + 765 century books; a family emerged, not a cell — dip 30–50% / SPMO 50–70%, shock trigger on, no vol target, no own-momentum; insurance = the one era-dependent knob (bull-decade cost ~1.7 pp/yr, long-bear payoff +15–20 pp). Recommended: dip 40 / SPMO 60 + shock + insurance ×0.5.
- [x] **Operator decision 2026-10-27: GO** → Decision 068 built (Phase 2.7): 40 % dip book on the live list, 60 % SPMO, shock trigger −7 % / 10 / 20 / ×0.5, insurance ×0.5 on the whole book by min(), SPY residual, slots 10 % of equity, new clean window from `window_started_at`.
- [x] Crash scenarios page (every recorded bear, 4 books) and regime-switching test: slow regime rules add nothing beyond the live insurance; the shock trigger (SPY −7% in 10 sessions → ×0.5 for 20) cuts the worst drawdown by a third at 0–1 pp/yr, robust over 81 cells on the century. Recommended as part of Decision 068 (same `exposure_scale` mechanism, second trigger).
- [x] ~~If yes, open design points~~ (decided in Decision 068: 40 / 60, a 5 % band, the insurance as min with the shock trigger): sleeve weight (recommended 50/50), rebalance band for the sleeve, whether the insurance scales the sleeve ×0.5 like the rest (tested: costs ~0.5 pp/yr of the ETF's excess, cuts little drawdown — momentum crashes are not regime-flagged), minimum account size for 1 + 2 + 3 whole-share legs.

## Phase 2.4: Universe research — can a rule find the names? (2026-10-27) — Decision 066
- [x] Data: 742 S&P 500 members 2016 → 2026 with delisted names (Alpaca), French momentum / reversal / size×momentum deciles and 49 industries 1927 →; archived on titanserver `/home/TitanTrade/archive/param_search/`. Yahoo 1999 → still 429 (patient fetcher in the scratchpad; Tiingo key = clean fallback).
- [x] Eight pre-registered screens tested IS / OOS vs SPY and vs EW-all; momentum the only survivor (+5 median, flat 2017–21, 2026-heavy); low vol, conservative, LT reversal, anti-momentum rejected; near-high / smooth / quiet ≈ noise. Century: top momentum decile +5.1 pp/yr with its own crashes; guards don't help.
- [x] Dip rule × momentum picks = −14 pp/yr (3 slots): the overlay and momentum are antagonistic — momentum is harvested by holding. Trade-level entry features: nothing robust beyond the market regime (already in the design). Operator's list = high-vol, moderate-momentum names below their highs; +32% vs SPY +24% since Mar 30 at higher vol.
- [x] ~~**Operator decision**~~ (superseded: the momentum *ETF* sleeve, Decisions 067–068): build a momentum sleeve beside the SPY core (15 names, 6-1 or 12-1, yearly, equal-weight, no dip rule on them; expect +1–1.5 pp/yr at 30%, +3–5 at 100%, −20% relative years, ~90% turnover)? If yes: stage-3 walk-forward of the selection rule + a second universe (S&P 400) first, then a paper sleeve (new module, new Decision, both images).

## Phase 2.2: Cleanup after the conversion — legacy freeze, plan schema, app deleted (2026-10-13) — Decision 063
Operator: "larger cleanup — redundant code and docs, perhaps even the architecture"; answers: old LLM code → `legacy/` (not deleted), Flutter app → deleted, thesis/sentry schema → plain plan.
- [x] `legacy/` holds the LLM-era modules, their tests, the pyramid probe script, the full indicator suite and the prompt-engineering doc; tag `v2-llm-pipeline` = last commit with all 613 tests green. Not importable, not collected, not in the image.
- [x] `titan_trade_app/` deleted; dashboard-only endpoints removed; the API has 18 routes.
- [x] `state/plan.json` (`mechanical.build_plan` / `refresh_plan`) replaces `weekly_thesis.json` + `sentry_signals.json` + `signals.json`; the executor consumes NEW / HOLD items directly. Trade records carry `stop_price` / `target_price` (old spellings still read).
- [x] Eight gates (confidence gate removed); `handle_entry` = one near-market bracket + GTC stop on fill; `close_position_settled` for every exit — fixes the 40310000 orphan-close rejections of the 14:15 UTC first run (FCX / HCA / LLY were left bare until the manual trigger).
- [x] Config and env trimmed (Gemini, FMP, SEC, `strategy`, `risk_per_trade`, `stop_loss_pct`); `data/watchlist.json` settings = `trading_mode` + `mechanical`.
- [x] 236 tests, all mocked, ruff clean; docs rewritten for one system (CLAUDE.md, root docs, backend docs).
- [x] **Deployed 2026-10-13 14:47 UTC** (commit `9bf2754`): both images rebuilt and import-verified, API restarted, 7 jobs, first `signals` run wrote `plan.json` (3 HOLD items at the live stops, 0 free slots, FCX on watch at 8.3%, insurance on), `/api/plan` serves it.
- [x] **Verified 2026-10-16**: 5 execute runs on the plan path, 0 errors / 0 warnings in container and file logs, no thesis / sentry references, `portfolio.json` written before each daily summary, all 3 positions GTC-stopped at the plan levels, gapcheck "0 closed, 0 placed". Benchmark Oct 13–15 (2 td): −0.32% vs SPY −0.80% (noise).
- [x] **Decision 064 verified live 2026-10-20**: 0 expired-bracket lines in 5 runs incl. the first Sunday `full` (Oct 18); 1 WARNING in 4 days (FRED 502, retried); book and stops unchanged; breadth 45.5% → 54.5%.
- [x] **First exit seen 2026-10-26 — the broker stop**: DASH stop-limit filled at $168.74 (stop $169.75), −$3,459 / −12.5%; cooldown stamped with the fill price; the freed slot went to DXCM (325 sh @ $78.08, GTC stop $68.91) two minutes later, trimmed 25% → 23.2% by the cash reserve because SPY sat inside the rebalance band. Every step as designed.
- [ ] **Still to see live**: an exit through `close_position_settled` (target / holding limit / orphan). URI is the closest to the +20% target (+5.3%); the 60-day clocks on JPM / URI end 2026-01-08, DXCM's 2026-01-21.
- [x] ~~**Cosmetic**~~ (done 2026-11-03 on the operator's "make informational", Decision 091 — the slot-trimming flags log at INFO, the drawdown flag stays a WARNING; deploy pending): `entries` logged "Position reduced to N shares (cash reserve)" at WARNING; after any stop-out the next entry is cash-bound by construction (proceeds − 5% reserve), so this will fire on most entries. Downgrade to INFO with the slot and the cap stated.
- [x] **Disk 2026-10-27**: 58% → 43% (6.4 GB build cache from two rebuilds + 2 resevolve PG 15 orphans). Deploy routine now ends with `docker builder prune -a -f`.
- [x] **Decision 065 (2026-10-20)**: benchmark verdict + ratios withheld under 20 trading days; daily benchmark refresh anchored at the strategy start; "risk-off yes/no" wording in log / CLI / Discord; watch-list reason distinguishes "slots held" from "deeper dips took the free slot". 236 tests.
- [x] ~~**Watch, no action**~~ (moot since Decision 070 — the names are the shadow list): CRWD / ANET at 18%+ dips cannot be taken while the three slots are held by shallower entries — no rotation rule by design (Decision 062). Revisit only with a backtest of a swap rule, not before the next parameter search.
- [x] **Unread state files archived 2026-10-16**: `weekly_thesis.json`, `sentry_signals.json`, `signals.json`, `trailing_stops.json`, `pricecheck_signals.json`, `thesis_history.json`, `cik_cache.json`, `backtest_results.json` moved to `state/archive/legacy_2026-10-13/` (1.3 MB; the thesis history stays available for audits). `state/` now holds only the Decision 063 files.
- [x] **titanserver disk cleanup 2026-10-16** (operator's go): 6 anonymous dangling Postgres 15 volumes (resevolve orphans, 501 MB) removed after a PG_VERSION check, build cache pruned (6.8 GB), no dangling images; named resevolve volumes and both TitanTrade images untouched, all 16 containers up, API healthy. Disk 60% → 43%.
- [x] **Expired-bracket scan removed (Decision 064, 2026-10-16)**: `resubmit_expired_brackets`, `get_expired_brackets`, `MAX_BRACKET_ATTEMPTS`, the `resubmit` CLI / scheduler command and `handle_entry`'s `trigger` parameter deleted — the NEW-item path already re-enters after an expiry. 233 tests.
- [ ] **Technical debt left on purpose**: `scripts/param_search/` is research code (ruff E70x style only); `broker.py` (570 lines) and `benchmark.py` are unchanged from the LLM era and could lose a few unused helpers at the next pass.

## Phase 2.1: Parameter search on long history (2026-10-13) — Decision 062
- [x] Data: Alpaca SIP 2016 → (all 28 symbols; `download-history` switched to SIP) and Yahoo adjusted daily closes 1993/1999 → 2026 (SPY, QQQ, 11 sectors, 15 names). Stooq blocked (JS challenge); Yahoo needs `period1=0&period2=<now>` for daily granularity and a cookie jar.
- [x] Harness: `scripts/param_search/` (fastbt validated trade-for-trade vs `backtest/mechanical.py`; stage 1 grid 6,000 × 4 datasets; stage 2 insurance × sizing; stage 3 walk-forward of the selection procedure; plateau scoring).
- [x] Chosen plateau midpoint applied to `data/watchlist.json` settings.mechanical: dip 8% / 90 d / SMA150 / 60 d / +20% / −12%, 25% × 3 slots, insurance unchanged (SMA200, breadth 0.5, scale 0.5).
- [ ] **Watch**: the first weeks under the new parameters — candidate count per run (expect more than under 10%/60 d), the 70% overlay cap trimming the third slot, and that targets/time exits fire at 20% / 60 d.
- [ ] **Next search (not before 6 months of live data)**: extend the sector universe test with a hindsight-free *name* universe (e.g. the S&P 100 constituents as of 2010 from a point-in-time list), add a second hold-out era, and re-run stage 3 only. Add the exit-side variants from the 2026-10-27 outlier test (target 25–40% / none, hold 90–250, `trail_pct` 10–20%, now supported by `fastbt.py`) on the 1999 → datasets.
- [x] **Datasets rebuilt and archived 2026-10-27**: Alpaca SIP 2016 → for the 15 names + SPY + sectors (back from the server), **E** the S&P 500 as of 2016-01-04 (502 names incl. 94 delisted — survivorship-free) and **F** French 49 industries 1926 → (`scripts/param_search/datasets.py`); all under `/home/TitanTrade/archive/param_search/` on titanserver (copy back with the base64 pipe). Still missing: the Yahoo 1999 → files for B / C — Yahoo returns 429 from both machines; `scratchpad/yahoo_patient.py` keeps probing; when it succeeds, archive `data/param_search/yahoo` on the server too. If it never lifts, a free Tiingo key (operator sign-up) is the clean replacement.
- [ ] **Next search — add to the plan**: universe size × slot count (E: 3 × 25% deepest-first = −10 pp/yr adverse selection, 10 × 7.5% = +1.4) and the crash filter only on a broad universe (dip 8–20% +1.5 on E but 8–25% −1.9 — no plateau yet). The French century is the hindsight-free backbone for the exit-side variants (all within ±1 pp/yr out-of-sample).
- [x] **Outlier question answered 2026-10-27** (Decision 065 Evidence): the live design is not outlier-driven (best decile = 28% of gains, profitable without it); let-winners-run variants gain +5–6 pp/yr on the hindsight names and lose on the hindsight-free sectors in every variant — not adopted.

## Phase 2.0: Conversion to the mechanical strategy (2026-10-13) — Decision 061
Operator's call after the component audit: "fully convert with all the points made; the large parameter search comes after, on my call".
- [x] **Sentry and price-check exit authority retired**; broker stop + target + holding limit are the only exits (`executor._manage_held_mechanical`).
- [x] **LLM selection / direction / confidence retired**; `mechanical.py` generates the thesis file from the dip-in-uptrend rule with flat 20% slots (max 3); the nine gates and the bracket path are unchanged.
- [x] **SPY core is the residual** of exposure scale × 95% − overlay (`mechanical.core_target_pct`); **insurance** = two-signal confirmation (SPY < SMA200 and sector breadth < 50% → 50% exposure, no new entries).
- [x] **LLM reassigned**: monthly universe-curation proposal + post-mortem (`curator.py`, `curate` job, `/api/universe-proposal`). No orders.
- [x] **Backtester for the mechanical strategy** (`backtest/mechanical.py`, `backtest-mech`, `download-history --days N` with sector ETFs) using the same `signals.py` code as live; walk-forward helper and a coarse built-in grid.
- [x] Schedule rewritten (`data/schedule.json`); `strategy: "mechanical"` in `data/watchlist.json`; 612 tests green.
- [x] **Deployed 2026-10-13 12:42 UTC** (commit `bdc558a`, both images, 7 jobs, health ok); first signals run 12:43 UTC: strategy started, insurance on, DASH signal, 8 legacy positions queued for the 14:15 UTC orphan close. **Verify after the 14:15 UTC run**: legacy positions sold, SPY at ≈75% of equity, DASH bracket placed/filled at ≈20%, `/api/signals` served.
- [x] ~~Flutter app follow-ups~~ — the app was deleted in Decision 063 (unused); `/api/plan` replaced `/api/signals`.
- [ ] **Go/stop rule (recalibrated 2026-10-29, Decision 069; the Decision 061 wording is withdrawn)**: fund ≥ $25k only when, over the clean window since `window_started_at` (2026-10-27): (1) **behaviour** — every trade-log action is one the rules prescribe (entries on plan NEW items at the plan's levels; exits only by stop / target / holding limit / orphan close / core rebalance; exposure halved exactly on trigger sessions) and the median fill-vs-backtest gap (fill vs the next close after the signal) is reported at each checkup — by hand from `trade_log.json` vs `plan.json` until the ledger exists, no numeric threshold before 20 trades; (2) **drawdown** — at least one SPY drawdown ≥ 10 % in the window; in every SPY drawdown ≥ 10 % the book fell no further than SPY, in any ≥ 20 % at most 0.7 × SPY's fall; (3) **return** — reported with its bootstrap band, never a condition under 3 years.
- [x] **Decision 069 code follow-ups built 2026-10-29 (operator's go)**: (a) fill-vs-backtest ledger — `fill_ledger.py`, `fill_price` on the BUY record, `state/fill_ledger.json` appended by the daily summary, `GET /api/fill-ledger`, a Discord summary field; (b) benchmark verdict under 3 years → "Too short to judge the return … excess ±band" (`tracking_error_annual_pct`, `excess_annual_pct`, `MIN_RETURN_VERDICT_DAYS` 756), the summary line shows the band instead of α. 256 tests, ruff clean. **Not deployed — needs the operator's go** (both images). **Verify after deploy**: the first entry after the deploy gets a `fill_price` in the trade log and a ledger row at that day's 16:30 ET summary; the summary's benchmark line reads "excess … ±… pp/yr (too short to judge)"; `/api/fill-ledger` serves the rows.
- [ ] **Go-live checklist (Decision 071, answers researched 2026-10-29)** — what only the operator can do: (a) open / fund the live account at ≥ $25k (every ETF slot ≥ 13 whole shares; $10k is the floor, $5k hits the dust guard) with a W-8BEN on file (15 % treaty withholding on US dividends, which a live account does receive — paper does not); (b) in the Alpaca dashboard, Plans and Features: enrol in **High-Yield Cash** (up to 3.56 % APY variable, FDIC sweep, usable as buying power, non-PDT accounts) — if the account can enrol, leave `cash_ticker` off (**Decision 087: an ETF leg on top of the programme adds only +0.03 … +0.06 pp/yr at today's rate**); if it cannot, set `cash_ticker: "SHY"` (a 1–3-year Treasury ETF; Decision 080's proposal: +0.3 pp/yr over bills on fifty years, −0.1 in a 2020s-type regime; the leg is built, off by default; SGOV was the Decision 071 placeholder, IEF is the higher-return / rate-shock-exposed dial, the operator's call); (c) create one healthchecks.io check (free: 20 checks; schedule `35 16 * * 1-5`, timezone America/New_York, grace 2 h), put its URL in the server `.env` as `HEALTHCHECK_PING_URL`, `docker compose up -d api`, confirm the first ping after the next 16:30 ET summary; (d) the tax line to the advisor: dip-sleeve trades are taxable (inside the 3-year time test; 15 % / 23 % as other income; the CZK 100,000 gross-proceeds exemption will not apply at this size), the SPY / SPMO / SGOV lots become exempt lot by lot after three years (the CZK 40 m cap no longer applies to securities from 2026), US dividends withheld 15 % with credit; (e) read the server-down runbook once. Done by the agent: backups daily on the host + `scripts/pull_backup.sh` for the off-server copy at every checkup; the 90-day GTC expiry confirmed in Alpaca's docs (aged-order policy, cancelled at 16:15 ET on `expires_at`, re-placed by the 09:35 ET coverage job); the go/stop rule (069).

## Phase 1.37: October 13 checkup — ADR 059 verified live, bracket-leg stop coverage fixed, selection-vs-execution attribution (2026-10-13) — Decision 060
Sweep Sep 29 → Oct 12 close: 0 ERROR/CRITICAL in 3,029 log lines (14 d), 75 WARNINGs all expected (sentry noise/abort, cooldown override, ADJUST live-price floor ×3 on JPM, FRED 502 retries ×5), 8 scheduler jobs `completed`, both images = Sep 29 12:20 build, git clean at `ef42847`, AI $3.03 Oct-to-date ($6.30 Sep). Equity $112,682; 8 overlay positions + SPY core 34.5%, all 8 GTC stop-covered at check time, cash 6.3%. Disk 62% (build cache 7.3 GB, 6 dangling PG 15 volumes 498 MB).
- [x] **Decision 059 verified live:** `benchmark_metrics.json` computed Oct 12 20:30 UTC has `window_end = 2026-10-12` (fix 2 ✓). Override log lines read "≥1% above the $X exit" (fix 1 ✓): 3 overrides allowed (FCX Oct 2 +4.2% above the $68.91 exit, EQIX Oct 2 +3.0% above $998.13, EQIX Oct 9 +2.6% above $998.23), ≥5 evaluations refused (JPM ×2 at +0.0…+0.4% above the $333.08 exit, DXCM ×3 at +0.5…+0.6% above $83.91). Both refused tickers went nowhere: JPM $334.30 on Oct 12 (+0.4%) and was dropped by the Oct 4 review; DXCM re-dipped −5% on Oct 8 before +1.8%. DASH's legacy record (no `exit_price`) fired the old-wording override ×4 Sep 30 – Oct 2; every attempt was dust-blocked ($90–99 budget behind the pending DXCM bracket), so no harm.
- [ ] **Performance to Oct 12 (strategy / SPY):** new clean window since the Sep 29 deploy (9 td) **+1.05% vs +1.82%** (−0.77 pp; max DD −1.27% vs −0.66%); clean since Jul 8 (67 td) +4.22% vs +4.39% (beta 0.69, Sharpe 1.37 vs 1.54, up-cap 0.77 / down-cap 0.71, max DD −4.64% vs −3.38%); since the Aug 12 peak −1.56% vs +0.73%; since Decision 057 (Sep 2) +2.17% vs +1.69%; since Decision 046 (May 12) +11.41% vs +5.41% (CRWD-split polluted); inception +12.76% vs +23.12%. Go/stop rule (Phase 1.36) unchanged: no SPY drawdown yet (max −0.66% in the window).
- [ ] **Churn in the new window:** 5 exits (JPM Sep 30, FCX Oct 1, EQIX Oct 1, DXCM Oct 6, EQIX Oct 8), all broker stops at analyst levels, all losers, realised −$629 (FIFO on Alpaca fills); 3 of 5 re-bought within 7 d at a higher price (FCX +4.2%, EQIX +3.0%, EQIX +2.6%), re-entry gap ≈ $562. Exits + gap ≈ $1.2k ≈ 1.05% of equity ≈ the whole lag vs SPY. Watch: CRWD $258 and ANET $206.50 analyst stops sit 1.0–1.1% below the Oct 12 close.
- [x] **Fixed — bracket legs are DAY orders and the two post-fill paths disagreed (Decision 060).** A filled bracket's TP/stop legs inherit the parent's `tif=day` and die at 20:00 UTC. (1) Held ticker with `review_action == ADJUST` re-opened after the review: the Decision 056 guard `continue`d past *all* management, so the DAY legs expired and the position had no stop until the next market-open run — FCX none from Fri Oct 2 20:00 to Mon Oct 5 14:15; EQIX (Fri Oct 9 19:46 fill) none until Mon Oct 12 14:15. (2) `_manage_held_bullish`: Alpaca keeps the bracket's stop leg in `held` (not returned by `status=open`), so the executor saw "TP leg but no stop", cancelled the TP and placed a GTC stop at the *thesis* level instead of the adapted bracket's — EQIX Oct 2: $969.95 → $1000, tagged Oct 8 (−$119) and re-bought Oct 9 (+$128 gap); URI: $987.09 → $970. Shipped: `_ensure_coverage` / `_ensure_protective_stop` (one helper, both paths), `_coverage_stop_price` (entry-time stop from `trade_state.position_entry_stop` for positions newer than the review), `ensure_stop_coverage` run by the 13:35 gapcheck job and CLI. 9 tests (`tests/test_stop_coverage.py`), 587 total.
- [x] **Deployed 2026-10-13 09:29 UTC** (commit `452a6e1`): both images rebuilt (`api` + `titantrade`, both verified to import `ensure_stop_coverage` and carry the gapcheck wiring — the CLI image must be checked through its `uv run` entrypoint, a bare `/app/.venv/bin/python` cannot import the package there), API restarted, health ok, 8 scheduler jobs registered, smoke `ensure_stop_coverage(load_config())` → 0 (market closed, all 8 positions already covered) — 3.5 h before the day's 13:00 UTC fetch. **Verify at the next checkup:** no "has no stop, market closed" line after any fill; the 13:35 gapcheck result reads "N positions closed, M stops placed"; a re-opened ticker's GTC stop equals its trade-log `stop_loss_price`.
- [ ] **Selection vs execution (operator question, Oct 13)** — counterfactual in Decision 060 Evidence: over the clean window the analyst's equal-weight basket made +2.56% vs SPY +4.39% while the strategy made +4.22% — execution *added* 1.2–1.7 pp over passively holding the picks; since Aug 12 the basket lost 4.6% vs SPY +0.7% (selection drove the lag, execution recovered ~1 pp); only the Sep 29 → Oct 12 fortnight shows execution as the net cost (−0.6 pp, five stop-outs). Static buy-and-hold of every selected name beat the weekly re-selected basket by 2.7 pp — the weekly rotation is a drag. Next lever, if any, is the analyst's selection/rotation, fills-first test required before anything ships; the risk machinery stays frozen.
- [ ] **Watchlist size (operator question, Oct 13) — answered, nothing shipped** (Decision 060 Evidence 2): the analyst's weekly selection has no ranking skill at the weekly horizon (Spearman(confidence, next-week return) −0.05; selected +12.6% vs left-out +29.8% vs whole watchlist +18.6% vs SPY +5.2% since May 10). A bigger watchlist does not help a picker with no skill; the book is capital-bound anyway. Candidate follow-ups, fills/history-first: (a) 4-week-horizon version of the skill test; (b) trade the gated watchlist instead of the confidence-ranked subset; (c) universe curation. Not under the hold's strategy freeze until tested.

## Phase 1.36: September 29 checkup — exit-anchored cooldown override, closed-session benchmark equity, ATR floor rejected (2026-09-29) — Decision 059
Prompted by the operator's "the bot has been underperforming for months". Checkup (Sep 22 → Sep 28): 0 errors in 30 days, 8 jobs `completed`, $6.26 AI in September, both images current, every position stop-covered, cash 5.7%. Windows to Sep 28: clean since Jul 8 (57 td) **+3.18% vs SPY +2.71%** (beta 0.64, Sharpe 1.22 vs 1.09); since the Aug 12 peak **−2.55% vs −0.89%**; since ADR 057 +1.15% vs +0.06%; since ADR 046 +10.30% vs +3.72%; inception +11.64% vs +21.15% (all of it April). Verdict given: three months ≈ tie with SPY in a flat market; the lag since the peak is churn — 20 of 37 exits since Aug 13 re-bought within 7 days at a higher price ($1,915 re-entry gap ≈ 1.7% of equity). **Operator decisions (2026-09-29): keep the bot in paper, do not fund it, ship the data-backed fixes, judge the bot on a new clean window from the deploy date, and decide funding by the rule below.**
- [x] **Fix 1 — cooldown override recovery is measured against the exit price** (Decision 059 item 1): the cooldown record stores `exit_price` (abort mark / stop fill); `cooldown_override_allowed` also needs the current price ≥ 1% above it (`COOLDOWN_RECOVERY_PCT`). Calibrated on all 23 override-population re-entries since Jul 8: the 10 that came in < 1% above the exit all lost (−$767), the 13 ≥ 1% above kept every winner (+$2,250); ≥ 2% would have blocked CRWD's +$1,946 — rejected. `cooldown.py`, `entries.py`, `executor.py`, `price_check.py`, `notifier.py`.
- [x] **Fix 2 — benchmark `window_end` lag closed** (Decision 059 item 2): the Phase 1.35 Fix 5 verification failed (Sep 28 20:30 UTC file still ended Sep 25) because Alpaca's 1D equity point is stamped 20:00 ET; `benchmark._append_closed_session` now appends the `15Min` history's 16:00 ET bucket when the 1D series lacks the session. `benchmark.py`. **Verify at the first 20:30 UTC summary after the deploy that `window_end` equals that day.**
- [x] **Tested and rejected — ATR-scaled floor on analyst ADJUST raises** (the Phase 1.34/1.35 watch item): on 35 filled analyst ADJUST stops since May 12, keeping the previous level or clamping to `close − k×ATR` (k = 1.0–2.0) never beat the analyst's level over 5/10-day horizons (−$0.2k … −$3.6k) — the stocks fell through the wider level too. Closed; the Decision 058 live-price floor stays as the only ADJUST guard.
- [x] 578 tests green (17 new); touched files ruff-clean. Docs: decisions (059 with both evidence tables), features, risk_management, both architectures, deployment, insights, CLAUDE.md.
- [x] **Deployed 2026-09-29 12:20 UTC** (commit `2ed5698`): both images rebuilt (`api` + `titantrade`, both verified to contain `COOLDOWN_RECOVERY_PCT` / `_append_closed_session`), API restarted, health ok via the tunnel, 8 scheduler jobs registered, live `compute_benchmark(since=2026-07-08, persist=False)` smoke test clean — 40 min before the day's 13:00 UTC fetch. The 7 cooldown records on disk at deploy time (URI, EQIX, CRWD, FCX, GS, HCA, DASH) carry no `exit_price` and keep the stop-only override test until they expire (DASH's on Oct 1 19:30 UTC); every record written from now on carries it. **New clean window for the go/stop rule starts 2026-09-29.**
- [ ] **Go / stop rule for real money (operator, 2026-09-29)** — new clean window starts at the Decision 059 deploy date. **Fund** (≥ $25k, PDT floor) if after ≥ 3 months, including at least one SPY drawdown of ≥ 8%, the window shows (a) strategy return ≥ SPY return and (b) strategy max drawdown clearly smaller than SPY's in that drawdown. **Stop and index** if the window is still a tie or behind, or if the drawdown protection does not show up. Do not fund before the rule has been tested. Re-check the churn signature at every checkup: exits re-bought within 7 days (20 of 37 in the Aug 13 → Sep 28 window) and the re-entry gap in dollars.
- [ ] Housekeeping (titanserver): disk 61% — build cache 7.1 GB (`docker builder prune -a -f`) + 4 dangling PG 15 volumes (421 MB) pending the operator; untracked `data/historical_long/` to gitignore or delete.

## Phase 1.35: September 22 sweep — ADJUST live-price floor, in-run cash refresh, real days-held, Discord retry, SIP benchmark bars (2026-09-22) — Decision 058
Sweep of the live server (Sep 8 → Sep 21): 0 errors in 3,460 log lines, 8 jobs green, $4.61 AI, 536 → 562 tests, every position stop-covered, both images current. Clean window (`--since 2026-07-08`, 52 td): **+3.61% vs SPY +3.79%**, beta 0.68, Sharpe 1.44 vs 1.61, down-cap 0.76; since Sep 4 +0.66% vs +0.43%; since the Aug 12 peak −2.14% vs +0.13%. The Sep 8–16 dip (SPY −2.1%, fully recovered) produced 9 exits + 8 re-entries, realised −$1,934 — not the hold's "genuine drawdown" trigger. Five fixes, none a strategy change:
- [x] **Fix 1 — ADJUST live-price floor**: Sep 13 raised ANET $181 → $191 (1.29×ATR below Friday's close); Monday's 14:15 run placed it at $189.82 → filled instantly, ANET +8% within a week. New pure `pricing.adjust_stop_too_tight(live, new_stop)` (Decision 055's 1.5% floor measured from the live mark, also flags at/above); Section 4a keeps the existing stop when the raise is too tight, still places when there is no stop at all, fails open without a price. `pricing.py`, `executor.py` (`_position_live_price`).
- [x] **Fix 2 — in-run cash refresh**: ANET's bracket filled instantly on Sep 21 and vanished from `open_buy_commitment`; DXCM was sized against pre-fill cash → reserve 5% → 2.6%. Section 2 now re-reads the account after each executed entry (as `resubmit_expired_brackets` already did). `executor.py`.
- [x] **Fix 3 — real "Days held"**: every review prompt said "Days held: 0" (no `entry_date` on broker positions, no per-ticker `generated_at`). New `trade_state.position_opened_at` (shared with the Decision 056 guard) + pure `weekly_analyst._days_held_from`. `trade_state.py`, `weekly_analyst.py`.
- [x] **Fix 4 — Discord retry**: transport errors / 429 / 5xx retried twice (1 s, 2 s); a Sep 17 503 had lost a job notification. `notifier.py`.
- [x] **Fix 5 — SIP benchmark bars**: `benchmark_metrics.json` always ended one session early (IEX daily bar not published at 20:30 UTC). `get_ohlcv(..., feed=...)` override; SIP queries end at now − 16 min (free-plan recency rule, verified on the server). `data_providers/native.py`, `fmp.py`, `market_data.py`, `benchmark.py`. **Verify at the Sep 22 20:30 UTC summary that `window_end` = 2026-09-22.**
- [x] Withdrawn finding — "ghost" sentry checks on sold review-thesis tickers are the gate that stops Section 2 re-buying them under the stale thesis; left unchanged (Decision 058 §Withdrawn).
- [x] 26 new regression tests; **562 tests green**; touched files ruff-clean.
- [x] **Deployed 2026-09-22 10:19 UTC** (commit `bb77507`): both images rebuilt (`api` + `titantrade`, verified to contain the ADR 058 symbols), API restarted, health ok, 8 scheduler jobs registered — 2 h 40 min before the day's 13:00 UTC fetch.
- [x] **Fix 5 verification FAILED (Sep 29 checkup) → closed by Decision 059 (Phase 1.36)**: `benchmark_metrics.json` computed 2026-09-28 20:30 UTC still read `window_end = 2026-09-25`. The SIP side worked; the *equity* side lagged (Alpaca stamps the 1D point at 20:00 ET = 00:00 UTC next day). Fixed by appending the `15Min` history's 16:00 ET close.
- [x] Watch item — ATR-scaled ADJUST floor (strategy, parked): book on Sep 21 carries DASH 0.82×ATR, FCX 1.23×, JPM 1.30× analyst stops vs the 3.0× system trail. → **Tested on the fills and rejected, Decision 059 (Phase 1.36).**
- [ ] Housekeeping (titanserver): disk 60% — build cache 6.8 GB (`docker builder prune -a -f`) + 3 dangling PG 15 volumes (332 MB) pending the operator; untracked `data/historical_long/` (2.5 MB) to gitignore or delete.

## Phase 1.34: September checkup — sentry price-override corroboration fix (2026-09-02) — Decision 057
Checkup of the live server (Aug 18 → Sep 1): 0 errors in 15 days, all 8 jobs green, $3.24 AI cost, every overlay position stop-protected, both images current. Clean window (`--since 2026-07-08`, 39 td): **+2.58% vs SPY +2.19%, beta 0.60, Sharpe 1.39 vs 1.27, down-capture 0.73** — still adding value, edge narrower than on Aug 18. First pullback since the hold (Aug 12 peak → Sep 1, 14 td): **−3.11% vs SPY −1.41%, down-capture 1.16** — 11 exits and 9 re-entries in 10 sessions.
- [x] **Fix — `price_concern` no longer corroborates a 3–5% ABORT**: 36 of 39 "news-confirmed" ABORTs since ADR 045 had no headlines and no market concern, and Gemini's own reasoning called each move normal volatility. The flag is circular (the prompt shows Gemini the price alert and asks whether it is a factor). `daily_sentry.check_stock()` now confirms only on `conflicting_headlines` or `market_concern`. 2 regression tests; **536 tests green**; touched files ruff-clean (2 pre-existing E402s in the test module untouched).
- [x] Stale-doc fix: `docs/agent_instructions.md`, `TitanTrade/docs/agent_instructions.md`, `TitanTrade/docs/architecture.md` still described the pre-ADR-045 "3% hard override".
- [x] **Deployed 2026-09-02** on the operator's decision (this changes live abort frequency in the 3–5% band — the sentry sensitivity the 2026-06-22 hold froze): both images rebuilt (`api` + `titantrade`), API container restarted, 8 scheduler jobs verified, well before the day's 13:00 UTC fetch.
- [x] Watch item (closed by Decision 059 — tested and rejected, see Phase 1.36) — analyst ADJUST stops are noise-tight: Aug 30 set HCA $413 (0.49×ATR, 1.16% below close), FCX $73.60 (1.03×), DASH $228.50 (1.16×) → all three tagged at the Sep 1 open on a −0.7% SPY day; Aug 16's JPM $354 / ANET $184 / EQIX $1,055 / URI $1,094 (1.7–2.4×ATR) all tagged Aug 19–20 on a −1.3% SPY move, then re-bought higher Aug 24–25. The system's own trail is 3.0×ATR; the ADR 055 1.5% floor covers entries only. Candidate: ATR-scaled floor on ADJUST raises (keep the existing stop when the analyst's is tighter than ~1.5×ATR). Strategy change → parked under the hold. **Sep 22 sweep — 3rd occurrence:** Sep 13 review raised ANET $181 → $191 (1.29×ATR below the $199.74 Friday close); the Monday 14:15 run placed it while ANET traded $189.82 → filled instantly at $189.91 (−$104), ANET then rallied to $205 and was re-bought $202.36 on Sep 21 (22 sh vs 36). DVN's $47.75 (2.17×ATR) tagged a week later at breakeven. Book on Sep 21 carries DASH 0.82×ATR, FCX 1.23×, JPM 1.30× analyst stops. The `executor.py` ADJUST path has no live-price check at all — a stop placed at or above the market is a guaranteed exit, not a stop. Minimal non-strategy fix: apply the ADR 055 `stop_too_tight` 1.5% floor (entries-only today) to ADJUST raises against the live price. → **Decision 058 ships the non-strategy half**: the raise is now measured against the live price with the flat 1.5% floor (ANET's Sep 14 fill would not have happened); the ATR-scaled floor remains parked.
- [x] Watch item (closed by Decision 059 — recovery now measured vs the exit price, see Phase 1.36) — cooldown override is nearly always satisfied: "price recovered" = ≥1% above the *thesis stop*, which any 3–5% abort trivially meets, so the 72 h cooldown is effectively 24 h (EQIX: aborted $1,031.74 Aug 31 14:15, re-bought $1,032.65 Sep 1 15:13). Candidate: require recovery relative to the abort price. Parked. Sep 22 sweep: re-confirmed — overrides fired at 24.7 h (FCX), 27.6 h (JPM), 29.2 h (ANET).
- [x] **Defect (Sep 22 sweep) — `days_held` is always 0 in the weekly review** — shipped in Decision 058 (Phase 1.35): `trade_state.position_opened_at` + `weekly_analyst._days_held_from`.
- [ ] Cosmetic (Sep 22 sweep) — ghost sentry checks after a mid-week exit: review theses keep `selected_for_trading=True` after an abort/stop-out, so Gemini re-evaluated GE for 4 days after it was sold ("Catastrophic ABORT for GE" ×10, executor "no position to close"). Harmless (~$0.001/call), log noise; `daily_sentry.py` skip covers only the CLOSE + orphan-close case. → **Withdrawn on review**: for a review thesis with no position the price check (vs `target_entry_price`) is what stops Section 2 re-buying under the stale thesis; a synthetic CONTINUE would have let GE at −6% qualify for a 24 h cooldown-override re-buy. Left as is.
- [ ] Sep 22 sweep numbers (Sep 8 → 21): 0 errors, 8 jobs green, $4.61 AI, 536 tests. Clean window (52 td) **+3.61% vs SPY +3.79%**, beta 0.68, Sharpe 1.44 vs 1.61, down-cap 0.76; since Sep 4 +0.66% vs +0.43%; since the Aug 12 peak −2.14% vs +0.13%. The Sep 8–16 SPY dip (−2.1%, fully recovered) produced 9 exits + 8 re-entries, realised −$1,934 (FCX −$982 over two round trips). Not the hold's "genuine drawdown" trigger. Disk 60% (Docker build cache 6.8 GB from a resevolve rebuild + 3 orphaned PG15 volumes) — not cleaned. Fixes shipped as Decision 058 (Phase 1.35).
- [x] Housekeeping (titanserver): the three unreferenced images (`nginx:alpine`, `node:22-alpine`, `python:3.12-slim`) removed by name at deploy — ~130 MB real unique size; `docker system df`'s "14 GB reclaimable" double-counts shared layers. **Never `docker image prune -a` here**: the CLI image `titantrade-titantrade:latest` is unreferenced by any container by design and would be deleted (the ADR 054 stale-CLI-image gotcha in reverse). Same morning, on the operator's instruction: build cache cleared (`docker builder prune -a`, ~9.3 GB), the stale exited `titantrade-titantrade-1` container removed, and the 37 anonymous orphaned volumes removed (3.6 GB) — all were Postgres 15 data dirs or a resevolve pgadmin volume, i.e. resevolve leftovers (only resevolve runs PG 15 here). Disk 79% → 43%. Note: they accumulate ~1×137 MB per week (a resevolve job recreates a PG 15 container without `-v`), so expect them back.
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

## Phase 1.13: Bear Market Hedging & Execution Quality
- [x] Inverse ETF hedging: SH/PSQ/SDS analyzed in bearish/crisis regimes
- [x] Slippage model in backtester (0.15% per fill, configurable)
- [x] Slippage-aware limit exits for non-urgent ABORT signals
- [x] Limit sell function for executor (reduces market order slippage)

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

## Phase 1.10: Position Protection & Monitoring
- [x] Trailing stop mechanism (5% trigger, 3% trail below HWM)
- [x] Thesis expiry: force-close orphaned positions with no active monitoring
- [x] Dynamic entry price adjustment on bracket resubmission (current price awareness)
- [x] Lightweight intraday price checks between sentry runs (zero LLM cost)
- [x] Gap-down protection: detect unfilled stop-limits and market-sell immediately
- [x] New CLI commands: `pricecheck`, `gapcheck`
- [x] FastAPI HTTP server for Flutter app to connect remotely
- [x] Cloudflare tunnel integration (docker-compose with cloudflared service)

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

## Phase 1.8: Statistics & Cost Tracking
- [x] Operational cost logger (state/costs.json with per-API-call token usage)
- [x] Claude token usage capture in weekly_analyst.py
- [x] Gemini token usage capture in daily_sentry.py
- [x] Cost model and provider in Flutter app
- [x] Statistics screen: open positions P&L (unrealized)
- [x] Statistics screen: closed trades P&L with BUY->SELL round-trip matching
- [x] Statistics screen: operational costs breakdown by service
- [x] Statistics screen: net P&L (trading P&L minus operational costs)

## Phase 1.7: Trade Intelligence
- [x] All-gate evaluation in risk manager (no short-circuit, reports all failures)
- [x] Trade context snapshots (market regime, VIX, technicals, news at trade time)
- [x] Near-miss recording (blocked by <= 2 gates, saved to state/near_misses.json)
- [x] Watchlist write function (save_watchlist in config.py)
- [x] Enriched trade detail screen (context, gate results, risk flags)
- [x] Near misses screen + detail screen in Flutter app
- [x] Watchlist management screen in Flutter app (add/remove tickers)

## Phase 1.6: Infrastructure
- [x] Docker containerization (Dockerfile + docker-compose.yml + .dockerignore)
- [x] Server-based cron deployment documentation
- [x] Flutter desktop app project setup and foundation

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

## Phase 5: Desktop App (Trade Tracker) — deleted in Decision 063 (unused; the API is the only front end)
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
- Alpaca bracket orders are DAY-only (no GTC bracket): an expired entry is placed again at the next run while the signal holds, and a filled bracket needs its own GTC stop (placed on fill and by the 09:35 ET coverage job)
- Whole shares only: a 25% slot below one share is skipped (irrelevant above ~$5k equity at current prices)
- Positions are evaluated at two run times a day (10:15 / 15:30 ET); the stop is the only intraday protection, by design
- The strategy's edge on a hindsight-free universe is small (+0.5 to +1 pp/yr before insurance, Decision 062) and period-dependent; it loses to SPY in low-volatility bulls
- The benchmark window still carries the CRWD split artifact of July 2026 until it rolls out
- The API has no authentication of its own (Cloudflare tunnel only)

## Technical Debt
- `scripts/param_search/`: research scripts, not lint-clean (E70x), numpy-only, documented in their README
- `broker.py` and `benchmark.py` were not touched by the Decision 063 cleanup; a few helpers may be unused now
- `legacy/` is frozen and will rot against the current module layout — it is a reference, not a fallback (use the tag)
