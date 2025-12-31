"""
Alpaca Market Data Client

Provides access to Alpaca's Market Data API v2 for:
- Historical price bars (OHLCV)
- Real-time snapshots and quotes
- Company news articles

This uses the same API credentials as the trading API but connects
to the data.alpaca.markets endpoint instead of paper-api/api.

Note: Alpaca does NOT provide fundamental data (financial statements,
metrics, insider trades). For fundamentals, use Yahoo Finance or FMP.
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


@dataclass
class AlpacaBar:
    """Single price bar from Alpaca"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    trade_count: Optional[int] = None
    vwap: Optional[float] = None


@dataclass
class AlpacaSnapshot:
    """Latest market snapshot for a symbol"""
    symbol: str
    latest_trade_price: Optional[float] = None
    latest_trade_timestamp: Optional[datetime] = None
    latest_quote_bid: Optional[float] = None
    latest_quote_ask: Optional[float] = None
    minute_bar: Optional[AlpacaBar] = None
    daily_bar: Optional[AlpacaBar] = None
    prev_daily_bar: Optional[AlpacaBar] = None


@dataclass
class AlpacaNews:
    """News article from Alpaca"""
    id: str
    headline: str
    summary: str
    author: Optional[str]
    source: str
    url: str
    symbols: List[str]
    created_at: datetime
    updated_at: Optional[datetime] = None


