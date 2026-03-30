"""Tests for dual Alpaca credentials and trading mode switching."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from titantrade.config import (
    _resolve_alpaca_keys,
    live_keys_configured,
    load_config,
    load_watchlist,
    save_trading_mode,
)


# ---------------------------------------------------------------------------
# _resolve_alpaca_keys
# ---------------------------------------------------------------------------

class TestResolveAlpacaKeys:
    def test_paper_keys_from_new_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ALPACA_PAPER_KEY", "pk")
        monkeypatch.setenv("ALPACA_PAPER_SECRET", "ps")
        monkeypatch.delenv("ALPACA_KEY", raising=False)
        monkeypatch.delenv("ALPACA_SECRET", raising=False)
        keys = _resolve_alpaca_keys()
        assert keys["ALPACA_PAPER_KEY"] == "pk"
        assert keys["ALPACA_PAPER_SECRET"] == "ps"

    def test_legacy_fallback(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("ALPACA_PAPER_KEY", raising=False)
        monkeypatch.delenv("ALPACA_PAPER_SECRET", raising=False)
        monkeypatch.setenv("ALPACA_KEY", "legacy-k")
        monkeypatch.setenv("ALPACA_SECRET", "legacy-s")
        keys = _resolve_alpaca_keys()
        assert keys["ALPACA_PAPER_KEY"] == "legacy-k"
        assert keys["ALPACA_PAPER_SECRET"] == "legacy-s"

    def test_missing_paper_keys_raises(self, monkeypatch: pytest.MonkeyPatch):
        for var in ("ALPACA_PAPER_KEY", "ALPACA_PAPER_SECRET", "ALPACA_KEY", "ALPACA_SECRET"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(ValueError, match="Missing Alpaca paper"):
            _resolve_alpaca_keys()

    def test_live_keys_optional(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ALPACA_PAPER_KEY", "pk")
        monkeypatch.setenv("ALPACA_PAPER_SECRET", "ps")
        monkeypatch.delenv("ALPACA_LIVE_KEY", raising=False)
        monkeypatch.delenv("ALPACA_LIVE_SECRET", raising=False)
        keys = _resolve_alpaca_keys()
        assert keys["ALPACA_LIVE_KEY"] == ""
        assert keys["ALPACA_LIVE_SECRET"] == ""


# ---------------------------------------------------------------------------
# live_keys_configured
# ---------------------------------------------------------------------------

class TestLiveKeysConfigured:
    def test_true_when_both_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ALPACA_LIVE_KEY", "lk")
        monkeypatch.setenv("ALPACA_LIVE_SECRET", "ls")
        assert live_keys_configured() is True

    def test_false_when_missing(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("ALPACA_LIVE_KEY", raising=False)
        monkeypatch.delenv("ALPACA_LIVE_SECRET", raising=False)
        assert live_keys_configured() is False

    def test_false_when_partial(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ALPACA_LIVE_KEY", "lk")
        monkeypatch.delenv("ALPACA_LIVE_SECRET", raising=False)
        assert live_keys_configured() is False


# ---------------------------------------------------------------------------
# save_trading_mode
# ---------------------------------------------------------------------------

class TestSaveTradingMode:
    def test_save_and_load(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("titantrade.config.DATA_DIR", tmp_path)
        monkeypatch.delenv("TRADING_MODE", raising=False)
        # Write initial watchlist
        wl = {"watchlist": ["AAPL"], "settings": {"trading_mode": "paper", "risk_per_trade": 0.10}}
        (tmp_path / "watchlist.json").write_text(json.dumps(wl))

        save_trading_mode("live")
        settings = load_watchlist()
        assert settings.trading_mode == "live"

    def test_preserves_other_settings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("titantrade.config.DATA_DIR", tmp_path)
        monkeypatch.delenv("TRADING_MODE", raising=False)
        wl = {"watchlist": ["MSFT"], "settings": {"trading_mode": "paper", "risk_per_trade": 0.15, "stop_loss_pct": 0.08}}
        (tmp_path / "watchlist.json").write_text(json.dumps(wl))

        save_trading_mode("live")
        data = json.loads((tmp_path / "watchlist.json").read_text())
        assert data["settings"]["risk_per_trade"] == 0.15
        assert data["settings"]["stop_loss_pct"] == 0.08
        assert data["watchlist"] == ["MSFT"]

    def test_invalid_mode_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("titantrade.config.DATA_DIR", tmp_path)
        with pytest.raises(ValueError, match="Invalid trading mode"):
            save_trading_mode("turbo")

    def test_creates_file_if_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("titantrade.config.DATA_DIR", tmp_path)
        monkeypatch.delenv("TRADING_MODE", raising=False)
        save_trading_mode("paper")
        assert (tmp_path / "watchlist.json").exists()
        settings = load_watchlist()
        assert settings.trading_mode == "paper"


# ---------------------------------------------------------------------------
# load_config — credential selection by mode
# ---------------------------------------------------------------------------

class TestLoadConfigCredentialSelection:
    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr("titantrade.config.DATA_DIR", tmp_path)
        monkeypatch.delenv("TRADING_MODE", raising=False)
        monkeypatch.delenv("ALPACA_BASE_URL", raising=False)
        # Required non-Alpaca keys
        monkeypatch.setenv("FMP_KEY", "fmp")
        monkeypatch.setenv("CLAUDE_KEY", "claude")
        monkeypatch.setenv("GEMINI_KEY", "gemini")
        # Paper keys
        monkeypatch.setenv("ALPACA_PAPER_KEY", "paper-k")
        monkeypatch.setenv("ALPACA_PAPER_SECRET", "paper-s")
        # Live keys
        monkeypatch.setenv("ALPACA_LIVE_KEY", "live-k")
        monkeypatch.setenv("ALPACA_LIVE_SECRET", "live-s")
        # Clean legacy
        monkeypatch.delenv("ALPACA_KEY", raising=False)
        monkeypatch.delenv("ALPACA_SECRET", raising=False)
        self.tmp = tmp_path

    def _write_watchlist(self, mode: str):
        wl = {"watchlist": ["AAPL"], "settings": {"trading_mode": mode}}
        (self.tmp / "watchlist.json").write_text(json.dumps(wl))

    def test_paper_mode_uses_paper_keys(self):
        self._write_watchlist("paper")
        cfg = load_config()
        assert cfg.alpaca.key == "paper-k"
        assert cfg.alpaca.secret == "paper-s"
        assert "paper-api" in cfg.alpaca.base_url

    def test_live_mode_uses_live_keys(self):
        self._write_watchlist("live")
        cfg = load_config()
        assert cfg.alpaca.key == "live-k"
        assert cfg.alpaca.secret == "live-s"
        assert cfg.alpaca.base_url == "https://api.alpaca.markets"

    def test_live_mode_without_live_keys_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("ALPACA_LIVE_KEY", raising=False)
        monkeypatch.delenv("ALPACA_LIVE_SECRET", raising=False)
        self._write_watchlist("live")
        with pytest.raises(ValueError, match="ALPACA_LIVE_KEY"):
            load_config()
