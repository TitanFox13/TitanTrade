"""Fill-vs-backtest ledger (Decision 069): one row per entry, the fill against the session's close."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from titantrade import fill_ledger as fl


def _trade(tid: str, ticker: str, ts: str, price: float, fill: float | None = None, **extra) -> dict:
    t = {"id": tid, "ticker": ticker, "action": "BUY", "trigger": "entry", "timestamp": ts, "price": price, **extra}
    if fill is not None:
        t["fill_price"] = fill
    return t


class TestMaths:
    def test_gap_is_fill_over_close(self):
        assert fl.fill_gap_pct(101.0, 100.0) == pytest.approx(1.0)
        assert fl.fill_gap_pct(99.0, 100.0) == pytest.approx(-1.0)

    def test_session_date_is_eastern(self):
        # 14:15 UTC and 19:30 UTC are the same Eastern session; 02:00 UTC belongs to the previous one.
        assert fl.session_date("2026-10-27T14:15:00+00:00") == "2026-10-27"
        assert fl.session_date("2026-10-27T19:30:00Z") == "2026-10-27"
        assert fl.session_date("2026-10-28T02:00:00+00:00") == "2026-10-27"

    def test_summary(self):
        assert fl.summary([]) == {"n": 0}
        s = fl.summary([{"gap_pct": 0.5, "fill_known": True}, {"gap_pct": -0.2, "fill_known": False}, {"gap_pct": 1.1, "fill_known": True}])
        assert s == {"n": 3, "median_gap_pct": 0.5, "mean_gap_pct": pytest.approx(0.467, abs=1e-3), "worst_gap_pct": 1.1, "fills_known": 2}


class TestUpdate:
    def test_rows_appended_once_with_the_session_close(self, fake_config, tmp_state_dir):
        now = datetime.now(timezone.utc)
        today = fl.session_date(now.isoformat())
        old = (now - timedelta(days=40)).isoformat()
        (tmp_state_dir / "trade_log.json").write_text(json.dumps({"trades": [
            _trade("t1", "URI", now.isoformat(), 1068.4, fill=1065.0),       # fill captured
            _trade("t2", "GS", now.isoformat(), 500.0),                       # fill not captured → bracket limit, flagged
            _trade("t3", "JPM", old, 300.0),                                  # too old: left alone
            {**_trade("t4", "URI", now.isoformat(), 1.0), "action": "SELL", "trigger": "target"},   # not an entry
        ]}))
        bars = lambda ticker, cfg, days, feed: [{"date": today, "close": {"URI": 1060.0, "GS": 505.0}[ticker]}]  # noqa: E731
        assert fl.update_fill_ledger(fake_config, bars_for=bars) == 2
        rows = fl.load_ledger()["rows"]
        assert [r["trade_id"] for r in rows] == ["t1", "t2"]
        assert rows[0] == {"trade_id": "t1", "ticker": "URI", "date": today, "fill_price": 1065.0, "fill_known": True,
                           "backtest_close": 1060.0, "gap_pct": pytest.approx(0.472, abs=1e-3)}
        assert rows[1]["fill_known"] is False and rows[1]["fill_price"] == 500.0 and rows[1]["gap_pct"] == pytest.approx(-0.99, abs=1e-2)
        # idempotent: a second run adds nothing
        assert fl.update_fill_ledger(fake_config, bars_for=bars) == 0

    def test_missing_bar_or_failed_fetch_is_retried_later(self, fake_config, tmp_state_dir):
        now = datetime.now(timezone.utc).isoformat()
        (tmp_state_dir / "trade_log.json").write_text(json.dumps({"trades": [_trade("t1", "URI", now, 100.0), _trade("t2", "GS", now, 100.0)]}))

        def bars(ticker, cfg, days, feed):
            if ticker == "GS":
                raise RuntimeError("alpaca down")
            return [{"date": "2020-01-02", "close": 99.0}]   # today's bar not published yet
        assert fl.update_fill_ledger(fake_config, bars_for=bars) == 0
        assert not (tmp_state_dir / fl.LEDGER_FILE).exists()

    def test_no_trade_log(self, fake_config, tmp_state_dir):
        assert fl.update_fill_ledger(fake_config, bars_for=lambda *a, **k: []) == 0


class TestSurfaces:
    def test_api_serves_summary_and_rows(self, tmp_state_dir):
        from fastapi.testclient import TestClient

        from titantrade.api import app
        (tmp_state_dir / fl.LEDGER_FILE).write_text(json.dumps({"rows": [{"trade_id": "t1", "ticker": "URI", "date": "2026-10-27", "gap_pct": 0.3, "fill_known": True}]}))
        body = TestClient(app).get("/api/fill-ledger").json()
        assert body["summary"]["n"] == 1 and body["rows"][0]["ticker"] == "URI"

    def test_daily_summary_field(self, tmp_state_dir, monkeypatch):
        from unittest.mock import MagicMock, patch

        from titantrade import notifier
        monkeypatch.setattr("titantrade.notifier.STATE_DIR", tmp_state_dir, raising=False)
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/x")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        (tmp_state_dir / fl.LEDGER_FILE).write_text(json.dumps({"rows": [
            {"trade_id": "t1", "ticker": "URI", "date": today, "gap_pct": 0.3, "fill_known": True},
            {"trade_id": "t0", "ticker": "JPM", "date": "2026-10-01", "gap_pct": -0.1, "fill_known": True},
        ]}))
        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            notifier.send_daily_summary()
        fields = {f["name"]: f["value"] for f in mock_post.call_args.kwargs["json"]["embeds"][0]["fields"]}
        assert fields["Fill vs backtest"] == "2 entries, median gap +0.10% | today: URI +0.30%"
