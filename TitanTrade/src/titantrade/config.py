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
    # Market-data API is a different host from the trading API. Same keys.
    # Free plan serves the IEX feed, which is all we need for daily bars,
    # latest trades, and news.
    data_base_url: str = "https://data.alpaca.markets"
    data_feed: str = "iex"


@dataclass(frozen=True)
class FMPConfig:
    # Retained only so legacy code / test fixtures that reference cfg.fmp keep
    # working. FMP was fully replaced by Alpaca + FRED + Yahoo (see ADR 040);
    # the key is no longer required.
    key: str = ""
    base_url: str = "https://financialmodelingprep.com/api/v3"


@dataclass(frozen=True)
class FREDConfig:
    """St. Louis Fed (FRED) — free, official source for VIX, treasury yields,
    and the economic-release calendar. Key is optional: without it those
    macro inputs are simply absent (the macro-blackout gate fails open)."""
    key: str = ""
    base_url: str = "https://api.stlouisfed.org/fred"


@dataclass(frozen=True)
class FinnhubConfig:
    """Finnhub (free tier) — per-ticker earnings dates, analyst recommendation
    trends, and sector/industry. Key is optional: without it those per-ticker
    enrichments are absent (earnings-blackout gate fails open; Claude simply
    sees no analyst block)."""
    key: str = ""
    base_url: str = "https://finnhub.io/api/v1"


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
    max_tokens: int = 2048


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
    # ATR-based trailing distance. Set to 2.5 ATRs below HWM by default — gives
    # volatility room so we don't crystallize winners on noise. A 3% fixed
    # trail (the prior default) stopped a 25% URI winner on first dip in
    # production. Falls back to ``trailing_distance_pct`` only when ATR
    # isn't available.
    trailing_atr_multiplier: float = 2.5
    trailing_distance_pct: float = 0.05  # Fallback %-trail if ATR missing (was 3%, now 5%)
    # Take-profit tranche: at this fraction of the entry→TP distance, sell
    # ``tp1_fraction`` of the position and raise the stop to breakeven.
    # The remainder runs with the trailing stop. De-risks while keeping
    # the runway open for outsized winners.
    tp1_trigger_fraction: float = 0.5  # Trigger at 50% of upside-to-TP
    tp1_fraction: float = 0.333         # Sell 1/3 at TP1

    # Pyramid: add to a winning position when it's working. Aligned with the
    # "ride the wave" mandate — current behavior caps at one entry per
    # ticker and just trails. Adds happen exactly once per position, at
    # ``pyramid_trigger_pct`` gain, sizing ``pyramid_size_fraction`` of the
    # original position's notional (so the average entry walks up but the
    # position doesn't blow past concentration caps).
    pyramid_enabled: bool = True
    pyramid_trigger_pct: float = 0.05      # Add when gain >= 5%
    pyramid_size_fraction: float = 0.5     # Add 50% of original notional
    pyramid_max_total_pct: float = 0.30    # Hard cap on total position size
    hedge_instruments: list[str] = field(default_factory=lambda: [
        "SH",    # Inverse S&P 500 (1x)
        "PSQ",   # Inverse Nasdaq 100 (1x)
        "SDS",   # Inverse S&P 500 (2x) — more aggressive
    ])
    # --- Core/hedge allocation (Phase 3: "always deployed") ---
    # The core position is a baseline market exposure that's always on,
    # independent of the AI thesis. AI-picks are *overlays* on top of this.
    # When sentry detects market stress, the core ticker is swapped for a
    # hedge ticker (inverse ETF). Cash is transit, never a destination.
    core_ticker: str = "SPY"        # Default-on market exposure
    core_hedge_ticker: str = "SH"   # Inverse swap when market stress fires
    core_allocation_pct: float = 0.30  # Target 30% of portfolio in the core
    core_rebalance_band_pct: float = 0.05  # Rebalance if drift exceeds 5%pts


@dataclass(frozen=True)
class Config:
    alpaca: AlpacaConfig
    fmp: FMPConfig
    claude: ClaudeConfig
    gemini: GeminiConfig
    trading: TradingSettings
    fred: FREDConfig = field(default_factory=FREDConfig)
    finnhub: FinnhubConfig = field(default_factory=FinnhubConfig)


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
    "CLAUDE_KEY": "Anthropic Claude (weekly analysis)",
    "GEMINI_KEY": "Google Gemini (daily sentry)",
}

# Optional keys — absent ones degrade gracefully rather than failing startup.
#   FMP_KEY  — legacy; FMP was fully replaced (ADR 040), no longer used.
#   FRED_KEY — St. Louis Fed: VIX, treasury, economic calendar. Without it
#              those macro inputs are absent and the macro-blackout gate
#              fails open (its existing behaviour on a data error).
OPTIONAL_KEYS = ("FMP_KEY", "FRED_KEY", "FINNHUB_KEY")


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

    # Optional keys: included if present, never block startup.
    for key_name in OPTIONAL_KEYS:
        keys[key_name] = os.environ.get(key_name, "").strip()

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
            key=keys.get("FMP_KEY", ""),
        ),
        fred=FREDConfig(
            key=keys.get("FRED_KEY", ""),
        ),
        finnhub=FinnhubConfig(
            key=keys.get("FINNHUB_KEY", ""),
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
