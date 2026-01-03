import logging
import math
import os

from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

# Cache for chart vision setting
_chart_vision_enabled_cache = None
_chart_vision_cache_time = 0


def _is_chart_vision_enabled() -> bool:
    """
    Check if chart vision analysis is enabled.
    Checks environment variable first, then database setting.
    Caches result for 60 seconds to avoid repeated DB queries.
    """
    global _chart_vision_enabled_cache, _chart_vision_cache_time
    import time
    
    # Check cache (valid for 60 seconds)
    if _chart_vision_enabled_cache is not None and (time.time() - _chart_vision_cache_time) < 60:
        return _chart_vision_enabled_cache
    
    # Check environment variable first
    env_value = os.environ.get("ENABLE_CHART_VISION_ANALYSIS", "").lower()
    if env_value in ("true", "1", "yes"):
        _chart_vision_enabled_cache = True
        _chart_vision_cache_time = time.time()
        return True
    if env_value in ("false", "0", "no"):
        _chart_vision_enabled_cache = False
        _chart_vision_cache_time = time.time()
        return False
    
    # Check database setting
    try:
        from sqlalchemy import create_engine, text
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://mazo:mazo@mazo-postgres:5432/mazo_pantheon"
        )
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT key_value FROM api_keys WHERE provider = 'ENABLE_CHART_VISION_ANALYSIS' AND is_active = true")
            )
            row = result.fetchone()
            if row and row[0]:
                enabled = row[0].lower() in ("true", "1", "yes")
                _chart_vision_enabled_cache = enabled
                _chart_vision_cache_time = time.time()
                return enabled
    except Exception as e:
        logger.debug(f"Could not check chart vision setting from DB: {e}")
    
    # Default to disabled
    _chart_vision_enabled_cache = False
    _chart_vision_cache_time = time.time()
    return False

from src.graph.state import AgentState, show_agent_reasoning
from src.utils.api_key import get_api_key_from_state
import json
import pandas as pd
import numpy as np

from src.tools.api import get_prices, prices_to_df
from src.utils.progress import progress


def _check_danelfin_agreement(our_signal: str, ai_score: int, tech_score: int) -> dict:
    """
    Check if Danelfin agrees with our technical signal.
    
    Returns agreement status and any confidence adjustment.
    """
    our_bullish = our_signal.lower() in ("bullish", "buy", "long")
    our_bearish = our_signal.lower() in ("bearish", "sell", "short")
    
    # Danelfin considers 7+ as bullish, 4- as bearish
    danelfin_bullish = ai_score >= 7 or tech_score >= 7
    danelfin_bearish = ai_score <= 4 or tech_score <= 4
    
    if our_bullish and danelfin_bullish:
        return {"agrees": True, "strength": "strong", "note": f"Danelfin confirms bullish (AI={ai_score}, Tech={tech_score})"}
    elif our_bearish and danelfin_bearish:
        return {"agrees": True, "strength": "strong", "note": f"Danelfin confirms bearish (AI={ai_score}, Tech={tech_score})"}
    elif our_bullish and danelfin_bearish:
        return {"agrees": False, "strength": "weak", "note": f"Danelfin disagrees - bearish (AI={ai_score}, Tech={tech_score})"}
    elif our_bearish and danelfin_bullish:
        return {"agrees": False, "strength": "weak", "note": f"Danelfin disagrees - bullish (AI={ai_score}, Tech={tech_score})"}
    else:
        return {"agrees": True, "strength": "neutral", "note": f"Danelfin neutral (AI={ai_score}, Tech={tech_score})"}


def safe_float(value, default=0.0):
    """
    Safely convert a value to float, handling NaN cases
    
    Args:
        value: The value to convert (can be pandas scalar, numpy value, etc.)
        default: Default value to return if the input is NaN or invalid
    
    Returns:
        float: The converted value or default if NaN/invalid
    """
    try:
        if pd.isna(value) or np.isnan(value):
            return default
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return default


