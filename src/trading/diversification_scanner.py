"""
Diversification Scanner

Scans for affordable, quality stocks that could improve portfolio diversification.
Uses multiple data sources to find opportunities across sectors.
"""

import os
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from src.tools.api import get_financial_metrics, get_prices
from src.trading.alpaca_service import AlpacaService


@dataclass
class StockCandidate:
    """A potential stock for diversification."""
    ticker: str
    name: str
    sector: str
    price: float
    market_cap: float
    volume: float
    pe_ratio: Optional[float]
    dividend_yield: Optional[float]
    beta: Optional[float]
    analyst_rating: Optional[float]  # 1-5 scale
    score: float  # Diversification score 0-100
    reason: str


@dataclass
class ScanCriteria:
    """Criteria for scanning stocks."""
    max_price: float = 50.0
    min_volume: int = 500_000
    min_market_cap: float = 500_000_000  # $500M
    target_sectors: Optional[List[str]] = None
    exclude_sectors: Optional[List[str]] = None
    max_correlation: float = 0.6
    min_dividend_yield: Optional[float] = None
    max_beta: Optional[float] = None
    max_pe_ratio: Optional[float] = None


class DiversificationScanner:
    """Scans for stocks that could diversify the portfolio."""
    
    # Sector classifications
    SECTORS = [
        "Technology",
        "Healthcare", 
        "Financials",
        "Consumer Discretionary",
        "Consumer Staples",
        "Industrials",
        "Energy",
        "Utilities",
        "Materials",
        "Real Estate",
        "Communication Services",
    ]
    
    # Popular affordable stocks by sector (seed list)
    SECTOR_STOCKS = {
        "Technology": ["AMD", "PLTR", "SOFI", "RBLX", "HOOD", "SNAP", "PINS"],
        "Healthcare": ["HIMS", "TDOC", "GDRX", "SDC", "BNGO", "SNDL"],
        "Financials": ["SOFI", "NU", "HOOD", "COIN", "AFRM", "UPST"],
        "Consumer Discretionary": ["F", "GM", "NIO", "LCID", "RIVN", "W", "CHWY"],
        "Consumer Staples": ["KHC", "KDP", "TAP", "STZ", "BG"],
        "Industrials": ["PLUG", "CHPT", "BLDP", "FCEL", "BE"],
        "Energy": ["XOM", "CVX", "BP", "ET", "FANG", "SLB"],
        "Utilities": ["NEE", "DUK", "SO", "D", "AEP"],
        "Materials": ["CLF", "X", "AA", "FCX", "NEM"],
        "Real Estate": ["O", "VNQ", "SPG", "WELL", "PSA"],
        "Communication Services": ["T", "VZ", "TMUS", "LUMN"],
    }
    
    def __init__(self):
        self.alpaca = AlpacaService()
        
    def get_current_portfolio_sectors(self) -> Dict[str, float]:
        """Get sector allocation of current portfolio."""
        positions = self.alpaca.get_positions()
        account = self.alpaca.get_account()
        
        if not positions or not account:
            return {}
            
        total_equity = float(account.equity)
        sector_allocation = {}
        
        for pos in positions:
            # Get sector for ticker (simplified - in production, use actual sector data)
            ticker = pos.symbol
            sector = self._get_sector(ticker)
            market_value = abs(float(pos.market_value))
            allocation = market_value / total_equity if total_equity > 0 else 0
            
            if sector in sector_allocation:
                sector_allocation[sector] += allocation
            else:
                sector_allocation[sector] = allocation
                
        return sector_allocation
    
    def _get_sector(self, ticker: str) -> str:
        """Get sector for a ticker (simplified lookup)."""
        for sector, tickers in self.SECTOR_STOCKS.items():
            if ticker in tickers:
                return sector
        # Default mappings for common tickers
        sector_map = {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "GOOGL": "Technology",
            "AMZN": "Consumer Discretionary",
            "TSLA": "Consumer Discretionary",
            "META": "Communication Services",
            "NVDA": "Technology",
            "JPM": "Financials",
            "JNJ": "Healthcare",
            "V": "Financials",
        }
        return sector_map.get(ticker, "Unknown")
    
    def scan_for_opportunities(
        self, 
        criteria: Optional[ScanCriteria] = None,
        limit: int = 20
    ) -> List[StockCandidate]:
        """
        Scan for stocks that meet diversification criteria.
        
        Args:
            criteria: Filtering criteria for the scan
            limit: Maximum number of candidates to return
            
        Returns:
            List of stock candidates sorted by diversification score
        """
        if criteria is None:
            criteria = ScanCriteria()
            
        # Get current sector allocation
        current_sectors = self.get_current_portfolio_sectors()
        underweight_sectors = self._find_underweight_sectors(current_sectors)
        
        candidates = []
        
        # Prioritize stocks in underweight sectors
        for sector in underweight_sectors:
            if criteria.exclude_sectors and sector in criteria.exclude_sectors:
                continue
            if criteria.target_sectors and sector not in criteria.target_sectors:
                continue
                
            sector_stocks = self.SECTOR_STOCKS.get(sector, [])
            for ticker in sector_stocks:
                candidate = self._evaluate_stock(ticker, sector, criteria, current_sectors)
                if candidate:
                    candidates.append(candidate)
                    
        # Also check other sectors for opportunities
        for sector, tickers in self.SECTOR_STOCKS.items():
            if sector in underweight_sectors:
                continue  # Already processed
            if criteria.exclude_sectors and sector in criteria.exclude_sectors:
                continue
            if criteria.target_sectors and sector not in criteria.target_sectors:
                continue
                
            for ticker in tickers:
                candidate = self._evaluate_stock(ticker, sector, criteria, current_sectors)
                if candidate:
                    candidates.append(candidate)
        
        # Sort by diversification score
        candidates.sort(key=lambda x: x.score, reverse=True)
        
        return candidates[:limit]
    
    def _find_underweight_sectors(
        self, 
        current_sectors: Dict[str, float],
        target_allocation: float = 0.10  # 10% per sector ideal
    ) -> List[str]:
        """Find sectors that are underweight in the portfolio."""
        underweight = []
        
        for sector in self.SECTORS:
            current = current_sectors.get(sector, 0)
            if current < target_allocation:
                underweight.append(sector)
                
        # Sort by how underweight they are
        underweight.sort(key=lambda s: current_sectors.get(s, 0))
        
        return underweight
    
    def _evaluate_stock(
        self,
        ticker: str,
        sector: str,
        criteria: ScanCriteria,
        current_sectors: Dict[str, float]
    ) -> Optional[StockCandidate]:
        """
        Evaluate a single stock against criteria.
        
        Returns StockCandidate if it passes, None otherwise.
        """
        try:
            # Get current price
            prices = get_prices(ticker, limit=5)
            if not prices:
                return None
                
            current_price = prices[-1].close
            
            # Check price criteria
            if current_price > criteria.max_price:
                return None
                
            # Get financial metrics
            end_date = datetime.now().strftime("%Y-%m-%d")
            metrics = get_financial_metrics(ticker, end_date=end_date, limit=1)
            
            if not metrics:
                return None
                
            latest_metrics = metrics[0]
            
            # Check market cap
            market_cap = latest_metrics.market_cap or 0
            if market_cap < criteria.min_market_cap:
                return None
                
            # Check PE ratio
            pe_ratio = latest_metrics.price_to_earnings_ratio
            if criteria.max_pe_ratio and pe_ratio and pe_ratio > criteria.max_pe_ratio:
                return None
                
            # Calculate diversification score
            score, reason = self._calculate_diversification_score(
                ticker, sector, current_price, market_cap, 
                pe_ratio, current_sectors, criteria
            )
            
            return StockCandidate(
                ticker=ticker,
                name=ticker,  # Would need company name lookup
                sector=sector,
                price=current_price,
                market_cap=market_cap,
                volume=0,  # Would need volume data
                pe_ratio=pe_ratio,
                dividend_yield=latest_metrics.dividend_yield,
                beta=None,  # Would need beta calculation
                analyst_rating=None,  # Would need analyst data
                score=score,
                reason=reason,
            )
            
        except Exception as e:
            print(f"Error evaluating {ticker}: {e}")
            return None
    
    def _calculate_diversification_score(
        self,
        ticker: str,
        sector: str,
        price: float,
        market_cap: float,
        pe_ratio: Optional[float],
        current_sectors: Dict[str, float],
        criteria: ScanCriteria
    ) -> tuple[float, str]:
        """
        Calculate a diversification score for a stock.
        
        Returns (score, reason) tuple.
        """
        score = 50.0  # Base score
        reasons = []
        
        # Sector diversification bonus
        current_sector_weight = current_sectors.get(sector, 0)
        if current_sector_weight == 0:
            score += 30
            reasons.append(f"New sector exposure ({sector})")
        elif current_sector_weight < 0.05:
            score += 20
            reasons.append(f"Underweight sector ({sector}: {current_sector_weight:.1%})")
        elif current_sector_weight < 0.10:
            score += 10
            reasons.append(f"Below target allocation ({sector})")
        elif current_sector_weight > 0.25:
            score -= 20
            reasons.append(f"Overweight sector ({sector}: {current_sector_weight:.1%})")
            
        # Price affordability bonus
        if price < 10:
            score += 15
            reasons.append("Very affordable (<$10)")
        elif price < 25:
            score += 10
            reasons.append("Affordable (<$25)")
        elif price < 50:
            score += 5
            reasons.append("Reasonable price (<$50)")
            
        # Market cap stability
        if market_cap > 10_000_000_000:  # $10B+
            score += 10
            reasons.append("Large cap stability")
        elif market_cap > 2_000_000_000:  # $2B+
            score += 5
            reasons.append("Mid cap")
            
        # PE ratio value
        if pe_ratio:
            if 0 < pe_ratio < 15:
                score += 10
                reasons.append("Value P/E (<15)")
            elif pe_ratio < 0:
                score -= 10
                reasons.append("Negative earnings")
            elif pe_ratio > 50:
                score -= 5
                reasons.append("High P/E (>50)")
                
        # Ensure score is 0-100
        score = max(0, min(100, score))
        
        return score, " | ".join(reasons) if reasons else "Meets basic criteria"
    
    def get_sector_breakdown(self) -> Dict[str, Any]:
        """Get detailed sector breakdown of current portfolio."""
        positions = self.alpaca.get_positions()
        account = self.alpaca.get_account()
        
        if not account:
            return {"error": "Could not fetch account"}
            
        total_equity = float(account.equity)
        
        sectors = {}
        for pos in positions:
            sector = self._get_sector(pos.symbol)
            market_value = abs(float(pos.market_value))
            
            if sector not in sectors:
                sectors[sector] = {
                    "total_value": 0,
                    "allocation": 0,
                    "positions": []
                }
                
            sectors[sector]["total_value"] += market_value
            sectors[sector]["positions"].append({
                "ticker": pos.symbol,
                "qty": float(pos.qty),
                "value": market_value,
                "pnl": float(pos.unrealized_pl),
            })
            
        # Calculate allocations
        for sector in sectors:
            sectors[sector]["allocation"] = (
                sectors[sector]["total_value"] / total_equity 
                if total_equity > 0 else 0
            )
            
        return {
            "total_equity": total_equity,
            "sectors": sectors,
            "missing_sectors": [s for s in self.SECTORS if s not in sectors],
        }


def scan_diversification(
    max_price: float = 50.0,
    target_sectors: Optional[List[str]] = None,
    limit: int = 20
) -> List[StockCandidate]:
    """
    Convenience function to run a diversification scan.
    
    Args:
        max_price: Maximum stock price
        target_sectors: List of sectors to focus on (None = all)
        limit: Max results
        
    Returns:
        List of stock candidates
    """
    scanner = DiversificationScanner()
    criteria = ScanCriteria(
        max_price=max_price,
        target_sectors=target_sectors,
    )
    return scanner.scan_for_opportunities(criteria, limit)
