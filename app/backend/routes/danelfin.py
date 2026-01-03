"""
Danelfin AI Scoring API routes.

Provides endpoints for testing connection and retrieving AI scores
from Danelfin's stock analytics platform.
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/danelfin", tags=["danelfin"])


class DanelfinScoreResponse(BaseModel):
    """Response model for Danelfin score."""
    ticker: str
    date: str
    ai_score: int
    technical: int
    fundamental: int
    sentiment: int
    low_risk: int
    buy_track_record: Optional[bool] = None
    sell_track_record: Optional[bool] = None
    signal: str  # Derived: strong_buy, buy, hold, sell, strong_sell
    highest_category: str
    highest_value: int
    success: bool
    error: Optional[str] = None


class DanelfinTestResponse(BaseModel):
    """Response model for connection test."""
    success: bool
    configured: bool
    message: Optional[str] = None
    error: Optional[str] = None
    test_ticker: Optional[str] = None


@router.get("/test", response_model=DanelfinTestResponse)
async def test_danelfin_connection():
    """
    Test Danelfin API connection.
    
    Used by the Settings UI to verify the API key is valid.
    """
    from src.tools.danelfin_api import test_connection
    
    result = test_connection()
    
    return DanelfinTestResponse(
        success=result.get("success", False),
        configured=result.get("configured", False),
        message=result.get("message"),
        error=result.get("error"),
        test_ticker=result.get("test_ticker"),
    )


@router.get("/score/{ticker}", response_model=DanelfinScoreResponse)
async def get_danelfin_score(
    ticker: str,
    refresh: bool = Query(False, description="Force refresh, bypassing cache"),
):
    """
    Get Danelfin AI scores for a specific ticker.
    
    Returns all 5 score metrics:
    - AI Score: Overall AI-powered ranking (1-10)
    - Technical: Technical analysis rating (1-10)
    - Fundamental: Fundamental analysis rating (1-10)
    - Sentiment: Market sentiment analysis (1-10)
    - Low Risk: Risk assessment rating (1-10)
    
    Results are cached for 15 minutes unless refresh=true.
    """
    from src.tools.danelfin_api import get_score
    
    score = get_score(ticker, use_cache=not refresh)
    
    if not score.success:
        # Return the error response but don't raise exception
        # This allows the UI to handle gracefully
        return DanelfinScoreResponse(
            ticker=ticker,
            date="",
            ai_score=0,
            technical=0,
            fundamental=0,
            sentiment=0,
            low_risk=0,
            signal="unknown",
            highest_category="",
            highest_value=0,
            success=False,
            error=score.error,
        )
    
    highest_cat, highest_val = score.highest_score
    
    return DanelfinScoreResponse(
        ticker=score.ticker,
        date=score.date,
        ai_score=score.ai_score,
        technical=score.technical,
        fundamental=score.fundamental,
        sentiment=score.sentiment,
        low_risk=score.low_risk,
        buy_track_record=score.buy_track_record,
        sell_track_record=score.sell_track_record,
        signal=score.signal,
        highest_category=highest_cat,
        highest_value=highest_val,
        success=True,
    )


@router.get("/top")
async def get_top_danelfin_stocks(
    min_score: int = Query(8, ge=1, le=10, description="Minimum AI score"),
    sector: Optional[str] = Query(None, description="Filter by sector slug"),
    industry: Optional[str] = Query(None, description="Filter by industry slug"),
    asset_type: str = Query("stock", description="stock or etf"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
):
    """
    Get top-ranked stocks from Danelfin.
    
    Returns stocks with AI Score >= min_score, optionally filtered by sector/industry.
    """
    from src.tools.danelfin_api import get_top_stocks
    
    results = get_top_stocks(
        min_ai_score=min_score,
        sector=sector,
        industry=industry,
        asset_type=asset_type,
        limit=limit,
    )
    
    return {
        "success": bool(results),
        "count": len(results),
        "stocks": [score.to_dict() for score in results.values()],
    }


@router.get("/sectors")
async def get_danelfin_sectors():
    """Get list of available sectors for filtering."""
    from src.tools.danelfin_api import get_sectors
    
    sectors = get_sectors()
    return {"sectors": sectors}


@router.get("/industries")
async def get_danelfin_industries():
    """Get list of available industries for filtering."""
    from src.tools.danelfin_api import get_industries
    
    industries = get_industries()
    return {"industries": industries}


@router.post("/batch")
async def get_batch_scores(tickers: List[str]):
    """
    Get Danelfin scores for multiple tickers.
    
    Useful for getting scores for all positions or watchlist items.
    Limited to 20 tickers per batch.
    """
    from src.tools.danelfin_api import get_score
    
    if len(tickers) > 20:
        raise HTTPException(
            status_code=400,
            detail="Maximum 20 tickers per batch"
        )
    
    results = []
    for ticker in tickers:
        score = get_score(ticker)
        if score.success:
            highest_cat, highest_val = score.highest_score
            results.append({
                **score.to_dict(),
                "signal": score.signal,
                "highest_category": highest_cat,
                "highest_value": highest_val,
            })
        else:
            results.append({
                "ticker": ticker,
                "success": False,
                "error": score.error,
            })
    
    successful = sum(1 for r in results if r.get("success", False))
    
    return {
        "total": len(tickers),
        "successful": successful,
        "failed": len(tickers) - successful,
        "scores": results,
    }
