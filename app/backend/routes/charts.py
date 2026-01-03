"""
Chart-img API integration for TradingView chart snapshots.

Uses Chart-img (https://chart-img.com/) to generate professional chart images
for AI visual pattern analysis via vision models (GPT-4V, Claude, etc.).

API Documentation: https://doc.chart-img.com/
"""

import logging
import os
from typing import Optional, List

import requests
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.backend.database.connection import engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/charts", tags=["charts"])

# Chart-img API configuration
CHART_IMG_API_V2 = "https://api.chart-img.com/v2/tradingview/advanced-chart"
CHART_IMG_API_V2_STORAGE = "https://api.chart-img.com/v2/tradingview/advanced-chart/storage"


def get_chart_img_api_key() -> Optional[str]:
    """Get Chart-img API key from database or environment."""
    # Try database first (Settings UI)
    try:
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


class ChartRequest(BaseModel):
    """Request body for generating a chart."""
    symbol: str  # e.g., "NASDAQ:AAPL" or "BINANCE:BTCUSDT"
    interval: str = "1D"  # 1m, 5m, 15m, 30m, 1h, 4h, 1D, 1W, 1M
    width: int = 800
    height: int = 600
    theme: str = "dark"  # light or dark
    style: str = "candle"  # bar, candle, line, area, heikinAshi, hollowCandle
    studies: Optional[List[str]] = None  # e.g., ["RSI", "MACD", "Bollinger Bands"]
    timezone: str = "America/New_York"
    save_to_storage: bool = False  # If true, saves to Chart-img storage and returns URL


class ChartResponse(BaseModel):
    """Response from chart generation."""
    success: bool
    url: Optional[str] = None  # URL if saved to storage
    image_data: Optional[str] = None  # Base64 image data if not saved
    error: Optional[str] = None
    symbol: Optional[str] = None
    interval: Optional[str] = None


@router.get("/test")
async def test_chart_img_connection():
    """
    Test Chart-img API connection and return account info.
    """
    api_key = get_chart_img_api_key()
    
    if not api_key:
        return {
            "success": False,
            "error": "Chart-img API key not configured. Add CHART_IMG_API_KEY in Settings.",
            "configured": False,
        }
    
    # Test with a simple chart request
    try:
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
        }
        
        # Make a minimal test request
        test_payload = {
            "symbol": "NASDAQ:AAPL",
            "interval": "1D",
            "width": 400,
            "height": 300,
            "theme": "dark",
        }
        
        response = requests.post(
            CHART_IMG_API_V2,
            headers=headers,
            json=test_payload,
            timeout=30,
        )
        
        if response.status_code == 200:
            # Success - we got an image back
            return {
                "success": True,
                "configured": True,
                "message": "Chart-img API connected successfully",
                "plan": "PRO or higher",  # Can't determine exact plan from response
                "test_symbol": "NASDAQ:AAPL",
            }
        elif response.status_code == 403:
            return {
                "success": False,
                "error": "Invalid API key or inactive subscription",
                "configured": True,
            }
        elif response.status_code == 429:
            return {
                "success": True,  # Key works but rate limited
                "configured": True,
                "message": "API key valid but rate limited. Wait and try again.",
                "plan": "Check your plan limits",
            }
        else:
            error_detail = response.text[:200] if response.text else "Unknown error"
            return {
                "success": False,
                "error": f"API error: {response.status_code} - {error_detail}",
                "configured": True,
            }
            
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Connection timeout. Chart-img API may be slow.",
            "configured": True,
        }
    except Exception as e:
        logger.error(f"Chart-img test error: {e}")
        return {
            "success": False,
            "error": str(e),
            "configured": True,
        }


