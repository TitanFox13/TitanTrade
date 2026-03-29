"""Central configuration loaded from environment variables and watchlist.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
STATE_DIR = ROOT_DIR / "state"
LOGS_DIR = ROOT_DIR / "logs"

for d in (DATA_DIR, STATE_DIR, LOGS_DIR):
    d.mkdir(exist_ok=True)


@dataclass(frozen=True)
class AlpacaConfig:
    key: str = ""
    secret: str = ""
    base_url: str = "https://paper-api.alpaca.markets"


@dataclass(frozen=True)
class FMPConfig:
    key: str = ""
    base_url: str = "https://financialmodelingprep.com/api/v3"


@dataclass(frozen=True)
class SECAPIConfig:
    key: str = ""
    base_url: str = "https://efts.sec-api.io"


@dataclass(frozen=True)
class ClaudeConfig:
    key: str = ""
    model: str = "claude-sonnet-4-6-20250514"
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass(frozen=True)
class GeminiConfig:
    key: str = ""
    model: str = "gemini-2.0-flash"
    temperature: float = 0.1
    max_tokens: int = 1024


@dataclass(frozen=True)
class TradingSettings:
    watchlist: list[str] = field(default_factory=lambda: [
        "AAPL", "NVDA", "TSLA", "MSFT", "AMZN",
        "GOOGL", "META", "BRK.B", "LLY", "JPM",
    ])
    risk_per_trade: float = 0.10
    trading_mode: str = "paper"
    stop_loss_pct: float = 0.05


@dataclass(frozen=True)
class Config:
    alpaca: AlpacaConfig
    fmp: FMPConfig
    sec_api: SECAPIConfig
    claude: ClaudeConfig
    gemini: GeminiConfig
    trading: TradingSettings


def load_watchlist() -> TradingSettings:
    """Load watchlist.json, falling back to defaults."""
    path = DATA_DIR / "watchlist.json"
    if not path.exists():
        return TradingSettings()
    with open(path) as f:
        data = json.load(f)
    settings = data.get("settings", {})
    mode = os.environ.get("TRADING_MODE", settings.get("trading_mode", "paper"))
    return TradingSettings(
        watchlist=data.get("watchlist", TradingSettings().watchlist),
        risk_per_trade=settings.get("risk_per_trade", 0.10),
        trading_mode=mode,
        stop_loss_pct=settings.get("stop_loss_pct", 0.05),
    )


def save_watchlist(tickers: list[str]) -> None:
    """Update the watchlist tickers in watchlist.json, preserving settings."""
    path = DATA_DIR / "watchlist.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
    else:
        data = {"settings": {"risk_per_trade": 0.10, "trading_mode": "paper", "stop_loss_pct": 0.05}}
    data["watchlist"] = tickers
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


REQUIRED_KEYS = {
    "FMP_KEY": "Financial Modeling Prep (data source)",
    "CLAUDE_KEY": "Anthropic Claude (weekly analysis)",
    "GEMINI_KEY": "Google Gemini (daily sentry)",
    "ALPACA_KEY": "Alpaca Markets (trade execution)",
    "ALPACA_SECRET": "Alpaca Markets (trade execution)",
}


def validate_api_keys() -> dict[str, str]:
    """Check that all required API keys are present and non-empty.

    Returns dict of key_name -> value. Raises ValueError listing all missing keys.
    """
    keys: dict[str, str] = {}
    missing: list[str] = []

    for key_name, description in REQUIRED_KEYS.items():
        value = os.environ.get(key_name, "").strip()
        if not value:
            missing.append(f"  {key_name} - {description}")
        keys[key_name] = value

    if missing:
        raise ValueError(
            "Missing required API keys in .env file:\n"
            + "\n".join(missing)
            + "\n\nCopy .env.example to .env and fill in your keys."
        )

    return keys


def load_config() -> Config:
    """Build the full configuration from env vars and watchlist.json.

    Validates all API keys are present before returning.
    """
    keys = validate_api_keys()
    trading = load_watchlist()

    base_url = os.environ.get("ALPACA_BASE_URL")
    if base_url is None:
        base_url = (
            "https://api.alpaca.markets"
            if trading.trading_mode == "live"
            else "https://paper-api.alpaca.markets"
        )

    return Config(
        alpaca=AlpacaConfig(
            key=keys["ALPACA_KEY"],
            secret=keys["ALPACA_SECRET"],
            base_url=base_url,
        ),
        fmp=FMPConfig(
            key=keys["FMP_KEY"],
        ),
        sec_api=SECAPIConfig(
            key=os.environ.get("SEC_API_KEY", ""),  # optional - degrades gracefully
        ),
        claude=ClaudeConfig(
            key=keys["CLAUDE_KEY"],
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6-20250514"),
        ),
        gemini=GeminiConfig(
            key=keys["GEMINI_KEY"],
            model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        ),
        trading=trading,
    )
