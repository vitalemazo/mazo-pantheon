"""
Diversification Scanner API Routes

Provides endpoints for scanning and analyzing portfolio diversification opportunities.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.trading.diversification_scanner import (
    DiversificationScanner,
    ScanCriteria,
    StockCandidate,
    scan_diversification,
)


router = APIRouter(prefix="/diversification", tags=["diversification"])


class ScanRequest(BaseModel):
    """Request model for diversification scan."""
    max_price: float = 50.0
    min_volume: int = 500_000
    min_market_cap: float = 500_000_000
    target_sectors: Optional[List[str]] = None
    exclude_sectors: Optional[List[str]] = None
    limit: int = 20


class StockCandidateResponse(BaseModel):
    """Response model for a stock candidate."""
    ticker: str
    name: str
    sector: str
    price: float
    market_cap: float
    volume: float
    pe_ratio: Optional[float]
    dividend_yield: Optional[float]
    beta: Optional[float]
    analyst_rating: Optional[float]
    score: float
    reason: str


class ScanResponse(BaseModel):
    """Response model for scan results."""
    success: bool
    candidates: List[StockCandidateResponse]
    total_found: int
    sectors_scanned: List[str]
    current_portfolio_sectors: dict
    error: Optional[str] = None


class SectorBreakdownResponse(BaseModel):
    """Response model for sector breakdown."""
    success: bool
    total_equity: float
    sectors: dict
    missing_sectors: List[str]
    error: Optional[str] = None


@router.post("/scan", response_model=ScanResponse)
async def scan_for_diversification(request: ScanRequest):
    """
    Scan for stocks that could diversify the portfolio.
    
    Finds affordable, quality stocks in underweight sectors.
    """
    try:
        scanner = DiversificationScanner()
        
        criteria = ScanCriteria(
            max_price=request.max_price,
            min_volume=request.min_volume,
            min_market_cap=request.min_market_cap,
            target_sectors=request.target_sectors,
            exclude_sectors=request.exclude_sectors,
        )
        
        candidates = scanner.scan_for_opportunities(criteria, request.limit)
        current_sectors = scanner.get_current_portfolio_sectors()
        
        return ScanResponse(
            success=True,
            candidates=[
                StockCandidateResponse(
                    ticker=c.ticker,
                    name=c.name,
                    sector=c.sector,
                    price=c.price,
                    market_cap=c.market_cap,
                    volume=c.volume,
                    pe_ratio=c.pe_ratio,
                    dividend_yield=c.dividend_yield,
                    beta=c.beta,
                    analyst_rating=c.analyst_rating,
                    score=c.score,
                    reason=c.reason,
                )
                for c in candidates
            ],
            total_found=len(candidates),
            sectors_scanned=list(scanner.SECTOR_STOCKS.keys()),
            current_portfolio_sectors=current_sectors,
        )
        
    except Exception as e:
        return ScanResponse(
            success=False,
            candidates=[],
            total_found=0,
            sectors_scanned=[],
            current_portfolio_sectors={},
            error=str(e),
        )


@router.get("/sectors", response_model=SectorBreakdownResponse)
async def get_sector_breakdown():
    """
    Get detailed sector breakdown of the current portfolio.
    
    Shows allocation per sector and identifies missing sectors.
    """
    try:
        scanner = DiversificationScanner()
        breakdown = scanner.get_sector_breakdown()
        
        if "error" in breakdown:
            return SectorBreakdownResponse(
                success=False,
                total_equity=0,
                sectors={},
                missing_sectors=[],
                error=breakdown["error"],
            )
            
        return SectorBreakdownResponse(
            success=True,
            total_equity=breakdown["total_equity"],
            sectors=breakdown["sectors"],
            missing_sectors=breakdown["missing_sectors"],
        )
        
    except Exception as e:
        return SectorBreakdownResponse(
            success=False,
            total_equity=0,
            sectors={},
            missing_sectors=[],
            error=str(e),
        )


@router.get("/quick-scan")
async def quick_scan(
    max_price: float = 50.0,
    limit: int = 10
):
    """
    Quick scan for affordable diversification opportunities.
    
    Returns top candidates without detailed filtering.
    """
    try:
        candidates = scan_diversification(max_price=max_price, limit=limit)
        
        return {
            "success": True,
            "candidates": [
                {
                    "ticker": c.ticker,
                    "sector": c.sector,
                    "price": c.price,
                    "score": c.score,
                    "reason": c.reason,
                }
                for c in candidates
            ],
        }
        
    except Exception as e:
        return {
            "success": False,
            "candidates": [],
            "error": str(e),
        }


@router.get("/underweight-sectors")
async def get_underweight_sectors():
    """
    Get list of sectors that are underweight in the portfolio.
    
    Useful for identifying where to look for new positions.
    """
    try:
        scanner = DiversificationScanner()
        current_sectors = scanner.get_current_portfolio_sectors()
        underweight = scanner._find_underweight_sectors(current_sectors)
        
        return {
            "success": True,
            "underweight_sectors": underweight,
            "current_allocations": current_sectors,
            "target_allocation": 0.10,  # 10% per sector ideal
            "recommendations": [
                f"Consider adding positions in {sector}" 
                for sector in underweight[:3]
            ],
        }
        
    except Exception as e:
        return {
            "success": False,
            "underweight_sectors": [],
            "error": str(e),
        }
