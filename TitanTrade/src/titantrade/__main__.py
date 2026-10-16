"""CLI entry point for TitanTrade.

Usage:
    python -m titantrade fetch       # Data bundle (prices, signal inputs, breadth, earnings, macro)
    python -m titantrade signals     # Plan from the bundle (plan.json)
    python -m titantrade execute     # Execute the plan via Alpaca
    python -m titantrade full        # fetch -> signals -> execute
"""
from __future__ import annotations

import sys


COMMANDS = {
    "fetch": "titantrade.data_fetcher",
    "signals": "titantrade.mechanical",
    "execute": "titantrade.executor",
    "curate": "titantrade.curator",
    "benchmark": "titantrade.benchmark",
}

HELP = """TitanTrade - mechanical dip-in-uptrend strategy (Decisions 061-063)

Commands:
  fetch            Build the data bundle (prices, signal inputs, sector breadth, earnings, macro calendar)
  signals          Compute the plan from the bundle -> state/plan.json
  execute          Execute the plan via Alpaca (the scheduler runs signals first)
  full             fetch -> signals -> execute
  gapcheck         Gap-down protection + place missing stops
  curate           Monthly LLM universe proposal + post-mortem (advisory, no orders)
  benchmark [days] Performance vs SPY: beta, alpha, Sharpe (--since YYYY-MM-DD)
  backtest-mech [dir] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--split YYYY-MM-DD] [--grid]
                   Backtest the strategy on data/historical (same rule code as live)
  download-history [dir] [--days N]
                   Download OHLCV (watchlist + SPY + sector ETFs, SIP feed) for backtesting
"""


def _opt(argv: list[str], key: str, default=None):
    return argv[argv.index(key) + 1] if key in argv else default


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(HELP)
        sys.exit(0)
    command = sys.argv[1]
    argv = sys.argv[2:]

    if command == "full":
        from titantrade.config import load_config
        from titantrade.data_fetcher import main as fetch_main
        from titantrade.executor import execute_trades
        from titantrade.mechanical import refresh_plan

        cfg = load_config()
        print("Step 1/3: Fetching data bundle...")
        fetch_main()
        print("Step 2/3: Computing the plan...")
        refresh_plan(cfg)
        print("Step 3/3: Executing...")
        trades = execute_trades(cfg)
        print(f"Done. {len(trades)} trades executed.")
        return

    if command == "gapcheck":
        from titantrade.config import load_config
        from titantrade.executor import check_gap_down_protection, ensure_stop_coverage

        cfg = load_config()
        trades = check_gap_down_protection(cfg)
        print(f"Gap-down protection: {len(trades)} positions closed")
        for t in trades:
            print(f"  SELL {t.get('shares', '?'):>5} {t['ticker']:<6} @ ${t.get('price', 0):.2f}")
        print(f"Stop coverage: {ensure_stop_coverage(cfg)} missing stop(s) placed")
        return

    if command == "download-history":
        from titantrade.backtest.data_loader import download_historical_data
        from titantrade.config import load_config

        cfg = load_config()
        args = [a for a in argv if not a.startswith("--")]
        download_historical_data(
            cfg.trading.watchlist + list(cfg.trading.sector_etfs), cfg,
            args[0] if args else "data/historical", days=int(_opt(argv, "--days", 750)),
        )
        return

    if command == "backtest-mech":
        from titantrade.backtest.mechanical import main as mech_main

        mech_main(argv)
        return

    if command not in COMMANDS:
        print(f"Unknown command: {command}")
        print(f"Available: {', '.join(COMMANDS)}, full, gapcheck, backtest-mech, download-history")
        sys.exit(1)

    import importlib
    importlib.import_module(COMMANDS[command]).main()


if __name__ == "__main__":
    main()
