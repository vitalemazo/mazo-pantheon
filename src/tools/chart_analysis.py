"""
Chart Analysis Service for AI Visual Pattern Recognition.

Uses Chart-img API to generate TradingView chart snapshots and
vision-capable LLMs (Claude, GPT-4V) to analyze patterns.

Features:
- Generate professional chart images with indicators
- AI pattern recognition (support/resistance, trends, formations)
- Integration with technical analyst agent
"""

import base64
import logging
import os
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Chart-img API endpoints
CHART_IMG_API_V2 = "https://api.chart-img.com/v2/tradingview/advanced-chart"
CHART_IMG_API_V2_STORAGE = "https://api.chart-img.com/v2/tradingview/advanced-chart/storage"


def get_chart_img_api_key() -> Optional[str]:
    """Get Chart-img API key from database or environment."""
    # Try database first (Settings UI)
    try:
        from sqlalchemy import create_engine, text
        db_url = os.environ.get(
            "DATABASE_URL", 
            "postgresql://mazo:mazo@mazo-postgres:5432/mazo_pantheon"
        )
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT key_value FROM api_keys WHERE provider = 'CHART_IMG_API_KEY' AND is_active = true")
            )
            row = result.fetchone()
            if row and row[0]:
                return row[0]
    except Exception as e:
        logger.debug(f"Could not fetch Chart-img key from DB: {e}")
    
    # Fall back to environment variable
    return os.environ.get("CHART_IMG_API_KEY")


@dataclass
class ChartAnalysisResult:
    """Result from chart pattern analysis."""
    ticker: str
    interval: str
    chart_url: Optional[str] = None
    patterns_detected: List[str] = None
    trend_direction: str = "neutral"  # bullish, bearish, neutral
    key_levels: Dict[str, float] = None  # support, resistance levels
    signal: str = "hold"  # buy, sell, hold
    confidence: float = 0.5
    analysis_summary: str = ""
    raw_llm_response: str = ""
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.patterns_detected is None:
            self.patterns_detected = []
        if self.key_levels is None:
            self.key_levels = {}


def generate_chart_image(
    ticker: str,
    interval: str = "1D",
    exchange: str = "NASDAQ",
    studies: Optional[List[str]] = None,
    width: int = 1200,
    height: int = 600,
    save_to_storage: bool = True,
) -> Dict[str, Any]:
    """
    Generate a TradingView chart image using Chart-img API.
    
    Args:
        ticker: Stock symbol (e.g., "AAPL")
        interval: Chart interval ("1m", "5m", "15m", "1h", "4h", "1D", "1W")
        exchange: Exchange name ("NASDAQ", "NYSE", "BINANCE")
        studies: List of technical indicators to overlay
        width: Chart width in pixels
        height: Chart height in pixels
        save_to_storage: If True, returns URL; if False, returns base64 image
    
    Returns:
        Dict with success status, url/image_data, and metadata
    """
    api_key = get_chart_img_api_key()
    
    if not api_key:
        return {
            "success": False,
            "error": "Chart-img API key not configured",
        }
    
    # Format symbol (e.g., NASDAQ:AAPL)
    symbol = f"{exchange.upper()}:{ticker.upper()}"
    
    # Default studies if not specified
    if studies is None:
        studies = [
            {"name": "Volume", "forceOverlay": True},
            {"name": "Moving Average Exponential", "input": {"length": 20}},
            {"name": "Moving Average Exponential", "input": {"length": 50}},
            {"name": "Bollinger Bands"},
            {"name": "Relative Strength Index"},
            {"name": "MACD"},
        ]
    else:
        studies = [{"name": s} if isinstance(s, str) else s for s in studies]
    
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }
    
    payload = {
        "symbol": symbol,
        "interval": interval,
        "width": width,
        "height": height,
        "theme": "dark",
        "style": "candle",
        "timezone": "America/New_York",
        "studies": studies,
    }
    
    try:
        if save_to_storage:
            response = requests.post(
                CHART_IMG_API_V2_STORAGE,
                headers=headers,
                json=payload,
                timeout=60,
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "url": data.get("url"),
                    "symbol": symbol,
                    "interval": interval,
                    "expires": data.get("expire"),
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}",
                }
        else:
            response = requests.post(
                CHART_IMG_API_V2,
                headers=headers,
                json=payload,
                timeout=60,
            )
            
            if response.status_code == 200:
                image_base64 = base64.b64encode(response.content).decode("utf-8")
                content_type = response.headers.get("content-type", "image/png")
                return {
                    "success": True,
                    "image_data": f"data:{content_type};base64,{image_base64}",
                    "symbol": symbol,
                    "interval": interval,
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}",
                }
                
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timeout"}
    except Exception as e:
        logger.error(f"Chart generation error: {e}")
        return {"success": False, "error": str(e)}


