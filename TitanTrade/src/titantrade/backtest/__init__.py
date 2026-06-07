"""Backtesting engine for TitanTrade.

Tests the rules-based components (risk gates, trailing stops, position sizing,
two-tranche entry, gap-down protection) against historical data.

Does NOT call any APIs or LLMs. Uses synthetic thesis generation based on
technical indicator heuristics.
"""

from titantrade.backtest.engine import run_backtest

__all__ = ["run_backtest"]
