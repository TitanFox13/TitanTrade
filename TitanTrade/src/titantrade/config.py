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
    base_url: str = "https://api.sec-api.io"


@dataclass(frozen=True)
class ClaudeConfig:
    key: str = ""
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.3
    max_tokens: int = 8192


@dataclass(frozen=True)
class GeminiConfig:
    key: str = ""
    model: str = "gemini-2.5-flash"
    temperature: float = 0.1
    max_tokens: int = 1024


@dataclass(frozen=True)
class TradingSettings:
    watchlist: list[str] = field(default_factory=lambda: [
        "CRWD", "ANET", "LLY", "DXCM", "HCA",
        "JPM", "GS", "DVN", "FANG", "URI",
        "GE", "DASH", "DECK", "FCX", "EQIX",
    ])
    risk_per_trade: float = 0.10
    trading_mode: str = "paper"
    stop_loss_pct: float = 0.05
    trailing_trigger_pct: float = 0.05   # Activate trailing stop after 5% gain
    trailing_distance_pct: float = 0.03  # Trail 3% below high-water mark
    hedge_instruments: list[str] = field(default_factory=lambda: [
        "SH",    # Inverse S&P 500 (1x)
        "PSQ",   # Inverse Nasdaq 100 (1x)
        "SDS",   # Inverse S&P 500 (2x) — more aggressive
    ])


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


def save_trading_mode(mode: str) -> None:
    """Update the trading_mode in watchlist.json, preserving everything else."""
    if mode not in ("paper", "live"):
        raise ValueError(f"Invalid trading mode: {mode!r} (must be 'paper' or 'live')")
    path = DATA_DIR / "watchlist.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
    else:
        data = {"watchlist": TradingSettings().watchlist, "settings": {}}
    data.setdefault("settings", {})["trading_mode"] = mode
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


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
}


def _resolve_alpaca_keys() -> dict[str, str]:
    """Resolve Alpaca paper and live credentials.

    Paper keys are required (falls back to legacy ALPACA_KEY/ALPACA_SECRET).
    Live keys are optional — live trading is only available when they're set.
    """
    paper_key = os.environ.get("ALPACA_PAPER_KEY", "").strip()
    paper_secret = os.environ.get("ALPACA_PAPER_SECRET", "").strip()

    # Backward compat: fall back to legacy single-credential env vars
    if not paper_key:
        paper_key = os.environ.get("ALPACA_KEY", "").strip()
    if not paper_secret:
        paper_secret = os.environ.get("ALPACA_SECRET", "").strip()

    if not paper_key or not paper_secret:
        raise ValueError(
            "Missing Alpaca paper trading credentials.\n"
            "Set ALPACA_PAPER_KEY and ALPACA_PAPER_SECRET in your .env file.\n"
            "(Legacy ALPACA_KEY / ALPACA_SECRET are also accepted.)"
        )

    return {
        "ALPACA_PAPER_KEY": paper_key,
        "ALPACA_PAPER_SECRET": paper_secret,
        "ALPACA_LIVE_KEY": os.environ.get("ALPACA_LIVE_KEY", "").strip(),
        "ALPACA_LIVE_SECRET": os.environ.get("ALPACA_LIVE_SECRET", "").strip(),
    }


def live_keys_configured() -> bool:
    """Return True if live Alpaca credentials are present in the environment."""
    return bool(
        os.environ.get("ALPACA_LIVE_KEY", "").strip()
        and os.environ.get("ALPACA_LIVE_SECRET", "").strip()
    )


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

    # Merge in Alpaca keys (has its own validation)
    keys.update(_resolve_alpaca_keys())
    return keys


def load_config() -> Config:
    """Build the full configuration from env vars and watchlist.json.

    Validates all API keys are present before returning.
    Selects paper or live Alpaca credentials based on trading_mode.
    """
    keys = validate_api_keys()
    trading = load_watchlist()

    if trading.trading_mode == "live":
        if not keys["ALPACA_LIVE_KEY"] or not keys["ALPACA_LIVE_SECRET"]:
            raise ValueError(
                "Live trading mode is enabled but ALPACA_LIVE_KEY / "
                "ALPACA_LIVE_SECRET are not set in .env."
            )
        alpaca_key = keys["ALPACA_LIVE_KEY"]
        alpaca_secret = keys["ALPACA_LIVE_SECRET"]
    else:
        alpaca_key = keys["ALPACA_PAPER_KEY"]
        alpaca_secret = keys["ALPACA_PAPER_SECRET"]

    base_url = os.environ.get("ALPACA_BASE_URL")
    if base_url is None:
        base_url = (
            "https://api.alpaca.markets"
            if trading.trading_mode == "live"
            else "https://paper-api.alpaca.markets"
        )

    return Config(
        alpaca=AlpacaConfig(
            key=alpaca_key,
            secret=alpaca_secret,
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
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        ),
        gemini=GeminiConfig(
            key=keys["GEMINI_KEY"],
            model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        ),
        trading=trading,
    )
