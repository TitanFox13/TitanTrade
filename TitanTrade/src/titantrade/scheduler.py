"""Built-in job scheduler — runs trading jobs inside the API process.

Jobs are defined in data/schedule.json and executed via APScheduler's
BackgroundScheduler.  Each job calls the same functions as the CLI commands.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from .config import DATA_DIR

log = logging.getLogger("titantrade.scheduler")

_scheduler: BackgroundScheduler | None = None
_job_config: list[dict[str, Any]] = []
_job_history: dict[str, list[dict[str, Any]]] = {}
_lock = threading.Lock()

MAX_HISTORY = 20


# ---------------------------------------------------------------------------
# Command registry — maps command strings to callable functions
# ---------------------------------------------------------------------------

def _run_full() -> str:
    from .config import load_config
    from .weekly_analyst import run_weekly_analysis
    from .daily_sentry import run_daily_sentry
    from .executor import execute_trades

    cfg = load_config()
    run_weekly_analysis(cfg)
    run_daily_sentry(cfg)
    trades = execute_trades(cfg)
    return f"{len(trades)} trades executed"


def _run_fetch() -> str:
    from .data_fetcher import main as fetch_main
    fetch_main()
    return "data bundle refreshed"


def _run_sentry() -> str:
    from .daily_sentry import main as sentry_main
    sentry_main()
    return "sentry complete"


def _run_execute() -> str:
    from .executor import main as executor_main
    executor_main()
    return "executor complete"


def _run_sentry_execute() -> str:
    from .config import load_config
    from .daily_sentry import run_daily_sentry
    from .executor import execute_trades

    cfg = load_config()
    run_daily_sentry(cfg)
    trades = execute_trades(cfg)
    return f"sentry + {len(trades)} trades"


def _run_pricecheck() -> str:
    from .price_check import main as pc_main
    pc_main()
    return "pricecheck complete"


def _run_gapcheck() -> str:
    from .config import load_config
    from .executor import check_gap_down_protection

    cfg = load_config()
    trades = check_gap_down_protection(cfg)
    return f"{len(trades)} positions closed"


def _run_resubmit() -> str:
    from .config import STATE_DIR, load_config
    from .executor import get_positions, resubmit_expired_brackets

    cfg = load_config()
    thesis_path = STATE_DIR / "weekly_thesis.json"
    bundle_path = STATE_DIR / "data_bundle.json"

    if not thesis_path.exists():
        return "no thesis found"

    with open(thesis_path) as f:
        thesis_doc = json.load(f)
    data_bundle = {}
    if bundle_path.exists():
        with open(bundle_path) as f:
            data_bundle = json.load(f)

    positions = get_positions(cfg)
    trades = resubmit_expired_brackets(cfg, thesis_doc, positions, data_bundle)
    return f"{len(trades)} brackets resubmitted"


def _run_daily_summary() -> str:
    from .notifier import send_daily_summary
    return send_daily_summary()


COMMANDS: dict[str, callable] = {
    "full": _run_full,
    "fetch": _run_fetch,
    "sentry": _run_sentry,
    "execute": _run_execute,
    "sentry_execute": _run_sentry_execute,
    "pricecheck": _run_pricecheck,
    "gapcheck": _run_gapcheck,
    "resubmit": _run_resubmit,
    "daily_summary": _run_daily_summary,
}


# ---------------------------------------------------------------------------
# Job execution wrapper (called by APScheduler)
# ---------------------------------------------------------------------------

def _execute_job(job_id: str, command: str) -> None:
    """Run a command and record the result in job history."""
    run: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "status": "running",
        "result": None,
        "error": None,
    }

    with _lock:
        _job_history.setdefault(job_id, []).insert(0, run)
        # Trim history
        _job_history[job_id] = _job_history[job_id][:MAX_HISTORY]

    # Resolve human-readable name for notifications
    job_name = job_id
    for job_def in _job_config:
        if job_def["id"] == job_id:
            job_name = job_def.get("name", job_id)
            break

    log.info(f"Scheduler: starting job {job_id} (command={command})")
    started = datetime.now(timezone.utc)

    try:
        fn = COMMANDS[command]
        result = fn()
        run["status"] = "completed"
        run["result"] = result
        log.info(f"Scheduler: job {job_id} completed — {result}")
    except Exception as exc:
        run["status"] = "failed"
        run["error"] = str(exc)
        log.exception(f"Scheduler: job {job_id} failed")
    finally:
        run["finished_at"] = datetime.now(timezone.utc).isoformat()
        duration = (datetime.now(timezone.utc) - started).total_seconds()

        # Send Discord notification (never crash the job)
        try:
            from .notifier import notify_job_completed, notify_job_failed
            if run["status"] == "completed":
                notify_job_completed(job_name, run["result"], duration)
            elif run["status"] == "failed":
                notify_job_failed(job_name, run["error"] or "unknown error", duration)
        except Exception:
            log.exception("Failed to send Discord notification")


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def _load_schedule() -> list[dict[str, Any]]:
    """Read data/schedule.json."""
    path = DATA_DIR / "schedule.json"
    if not path.exists():
        log.warning(f"Schedule file not found: {path}")
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("jobs", [])


def start_scheduler() -> None:
    """Read schedule.json, register all enabled jobs, and start."""
    global _scheduler, _job_config

    _job_config = _load_schedule()
    _scheduler = BackgroundScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
    )

    for job in _job_config:
        if not job.get("enabled", True):
            continue
        command = job["command"]
        if command not in COMMANDS:
            log.warning(f"Unknown command {command!r} in job {job['id']}")
            continue

        cron = job["cron"]
        trigger = CronTrigger(**cron)
        _scheduler.add_job(
            _execute_job,
            trigger=trigger,
            args=[job["id"], command],
            id=job["id"],
            name=job.get("name", job["id"]),
            replace_existing=True,
        )
        log.info(f"Registered job: {job['id']} ({command}) — {cron}")

    _scheduler.start()
    log.info(f"Scheduler started with {len(_scheduler.get_jobs())} jobs")


def stop_scheduler() -> None:
    """Shut down the scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")
        _scheduler = None


