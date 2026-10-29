# TitanTrade Roadmap

*Written 2026-10-29 after the first day of the mechanical book's second design (Decision 070). A living document: every item here is either done, ready to test with data in hand, waiting on the operator, waiting on live time, or closed with the evidence named. Results go to `docs/decisions.md`; the state of each item is updated here when it moves.*

**Status marks**: ✅ done · 🔬 ready to test (data in hand, pre-register and run) · 🔑 needs the operator (a key, a sign-up, a decision, money) · ⏳ needs live time · 🚫 closed — not to be re-proposed without the new evidence named in the row · 💡 idea, not yet designed.

**The standard every test meets** (Decision 062 → 068): hypotheses in the script docstring before the first run; hindsight-free universes (the sector ETFs, the French century; point-in-time membership for any single-name list); in-sample / out-of-sample halves both ways and the four quarter-centuries; judged against SPY *and* the equal-weight hold of the universe; costs charged; every state-, label- or timing-based idea against a placebo with the same count and shape; a grid finds a family, never a cell; the luck meter (deflated Sharpe, bootstrap band) on anything that survives. Nothing goes live from research: a Decision with the numbers, then the operator's go.

**The book today** (Decision 070): 60 % SPMO held · 40 % dip rule on the 11 sector ETFs (3 × 10 % slots, −12 % / +20 % / 60 trading days) with SPY as the residual · two-signal insurance ×0.5 · shock trigger ×0.5 · exposure = min · the hand-picked 15 names as a shadow list, tracked not traded · eight gates · broker-side GTC stops. Hindsight-free expectation: +1.4 pp/yr vs SPY in a decade like the last (both halves positive, worst relative year −11), +3.6 over a century with every quarter-century ahead, worst drawdown about a third smaller than the index's. The return edge is a century claim; the drawdown behaviour is the better-evidenced half.

---

## Track A — Live evidence (needs time, not ideas)