def analyze_chart_with_vision(
    ticker: str,
    chart_url: Optional[str] = None,
    chart_base64: Optional[str] = None,
    interval: str = "1D",
    additional_context: str = "",
) -> ChartAnalysisResult:
    """
    Analyze a chart image using a vision-capable LLM.
    
    Args:
        ticker: Stock symbol for context
        chart_url: URL of the chart image (preferred)
        chart_base64: Base64-encoded chart image (fallback)
        interval: Chart timeframe for context
        additional_context: Extra context (e.g., recent news, fundamentals)
    
    Returns:
        ChartAnalysisResult with pattern analysis
    """
    from src.llm.models import get_model
    import json
    
    if not chart_url and not chart_base64:
        return ChartAnalysisResult(
            ticker=ticker,
            interval=interval,
            error="No chart image provided"
        )
    
    # Build the analysis prompt
    system_prompt = """You are an expert technical analyst specializing in chart pattern recognition.
Analyze the provided TradingView chart and identify:

1. **Trend Direction**: Is the stock in an uptrend, downtrend, or sideways consolidation?
2. **Chart Patterns**: Identify any patterns (head & shoulders, double top/bottom, triangles, flags, etc.)
3. **Key Levels**: Identify support and resistance levels visible on the chart
4. **Indicator Signals**: Analyze the indicators shown (EMA crossovers, RSI overbought/oversold, MACD divergence, Bollinger Band squeeze/breakout)
5. **Volume Analysis**: Note any significant volume patterns

Provide your analysis in JSON format:
{
    "trend_direction": "bullish" | "bearish" | "neutral",
    "patterns_detected": ["pattern1", "pattern2"],
    "key_levels": {
        "support_1": price,
        "support_2": price,
        "resistance_1": price,
        "resistance_2": price
    },
    "indicator_signals": {
        "ema": "bullish/bearish/neutral",
        "rsi": "overbought/oversold/neutral",
        "macd": "bullish/bearish/neutral",
        "bollinger": "squeeze/breakout_up/breakout_down/neutral"
    },
    "volume_trend": "increasing" | "decreasing" | "stable",
    "signal": "buy" | "sell" | "hold",
    "confidence": 0.0 to 1.0,
    "analysis_summary": "Brief 2-3 sentence summary of the chart setup"
}"""

    user_prompt = f"""Analyze this {interval} chart for {ticker}.
{f'Additional context: {additional_context}' if additional_context else ''}

Provide your technical analysis in the JSON format specified."""

    try:
        # Try to use Claude with vision (Anthropic)
        model_name = os.environ.get("VISION_MODEL", "claude-sonnet-4-5-20250929")
        
        # Build message with image
        if chart_url:
            # Use URL-based image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "url",
                                "url": chart_url,
                            },
                        },
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                    ],
                }
            ]
        else:
            # Use base64 image
            # Extract media type and data from data URL
            if chart_base64.startswith("data:"):
                media_type = chart_base64.split(";")[0].split(":")[1]
                image_data = chart_base64.split(",")[1]
            else:
                media_type = "image/png"
                image_data = chart_base64
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                    ],
                }
            ]
        
        # Call the vision model using Anthropic SDK directly
        import anthropic
        
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            # Try to get from database
            try:
                from sqlalchemy import create_engine, text
                db_url = os.environ.get(
                    "DATABASE_URL",
                    "postgresql://mazo:mazo@mazo-postgres:5432/mazo_pantheon"
                )
                engine = create_engine(db_url)
                with engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT key_value FROM api_keys WHERE provider = 'ANTHROPIC_API_KEY' AND is_active = true")
                    )
                    row = result.fetchone()
                    if row and row[0]:
                        api_key = row[0]
            except Exception:
                pass
        
        if not api_key:
            return ChartAnalysisResult(
                ticker=ticker,
                interval=interval,
                chart_url=chart_url,
                error="Anthropic API key not configured for vision analysis"
            )
        
        client = anthropic.Anthropic(api_key=api_key)
        
        response = client.messages.create(
            model=model_name,
            max_tokens=2000,
            system=system_prompt,
            messages=messages,
        )
        
        # Parse the response
        raw_response = response.content[0].text
        
        # Extract JSON from response
        try:
            # Try to parse directly
            if "{" in raw_response:
                json_start = raw_response.find("{")
                json_end = raw_response.rfind("}") + 1
                json_str = raw_response[json_start:json_end]
                analysis = json.loads(json_str)
            else:
                analysis = {}
        except json.JSONDecodeError:
            analysis = {}
        
        return ChartAnalysisResult(
            ticker=ticker,
            interval=interval,
            chart_url=chart_url,
            patterns_detected=analysis.get("patterns_detected", []),
            trend_direction=analysis.get("trend_direction", "neutral"),
            key_levels=analysis.get("key_levels", {}),
            signal=analysis.get("signal", "hold"),
            confidence=float(analysis.get("confidence", 0.5)),
            analysis_summary=analysis.get("analysis_summary", raw_response[:500]),
            raw_llm_response=raw_response,
        )
        
    except Exception as e:
        logger.error(f"Chart vision analysis error: {e}")
        return ChartAnalysisResult(
            ticker=ticker,
            interval=interval,
            chart_url=chart_url,
            error=str(e)
        )


