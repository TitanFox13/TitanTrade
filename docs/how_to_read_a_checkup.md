# How to read a checkup

*Written 2026-10-30 for the operator (roadmap Track F). A checkup is the record an agent writes every one to two weeks at the top of `docs/decisions.md` ("Check <date>"). This page says, in everyday words, what each part of it means, what is normal, and what would be a problem. The numbers that matter are few; most lines are there to show that nothing is wrong.*

---

## The one-line version

A checkup answers four questions, in this order:

1. **Is the machine running?** Every scheduled job finished, no errors in the log, every held dip position has its stop in place.
2. **Is the book what the rules say it should be?** The right legs in the right sizes, the two safety switches reading the market correctly.
3. **Did it trade only as the rules prescribe?** Every entry and exit has a reason the rules give.
4. **How is it doing against the index?** Reported, with its uncertainty, and not judged for three years.

If the first three are fine, the fourth is information, not a verdict.

---

## 1. The health lines

| what the checkup says | what it means | normal | a problem |
|---|---|---|---|
| "0 ERROR / n WARNING in the log" | The container log since the last checkup | 0 errors; a few expected warnings (a slow data source, a retried message) | Any ERROR or Traceback; a warning that repeats every run |
| "every job completed" | The seven-slot schedule (fetch, gap check, two execute runs, the daily summary, the Sunday full run; the monthly curate is switched off) | Every job's last result reads completed | A job that failed or never ran; a job still "running" long after its time |
| "every dip position stop-covered, n days from expiry" | Each held name has a stop order resting at the broker, and that order is not about to expire | A stop at the level the plan shows, 30+ days from its 90-day expiry | A position with no stop; a stop within a week of expiry; a stop at a level the plan does not show |
| "backup pulled" | The daily state archive copied off the server | Yes, once per checkup | The server's backup cron not running; the pull failing |
| "disk n %" | The server's disk | Under 60 % | Above 70 % (build caches pile up; the deploy procedure prunes them) |
| heartbeat | A ping after every daily summary, to a monitor that alarms when it stops | Not configured yet (the operator's sign-up) | Once configured: an alarm means the server, the scheduler or the summary is dead |

Why stops matter most: the broker's stop is the only protection that works while the server is down. Everything else (targets, the holding limit, the switches) is evaluated by the executor and stops with it.

## 2. The book

The book has three kinds of holdings and one reserve:

- **The momentum sleeve** — one ETF of the index's strongest recent names, held at 60 % of the investable book. "Investable" means equity minus the 5 % cash reserve, so the target is 57 % of equity. It is bought and sold only when it drifts more than 5 points of equity away from that target, so it normally sits anywhere between 52 % and 62 %. Since 2026-10-29 it has been well below that because it fills only from cash freed by the old positions; that is the transition, not a fault.
- **The dip slots** — up to three positions of 10 % of equity each, bought when a sector ETF closes 8 % or more below its 90-day high while still above its 150-day average. Each has a stop 12 % below its entry, a target 20 % above, and a 60-trading-day clock.
- **SPY** — whatever is left of the dip sleeve's 40 % after the slots. With three slots held it is about 8 %; while the old 25 %-sized positions are still held it is zero.
- **Cash** — about 5 %, the reserve the entries need.

| what the checkup says | normal | a problem |
|---|---|---|
| "SPMO n % of its 57 % target" | Within the band, or below it while old positions run out | Far below target with free cash sitting idle for more than a run or two |
| "DXCM / URI / JPM held" (the transition names) | Each with its stop, target and clock from the plan; they leave only by those three exits | A forced sale of one of them; one without a plan item |
| "n free slots, candidates: …" | 0 free slots while the three old names are held; afterwards 0–3 | A free slot with a valid candidate and no entry, with no gate named as the reason |
| "SPY n %" | 0 during the transition; later the small remainder | SPY above the remainder while slots are held (money double-counted) |
| "cash n %" | About 5 % | Far above 5 % for days with targets unmet (something is not buying); below 2 % |

**The two switches.** Both halve the exposure of the two core legs; neither touches a held dip position, which keeps its own exits.

- **Insurance** reads two things: is the index below its 200-day average, and are fewer than half of the eleven sectors above theirs? Only when *both* say "yes" does it switch on. The checkup prints both inputs (e.g. "SPY above its SMA, breadth 64 %"). Normal: off in a rising market. It costs about 1.4 points a year in a bull decade and is there for the long bear (1929, 1973, 2008-type years), where it has saved 15–20 points each time.
- **The shock trigger** reads one thing: did the index fall 7 % or more over any ten sessions in the last twenty? The checkup prints the worst ten-session move. Normal: off; on for a month after a sharp fall. It costs about 0.1 point a year and cuts the worst drawdown by about four points.
- **Exposure** is the smaller of the two (never their product): 1.0 when both are off, 0.5 when either is on.

A problem is an inconsistency, not a reading: a switch "on" while its printed inputs say otherwise, an exposure of 0.25, or a new entry made while a switch was on.

**Two lines that mean the broker's data was not trusted** (Decision 084): "SUSPECT ACCOUNT VALUE … this run keeps the stops and places no order" means the broker reported an account value half or double the recorded peak, so the run did nothing but keep the stops and sent an alert; "target not confirmed by the market, no exit" means a position looked like it had reached its target on the broker's mark while the live quote said otherwise, so it was kept. Both are the system refusing to act on bad data; a run that trades normally the next day is the expected follow-up. The log line without a glitch behind it would be the problem.

## 3. The trades since the last checkup

Every action in the trade log must be one the rules prescribe:

| action | the only reasons it may have |
|---|---|
| a BUY of a sector ETF | a NEW item in the plan that day, at the plan's levels, through the eight gates |
| a SELL of a dip position | the broker's stop; the +20 % target; the 60-trading-day clock; an orphan close (a position with no plan item); gap-down protection after a large overnight gap |
| a BUY or SELL of SPY, SPMO (or the cash-leg ETF when on) | a core rebalance toward its target, outside the band |

Anything else is a finding. The two things that look like problems and are not: a position that leaves the watchlist keeps its item and exits on its own (never force-sold); an entry order that did not fill by the close simply comes back the next run.

**Near misses** are entries blocked by one or two gates; the checkup may list them with the gate that blocked them. They are information about the gates, nothing to act on.

**The cooldown**: a name stopped out cannot be re-bought for 72 hours unless it is at least 1 % above the exit price after 24 hours. A re-entry inside that window must show the override reason.

## 4. The numbers against the index

Everything is measured against SPY, over the "clean window" that started when the current design went live (2026-10-29). Three things are reported.

**The benchmark line.** For the first 20 trading days it reads "insufficient data": a handful of daily returns say nothing. From 20 days to three years it reads "too short to judge the return: excess +x pp/yr, 90 % band ±y". The excess is the book's annualised lead over SPY so far; the band is how far that number could be from the truth. The band is wide, and it stays wide for years, because the book moves about 9 points a year differently from SPY: a true lead of one point a year would take decades to prove. That is why the return is **reported and never judged under three years**. What the checkup can say is whether the ride looks like the backtest's (beta below one, a smaller drawdown than SPY's when SPY falls).

**The fill ledger.** One number per entry: what the book paid against the close of that session, which is the price the backtest assumes. The checkup reports the median gap in percent; positive means the live book paid more. Normal: a few tenths of a percent either way (the entry is placed at the live price plus 0.3 %). A problem: a median above +1 % once there are 20 or more entries, or a gap that grows month by month.

**The shadow comparison.** The backtester is run over the clean window twice: on the live list (the eleven sector ETFs) and on the shadow list (the operator's fifteen hand-picked names), both under the same two-sleeve book, plus each list's dip sleeve alone. The question it answers, over years: would the hand-picked names have done better than the sectors with the same rule? The first months are noise by construction (two sessions, zero trades); and the list's past edge exists only since 2022, so a lead is not evidence of judgment until the window holds a bad year as well as a good one. Nothing in the book depends on this number.

## 5. The go / stop rule — what would ever change anything

The book goes live with real money only when all three hold over the clean window (Decision 069):

1. **Behaviour** — every action rule-prescribed (section 3) and the fill ledger's median gap small.
2. **Drawdown** — the window contains at least one SPY fall of 10 % or more; in every such fall the book fell no further than SPY, and in any fall of 20 % or more at most seven tenths as far.
3. **Return** — not a condition. Reported with its band; judged only after three years.

So a bad month, or a bad quarter, changes nothing. What would stop the book: an action the rules do not prescribe, a stop missing where one should be, or the book falling further than the index in a real fall.

## 6. What to expect, so a normal stretch does not look like a fault

The expectation, computed on the exact path of this book over 2017–2026 on the sector ETFs with no hindsight (Decision 081):

- about **+1 point a year** over SPY in a decade like the last — slightly behind in the first half of that decade, ahead in the second;
- a worst drawdown of about **−19 %** when SPY's was −34 %;
- a worst calendar year about **11 points behind** SPY, which happens in the rebound year after a crash: the switches step aside in the fall and step back in late. That year is the price of the protection, and it is expected.

Over a century of similar rules (a research blend, not an exact path) the lead is larger and present in every quarter-century, which is the real evidence; the decade alone is a coin flip. In plain words: the book is built to lose a little in strong bull years and a lot less in bear years, and to be judged on the second.

---

## The checklist

| question | if yes |
|---|---|
| Any ERROR in the log, or a job that did not complete? | Fix first; nothing else matters until the machine runs |
| Any held dip position without a stop, or a stop within a week of expiry? | A problem: the coverage job should have placed it; check it ran |
| Any trade that is not one of the prescribed actions? | A finding for `docs/decisions.md`, and a possible bug |
| A switch "on" with inputs that say "off", or exposure 0.25? | A bug |
| Cash far above 5 % with targets unmet for several runs? | Something is not buying: read the executor log for the gate or the band |
| The fill ledger's median gap above +1 % over 20+ entries? | The entry pricing is drifting: a finding |
| The book fell further than SPY in a SPY fall of 10 % or more? | The go/stop rule's drawdown leg failed: the design question reopens |
| The benchmark excess is negative this month? | Nothing: it is reported, not judged, for three years |
