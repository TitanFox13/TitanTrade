"""Tests for the /api/settings endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from titantrade.api import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr("titantrade.config.DATA_DIR", data)
    monkeypatch.setattr("titantrade.api.DATA_DIR", data)
    return data


class TestGetSettings:
    def test_returns_paper_by_default(self, client, tmp_data_dir: Path):
        wl = {"watchlist": ["AAPL"], "settings": {"trading_mode": "paper"}}
        (tmp_data_dir / "watchlist.json").write_text(json.dumps(wl))
        with patch("titantrade.api.live_keys_configured", return_value=False):
            resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trading_mode"] == "paper"
        assert data["live_keys_configured"] is False

    def test_returns_live_keys_status(self, client, tmp_data_dir: Path):
        wl = {"watchlist": ["AAPL"], "settings": {"trading_mode": "paper"}}
        (tmp_data_dir / "watchlist.json").write_text(json.dumps(wl))
        with patch("titantrade.api.live_keys_configured", return_value=True):
            resp = client.get("/api/settings")
        assert resp.json()["live_keys_configured"] is True

    def test_missing_watchlist_returns_defaults(self, client, tmp_data_dir: Path):
        with patch("titantrade.api.live_keys_configured", return_value=False):
            resp = client.get("/api/settings")
        assert resp.status_code == 200
        assert resp.json()["trading_mode"] == "paper"


class TestPutTradingMode:
    def test_switch_to_live(self, client, tmp_data_dir: Path):
        wl = {"watchlist": ["AAPL"], "settings": {"trading_mode": "paper"}}
        (tmp_data_dir / "watchlist.json").write_text(json.dumps(wl))
        with patch("titantrade.api.live_keys_configured", return_value=True):
            resp = client.put(
                "/api/settings/mode",
                json={"trading_mode": "live"},
            )
        assert resp.status_code == 200
        assert resp.json()["trading_mode"] == "live"
        # Verify persisted
        saved = json.loads((tmp_data_dir / "watchlist.json").read_text())
        assert saved["settings"]["trading_mode"] == "live"

    def test_switch_to_paper(self, client, tmp_data_dir: Path):
        wl = {"watchlist": ["AAPL"], "settings": {"trading_mode": "live"}}
        (tmp_data_dir / "watchlist.json").write_text(json.dumps(wl))
        with patch("titantrade.api.live_keys_configured", return_value=True):
            resp = client.put(
                "/api/settings/mode",
                json={"trading_mode": "paper"},
            )
        assert resp.status_code == 200
        assert resp.json()["trading_mode"] == "paper"

    def test_live_without_keys_returns_400(self, client, tmp_data_dir: Path):
        wl = {"watchlist": ["AAPL"], "settings": {"trading_mode": "paper"}}
        (tmp_data_dir / "watchlist.json").write_text(json.dumps(wl))
        with patch("titantrade.api.live_keys_configured", return_value=False):
            resp = client.put(
                "/api/settings/mode",
                json={"trading_mode": "live"},
            )
        assert resp.status_code == 400
        assert "not configured" in resp.json()["detail"]

    def test_invalid_mode_returns_400(self, client, tmp_data_dir: Path):
        with patch("titantrade.api.live_keys_configured", return_value=True):
            resp = client.put(
                "/api/settings/mode",
                json={"trading_mode": "turbo"},
            )
        assert resp.status_code == 400
