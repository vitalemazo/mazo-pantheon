"""
FMP Ultimate Gateway Module

Comprehensive wrapper for the full FMP Ultimate data catalog including:
- Company fundamentals, profiles, peers, executives
- Financial statements (as reported, growth, ratios, DCF)
- Analyst estimates, price targets, stock grades
- SEC filings (8-K, 10-K, 13F) and insider trading
- Market calendars (earnings, dividends, IPOs)
- Macro/economic indicators
- Market performance, sector/industry data
- Non-equity markets (ETF, commodities, forex, crypto)

Each data family can be enabled/disabled via environment variables.
All calls are cached and rate-limit monitored.
"""

import os
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

from src.tools.fmp_data import get_fmp_data_client, FMPDataClient
from src.data.cache import get_cache

logger = logging.getLogger(__name__)


def _cache_get(cache, key: str):
    """Helper to access cache internal _get method."""
    if hasattr(cache, '_get'):
        return cache._get(key)
    return None


def _cache_set(cache, key: str, value, ttl: int = 3600):
    """Helper to access cache internal _set method."""
    if hasattr(cache, '_set'):
        cache._set(key, value, ttl)


# =============================================================================
# Configuration: Enable/disable FMP data families via environment
# =============================================================================

class FMPModule(Enum):
    """FMP data modules that can be toggled."""
    FUNDAMENTALS = "FMP_MODULE_FUNDAMENTALS"
    ANALYSTS = "FMP_MODULE_ANALYSTS"
    FILINGS = "FMP_MODULE_FILINGS"
    INSIDER = "FMP_MODULE_INSIDER"
    CALENDAR = "FMP_MODULE_CALENDAR"
    MACRO = "FMP_MODULE_MACRO"
    MARKET = "FMP_MODULE_MARKET"
    ETF = "FMP_MODULE_ETF"
    COMMODITIES = "FMP_MODULE_COMMODITIES"
    FOREX = "FMP_MODULE_FOREX"
    CRYPTO = "FMP_MODULE_CRYPTO"
    ESG = "FMP_MODULE_ESG"


def is_module_enabled(module: FMPModule) -> bool:
    """Check if an FMP module is enabled via environment variable."""
    # Default all modules to enabled
    return os.getenv(module.value, "true").lower() in ("true", "1", "yes")


def get_enabled_modules() -> List[str]:
    """Get list of enabled FMP modules."""
    return [m.name for m in FMPModule if is_module_enabled(m)]


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class CompanyProfile:
    """Full company profile from FMP."""
    symbol: str
    company_name: str
    exchange: str
    sector: str
    industry: str
    description: str
    ceo: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None
    market_cap: Optional[float] = None
    employees: Optional[int] = None
    ipo_date: Optional[str] = None
    currency: str = "USD"
    is_etf: bool = False
    is_actively_trading: bool = True


@dataclass
class CompanyPeer:
    """Company peer comparison."""
    symbol: str
    peers: List[str] = field(default_factory=list)


@dataclass
class Executive:
    """Company executive information."""
    name: str
    title: str
    pay: Optional[float] = None
    currency: str = "USD"
    year_born: Optional[int] = None


@dataclass
class AnalystEstimate:
    """Analyst earnings/revenue estimates."""
    symbol: str
    date: str
    estimated_revenue_avg: Optional[float] = None
    estimated_revenue_low: Optional[float] = None
    estimated_revenue_high: Optional[float] = None
    number_analysts_estimated_revenue: int = 0
    estimated_eps_avg: Optional[float] = None
    estimated_eps_low: Optional[float] = None
    estimated_eps_high: Optional[float] = None
    number_analysts_estimated_eps: int = 0


@dataclass
class PriceTarget:
    """Analyst price target."""
    symbol: str
    published_date: str
    analyst_name: Optional[str] = None
    analyst_company: Optional[str] = None
    price_target: Optional[float] = None
    price_when_posted: Optional[float] = None
    upside: Optional[float] = None  # Percentage upside


