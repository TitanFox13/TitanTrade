"""Tests for the built-in scheduler module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from titantrade.scheduler import (
    COMMANDS,
    _execute_job,
    _load_schedule,
    get_all_jobs,
    get_job_history,
    set_job_enabled,
    start_scheduler,
    stop_scheduler,
    trigger_job,
    _job_config,
    _job_history,
)


@pytest.fixture(autouse=True)
def _clean_scheduler():
    """Reset scheduler state between tests."""
    import titantrade.scheduler as mod
    mod._scheduler = None
    mod._job_config = []
    mod._job_history = {}
    mod._schedule_timezone = "UTC"
    yield
    if mod._scheduler:
        mod._scheduler.shutdown(wait=False)
        mod._scheduler = None


@pytest.fixture
def schedule_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("titantrade.scheduler.DATA_DIR", tmp_path)
    return tmp_path


def _write_schedule(path: Path, jobs: list[dict]) -> None:
    with open(path / "schedule.json", "w") as f:
        json.dump({"timezone": "UTC", "jobs": jobs}, f)


class TestLoadSchedule:
    def test_loads_jobs(self, schedule_dir: Path):
        _write_schedule(schedule_dir, [
            {"id": "test1", "name": "Test", "command": "pricecheck", "cron": {"hour": 10}, "enabled": True},
        ])
        jobs = _load_schedule()
        assert len(jobs) == 1
        assert jobs[0]["id"] == "test1"

    def test_missing_file_returns_empty(self, schedule_dir: Path):
        assert _load_schedule() == []


class TestTimezone:
    """Cron times are interpreted in the schedule's top-level timezone so
    market-relative jobs track DST automatically (the pre-close cycle no
    longer drifts past the close in summer)."""

    def _write_tz_schedule(self, path: Path, tz: str) -> None:
        with open(path / "schedule.json", "w") as f:
            json.dump({"timezone": tz, "jobs": [
                {"id": "preclose", "name": "Pre-Close", "command": "sentry_execute",
                 "cron": {"day_of_week": "mon-fri", "hour": 15, "minute": 30}, "enabled": True},
            ]}, f)

    def test_scheduler_uses_configured_timezone(self, schedule_dir: Path):
        self._write_tz_schedule(schedule_dir, "America/New_York")
        start_scheduler()
        import titantrade.scheduler as mod
        assert "New_York" in str(mod._scheduler.timezone)
        stop_scheduler()

    def test_missing_timezone_defaults_utc(self, schedule_dir: Path):
        with open(schedule_dir / "schedule.json", "w") as f:
            json.dump({"jobs": [
                {"id": "j", "name": "J", "command": "pricecheck",
                 "cron": {"hour": 10}, "enabled": True},
            ]}, f)
        start_scheduler()
        import titantrade.scheduler as mod
        assert str(mod._scheduler.timezone) == "UTC"
        stop_scheduler()

    def test_toggle_preserves_timezone(self, schedule_dir: Path):
        """set_job_enabled must not clobber the timezone back to UTC when it
        rewrites schedule.json (the Flutter app toggles jobs via this path)."""
        self._write_tz_schedule(schedule_dir, "America/New_York")
        start_scheduler()
        set_job_enabled("preclose", False)
        stop_scheduler()
        with open(schedule_dir / "schedule.json") as f:
            data = json.load(f)
        assert data["timezone"] == "America/New_York"


class TestCommandRegistry:
    def test_all_commands_are_callable(self):
        for name, fn in COMMANDS.items():
            assert callable(fn), f"Command {name} is not callable"

    def test_expected_commands_exist(self):
        expected = {"full", "fetch", "sentry", "execute", "sentry_execute", "pricecheck", "gapcheck", "resubmit", "daily_summary"}
        assert set(COMMANDS.keys()) == expected

    def test_fetch_command_registered(self):
        """A daily `fetch` job keeps the data bundle fresh — without it the
        bundle only refreshed weekly and aged to 120h+ between Sunday runs,
        making trend-regime/ATR decisions run on stale data."""
        assert "fetch" in COMMANDS
        assert callable(COMMANDS["fetch"])


class TestExecuteJob:
    def test_successful_run(self):
        with patch.dict(COMMANDS, {"test_cmd": lambda: "ok"}):
            _execute_job("job1", "test_cmd")
        history = get_job_history("job1")
        assert len(history) == 1
        assert history[0]["status"] == "completed"
        assert history[0]["result"] == "ok"

    def test_failed_run(self):
        def _fail():
            raise RuntimeError("boom")

        with patch.dict(COMMANDS, {"fail_cmd": _fail}):
            _execute_job("job2", "fail_cmd")
        history = get_job_history("job2")
        assert len(history) == 1
        assert history[0]["status"] == "failed"
        assert "boom" in history[0]["error"]

    def test_history_capped(self):
        with patch.dict(COMMANDS, {"fast": lambda: "ok"}):
            for _ in range(25):
                _execute_job("capped", "fast")
        assert len(get_job_history("capped")) == 20


class TestStartStopScheduler:
    def test_start_and_stop(self, schedule_dir: Path):
        _write_schedule(schedule_dir, [
            {"id": "t1", "name": "T1", "command": "pricecheck", "cron": {"hour": 10}, "enabled": True},
            {"id": "t2", "name": "T2", "command": "gapcheck", "cron": {"hour": 12}, "enabled": False},
        ])
        start_scheduler()
        jobs = get_all_jobs()
        assert len(jobs) == 2
        # Only enabled job should have next_run
        enabled_job = next(j for j in jobs if j["id"] == "t1")
        disabled_job = next(j for j in jobs if j["id"] == "t2")
        assert enabled_job["next_run"] is not None
        assert disabled_job["next_run"] is None
        stop_scheduler()

    def test_unknown_command_skipped(self, schedule_dir: Path):
        _write_schedule(schedule_dir, [
            {"id": "bad", "name": "Bad", "command": "nonexistent", "cron": {"hour": 10}, "enabled": True},
        ])
        start_scheduler()
        # Should not crash, job just not registered in APScheduler
        stop_scheduler()


class TestTriggerJob:
    def test_trigger_known_job(self, schedule_dir: Path):
        _write_schedule(schedule_dir, [
            {"id": "j1", "name": "J1", "command": "pricecheck", "cron": {"hour": 10}, "enabled": True},
        ])
        start_scheduler()
        assert trigger_job("j1") is True
        stop_scheduler()

    def test_trigger_unknown_job(self, schedule_dir: Path):
        _write_schedule(schedule_dir, [])
        start_scheduler()
        assert trigger_job("nonexistent") is False
        stop_scheduler()


class TestSetJobEnabled:
    def test_disable_and_enable(self, schedule_dir: Path):
        _write_schedule(schedule_dir, [
            {"id": "toggle", "name": "Toggle", "command": "pricecheck", "cron": {"hour": 10}, "enabled": True},
        ])
        start_scheduler()

        assert set_job_enabled("toggle", False) is True
        jobs = get_all_jobs()
        assert jobs[0]["enabled"] is False
        assert jobs[0]["next_run"] is None

        assert set_job_enabled("toggle", True) is True
        jobs = get_all_jobs()
        assert jobs[0]["enabled"] is True
        assert jobs[0]["next_run"] is not None

        stop_scheduler()

    def test_persists_to_file(self, schedule_dir: Path):
        _write_schedule(schedule_dir, [
            {"id": "persist", "name": "P", "command": "pricecheck", "cron": {"hour": 10}, "enabled": True},
        ])
        start_scheduler()
        set_job_enabled("persist", False)
        stop_scheduler()

        # Re-read file
        with open(schedule_dir / "schedule.json") as f:
            data = json.load(f)
        assert data["jobs"][0]["enabled"] is False

    def test_unknown_job_returns_false(self, schedule_dir: Path):
        _write_schedule(schedule_dir, [])
        start_scheduler()
        assert set_job_enabled("nope", True) is False
        stop_scheduler()


class TestSchedulerApiEndpoints:
    """Test the API endpoints for the scheduler."""

    @pytest.fixture
    def client(self, schedule_dir: Path, monkeypatch: pytest.MonkeyPatch):
        # Also patch DATA_DIR in api module
        monkeypatch.setattr("titantrade.api.DATA_DIR", schedule_dir)
        _write_schedule(schedule_dir, [
            {"id": "api_test", "name": "API Test", "command": "pricecheck", "cron": {"hour": 10}, "enabled": True},
        ])

        from fastapi.testclient import TestClient
        from titantrade.api import app
        with TestClient(app) as c:
            yield c

    def test_get_scheduler(self, client):
        resp = client.get("/api/scheduler")
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert len(data["jobs"]) >= 1

    def test_trigger_job(self, client):
        resp = client.post("/api/scheduler/api_test/trigger")
        assert resp.status_code == 200
        assert resp.json()["status"] == "triggered"

    def test_trigger_unknown_returns_404(self, client):
        resp = client.post("/api/scheduler/nonexistent/trigger")
        assert resp.status_code == 404

    def test_enable_disable(self, client):
        resp = client.put(
            "/api/scheduler/api_test/enabled",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
