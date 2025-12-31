"""
Multi-Source Market Data Provider with Automatic Fallback

This module provides a unified interface to multiple free market data APIs,
with automatic fallback when primary sources fail or hit rate limits.

Supported Data Sources (Priority Order):
1. Financial Datasets API (Primary - if key configured)
2. Yahoo Finance (yfinance - free, unlimited, no key needed)
3. Polygon.io (5 calls/min free tier)
4. FMP - Financial Modeling Prep (250 calls/day free tier)
5. Finnhub (60 calls/min free tier)
6. Alpha Vantage (25 calls/day - last resort)

Data Types:
- Prices: yfinance (primary), Polygon, FMP
- Fundamentals: yfinance (primary), FMP
- News: Finnhub (primary), Tavily
- Insider Trading: FMP, SEC Direct
"""

import os
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd

logger = logging.getLogger(__name__)


class DataSource(Enum):
    """Available data sources"""
    ALPACA_DATA = "alpaca"  # Alpaca Market Data API (prices & news only)
    FINANCIAL_DATASETS = "financial_datasets"
    YFINANCE = "yfinance"
    POLYGON = "polygon"
    FMP = "fmp"
    FINNHUB = "finnhub"
    ALPHA_VANTAGE = "alpha_vantage"
    TAVILY = "tavily"


@dataclass
class DataSourceConfig:
    """Configuration for a data source"""
    name: str
    source: DataSource
    api_key_env: Optional[str]
    rate_limit_per_minute: Optional[int]
    rate_limit_per_day: Optional[int]
    requires_key: bool
    priority: int  # Lower = higher priority


# Data source configurations
DATA_SOURCES = {
    DataSource.ALPACA_DATA: DataSourceConfig(
        name="Alpaca Market Data",
        source=DataSource.ALPACA_DATA,
        api_key_env="ALPACA_API_KEY",
        rate_limit_per_minute=200,
        rate_limit_per_day=None,
        requires_key=True,
        priority=0,  # Highest priority when selected as primary
    ),
    DataSource.FINANCIAL_DATASETS: DataSourceConfig(
        name="Financial Datasets",
        source=DataSource.FINANCIAL_DATASETS,
        api_key_env="FINANCIAL_DATASETS_API_KEY",
        rate_limit_per_minute=10,
        rate_limit_per_day=None,
        requires_key=True,
        priority=1,
    ),
    DataSource.YFINANCE: DataSourceConfig(
        name="Yahoo Finance",
        source=DataSource.YFINANCE,
        api_key_env=None,
        rate_limit_per_minute=None,  # No hard limit but be nice
        rate_limit_per_day=None,
        requires_key=False,
        priority=2,
    ),
    DataSource.POLYGON: DataSourceConfig(
        name="Polygon.io",
        source=DataSource.POLYGON,
        api_key_env="POLYGON_API_KEY",
        rate_limit_per_minute=5,
        rate_limit_per_day=None,
        requires_key=True,
        priority=3,
    ),
    DataSource.FMP: DataSourceConfig(
        name="Financial Modeling Prep",
        source=DataSource.FMP,
        api_key_env="FMP_API_KEY",
        rate_limit_per_minute=None,
        rate_limit_per_day=250,
        requires_key=True,
        priority=4,
    ),
    DataSource.FINNHUB: DataSourceConfig(
        name="Finnhub",
        source=DataSource.FINNHUB,
        api_key_env="FINNHUB_API_KEY",
        rate_limit_per_minute=60,
        rate_limit_per_day=None,
        requires_key=True,
        priority=5,
    ),
    DataSource.ALPHA_VANTAGE: DataSourceConfig(
        name="Alpha Vantage",
        source=DataSource.ALPHA_VANTAGE,
        api_key_env="ALPHA_VANTAGE_API_KEY",
        rate_limit_per_minute=5,
        rate_limit_per_day=25,
        requires_key=True,
        priority=6,
    ),
}