@dataclass
class StockGrade:
    """Stock upgrade/downgrade."""
    symbol: str
    published_date: str
    grading_company: str
    previous_grade: Optional[str] = None
    new_grade: Optional[str] = None
    action: Optional[str] = None  # upgrade, downgrade, maintain


@dataclass
class InsiderTrade:
    """Insider trading activity."""
    symbol: str
    filing_date: str
    reporting_name: str
    transaction_type: str  # P-Purchase, S-Sale
    transaction_date: Optional[str] = None
    securities_owned: Optional[float] = None
    securities_transacted: Optional[float] = None
    price: Optional[float] = None
    form_type: str = "4"


@dataclass
class Form13F:
    """Institutional 13F filing data."""
    cik: str
    filing_date: str
    investor_name: str
    symbol: str
    shares: int
    value: float
    weight: Optional[float] = None
    change: Optional[float] = None  # Shares change from prior quarter


@dataclass
class EarningsEvent:
    """Upcoming/past earnings event."""
    symbol: str
    date: str
    eps_estimated: Optional[float] = None
    eps_actual: Optional[float] = None
    revenue_estimated: Optional[float] = None
    revenue_actual: Optional[float] = None
    time: Optional[str] = None  # bmo, amc


@dataclass
class DividendEvent:
    """Dividend event."""
    symbol: str
    date: str
    dividend: float
    adj_dividend: Optional[float] = None
    record_date: Optional[str] = None
    payment_date: Optional[str] = None
    declaration_date: Optional[str] = None


@dataclass
class EconomicIndicator:
    """Economic/macro indicator."""
    name: str
    date: str
    value: float
    previous: Optional[float] = None
    change: Optional[float] = None
    unit: Optional[str] = None


@dataclass
class SectorPerformance:
    """Sector performance data."""
    sector: str
    change_percentage: float
    one_day_change: Optional[float] = None
    five_day_change: Optional[float] = None
    one_month_change: Optional[float] = None
    ytd_change: Optional[float] = None


@dataclass
class MarketMover:
    """Stock gainer/loser."""
    symbol: str
    name: str
    change: float
    change_percentage: float
    price: float


@dataclass
class ETFHolding:
    """ETF constituent holding."""
    etf_symbol: str
    symbol: str
    name: str
    weight: float
    shares: Optional[int] = None


@dataclass
class CommodityQuote:
    """Commodity price quote."""
    symbol: str
    name: str
    price: float
    change: float
    change_percentage: float


@dataclass
class ForexQuote:
    """Forex pair quote."""
    symbol: str
    bid: float
    ask: float
    open: float
    high: float
    low: float
    change: float
    change_percentage: float


@dataclass
class CryptoQuote:
    """Cryptocurrency quote."""
    symbol: str
    name: str
    price: float
    change: float
    change_percentage: float
    market_cap: Optional[float] = None
    volume: Optional[float] = None


@dataclass
class ESGScore:
    """ESG (Environmental, Social, Governance) score."""
    symbol: str
    date: str
    environment_score: Optional[float] = None
    social_score: Optional[float] = None
    governance_score: Optional[float] = None
    esg_score: Optional[float] = None
    esg_rating: Optional[str] = None


# =============================================================================
# FMP Gateway Class
# =============================================================================

