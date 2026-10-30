"""The curator ledger (Decision 082): one row per proposal, outcomes filled per horizon from bars,
the reading guard, the API and the curator hook. Zero network."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from titantrade import curator_ledger as cl

PROPOSAL = {"generated_at": "2025-01-05T20:00:00+00:00", "watchlist": ["AAA", "BBB"], "list": "shadow_watchlist",
            "proposal": {"add": [{"ticker": "ADD", "reason": "x"}, {"ticker": "GONE", "reason": "y"}], "remove": [{"ticker": "RMV", "reason": "z"}]}}
GROWTH = {"SPY": 1.001, "AAA": 1.002, "BBB": 1.0, "ADD": 1.003, "RMV": 0.999}


def _bars(ticker, cfg, days, feed, n=200):
    if ticker not in GROWTH:
        raise RuntimeError("no such symbol")
    d, out = date(2025, 1, 6), []
    for i in range(n):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append({"date": d.isoformat(), "close": 100 * GROWTH[ticker] ** i})
        d += timedelta(days=1)
    return out


def test_record_proposal_once_and_an_empty_one_too(tmp_state_dir):
    assert cl.record_proposal(PROPOSAL) and not cl.record_proposal(PROPOSAL)
    assert cl.record_proposal({**PROPOSAL, "generated_at": "2025-02-02T20:00:00+00:00", "proposal": {}})
    rows = cl.load_ledger()["rows"]
    assert rows[0] == {"proposal_id": PROPOSAL["generated_at"], "date": "2025-01-05", "list": "shadow_watchlist",
                       "members": ["AAA", "BBB"], "adds": ["ADD", "GONE"], "removes": ["RMV"], "outcomes": {}}
    assert rows[1]["adds"] == [] and rows[1]["removes"] == []


def test_outcomes_fill_per_horizon_from_the_first_close_after_the_proposal(fake_config, tmp_state_dir):
    cl.record_proposal(PROPOSAL)
    assert cl.update_curator_ledger(fake_config, bars_for=_bars) == 3          # 200 sessions of bars: 21 / 63 / 126 filled, 252 not yet
    o = cl.load_ledger()["rows"][0]["outcomes"]
    assert set(o) == {"21", "63", "126"}
    assert o["21"]["adds"]["ADD"] == pytest.approx((1.003 ** 21 - 1) * 100, abs=0.01)
    assert o["21"]["adds"]["GONE"] is None                                     # no bars → stays null, the row still fills
    assert o["21"]["removes"]["RMV"] == pytest.approx((0.999 ** 21 - 1) * 100, abs=0.01)
    assert o["21"]["list_ew"] == pytest.approx(((1.002 ** 21 - 1) * 100 + 0) / 2, abs=0.01)
    assert o["21"]["spy"] == pytest.approx((1.001 ** 21 - 1) * 100, abs=0.01) and o["21"]["date"] == _bars("SPY", None, 0, None)[21]["date"]
    assert cl.update_curator_ledger(fake_config, bars_for=_bars) == 0          # idempotent; 252 waits for its session
    assert cl.update_curator_ledger(fake_config, bars_for=lambda *a, **k: _bars(*a, **k, n=300)) == 1


def test_summary_reads_nothing_under_twelve_proposals():
    rows = [{"adds": ["A"], "removes": ["R"], "outcomes": {"126": {"list_ew": 10.0, "spy": 9.0, "adds": {"A": 10.0 + x}, "removes": {"R": 8.0}}}}
            for x in (3.0, -1.0, 2.0)]
    s = cl.summary(rows)
    assert s["proposals"] == 3 and s["verdict"].startswith("No reading under 12")
    assert s["horizons"]["126"]["additions"] == {"n": 3, "median_vs_list_pp": 2.0, "beat_list": 2, "p_luck": 0.5}
    assert s["horizons"]["126"]["removals"]["median_vs_list_pp"] == 2.0 and s["horizons"]["21"] == {"additions": {"n": 0}, "removals": {"n": 0}}
    assert "Reading at 12 proposals, 126 sessions" in cl.summary(rows * 4)["verdict"]


def test_api_serves_the_ledger(tmp_state_dir):
    from fastapi.testclient import TestClient

    from titantrade.api import app
    cl.record_proposal(PROPOSAL)
    body = TestClient(app).get("/api/curator-ledger").json()
    assert body["summary"]["proposals"] == 1 and body["rows"][0]["adds"] == ["ADD", "GONE"]


def test_universe_review_records_the_row(fake_config, tmp_state_dir):
    from titantrade.curator import run_universe_review
    cfg = replace(fake_config, trading=replace(fake_config.trading, shadow_watchlist=["CRWD", "ANET"]))
    (tmp_state_dir / "data_bundle.json").write_text(json.dumps({"stocks": {}}))
    reply = '{"remove": [{"ticker": "CRWD", "reason": "weak"}], "add": [], "notes": "ok"}'
    with patch("titantrade.curator._call_claude", return_value=reply), patch("titantrade.curator._trades", return_value=[]), \
         patch("titantrade.market_data.get_news", return_value=[]), patch("titantrade.market_data.get_analyst_ratings", return_value={}), \
         patch("titantrade.notifier.send_discord"):
        run_universe_review(cfg)
    rows = cl.load_ledger()["rows"]
    assert len(rows) == 1 and rows[0]["removes"] == ["CRWD"] and rows[0]["members"] == ["CRWD", "ANET"] and rows[0]["list"] == "shadow_watchlist"