class AlpacaDataClient:
    """
    Client for Alpaca Market Data API v2.
    
    Uses the same credentials as trading API but different base URL.
    Provides prices and news (NOT fundamentals).
    
    Usage:
        client = get_alpaca_data_client()
        bars = client.get_bars("AAPL", "2024-01-01", "2024-01-15")
        snapshot = client.get_snapshot("AAPL")
        news = client.get_news(["AAPL", "MSFT"], limit=10)
    """
    
    # Alpaca Market Data API base URL (different from trading API)
    BASE_URL = "https://data.alpaca.markets"
    
    def __init__(
        self,
        api_key: str = None,
        secret_key: str = None,
    ):
        """
        Initialize Alpaca data client.
        
        Args:
            api_key: Alpaca API key (defaults to env var)
            secret_key: Alpaca secret key (defaults to env var)
        """
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")
        self._cache = get_cache()
        
        if not self.api_key or not self.secret_key:
            logger.warning(
                "Alpaca API credentials not found. "
                "Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables."
            )
    
    def is_configured(self) -> bool:
        """Check if Alpaca credentials are configured."""
        return bool(self.api_key and self.secret_key)
    
    def _headers(self) -> Dict[str, str]:
        """Get API headers."""
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json",
        }
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        version: str = "v2",
    ) -> Dict:
        """
        Make API request with monitoring.
        
        Args:
            method: HTTP method
            endpoint: API endpoint path
            params: Query parameters
            version: API version (v2 for stocks, v1beta1 for news)
        """
        url = f"{self.BASE_URL}/{version}/{endpoint}"
        rate_monitor = _get_rate_limit_monitor()
        
        start_time = time.time()
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                params=params,
                timeout=30,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code == 429:
                # Rate limited
                if rate_monitor:
                    retry_after = response.headers.get("Retry-After")
                    rate_monitor.record_rate_limit_hit(
                        "alpaca_data",
                        retry_after=int(retry_after) if retry_after else None
                    )
                raise Exception("Alpaca Data API rate limited (429)")
            
            if response.status_code == 403:
                # Subscription/permission error
                raise Exception(
                    "Alpaca Data API access denied (403). "
                    "Check your subscription plan - free tier only includes IEX data."
                )
            
            if response.status_code >= 400:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", response.text)
                except (ValueError, KeyError):
                    pass
                
                if rate_monitor:
                    rate_monitor.record_call(
                        "alpaca_data",
                        success=False,
                        latency_ms=latency_ms,
                    )
                raise Exception(f"Alpaca Data API error ({response.status_code}): {error_msg}")
            
            # Log successful call
            if rate_monitor:
                remaining = response.headers.get("X-RateLimit-Remaining")
                rate_monitor.record_call(
                    "alpaca_data",
                    success=True,
                    rate_limit_remaining=int(remaining) if remaining else None,
                    latency_ms=latency_ms,
                )
            
            if response.text:
                return response.json()
            return {}
            
        except requests.exceptions.Timeout:
            latency_ms = int((time.time() - start_time) * 1000)
            if rate_monitor:
                rate_monitor.record_call(
                    "alpaca_data",
                    success=False,
                    latency_ms=latency_ms,
                )
            raise Exception("Alpaca Data API timeout")
        except requests.exceptions.RequestException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            if rate_monitor:
                rate_monitor.record_call(
                    "alpaca_data",
                    success=False,
                    latency_ms=latency_ms,
                )
            raise
    
    # ==================== Price Data ====================
    
    def get_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = "1Day",
        limit: int = 10000,
    ) -> pd.DataFrame:
        """
        Get historical price bars for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            timeframe: Bar timeframe (1Min, 5Min, 15Min, 1Hour, 1Day)
            limit: Maximum bars to return
            
        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        if not self.is_configured():
            logger.warning("Alpaca not configured, returning empty DataFrame")
            return pd.DataFrame()
        
        # Check cache first
        cache_key = f"alpaca_{symbol}_{start_date}_{end_date}_{timeframe}"
        if cached := self._cache.get_prices(cache_key):
            logger.debug(f"Cache hit for Alpaca bars: {symbol}")
            return pd.DataFrame(cached)
        
        try:
            params = {
                "symbols": symbol.upper(),
                "timeframe": timeframe,
                "start": f"{start_date}T00:00:00Z",
                "end": f"{end_date}T23:59:59Z",
                "limit": limit,
                "adjustment": "all",  # Include splits and dividends
                "feed": "iex",  # Use IEX (available on free tier)
            }
            
            data = self._request("GET", "stocks/bars", params=params)
            
            bars = data.get("bars", {}).get(symbol.upper(), [])
            
            if not bars:
                logger.info(f"No Alpaca bars returned for {symbol}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            records = []
            for bar in bars:
                records.append({
                    "time": pd.to_datetime(bar["t"]),
                    "open": float(bar["o"]),
                    "high": float(bar["h"]),
                    "low": float(bar["l"]),
                    "close": float(bar["c"]),
                    "volume": int(bar["v"]),
                    "vwap": float(bar.get("vw", 0)),
                    "trade_count": int(bar.get("n", 0)),
                })
            
            df = pd.DataFrame(records)
            df = df.sort_values("time").reset_index(drop=True)
            
            # Cache the results
            self._cache.set_prices(cache_key, df.to_dict("records"))
            
            logger.info(f"Got {len(df)} Alpaca bars for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to get Alpaca bars for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_snapshot(self, symbol: str) -> Optional[AlpacaSnapshot]:
        """
        Get latest market snapshot for a symbol.
        
        Includes latest trade, quote, minute bar, and daily bar.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            AlpacaSnapshot or None if failed
        """
        if not self.is_configured():
            return None
        
        try:
            params = {"symbols": symbol.upper(), "feed": "iex"}
            data = self._request("GET", "stocks/snapshots", params=params)
            
            snapshot_data = data.get(symbol.upper())
            if not snapshot_data:
                return None
            
            # Parse latest trade
            trade = snapshot_data.get("latestTrade", {})
            
            # Parse daily bar
            daily = snapshot_data.get("dailyBar", {})
            daily_bar = None
            if daily:
                daily_bar = AlpacaBar(
                    timestamp=pd.to_datetime(daily.get("t")),
                    open=float(daily.get("o", 0)),
                    high=float(daily.get("h", 0)),
                    low=float(daily.get("l", 0)),
                    close=float(daily.get("c", 0)),
                    volume=int(daily.get("v", 0)),
                )
            
            return AlpacaSnapshot(
                symbol=symbol.upper(),
                latest_trade_price=float(trade.get("p", 0)) if trade else None,
                latest_trade_timestamp=pd.to_datetime(trade.get("t")) if trade.get("t") else None,
                latest_quote_bid=float(snapshot_data.get("latestQuote", {}).get("bp", 0)),
                latest_quote_ask=float(snapshot_data.get("latestQuote", {}).get("ap", 0)),
                daily_bar=daily_bar,
            )
            
        except Exception as e:
            logger.error(f"Failed to get Alpaca snapshot for {symbol}: {e}")
            return None
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Get the latest trade price for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Latest price or None
        """
        snapshot = self.get_snapshot(symbol)
        if snapshot and snapshot.latest_trade_price:
            return snapshot.latest_trade_price
        return None
    
    def get_multi_snapshots(self, symbols: List[str]) -> Dict[str, AlpacaSnapshot]:
        """
        Get snapshots for multiple symbols at once.
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            Dict mapping symbol to snapshot
        """
        if not self.is_configured() or not symbols:
            return {}
        
        try:
            params = {
                "symbols": ",".join(s.upper() for s in symbols),
                "feed": "iex",
            }
            data = self._request("GET", "stocks/snapshots", params=params)
            
            results = {}
            for symbol in symbols:
                symbol_upper = symbol.upper()
                snapshot_data = data.get(symbol_upper)
                if snapshot_data:
                    trade = snapshot_data.get("latestTrade", {})
                    daily = snapshot_data.get("dailyBar", {})
                    
                    daily_bar = None
                    if daily:
                        daily_bar = AlpacaBar(
                            timestamp=pd.to_datetime(daily.get("t")),
                            open=float(daily.get("o", 0)),
                            high=float(daily.get("h", 0)),
                            low=float(daily.get("l", 0)),
                            close=float(daily.get("c", 0)),
                            volume=int(daily.get("v", 0)),
                        )
                    
                    results[symbol_upper] = AlpacaSnapshot(
                        symbol=symbol_upper,
                        latest_trade_price=float(trade.get("p", 0)) if trade else None,
                        latest_trade_timestamp=pd.to_datetime(trade.get("t")) if trade.get("t") else None,
                        daily_bar=daily_bar,
                    )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get Alpaca multi-snapshots: {e}")
            return {}
    
    # ==================== News Data ====================
    
    def get_news(
        self,
        symbols: List[str] = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 20,
        include_content: bool = False,
    ) -> List[AlpacaNews]:
        """
        Get news articles for symbols.
        
        Args:
            symbols: List of stock symbols (None for general market news)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Maximum articles to return
            include_content: Include full article content
            
        Returns:
            List of AlpacaNews objects
        """
        if not self.is_configured():
            return []
        
        try:
            params = {
                "limit": min(limit, 50),  # Alpaca max is 50
                "include_content": str(include_content).lower(),
            }
            
            if symbols:
                params["symbols"] = ",".join(s.upper() for s in symbols)
            
            if start_date:
                params["start"] = f"{start_date}T00:00:00Z"
            if end_date:
                params["end"] = f"{end_date}T23:59:59Z"
            
            # News API uses v1beta1
            data = self._request("GET", "news", params=params, version="v1beta1")
            
            articles = data.get("news", [])
            
            results = []
            for article in articles:
                results.append(AlpacaNews(
                    id=article.get("id", ""),
                    headline=article.get("headline", ""),
                    summary=article.get("summary", ""),
                    author=article.get("author"),
                    source=article.get("source", ""),
                    url=article.get("url", ""),
                    symbols=article.get("symbols", []),
                    created_at=pd.to_datetime(article.get("created_at")),
                    updated_at=pd.to_datetime(article.get("updated_at")) if article.get("updated_at") else None,
                ))
            
            logger.info(f"Got {len(results)} Alpaca news articles")
            return results
            
        except Exception as e:
            logger.error(f"Failed to get Alpaca news: {e}")
            return []
    
    def get_news_for_ticker(
        self,
        ticker: str,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Get news for a specific ticker in standard dict format.
        
        This returns data in the same format as other news providers
        for easy integration with existing code.
        
        Args:
            ticker: Stock symbol
            limit: Maximum articles
            
        Returns:
            List of news dicts with title, summary, source, url, date
        """
        articles = self.get_news(symbols=[ticker], limit=limit)
        
        return [
            {
                "title": a.headline,
                "summary": a.summary,
                "source": a.source,
                "url": a.url,
                "date": a.created_at.isoformat() if a.created_at else None,
                "symbols": a.symbols,
            }
            for a in articles
        ]


# Global client instance
_alpaca_data_client: Optional[AlpacaDataClient] = None


def get_alpaca_data_client() -> AlpacaDataClient:
    """Get or create the global Alpaca data client."""
    global _alpaca_data_client
    if _alpaca_data_client is None:
        _alpaca_data_client = AlpacaDataClient()
    return _alpaca_data_client


def alpaca_data_available() -> bool:
    """Check if Alpaca data is available (configured)."""
    client = get_alpaca_data_client()
    return client.is_configured()


# Convenience functions for use by data_providers.py

def get_alpaca_prices(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Get prices from Alpaca (convenience function)."""
    client = get_alpaca_data_client()
    return client.get_bars(ticker, start_date, end_date)


def get_alpaca_news(ticker: str, limit: int = 20) -> List[Dict]:
    """Get news from Alpaca (convenience function)."""
    client = get_alpaca_data_client()
    return client.get_news_for_ticker(ticker, limit=limit)


if __name__ == "__main__":
    # Test the client
    import json
    
    client = AlpacaDataClient()
    
    print("=" * 60)
    print("ALPACA MARKET DATA CLIENT TEST")
    print("=" * 60)
    
    if not client.is_configured():
        print("\n⚠️ Alpaca not configured. Set ALPACA_API_KEY and ALPACA_SECRET_KEY")
    else:
        print("\n✓ Alpaca configured")
        
        # Test snapshot
        print("\n--- Testing Snapshot ---")
        snapshot = client.get_snapshot("AAPL")
        if snapshot:
            print(f"AAPL Latest Price: ${snapshot.latest_trade_price:.2f}")
        
        # Test bars
        print("\n--- Testing Bars ---")
        from datetime import datetime, timedelta
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        bars = client.get_bars("AAPL", start, end)
        print(f"Got {len(bars)} bars for AAPL")
        if not bars.empty:
            print(bars.tail())
        
        # Test news
        print("\n--- Testing News ---")
        news = client.get_news(symbols=["AAPL", "MSFT"], limit=5)
        for article in news[:3]:
            print(f"  - {article.headline[:60]}... ({article.source})")
    
    print("\n" + "=" * 60)
