"""
FMP (Financial Modeling Prep) Data Client

Comprehensive financial data provider supporting:
- Historical and intraday prices
- Financial statements (income, balance sheet, cash flow)
- Key metrics and ratios
- Company profiles and fundamentals
- News and press releases
- Insider trades
- Analyst estimates and ratings
- Earnings transcripts
- ETF/Mutual fund holdings

This is the primary data source when PRIMARY_DATA_SOURCE=fmp.
Alpaca and Yahoo Finance serve as fallbacks.

API Documentation: https://site.financialmodelingprep.com/developer/docs
"""

import os
import time
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

from src.data.cache import get_cache

load_dotenv()

logger = logging.getLogger(__name__)

# Lazy import for monitoring to avoid circular imports
_rate_limit_monitor = None


def _get_rate_limit_monitor():
    """Lazy load the rate limit monitor."""
    global _rate_limit_monitor
    if _rate_limit_monitor is None:
        try:
            from src.monitoring import get_rate_limit_monitor
            _rate_limit_monitor = get_rate_limit_monitor()
        except Exception:
            pass
    return _rate_limit_monitor


# FMP API Base URL
FMP_BASE_URL = "https://financialmodelingprep.com/stable"


@dataclass
class FMPQuote:
    """Real-time quote from FMP"""
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: int
    avg_volume: Optional[int] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    previous_close: Optional[float] = None


@dataclass
class FMPNews:
    """News article from FMP"""
    title: str
    text: str
    url: str
    site: str
    published_date: datetime
    symbol: Optional[str] = None


