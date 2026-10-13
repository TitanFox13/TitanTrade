# Insights & Lessons

## Design Insights

### Why Software Stop-Losses Are Dangerous
A stop checked by a cron job fires twice a day. Overnight a stock can drop 15–20% on earnings or macro news, and by the morning run the "stop" fires far below the intended level. Alpaca's native `stop_limit` orders live on the broker's servers and trigger the moment price touches them, whether or not the bot is running. Every held position carries one.

### Bracket Order Nuance
Alpaca brackets are DAY orders: an entry that does not fill by the close expires with its legs, and after a fill the exit legs expire at 20:00 UTC too. The stop leg also sits in `held` while the take-profit leg is live, so it is invisible to the open-orders query. Hence two mechanisms: expired brackets are resubmitted the next morning at a fresh price, and a filled bracket gets its own GTC stop (the TP leg is cancelled, which takes the held stop with it, and a GTC stop is placed at the bracket's level).

### JSON as a "Poor Man's Database"
A 15-name watchlist with a few runs a day fits in a handful of JSON files under 100 KB. No database, no migrations, no connection pooling; jobs run sequentially inside one scheduler so there are no concurrent writes. Append-only files archive themselves past a size cap.

### Stop-Loss as Insurance, Not Strategy
The −12% stop exists to bound a position's loss, not as a signal. Tighter stops tested as pure churn (Decision 059); the stop width barely moved the backtest (Decision 062, 8–20% flat), so it is set where it stops a disaster and stays out of normal volatility.

## API Insights

### Alpaca Paper Trading
- Paper fills are at the last price (no slippage simulation); the backtester charges 0.05% per side instead
- A cancel must reach a terminal state before a market sell on the same qty, or the sell is rejected with 40310000 "insufficient qty available"; the stop placed after a fill can hit the same race and must poll the blocking order from `related_orders`
- IEX daily history starts in 2020; SIP from 2016, and a SIP request must end ≥ 15 minutes in the past on the free plan
- Corporate actions are processed on the position days after the market trades post-split (the CRWD lesson below)

### Free Market Data
- FRED has the release calendar but not FOMC dates (`data/fomc_dates.json`); Finnhub has earnings and sectors; both fail open when the key is missing
- Yahoo's chart endpoint returns daily bars only with `period1=0&period2=<now>&interval=1d` (`range=max` is monthly) and needs a cookie jar and pacing; Stooq is JS-walled (Decision 062)

## Operational Insights

### Broker Data Is Not Ground Truth (the CRWD Split, Decision 054)
CRWD split 4:1 on 2026-07-02. The market traded post-split (~$193) from the open, but Alpaca paper adjusted the *position* three trading days later. In that gap the account showed a 15-share position "crashing" 71% below its stop, and gap-down protection sold a healthy position at the artificial bottom. The live-quote cross-check passed, because the quote genuinely was $193 — **a real price can still be a broker-state artifact**. Days later the same processing made `GET /v2/account` briefly report $22,828 against a real ~$100k equity, tripping the drawdown breaker at a phantom "79.1%". Lessons baked into code: a > 30% gap checks the corporate-actions feed before liquidating; a single account value ±50% off the peak is treated as corruption (alert, sit out one run, never written to state); phantom swings pollute derived analytics until they roll out of the window.

### Dust Orders Are Pure Downside
Sizing that "reduces to fit" can shrink an order to slivers (production: 0.01 URI shares = $11). Dust fills, pays fees and churns like a real trade but cannot carry a stop. The $500 minimum-notional floor turns these into clean near-miss records (Decision 054).

### The Tight Stops Weren't the Churn — the Flat Re-Buys Were (Decision 059)
Four checkups blamed tight stops for the sell-the-dip / buy-the-rebound cycle. Tested against 35 filled stops, no wider alternative beat them. The money was lost one step later: the re-entry test was trivially met, so the system re-bought the same name at the same price a day later. Of 23 such re-entries, the 10 that came in < 1% above the exit all lost; the 13 that came in ≥ 1% above kept every winner. Attribute churn to the *re-entry* rule before touching the *exit* rule, and test the fix on the fills before shipping it.

### A Safety Invariant Needs One Owner (Decision 060)
"Every whole-share position has a GTC stop" was enforced by two code paths that disagreed and a third that skipped the check. An invariant that matters gets one function, called from every path that can break it, plus the earliest job of the day as a backstop.

### Every Exit Is the Same Exit (Decision 063)
The first live run of the mechanical strategy had to close eight legacy positions. Three of the seven market sells were rejected with 40310000 because the orphan-close path cancelled the stop and sold in the same breath, while the abort path next to it had polled the cancel to a terminal state for months. The positions sat bare until a manual trigger. The cleanup gave every exit — target, holding limit, orphan — one function: cancel, wait for the terminal state, re-read the position, sell, restore the stop if the sell fails. When two paths do the same dangerous thing, one of them is wrong; merge them before the wrong one runs.

### Backtest What Trades, Trade What You Backtested (Decision 061)
The LLM pipeline could only be judged forward, one week at a time; after five months that was 22 samples. The mechanical replacement was tested on a decade before it ran a day live, because the rule code is one module shared by the executor and the backtester. A rule that lives only in the live path cannot be tested, and a backtest that re-implements the live rule tests something else.

### Optimise Across Universes, Not Within Windows (Decision 062)
On the hindsight-free sector universe, the point that won each training window lost to SPY in every test window; the point that merely agreed across universes and eras won most of them. Small edges are found by consensus and plateau width, not by the maximum of one backtest. Every future search: several universes (one chosen without hindsight), in-sample / out-of-sample halves, the median over neighbours as the score, and a walk-forward of the selection rule itself.

### Delete What You Stopped Trusting (Decision 063)
Keeping the retired pipeline importable "for A/B" meant six modules, 350 tests and three state-file schemas that nothing scheduled used, a thesis schema the mechanical plan had to impersonate, and docs that described two systems at once. Freezing it under `legacy/` with a git tag kept the option and removed the weight: the live tree is a third of the size and every file in it is exercised by the schedule.
