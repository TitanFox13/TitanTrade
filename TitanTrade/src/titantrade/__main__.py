"""CLI entry point for TitanTrade.

Usage:
    python -m titantrade fetch       # Fetch data bundle
    python -m titantrade analyze     # Run weekly analyst
    python -m titantrade sentry      # Run daily sentry
    python -m titantrade execute     # Execute trades
    python -m titantrade full        # Full pipeline: fetch -> analyze -> sentry -> execute
"""

from __future__ import annotations

import sys


def main() -> None:
    commands = {
        "fetch": "titantrade.data_fetcher",
        "analyze": "titantrade.weekly_analyst",
        "sentry": "titantrade.daily_sentry",
        "execute": "titantrade.executor",
    }

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("TitanTrade - Semi-automated AI trading system")
        print()
        print("Commands:")
        print("  fetch      Fetch data bundle (prices, news, filings)")
        print("  analyze    Run weekly Claude analysis")
        print("  sentry     Run daily Gemini sentry check")
        print("  execute    Execute trades via Alpaca")
        print("  resubmit   Resubmit expired bracket orders")
        print("  full       Run full pipeline (fetch -> analyze -> sentry -> execute)")
        sys.exit(0)

    command = sys.argv[1]

    if command == "resubmit":
        from titantrade.config import load_config
        from titantrade.executor import resubmit_expired_brackets, get_positions

        cfg = load_config()

        import json
        from titantrade.config import STATE_DIR
        thesis_path = STATE_DIR / "weekly_thesis.json"
        bundle_path = STATE_DIR / "data_bundle.json"

        if not thesis_path.exists():
            print("No weekly thesis found - nothing to resubmit")
            return

        with open(thesis_path) as f:
            thesis_doc = json.load(f)
        with open(bundle_path) as f:
            data_bundle = json.load(f) if bundle_path.exists() else {}

        positions = get_positions(cfg)
        trades = resubmit_expired_brackets(cfg, thesis_doc, positions, data_bundle)
        print(f"Resubmitted {len(trades)} expired brackets")
        for t in trades:
            print(f"  BUY {t.get('shares', '?'):>5} {t['ticker']:<6} @ ${t.get('price', 0):.2f}")
        return

    if command == "full":
        from titantrade.config import load_config
        from titantrade.weekly_analyst import run_weekly_analysis
        from titantrade.daily_sentry import run_daily_sentry
        from titantrade.executor import execute_trades

        cfg = load_config()
        print("Step 1/3: Running weekly analysis...")
        run_weekly_analysis(cfg)
        print("Step 2/3: Running daily sentry...")
        run_daily_sentry(cfg)
        print("Step 3/3: Executing trades...")
        trades = execute_trades(cfg)
        print(f"Done. {len(trades)} trades executed.")
        return

    if command not in commands:
        print(f"Unknown command: {command}")
        print(f"Available: {', '.join(commands)} or 'full'")
        sys.exit(1)

    # Import and run the module's main()
    import importlib
    module = importlib.import_module(commands[command])
    module.main()


if __name__ == "__main__":
    main()
