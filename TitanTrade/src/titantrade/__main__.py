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
        "pricecheck": "titantrade.price_check",
        "benchmark": "titantrade.benchmark",
        "signals": "titantrade.mechanical",
        "curate": "titantrade.curator",
    }

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("TitanTrade - Semi-automated AI trading system")
        print()
        print("Commands:")
        print("  fetch            Fetch data bundle (prices, news, filings)")
        print("  signals          Mechanical signals → thesis/sentry state files (Decision 061)")
        print("  execute          Execute trades via Alpaca (run `signals` first under the mechanical strategy)")
        print("  curate           Monthly LLM universe-curation proposal + post-mortem (no orders)")
        print("  analyze          [legacy strategy=llm] Run weekly Claude analysis")
        print("  sentry           [legacy strategy=llm] Run daily Gemini sentry check")
        print("  pricecheck       Intraday price check (no LLM, pure price)")
        print("  benchmark [days] Performance vs SPY: beta, alpha, Sharpe (--since YYYY-MM-DD)")
        print("  gapcheck         Check for unfilled stop-limits after gap-downs")
        print("  resubmit         Resubmit expired bracket orders")
        print("  full             Full pipeline (fetch -> analyze -> sentry -> execute)")
        print("  backtest [dir]   Run backtest on historical data (default: data/historical)")
        print("                   mirrors the live strategy; add --legacy for the old dip-buy path")
        print("  backtest-ab [dir]  A/B compare baseline vs confidence-scaled sizing (legacy strategy)")
        print("  backtest-mech [dir] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--split YYYY-MM-DD] [--grid]")
        print("                   Mechanical strategy backtest (Decision 061); --grid runs walk-forward over the built-in grid")
        print("  download-history [dir] [--days N]  Download OHLCV (watchlist + SPY + sector ETFs) for backtesting")
        sys.exit(0)

    command = sys.argv[1]

    if command == "backtest":
        from titantrade.backtest.engine import run_backtest, print_summary

        data_dir = sys.argv[2] if len(sys.argv) > 2 else "data/historical"
        use_scaling = "--confidence-scaling" in sys.argv
        # v2 (production-faithful) is the default; --legacy/--v1 opts into the
        # old dip-buy strategy. --v2 still accepted as an explicit no-op.
        legacy = "--legacy" in sys.argv or "--v1" in sys.argv
        result = run_backtest(
            data_dir=data_dir,
            use_confidence_scaling=use_scaling,
            strategy_v2=not legacy,
        )
        print_summary(result)
        return

    if command == "backtest-ab":
        import json as _json
        from titantrade.backtest.engine import run_ab_comparison

        data_dir = sys.argv[2] if len(sys.argv) > 2 else "data/historical"
        result = run_ab_comparison(data_dir=data_dir)
        cmp = result["comparison"]
        print("=" * 70)
        print("  Backtest A/B: flat risk_per_trade  vs  confidence-scaled")
        print("=" * 70)
        for metric, row in cmp.items():
            if metric == "trade_count":
                print(f"  {metric:20s}  baseline={row['baseline']}  scaled={row['scaled']}")
            else:
                b = row.get("baseline")
                s = row.get("scaled")
                d = row.get("delta")
                if d is None:
                    print(f"  {metric:20s}  baseline={b!r}  scaled={s!r}")
                else:
                    arrow = "▲" if d > 0 else ("▼" if d < 0 else "=")
                    print(f"  {metric:20s}  baseline={b:>8.2f}  scaled={s:>8.2f}  Δ={d:+.2f} {arrow}")
        print("=" * 70)
        # Also dump the full JSON for programmatic consumption
        out_path = "state/backtest_ab.json"
        with open(out_path, "w") as f:
            _json.dump(result, f, indent=2, default=str)
        print(f"\nFull results saved to {out_path}")
        return

    if command == "download-history":
        from titantrade.backtest.data_loader import download_historical_data
        from titantrade.config import load_config as _load_cfg

        cfg = _load_cfg()
        args = [a for a in sys.argv[2:] if not a.startswith("--")]
        data_dir = args[0] if args else "data/historical"
        days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 750
        download_historical_data(
            cfg.trading.watchlist + list(cfg.trading.sector_etfs), cfg, data_dir, days=days,
        )
        return

    if command == "backtest-mech":
        from titantrade.backtest.mechanical import main as mech_main

        mech_main(sys.argv[2:])
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
        from titantrade.executor import execute_trades

        cfg = load_config()
        if cfg.trading.strategy == "mechanical":
            from titantrade.data_fetcher import main as fetch_main
            from titantrade.mechanical import refresh_mechanical_signals

            print("Step 1/3: Fetching data bundle...")
            fetch_main()
            print("Step 2/3: Computing mechanical signals...")
            refresh_mechanical_signals(cfg)
        else:
            from titantrade.weekly_analyst import run_weekly_analysis
            from titantrade.daily_sentry import run_daily_sentry

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
