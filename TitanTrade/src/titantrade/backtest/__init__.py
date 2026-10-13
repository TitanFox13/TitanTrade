"""Backtesting for the mechanical strategy — the same rule code as live.
No API or LLM calls; data comes from `download-history`.
"""
from titantrade.backtest.mechanical import run_mechanical_backtest, walk_forward

__all__ = ["run_mechanical_backtest", "walk_forward"]
