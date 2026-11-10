"""The container's health check (Decision 107): /api/health is 503 until the scheduler thread runs."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from titantrade.api import app


def test_health_is_503_without_the_scheduler():
    r = TestClient(app).get("/api/health")   # no lifespan here: the scheduler never started
    assert r.status_code == 503 and r.json() == {"status": "degraded", "scheduler": False}


def test_health_is_200_with_the_scheduler_running():
    with patch("titantrade.api.scheduler_running", return_value=True):
        r = TestClient(app).get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "scheduler": True}
