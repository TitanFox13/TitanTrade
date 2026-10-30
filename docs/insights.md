# Insights & Lessons

## Design Insights

### Why Software Stop-Losses Are Dangerous
A stop checked by a cron job fires twice a day. Overnight a stock can drop 15–20% on earnings or macro news, and by the morning run the "stop" fires far below the intended level. Alpaca's native `stop_limit` orders live on the broker's servers and trigger the moment price touches them, whether or not the bot is running. Every held position carries one.

### Bracket Order Nuance
Alpaca brackets are DAY orders: an entry that does not fill by the close expires with its legs, and after a fill the exit legs expire at 20:00 UTC too. The stop leg also sits in `held` while the take-profit leg is live, so it is invisible to the open-orders query. Hence: a ticker whose entry expired keeps its plan item and gets a fresh bracket at the next run, and a filled bracket gets its own GTC stop (the TP leg is cancelled, which takes the held stop with it, and a GTC stop is placed at the bracket's level).

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

### A Grid Finds a Family, Never a Winner (Decision 067)
Four thousand books on the decade and eight hundred on the century, scored
one way, produced no cell worth naming. The best cell changed with every
objective and every era, and the walk-forward showed the chosen cell doing no
better than the median of its family. What held across both eras was a
*region*: momentum-majority, the shock trigger on, no volatility target. The
useful output of a big search is the marginal-effects table, read before any
leaderboard; the leaderboard is where overfitting lives.

### The Placebo Is the Benchmark for a Cross Product (Decision 067 addendum)
Letting ten market types each pick their own strategy gained up to nine
points a year in-sample, and so did a random labelling with the same block
structure. Out of sample both gave the gain back. A big search needs a
null: shuffle the labels, run the same selection, and the "pattern" has to
beat that, not zero. Also learned: rotation by trailing return is momentum
under another name, so a rotating sleeve the operator asked for was already
in the design as the momentum ETF.

### Inverted Prices Are Not Shorts (Decision 067 addendum)
Feeding 1/P to a long-only engine looks like a free short simulation and
reads +4 %/yr on the S&P 500 for the anti-dip mirror; the same trades priced
as real shorts on the real path lose 15. A long position in 1/P has bounded
losses and unbounded gains; a short has the reverse, and the stopped trades
are exactly where the two diverge. Whenever a transform makes a test cheap,
price the result the way the broker would before reading it.

### Analogues Describe the Weather, Not the Plan (Decision 067 addendum)
Matching today's coarse state against a century finds the forward year is
below average when breadth narrows at the highs, and finds nothing from low
volatility, an uptrend or momentum leadership. That is useful to know and
useless to act on: the designs' relative returns in those states are
positive in one half of the century and negative in the other, and the
decade holds three episodes. The state tells you which kind of year to brace
for; the design already holds a sleeve for each kind.

### When the Placebo Beats Both Candidates, the Era Is Talking (Decision 068 addendum)
Member breadth looked like a better insurance signal than sector breadth on the
decade (+0.8 a year) until the placebo ran: a breadth series shuffled at random beat
both real measures. The decade rewards any loosening of the insurance, so anything
that fires it a little less looks smart. A placebo that beats the incumbent as well as
the candidate is not a null result about the candidate; it says the test window has a
preference of its own, and the comparison must be made on an era that does not.

### A Short List Is Not a Quality List (Decision 068 addendum)
The dip rule on the point-in-time Dow 30 lost 8 points a year in both halves, and
19 of 20 random 30-name lists drawn from the S&P 500 lost too. "A small edge on a
short list of quality names" was the wrong diagnosis: the rule wins only on the 11
diversified sector ETFs, which cannot have a single-name break, and on the
operator's 15 names after 2022. Any list of individual large caps hands the rule
breaks it cannot tell from dips. The curated list's edge is the list, not a property
any rule reproduces. Corollaries from the same afternoon: a dip measured relative to
the market is a lagging sector, the anti-momentum trade (−4 to −5 a year); and a
filter on the speed of the fall has nothing to filter on ETFs and holds only
in-sample on single names.

### A Mirror Rule Can Only Act Where the Original Binds (Decision 068 addendum)
The shock trigger's hold is combined with the two-signal insurance by min(), and in
every rebound of the decade the insurance was the binding rule: SPY under its 200-day
SMA with breadth under half. Releasing the shock hold on a +7 % rebound changed nothing
in 2018, 2020, 2022 or 2025, and where it did act, the bear-market rallies of 1932 and
2008, it re-exposed the book into the next leg down. A fast rule's territory is the
complement of the slow rule's; its mirror inherits that scope, not the whole crash.

### A Quarter Cannot Judge a Return Edge (the luck meter, Decision 068 addendum)
The book tracks SPY with a 9 %/yr tracking error. A true +1.4 pp/yr would need about
170 years to reach a t-statistic of 2; over one quarter the book fails "≥ SPY − 2 pp/yr"
43 % of the time and beats SPY only 53 % of the time *when it is exactly as good as the
backtest*. The century, not the decade, is where the evidence lives (t = 3.16; bootstrap
band +1.9 … +5.2 against −2.8 … +5.1). A go/stop rule can decide behaviour and drawdown;
it cannot decide return, and the drawdown leg as first written (≤ 0.7 × SPY in every
≥ 10 % drawdown) fails the design's own backtest 3 times in 5, because in a fast 10–19 %
dip the insurance and the shock trigger barely engage, by design.

### The Vehicle Is Not the Premium (Decision 075 addendum)
The hindsight-free quality portfolios beat SPY by 1.6 to 3.4 points a year over
2017–2026. Twelve quality-labelled funds, their list fixed before a price was fetched,
all lagged SPY, each in at least one half. They were not fakes: eleven load positively on
the profitability factor. They load a quarter to a half of what the academic portfolio
loads — multi-metric screens, sector caps and fees dilute the tilt — and every alpha but
one is negative. A factor's history belongs to the portfolio that defined it; a fund with
the same name is a separate claim that has to beat its index on its own. SPMO did, MTUM
did not, and here none did. Test the vehicle; never infer it from the factor.

### Quality Is Harvested by Holding, Like Momentum (Decision 075)
Sixty-three years of profitability-sorted portfolios say the quality premium is real,
old and defensive: the most profitable third of the market beat the market by about a
point a year in every era with a smaller drawdown, and the long-short factor made money
in 2000–02 and 2008. The dip rule on those same portfolios lost 1.7 points a year to the
market and four to simply holding them, and it lost exactly as much on the *least*
profitable portfolios — profitability does not tell a dip from a break. This is Decision
066's momentum lesson from the other side: a premium that lives in the cross-section is
captured by owning it, and a rule that buys its dips and caps its wins throws it away.
Corollary: the fundamentals pipeline that would have filtered a single-name dip universe
by profitability has nothing to filter on, and stays unbuilt.

### Bought Protection Is Paid For Twice (Decision 074)
Forty years of Cboe's protective-put index say what a monthly put costs: 3 points a
year in every decade, for a drawdown a quarter smaller than the market's. The book's
two free signals — the 200-day line with breadth, and a 7 % fall in ten sessions — cost
0.7 on the market and left a smaller drawdown. In the crash itself the put protected as
much as the rules; in the rebound year it lost far more (−37 in 2009, −44 in 2020
against the market, versus the rules' −26 and −16), because the premium is still being
paid while the market is already up. Parking the de-risked half in the put instead of
cash does not help either: a 5 % out-of-the-money put leaves you three quarters long,
so the drawdown is twelve points deeper for a third of a point of return. Protection
that is paid for in premium is paid for again in the rebound; a rule that steps aside
and steps back pays once.

### Option Writing Is a Sharpe Tool, Not a Return Tool (Decision 074)
The put-write index's published claim — the S&P's return at two thirds of its
volatility — held from 1986 to 2006 and not since: on the twenty years with daily data
it lagged by 4 points a year, by 7 in the last decade. Inside the book an option-writing
sleeve smooths the ride (Sharpe 0.77 → 0.84 over forty years) and adds no return,
and its excess is slightly negatively correlated with both sleeves — a diversifier
that does not earn its place. A sleeve that raises the Sharpe without raising the
return only matters to a book that can lever, and this one cannot.

### Two Books That De-risk Together Are One Bet (Decision 073)
An ex-US copy of the live book was built on its own index: country ETFs for the dip
sleeve, an ex-US momentum ETF, insurance and the shock trigger read off ACWX. The two
dip sleeves' active returns correlated 0.04 — different bets, as hoped. The two *books'*
active returns correlated 0.58, because while a book is de-risked its active return is
minus half its market, the two markets are 0.85 correlated, and they fall at the same
times. The insurance that protects each book makes the pair the same bet in the week
that hurts; the diversification lives in the sleeves and is drowned by the exposure
rules. A second book under the same rules buys protection in the decades, not in the
crash, and this decade priced that at 2–4 pp/yr for one point of drawdown.

### A Basket Is Not Automatically a Floor (Decision 073)
The dip rule is ≥ 0 only on the 11 sector ETFs, and the reason given was that baskets
cannot have single-name breaks. Twenty single-country ETFs are baskets too, and the rule
lost on them in the first half and through 2025 (62 % winners, a +2.8 % median trade,
against 79 % and +4.9 % on the sectors). A country's dip inside an uptrend is as often a
currency or a policy move as a reversion, and the rule cannot tell them apart. The
sector floor is a property of US sectors, not of diversified baskets in general; every
new universe gets the floor test, whatever it is made of.

### You Cannot Detect the Epoch, You Can Detect the Fall (Decision 067)
Every slow "which regime are we in" rule we tried (trend, breadth, a three-state
mix, the sleeve's own momentum) gave back return and cut no drawdown, over a
decade and over a century, because a regime is only knowable after the move
that defines it. A fast rule that reacts to the fall itself, halve exposure
for twenty sessions after a 7% drop in ten, cut the worst drawdown by a third
at almost no cost, and 80 of 81 parameter cells agreed. The lesson is about
what a signal can know: the market's state is a story told afterwards; a 7%
drop is a fact on the day it happens.

### Point-in-Time Membership or Nothing (Decision 067)
A dip rule on "the S&P 500" made +6.7 pp/yr on the union of everything that
was ever in the index, +1.4 on the 2016 list, and −4.3 on the actual members
of each day. The first two let the rule buy names before the index did, and
index inclusion is a record of past strength: look-ahead wearing a lab coat.
Every universe test needs the membership mask, and a result that moves by
ten points when the mask goes on was never a result.

### Different Bets Add, Same Bets Pile Up (Decision 067)
Two dip rules on two universes had excess-return correlation 0.4 and summed
to nothing. A dip rule and a momentum ETF had correlation 0.05 and the sum
beat SPY in both halves, in 23 of 27 rolling windows and in all four
quarter-centuries. "Adding strategies" only hedges when the strategies bet
on different things; a second copy of the same bet is leverage, not
diversification.

### Momentum Is Harvested by Holding (Decision 066)
The one name-selection rule with a century behind it, buying last year's
winners, beat SPY by about 5 points a year since 1927 and by a noisy 2 to 8
in the 2017–2026 point-in-time S&P 500. Put the live dip rule on top of
those names and the result is −14 points a year: a momentum name's dip is
the moment its momentum broke, and a +20% cap throws away the trend. The
two ideas are not complementary; they are opposites. Also learned: a screen
whose decade is made by its last year (2026) is a candidate, not a result,
and a regime guard that halves a dip strategy's drawdown does nothing for
momentum's, because momentum crashes are its own.

### The Universe Is a Parameter (Decision 065 Evidence, 2026-10-27)
The same dip-in-uptrend rule made +4 pp/yr on the 15 curated names, +0.4 on
the 11 sector ETFs, −0.04 over a century of 49 industries, and **−10 pp/yr on
the 502 members of the 2016 S&P 500**. Nothing in the rule changed; "deepest
dip above its 150-day SMA, three slots" is a small edge on a short list of
quality names and adverse selection on a long list of anything (the deepest
dips in 500 names are blow-ups from parabolic runs; the median trade ended at
the stop). Ten slots or a crash filter repair most of it on the broad
universe. Lesson: a backtest result belongs to the universe it ran on as much
as to the rule, and a watchlist change is a strategy change — test it like
one.

### Delete What You Stopped Trusting (Decision 063)
Keeping the retired pipeline importable "for A/B" meant six modules, 350 tests and three state-file schemas that nothing scheduled used, a thesis schema the mechanical plan had to impersonate, and docs that described two systems at once. Freezing it under `legacy/` with a git tag kept the option and removed the weight: the live tree is a third of the size and every file in it is exercised by the schedule.
