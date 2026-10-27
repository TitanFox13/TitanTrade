# Parameter search harness (Decision 062)

Standalone scripts (numpy, not a project dependency: run with `uv run --with numpy python -I scripts/param_search/<script>.py`
from `TitanTrade/`; `-I` because the data files are downloaded, untrusted input). Data lives in `data/param_search/` (git-ignored;
**archived on titanserver under `/home/TitanTrade/archive/param_search/`** — copy back with the base64 pipe, never re-fetch blind):

- `alpaca_hist/historical_long/*.json` — `python -m titantrade download-history data/param_search/alpaca_hist/historical_long --days 2800`
  (SIP feed, 2016 →; the `download-history` command now uses SIP).
- `yahoo/*.json` — Yahoo chart API `v8/finance/chart/<SYM>?period1=0&period2=<now>&interval=1d` (adjusted closes;
  SPY from 1993, sector ETFs from 1998, names from their listing dates). Yahoo rate-limits aggressively (429 for hours, per address); fetch one symbol every few seconds, one attempt, and back off 20 minutes on a 429.
- `alpaca_hist/sp500_2016/*.json` — the S&P 500 as of 2016-01-04 (point-in-time list in `universes/`, from the public `fja05680/sp500` file), Alpaca SIP 2016 →, delisted names included.
- `french/*.csv` — Kenneth French 49 industry portfolios (daily value-weighted returns 1926 →) and the daily factors file (market = Mkt-RF + RF).

| Script | What |
|---|---|
| `fastbt.py` | Vectorised engine with the same semantics as `titantrade.backtest.mechanical` (`validate.py`: same trade set, equity to 1e-8); optional, default-off `trail_pct` (trailing stop armed once above entry), `rank` ("deepest" / "shallowest"), `dip_max` (crash filter); a name whose series ends is settled at its last price (`delist` exit) |
| `search.py` | Stage 1: 6,000-point entry/exit grid, insurance off, four datasets (Alpaca names/sectors 2016 →, Yahoo names/sectors 1999 →) |
| `analyze1.py` | Plateau scoring (median over one-step neighbours), marginal effects, cross-dataset ranks |
| `stage2.py` | Insurance (SMA × breadth × scale) × sizing (slot × max slots) around the chosen centres |
| `stage3.py` | Honest walk-forward: the *selection procedure* is trained on one window and tested on the next |
| `midpoint.py` | The chosen plateau midpoint vs the centres and the live defaults, with its neighbourhood |
| `datasets.py` | One loader per universe (A / D Alpaca, B / C Yahoo, E S&P 500 2016, F French industries) → `fastbt.Market` |
| `exits.py` | Decision 065 Evidence: exit-side variants (targets / clocks / trailing), `--universe` slot-count and ranking variants, `--band` crash filter |

Read the results in `docs/decisions.md` Decision 062 before re-running; pick plateaus, hold out time, charge costs.
