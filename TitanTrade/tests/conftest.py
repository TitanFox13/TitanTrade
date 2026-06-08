"""Shared test fixtures for TitanTrade.

CRITICAL: No tests in this suite make real API calls. All AI model
interactions (Claude, Gemini) and broker calls (Alpaca) are mocked.
This ensures zero token spend and zero side effects during testing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from titantrade.config import (
    AlpacaConfig,
    ClaudeConfig,
    Config,
    FMPConfig,
    GeminiConfig,
    TradingSettings,
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_stop_reconcile: exercise the real "
        "entries._ensure_gtc_stop_on_fill (the autouse fixture no-ops it "
        "elsewhere to avoid live broker calls during bracket tests)",
    )


@pytest.fixture(autouse=True)
def _noop_entry_stop_reconcile(request, monkeypatch):
    """``entries._ensure_gtc_stop_on_fill`` polls the broker for the entry
    fill and then places a GTC stop — all live Alpaca calls. Bracket-placement
    tests mock ``place_bracket_order`` but not those primitives, so by default
    we no-op the reconcile. Its own dedicated tests mark themselves
    ``@pytest.mark.real_stop_reconcile`` to run the real implementation.
    """
    if request.node.get_closest_marker("real_stop_reconcile"):
        return
    monkeypatch.setattr(
        "titantrade.entries._ensure_gtc_stop_on_fill",
        lambda *a, **k: None,
        raising=False,
    )


@pytest.fixture
def fake_config() -> Config:
    """A Config with dummy API keys — never hits real services."""
    return Config(
        alpaca=AlpacaConfig(key="test-key", secret="test-secret", base_url="https://paper-api.alpaca.markets"),
        fmp=FMPConfig(key="test-fmp-key"),
        claude=ClaudeConfig(key="test-claude-key", model="claude-sonnet-4-6-20250514"),
        gemini=GeminiConfig(key="test-gemini-key", model="gemini-2.0-flash"),
        trading=TradingSettings(
            watchlist=["AAPL", "NVDA", "TSLA", "MSFT", "AMZN"],
            risk_per_trade=0.10,
            trading_mode="paper",
            stop_loss_pct=0.05,
        ),
    )


@pytest.fixture
def tmp_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect STATE_DIR to a temp directory so tests don't pollute real state.

    Each consumer that imports STATE_DIR by name (``from titantrade.config
    import STATE_DIR``) gets its own module-level binding, so we have to
    patch each one.
    """
    state = tmp_path / "state"
    state.mkdir()
    # Patch STATE_DIR everywhere it's imported by name. raising=False tolerates
    # modules that don't bind STATE_DIR (e.g. executor after its state helpers
    # were extracted into trade_state/cooldown/trailing_state/alerts).
    for mod in (
        "titantrade.config", "titantrade.risk_manager", "titantrade.executor",
        "titantrade.daily_sentry", "titantrade.cooldown", "titantrade.trailing_state",
        "titantrade.trade_state", "titantrade.alerts",
    ):
        monkeypatch.setattr(f"{mod}.STATE_DIR", state, raising=False)
    return state


@pytest.fixture
def sample_bars() -> list[dict[str, Any]]:
    """250 OHLCV bars with a gentle uptrend + noise for indicator testing."""
    bars = []
    base = 100.0
    for i in range(250):
        # Gentle uptrend: +0.1/day with +/- 1.5 oscillation
        import math
        noise = 1.5 * math.sin(i * 0.3)
        close = base + i * 0.1 + noise
        high = close + 1.0
        low = close - 1.0
        o = close - 0.2
        bars.append({
            "date": f"2025-{(i // 30) + 1:02d}-{(i % 28) + 1:02d}",
            "open": round(o, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": 50_000_000 + i * 10_000,
        })
    return bars


@pytest.fixture
def bullish_thesis() -> dict[str, Any]:
    """A valid BULLISH thesis for testing risk gates."""
    return {
        "ticker": "AAPL",
        "thesis": "BULLISH",
        "confidence": 0.80,
        "target_entry_price": 185.50,
        "stop_loss_price": 176.23,
        "take_profit_price": 198.00,
        "thesis_breach_condition": "CEO departure",
        "reasoning": "Strong iPhone cycle",
    }


@pytest.fixture
def sample_positions() -> list[dict[str, Any]]:
    """Alpaca-style position list for risk gate testing."""
    return [
        {"symbol": "NVDA", "market_value": "15000", "qty": "50", "current_price": "300"},
        {"symbol": "MSFT", "market_value": "10000", "qty": "25", "current_price": "400"},
    ]


def write_state_file(state_dir: Path, filename: str, data: Any) -> None:
    """Helper to write a JSON state file in tests."""
    with open(state_dir / filename, "w") as f:
        json.dump(data, f)
