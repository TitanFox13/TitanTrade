"""Structured JSON logging for all TitanTrade modules."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from titantrade.config import LOGS_DIR


class DailyJSONFileHandler(logging.FileHandler):
    """File handler that rolls to a new ``{name}_{YYYY-MM-DD}.json`` file at UTC
    midnight.

    The plain ``FileHandler`` fixes its filename when the handler is created.
    Loggers are created once per process (cached by ``get_logger``), so a
    long-running process (the API container) would otherwise pile every day's
    records into the file dated at process start. This handler re-points the
    stream to the current date's file on the first emit after midnight,
    preserving the one-file-per-module-per-day convention.
    """

    def __init__(self, base_name: str) -> None:
        self._base_name = base_name
        self._date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        super().__init__(self._path(self._date), encoding="utf-8", delay=True)

    def _path(self, date_str: str):
        return LOGS_DIR / f"{self._base_name}_{date_str}.json"

    def emit(self, record: logging.LogRecord) -> None:
        current = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if current != self._date:
            self._date = current
            self.baseFilename = os.fspath(self._path(current))
            if self.stream:
                self.stream.close()
                self.stream = None  # FileHandler.emit reopens with the new name
        super().emit(record)


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

    # File handler - structured JSON, one file per module per day. Rolls at
    # UTC midnight even for a long-running process (see DailyJSONFileHandler).
    file_handler = DailyJSONFileHandler(name)
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