@router.post("/generate", response_model=ChartResponse)
async def generate_chart(request: ChartRequest):
    """
    Generate a TradingView chart image.
    
    Returns either a storage URL (if save_to_storage=true) or base64 image data.
    """
    api_key = get_chart_img_api_key()
    
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Chart-img API key not configured. Add CHART_IMG_API_KEY in Settings."
        )
    
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }
    
    # Build the request payload
    payload = {
        "symbol": request.symbol,
        "interval": request.interval,
        "width": request.width,
        "height": request.height,
        "theme": request.theme,
        "style": request.style,
        "timezone": request.timezone,
    }
    
    # Add studies/indicators if specified
    if request.studies:
        payload["studies"] = [{"name": study} for study in request.studies]
    
    try:
        if request.save_to_storage:
            # Use storage endpoint - returns a URL
            response = requests.post(
                CHART_IMG_API_V2_STORAGE,
                headers=headers,
                json=payload,
                timeout=60,
            )
            
            if response.status_code == 200:
                data = response.json()
                return ChartResponse(
                    success=True,
                    url=data.get("url") if isinstance(data, dict) else None,
                    symbol=request.symbol,
                    interval=request.interval,
                )
            else:
                try:
                    err_data = response.json()
                    error_msg = err_data.get("message", str(err_data)[:200]) if isinstance(err_data, dict) else str(err_data)[:200]
                except Exception:
                    error_msg = response.text[:200]
                return ChartResponse(
                    success=False,
                    error=f"Chart generation failed: {error_msg}",
                    symbol=request.symbol,
                )
        else:
            # Get image directly
            response = requests.post(
                CHART_IMG_API_V2,
                headers=headers,
                json=payload,
                timeout=60,
            )
            
            if response.status_code == 200:
                # Convert image to base64
                import base64
                image_base64 = base64.b64encode(response.content).decode("utf-8")
                content_type = response.headers.get("content-type", "image/png")
                
                return ChartResponse(
                    success=True,
                    image_data=f"data:{content_type};base64,{image_base64}",
                    symbol=request.symbol,
                    interval=request.interval,
                )
            else:
                try:
                    error_msg = response.json().get("message", "Unknown error")
                except:
                    error_msg = response.text[:200]
                return ChartResponse(
                    success=False,
                    error=f"Chart generation failed: {error_msg}",
                    symbol=request.symbol,
                )
                
    except requests.exceptions.Timeout:
        return ChartResponse(
            success=False,
            error="Request timeout. Try a smaller chart or check connection.",
            symbol=request.symbol,
        )
    except Exception as e:
        logger.error(f"Chart generation error: {e}")
        return ChartResponse(
            success=False,
            error=str(e),
            symbol=request.symbol,
        )


@router.get("/quick/{ticker}")
async def quick_chart(
    ticker: str,
    interval: str = Query("1D", description="Chart interval: 1m, 5m, 15m, 30m, 1h, 4h, 1D, 1W"),
    exchange: str = Query("NASDAQ", description="Exchange: NASDAQ, NYSE, BINANCE, etc."),
):
    """
    Quick chart generation for a ticker with sensible defaults.
    
    Returns a storage URL for the chart image.
    """
    api_key = get_chart_img_api_key()
    
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Chart-img API key not configured"
        )
    
    # Format symbol (e.g., NASDAQ:AAPL)
    symbol = f"{exchange.upper()}:{ticker.upper()}"
    
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }
    
    payload = {
        "symbol": symbol,
        "interval": interval,
        "width": 1200,
        "height": 600,
        "theme": "dark",
        "style": "candle",
        "timezone": "America/New_York",
        "studies": [
            {"name": "Volume", "forceOverlay": True},
            {"name": "Moving Average Exponential", "input": {"length": 20}},
            {"name": "Moving Average Exponential", "input": {"length": 50}},
            {"name": "Relative Strength Index"},
        ],
    }
    
    try:
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
            try:
                error_msg = response.json().get("message", "Unknown error")
            except:
                error_msg = response.text[:200]
            raise HTTPException(status_code=response.status_code, detail=error_msg)
            
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Chart generation timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quick chart error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def batch_charts(tickers: List[str], interval: str = "1D", exchange: str = "NASDAQ"):
    """
    Generate charts for multiple tickers.
    
    Useful for generating charts for all positions or watchlist items.
    Limited to 10 tickers per batch to avoid rate limits.
    """
    api_key = get_chart_img_api_key()
    
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Chart-img API key not configured"
        )
    
    if len(tickers) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 tickers per batch to avoid rate limits"
        )
    
    results = []
    
    for ticker in tickers:
        try:
            symbol = f"{exchange.upper()}:{ticker.upper()}"
            
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json",
            }
            
            payload = {
                "symbol": symbol,
                "interval": interval,
                "width": 800,
                "height": 400,
                "theme": "dark",
                "style": "candle",
                "studies": [
                    {"name": "Volume", "forceOverlay": True},
                    {"name": "Bollinger Bands"},
                ],
            }
            
            response = requests.post(
                CHART_IMG_API_V2_STORAGE,
                headers=headers,
                json=payload,
                timeout=30,
            )
            
            if response.status_code == 200:
                data = response.json()
                results.append({
                    "ticker": ticker,
                    "symbol": symbol,
                    "success": True,
                    "url": data.get("url"),
                    "expires": data.get("expire"),
                })
            else:
                results.append({
                    "ticker": ticker,
                    "symbol": symbol,
                    "success": False,
                    "error": "Generation failed",
                })
                
        except Exception as e:
            results.append({
                "ticker": ticker,
                "success": False,
                "error": str(e),
            })
    
    successful = sum(1 for r in results if r.get("success"))
    
    return {
        "total": len(tickers),
        "successful": successful,
        "failed": len(tickers) - successful,
        "charts": results,
    }
