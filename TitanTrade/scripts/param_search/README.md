# Parameter search harness (Decision 062)

Standalone scripts (numpy, not a project dependency: run with `uv run --with numpy python -I scripts/param_search/<script>.py`
from `TitanTrade/`; `-I` because the data files are downloaded, untrusted input). Data lives in `data/param_search/` (git-ignored;
**archived on titanserver under `/home/TitanTrade/archive/param_search/`** — copy back with the base64 pipe, never re-fetch blind):

- `alpaca_hist/historical_long/*.json` — `python -m titantrade download-history data/param_search/alpaca_hist/historical_long --days 2800`
  (SIP feed, 2016 →; the `download-history` command now uses SIP).
- `yahoo/*.json` — Yahoo chart API `v8/finance/chart/<SYM>?period1=0&period2=<now>&interval=1d` (adjusted closes;
  SPY from 1993, sector ETFs from 1998, names from their listing dates). Yahoo rate-limits aggressively (429 for hours, per address); fetch one symbol every few seconds, one attempt, and back off 20 minutes on a 429.
- `alpaca_hist/sp500_2016/*.json` — the S&P 500 as of 2016-01-04 (point-in-time list in `universes/`, from the public `fja05680/sp500` file), Alpaca SIP 2016 →, delisted names included.
- `french/*.csv` — Kenneth French daily files: 49 industry portfolios, 10 prior-return (momentum 12-2, short-term 1-0, long-term 60-13) deciles, 25 size × momentum, the momentum factor and the daily factors file (market = Mkt-RF + RF), all 1926 →.
- `alpaca_hist/historical_long/` also holds factor ETFs (MTUM, SPMO, USMV, QUAL, RSP), multi-asset ETFs (GLD, TLT, IEF, EEM, EFA, IWM, VNQ, DBC, LQD, HYG, SLV, SH) and industry ETFs (XBI, SMH, ITB, KRE, XOP, IBB), all 2016 →.
- `alpaca_hist/sp500_2016/` also holds every member added 2016 → 2026 (742 names; `universes/sp500_union_2016_2026.json`), so screens can use each date's actual membership.

| Script | What |
|---|---|
| `fastbt.py` | Vectorised engine with the same semantics as `titantrade.backtest.mechanical` (`validate.py`: same trade set, equity to 1e-8); optional, default-off `trail_pct` (trailing stop armed once above entry), `rank` ("deepest" / "shallowest"), `dip_max` (crash filter), `eligible` (T × N mask), `stop_cooldown_days` (post-stop exclusion); a name whose series ends is settled at its last price (`delist` exit) |
| `search.py` | Stage 1: 6,000-point entry/exit grid, insurance off, four datasets (Alpaca names/sectors 2016 →, Yahoo names/sectors 1999 →) |
| `analyze1.py` | Plateau scoring (median over one-step neighbours), marginal effects, cross-dataset ranks |
| `stage2.py` | Insurance (SMA × breadth × scale) × sizing (slot × max slots) around the chosen centres |
| `stage3.py` | Honest walk-forward: the *selection procedure* is trained on one window and tested on the next |
| `midpoint.py` | The chosen plateau midpoint vs the centres and the live defaults, with its neighbourhood |
| `datasets.py` | One loader per universe (A / D Alpaca, B / C Yahoo, E S&P 500 2016, F French industries) → `fastbt.Market` |
| `exits.py` | Decision 065 Evidence: exit-side variants (targets / clocks / trailing), `--universe` slot-count and ranking variants, `--band` crash filter |
| `screens.py` | Decision 066: pre-registered universe screens on the point-in-time S&P 500 (`--grid` momentum robustness, `--overlay` dip rule on screened picks, `--profile` the operator's list, `--trades` entry-time features, `--refine` guards and blends, `--s6`) |
| `century.py` | Decision 066: French momentum deciles 1927 → — the premium by era, the dip rule on deciles, `--regime` trend-guarded top decile |
| `combo.py` | Decision 067: portfolio of sleeves — walk-forward of the momentum and broad-dip rules, sleeve correlations, blends (curated vs sector floor), the century blend |
| `etf_sleeve.py` | Decision 067: momentum ETFs (MTUM / SPMO) as the second sleeve — year by year, weight sweep, rolling 3-year windows |
| `crashes.py` | Decision 067: every recorded crash from the peak, four books, century and ETF era → `data/param_search/crashes.json` (the crash-scenarios page) |
| `master.py` | Decision 067: the master grid — every discussed design on the decade (4,140 books) and the century (765); marginal effects, constrained leaderboards, walk-forward of the selection; `--finalists` for the consensus region with crash episodes |
| `regimes.py` | Decision 067: regime rules on the 50/50 book (two-signal, three-state, own momentum, vol target, shock trigger); `--grid` = the shock trigger's 81-cell robustness grid |
| `shorts.py` | Decision 067 addendum: shorts — the French WML factor as an overlay, the de-risked half short the market (−1× / SH) instead of cash, the anti-dip mirror on 1/P priced as real shorts |
| `analogues.py` | Decision 067 addendum: today's coarse state (trend, 12-month return, 20-day vol, distance from the high, breadth, momentum leadership) → historical analogue days and episodes, forward 1 / 2-year market and design distributions, the state over the past 12 months |
| `dynamic_universe.py` | Decision 067 addendum: multi-asset / industry ETF universes (3 and 5 slots), `stop_cooldown_days` 60–250, own-12-month eligibility inside the dip rule — each vs SPY and vs the equal-weight universe || `states.py` | Decision 067 addendum: state-conditional strategy — 8 state schemes (incl. k-means K = 4–12) × book-mix / dip-parameter actions × walk-forward both ways × placebo labellings; `--momcrash` = five published momentum-crash guards on the recommended book; `--tilt` = the post-crash tilt into the dip sleeve (triggers × hold × tilt, placebo) |
| `rotation.py` | Decision 067 addendum: rotation sleeves — sector rotation (36 cells), multi-asset rotation, Faber GTAA 5, century industry rotation — alone and as the sleeve beside the dip book, vs SPMO; `--timing` = rebalance frequency (daily → annual), rank tolerance bands, trend-break and shock triggers |
Read the results in `docs/decisions.md` Decision 062 before re-running; pick plateaus, hold out time, charge costs.