class FMPGateway:
    """
    Unified gateway for FMP Ultimate API.
    
    Provides typed, cached access to all FMP data families
    with configurable module toggles.
    """
    
    def __init__(self, client: FMPDataClient = None):
        self._client = client or get_fmp_data_client()
        self._cache = get_cache()
    
    @property
    def client(self) -> FMPDataClient:
        return self._client
    
    def is_configured(self) -> bool:
        """Check if FMP is properly configured."""
        return self._client.is_configured()
    
    def get_module_status(self) -> Dict[str, bool]:
        """Get status of all FMP modules."""
        return {m.name.lower(): is_module_enabled(m) for m in FMPModule}
    
    # =========================================================================
    # Company Fundamentals
    # =========================================================================
    
    def get_company_profile(self, symbol: str) -> Optional[CompanyProfile]:
        """Get full company profile."""
        if not is_module_enabled(FMPModule.FUNDAMENTALS):
            return None
        
        cache_key = f"fmp_profile_{symbol}"
        if cached := _cache_get(self._cache, cache_key):
            return CompanyProfile(**cached) if isinstance(cached, dict) else cached
        
        try:
            data = self._client._request("profile", {"symbol": symbol})
            if data and len(data) > 0:
                p = data[0]
                profile = CompanyProfile(
                    symbol=p.get("symbol", symbol),
                    company_name=p.get("companyName", ""),
                    exchange=p.get("exchangeShortName", ""),
                    sector=p.get("sector", ""),
                    industry=p.get("industry", ""),
                    description=p.get("description", ""),
                    ceo=p.get("ceo"),
                    website=p.get("website"),
                    country=p.get("country"),
                    market_cap=p.get("mktCap"),
                    employees=p.get("fullTimeEmployees"),
                    ipo_date=p.get("ipoDate"),
                    currency=p.get("currency", "USD"),
                    is_etf=p.get("isEtf", False),
                    is_actively_trading=p.get("isActivelyTrading", True),
                )
                _cache_set(self._cache, cache_key, asdict(profile), 86400)  # 24hr
                return profile
        except Exception as e:
            logger.error(f"Failed to get company profile for {symbol}: {e}")
        return None
    
    def get_company_peers(self, symbol: str) -> Optional[CompanyPeer]:
        """Get company peer list."""
        if not is_module_enabled(FMPModule.FUNDAMENTALS):
            return None
        
        try:
            data = self._client._request("stock_peers", {"symbol": symbol})
            if data and len(data) > 0:
                return CompanyPeer(
                    symbol=symbol,
                    peers=data[0].get("peersList", [])
                )
        except Exception as e:
            logger.debug(f"Failed to get peers for {symbol}: {e}")
        return None
    
    def get_company_executives(self, symbol: str) -> List[Executive]:
        """Get company executive information."""
        if not is_module_enabled(FMPModule.FUNDAMENTALS):
            return []
        
        try:
            data = self._client._request("key-executives", {"symbol": symbol})
            return [
                Executive(
                    name=e.get("name", ""),
                    title=e.get("title", ""),
                    pay=e.get("pay"),
                    currency=e.get("currencyPay", "USD"),
                    year_born=e.get("yearBorn"),
                )
                for e in (data or [])
            ]
        except Exception as e:
            logger.debug(f"Failed to get executives for {symbol}: {e}")
        return []
    
    # =========================================================================
    # Analyst Data
    # =========================================================================
    
    def get_analyst_estimates(
        self, 
        symbol: str, 
        period: str = "annual",
        limit: int = 4
    ) -> List[AnalystEstimate]:
        """Get analyst earnings/revenue estimates."""
        if not is_module_enabled(FMPModule.ANALYSTS):
            return []
        
        try:
            data = self._client._request(
                "analyst-estimates",
                {"symbol": symbol, "period": period, "limit": limit}
            )
            return [
                AnalystEstimate(
                    symbol=symbol,
                    date=e.get("date", ""),
                    estimated_revenue_avg=e.get("estimatedRevenueAvg"),
                    estimated_revenue_low=e.get("estimatedRevenueLow"),
                    estimated_revenue_high=e.get("estimatedRevenueHigh"),
                    number_analysts_estimated_revenue=e.get("numberAnalystsEstimatedRevenue", 0),
                    estimated_eps_avg=e.get("estimatedEpsAvg"),
                    estimated_eps_low=e.get("estimatedEpsLow"),
                    estimated_eps_high=e.get("estimatedEpsHigh"),
                    number_analysts_estimated_eps=e.get("numberAnalystsEstimatedEps", 0),
                )
                for e in (data or [])
            ]
        except Exception as e:
            logger.debug(f"Failed to get analyst estimates for {symbol}: {e}")
        return []
    
    def get_price_targets(self, symbol: str, limit: int = 10) -> List[PriceTarget]:
        """Get analyst price targets."""
        if not is_module_enabled(FMPModule.ANALYSTS):
            return []
        
        try:
            data = self._client._request(
                "price-target",
                {"symbol": symbol}
            )
            results = []
            for pt in (data or [])[:limit]:
                results.append(PriceTarget(
                    symbol=symbol,
                    published_date=pt.get("publishedDate", ""),
                    analyst_name=pt.get("analystName"),
                    analyst_company=pt.get("analystCompany"),
                    price_target=pt.get("priceTarget"),
                    price_when_posted=pt.get("priceWhenPosted"),
                    upside=pt.get("upside"),
                ))
            return results
        except Exception as e:
            logger.debug(f"Failed to get price targets for {symbol}: {e}")
        return []
    
    def get_price_target_consensus(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get consensus price target."""
        if not is_module_enabled(FMPModule.ANALYSTS):
            return None
        
        try:
            data = self._client._request("price-target-consensus", {"symbol": symbol})
            if data and len(data) > 0:
                return data[0]
        except Exception as e:
            logger.debug(f"Failed to get price target consensus for {symbol}: {e}")
        return None
    
    def get_stock_grades(self, symbol: str, limit: int = 10) -> List[StockGrade]:
        """Get stock upgrade/downgrade history."""
        if not is_module_enabled(FMPModule.ANALYSTS):
            return []
        
        try:
            data = self._client._request(
                "grade",
                {"symbol": symbol, "limit": limit}
            )
            return [
                StockGrade(
                    symbol=symbol,
                    published_date=g.get("date", ""),
                    grading_company=g.get("gradingCompany", ""),
                    previous_grade=g.get("previousGrade"),
                    new_grade=g.get("newGrade"),
                    action=g.get("action"),
                )
                for g in (data or [])
            ]
        except Exception as e:
            logger.debug(f"Failed to get stock grades for {symbol}: {e}")
        return []
    
    def get_analyst_recommendations(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get analyst recommendation summary (buy/hold/sell counts)."""
        if not is_module_enabled(FMPModule.ANALYSTS):
            return None
        
        try:
            data = self._client._request("analyst-stock-recommendations", {"symbol": symbol})
            if data and len(data) > 0:
                return data[0]
        except Exception as e:
            logger.debug(f"Failed to get analyst recommendations for {symbol}: {e}")
        return None
    
    # =========================================================================
    # Insider & Institutional Data
    # =========================================================================
    
    def get_insider_trades(self, symbol: str, limit: int = 50) -> List[InsiderTrade]:
        """Get insider trading activity."""
        if not is_module_enabled(FMPModule.INSIDER):
            return []
        
        try:
            data = self._client._request(
                "insider-trading",
                {"symbol": symbol, "limit": limit}
            )
            return [
                InsiderTrade(
                    symbol=symbol,
                    filing_date=t.get("filingDate", ""),
                    transaction_date=t.get("transactionDate"),
                    reporting_name=t.get("reportingName", ""),
                    transaction_type=t.get("transactionType", ""),
                    securities_owned=t.get("securitiesOwned"),
                    securities_transacted=t.get("securitiesTransacted"),
                    price=t.get("price"),
                    form_type=t.get("formType", "4"),
                )
                for t in (data or [])
            ]
        except Exception as e:
            logger.debug(f"Failed to get insider trades for {symbol}: {e}")
        return []
    
    def get_form_13f(
        self, 
        symbol: str = None,
        cik: str = None,
        date: str = None,
        limit: int = 100
    ) -> List[Form13F]:
        """
        Get 13F institutional holdings.
        
        Can query by symbol (who holds it) or by CIK (what an institution holds).
        """
        if not is_module_enabled(FMPModule.FILINGS):
            return []
        
        try:
            params = {"limit": limit}
            if symbol:
                params["symbol"] = symbol
            if cik:
                params["cik"] = cik
            if date:
                params["date"] = date
            
            data = self._client._request("form-thirteen", params)
            return [
                Form13F(
                    cik=f.get("cik", ""),
                    filing_date=f.get("fillingDate", ""),
                    investor_name=f.get("investorName", ""),
                    symbol=f.get("symbol", ""),
                    shares=int(f.get("shares", 0)),
                    value=float(f.get("value", 0)),
                    weight=f.get("weight"),
                    change=f.get("change"),
                )
                for f in (data or [])
            ]
        except Exception as e:
            logger.debug(f"Failed to get 13F data: {e}")
        return []
    
    def get_institutional_holders(self, symbol: str) -> List[Dict[str, Any]]:
        """Get institutional holders for a symbol."""
        if not is_module_enabled(FMPModule.FILINGS):
            return []
        
        try:
            data = self._client._request("institutional-holder", {"symbol": symbol})
            return data or []
        except Exception as e:
            logger.debug(f"Failed to get institutional holders for {symbol}: {e}")
        return []
    
    # =========================================================================
    # Market Calendars
    # =========================================================================
    
    def get_earnings_calendar(
        self,
        from_date: str = None,
        to_date: str = None
    ) -> List[EarningsEvent]:
        """Get earnings calendar."""
        if not is_module_enabled(FMPModule.CALENDAR):
            return []
        
        try:
            params = {}
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            
            data = self._client._request("earning_calendar", params)
            return [
                EarningsEvent(
                    symbol=e.get("symbol", ""),
                    date=e.get("date", ""),
                    eps_estimated=e.get("epsEstimated"),
                    eps_actual=e.get("eps"),
                    revenue_estimated=e.get("revenueEstimated"),
                    revenue_actual=e.get("revenue"),
                    time=e.get("time"),
                )
                for e in (data or [])
            ]
        except Exception as e:
            logger.debug(f"Failed to get earnings calendar: {e}")
        return []
    
    def get_dividend_calendar(
        self,
        from_date: str = None,
        to_date: str = None
    ) -> List[DividendEvent]:
        """Get dividend calendar."""
        if not is_module_enabled(FMPModule.CALENDAR):
            return []
        
        try:
            params = {}
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            
            data = self._client._request("stock_dividend_calendar", params)
            return [
                DividendEvent(
                    symbol=d.get("symbol", ""),
                    date=d.get("date", ""),
                    dividend=float(d.get("dividend", 0)),
                    adj_dividend=d.get("adjDividend"),
                    record_date=d.get("recordDate"),
                    payment_date=d.get("paymentDate"),
                    declaration_date=d.get("declarationDate"),
                )
                for d in (data or [])
            ]
        except Exception as e:
            logger.debug(f"Failed to get dividend calendar: {e}")
        return []
    
    def get_ipo_calendar(
        self,
        from_date: str = None,
        to_date: str = None
    ) -> List[Dict[str, Any]]:
        """Get IPO calendar."""
        if not is_module_enabled(FMPModule.CALENDAR):
            return []
        
        try:
            params = {}
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            
            data = self._client._request("ipo_calendar", params)
            return data or []
        except Exception as e:
            logger.debug(f"Failed to get IPO calendar: {e}")
        return []
    
    def get_economic_calendar(
        self,
        from_date: str = None,
        to_date: str = None
    ) -> List[Dict[str, Any]]:
        """Get economic events calendar."""
        if not is_module_enabled(FMPModule.CALENDAR):
            return []
        
        try:
            params = {}
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            
            data = self._client._request("economic_calendar", params)
            return data or []
        except Exception as e:
            logger.debug(f"Failed to get economic calendar: {e}")
        return []
    
    # =========================================================================
    # Macro/Economic Indicators
    # =========================================================================
    
    def get_economic_indicators(self, name: str = None) -> List[EconomicIndicator]:
        """Get economic indicators (GDP, CPI, unemployment, etc.)."""
        if not is_module_enabled(FMPModule.MACRO):
            return []
        
        try:
            endpoint = f"economic" if not name else f"economic/{name}"
            data = self._client._request(endpoint, {})
            return [
                EconomicIndicator(
                    name=i.get("name", name or ""),
                    date=i.get("date", ""),
                    value=float(i.get("value", 0)),
                    previous=i.get("previous"),
                    change=i.get("change"),
                    unit=i.get("unit"),
                )
                for i in (data or [])
            ]
        except Exception as e:
            logger.debug(f"Failed to get economic indicators: {e}")
        return []
    
    def get_treasury_rates(self) -> Dict[str, float]:
        """Get current US treasury rates."""
        if not is_module_enabled(FMPModule.MACRO):
            return {}
        
        try:
            data = self._client._request("treasury", {})
            if data and len(data) > 0:
                return data[0]
        except Exception as e:
            logger.debug(f"Failed to get treasury rates: {e}")
        return {}
    
    # =========================================================================
    # Market Performance
    # =========================================================================
    
    def get_sector_performance(self) -> List[SectorPerformance]:
        """Get sector performance."""
        if not is_module_enabled(FMPModule.MARKET):
            return []
        
        cache_key = "fmp_sector_performance"
        if cached := _cache_get(self._cache, cache_key):
            return [SectorPerformance(**s) for s in cached]
        
        try:
            data = self._client._request("sector-performance", {})
            results = [
                SectorPerformance(
                    sector=s.get("sector", ""),
                    change_percentage=float(s.get("changesPercentage", 0)),
                )
                for s in (data or [])
            ]
            _cache_set(self._cache, cache_key, [asdict(r) for r in results], 300)
            return results
        except Exception as e:
            logger.debug(f"Failed to get sector performance: {e}")
        return []
    
    def get_gainers(self, limit: int = 10) -> List[MarketMover]:
        """Get top gainers."""
        if not is_module_enabled(FMPModule.MARKET):
            return []
        
        try:
            data = self._client._request("stock_market/gainers", {})
            return [
                MarketMover(
                    symbol=s.get("symbol", ""),
                    name=s.get("name", ""),
                    change=float(s.get("change", 0)),
                    change_percentage=float(s.get("changesPercentage", 0)),
                    price=float(s.get("price", 0)),
                )
                for s in (data or [])[:limit]
            ]
        except Exception as e:
            logger.debug(f"Failed to get gainers: {e}")
        return []
    
    def get_losers(self, limit: int = 10) -> List[MarketMover]:
        """Get top losers."""
        if not is_module_enabled(FMPModule.MARKET):
            return []
        
        try:
            data = self._client._request("stock_market/losers", {})
            return [
                MarketMover(
                    symbol=s.get("symbol", ""),
                    name=s.get("name", ""),
                    change=float(s.get("change", 0)),
                    change_percentage=float(s.get("changesPercentage", 0)),
                    price=float(s.get("price", 0)),
                )
                for s in (data or [])[:limit]
            ]
        except Exception as e:
            logger.debug(f"Failed to get losers: {e}")
        return []
    
    def get_most_active(self, limit: int = 10) -> List[MarketMover]:
        """Get most actively traded stocks."""
        if not is_module_enabled(FMPModule.MARKET):
            return []
        
        try:
            data = self._client._request("stock_market/actives", {})
            return [
                MarketMover(
                    symbol=s.get("symbol", ""),
                    name=s.get("name", ""),
                    change=float(s.get("change", 0)),
                    change_percentage=float(s.get("changesPercentage", 0)),
                    price=float(s.get("price", 0)),
                )
                for s in (data or [])[:limit]
            ]
        except Exception as e:
            logger.debug(f"Failed to get most active: {e}")
        return []
    
    # =========================================================================
    # ETF Data
    # =========================================================================
    
    def get_etf_holdings(self, symbol: str) -> List[ETFHolding]:
        """Get ETF constituent holdings."""
        if not is_module_enabled(FMPModule.ETF):
            return []
        
        try:
            data = self._client._request("etf-holder", {"symbol": symbol})
            return [
                ETFHolding(
                    etf_symbol=symbol,
                    symbol=h.get("asset", ""),
                    name=h.get("name", ""),
                    weight=float(h.get("weightPercentage", 0)),
                    shares=h.get("sharesNumber"),
                )
                for h in (data or [])
            ]
        except Exception as e:
            logger.debug(f"Failed to get ETF holdings for {symbol}: {e}")
        return []
    
    # =========================================================================
    # Commodities, Forex, Crypto
    # =========================================================================
    
    def get_commodity_quotes(self) -> List[CommodityQuote]:
        """Get commodity quotes (gold, oil, etc.)."""
        if not is_module_enabled(FMPModule.COMMODITIES):
            return []
        
        try:
            data = self._client._request("quote/commodity", {})
            return [
                CommodityQuote(
                    symbol=c.get("symbol", ""),
                    name=c.get("name", ""),
                    price=float(c.get("price", 0)),
                    change=float(c.get("change", 0)),
                    change_percentage=float(c.get("changesPercentage", 0)),
                )
                for c in (data or [])
            ]
        except Exception as e:
            logger.debug(f"Failed to get commodity quotes: {e}")
        return []
    
    def get_forex_quotes(self) -> List[ForexQuote]:
        """Get forex quotes."""
        if not is_module_enabled(FMPModule.FOREX):
            return []
        
        try:
            data = self._client._request("fx", {})
            return [
                ForexQuote(
                    symbol=f.get("ticker", ""),
                    bid=float(f.get("bid", 0)),
                    ask=float(f.get("ask", 0)),
                    open=float(f.get("open", 0)),
                    high=float(f.get("high", 0)),
                    low=float(f.get("low", 0)),
                    change=float(f.get("changes", 0)),
                    change_percentage=float(f.get("changesPercentage", 0)),
                )
                for f in (data or [])
            ]
        except Exception as e:
            logger.debug(f"Failed to get forex quotes: {e}")
        return []
    
    def get_crypto_quotes(self, limit: int = 20) -> List[CryptoQuote]:
        """Get cryptocurrency quotes."""
        if not is_module_enabled(FMPModule.CRYPTO):
            return []
        
        try:
            data = self._client._request("quote/crypto", {})
            return [
                CryptoQuote(
                    symbol=c.get("symbol", ""),
                    name=c.get("name", ""),
                    price=float(c.get("price", 0)),
                    change=float(c.get("change", 0)),
                    change_percentage=float(c.get("changesPercentage", 0)),
                    market_cap=c.get("marketCap"),
                    volume=c.get("volume"),
                )
                for c in (data or [])[:limit]
            ]
        except Exception as e:
            logger.debug(f"Failed to get crypto quotes: {e}")
        return []
    
    # =========================================================================
    # ESG Data
    # =========================================================================
    
    def get_esg_score(self, symbol: str) -> Optional[ESGScore]:
        """Get ESG (Environmental, Social, Governance) score."""
        if not is_module_enabled(FMPModule.ESG):
            return None
        
        try:
            data = self._client._request("esg-environmental-social-governance-data", {"symbol": symbol})
            if data and len(data) > 0:
                e = data[0]
                return ESGScore(
                    symbol=symbol,
                    date=e.get("date", ""),
                    environment_score=e.get("environmentScore"),
                    social_score=e.get("socialScore"),
                    governance_score=e.get("governanceScore"),
                    esg_score=e.get("ESGScore"),
                    esg_rating=e.get("ESGRating"),
                )
        except Exception as e:
            logger.debug(f"Failed to get ESG score for {symbol}: {e}")
        return None


# =============================================================================
# Singleton Access
# =============================================================================

_fmp_gateway: Optional[FMPGateway] = None


def get_fmp_gateway() -> FMPGateway:
    """Get singleton FMP Gateway instance."""
    global _fmp_gateway
    if _fmp_gateway is None:
        _fmp_gateway = FMPGateway()
    return _fmp_gateway