| # | item | status | what "done" looks like |
|---|---|---|---|
| A1 | **Checkup every 1–2 weeks** — log sweep, scheduler, every dip position stop-covered and nowhere near its 90-day expiry, benchmark over the clean window with its band, the fill ledger's median gap, `backtest-mech --shadow` beside the live sleeve, `scripts/pull_backup.sh`, the record in decisions/todo | ⏳ | first one ≈ 2026-11-05; the Oct 29 executes, the Nov 1 curator proposal on the shadow list, the first ETF entry, the first ledger row |
| A2 | **The go/stop rule** (Decision 069): behaviour (actions rule-prescribed, fills near the backtest's price), drawdown (never further than SPY in a ≥ 10 % drawdown, ≤ 0.7 × in a ≥ 20 % one), return reported with its band and never judged under 3 years | ⏳ | at least one SPY drawdown ≥ 10 % in the window |
| A3 | **The first real selloff** — the insurance and the shock trigger live for the first time; the rebound after it (the design's known cost) | ⏳ | what the backtest says: the book falls less, then lags for a year |
| A4 | **The shadow list's verdict** — the dip rule on the 15 names vs the live ETF sleeve, same window, year after year; is the operator's judgment skill or luck? | ⏳ | a multi-year record; the first number is meaningless |
| A5 | **The curator's skill** — the monthly proposals for the shadow list, shadow-tracked vs outcome (brainstorm #16, a small build) | 💡 build | a ledger like the fill ledger, one row per proposal |
| A6 | **The gates valued on live data** (brainstorm #17): earnings and macro blackouts vs what the blocked entries did | ⏳ | at 6 months of near-miss records; needs A2-style patience |

## Track B — Tests the new data unlocks (Decision 072; all hindsight-free; operator's go per test)

| # | item | status | expected / what would make it a Decision |
|---|---|---|---|
| B1 | **Put-writing vs the S&P**, 40 years of Cboe indices (PUT 1991 →, BXM 2002 →, BXMD / CNDR / RXM / CMBO / PPUT 1986 →, CLL 2008 →): the put-write index as a *sleeve* beside the book, and a *collar / protective-put index as the insurance* instead of de-risking to cash | 🔬 | published: PUT ≈ S&P return at 2/3 the volatility over decades. In the book: Sharpe up, return flat → a Decision only if it beats the 40/60 book in both halves and all four eras available. Trading it needs options on Alpaca (level 1–2) — a build of its own |
| B2 | **Quality over a century** — French profitability (OP) and investment (INV) sorts daily 1963 →, AQR QMJ daily: does profitability carry a premium like momentum, does it crash differently, and does a dip rule on high-profitability portfolios behave like the sectors (diversified, no breaks) or like single names? | 🔬 | the quality question answered before any fundamentals pipeline. A Decision only if a quality sleeve adds to the book in both halves and the eras — the momentum-sleeve bar |
| B3 | **Trend and carry over a century** — AQR Century of Factor Premia (monthly, 1920s →) and TSMOM factors: the trend-following family judged on the operator's own eras without futures data; is a trend premium diversifying for *this* book? | 🔬 | published Sharpe 0.7–0.8 gross; the catch is instruments: futures are not on Alpaca, so a surviving result becomes an ETF-proxy question (DBMF / KMLM from 2019) — probably knowledge, not a sleeve |
| B4 | **Rates by era** — bills since 1954 (FRED) and French RF: the carry on idle cash and the insurance's cost priced on real rates per era; the T-bill leg's value when rates are 0 vs 5 % | 🔬 small | numbers for the go-live decision on the cash sweep vs the SGOV leg (Decision 071) |
| B5 | **Credit and stress as a second insurance signal** — NFCI / ANFCI 1971 →, STLFSI 1993 →: a *different population* than breadth (member breadth failed because the decade wants less insurance; the century had no breadth of its own) | 🔬 | the breadth2 standard: a placebo (block-shuffled series) on both eras; prior low — "the era is talking" lesson |
| B6 | **A VIX-based shock trigger** — VIX > X or a VIX jump instead of a −7 % fall; VIX 1990 → | 🔬 | the shock trigger's 81-cell robustness as the bar; prior: ≈ the price rule, maybe a day faster; a Decision only with a plateau and both eras (1990 → only, so one era) |
| B7 | **Gold over a century** — datahub monthly 1833 → against the French market: a permanent 10 % gold sleeve was a decade-only test (Sharpe +0.08 for −0.3 return); the century says whether that was the 2020s | 🔬 small | reopens brainstorm #12 with hindsight-free data; a Decision only if the century agrees with the decade |
| B8 | **Bonds as the de-risk destination** — Treasury yields since 1954 / 1962 → a constant-maturity total-return series: de-risk into bonds instead of cash; a bond sleeve (closed on the decade by 2022) | 🔬 | the multi-asset verdict (−5 … −10 on the decade) re-judged on 60 years; low prior in the 2020s rate regime |
| B9 | **Fundamentals pipeline** (SEC financial-statement data sets 2009 →): a profitability filter for a *single-name* dip universe | 💡 after B2 | only if B2 finds that profitability separates dips from breaks; otherwise the single-name door stays closed (Dow 30 and 19 of 20 random lists lose) |
| B10 | **Earnings dates history** (Alpha Vantage, free key): the earnings gate valued on a decade instead of six months of near misses | 🔑 then 🔬 | the gate costs or saves ≤ 0.2 pp/yr either way |
| B11 | **Longer investable history** (Tiingo, free key): sector ETFs and the 15 names 1999 →, covering 2000–02 and 2008 on real ETFs | 🔑 then 🔬 | the sector floor and the insurance's cost on two more bears; the vol-managed share (C1) on investable data |

## Track C — The freedom areas (where new ideas can still come from)

### C1 Risk preference — the dials the evidence does not set

| item | status | note |
|---|---|---|
| **Momentum weight 60 → 70** | 🔑 decision | +0.5 … +0.9 pp/yr on the decade, a bumpier ride (DD −21 vs −20, Sharpe −0.03); the century wants more momentum. A preference, measured |
| **Insurance on / off** | 🔑 decision | off = +1.6 on the decade, −15 … −20 in a 1929 / 1973 / 2008. The operator keeps it on; revisit only with a stated drawdown tolerance |
| **Volatility-managed momentum share** (Barroso–Santa-Clara, long-only) | 🚫 until B11 or a live momentum crash | the one century-only survivor (+0.3 … +0.4, beats its placebo, Sharpe 0.86 → 0.90), invisible on the decade; reopen when investable data covers a momentum crash |
| **SPMO vs 30 / 30 SPMO + MTUM** | 🔑 decision | ~1 pp/yr this decade for diversification of index-construction risk; the century cannot separate them |
| **Leverage to SPY's volatility** | 🚫 until live proof | +1.5 … +2 net *if* the live book keeps its Sharpe; scales every drawdown; never before years of live evidence |
| **The operator's stated risk preference** (2026-10-29) | ✅ stated | No fixed numbers: "there is always a trade-off; something that projects a high return but hurts the safe side I will evaluate case by case; the future belongs to those willing to take risks." Two named fears: **an AI-bubble burst** and **a weaker US market after a political change** (the current strength suspected to be policy-flattered). Replayed on the data: in the three bubble bursts we have (1929, 1973, 2000) the book fell −58 / −27 / −32 vs the market's −84 / −48 / −49, the momentum sleeve fell with the market every time (it *is* the leaders), the dip sleeve was flat at the 2000 trough and +97 five years on; the book was +13 five years after the 2000 peak vs the market's −18. A US lost decade is real history: 2000–2009 US −0.4 %/yr vs developed ex-US +2.5, Europe +3.3, and EUR/USD went 0.90 → 1.60 in 2002–08 — for a CZK-based investor the dollar is the larger risk. Consequences: the 40/60 split stands (50/50 is the cheap extra bubble insurance, ≈ −0.3 pp/yr); Track E (other markets) and the currency question move to the front; B1's collar index prices an explicit hedge |

### C2 Information — inputs beyond prices

| item | status | note |
|---|---|---|
| Fundamentals (profitability, leverage, accruals) | B2 → B9 | the century sorts first, the pipeline only if they say yes |
| Earnings dates and surprises | B10 | the gate, and whether a dip *into* earnings is different (Decision 066: nothing at entry predicts a trade, but earnings were not a feature) |
| Option-implied information (VIX term structure, SKEW, VVIX) | B6, then 💡 | as a regime input it will meet the placebo; the analogue verdict stands until a pre-registered test beats it |
| Positioning (CFTC) and leverage (FINRA margin) | 💡 low | "who is crowded" as a state variable → the states.py machinery with its placebo; prior low |
| Sentiment surveys (AAII walled, NAAIM manual) | 💡 low | contrarian signals are weak and already priced in the literature's post-publication decay |
| News / text | 🚫 | the LLM era's lesson (Decision 060): no skill at the horizon this book trades |

### C3 Instruments

| item | status | note |
|---|---|---|
| **Options** — put-writing as the dip entry, collars as the insurance | B1 | the indices answer the question; trading them is a separate build (Alpaca options) |
| **International equities** | Track E | the one instrument class with a diversification case for *this* book |
| Futures (trend, carry) | B3 → 🚫 trading | not on Alpaca; a second broker is a project of its own |
| Shorting | 🚫 | Decision 067 addendum: WML = leverage on momentum, short-the-market = the insurance doubled, the anti-dip mirror loses as a real short |
| Bonds, gold, commodities | B7, B8 | reopened on long data only |
| **Crypto momentum sleeve** (Alpaca trades crypto; BTC / ETH daily is free from Coinbase, 2015 →) | 💡 explore, health warning | time-series momentum in crypto is a documented premium with 70–80 % volatility and 80 % drawdowns; the 2010s are one bubble-shaped sample. A sleeve of a few percent is the only size that could survive the drawdown leg; test with the discipline, expect a placebo-level result, record it either way |
| **The volatility risk premium** (Cboe VPD / VPN indices 2004 →; short-VIX ETFs 2011 →) | 💡 explore, with B1 | selling volatility is the same family as put-writing with a worse tail (2018-02); B1's indices answer most of it; VPD / VPN to be added to the fetcher |

### C4 Judgment — where the human stays

| item | status | note |
|---|---|---|
| The shadow list (A4) and the curator ledger (A5) | ⏳ / 💡 | measure the judgment, never bet the sleeve on it |
| The universe as a parameter | ✅ principle | a watchlist change is a strategy change (Decision 065); the ETFs are the hindsight-free universe, the names the measured bet |
| The operator's risk line (C1) | 🔑 | the one judgment the data cannot replace |

### C5 Operations — where live systems fail

| item | status | note |
|---|---|---|
| Backups (daily on the host, pulled off-server at every checkup), heartbeat (URL pending), the server-down runbook, the 90-day GTC expiry | ✅ / 🔑 URL | Decision 071 |
| The fill ledger — live fills vs the backtest's price | ✅ built, ⏳ data | the behaviour leg of the go/stop rule |
| Execution timing (10:15 vs 15:30 vs close; Alpaca minute bars) | 💡 low | turnover is ~60 % of equity a year: 10 bp = 0.06 pp/yr |
| The go-live checklist (fund ≥ $25k, W-8BEN, the cash sweep or the SGOV leg, the heartbeat, the tax line) | 🔑 | Decision 071, todo Phase 2.0 |
| A second broker (international single names, futures) | 💡 later | only if Track E or B3 produces something the first broker cannot trade |
| **Tax-aware lots when live** | 💡 at go-live | ask Alpaca for the lot-selection method; the three-year test is per lot and FIFO sells the oldest lots first when the exposure rules cut SPMO (Decision 071) |
| **Risk budgeting across books** | 💡 with E3 | a second book shares the account: the cash reserve, the overlay cap and the drawdown breaker must be per book or the two books starve each other |
| **The benchmark once the book is not US-only** | 💡 with E3 | SPY is the yardstick today; a global book is judged against ACWI, and a CZK-based operator may want the yardstick in crowns |

## Track D — Closed doors the new data could reopen (and the ones it cannot)

| closed door | reopened by | status |
|---|---|---|
| Put-writing ("untestable here") | Cboe indices 1986 → | **reopened → B1** |
| Gold 10 % (decade-only, 2020s-flattered) | datahub gold 1833 → + French market | **reopened → B7** |
| Bonds / multi-asset de-risking (decade-only, 2022-hurt) | yields 1954 → | **reopened → B8**, low prior |
| Volatility-managed momentum share (century-only survivor) | Tiingo 1999 → (B11), a live momentum crash | **parked → C1** |
| Member breadth, credit as the insurance's second signal | NFCI 1971 → is a new population | **reopened → B5**, placebo-standard |
| Shock trigger on VIX | VIX 1990 → | **reopened → B6** |
| Quality / low-beta as vehicles (USMV, QUAL rejected) | French OP / INV sorts, AQR QMJ / BAB over 60–90 years | **reopened as B2** (a century, not an ETF decade) |
| Value sleeve | AQR VME, French BM | 🚫 stays closed: long-only value is a drag in a bull decade and a wash over the century; the AMP diversification is long-short |
| Any single-name dip universe (Dow 30, random lists, S&P 500) | fundamentals (B9) | 🚫 unless B2 says profitability separates dips from breaks |
| Relative dip, fast-dip filter, down-day entry, entry month, Halloween | — | 🚫 no new data bears on them |
| Residual momentum, industry rotation beside SPMO, let-winners-run, ATR stops, crash filters, stop cooldowns, own-momentum eligibility, ten market types, regime switching, post-crash tilt, momentum-crash guards, shorts, shock early release | — | 🚫 closed with numbers in Decisions 062–068; the new data does not touch the mechanism |
| The entry-time model ("can AI pick the trades") | — | 🚫 closed on 1,156 century trades with a placebo |

## Track E — Other markets (diversification)

**The case.** The book is 100 % US equities; the operator is not. International equities are the one instrument class with a real diversification argument for this book: the lost decades differ (Japan 1990–2010, the US 2000–2010, Europe 2007–2017), momentum premia exist in every developed region (French's regional momentum factors), and country or region ETFs are *diversified baskets* — the only universe class on which the dip rule has ever been ≥ 0 (sectors), never single names. The honest caveats: equity correlations converge to 0.8–0.9 in crashes, so the diversification is in the decades, not in the week that hurts; US-listed international ETFs carry the dollar; and single foreign stocks are not on Alpaca.

| # | item | status | note |
|---|---|---|---|
| E1 | **Data**: French regional factors and momentum daily (Developed ex-US, Europe, Japan, Asia-Pacific ex-Japan, Developed; Emerging monthly) 1990 →; 39 region / country ETFs on Alpaca 2016 → dividend-adjusted (`data/param_search/alpaca_hist/intl/`: ACWX VEU IEFA IEMG EFA EEM VGK EZU EWJ EPP AAXJ, 20 country funds, IMTM IDMO IQLT IVLU, hedged DBEF HEDJ, VWO VXUS VT) | ✅ 2026-10-29 | MSCI country index histories (longer, daily) are a manual download from MSCI's tool; Tiingo (B11) for 1999 → ETFs |
| E2 | **Pre-registered test — the international book** (`scripts/param_search/intl.py`, hypotheses I1–I7 committed before the run): (a) the momentum premium by region on French data 1990 →; (b) IMTM / IDMO held vs ACWX; (c) the dip rule on the 20 country ETFs vs ACWX and vs the equal-weight basket; (d) the correlation of the ex-US two-sleeve book with the US book; (e) the global blend US 50–90 / ex-US with two placebos; (f) through 2025; (g) the euro view | ✅ run 2026-10-29 → **Decision 073: no ex-US book, no blend** | **Held**: the momentum premium is real and stronger ex-US than in the US over 1990–2026 (Developed ex-US WML +7.4 pp/yr, t = 4.7, both halves; Europe +9.9, Asia-Pacific ex-Japan +10.8; Japan +0.6 = none), and a long-only ex-US momentum ETF captures it (IDMO +4.3 vs ACWX, IMTM +1.4, both halves). **Failed**: the dip rule on country ETFs is not a sector floor (−0.9 in the first half vs ACWX, −1.5 through 2025 — the whole positive is 2026); the two books' active returns correlate 0.58 (the exposure rules make both books the same bet, the market's fall); every blend gives back 0.7–3.8 pp/yr vs SPY, no better than holding ACWX in the slot, and none is positive vs SPY in both halves. Knowledge kept: the dollar fear is real in history (2002–08: US stocks −4.9 %/yr in euros while ex-US made +3.5) and round-trips over the euro era (1999–2026 US +9.2 vs ex-US +6.7 in both currencies) |
| E3 | **Build, if E2 survives**: a second book on Alpaca under the same engine — region ETFs as the dip universe, an ex-US momentum ETF as the sleeve, ACWX as the residual | 🚫 closed by E2 (Decision 073) | reopened only by a hindsight-free country-ETF universe on which the dip rule is ≥ 0 in both halves (Tiingo 1996 → country ETFs, B11, would add 2000–02 and 2008), or by a pre-registered ex-US momentum-ETF share of the SPMO sleeve (C1 dial: IDMO held alone in a 10–20 % slot — priced in Decision 073, not a result) |
| E4 | **Currency**: the operator is CZK-based; USD-denominated ETFs embed the dollar; hedged variants exist (DBEF, HEDJ) | 💡 priced once | Decision 073 reference: the dollar drifted −0.7 %/yr against the euro over 2017–2026, so every decade number in euros is ≈ 0.8 pp lower (US book 15.8 %/yr in euros vs SPY 14.5); DBEF (hedged EAFE) beat EFA by +2.3 pp/yr this decade (+0.3 / +4.3 — the rate differential since 2022, not a currency call). A hedge for the US book itself would be a USD/CZK forward, which Alpaca does not offer; the question stays open as a go-live item, not a research one |
| E5 | **Single foreign names** (European / Asian stocks) | 💡 far | needs another broker and point-in-time index membership per market; everything learned about single-name universes in the US (Decision 070) applies first |

## Track H — Data still worth collecting

| item | status | why / how |
|---|---|---|
| **Tiingo** — 30 years of adjusted daily history for ETFs and names (free key, 50 symbols/hour) | 🔑 | B11: the sector floor through 2000–02 and 2008 on real ETFs; the 15 names 1999 →; the ETF parameter re-check on two more bears |
| **Alpha Vantage** — historical earnings dates per symbol (free key, 25 requests/day) | 🔑 | B10: the earnings gate valued on a decade |
| **MSCI country and regional index histories** (daily, 1970s →; the end-of-day tool is a manual download) | 🔑 manual | Track E over 1970 → instead of 1990 → / 2016 → |
| **Cboe VIX premium indices (VPD, VPN) and VIX futures settlements (per-contract CSVs)** | 💡 add to the fetcher | the volatility-risk-premium exploration (C3); the futures term structure as a regime input, placebo-tested |
| **Crypto daily (BTC, ETH) from Coinbase, 2015 →** | 💡 add to the fetcher | the crypto-sleeve exploration (C3) |
| **FOMC meeting dates 1936 → (the Fed's site) and release calendars** | 💡 | the macro gate valued on history (A6 needs live data otherwise) |
| **S&P 400 / 600 point-in-time membership** (public GitHub lists) | 💡 | only if a single-name universe ever returns (Decision 070 closed it; B9 could reopen it) |
| **Alpaca minute bars 2016 →** (our own keys) | 💡 on demand | execution timing (C5), worth 0.06 pp/yr at this turnover |
| **The full SEC financial-statement data sets 2009 →** (≈ 5 GB) | 💡 on demand | B9, only after B2 |
| **What is not worth money today**: option chains ($100 / year) — only if B1 outgrows the Cboe indices; EODHD (€20 / month) — only if Tiingo's free tier is too slow | 🔑 later | |

## Track F — Method, tooling and cleanup

| item | status | note |
|---|---|---|
| **One engine for research and live: the two-sleeve book in the package backtester** | 💡 the most valuable cleanup | `backtest/mechanical.py` still models the dip-only book of Decision 061; the live design (SPMO leg, shock trigger, min(), 10 % slots, the 5 % band) exists only as a post-hoc blend of daily returns in the research harness, which assumes constant 40 / 60 weights rebalanced daily — not what the executor does. "Backtest what trades, trade what you backtested" (Decision 061's lesson) is currently broken for the sleeve. Path-exact two-sleeve backtester in the package → `backtest-mech` reproduces the live book, the fill ledger compares against the real path, and the research harness can call it instead of `master.book` |
| **Deduplicate the harness** | 💡 small | twenty-five scripts rebuild the same series (`carry.sets()`, `master.decade()`, `regimes.main()` each load the decade and the century); `search.py` duplicates `datasets.py`; `analyze1.py` duplicates `analyze1_lib.py`. One `books.py` with the recommended-book builders, every script importing it. For the next agent, not for the numbers |
| **Loaders for the external library** | 💡 on demand | one function per source in `datasets.py` as each test needs it (Cboe CSV, FRED CSV, CFTC annual.txt, Shiller / AQR xlsx via `--with openpyxl`); the manifest is the index |
| **Reorder `docs/todo.md`** | 💡 cosmetic | phases 2.0 → 2.12 are interleaved from a day of appending; newest first, consistently, with the open items at the top |
| **A plain-language "how to read a checkup" page** | 💡 docs | the operator asked for plain words first: one page that says what each number on the checkup means (the band, the median fill gap, the shadow comparison, the drawdown leg) and what would make it a problem |
| The luck meter in every result (deflated Sharpe, bootstrap band, PBO) — fold into `master.score` | 💡 small | `luck.py` exists; make it automatic |
| **A chaos test for broker anomalies** | 💡 ops | the CRWD split lesson (Decision 054): a test that feeds the executor a phantom price, a ±50 % equity jump, a cancelled stop, a 40310000 rejection, and checks nothing bare or doubled results. The guards exist; the drill that exercises them together does not |
| Parsers for the new data (xlsx / xls / CFTC / Shiller) | 💡 on demand | `uv run --with openpyxl`; one loader per source in `datasets.py` as each test needs it |
| The backtester / live equivalence check at every checkup (fill ledger, plan actions) | ✅ built, ⏳ | Decision 069 leg 1 |
| The deploy procedure for config + code changes (build api → stop → swap → up → build CLI → retire the staged file) | ✅ | Decision 070 |

## Track G — Toward real money

The order the evidence imposes: A1 checkups → A3 the first selloff (the drawdown leg) → the go-live checklist (C5) → fund at ≥ $25k with the cash sweep or the SGOV leg → the return judged only after three years, with its band. Nothing in Tracks B–E changes that order; they change what the book *is* when it goes live, and each change restarts the clean window.

---

**What I would run first, in order** (revised 2026-10-29 after the operator's risk statement): ~~E2 (the international book — the one fear the US-only book cannot hedge)~~ run the same evening → Decision 073, no book; then B1 (put-writing and the collar indices — the explicit hedge, priced), B2 (quality over a century), then B5 / B6 / B7 as cheap afternoon tests; in parallel the one cleanup that matters, the two-sleeve book in the package backtester (Track F). Everything else waits on a key, a decision, or live time.
