"""Tests for the structured JSON logger — focus on the daily file rotation
(a long-running process must not pile every day's logs into one file)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from titantrade import logger as tlog


def _record(msg: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="titantrade.testmod", level=logging.INFO, pathname="", lineno=0,
        msg=msg, args=(), exc_info=None,
    )


def test_writes_to_todays_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tlog, "LOGS_DIR", tmp_path)
    h = tlog.DailyJSONFileHandler("testmod")
    h.setFormatter(tlog.JSONFormatter())
    h.emit(_record("hello"))
    h.close()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    f = tmp_path / f"testmod_{today}.json"
    assert f.exists()
    assert json.loads(f.read_text().strip())["message"] == "hello"


def test_rolls_to_new_file_after_midnight(tmp_path, monkeypatch):
    """Simulate a handler created on a previous day: the next emit must roll
    to the current date's file rather than keep writing the stale one."""
    monkeypatch.setattr(tlog, "LOGS_DIR", tmp_path)
    h = tlog.DailyJSONFileHandler("testmod")
    h.setFormatter(tlog.JSONFormatter())

    # Pretend the handler was created yesterday (process started before midnight).
    h._date = "2000-01-01"
    h.emit(_record("after midnight"))
    h.close()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rolled = tmp_path / f"testmod_{today}.json"
    stale = tmp_path / "testmod_2000-01-01.json"
    assert rolled.exists(), "should write to the current date's file"
    assert json.loads(rolled.read_text().strip())["message"] == "after midnight"
    assert not stale.exists(), "must not write to the stale process-start-dated file"
