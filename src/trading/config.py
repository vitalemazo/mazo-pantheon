"""
Centralized Trading Configuration

All configurable parameters for the autonomous trading system.
Values can be overridden via environment variables.

Environment Variable Pattern: TRADING_{SECTION}_{PARAM}
Example: TRADING_RISK_STOP_LOSS_PCT=0.05
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json
import logging

logger = logging.getLogger(__name__)


def _env_float(key: str, default: float) -> float:
    """Get float from environment variable."""
    val = os.environ.get(key)
    if val:
        try:
            return float(val)
        except ValueError:
            logger.warning(f"Invalid float value for {key}: {val}, using default {default}")
    return default


def _env_int(key: str, default: int) -> int:
    """Get int from environment variable."""
    val = os.environ.get(key)
    if val:
        try:
            return int(val)
        except ValueError:
            logger.warning(f"Invalid int value for {key}: {val}, using default {default}")
    return default


def _env_bool(key: str, default: bool) -> bool:
    """Get bool from environment variable."""
    val = os.environ.get(key)
    if val:
        return val.lower() in ("true", "1", "yes", "on")
    return default


def _env_list(key: str, default: List[str]) -> List[str]:
    """Get list from comma-separated environment variable."""
    val = os.environ.get(key)
    if val:
        return [item.strip() for item in val.split(",") if item.strip()]
    return default


@dataclass
class RiskConfig:
    """Risk management parameters."""
    
    # Default position sizing
    default_position_size_pct: float = field(
        default_factory=lambda: _env_float("TRADING_RISK_POSITION_SIZE_PCT", 0.05)
    )
    
    # Stop loss / take profit
    default_stop_loss_pct: float = field(
        default_factory=lambda: _env_float("TRADING_RISK_STOP_LOSS_PCT", 0.05)
    )
    default_take_profit_pct: float = field(
        default_factory=lambda: _env_float("TRADING_RISK_TAKE_PROFIT_PCT", 0.10)
    )
    
    # Position limits
    max_position_pct: float = field(
        default_factory=lambda: _env_float("TRADING_RISK_MAX_POSITION_PCT", 0.20)
    )
    max_sector_pct: float = field(
        default_factory=lambda: _env_float("TRADING_RISK_MAX_SECTOR_PCT", 0.30)
    )
    max_total_positions: int = field(
        default_factory=lambda: _env_int("TRADING_RISK_MAX_POSITIONS", 20)
    )
    
    # Hold time limits
    max_hold_hours: int = field(
        default_factory=lambda: _env_int("TRADING_RISK_MAX_HOLD_HOURS", 120)  # 5 days
    )
    
    # PDT protection
    enforce_pdt: bool = field(
        default_factory=lambda: _env_bool("ENFORCE_PDT", True)  # Enable PDT protection
    )
    pdt_equity_threshold: float = field(
        default_factory=lambda: _env_float("PDT_EQUITY_THRESHOLD", 25000.0)  # PDT threshold
    )


@dataclass
class IntradayConfig:
    """Intraday data settings."""
    
    use_intraday_data: bool = field(
        default_factory=lambda: _env_bool("USE_INTRADAY_DATA", True)
    )
    quote_cache_seconds: int = field(
        default_factory=lambda: _env_int("QUOTE_CACHE_SECONDS", 30)
    )


@dataclass
class SignalConfig:
    """Signal processing parameters."""
    
    # Confidence thresholds
    min_signal_confidence: int = field(
        default_factory=lambda: _env_int("TRADING_SIGNAL_MIN_CONFIDENCE", 60)
    )
    high_confidence_threshold: int = field(
        default_factory=lambda: _env_int("TRADING_SIGNAL_HIGH_CONFIDENCE", 80)
    )
    
    # Processing limits
    max_signals_per_cycle: int = field(
        default_factory=lambda: _env_int("TRADING_SIGNAL_MAX_PER_CYCLE", 5)
    )
    max_tickers_per_cycle: int = field(
        default_factory=lambda: _env_int("TRADING_SIGNAL_MAX_TICKERS", 30)
    )
    
    # Validation depth (quick, standard, deep)
    mazo_validation_depth: str = field(
        default_factory=lambda: os.environ.get("TRADING_SIGNAL_MAZO_DEPTH", "standard")
    )


@dataclass
class CooldownConfig:
    """Trade cooldown and concentration parameters."""
    
    # Minimum minutes between trades for the same ticker
    trade_cooldown_minutes: int = field(
        default_factory=lambda: _env_int("TRADE_COOLDOWN_MINUTES", 30)
    )
    
    # Maximum portfolio percentage allowed per ticker (0.10 = 10%)
    max_position_pct_per_ticker: float = field(
        default_factory=lambda: _env_float("MAX_POSITION_PCT_PER_TICKER", 0.15)
    )
    
    # Enable/disable cooldown checks
    cooldown_enabled: bool = field(
        default_factory=lambda: _env_bool("TRADE_COOLDOWN_ENABLED", True)
    )
    
    # Enable/disable concentration checks
    concentration_check_enabled: bool = field(
        default_factory=lambda: _env_bool("TRADE_CONCENTRATION_CHECK_ENABLED", True)
    )


@dataclass  
class CapitalConfig:
    """Capital management parameters."""
    
    # Minimum buying power threshold to trigger rotation
    min_buying_power_pct: float = field(
        default_factory=lambda: _env_float("TRADING_CAPITAL_MIN_BUYING_POWER_PCT", 0.10)
    )
    
    # Position rotation thresholds
    rotation_threshold_pct: float = field(
        default_factory=lambda: _env_float("TRADING_CAPITAL_ROTATION_THRESHOLD_PCT", 0.02)
    )
    max_position_age_hours: int = field(
        default_factory=lambda: _env_int("TRADING_CAPITAL_MAX_AGE_HOURS", 48)
    )
    
    # Reserve for new opportunities
    cash_reserve_pct: float = field(
        default_factory=lambda: _env_float("TRADING_CAPITAL_RESERVE_PCT", 0.05)
    )


@dataclass
class ScannerConfig:
    """Stock screening/scanning parameters."""
    
    # Universe configuration
    scan_sp500: bool = field(
        default_factory=lambda: _env_bool("TRADING_SCANNER_SP500", True)
    )
    scan_nasdaq100: bool = field(
        default_factory=lambda: _env_bool("TRADING_SCANNER_NASDAQ100", True)
    )
    
    # Additional watchlist tickers (comma-separated in env)
    additional_tickers: List[str] = field(
        default_factory=lambda: _env_list("TRADING_SCANNER_ADDITIONAL_TICKERS", [])
    )
    
    # Sector rotation (day of week -> tickers)
    # Can be overridden via TRADING_SCANNER_SECTOR_ROTATION_JSON
    sector_rotation: Dict[int, List[str]] = field(
        default_factory=lambda: _load_sector_rotation()
    )
    
    # Technical screening thresholds
    min_volume: int = field(
        default_factory=lambda: _env_int("TRADING_SCANNER_MIN_VOLUME", 1000000)
    )
    min_price: float = field(
        default_factory=lambda: _env_float("TRADING_SCANNER_MIN_PRICE", 5.0)
    )
    max_price: float = field(
        default_factory=lambda: _env_float("TRADING_SCANNER_MAX_PRICE", 10000.0)
    )


def _load_sector_rotation() -> Dict[int, List[str]]:
    """Load sector rotation from env or use defaults."""
    json_str = os.environ.get("TRADING_SCANNER_SECTOR_ROTATION_JSON")
    
    if json_str:
        try:
            data = json.loads(json_str)
            return {int(k): v for k, v in data.items()}
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Invalid sector rotation JSON: {e}")
    
    # Default sector rotation by day of week
    return {
        0: ["NVDA", "AMD", "AVGO", "QCOM", "INTC"],      # Monday: Semiconductors
        1: ["JPM", "GS", "MS", "BAC", "C"],              # Tuesday: Financials
        2: ["UNH", "JNJ", "PFE", "ABBV", "MRK"],         # Wednesday: Healthcare
        3: ["XOM", "CVX", "COP", "SLB", "EOG"],          # Thursday: Energy
        4: ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],    # Friday: Big Tech
    }


@dataclass
class ModelConfig:
    """AI Model configuration."""
    
    # Default model for most agents
    default_model: str = field(
        default_factory=lambda: os.environ.get("DEFAULT_MODEL", "claude-opus-4-5-20251101")
    )
    
    # Thinking model for critical decisions
    thinking_model: str = field(
        default_factory=lambda: os.environ.get("THINKING_MODEL", "claude-opus-4-5-20251101-thinking")
    )
    
    # Cheaper/faster model for less critical tasks
    fast_model: str = field(
        default_factory=lambda: os.environ.get("FAST_MODEL", "claude-sonnet-4-5-20250929")
    )
    
    # Model provider (for proxy routing)
    provider: str = field(
        default_factory=lambda: os.environ.get("MODEL_PROVIDER", "OPENAI")
    )


@dataclass
class FractionalConfig:
    """Fractional share trading configuration."""
    
    # Enable fractional share trading (default True for paper trading)
    allow_fractional: bool = field(
        default_factory=lambda: _env_bool("ALLOW_FRACTIONAL", True)
    )
    
    # Minimum quantity for fractional orders (Alpaca minimum is 0.0001)
    min_fractional_qty: float = field(
        default_factory=lambda: _env_float("MIN_FRACTIONAL_QTY", 0.0001)
    )
    
    # Decimal places for quantity rounding (4 is Alpaca's precision)
    fractional_precision: int = field(
        default_factory=lambda: _env_int("FRACTIONAL_PRECISION", 4)
    )
    
    # Whether to use notional (dollar-based) orders instead of share-based
    use_notional_orders: bool = field(
        default_factory=lambda: _env_bool("USE_NOTIONAL_ORDERS", False)
    )


@dataclass
class DataConfig:
    """Market data configuration."""
    
    # Primary data source
    primary_source: str = field(
        default_factory=lambda: os.environ.get("DATA_PRIMARY_SOURCE", "yfinance")
    )
    
    # Fallback sources (comma-separated)
    fallback_sources: List[str] = field(
        default_factory=lambda: _env_list(
            "DATA_FALLBACK_SOURCES",
            ["financial_datasets", "polygon", "fmp"]
        )
    )
    
    # Cache settings
    cache_ttl_minutes: int = field(
        default_factory=lambda: _env_int("DATA_CACHE_TTL_MINUTES", 15)
    )
    
    # Rate limiting
    max_requests_per_minute: int = field(
        default_factory=lambda: _env_int("DATA_MAX_REQUESTS_PER_MINUTE", 60)
    )


@dataclass
class TradingConfig:
    """Master configuration container."""

    risk: RiskConfig = field(default_factory=RiskConfig)
    signal: SignalConfig = field(default_factory=SignalConfig)
    capital: CapitalConfig = field(default_factory=CapitalConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    cooldown: CooldownConfig = field(default_factory=CooldownConfig)
    fractional: FractionalConfig = field(default_factory=FractionalConfig)
    intraday: IntradayConfig = field(default_factory=IntradayConfig)
    
    def to_dict(self) -> dict:
        """Export configuration as dictionary."""
        import dataclasses
        
        def asdict_recursive(obj):
            if dataclasses.is_dataclass(obj):
                return {k: asdict_recursive(v) for k, v in dataclasses.asdict(obj).items()}
            elif isinstance(obj, (list, tuple)):
                return [asdict_recursive(v) for v in obj]
            elif isinstance(obj, dict):
                return {k: asdict_recursive(v) for k, v in obj.items()}
            return obj
        
        return asdict_recursive(self)


# Global configuration instance
_config: Optional[TradingConfig] = None


def get_trading_config() -> TradingConfig:
    """Get or create the global trading configuration."""
    global _config
    if _config is None:
        _config = TradingConfig()
        logger.info("Trading configuration loaded")
    return _config


def reload_config() -> TradingConfig:
    """Force reload configuration from environment."""
    global _config
    _config = TradingConfig()
    logger.info("Trading configuration reloaded")
    return _config


# Convenience accessors
def get_risk_config() -> RiskConfig:
    return get_trading_config().risk


def get_signal_config() -> SignalConfig:
    return get_trading_config().signal


def get_capital_config() -> CapitalConfig:
    return get_trading_config().capital


def get_scanner_config() -> ScannerConfig:
    return get_trading_config().scanner


def get_model_config() -> ModelConfig:
    return get_trading_config().model


def get_data_config() -> DataConfig:
    return get_trading_config().data


def get_cooldown_config() -> CooldownConfig:
    return get_trading_config().cooldown


def get_fractional_config() -> FractionalConfig:
    return get_trading_config().fractional


def get_intraday_config() -> IntradayConfig:
    return get_trading_config().intraday
