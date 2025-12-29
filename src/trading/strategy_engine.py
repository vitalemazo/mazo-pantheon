"""
Trading Strategy Engine

Implements various trading strategies:
- Momentum: Capture quick moves on high-volume stocks
- Mean Reversion: Fade extreme moves back to mean
- Trend Following: Ride multi-day trends
"""

import os
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import statistics

from datetime import date
from src.tools.api import get_prices, get_financial_metrics
from src.trading.alpaca_service import AlpacaService

logger = logging.getLogger(__name__)


class SignalDirection(Enum):
    """Trading signal direction"""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class SignalStrength(Enum):
    """Signal strength levels"""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


@dataclass
class TradingSignal:
    """A trading signal from a strategy"""
    ticker: str
    strategy: str
    direction: SignalDirection
    strength: SignalStrength
    confidence: float  # 0-100
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    position_size_pct: float  # Suggested % of portfolio
    reasoning: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "strategy": self.strategy,
            "direction": self.direction.value,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_size_pct": self.position_size_pct,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class BaseStrategy:
    """Base class for trading strategies"""
    
    name: str = "base"
    description: str = "Base strategy"
    
    # Default risk parameters
    default_stop_loss_pct: float = 0.05  # 5%
    default_take_profit_pct: float = 0.10  # 10%
    default_position_size_pct: float = 0.05  # 5% of portfolio
    
    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {}
        self.alpaca = AlpacaService()
    
    def analyze(self, ticker: str) -> Optional[TradingSignal]:
        """Analyze a ticker and return a signal. Override in subclass."""
        raise NotImplementedError
    
    def scan(self, tickers: List[str]) -> List[TradingSignal]:
        """Scan multiple tickers and return signals."""
        signals = []
        for ticker in tickers:
            try:
                signal = self.analyze(ticker)
                if signal and signal.direction != SignalDirection.NEUTRAL:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Error analyzing {ticker}: {e}")
        
        # Sort by confidence
        signals.sort(key=lambda x: x.confidence, reverse=True)
        return signals
    
    def _get_price_data(self, ticker: str, days: int = 20) -> List[float]:
        """Get recent closing prices."""
        end = date.today()
        start = end - timedelta(days=days + 10)  # Extra buffer for weekends/holidays
        prices = get_prices(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if not prices:
            return []
        # Return most recent 'days' prices
        return [p.close for p in prices[-days:]]
    
    def _calculate_sma(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Simple Moving Average."""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def _calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_bollinger_bands(
        self, 
        prices: List[float], 
        period: int = 20, 
        std_dev: float = 2.0
    ) -> Optional[Tuple[float, float, float]]:
        """Calculate Bollinger Bands (upper, middle, lower)."""
        if len(prices) < period:
            return None
        
        sma = self._calculate_sma(prices, period)
        if sma is None:
            return None
        
        std = statistics.stdev(prices[-period:])
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        return (upper, sma, lower)
    
    def _calculate_atr(self, ticker: str, period: int = 14) -> Optional[float]:
        """Calculate Average True Range for volatility."""
        end = date.today()
        start = end - timedelta(days=period + 15)  # Extra buffer
        prices = get_prices(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if not prices or len(prices) < period + 1:
            return None
        prices = prices[-(period + 1):]  # Take most recent
        
        true_ranges = []
        for i in range(1, len(prices)):
            high = prices[i].high
            low = prices[i].low
            prev_close = prices[i-1].close
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        return sum(true_ranges[-period:]) / period


class MomentumStrategy(BaseStrategy):
    """
    Momentum Strategy
    
    Entry: Strong price momentum with volume confirmation
    Exit: Momentum exhaustion or time-based
    
    Best for: Quick 1-3% moves on high-volume stocks
    """
    
    name = "momentum"
    description = "Capture quick moves on high-momentum stocks"
    
    # Momentum parameters
    lookback_period: int = 5  # Days to measure momentum
    volume_threshold: float = 1.5  # Volume must be 1.5x average
    momentum_threshold: float = 2.0  # Min % move to trigger
    
    def __init__(self, params: Optional[Dict] = None):
        super().__init__(params)
        
        # Override defaults from params
        self.lookback_period = params.get("lookback_period", 5) if params else 5
        self.volume_threshold = params.get("volume_threshold", 1.5) if params else 1.5
        self.momentum_threshold = params.get("momentum_threshold", 2.0) if params else 2.0
    
    def analyze(self, ticker: str) -> Optional[TradingSignal]:
        """Analyze ticker for momentum signals."""
        end = date.today()
        start = end - timedelta(days=self.lookback_period + 15)
        prices = get_prices(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        
        if not prices or len(prices) < self.lookback_period:
            return None
        prices = prices[-(self.lookback_period + 5):]  # Take most recent
        
        # Calculate momentum
        current_price = prices[-1].close
        start_price = prices[-self.lookback_period].close
        momentum_pct = ((current_price - start_price) / start_price) * 100
        
        # Calculate average volume
        avg_volume = sum(p.volume for p in prices[:-1]) / len(prices[:-1])
        current_volume = prices[-1].volume
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        # Calculate RSI for overbought/oversold
        rsi = self._calculate_rsi([p.close for p in prices])
        
        # Determine signal
        direction = SignalDirection.NEUTRAL
        strength = SignalStrength.WEAK
        confidence = 50
        reasoning_parts = []
        
        # Bullish momentum
        if momentum_pct > self.momentum_threshold:
            if volume_ratio > self.volume_threshold:
                direction = SignalDirection.LONG
                confidence = min(80, 50 + momentum_pct * 5 + (volume_ratio - 1) * 10)
                
                if momentum_pct > 5 and volume_ratio > 2:
                    strength = SignalStrength.STRONG
                elif momentum_pct > 3 or volume_ratio > 1.75:
                    strength = SignalStrength.MODERATE
                    
                reasoning_parts.append(f"+{momentum_pct:.1f}% in {self.lookback_period} days")
                reasoning_parts.append(f"Volume {volume_ratio:.1f}x average")
                
                # Check RSI for overbought warning
                if rsi and rsi > 70:
                    confidence -= 10
                    reasoning_parts.append(f"⚠️ RSI {rsi:.0f} (overbought)")
        
        # Bearish momentum
        elif momentum_pct < -self.momentum_threshold:
            if volume_ratio > self.volume_threshold:
                direction = SignalDirection.SHORT
                confidence = min(80, 50 + abs(momentum_pct) * 5 + (volume_ratio - 1) * 10)
                
                if abs(momentum_pct) > 5 and volume_ratio > 2:
                    strength = SignalStrength.STRONG
                elif abs(momentum_pct) > 3 or volume_ratio > 1.75:
                    strength = SignalStrength.MODERATE
                    
                reasoning_parts.append(f"{momentum_pct:.1f}% in {self.lookback_period} days")
                reasoning_parts.append(f"Volume {volume_ratio:.1f}x average")
                
                # Check RSI for oversold warning
                if rsi and rsi < 30:
                    confidence -= 10
                    reasoning_parts.append(f"⚠️ RSI {rsi:.0f} (oversold)")
        
        if direction == SignalDirection.NEUTRAL:
            return None
        
        # Calculate stops
        atr = self._calculate_atr(ticker)
        if atr:
            stop_distance = atr * 1.5
        else:
            stop_distance = current_price * 0.03  # 3% default
        
        if direction == SignalDirection.LONG:
            stop_loss = current_price - stop_distance
            take_profit = current_price + (stop_distance * 2)  # 2:1 risk-reward
        else:
            stop_loss = current_price + stop_distance
            take_profit = current_price - (stop_distance * 2)
        
        return TradingSignal(
            ticker=ticker,
            strategy=self.name,
            direction=direction,
            strength=strength,
            confidence=confidence,
            entry_price=current_price,
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            position_size_pct=0.05,  # 5% per momentum trade
            reasoning=" | ".join(reasoning_parts)
        )


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy
    
    Entry: Price at extreme deviation from mean (Bollinger Bands)
    Exit: Return to mean or opposite band
    
    Best for: Range-bound stocks with clear mean
    """
    
    name = "mean_reversion"
    description = "Fade extreme moves back to mean"
    
    # Parameters
    bb_period: int = 20  # Bollinger Band period
    bb_std: float = 2.0  # Standard deviations
    rsi_oversold: float = 30
    rsi_overbought: float = 70
    
    def __init__(self, params: Optional[Dict] = None):
        super().__init__(params)
        
        self.bb_period = params.get("bb_period", 20) if params else 20
        self.bb_std = params.get("bb_std", 2.0) if params else 2.0
    
    def analyze(self, ticker: str) -> Optional[TradingSignal]:
        """Analyze ticker for mean reversion signals."""
        end = date.today()
        start = end - timedelta(days=self.bb_period + 15)
        prices_data = get_prices(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        
        if not prices_data or len(prices_data) < self.bb_period:
            return None
        prices_data = prices_data[-(self.bb_period + 5):]  # Take most recent
        
        prices = [p.close for p in prices_data]
        current_price = prices[-1]
        
        # Calculate Bollinger Bands
        bb = self._calculate_bollinger_bands(prices, self.bb_period, self.bb_std)
        if not bb:
            return None
        
        upper, middle, lower = bb
        
        # Calculate RSI
        rsi = self._calculate_rsi(prices)
        
        # Calculate how far price is from middle
        band_width = upper - lower
        price_position = (current_price - lower) / band_width if band_width > 0 else 0.5
        
        direction = SignalDirection.NEUTRAL
        strength = SignalStrength.WEAK
        confidence = 50
        reasoning_parts = []
        
        # Oversold - potential long
        if current_price < lower:
            direction = SignalDirection.LONG
            distance_pct = ((lower - current_price) / lower) * 100
            confidence = min(85, 60 + distance_pct * 5)
            
            if rsi and rsi < 25:
                strength = SignalStrength.STRONG
                confidence = min(90, confidence + 10)
                reasoning_parts.append(f"Extreme oversold: RSI {rsi:.0f}")
            elif rsi and rsi < self.rsi_oversold:
                strength = SignalStrength.MODERATE
                reasoning_parts.append(f"Oversold: RSI {rsi:.0f}")
            
            reasoning_parts.append(f"Price {distance_pct:.1f}% below lower BB")
            reasoning_parts.append(f"Target: {middle:.2f} (middle band)")
        
        # Overbought - potential short
        elif current_price > upper:
            direction = SignalDirection.SHORT
            distance_pct = ((current_price - upper) / upper) * 100
            confidence = min(85, 60 + distance_pct * 5)
            
            if rsi and rsi > 75:
                strength = SignalStrength.STRONG
                confidence = min(90, confidence + 10)
                reasoning_parts.append(f"Extreme overbought: RSI {rsi:.0f}")
            elif rsi and rsi > self.rsi_overbought:
                strength = SignalStrength.MODERATE
                reasoning_parts.append(f"Overbought: RSI {rsi:.0f}")
            
            reasoning_parts.append(f"Price {distance_pct:.1f}% above upper BB")
            reasoning_parts.append(f"Target: {middle:.2f} (middle band)")
        
        if direction == SignalDirection.NEUTRAL:
            return None
        
        # Stop loss outside the bands, take profit at middle
        if direction == SignalDirection.LONG:
            stop_loss = lower - (band_width * 0.25)  # 25% beyond lower band
            take_profit = middle
        else:
            stop_loss = upper + (band_width * 0.25)  # 25% beyond upper band
            take_profit = middle
        
        return TradingSignal(
            ticker=ticker,
            strategy=self.name,
            direction=direction,
            strength=strength,
            confidence=confidence,
            entry_price=current_price,
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            position_size_pct=0.05,  # 5% per mean reversion trade
            reasoning=" | ".join(reasoning_parts)
        )


class TrendFollowingStrategy(BaseStrategy):
    """
    Trend Following Strategy
    
    Entry: Breakout from consolidation with volume
    Exit: Trailing stop or trend reversal
    
    Best for: Stocks in clear uptrend or downtrend
    """
    
    name = "trend_following"
    description = "Ride multi-day trends"
    
    # Parameters
    short_ma_period: int = 10
    long_ma_period: int = 50
    breakout_period: int = 20  # Look for breakouts over this period
    
    def __init__(self, params: Optional[Dict] = None):
        super().__init__(params)
        
        self.short_ma_period = params.get("short_ma_period", 10) if params else 10
        self.long_ma_period = params.get("long_ma_period", 50) if params else 50
    
    def analyze(self, ticker: str) -> Optional[TradingSignal]:
        """Analyze ticker for trend following signals."""
        end = date.today()
        start = end - timedelta(days=self.long_ma_period + 30)
        prices_data = get_prices(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        
        if not prices_data or len(prices_data) < self.long_ma_period:
            return None
        prices_data = prices_data[-(self.long_ma_period + 10):]  # Take most recent
        
        prices = [p.close for p in prices_data]
        current_price = prices[-1]
        
        # Calculate MAs
        short_ma = self._calculate_ema(prices, self.short_ma_period)
        long_ma = self._calculate_sma(prices, self.long_ma_period)
        
        if not short_ma or not long_ma:
            return None
        
        # Calculate RSI
        rsi = self._calculate_rsi(prices)
        
        # Calculate trend strength
        ma_diff_pct = ((short_ma - long_ma) / long_ma) * 100
        
        # Check for recent crossover
        prev_prices = prices[:-1]
        prev_short_ma = self._calculate_ema(prev_prices, self.short_ma_period)
        prev_long_ma = self._calculate_sma(prev_prices, self.long_ma_period)
        
        golden_cross = (prev_short_ma < prev_long_ma) and (short_ma > long_ma) if prev_short_ma and prev_long_ma else False
        death_cross = (prev_short_ma > prev_long_ma) and (short_ma < long_ma) if prev_short_ma and prev_long_ma else False
        
        # Find 20-day high/low for breakout detection
        high_20 = max(p.high for p in prices_data[-self.breakout_period:])
        low_20 = min(p.low for p in prices_data[-self.breakout_period:])
        
        direction = SignalDirection.NEUTRAL
        strength = SignalStrength.WEAK
        confidence = 50
        reasoning_parts = []
        
        # Bullish trend
        if short_ma > long_ma:
            direction = SignalDirection.LONG
            
            if golden_cross:
                strength = SignalStrength.STRONG
                confidence = 75
                reasoning_parts.append("Golden cross (bullish crossover)")
            elif ma_diff_pct > 5:
                strength = SignalStrength.STRONG
                confidence = 70
                reasoning_parts.append(f"Strong uptrend: {ma_diff_pct:.1f}% above 50-day MA")
            elif ma_diff_pct > 2:
                strength = SignalStrength.MODERATE
                confidence = 60
                reasoning_parts.append(f"Moderate uptrend: {ma_diff_pct:.1f}% above 50-day MA")
            else:
                confidence = 55
                reasoning_parts.append(f"Weak uptrend: {ma_diff_pct:.1f}% above 50-day MA")
            
            # Check for breakout
            if current_price >= high_20 * 0.99:  # Within 1% of 20-day high
                confidence += 10
                reasoning_parts.append(f"Near 20-day high: ${high_20:.2f}")
        
        # Bearish trend
        elif short_ma < long_ma:
            direction = SignalDirection.SHORT
            
            if death_cross:
                strength = SignalStrength.STRONG
                confidence = 75
                reasoning_parts.append("Death cross (bearish crossover)")
            elif abs(ma_diff_pct) > 5:
                strength = SignalStrength.STRONG
                confidence = 70
                reasoning_parts.append(f"Strong downtrend: {abs(ma_diff_pct):.1f}% below 50-day MA")
            elif abs(ma_diff_pct) > 2:
                strength = SignalStrength.MODERATE
                confidence = 60
                reasoning_parts.append(f"Moderate downtrend: {abs(ma_diff_pct):.1f}% below 50-day MA")
            else:
                confidence = 55
                reasoning_parts.append(f"Weak downtrend: {abs(ma_diff_pct):.1f}% below 50-day MA")
            
            # Check for breakdown
            if current_price <= low_20 * 1.01:  # Within 1% of 20-day low
                confidence += 10
                reasoning_parts.append(f"Near 20-day low: ${low_20:.2f}")
        
        if direction == SignalDirection.NEUTRAL:
            return None
        
        # Use ATR for stops
        atr = self._calculate_atr(ticker)
        if atr:
            stop_distance = atr * 2.5  # Wider stop for trend trades
        else:
            stop_distance = current_price * 0.05  # 5% default
        
        if direction == SignalDirection.LONG:
            stop_loss = current_price - stop_distance
            take_profit = current_price + (stop_distance * 2)
        else:
            stop_loss = current_price + stop_distance
            take_profit = current_price - (stop_distance * 2)
        
        return TradingSignal(
            ticker=ticker,
            strategy=self.name,
            direction=direction,
            strength=strength,
            confidence=min(85, confidence),
            entry_price=current_price,
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            position_size_pct=0.08,  # 8% per trend trade (longer hold)
            reasoning=" | ".join(reasoning_parts)
        )


class StrategyEngine:
    """
    Strategy Engine
    
    Manages and runs multiple trading strategies.
    """
    
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """Register default strategies."""
        self.strategies = {
            "momentum": MomentumStrategy(),
            "mean_reversion": MeanReversionStrategy(),
            "trend_following": TrendFollowingStrategy(),
        }
    
    def add_strategy(self, strategy: BaseStrategy):
        """Add a custom strategy."""
        self.strategies[strategy.name] = strategy
    
    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """Get a strategy by name."""
        return self.strategies.get(name)
    
    def analyze_ticker(
        self, 
        ticker: str, 
        strategies: Optional[List[str]] = None
    ) -> List[TradingSignal]:
        """
        Analyze a ticker with specified strategies.
        
        Args:
            ticker: Stock ticker to analyze
            strategies: List of strategy names (None = all)
            
        Returns:
            List of trading signals from all strategies
        """
        signals = []
        
        strats_to_run = strategies or list(self.strategies.keys())
        
        for strat_name in strats_to_run:
            strategy = self.strategies.get(strat_name)
            if not strategy:
                continue
                
            try:
                signal = strategy.analyze(ticker)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Strategy {strat_name} failed for {ticker}: {e}")
        
        return signals
    
    def scan_universe(
        self,
        tickers: List[str],
        strategies: Optional[List[str]] = None,
        min_confidence: float = 60
    ) -> Dict[str, List[TradingSignal]]:
        """
        Scan a list of tickers with strategies.
        
        Args:
            tickers: List of tickers to scan
            strategies: List of strategy names (None = all)
            min_confidence: Minimum confidence to include
            
        Returns:
            Dict of ticker -> signals
        """
        results = {}
        
        for ticker in tickers:
            signals = self.analyze_ticker(ticker, strategies)
            
            # Filter by confidence
            signals = [s for s in signals if s.confidence >= min_confidence]
            
            if signals:
                results[ticker] = signals
        
        return results
    
    def get_best_signals(
        self,
        tickers: List[str],
        top_n: int = 5
    ) -> List[TradingSignal]:
        """
        Get the best trading signals across all tickers and strategies.
        
        Args:
            tickers: Tickers to scan
            top_n: Number of top signals to return
            
        Returns:
            Top N signals sorted by confidence
        """
        all_signals = []
        
        scan_results = self.scan_universe(tickers)
        
        for ticker_signals in scan_results.values():
            all_signals.extend(ticker_signals)
        
        # Sort by confidence and take top N
        all_signals.sort(key=lambda x: x.confidence, reverse=True)
        
        return all_signals[:top_n]
    
    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """Get list of available strategies with info."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "default_stop_loss_pct": s.default_stop_loss_pct,
                "default_take_profit_pct": s.default_take_profit_pct,
            }
            for s in self.strategies.values()
        ]


# Global engine instance
_engine: Optional[StrategyEngine] = None


def get_strategy_engine() -> StrategyEngine:
    """Get the global strategy engine instance."""
    global _engine
    if _engine is None:
        _engine = StrategyEngine()
    return _engine