class MultiSourceDataProvider:
    """
    Unified interface to multiple market data sources with automatic fallback.
    
    Features:
    - Automatic fallback when primary source fails
    - Rate limit tracking per source
    - Caching to minimize API calls
    - Logging of data source usage
    """
    
    def __init__(self):
        self._rate_limit_tracker: Dict[DataSource, Dict] = {}
        self._failed_sources: Dict[str, datetime] = {}  # Track failed sources
        self._failure_cooldown = timedelta(minutes=5)  # Wait before retrying failed source
        
        # Check which sources are available
        self._available_sources = self._check_available_sources()
        logger.info(f"Available data sources: {[s.value for s in self._available_sources]}")
    
    def _check_available_sources(self) -> List[DataSource]:
        """Check which data sources are available based on API keys."""
        available = []
        
        for source, config in DATA_SOURCES.items():
            if not config.requires_key:
                available.append(source)
                continue
            
            if config.api_key_env:
                key = os.environ.get(config.api_key_env, "")
                if key and "your-" not in key.lower():
                    available.append(source)
        
        # Sort by priority
        available.sort(key=lambda s: DATA_SOURCES[s].priority)
        return available
    
    def _is_source_available(self, source: DataSource) -> bool:
        """Check if a source is currently available (not rate limited or failed)."""
        if source not in self._available_sources:
            return False
        
        # Check if source recently failed
        fail_key = source.value
        if fail_key in self._failed_sources:
            if datetime.now() - self._failed_sources[fail_key] < self._failure_cooldown:
                return False
            else:
                # Cooldown expired, try again
                del self._failed_sources[fail_key]
        
        return True
    
    def _mark_source_failed(self, source: DataSource):
        """Mark a source as temporarily failed."""
        self._failed_sources[source.value] = datetime.now()
        logger.warning(f"Marked {source.value} as failed, will retry after cooldown")
    
    def _get_sources_for_data_type(self, data_type: str) -> List[DataSource]:
        """Get ordered list of sources that support a given data type."""
        # Check primary data source preference
        primary_source = os.environ.get("PRIMARY_DATA_SOURCE", "financial_datasets")
        
        # Define which sources support which data types
        # Note: ALPACA_DATA only supports prices and news, NOT fundamentals
        source_capabilities = {
            "prices": [
                DataSource.YFINANCE,
                DataSource.FINANCIAL_DATASETS,
                DataSource.POLYGON,
                DataSource.FMP,
                DataSource.ALPHA_VANTAGE,
                DataSource.ALPACA_DATA,  # Added
            ],
            "financials": [
                # Alpaca does NOT provide fundamentals
                DataSource.YFINANCE,
                DataSource.FINANCIAL_DATASETS,
                DataSource.FMP,
            ],
            "metrics": [
                # Alpaca does NOT provide metrics
                DataSource.YFINANCE,
                DataSource.FINANCIAL_DATASETS,
                DataSource.FMP,
            ],
            "news": [
                DataSource.FINNHUB,
                DataSource.FINANCIAL_DATASETS,
                DataSource.FMP,
                DataSource.ALPACA_DATA,  # Added
            ],
            "insider_trades": [
                # Alpaca does NOT provide insider trades
                DataSource.FINANCIAL_DATASETS,
                DataSource.FMP,
            ],
            "company_info": [
                DataSource.YFINANCE,
                DataSource.FINANCIAL_DATASETS,
                DataSource.FMP,
                DataSource.FINNHUB,
            ],
        }
        
        available_for_type = source_capabilities.get(data_type, [])
        available = [s for s in available_for_type if self._is_source_available(s)]
        
        # If PRIMARY_DATA_SOURCE is set to alpaca, move it to front for supported types
        if primary_source == "alpaca" and data_type in ["prices", "news"]:
            if DataSource.ALPACA_DATA in available:
                available.remove(DataSource.ALPACA_DATA)
                available.insert(0, DataSource.ALPACA_DATA)
        
        return available

    # ========================================================================
    # PRICE DATA
    # ========================================================================
    
    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> Tuple[pd.DataFrame, DataSource]:
        """
        Get historical price data with automatic fallback.
        
        Returns:
            Tuple of (DataFrame with OHLCV data, source used)
        """
        sources = self._get_sources_for_data_type("prices")
        
        for source in sources:
            try:
                logger.debug(f"Trying {source.value} for {ticker} prices")
                
                if source == DataSource.ALPACA_DATA:
                    df = self._get_prices_alpaca(ticker, start_date, end_date)
                elif source == DataSource.YFINANCE:
                    df = self._get_prices_yfinance(ticker, start_date, end_date)
                elif source == DataSource.FINANCIAL_DATASETS:
                    df = self._get_prices_financial_datasets(ticker, start_date, end_date)
                elif source == DataSource.POLYGON:
                    df = self._get_prices_polygon(ticker, start_date, end_date)
                elif source == DataSource.FMP:
                    df = self._get_prices_fmp(ticker, start_date, end_date)
                elif source == DataSource.ALPHA_VANTAGE:
                    df = self._get_prices_alpha_vantage(ticker, start_date, end_date)
                else:
                    continue
                
                if df is not None and not df.empty:
                    logger.info(f"Got {len(df)} price records for {ticker} from {source.value}")
                    return df, source
                    
            except Exception as e:
                logger.warning(f"Failed to get prices from {source.value}: {e}")
                self._mark_source_failed(source)
        
        logger.error(f"All sources failed for {ticker} prices")
        return pd.DataFrame(), DataSource.YFINANCE
    
    def _get_prices_alpaca(
        self, ticker: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Get prices from Alpaca Market Data API."""
        try:
            from src.tools.alpaca_data import get_alpaca_data_client
        except ImportError:
            logger.warning("alpaca_data module not available")
            return pd.DataFrame()
        
        client = get_alpaca_data_client()
        if not client.is_configured():
            return pd.DataFrame()
        
        return client.get_bars(ticker, start_date, end_date)
    
    def _get_prices_yfinance(
        self, ticker: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Get prices from Yahoo Finance (free, unlimited)."""
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed, run: pip install yfinance")
            return pd.DataFrame()
        
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date)
        
        if df.empty:
            return df
        
        # Normalize column names
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"date": "time"})
        
        return df
    
    def _get_prices_financial_datasets(
        self, ticker: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Get prices from Financial Datasets API."""
        from src.tools.api import get_prices, prices_to_df
        prices = get_prices(ticker, start_date, end_date)
        return prices_to_df(prices)
    
    def _get_prices_polygon(
        self, ticker: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Get prices from Polygon.io."""
        import requests
        
        api_key = os.environ.get("POLYGON_API_KEY")
        if not api_key:
            return pd.DataFrame()
        
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
        params = {"apiKey": api_key, "adjusted": "true", "sort": "asc"}
        
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            return pd.DataFrame()
        
        data = response.json()
        results = data.get("results", [])
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        df["time"] = pd.to_datetime(df["t"], unit="ms")
        df = df.rename(columns={
            "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"
        })
        
        return df[["time", "open", "high", "low", "close", "volume"]]
    
    def _get_prices_fmp(
        self, ticker: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Get prices from Financial Modeling Prep."""
        import requests
        
        api_key = os.environ.get("FMP_API_KEY")
        if not api_key:
            return pd.DataFrame()
        
        url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}"
        params = {"apikey": api_key, "from": start_date, "to": end_date}
        
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            return pd.DataFrame()
        
        data = response.json()
        historical = data.get("historical", [])
        
        if not historical:
            return pd.DataFrame()
        
        df = pd.DataFrame(historical)
        df["time"] = pd.to_datetime(df["date"])
        df = df.rename(columns={"adjClose": "close"})
        
        return df[["time", "open", "high", "low", "close", "volume"]].sort_values("time")
    
    def _get_prices_alpha_vantage(
        self, ticker: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Get prices from Alpha Vantage (25 calls/day limit)."""
        import requests
        
        api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            return pd.DataFrame()
        
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "apikey": api_key,
            "outputsize": "full",
        }
        
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            return pd.DataFrame()
        
        data = response.json()
        time_series = data.get("Time Series (Daily)", {})
        
        if not time_series:
            return pd.DataFrame()
        
        records = []
        for date_str, values in time_series.items():
            date = datetime.strptime(date_str, "%Y-%m-%d")
            if start_date <= date_str <= end_date:
                records.append({
                    "time": date,
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["5. adjusted close"]),
                    "volume": int(values["6. volume"]),
                })
        
        return pd.DataFrame(records).sort_values("time")

    # ========================================================================
    # FINANCIAL METRICS / FUNDAMENTALS
    # ========================================================================
    
    def get_fundamentals(
        self, ticker: str
    ) -> Tuple[Dict[str, Any], DataSource]:
        """
        Get financial fundamentals with automatic fallback.
        
        Returns company fundamentals including P/E, P/B, margins, etc.
        """
        sources = self._get_sources_for_data_type("financials")
        
        for source in sources:
            try:
                logger.debug(f"Trying {source.value} for {ticker} fundamentals")
                
                if source == DataSource.YFINANCE:
                    data = self._get_fundamentals_yfinance(ticker)
                elif source == DataSource.FINANCIAL_DATASETS:
                    data = self._get_fundamentals_financial_datasets(ticker)
                elif source == DataSource.FMP:
                    data = self._get_fundamentals_fmp(ticker)
                else:
                    continue
                
                if data:
                    logger.info(f"Got fundamentals for {ticker} from {source.value}")
                    return data, source
                    
            except Exception as e:
                logger.warning(f"Failed to get fundamentals from {source.value}: {e}")
                self._mark_source_failed(source)
        
        logger.error(f"All sources failed for {ticker} fundamentals")
        return {}, DataSource.YFINANCE
    
    def _get_fundamentals_yfinance(self, ticker: str) -> Dict[str, Any]:
        """Get fundamentals from Yahoo Finance."""
        try:
            import yfinance as yf
        except ImportError:
            return {}
        
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info:
            return {}
        
        return {
            "ticker": ticker,
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "peg_ratio": info.get("pegRatio"),
            "dividend_yield": info.get("dividendYield"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "gross_margin": info.get("grossMargins"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "beta": info.get("beta"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "float_shares": info.get("floatShares"),
            "short_ratio": info.get("shortRatio"),
            "short_percent": info.get("shortPercentOfFloat"),
            "source": "yfinance",
        }
    
    def _get_fundamentals_financial_datasets(self, ticker: str) -> Dict[str, Any]:
        """Get fundamentals from Financial Datasets API."""
        from src.tools.api import get_financial_metrics
        from datetime import datetime
        
        end_date = datetime.now().strftime("%Y-%m-%d")
        metrics = get_financial_metrics(ticker, end_date, limit=1)
        
        if not metrics:
            return {}
        
        m = metrics[0]
        return {
            "ticker": ticker,
            "pe_ratio": m.pe_ratio_ttm,
            "pb_ratio": m.price_to_book_ratio,
            "ps_ratio": m.price_to_sales_ratio_ttm,
            "profit_margin": m.net_margin,
            "operating_margin": m.operating_margin,
            "gross_margin": m.gross_margin,
            "roe": m.return_on_equity,
            "roa": m.return_on_assets,
            "debt_to_equity": m.debt_to_equity,
            "current_ratio": m.current_ratio,
            "revenue_growth": m.revenue_growth_yoy,
            "earnings_growth": m.earnings_growth_yoy,
            "market_cap": m.market_cap,
            "source": "financial_datasets",
        }
    
    def _get_fundamentals_fmp(self, ticker: str) -> Dict[str, Any]:
        """Get fundamentals from FMP."""
        import requests
        
        api_key = os.environ.get("FMP_API_KEY")
        if not api_key:
            return {}
        
        # Get key metrics
        url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{ticker}"
        params = {"apikey": api_key}
        
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            return {}
        
        data = response.json()
        if not data:
            return {}
        
        m = data[0]
        return {
            "ticker": ticker,
            "pe_ratio": m.get("peRatioTTM"),
            "pb_ratio": m.get("priceToBookRatioTTM"),
            "ps_ratio": m.get("priceToSalesRatioTTM"),
            "dividend_yield": m.get("dividendYieldTTM"),
            "roe": m.get("roeTTM"),
            "roa": m.get("roaTTM"),
            "debt_to_equity": m.get("debtToEquityTTM"),
            "current_ratio": m.get("currentRatioTTM"),
            "market_cap": m.get("marketCapTTM"),
            "enterprise_value": m.get("enterpriseValueTTM"),
            "source": "fmp",
        }

    # ========================================================================
    # NEWS DATA
    # ========================================================================
    
    def get_news(
        self,
        ticker: str,
        limit: int = 20,
    ) -> Tuple[List[Dict], DataSource]:
        """Get news articles for a ticker with automatic fallback."""
        sources = self._get_sources_for_data_type("news")
        
        for source in sources:
            try:
                if source == DataSource.ALPACA_DATA:
                    news = self._get_news_alpaca(ticker, limit)
                elif source == DataSource.FINNHUB:
                    news = self._get_news_finnhub(ticker, limit)
                elif source == DataSource.FINANCIAL_DATASETS:
                    news = self._get_news_financial_datasets(ticker, limit)
                elif source == DataSource.FMP:
                    news = self._get_news_fmp(ticker, limit)
                else:
                    continue
                
                if news:
                    logger.info(f"Got {len(news)} news articles for {ticker} from {source.value}")
                    return news, source
                    
            except Exception as e:
                logger.warning(f"Failed to get news from {source.value}: {e}")
                self._mark_source_failed(source)
        
        return [], DataSource.FINNHUB
    
    def _get_news_alpaca(self, ticker: str, limit: int) -> List[Dict]:
        """Get news from Alpaca Market Data API."""
        try:
            from src.tools.alpaca_data import get_alpaca_data_client
        except ImportError:
            logger.warning("alpaca_data module not available")
            return []
        
        client = get_alpaca_data_client()
        if not client.is_configured():
            return []
        
        return client.get_news_for_ticker(ticker, limit=limit)
    
    def _get_news_finnhub(self, ticker: str, limit: int) -> List[Dict]:
        """Get news from Finnhub (60 calls/min free)."""
        import requests
        
        api_key = os.environ.get("FINNHUB_API_KEY")
        if not api_key:
            return []
        
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        
        url = "https://finnhub.io/api/v1/company-news"
        params = {
            "symbol": ticker,
            "from": week_ago.strftime("%Y-%m-%d"),
            "to": today.strftime("%Y-%m-%d"),
            "token": api_key,
        }
        
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            return []
        
        articles = response.json()[:limit]
        
        return [
            {
                "title": a.get("headline"),
                "summary": a.get("summary"),
                "source": a.get("source"),
                "url": a.get("url"),
                "date": datetime.fromtimestamp(a.get("datetime", 0)).isoformat(),
                "sentiment": a.get("sentiment"),
            }
            for a in articles
        ]
    
    def _get_news_financial_datasets(self, ticker: str, limit: int) -> List[Dict]:
        """Get news from Financial Datasets."""
        from src.tools.api import get_company_news
        
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        news = get_company_news(ticker, start_date, end_date, limit=limit)
        
        return [
            {
                "title": n.title,
                "summary": n.description,
                "source": n.source,
                "url": n.url,
                "date": n.date,
            }
            for n in news
        ]
    
    def _get_news_fmp(self, ticker: str, limit: int) -> List[Dict]:
        """Get news from FMP."""
        import requests
        
        api_key = os.environ.get("FMP_API_KEY")
        if not api_key:
            return []
        
        url = f"https://financialmodelingprep.com/api/v3/stock_news"
        params = {"tickers": ticker, "limit": limit, "apikey": api_key}
        
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            return []
        
        articles = response.json()
        
        return [
            {
                "title": a.get("title"),
                "summary": a.get("text"),
                "source": a.get("site"),
                "url": a.get("url"),
                "date": a.get("publishedDate"),
                "symbol": a.get("symbol"),
            }
            for a in articles
        ]


# Global instance
_data_provider: Optional[MultiSourceDataProvider] = None


def get_data_provider() -> MultiSourceDataProvider:
    """Get or create the global data provider instance."""
    global _data_provider
    if _data_provider is None:
        _data_provider = MultiSourceDataProvider()
    return _data_provider


def get_available_data_sources() -> Dict[str, bool]:
    """Get status of all configured data sources."""
    provider = get_data_provider()
    
    result = {}
    for source, config in DATA_SOURCES.items():
        is_available = source in provider._available_sources
        result[config.name] = {
            "available": is_available,
            "requires_key": config.requires_key,
            "api_key_env": config.api_key_env,
            "rate_limit_per_minute": config.rate_limit_per_minute,
            "rate_limit_per_day": config.rate_limit_per_day,
        }
    
    return result