def analyze_ticker_chart(
    ticker: str,
    interval: str = "1D",
    exchange: str = "NASDAQ",
    include_vision_analysis: bool = True,
    additional_context: str = "",
) -> ChartAnalysisResult:
    """
    Complete chart analysis pipeline: generate chart and analyze with AI.
    
    Args:
        ticker: Stock symbol
        interval: Chart timeframe
        exchange: Stock exchange
        include_vision_analysis: Whether to run AI vision analysis
        additional_context: Extra context for the AI
    
    Returns:
        ChartAnalysisResult with full analysis
    """
    logger.info(f"[Chart] Generating chart for {ticker} ({interval})")
    
    # Step 1: Generate the chart
    chart_result = generate_chart_image(
        ticker=ticker,
        interval=interval,
        exchange=exchange,
        save_to_storage=True,  # Get URL for vision analysis
    )
    
    if not chart_result.get("success"):
        return ChartAnalysisResult(
            ticker=ticker,
            interval=interval,
            error=chart_result.get("error", "Chart generation failed")
        )
    
    chart_url = chart_result.get("url")
    logger.info(f"[Chart] Generated chart URL: {chart_url}")
    
    # Step 2: Analyze with vision AI (optional)
    if include_vision_analysis and chart_url:
        logger.info(f"[Chart] Running AI vision analysis for {ticker}")
        return analyze_chart_with_vision(
            ticker=ticker,
            chart_url=chart_url,
            interval=interval,
            additional_context=additional_context,
        )
    else:
        # Return just the chart URL without AI analysis
        return ChartAnalysisResult(
            ticker=ticker,
            interval=interval,
            chart_url=chart_url,
            analysis_summary="Chart generated successfully. Vision analysis not requested.",
        )


def batch_analyze_charts(
    tickers: List[str],
    interval: str = "1D",
    exchange: str = "NASDAQ",
    include_vision_analysis: bool = False,  # Default to False for batch to save API costs
) -> Dict[str, ChartAnalysisResult]:
    """
    Generate and optionally analyze charts for multiple tickers.
    
    Args:
        tickers: List of stock symbols
        interval: Chart timeframe
        exchange: Stock exchange
        include_vision_analysis: Whether to run AI analysis (expensive for batch)
    
    Returns:
        Dict mapping ticker to ChartAnalysisResult
    """
    results = {}
    
    for ticker in tickers[:10]:  # Limit to 10 to avoid rate limits
        try:
            result = analyze_ticker_chart(
                ticker=ticker,
                interval=interval,
                exchange=exchange,
                include_vision_analysis=include_vision_analysis,
            )
            results[ticker] = result
        except Exception as e:
            logger.error(f"[Chart] Error analyzing {ticker}: {e}")
            results[ticker] = ChartAnalysisResult(
                ticker=ticker,
                interval=interval,
                error=str(e)
            )
    
    return results