# ---------------------------------------------------------------------------
# Public query / control API
# ---------------------------------------------------------------------------

def get_all_jobs() -> list[dict[str, Any]]:
    """Return all configured jobs with next_run and last_run info."""
    result = []
    for job_def in _job_config:
        job_id = job_def["id"]
        entry: dict[str, Any] = {
            "id": job_id,
            "name": job_def.get("name", job_id),
            "command": job_def["command"],
            "cron": job_def["cron"],
            "enabled": job_def.get("enabled", True),
            "next_run": None,
            "last_run": None,
        }

        # Next run from APScheduler
        if _scheduler:
            ap_job = _scheduler.get_job(job_id)
            if ap_job and ap_job.next_run_time:
                entry["next_run"] = ap_job.next_run_time.isoformat()

        # Last run from history
        with _lock:
            history = _job_history.get(job_id, [])
            if history:
                entry["last_run"] = history[0]

        result.append(entry)
    return result


def get_job_history(job_id: str) -> list[dict[str, Any]]:
    """Return run history for a specific job."""
    with _lock:
        return list(_job_history.get(job_id, []))


def trigger_job(job_id: str) -> bool:
    """Manually trigger a job to run immediately. Returns False if job not found."""
    # Find the command for this job
    command = None
    for job_def in _job_config:
        if job_def["id"] == job_id:
            command = job_def["command"]
            break

    if command is None or command not in COMMANDS:
        return False

    if _scheduler:
        _scheduler.add_job(
            _execute_job,
            trigger=DateTrigger(),
            args=[job_id, command],
            id=f"{job_id}_manual",
            name=f"{job_id} (manual)",
            replace_existing=True,
        )
    return True


def set_job_enabled(job_id: str, enabled: bool) -> bool:
    """Enable or disable a job. Updates schedule.json and APScheduler."""
    # Update in-memory config
    found = False
    for job_def in _job_config:
        if job_def["id"] == job_id:
            job_def["enabled"] = enabled
            found = True
            break
    if not found:
        return False

    # Update APScheduler
    if _scheduler:
        if enabled:
            # Re-add the job
            job_def_match = next(j for j in _job_config if j["id"] == job_id)
            command = job_def_match["command"]
            if command in COMMANDS:
                trigger = CronTrigger(**job_def_match["cron"])
                _scheduler.add_job(
                    _execute_job,
                    trigger=trigger,
                    args=[job_id, command],
                    id=job_id,
                    name=job_def_match.get("name", job_id),
                    replace_existing=True,
                )
        else:
            ap_job = _scheduler.get_job(job_id)
            if ap_job:
                _scheduler.remove_job(job_id)

    # Persist to schedule.json
    _save_schedule()
    return True


def _save_schedule() -> None:
    """Write the current schedule config back to data/schedule.json."""
    path = DATA_DIR / "schedule.json"
    data = {"timezone": "UTC", "jobs": _job_config}
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
