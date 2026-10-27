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
    # Market-data host and feed. IEX is free and fine for live quotes; SIP is
    # used where full history or the just-closed session is needed (Decisions
    # 058/061) — a SIP query must end >= 15 minutes in the past.
    data_base_url: str = "https://data.alpaca.markets"
    data_feed: str = "iex"


@dataclass(frozen=True)
class FREDConfig:
    """St. Louis Fed (FRED) — the economic-release calendar behind the
    macro-blackout gate. Key is optional: without it the gate fails open."""
    key: str = ""
    base_url: str = "https://api.stlouisfed.org/fred"


@dataclass(frozen=True)
class FinnhubConfig:
    """Finnhub (free tier) — earnings dates (earnings-blackout gate), sector
    (sector-exposure gate) and analyst recommendations (monthly curator).
    Key is optional: without it those inputs are absent and the gates fail
    open."""
    key: str = ""
    base_url: str = "https://finnhub.io/api/v1"


@dataclass(frozen=True)
class ClaudeConfig:
    """Anthropic Claude — used only by the monthly curator (universe proposal,
    post-mortem). Never in the trading loop (Decision 061)."""
    key: str = ""
    model: str = "claude-opus-4-8"
    max_tokens: int = 16000


@dataclass(frozen=True)
class TradingSettings:
    """Watchlist + the mechanical strategy's parameters (Decisions 061/062).

    Everything here can be changed in ``data/watchlist.json`` without a
    deploy; the executor reads it at every run.
    """
    watchlist: list[str] = field(default_factory=lambda: [
        "CRWD", "ANET", "LLY", "DXCM", "HCA",
        "JPM", "GS", "DVN", "WMT", "URI",
        "GE", "DASH", "DECK", "FCX", "EQIX",
    ])
    trading_mode: str = "paper"

    # Entry: close >= dip_pct below the dip_lookback_days high, above the trend SMA
    dip_pct: float = 0.08
    dip_lookback_days: int = 90
    trend_sma_days: int = 150
    # Sizing: flat slots swapped out of the SPY core
    slot_pct: float = 0.25
    max_slots: int = 3
    # Exits: broker stop, target and holding limit (trading days)
    tp_pct: float = 0.20
    stop_pct: float = 0.12
    max_hold_days: int = 60
    # Insurance: exposure × insurance_scale while SPY < its SMA AND sector
    # breadth < insurance_breadth (two-signal confirmation)
    insurance_sma_days: int = 200
    insurance_breadth: float = 0.5
    insurance_scale: float = 0.5
    sector_etfs: list[str] = field(default_factory=lambda: [
        "XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLB", "XLRE", "XLP", "XLU", "XLC",
    ])

    # Core: SPY is the residual of the book; rebalance when drift exceeds the band
    core_ticker: str = "SPY"
    core_rebalance_band_pct: float = 0.05

    # Momentum sleeve (Decision 068): a momentum ETF held at ``momentum_weight``
    # of the investable book, same rebalance band; the dip overlay's slots are
    # sized on the remaining (1 − momentum_weight) share. 0 = dip book only.
    momentum_ticker: str = "SPMO"
    momentum_weight: float = 0.6
    # Shock trigger (Decision 068): SPY down ``shock_drop_pct`` over
    # ``shock_lookback_days`` sessions → exposure × ``shock_scale`` for the next
    # ``shock_hold_days`` sessions, combined with the insurance by min().
    shock_drop_pct: float = 0.07
    shock_lookback_days: int = 10
    shock_hold_days: int = 20
    shock_scale: float = 0.5

    @property
    def overlay_slot_pct(self) -> float:
        """One dip slot as a share of equity: ``slot_pct`` of the dip sleeve."""
        return self.slot_pct * (1 - self.momentum_weight)


@dataclass(frozen=True)
class Config:
    alpaca: AlpacaConfig
    claude: ClaudeConfig
    trading: TradingSettings
    fred: FREDConfig = field(default_factory=FREDConfig)
    finnhub: FinnhubConfig = field(default_factory=FinnhubConfig)


MECHANICAL_FIELDS = {
    "dip_pct", "dip_lookback_days", "trend_sma_days", "slot_pct", "max_slots",
    "tp_pct", "stop_pct", "max_hold_days", "insurance_sma_days",
    "insurance_breadth", "insurance_scale", "sector_etfs",
    "core_ticker", "core_rebalance_band_pct",
    "momentum_ticker", "momentum_weight",
    "shock_drop_pct", "shock_lookback_days", "shock_hold_days", "shock_scale",
}


def load_watchlist() -> TradingSettings:
    """Load watchlist.json, falling back to defaults.

    ``settings.trading_mode`` (env ``TRADING_MODE`` overrides) and
    ``settings.mechanical`` (any of ``MECHANICAL_FIELDS``) are honoured.
    """
    path = DATA_DIR / "watchlist.json"
    if not path.exists():
        return TradingSettings()
    with open(path) as f:
        data = json.load(f)
    settings = data.get("settings", {}) or {}
    mode = os.environ.get("TRADING_MODE", settings.get("trading_mode", "paper"))
    mech = settings.get("mechanical", {}) or {}
    overrides = {k: v for k, v in mech.items() if k in MECHANICAL_FIELDS}
    return TradingSettings(
        watchlist=data.get("watchlist", TradingSettings().watchlist),
        trading_mode=mode,
        **overrides,
    )


def _read_watchlist_file() -> dict:
    path = DATA_DIR / "watchlist.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"watchlist": TradingSettings().watchlist, "settings": {"trading_mode": "paper"}}


def save_trading_mode(mode: str) -> None:
    """Update the trading_mode in watchlist.json, preserving everything else."""
    if mode not in ("paper", "live"):
        raise ValueError(f"Invalid trading mode: {mode!r} (must be 'paper' or 'live')")
    data = _read_watchlist_file()
    data.setdefault("settings", {})["trading_mode"] = mode
    with open(DATA_DIR / "watchlist.json", "w") as f:
        json.dump(data, f, indent=2)


def save_watchlist(tickers: list[str]) -> None:
    """Update the watchlist tickers in watchlist.json, preserving settings."""
    data = _read_watchlist_file()
    data["watchlist"] = tickers
    with open(DATA_DIR / "watchlist.json", "w") as f:
        json.dump(data, f, indent=2)


REQUIRED_KEYS = {
    "CLAUDE_KEY": "Anthropic Claude (monthly curator)",
}

# Optional keys — absent ones degrade gracefully rather than failing startup.
OPTIONAL_KEYS = ("FRED_KEY", "FINNHUB_KEY")


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

    for key_name in OPTIONAL_KEYS:
        keys[key_name] = os.environ.get(key_name, "").strip()

    keys.update(_resolve_alpaca_keys())
    return keys


def load_config() -> Config:
    """Build the full configuration from env vars and watchlist.json.

    Validates the API keys and selects paper or live Alpaca credentials from
    ``trading_mode``.
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
        alpaca=AlpacaConfig(key=alpaca_key, secret=alpaca_secret, base_url=base_url),
        fred=FREDConfig(key=keys.get("FRED_KEY", "")),
        finnhub=FinnhubConfig(key=keys.get("FINNHUB_KEY", "")),
        claude=ClaudeConfig(
            key=keys["CLAUDE_KEY"],
            model=os.environ.get("CLAUDE_MODEL", "claude-opus-4-8"),
        ),
        trading=trading,
    )