##### Technical Analyst #####
def technical_analyst_agent(state: AgentState, agent_id: str = "technical_analyst_agent"):
    """
    Sophisticated technical analysis system that combines multiple trading strategies for multiple tickers:
    1. Trend Following
    2. Mean Reversion
    3. Momentum
    4. Volatility Analysis
    5. Statistical Arbitrage Signals
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    # Initialize analysis for each ticker
    technical_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Analyzing price data")

        # Get the historical price data
        prices = get_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            api_key=api_key,
        )

        if not prices:
            progress.update_status(agent_id, ticker, "Failed: No price data found")
            continue

        # Convert prices to a DataFrame
        prices_df = prices_to_df(prices)

        progress.update_status(agent_id, ticker, "Calculating trend signals")
        trend_signals = calculate_trend_signals(prices_df)

        progress.update_status(agent_id, ticker, "Calculating mean reversion")
        mean_reversion_signals = calculate_mean_reversion_signals(prices_df)

        progress.update_status(agent_id, ticker, "Calculating momentum")
        momentum_signals = calculate_momentum_signals(prices_df)

        progress.update_status(agent_id, ticker, "Analyzing volatility")
        volatility_signals = calculate_volatility_signals(prices_df)

        progress.update_status(agent_id, ticker, "Statistical analysis")
        stat_arb_signals = calculate_stat_arb_signals(prices_df)

        # NEW: Calculate MACD
        progress.update_status(agent_id, ticker, "Calculating MACD")
        macd_signals = calculate_macd(prices_df)

        # NEW: Calculate Fibonacci levels
        progress.update_status(agent_id, ticker, "Calculating Fibonacci levels")
        fibonacci_signals = calculate_fibonacci_levels(prices_df)

        # NEW: Calculate Support/Resistance
        progress.update_status(agent_id, ticker, "Calculating Support/Resistance")
        sr_signals = calculate_support_resistance(prices_df)

        # Combine all signals using a weighted ensemble approach
        # Updated weights to include new indicators
        strategy_weights = {
            "trend": 0.18,
            "mean_reversion": 0.15,
            "momentum": 0.18,
            "volatility": 0.10,
            "stat_arb": 0.09,
            "macd": 0.12,
            "fibonacci": 0.10,
            "support_resistance": 0.08,
        }

        progress.update_status(agent_id, ticker, "Combining signals")
        combined_signal = weighted_signal_combination(
            {
                "trend": trend_signals,
                "mean_reversion": mean_reversion_signals,
                "momentum": momentum_signals,
                "volatility": volatility_signals,
                "stat_arb": stat_arb_signals,
                "macd": macd_signals,
                "fibonacci": fibonacci_signals,
                "support_resistance": sr_signals,
            },
            strategy_weights,
        )

        # Optional: AI Chart Pattern Analysis (uses Chart-img + Vision LLM)
        chart_analysis_result = None
        use_chart_analysis = _is_chart_vision_enabled()
        
        if use_chart_analysis:
            try:
                from src.tools.chart_analysis import analyze_ticker_chart
                progress.update_status(agent_id, ticker, "AI Chart Pattern Analysis")
                chart_analysis_result = analyze_ticker_chart(
                    ticker=ticker,
                    interval="1D",
                    exchange="NASDAQ",  # TODO: detect exchange from ticker
                    include_vision_analysis=True,
                )
                if chart_analysis_result.error:
                    logger.warning(f"Chart analysis failed for {ticker}: {chart_analysis_result.error}")
                    chart_analysis_result = None
            except Exception as e:
                logger.warning(f"Chart analysis unavailable for {ticker}: {e}")
                chart_analysis_result = None

        # Generate detailed analysis report for this ticker
        technical_analysis[ticker] = {
            "signal": combined_signal["signal"],
            "confidence": round(combined_signal["confidence"] * 100),
            "reasoning": {
                "trend_following": {
                    "signal": trend_signals["signal"],
                    "confidence": round(trend_signals["confidence"] * 100),
                    "metrics": normalize_pandas(trend_signals["metrics"]),
                },
                "mean_reversion": {
                    "signal": mean_reversion_signals["signal"],
                    "confidence": round(mean_reversion_signals["confidence"] * 100),
                    "metrics": normalize_pandas(mean_reversion_signals["metrics"]),
                },
                "momentum": {
                    "signal": momentum_signals["signal"],
                    "confidence": round(momentum_signals["confidence"] * 100),
                    "metrics": normalize_pandas(momentum_signals["metrics"]),
                },
                "volatility": {
                    "signal": volatility_signals["signal"],
                    "confidence": round(volatility_signals["confidence"] * 100),
                    "metrics": normalize_pandas(volatility_signals["metrics"]),
                },
                "statistical_arbitrage": {
                    "signal": stat_arb_signals["signal"],
                    "confidence": round(stat_arb_signals["confidence"] * 100),
                    "metrics": normalize_pandas(stat_arb_signals["metrics"]),
                },
                "macd": {
                    "signal": macd_signals["signal"],
                    "confidence": round(macd_signals["confidence"] * 100),
                    "metrics": normalize_pandas(macd_signals["metrics"]),
                },
                "fibonacci": {
                    "signal": fibonacci_signals["signal"],
                    "confidence": round(fibonacci_signals["confidence"] * 100),
                    "metrics": normalize_pandas(fibonacci_signals["metrics"]),
                },
                "support_resistance": {
                    "signal": sr_signals["signal"],
                    "confidence": round(sr_signals["confidence"] * 100),
                    "metrics": normalize_pandas(sr_signals["metrics"]),
                },
            },
        }
        
        # Add chart analysis if available
        if chart_analysis_result and not chart_analysis_result.error:
            technical_analysis[ticker]["chart_analysis"] = {
                "chart_url": chart_analysis_result.chart_url,
                "patterns_detected": chart_analysis_result.patterns_detected,
                "trend_direction": chart_analysis_result.trend_direction,
                "key_levels": chart_analysis_result.key_levels,
                "ai_signal": chart_analysis_result.signal,
                "ai_confidence": round(chart_analysis_result.confidence * 100),
                "summary": chart_analysis_result.analysis_summary,
            }
        
        # Add Danelfin external AI validation if available
        try:
            from src.tools.danelfin_api import get_score, is_danelfin_enabled
            from src.trading.config import get_danelfin_config
            
            danelfin_config = get_danelfin_config()
            if is_danelfin_enabled() and danelfin_config.include_in_agent_prompts:
                danelfin_score = get_score(ticker)
                if danelfin_score.success:
                    technical_analysis[ticker]["danelfin_validation"] = {
                        "ai_score": danelfin_score.ai_score,
                        "technical": danelfin_score.technical,
                        "fundamental": danelfin_score.fundamental,
                        "sentiment": danelfin_score.sentiment,
                        "low_risk": danelfin_score.low_risk,
                        "signal": danelfin_score.signal,
                        "agreement": _check_danelfin_agreement(
                            technical_analysis[ticker]["signal"],
                            danelfin_score.ai_score,
                            danelfin_score.technical
                        ),
                    }
                    logger.debug(f"[Danelfin] {ticker}: AI={danelfin_score.ai_score}, Tech={danelfin_score.technical}")
        except Exception as e:
            logger.debug(f"Danelfin not available for technicals: {e}")
        
        progress.update_status(agent_id, ticker, "Done", analysis=json.dumps(technical_analysis, indent=4))

    # Create the technical analyst message
    message = HumanMessage(
        content=json.dumps(technical_analysis),
        name=agent_id,
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(technical_analysis, "Technical Analyst")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = technical_analysis

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": data,
    }


def calculate_trend_signals(prices_df):
    """
    Advanced trend following strategy using multiple timeframes and indicators
    """
    # Calculate EMAs for multiple timeframes
    ema_8 = calculate_ema(prices_df, 8)
    ema_21 = calculate_ema(prices_df, 21)
    ema_55 = calculate_ema(prices_df, 55)

    # Calculate ADX for trend strength
    adx = calculate_adx(prices_df, 14)

    # Determine trend direction and strength
    short_trend = ema_8 > ema_21
    medium_trend = ema_21 > ema_55

    # Combine signals with confidence weighting
    trend_strength = adx["adx"].iloc[-1] / 100.0

    if short_trend.iloc[-1] and medium_trend.iloc[-1]:
        signal = "bullish"
        confidence = trend_strength
    elif not short_trend.iloc[-1] and not medium_trend.iloc[-1]:
        signal = "bearish"
        confidence = trend_strength
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "adx": safe_float(adx["adx"].iloc[-1]),
            "trend_strength": safe_float(trend_strength),
        },
    }


def calculate_mean_reversion_signals(prices_df):
    """
    Mean reversion strategy using statistical measures and Bollinger Bands
    """
    # Calculate z-score of price relative to moving average
    ma_50 = prices_df["close"].rolling(window=50).mean()
    std_50 = prices_df["close"].rolling(window=50).std()
    z_score = (prices_df["close"] - ma_50) / std_50

    # Calculate Bollinger Bands
    bb_upper, bb_lower = calculate_bollinger_bands(prices_df)

    # Calculate RSI with multiple timeframes
    rsi_14 = calculate_rsi(prices_df, 14)
    rsi_28 = calculate_rsi(prices_df, 28)

    # Mean reversion signals
    price_vs_bb = (prices_df["close"].iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])

    # Combine signals
    if z_score.iloc[-1] < -2 and price_vs_bb < 0.2:
        signal = "bullish"
        confidence = min(abs(z_score.iloc[-1]) / 4, 1.0)
    elif z_score.iloc[-1] > 2 and price_vs_bb > 0.8:
        signal = "bearish"
        confidence = min(abs(z_score.iloc[-1]) / 4, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "z_score": safe_float(z_score.iloc[-1]),
            "price_vs_bb": safe_float(price_vs_bb),
            "rsi_14": safe_float(rsi_14.iloc[-1]),
            "rsi_28": safe_float(rsi_28.iloc[-1]),
        },
    }


def calculate_momentum_signals(prices_df):
    """
    Multi-factor momentum strategy
    """
    # Price momentum - use cumulative returns over periods
    returns = prices_df["close"].pct_change()
    
    # Use shorter lookback if not enough data
    data_len = len(prices_df)
    
    # Calculate momentum with fallback for shorter data
    mom_1m = returns.rolling(min(21, data_len - 1)).sum() if data_len > 5 else returns.rolling(5).sum()
    mom_3m = returns.rolling(min(63, data_len - 1)).sum() if data_len > 21 else mom_1m
    mom_6m = returns.rolling(min(126, data_len - 1)).sum() if data_len > 63 else mom_3m

    # Volume momentum
    volume_ma = prices_df["volume"].rolling(min(21, data_len - 1)).mean()
    volume_momentum = prices_df["volume"] / volume_ma

    # Get last valid values (handling NaN)
    mom_1m_val = safe_float(mom_1m.dropna().iloc[-1] if len(mom_1m.dropna()) > 0 else 0)
    mom_3m_val = safe_float(mom_3m.dropna().iloc[-1] if len(mom_3m.dropna()) > 0 else 0)
    mom_6m_val = safe_float(mom_6m.dropna().iloc[-1] if len(mom_6m.dropna()) > 0 else 0)
    vol_mom_val = safe_float(volume_momentum.dropna().iloc[-1] if len(volume_momentum.dropna()) > 0 else 1.0)

    # Calculate momentum score with weights favoring recent momentum
    momentum_score = 0.4 * mom_1m_val + 0.35 * mom_3m_val + 0.25 * mom_6m_val

    # Volume confirmation
    volume_confirmation = vol_mom_val > 1.0

    # Adjusted thresholds - 0.05 (5% return) might be too high for some stocks
    if momentum_score > 0.03:  # 3% cumulative return threshold
        signal = "bullish"
        confidence = min(abs(momentum_score) * 8, 1.0)  # Scale up confidence
        if volume_confirmation:
            confidence = min(confidence * 1.2, 1.0)  # Boost if volume confirms
    elif momentum_score < -0.03:
        signal = "bearish"
        confidence = min(abs(momentum_score) * 8, 1.0)
        if volume_confirmation:
            confidence = min(confidence * 1.2, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "momentum_1m": mom_1m_val,
            "momentum_3m": mom_3m_val,
            "momentum_6m": mom_6m_val,
            "volume_momentum": vol_mom_val,
        },
    }


def calculate_volatility_signals(prices_df):
    """
    Volatility-based trading strategy
    """
    data_len = len(prices_df)
    
    # Calculate various volatility metrics
    returns = prices_df["close"].pct_change()

    # Historical volatility - use shorter windows if not enough data
    hist_vol_window = min(21, data_len - 1)
    hist_vol = returns.rolling(hist_vol_window).std() * math.sqrt(252)

    # Volatility regime detection
    vol_ma_window = min(63, data_len - 1)
    vol_ma = hist_vol.rolling(vol_ma_window).mean()
    vol_regime = hist_vol / vol_ma.replace(0, np.nan)  # Avoid division by zero

    # Volatility mean reversion
    vol_std = hist_vol.rolling(vol_ma_window).std()
    vol_z_score = (hist_vol - vol_ma) / vol_std.replace(0, np.nan)

    # ATR ratio
    atr = calculate_atr(prices_df)
    atr_ratio = atr / prices_df["close"].replace(0, np.nan)

    # Get last valid values
    hist_vol_val = safe_float(hist_vol.dropna().iloc[-1] if len(hist_vol.dropna()) > 0 else 0.2)
    current_vol_regime = safe_float(vol_regime.dropna().iloc[-1] if len(vol_regime.dropna()) > 0 else 1.0)
    vol_z = safe_float(vol_z_score.dropna().iloc[-1] if len(vol_z_score.dropna()) > 0 else 0)
    atr_ratio_val = safe_float(atr_ratio.dropna().iloc[-1] if len(atr_ratio.dropna()) > 0 else 0.02)

    # Generate signal based on volatility regime
    if current_vol_regime < 0.8 and vol_z < -1:
        signal = "bullish"  # Low vol regime, potential for expansion
        confidence = min(abs(vol_z) / 3, 1.0)
    elif current_vol_regime > 1.2 and vol_z > 1:
        signal = "bearish"  # High vol regime, potential for contraction
        confidence = min(abs(vol_z) / 3, 1.0)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "historical_volatility": hist_vol_val,
            "volatility_regime": current_vol_regime,
            "volatility_z_score": vol_z,
            "atr_ratio": atr_ratio_val,
        },
    }


def calculate_stat_arb_signals(prices_df):
    """
    Statistical arbitrage signals based on price action analysis
    """
    data_len = len(prices_df)
    
    # Calculate price distribution statistics
    returns = prices_df["close"].pct_change()

    # Skewness and kurtosis - use shorter window if needed
    stat_window = min(63, data_len - 1)
    skew = returns.rolling(stat_window).skew()
    kurt = returns.rolling(stat_window).kurt()

    # Test for mean reversion using Hurst exponent
    hurst = calculate_hurst_exponent(prices_df["close"])
    hurst = safe_float(hurst, 0.5)  # Default to random walk if calculation fails

    # Get last valid values
    skew_val = safe_float(skew.dropna().iloc[-1] if len(skew.dropna()) > 0 else 0)
    kurt_val = safe_float(kurt.dropna().iloc[-1] if len(kurt.dropna()) > 0 else 0)

    # Generate signal based on statistical properties
    # Hurst < 0.5 = mean-reverting, Hurst > 0.5 = trending
    if hurst < 0.4 and skew_val > 0.5:  # Mean-reverting with positive skew
        signal = "bullish"
        confidence = max((0.5 - hurst) * 2, 0.3)
    elif hurst < 0.4 and skew_val < -0.5:  # Mean-reverting with negative skew
        signal = "bearish"
        confidence = max((0.5 - hurst) * 2, 0.3)
    elif hurst > 0.6:  # Trending market - follow the trend
        # Determine trend direction from recent returns
        recent_return = safe_float(returns.rolling(5).mean().iloc[-1], 0)
        if recent_return > 0:
            signal = "bullish"
        elif recent_return < 0:
            signal = "bearish"
        else:
            signal = "neutral"
        confidence = max((hurst - 0.5) * 2, 0.3)
    else:
        signal = "neutral"
        confidence = 0.5

    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "hurst_exponent": hurst,
            "skewness": skew_val,
            "kurtosis": kurt_val,
        },
    }


def weighted_signal_combination(signals, weights):
    """
    Combines multiple trading signals using a weighted approach.
    
    Returns a signal with confidence that reflects:
    - For bullish/bearish: how strong the directional bias is
    - For neutral: how confidently the indicators agree on no clear direction
    """
    # Convert signals to numeric values
    signal_values = {"bullish": 1, "neutral": 0, "bearish": -1}

    weighted_sum = 0
    total_weight = 0
    avg_confidence = 0
    num_signals = 0
    
    # Track signal distribution for neutral confidence calculation
    signal_counts = {"bullish": 0, "bearish": 0, "neutral": 0}

    for strategy, signal in signals.items():
        numeric_signal = signal_values[signal["signal"]]
        weight = weights[strategy]
        confidence = signal["confidence"]
        
        signal_counts[signal["signal"]] += 1
        num_signals += 1

        weighted_sum += numeric_signal * weight * confidence
        total_weight += weight
        avg_confidence += confidence

    # Calculate average confidence across all strategies
    if num_signals > 0:
        avg_confidence = avg_confidence / num_signals
    else:
        avg_confidence = 0.5

    # Normalize the weighted sum
    if total_weight > 0:
        final_score = weighted_sum / total_weight
    else:
        final_score = 0

    # Convert back to signal
    if final_score > 0.15:  # Slightly lower threshold to be more decisive
        signal = "bullish"
        # Confidence is proportional to how bullish the score is
        confidence = min(abs(final_score) * 1.5, 1.0) * avg_confidence
    elif final_score < -0.15:
        signal = "bearish"
        confidence = min(abs(final_score) * 1.5, 1.0) * avg_confidence
    else:
        signal = "neutral"
        # For neutral signals, confidence reflects how consistently the strategies 
        # agree that there's no clear directional bias
        # High confidence neutral = most signals are neutral or balanced bullish/bearish
        neutral_agreement = (
            signal_counts["neutral"] / num_signals if num_signals > 0 else 0
        )
        # Also consider if bullish and bearish cancel each other out
        balance_factor = 1.0 - abs(signal_counts["bullish"] - signal_counts["bearish"]) / max(num_signals, 1)
        confidence = max(neutral_agreement, balance_factor * 0.5) * avg_confidence

    return {"signal": signal, "confidence": safe_float(confidence, 0.5)}


def normalize_pandas(obj):
    """Convert pandas Series/DataFrames to primitive Python types"""
    if isinstance(obj, pd.Series):
        return obj.tolist()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict("records")
    elif isinstance(obj, dict):
        return {k: normalize_pandas(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [normalize_pandas(item) for item in obj]
    return obj


def calculate_rsi(prices_df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = prices_df["close"].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger_bands(prices_df: pd.DataFrame, window: int = 20) -> tuple[pd.Series, pd.Series]:
    sma = prices_df["close"].rolling(window).mean()
    std_dev = prices_df["close"].rolling(window).std()
    upper_band = sma + (std_dev * 2)
    lower_band = sma - (std_dev * 2)
    return upper_band, lower_band


def calculate_ema(df: pd.DataFrame, window: int) -> pd.Series:
    """
    Calculate Exponential Moving Average

    Args:
        df: DataFrame with price data
        window: EMA period

    Returns:
        pd.Series: EMA values
    """
    return df["close"].ewm(span=window, adjust=False).mean()


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculate Average Directional Index (ADX)

    Args:
        df: DataFrame with OHLC data
        period: Period for calculations

    Returns:
        DataFrame with ADX values
    """
    # Calculate True Range
    df["high_low"] = df["high"] - df["low"]
    df["high_close"] = abs(df["high"] - df["close"].shift())
    df["low_close"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)

    # Calculate Directional Movement
    df["up_move"] = df["high"] - df["high"].shift()
    df["down_move"] = df["low"].shift() - df["low"]

    df["plus_dm"] = np.where((df["up_move"] > df["down_move"]) & (df["up_move"] > 0), df["up_move"], 0)
    df["minus_dm"] = np.where((df["down_move"] > df["up_move"]) & (df["down_move"] > 0), df["down_move"], 0)

    # Calculate ADX
    df["+di"] = 100 * (df["plus_dm"].ewm(span=period).mean() / df["tr"].ewm(span=period).mean())
    df["-di"] = 100 * (df["minus_dm"].ewm(span=period).mean() / df["tr"].ewm(span=period).mean())
    df["dx"] = 100 * abs(df["+di"] - df["-di"]) / (df["+di"] + df["-di"])
    df["adx"] = df["dx"].ewm(span=period).mean()

    return df[["adx", "+di", "-di"]]


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range

    Args:
        df: DataFrame with OHLC data
        period: Period for ATR calculation

    Returns:
        pd.Series: ATR values
    """
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)

    return true_range.rolling(period).mean()


def calculate_hurst_exponent(price_series: pd.Series, max_lag: int = 20) -> float:
    """
    Calculate Hurst Exponent to determine long-term memory of time series
    H < 0.5: Mean reverting series
    H = 0.5: Random walk
    H > 0.5: Trending series

    Args:
        price_series: Array-like price data
        max_lag: Maximum lag for R/S calculation

    Returns:
        float: Hurst exponent
    """
    lags = range(2, max_lag)
    # Add small epsilon to avoid log(0)
    tau = [max(1e-8, np.sqrt(np.std(np.subtract(price_series[lag:], price_series[:-lag])))) for lag in lags]

    # Return the Hurst exponent from linear fit
    try:
        reg = np.polyfit(np.log(lags), np.log(tau), 1)
        return reg[0]  # Hurst exponent is the slope
    except (ValueError, RuntimeWarning):
        # Return 0.5 (random walk) if calculation fails
        return 0.5


def calculate_macd(
    prices_df: pd.DataFrame, 
    fast_period: int = 12, 
    slow_period: int = 26, 
    signal_period: int = 9
) -> dict:
    """
    Calculate MACD (Moving Average Convergence Divergence)
    
    MACD Line = EMA(12) - EMA(26)
    Signal Line = EMA(9) of MACD Line
    Histogram = MACD Line - Signal Line
    
    Args:
        prices_df: DataFrame with 'close' prices
        fast_period: Fast EMA period (default 12)
        slow_period: Slow EMA period (default 26)
        signal_period: Signal line period (default 9)
    
    Returns:
        dict with macd_line, signal_line, histogram, and signal interpretation
    """
    close = prices_df["close"]
    
    # Calculate EMAs
    ema_fast = close.ewm(span=fast_period, adjust=False).mean()
    ema_slow = close.ewm(span=slow_period, adjust=False).mean()
    
    # MACD Line
    macd_line = ema_fast - ema_slow
    
    # Signal Line
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    
    # Histogram
    histogram = macd_line - signal_line
    
    # Get current values
    current_macd = safe_float(macd_line.iloc[-1])
    current_signal = safe_float(signal_line.iloc[-1])
    current_histogram = safe_float(histogram.iloc[-1])
    prev_histogram = safe_float(histogram.iloc[-2]) if len(histogram) > 1 else 0
    
    # Signal interpretation
    if current_macd > current_signal and current_histogram > 0:
        if current_histogram > prev_histogram:
            signal = "bullish"
            confidence = min(0.8, abs(current_histogram) * 10)
        else:
            signal = "bullish"
            confidence = 0.6
    elif current_macd < current_signal and current_histogram < 0:
        if current_histogram < prev_histogram:
            signal = "bearish"
            confidence = min(0.8, abs(current_histogram) * 10)
        else:
            signal = "bearish"
            confidence = 0.6
    else:
        signal = "neutral"
        confidence = 0.5
    
    # Detect crossovers
    crossover = None
    if len(macd_line) > 1:
        prev_macd = macd_line.iloc[-2]
        prev_signal_val = signal_line.iloc[-2]
        if prev_macd < prev_signal_val and current_macd > current_signal:
            crossover = "bullish_crossover"
            confidence = 0.85
        elif prev_macd > prev_signal_val and current_macd < current_signal:
            crossover = "bearish_crossover"
            confidence = 0.85
    
    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "macd_line": current_macd,
            "signal_line": current_signal,
            "histogram": current_histogram,
            "crossover": crossover,
        }
    }


def calculate_fibonacci_levels(prices_df: pd.DataFrame, lookback: int = 50) -> dict:
    """
    Calculate Fibonacci Retracement Levels
    
    Uses recent swing high and swing low to calculate key Fib levels:
    0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
    
    Args:
        prices_df: DataFrame with 'high', 'low', 'close' prices
        lookback: Period to find swing high/low (default 50 days)
    
    Returns:
        dict with levels, current position, and signal interpretation
    """
    # Use available data, up to lookback period
    period = min(lookback, len(prices_df) - 1)
    if period < 5:
        return {
            "signal": "neutral",
            "confidence": 0.3,
            "metrics": {"error": "Insufficient data for Fibonacci calculation"}
        }
    
    recent_data = prices_df.iloc[-period:]
    
    swing_high = safe_float(recent_data["high"].max())
    swing_low = safe_float(recent_data["low"].min())
    current_price = safe_float(prices_df["close"].iloc[-1])
    
    if swing_high == swing_low:
        return {
            "signal": "neutral",
            "confidence": 0.3,
            "metrics": {"error": "No price range for Fibonacci"}
        }
    
    diff = swing_high - swing_low
    
    # Standard Fibonacci levels (retracement from high)
    levels = {
        "0.0%": swing_high,
        "23.6%": swing_high - 0.236 * diff,
        "38.2%": swing_high - 0.382 * diff,
        "50.0%": swing_high - 0.500 * diff,
        "61.8%": swing_high - 0.618 * diff,
        "78.6%": swing_high - 0.786 * diff,
        "100%": swing_low,
    }
    
    # Find nearest support and resistance
    supports = [v for v in levels.values() if v < current_price]
    resistances = [v for v in levels.values() if v > current_price]
    
    nearest_support = max(supports) if supports else swing_low
    nearest_resistance = min(resistances) if resistances else swing_high
    
    # Calculate which Fib zone we're in
    retracement_pct = (swing_high - current_price) / diff if diff > 0 else 0.5
    
    # Signal interpretation
    # Near 61.8% or 78.6% retracement = potential reversal zone (bullish)
    # Near 23.6% or 38.2% = shallow pullback, trend continuation
    if 0.55 <= retracement_pct <= 0.70:
        signal = "bullish"
        confidence = 0.75
        zone = "golden_zone"  # 61.8% - prime reversal area
    elif 0.70 <= retracement_pct <= 0.85:
        signal = "bullish"
        confidence = 0.65
        zone = "deep_retracement"
    elif retracement_pct > 0.85:
        signal = "bearish"
        confidence = 0.6
        zone = "breakdown"
    elif retracement_pct < 0.25:
        signal = "bullish"
        confidence = 0.6
        zone = "near_highs"
    else:
        signal = "neutral"
        confidence = 0.5
        zone = "mid_range"
    
    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "swing_high": swing_high,
            "swing_low": swing_low,
            "current_price": current_price,
            "retracement_pct": round(retracement_pct * 100, 1),
            "zone": zone,
            "nearest_support": round(nearest_support, 2),
            "nearest_resistance": round(nearest_resistance, 2),
            "levels": {k: round(v, 2) for k, v in levels.items()},
        }
    }


def calculate_support_resistance(prices_df: pd.DataFrame, lookback: int = 50, num_levels: int = 3) -> dict:
    """
    Calculate Support and Resistance Levels
    
    Uses pivot points and price clustering to identify key levels.
    
    Args:
        prices_df: DataFrame with 'high', 'low', 'close' prices
        lookback: Period to analyze (default 50 days)
        num_levels: Number of S/R levels to return (default 3)
    
    Returns:
        dict with support levels, resistance levels, and signal interpretation
    """
    period = min(lookback, len(prices_df) - 1)
    if period < 10:
        return {
            "signal": "neutral",
            "confidence": 0.3,
            "metrics": {"error": "Insufficient data for S/R calculation"}
        }
    
    recent_data = prices_df.iloc[-period:]
    current_price = safe_float(prices_df["close"].iloc[-1])
    
    # Method 1: Pivot Points
    high = safe_float(recent_data["high"].max())
    low = safe_float(recent_data["low"].min())
    close = safe_float(recent_data["close"].iloc[-1])
    
    pivot = (high + low + close) / 3
    
    # Standard pivot levels
    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)
    
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)
    
    # Method 2: Find local maxima/minima for additional levels
    highs = recent_data["high"].values
    lows = recent_data["low"].values
    
    # Find peaks (local resistance)
    resistance_candidates = [r1, r2, r3, high]
    for i in range(2, len(highs) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1] and highs[i] > highs[i-2] and highs[i] > highs[i+2]:
            resistance_candidates.append(highs[i])
    
    # Find troughs (local support)
    support_candidates = [s1, s2, s3, low]
    for i in range(2, len(lows) - 2):
        if lows[i] < lows[i-1] and lows[i] < lows[i+1] and lows[i] < lows[i-2] and lows[i] < lows[i+2]:
            support_candidates.append(lows[i])
    
    # Filter and sort
    resistance_levels = sorted([r for r in set(resistance_candidates) if r > current_price])[:num_levels]
    support_levels = sorted([s for s in set(support_candidates) if s < current_price], reverse=True)[:num_levels]
    
    # Calculate distances
    nearest_resistance = resistance_levels[0] if resistance_levels else high
    nearest_support = support_levels[0] if support_levels else low
    
    upside_pct = ((nearest_resistance - current_price) / current_price) * 100 if current_price > 0 else 0
    downside_pct = ((current_price - nearest_support) / current_price) * 100 if current_price > 0 else 0
    
    # Risk/Reward interpretation
    if upside_pct > downside_pct * 2:
        signal = "bullish"
        confidence = min(0.8, 0.5 + (upside_pct / downside_pct) * 0.1)
    elif downside_pct > upside_pct * 2:
        signal = "bearish"
        confidence = min(0.8, 0.5 + (downside_pct / upside_pct) * 0.1)
    else:
        signal = "neutral"
        confidence = 0.5
    
    return {
        "signal": signal,
        "confidence": confidence,
        "metrics": {
            "current_price": current_price,
            "pivot": round(pivot, 2),
            "resistance_levels": [round(r, 2) for r in resistance_levels],
            "support_levels": [round(s, 2) for s in support_levels],
            "nearest_resistance": round(nearest_resistance, 2),
            "nearest_support": round(nearest_support, 2),
            "upside_to_resistance_pct": round(upside_pct, 1),
            "downside_to_support_pct": round(downside_pct, 1),
            "risk_reward_ratio": round(upside_pct / downside_pct, 2) if downside_pct > 0 else 0,
        }
    }
