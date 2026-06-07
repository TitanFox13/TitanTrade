"""Structured JSON logging for all TitanTrade modules."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from titantrade.config import LOGS_DIR


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            entry["data"] = record.extra_data
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = str(record.exc_info[1])
        return json.dumps(entry)


def get_logger(name: str) -> logging.Logger:
    """Create a logger that writes structured JSON to both console and file."""
    logger = logging.getLogger(f"titantrade.{name}")
    if logger.handlers:
        return logger

    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level, logging.INFO))

    # Console handler - human readable
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(console)

    # File handler - structured JSON, one file per module per day
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{name}_{today}.json"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    return logger


def log_decision(
    logger: logging.Logger,
    agent: str,
    ticker: str,
    decision: str,
    reasoning: str,
    extra: dict | None = None,
) -> None:
    """Log an AI decision with full context."""
    data = {
        "agent": agent,
        "ticker": ticker,
        "decision": decision,
        "reasoning": reasoning,
        **(extra or {}),
    }
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn="",
        lno=0,
        msg=f"[{agent}] {ticker}: {decision}",
        args=(),
        exc_info=None,
    )
    record.extra_data = data
    logger.handle(record)
