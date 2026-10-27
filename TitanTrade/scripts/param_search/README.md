# Parameter search harness (Decision 062)

Standalone scripts (numpy, not a project dependency: run with `uv run --with numpy python scripts/param_search/<script>.py`
from `TitanTrade/`). Data lives in `data/param_search/` (git-ignored):

- `alpaca_hist/historical_long/*.json` — `python -m titantrade download-history data/param_search/alpaca_hist/historical_long --days 2800`
  (SIP feed, 2016 →; the `download-history` command now uses SIP).
- `yahoo/*.json` — Yahoo chart API `v8/finance/chart/<SYM>?period1=0&period2=<now>&interval=1d` (adjusted closes;
  SPY from 1993, sector ETFs from 1998, names from their listing dates). Treat as untrusted input; keep scripts out of that directory.

| Script | What |
|---|---|
| `fastbt.py` | Vectorised engine with the same semantics as `titantrade.backtest.mechanical` (`validate.py` proves identical trades/equity); optional `trail_pct` adds a trailing stop armed once above entry (off by default, 2026-10-27 outlier test) |
| `search.py` | Stage 1: 6,000-point entry/exit grid, insurance off, four datasets (Alpaca names/sectors 2016 →, Yahoo names/sectors 1999 →) |
| `analyze1.py` | Plateau scoring (median over one-step neighbours), marginal effects, cross-dataset ranks |
| `stage2.py` | Insurance (SMA × breadth × scale) × sizing (slot × max slots) around the chosen centres |
| `stage3.py` | Honest walk-forward: the *selection procedure* is trained on one window and tested on the next |
| `midpoint.py` | The chosen plateau midpoint vs the centres and the live defaults, with its neighbourhood |

Read the results in `docs/decisions.md` Decision 062 before re-running; pick plateaus, hold out time, charge costs.