class FMPDataClient:
    """
    Client for FMP (Financial Modeling Prep) API.
    
    Provides comprehensive financial data including prices,
    fundamentals, news, and analytics.
    
    Usage:
        client = get_fmp_data_client()
        prices = client.get_historical_prices("AAPL", "2024-01-01", "2024-01-15")
        metrics = client.get_key_metrics("AAPL")
        news = client.get_stock_news("AAPL", limit=10)
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize FMP client.
        
        Args:
            api_key: FMP API key (defaults to env var)
        """
        self.api_key = api_key or os.environ.get("FMP_API_KEY")
        self._cache = get_cache()
        
        if not self.api_key:
            logger.warning(
                "FMP API key not found. Set FMP_API_KEY environment variable."
            )
    
    def is_configured(self) -> bool:
        """Check if FMP credentials are configured."""
        return bool(self.api_key and self.api_key != "your-fmp-api-key")
    
    def _request(
        self,
        endpoint: str,
        params: Dict = None,
        method: str = "GET",
    ) -> Any:
        """
        Make API request with monitoring.
        
        Args:
            endpoint: API endpoint path (without base URL)
            params: Query parameters
            method: HTTP method
        """
        if not self.is_configured():
            raise ValueError("FMP API key not configured")
        
        url = f"{FMP_BASE_URL}/{endpoint}"
        
        # Add API key to params
        if params is None:
            params = {}
        params["apikey"] = self.api_key
        
        # Determine call type from endpoint for telemetry
        call_type = self._get_call_type(endpoint)
        
        rate_monitor = _get_rate_limit_monitor()
        start_time = time.time()
        
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                timeout=30,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code == 429:
                if rate_monitor:
                    retry_after = response.headers.get("Retry-After")
                    rate_monitor.record_rate_limit_hit(
                        "fmp_data",
                        retry_after=int(retry_after) if retry_after else None
                    )
                raise Exception("FMP API rate limited (429)")
            
            if response.status_code == 401:
                raise Exception("FMP API key invalid or expired (401)")
            
            if response.status_code == 403:
                raise Exception("FMP API access denied - check subscription plan (403)")
            
            if response.status_code >= 400:
                error_msg = response.text[:200]
                if rate_monitor:
                    rate_monitor.record_call(
                        "fmp_data",
                        call_type=call_type,
                        success=False,
                        latency_ms=latency_ms,
                    )
                raise Exception(f"FMP API error ({response.status_code}): {error_msg}")
            
            # Log successful call
            if rate_monitor:
                remaining = response.headers.get("X-RateLimit-Remaining")
                rate_monitor.record_call(
                    "fmp_data",
                    call_type=call_type,
                    success=True,
                    rate_limit_remaining=int(remaining) if remaining else None,
                    latency_ms=latency_ms,
                )
            
            return response.json()
            
        except requests.exceptions.Timeout:
            latency_ms = int((time.time() - start_time) * 1000)
            if rate_monitor:
                rate_monitor.record_call("fmp_data", call_type=call_type, success=False, latency_ms=latency_ms)
            raise Exception("FMP API timeout")
        except requests.exceptions.RequestException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            if rate_monitor:
                rate_monitor.record_call("fmp_data", call_type=call_type, success=False, latency_ms=latency_ms)
            raise
    
    def _get_call_type(self, endpoint: str) -> str:
        """Map endpoint to call type for telemetry."""
        endpoint_lower = endpoint.lower()
        if "quote" in endpoint_lower:
            return "quote"
        elif "price" in endpoint_lower or "historical" in endpoint_lower:
            return "prices"
        elif "income" in endpoint_lower or "balance" in endpoint_lower or "cash" in endpoint_lower:
            return "financials"
        elif "ratio" in endpoint_lower or "metric" in endpoint_lower:
            return "metrics"
        elif "profile" in endpoint_lower:
            return "profile"
        elif "news" in endpoint_lower:
            return "news"
        elif "insider" in endpoint_lower:
            return "insider"
        elif "analyst" in endpoint_lower or "estimate" in endpoint_lower:
            return "analyst"
        elif "transcript" in endpoint_lower or "earnings" in endpoint_lower:
            return "earnings"
        elif "screener" in endpoint_lower or "stock-list" in endpoint_lower:
            return "screener"
        else:
            return "general"

    # ==================== Price Data ====================
    
    def get_quote(self, symbol: str) -> Optional[FMPQuote]:
        """Get real-time quote for a symbol."""
        if not self.is_configured():
            return None
        
        try:
            data = self._request("quote", {"symbol": symbol})
            if data and len(data) > 0:
                q = data[0]
                return FMPQuote(
                    symbol=q.get("symbol", symbol),
                    price=float(q.get("price", 0)),
                    change=float(q.get("change", 0)),
                    change_percent=float(q.get("changesPercentage", 0)),
                    volume=int(q.get("volume", 0)),
                    avg_volume=q.get("avgVolume"),
                    market_cap=q.get("marketCap"),
                    pe_ratio=q.get("pe"),
                    eps=q.get("eps"),
                    high=q.get("dayHigh"),
                    low=q.get("dayLow"),
                    open=q.get("open"),
                    previous_close=q.get("previousClose"),
                )
        except Exception as e:
            logger.error(f"Failed to get FMP quote for {symbol}: {e}")
        return None
    
    def get_historical_prices(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Get historical EOD price data.
        
        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame with time, open, high, low, close, volume
        """
        if not self.is_configured():
            return pd.DataFrame()
        
        # Check cache
        cache_key = f"fmp_{symbol}_{start_date}_{end_date}"
        if cached := self._cache.get_prices(cache_key):
            logger.debug(f"Cache hit for FMP prices: {symbol}")
            return pd.DataFrame(cached)
        
        try:
            data = self._request(
                f"historical-price-eod/full",
                {"symbol": symbol, "from": start_date, "to": end_date}
            )
            
            historical = data.get("historical", []) if isinstance(data, dict) else data
            
            if not historical:
                return pd.DataFrame()
            
            records = []
            for bar in historical:
                records.append({
                    "time": pd.to_datetime(bar.get("date")),
                    "open": float(bar.get("open", 0)),
                    "high": float(bar.get("high", 0)),
                    "low": float(bar.get("low", 0)),
                    "close": float(bar.get("adjClose", bar.get("close", 0))),
                    "volume": int(bar.get("volume", 0)),
                })
            
            df = pd.DataFrame(records)
            df = df.sort_values("time").reset_index(drop=True)
            
            # Cache results
            self._cache.set_prices(cache_key, df.to_dict("records"))
            
            logger.info(f"Got {len(df)} FMP prices for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to get FMP prices for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_intraday_prices(
        self,
        symbol: str,
        interval: str = "1hour",
        from_date: str = None,
        to_date: str = None,
    ) -> pd.DataFrame:
        """
        Get intraday price data.
        
        Args:
            symbol: Stock symbol
            interval: 1min, 5min, 15min, 30min, 1hour, 4hour
            from_date: Start datetime
            to_date: End datetime
        """
        if not self.is_configured():
            return pd.DataFrame()
        
        try:
            params = {"symbol": symbol}
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            
            data = self._request(f"historical-chart/{interval}", params)
            
            if not data:
                return pd.DataFrame()
            
            records = []
            for bar in data:
                records.append({
                    "time": pd.to_datetime(bar.get("date")),
                    "open": float(bar.get("open", 0)),
                    "high": float(bar.get("high", 0)),
                    "low": float(bar.get("low", 0)),
                    "close": float(bar.get("close", 0)),
                    "volume": int(bar.get("volume", 0)),
                })
            
            df = pd.DataFrame(records)
            return df.sort_values("time").reset_index(drop=True)
            
        except Exception as e:
            logger.error(f"Failed to get FMP intraday for {symbol}: {e}")
            return pd.DataFrame()

    # ==================== Fundamentals ====================
    
    def get_company_profile(self, symbol: str) -> Optional[Dict]:
        """Get company profile data."""
        if not self.is_configured():
            return None
        
        try:
            data = self._request("profile", {"symbol": symbol})
            if data and len(data) > 0:
                return data[0]
        except Exception as e:
            logger.error(f"Failed to get FMP profile for {symbol}: {e}")
        return None
    
    def get_key_metrics(self, symbol: str, period: str = "annual", limit: int = 10) -> List[Dict]:
        """Get key financial metrics."""
        if not self.is_configured():
            return []
        
        try:
            data = self._request(
                "key-metrics",
                {"symbol": symbol, "period": period, "limit": limit}
            )
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP key metrics for {symbol}: {e}")
            return []
    
    def get_key_metrics_ttm(self, symbol: str) -> Optional[Dict]:
        """Get trailing twelve month key metrics."""
        if not self.is_configured():
            return None
        
        try:
            data = self._request("key-metrics-ttm", {"symbol": symbol})
            if data and len(data) > 0:
                return data[0]
        except Exception as e:
            logger.error(f"Failed to get FMP TTM metrics for {symbol}: {e}")
        return None
    
    def get_ratios_ttm(self, symbol: str) -> Optional[Dict]:
        """Get trailing twelve month financial ratios."""
        if not self.is_configured():
            return None
        
        try:
            data = self._request("ratios-ttm", {"symbol": symbol})
            if data and len(data) > 0:
                return data[0]
        except Exception as e:
            logger.error(f"Failed to get FMP TTM ratios for {symbol}: {e}")
        return None
    
    def get_income_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> List[Dict]:
        """Get income statements."""
        if not self.is_configured():
            return []
        
        try:
            data = self._request(
                "income-statement",
                {"symbol": symbol, "period": period, "limit": limit}
            )
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP income statement for {symbol}: {e}")
            return []
    
    def get_balance_sheet(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> List[Dict]:
        """Get balance sheet statements."""
        if not self.is_configured():
            return []
        
        try:
            data = self._request(
                "balance-sheet-statement",
                {"symbol": symbol, "period": period, "limit": limit}
            )
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP balance sheet for {symbol}: {e}")
            return []
    
    def get_cash_flow_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> List[Dict]:
        """Get cash flow statements."""
        if not self.is_configured():
            return []
        
        try:
            data = self._request(
                "cash-flow-statement",
                {"symbol": symbol, "period": period, "limit": limit}
            )
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP cash flow for {symbol}: {e}")
            return []
    
    def get_financial_scores(self, symbol: str) -> Optional[Dict]:
        """Get financial health scores (Altman Z-Score, Piotroski Score, etc.)."""
        if not self.is_configured():
            return None
        
        try:
            data = self._request("financial-scores", {"symbol": symbol})
            if data and len(data) > 0:
                return data[0]
        except Exception as e:
            logger.error(f"Failed to get FMP financial scores for {symbol}: {e}")
        return None

    # ==================== News ====================
    
    def get_stock_news(
        self,
        symbols: List[str] = None,
        limit: int = 20,
    ) -> List[FMPNews]:
        """Get stock news articles."""
        if not self.is_configured():
            return []
        
        try:
            params = {"limit": limit}
            if symbols:
                params["symbols"] = ",".join(symbols)
            
            data = self._request("news/stock", params)
            
            articles = []
            for item in (data or []):
                articles.append(FMPNews(
                    title=item.get("title", ""),
                    text=item.get("text", ""),
                    url=item.get("url", ""),
                    site=item.get("site", ""),
                    published_date=pd.to_datetime(item.get("publishedDate")),
                    symbol=item.get("symbol"),
                ))
            
            logger.info(f"Got {len(articles)} FMP news articles")
            return articles
            
        except Exception as e:
            logger.error(f"Failed to get FMP news: {e}")
            return []
    
    def get_news_for_ticker(self, ticker: str, limit: int = 20) -> List[Dict]:
        """
        Get news for a specific ticker in standard dict format.
        
        Returns data compatible with other news providers.
        """
        articles = self.get_stock_news(symbols=[ticker], limit=limit)
        
        return [
            {
                "title": a.title,
                "summary": a.text[:500] if a.text else "",
                "source": a.site,
                "url": a.url,
                "date": a.published_date.isoformat() if a.published_date else None,
            }
            for a in articles
        ]
    
    def get_press_releases(self, symbol: str, limit: int = 20) -> List[Dict]:
        """Get company press releases."""
        if not self.is_configured():
            return []
        
        try:
            data = self._request(
                "news/press-releases",
                {"symbols": symbol, "limit": limit}
            )
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP press releases for {symbol}: {e}")
            return []

    # ==================== Insider Trading ====================
    
    def get_insider_trades(
        self,
        symbol: str = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Get insider trading activity."""
        if not self.is_configured():
            return []
        
        try:
            params = {"limit": limit}
            if symbol:
                params["symbol"] = symbol
            
            data = self._request("insider-trading/search", params)
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP insider trades: {e}")
            return []

    # ==================== Analyst Data ====================
    
    def get_analyst_estimates(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 10,
    ) -> List[Dict]:
        """Get analyst estimates."""
        if not self.is_configured():
            return []
        
        try:
            data = self._request(
                "analyst-estimates",
                {"symbol": symbol, "period": period, "limit": limit}
            )
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP analyst estimates for {symbol}: {e}")
            return []
    
    def get_price_target_consensus(self, symbol: str) -> Optional[Dict]:
        """Get analyst price target consensus."""
        if not self.is_configured():
            return None
        
        try:
            data = self._request("price-target-consensus", {"symbol": symbol})
            if data and len(data) > 0:
                return data[0]
        except Exception as e:
            logger.error(f"Failed to get FMP price targets for {symbol}: {e}")
        return None
    
    def get_stock_grades(self, symbol: str, limit: int = 20) -> List[Dict]:
        """Get analyst stock grades/ratings."""
        if not self.is_configured():
            return []
        
        try:
            data = self._request("grades", {"symbol": symbol, "limit": limit})
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP grades for {symbol}: {e}")
            return []

    # ==================== Earnings ====================
    
    def get_earnings(self, symbol: str, limit: int = 10) -> List[Dict]:
        """Get earnings history and estimates."""
        if not self.is_configured():
            return []
        
        try:
            data = self._request("earnings", {"symbol": symbol, "limit": limit})
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP earnings for {symbol}: {e}")
            return []
    
    def get_earnings_calendar(
        self,
        from_date: str = None,
        to_date: str = None,
    ) -> List[Dict]:
        """Get upcoming earnings calendar."""
        if not self.is_configured():
            return []
        
        try:
            params = {}
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            
            data = self._request("earnings-calendar", params)
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP earnings calendar: {e}")
            return []

    # ==================== Market Data ====================
    
    def get_market_cap(self, symbol: str) -> Optional[float]:
        """Get current market cap."""
        profile = self.get_company_profile(symbol)
        if profile:
            return profile.get("mktCap")
        return None
    
    def get_sector_performance(self) -> List[Dict]:
        """Get sector performance snapshot."""
        if not self.is_configured():
            return []
        
        try:
            data = self._request("sector-performance-snapshot", {"date": datetime.now().strftime("%Y-%m-%d")})
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP sector performance: {e}")
            return []
    
    def get_gainers(self) -> List[Dict]:
        """Get biggest gainers."""
        if not self.is_configured():
            return []
        
        try:
            data = self._request("biggest-gainers")
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP gainers: {e}")
            return []
    
    def get_losers(self) -> List[Dict]:
        """Get biggest losers."""
        if not self.is_configured():
            return []
        
        try:
            data = self._request("biggest-losers")
            return data if data else []
        except Exception as e:
            logger.error(f"Failed to get FMP losers: {e}")
            return []


# Global client instance
_fmp_data_client: Optional[FMPDataClient] = None


def get_fmp_data_client() -> FMPDataClient:
    """Get or create the global FMP data client."""
    global _fmp_data_client
    if _fmp_data_client is None:
        _fmp_data_client = FMPDataClient()
    return _fmp_data_client


def fmp_data_available() -> bool:
    """Check if FMP data is available (configured)."""
    client = get_fmp_data_client()
    return client.is_configured()


# Convenience functions for use by data_providers.py

def get_fmp_prices(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Get prices from FMP (convenience function)."""
    client = get_fmp_data_client()
    return client.get_historical_prices(ticker, start_date, end_date)


def get_fmp_news(ticker: str, limit: int = 20) -> List[Dict]:
    """Get news from FMP (convenience function)."""
    client = get_fmp_data_client()
    return client.get_news_for_ticker(ticker, limit=limit)


def get_fmp_fundamentals(ticker: str) -> Dict[str, Any]:
    """Get comprehensive fundamentals from FMP."""
    client = get_fmp_data_client()
    
    profile = client.get_company_profile(ticker) or {}
    metrics = client.get_key_metrics_ttm(ticker) or {}
    ratios = client.get_ratios_ttm(ticker) or {}
    
    return {
        "ticker": ticker,
        "pe_ratio": profile.get("pe") or metrics.get("peRatioTTM"),
        "forward_pe": metrics.get("forwardPERatioTTM"),
        "pb_ratio": metrics.get("pbRatioTTM") or ratios.get("priceToBookRatioTTM"),
        "ps_ratio": metrics.get("priceToSalesRatioTTM") or ratios.get("priceToSalesRatioTTM"),
        "peg_ratio": metrics.get("pegRatioTTM"),
        "dividend_yield": metrics.get("dividendYieldTTM") or ratios.get("dividendYielTTM"),
        "profit_margin": ratios.get("netProfitMarginTTM"),
        "operating_margin": ratios.get("operatingProfitMarginTTM"),
        "gross_margin": ratios.get("grossProfitMarginTTM"),
        "roe": metrics.get("roeTTM") or ratios.get("returnOnEquityTTM"),
        "roa": metrics.get("roaTTM") or ratios.get("returnOnAssetsTTM"),
        "debt_to_equity": metrics.get("debtToEquityTTM") or ratios.get("debtEquityRatioTTM"),
        "current_ratio": metrics.get("currentRatioTTM") or ratios.get("currentRatioTTM"),
        "quick_ratio": ratios.get("quickRatioTTM"),
        "revenue": metrics.get("revenuePerShareTTM"),
        "revenue_growth": metrics.get("revenueGrowthTTM"),
        "earnings_growth": metrics.get("netIncomeGrowthTTM"),
        "market_cap": profile.get("mktCap") or metrics.get("marketCapTTM"),
        "enterprise_value": metrics.get("enterpriseValueTTM"),
        "beta": profile.get("beta"),
        "52_week_high": profile.get("range", "").split("-")[1].strip() if profile.get("range") else None,
        "52_week_low": profile.get("range", "").split("-")[0].strip() if profile.get("range") else None,
        "avg_volume": profile.get("volAvg"),
        "shares_outstanding": profile.get("sharesOutstanding"),
        "source": "fmp",
    }


if __name__ == "__main__":
    # Test the client
    import json
    
    client = FMPDataClient()
    
    print("=" * 60)
    print("FMP DATA CLIENT TEST")
    print("=" * 60)
    
    if not client.is_configured():
        print("\n⚠️ FMP not configured. Set FMP_API_KEY")
    else:
        print("\n✓ FMP configured")
        
        # Test quote
        print("\n--- Testing Quote ---")
        quote = client.get_quote("AAPL")
        if quote:
            print(f"AAPL: ${quote.price:.2f} ({quote.change_percent:+.2f}%)")
        
        # Test historical prices
        print("\n--- Testing Historical Prices ---")
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        prices = client.get_historical_prices("AAPL", start, end)
        print(f"Got {len(prices)} price records")
        
        # Test key metrics
        print("\n--- Testing Key Metrics TTM ---")
        metrics = client.get_key_metrics_ttm("AAPL")
        if metrics:
            print(f"P/E: {metrics.get('peRatioTTM')}")
            print(f"ROE: {metrics.get('roeTTM')}")
        
        # Test news
        print("\n--- Testing News ---")
        news = client.get_stock_news(symbols=["AAPL"], limit=3)
        for article in news[:2]:
            print(f"  - {article.title[:60]}... ({article.site})")
        
        # Test insider trades
        print("\n--- Testing Insider Trades ---")
        insiders = client.get_insider_trades(symbol="AAPL", limit=3)
        print(f"Got {len(insiders)} insider trades")
    
    print("\n" + "=" * 60)
