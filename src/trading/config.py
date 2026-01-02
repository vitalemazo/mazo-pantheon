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
class SmallAccountConfig:
    """
    Dynamic Small Account Mode Configuration.
    
    When enabled and account equity is below threshold, the system
    adjusts the entire pipeline to favor many small intraday trades.
    """
    
    # Master toggle for small account mode
    enabled: bool = field(
        default_factory=lambda: _env_bool("SMALL_ACCOUNT_MODE", False)
    )
    
    # Equity threshold to activate small account mode (USD)
    # When equity <= this value, small account optimizations apply
    equity_threshold: float = field(
        default_factory=lambda: _env_float("SMALL_ACCOUNT_EQUITY_THRESHOLD", 10000.0)
    )
    
    # Target notional (dollar) amount per trade
    # e.g., $30 means each trade targets ~$30 exposure
    target_notional_per_trade: float = field(
        default_factory=lambda: _env_float("SMALL_ACCOUNT_TARGET_NOTIONAL", 30.0)
    )
    
    # Maximum signals to process per cycle (higher than normal)
    max_signals: int = field(
        default_factory=lambda: _env_int("SMALL_ACCOUNT_MAX_SIGNALS", 15)
    )
    
    # Minimum confidence threshold (lower to allow more trades)
    min_confidence: int = field(
        default_factory=lambda: _env_int("SMALL_ACCOUNT_MIN_CONFIDENCE", 55)
    )
    
    # Maximum concurrent positions (higher for diversification)
    max_positions: int = field(
        default_factory=lambda: _env_int("SMALL_ACCOUNT_MAX_POSITIONS", 30)
    )
    
    # Maximum position percentage per ticker (lower for diversification)
    max_position_pct: float = field(
        default_factory=lambda: _env_float("SMALL_ACCOUNT_MAX_POSITION_PCT", 0.05)
    )
    
    # Minimum buying power percentage before blocking trades
    min_buying_power_pct: float = field(
        default_factory=lambda: _env_float("SMALL_ACCOUNT_MIN_BUYING_POWER_PCT", 0.02)
    )
    
    # Trade cooldown in minutes (shorter for more activity)
    trade_cooldown_minutes: int = field(
        default_factory=lambda: _env_int("SMALL_ACCOUNT_COOLDOWN_MINUTES", 10)
    )
    
    # Maximum price for tickers in small account mode
    max_ticker_price: float = field(
        default_factory=lambda: _env_float("SMALL_ACCOUNT_MAX_TICKER_PRICE", 500.0)
    )
    
    # Minimum average daily volume
    min_avg_volume: int = field(
        default_factory=lambda: _env_int("SMALL_ACCOUNT_MIN_VOLUME", 500000)
    )
    
    # Include ETFs in universe (good for small accounts)
    include_etfs: bool = field(
        default_factory=lambda: _env_bool("SMALL_ACCOUNT_INCLUDE_ETFS", True)
    )
    
    # Enable intraday scalping strategies
    enable_scalping_strategies: bool = field(
        default_factory=lambda: _env_bool("SMALL_ACCOUNT_ENABLE_SCALPING", True)
    )
    
    # Enabled strategy names (comma-separated list or empty for all)
    enabled_strategies: List[str] = field(
        default_factory=lambda: _env_list(
            "SMALL_ACCOUNT_STRATEGIES",
            ["momentum", "mean_reversion", "trend_following", "vwap_scalper", "breakout_micro"]
        )
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
    small_account: SmallAccountConfig = field(default_factory=SmallAccountConfig)
    
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


def get_small_account_config() -> SmallAccountConfig:
    return get_trading_config().small_account


def is_small_account_mode_active(equity: float) -> bool:
    """
    Check if small account mode should be active based on config and equity.
    
    Args:
        equity: Current account equity in USD
        
    Returns:
        True if small account mode is enabled AND equity is below threshold
    """
    config = get_small_account_config()
    if not config.enabled:
        return False
    return equity <= config.equity_threshold


def get_effective_trading_params(equity: float) -> Dict[str, Any]:
    """
    Get effective trading parameters based on account size.
    
    Returns a dict with the active parameters, sourced from either
    SmallAccountConfig or the regular configs depending on mode.
    
    Args:
        equity: Current account equity
        
    Returns:
        Dict with effective parameters and mode indicator
    """
    small_active = is_small_account_mode_active(equity)
    
    if small_active:
        sac = get_small_account_config()
        return {
            "mode": "small_account",
            "active": True,
            "equity_threshold": sac.equity_threshold,
            "target_notional_per_trade": sac.target_notional_per_trade,
            "max_signals": sac.max_signals,
            "min_confidence": sac.min_confidence,
            "max_positions": sac.max_positions,
            "max_position_pct": sac.max_position_pct,
            "min_buying_power_pct": sac.min_buying_power_pct,
            "trade_cooldown_minutes": sac.trade_cooldown_minutes,
            "max_ticker_price": sac.max_ticker_price,
            "min_avg_volume": sac.min_avg_volume,
            "include_etfs": sac.include_etfs,
            "enabled_strategies": sac.enabled_strategies,
            "use_notional_sizing": True,
        }
    else:
        # Use standard config values
        signal = get_signal_config()
        risk = get_risk_config()
        capital = get_capital_config()
        cooldown = get_cooldown_config()
        
        return {
            "mode": "standard",
            "active": False,
            "max_signals": signal.max_signals_per_cycle,
            "min_confidence": signal.min_signal_confidence,
            "max_positions": risk.max_total_positions,
            "max_position_pct": risk.max_position_pct,
            "min_buying_power_pct": capital.min_buying_power_pct,
            "trade_cooldown_minutes": cooldown.trade_cooldown_minutes,
            "use_notional_sizing": False,
        }
