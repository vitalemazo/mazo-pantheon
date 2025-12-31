import datetime
import os
import pandas as pd
import requests
import time
import logging
from threading import Semaphore, Lock

from src.data.cache import get_cache

# Lazy import for monitoring to avoid circular imports
_rate_limit_monitor = None
_event_logger = None


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


def _get_event_logger():
    """Lazy load the event logger."""
    global _event_logger
    if _event_logger is None:
        try:
            from src.monitoring import get_event_logger
            _event_logger = get_event_logger()
        except Exception:
            pass
    return _event_logger
from src.data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    Price,
    PriceResponse,
    LineItem,
    LineItemResponse,
    InsiderTrade,
    InsiderTradeResponse,
    CompanyFactsResponse,
)

logger = logging.getLogger(__name__)

# Global cache instance
_cache = get_cache()


class DataAPIRateLimiter:
    """
    Rate limiter for Financial Datasets API calls.
    
    Prevents 429 errors by:
    1. Limiting concurrent requests
    2. Enforcing minimum delay between requests
    3. Exponential backoff on rate limit errors
    """
    
    def __init__(
        self,
        max_concurrent: int = 2,
        min_delay_seconds: float = 0.5,
        backoff_base: float = 2.0,
        max_backoff: float = 120.0,
    ):
        self.max_concurrent = max_concurrent
        self.min_delay = min_delay_seconds
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff
        
        self.semaphore = Semaphore(max_concurrent)
        self.last_request_time = 0
        self.time_lock = Lock()
        
        self.consecutive_429s = 0
        self.backoff_lock = Lock()
    
    def _wait_for_slot(self):
        """Wait for rate limit slot."""
        with self.time_lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
            self.last_request_time = time.time()
    
    def _calculate_backoff(self) -> float:
        """Calculate backoff delay based on consecutive 429 errors."""
        with self.backoff_lock:
            if self.consecutive_429s == 0:
                return 0.0
            backoff = min(self.backoff_base ** self.consecutive_429s, self.max_backoff)
            # Add jitter
            import random
            jitter = random.uniform(0, backoff * 0.1)
            return backoff + jitter
    
    def record_429(self):
        """Record a 429 error."""
        with self.backoff_lock:
            self.consecutive_429s += 1
            logger.warning(f"Data API rate limited, consecutive 429s: {self.consecutive_429s}")
    
    def record_success(self):
        """Record a successful request."""
        with self.backoff_lock:
            self.consecutive_429s = 0
    
    def acquire(self, timeout: float = 300) -> bool:
        """Acquire permission to make an API call."""
        if not self.semaphore.acquire(timeout=timeout):
            return False
        
        # Apply backoff if needed
        backoff = self._calculate_backoff()
        if backoff > 0:
            logger.info(f"Data API backoff: waiting {backoff:.1f}s")
            time.sleep(backoff)
        
        # Wait for minimum delay
        self._wait_for_slot()
        return True
    
    def release(self):
        """Release the rate limiter slot."""
        self.semaphore.release()


# Global rate limiter for data API
_data_rate_limiter = DataAPIRateLimiter(
    max_concurrent=int(os.getenv("DATA_API_MAX_CONCURRENT", "2")),
    min_delay_seconds=float(os.getenv("DATA_API_MIN_DELAY", "0.5")),
)


def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: dict = None, max_retries: int = 3) -> requests.Response:
    """
    Make an API request with rate limiting handling and exponential backoff.
    
    Args:
        url: The URL to request
        headers: Headers to include in the request
        method: HTTP method (GET or POST)
        json_data: JSON data for POST requests
        max_retries: Maximum number of retries (default: 3)
    
    Returns:
        requests.Response: The response object
    
    Raises:
        Exception: If the request fails with a non-429 error
    """
    rate_monitor = _get_rate_limit_monitor()
    
    for attempt in range(max_retries + 1):  # +1 for initial attempt
        # Acquire rate limiter permission
        if not _data_rate_limiter.acquire(timeout=300):
            logger.warning("Data API rate limiter timeout")
            # Return a fake 429 response to trigger retry logic
            response = requests.Response()
            response.status_code = 429
            return response
        
        start_time = time.time()
        try:
            if method.upper() == "POST":
                response = requests.post(url, headers=headers, json=json_data, timeout=30)
            else:
                response = requests.get(url, headers=headers, timeout=30)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code == 429:
                _data_rate_limiter.record_429()
                
                # Log rate limit hit to monitoring system
                if rate_monitor:
                    retry_after = response.headers.get("Retry-After")
                    rate_monitor.record_rate_limit_hit(
                        "financial_datasets",
                        retry_after=int(retry_after) if retry_after else None
                    )
                
                if attempt < max_retries:
                    # Exponential backoff: 10s, 20s, 40s...
                    delay = min(10 * (2 ** attempt), 120)
                    logger.info(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s...")
                    time.sleep(delay)
                    continue
            else:
                _data_rate_limiter.record_success()
                
                # Log successful call to monitoring system
                if rate_monitor:
                    # Parse rate limit headers if present
                    remaining = response.headers.get("X-RateLimit-Remaining")
                    rate_monitor.record_call(
                        "financial_datasets",
                        success=(response.status_code < 400),
                        rate_limit_remaining=int(remaining) if remaining else None,
                        latency_ms=latency_ms,
                    )
            
            return response
            
        except requests.exceptions.Timeout as e:
            latency_ms = int((time.time() - start_time) * 1000)
            if rate_monitor:
                rate_monitor.record_call(
                    "financial_datasets",
                    success=False,
                    latency_ms=latency_ms,
                )
            raise
        except requests.exceptions.RequestException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            if rate_monitor:
                rate_monitor.record_call(
                    "financial_datasets",
                    success=False,
                    latency_ms=latency_ms,
                )
            raise
        finally:
            _data_rate_limiter.release()


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """Fetch price data from cache or API.
    
    Routes through data sources based on PRIMARY_DATA_SOURCE:
    - fmp: FMP Ultimate first, then fallback
    - alpaca: Alpaca Market Data first, then fallback  
    - financial_datasets: Financial Datasets API (default)
    """
    primary_source = os.environ.get("PRIMARY_DATA_SOURCE", "fmp")
    
    # Try FMP first when selected as primary
    if primary_source == "fmp":
        try:
            from src.tools.fmp_data import get_fmp_data_client
            client = get_fmp_data_client()
            if client.is_configured():
                df = client.get_historical_prices(ticker, start_date, end_date)
                if df is not None and not df.empty:
                    prices = []
                    for _, row in df.iterrows():
                        prices.append(Price(
                            ticker=ticker,
                            time=row["time"].isoformat() if hasattr(row["time"], "isoformat") else str(row["time"]),
                            open=float(row["open"]),
                            high=float(row["high"]),
                            low=float(row["low"]),
                            close=float(row["close"]),
                            volume=int(row["volume"]),
                        ))
                    if prices:
                        logger.info(f"Got {len(prices)} prices for {ticker} from FMP")
                        return prices
        except Exception as e:
            logger.warning(f"FMP prices failed for {ticker}, falling back: {e}")
    
    # Try Alpaca when selected as primary
    if primary_source == "alpaca":
        try:
            from src.tools.alpaca_data import get_alpaca_data_client
            client = get_alpaca_data_client()
            if client.is_configured():
                df = client.get_bars(ticker, start_date, end_date)
                if df is not None and not df.empty:
                    prices = []
                    for _, row in df.iterrows():
                        prices.append(Price(
                            ticker=ticker,
                            time=row["time"].isoformat() if hasattr(row["time"], "isoformat") else str(row["time"]),
                            open=float(row["open"]),
                            high=float(row["high"]),
                            low=float(row["low"]),
                            close=float(row["close"]),
                            volume=int(row["volume"]),
                        ))
                    if prices:
                        logger.info(f"Got {len(prices)} prices for {ticker} from Alpaca")
                        return prices
        except Exception as e:
            logger.warning(f"Alpaca prices failed for {ticker}, falling back: {e}")
    
    # Fall back to Financial Datasets API
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date}_{end_date}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
    response = _make_api_request(url, headers)
    if response.status_code != 200:
        return []

    # Parse response with Pydantic model
    try:
        price_response = PriceResponse(**response.json())
        prices = price_response.prices
    except:
        return []

    if not prices:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_prices(cache_key, [p.model_dump() for p in prices])
    return prices


def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """Fetch financial metrics from cache or API.
    
    Routes through data sources based on PRIMARY_DATA_SOURCE:
    - fmp: FMP Ultimate first (comprehensive fundamentals)
    - Others: Financial Datasets API
    """
    primary_source = os.environ.get("PRIMARY_DATA_SOURCE", "fmp")
    
    # Try FMP first when selected as primary
    if primary_source == "fmp":
        try:
            from src.tools.fmp_data import get_fmp_data_client
            client = get_fmp_data_client()
            if client.is_configured():
                metrics_ttm = client.get_key_metrics_ttm(ticker)
                ratios_ttm = client.get_ratios_ttm(ticker)
                
                if metrics_ttm or ratios_ttm:
                    m = metrics_ttm or {}
                    r = ratios_ttm or {}
                    
                    # Build FinancialMetrics from FMP data
                    fmp_metrics = FinancialMetrics(
                        ticker=ticker,
                        report_period=end_date,
                        period=period,
                        pe_ratio_ttm=m.get("peRatioTTM"),
                        price_to_book_ratio=m.get("pbRatioTTM") or r.get("priceToBookRatioTTM"),
                        price_to_sales_ratio_ttm=m.get("priceToSalesRatioTTM") or r.get("priceToSalesRatioTTM"),
                        net_margin=r.get("netProfitMarginTTM"),
                        operating_margin=r.get("operatingProfitMarginTTM"),
                        gross_margin=r.get("grossProfitMarginTTM"),
                        return_on_equity=m.get("roeTTM") or r.get("returnOnEquityTTM"),
                        return_on_assets=m.get("roaTTM") or r.get("returnOnAssetsTTM"),
                        debt_to_equity=m.get("debtToEquityTTM") or r.get("debtEquityRatioTTM"),
                        current_ratio=m.get("currentRatioTTM") or r.get("currentRatioTTM"),
                        market_cap=m.get("marketCapTTM"),
                        enterprise_value=m.get("enterpriseValueTTM"),
                        revenue_growth_yoy=m.get("revenueGrowthTTM"),
                        earnings_growth_yoy=m.get("netIncomeGrowthTTM"),
                    )
                    logger.info(f"Got financial metrics for {ticker} from FMP")
                    return [fmp_metrics]
        except Exception as e:
            logger.warning(f"FMP metrics failed for {ticker}, falling back: {e}")
    
    # Fall back to Financial Datasets API
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{period}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_financial_metrics(cache_key):
        return [FinancialMetrics(**metric) for metric in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
    response = _make_api_request(url, headers)
    if response.status_code != 200:
        return []

    # Parse response with Pydantic model
    try:
        metrics_response = FinancialMetricsResponse(**response.json())
        financial_metrics = metrics_response.financial_metrics
    except:
        return []

    if not financial_metrics:
        return []

    # Cache the results as dicts using the comprehensive cache key
    _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
    return financial_metrics


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """Fetch line items from API."""
    # If not in cache or insufficient data, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    url = "https://api.financialdatasets.ai/financials/search/line-items"

    body = {
        "tickers": [ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit,
    }
    response = _make_api_request(url, headers, method="POST", json_data=body)
    if response.status_code != 200:
        return []
    
    try:
        data = response.json()
        response_model = LineItemResponse(**data)
        search_results = response_model.search_results
    except:
        return []
    if not search_results:
        return []

    # Cache the results
    return search_results[:limit]


def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """Fetch insider trades from cache or API.
    
    Routes through data sources based on PRIMARY_DATA_SOURCE:
    - fmp: FMP Ultimate first (comprehensive insider data)
    - Others: Financial Datasets API
    """
    primary_source = os.environ.get("PRIMARY_DATA_SOURCE", "fmp")
    
    # Try FMP first when selected as primary
    if primary_source == "fmp":
        try:
            from src.tools.fmp_data import get_fmp_data_client
            client = get_fmp_data_client()
            if client.is_configured():
                fmp_trades = client.get_insider_trades(symbol=ticker, limit=min(limit, 100))
                if fmp_trades:
                    trades_list = []
                    for trade in fmp_trades:
                        trades_list.append(InsiderTrade(
                            ticker=ticker,
                            issuer_name=trade.get("reportingName", ""),
                            owner_name=trade.get("reportingName", ""),
                            owner_title=trade.get("typeOfOwner", ""),
                            transaction_type=trade.get("transactionType", ""),
                            transaction_shares=trade.get("securitiesTransacted"),
                            transaction_price_per_share=trade.get("price"),
                            shares_owned_after_transaction=trade.get("securitiesOwned"),
                            filing_date=trade.get("filingDate", end_date),
                        ))
                    if trades_list:
                        logger.info(f"Got {len(trades_list)} insider trades for {ticker} from FMP")
                        return trades_list
        except Exception as e:
            logger.warning(f"FMP insider trades failed for {ticker}, falling back: {e}")
    
    # Fall back to Financial Datasets API
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_insider_trades(cache_key):
        return [InsiderTrade(**trade) for trade in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    all_trades = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
        if start_date:
            url += f"&filing_date_gte={start_date}"
        url += f"&limit={limit}"

        response = _make_api_request(url, headers)
        if response.status_code != 200:
            break

        try:
            data = response.json()
            response_model = InsiderTradeResponse(**data)
            insider_trades = response_model.insider_trades
        except:
            break  # Parsing error, exit loop

        if not insider_trades:
            break

        all_trades.extend(insider_trades)

        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(insider_trades) < limit:
            break

        # Update end_date to the oldest filing date from current batch for next iteration
        current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]

        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    if not all_trades:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in all_trades])
    return all_trades


def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """Fetch company news from cache or API.
    
    Routes through data sources based on PRIMARY_DATA_SOURCE:
    - fmp: FMP Ultimate first (comprehensive news)
    - alpaca: Alpaca Market Data first
    - Others: Financial Datasets API
    """
    primary_source = os.environ.get("PRIMARY_DATA_SOURCE", "fmp")
    
    # Try FMP first when selected as primary
    if primary_source == "fmp":
        try:
            from src.tools.fmp_data import get_fmp_data_client
            client = get_fmp_data_client()
            if client.is_configured():
                fmp_news = client.get_stock_news(symbols=[ticker], limit=min(limit, 100))
                if fmp_news:
                    news_list = []
                    for article in fmp_news:
                        news_list.append(CompanyNews(
                            ticker=ticker,
                            title=article.title,
                            description=article.text[:500] if article.text else "",
                            source=article.site,
                            url=article.url,
                            date=article.published_date.isoformat() if article.published_date else None,
                        ))
                    if news_list:
                        logger.info(f"Got {len(news_list)} news articles for {ticker} from FMP")
                        return news_list
        except Exception as e:
            logger.warning(f"FMP news failed for {ticker}, falling back: {e}")
    
    # Try Alpaca when selected as primary
    if primary_source == "alpaca":
        try:
            from src.tools.alpaca_data import get_alpaca_data_client
            client = get_alpaca_data_client()
            if client.is_configured():
                alpaca_news = client.get_news(
                    symbols=[ticker],
                    start_date=start_date,
                    end_date=end_date,
                    limit=min(limit, 50),  # Alpaca max is 50
                )
                if alpaca_news:
                    news_list = []
                    for article in alpaca_news:
                        news_list.append(CompanyNews(
                            ticker=ticker,
                            title=article.headline,
                            description=article.summary,
                            source=article.source,
                            url=article.url,
                            date=article.created_at.isoformat() if article.created_at else None,
                        ))
                    if news_list:
                        logger.info(f"Got {len(news_list)} news articles for {ticker} from Alpaca")
                        return news_list
        except Exception as e:
            logger.warning(f"Alpaca news failed for {ticker}, falling back: {e}")
    
    # Fall back to Financial Datasets API
    # Create a cache key that includes all parameters to ensure exact matches
    cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
    
    # Check cache first - simple exact match
    if cached_data := _cache.get_company_news(cache_key):
        return [CompanyNews(**news) for news in cached_data]

    # If not in cache, fetch from API
    headers = {}
    financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
    if financial_api_key:
        headers["X-API-KEY"] = financial_api_key

    all_news = []
    current_end_date = end_date

    while True:
        url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
        if start_date:
            url += f"&start_date={start_date}"
        url += f"&limit={limit}"

        response = _make_api_request(url, headers)
        if response.status_code != 200:
            break

        try:
            data = response.json()
            response_model = CompanyNewsResponse(**data)
            company_news = response_model.news
        except:
            break  # Parsing error, exit loop

        if not company_news:
            break

        all_news.extend(company_news)

        # Only continue pagination if we have a start_date and got a full page
        if not start_date or len(company_news) < limit:
            break

        # Update end_date to the oldest date from current batch for next iteration
        current_end_date = min(news.date for news in company_news).split("T")[0]

        # If we've reached or passed the start_date, we can stop
        if current_end_date <= start_date:
            break

    if not all_news:
        return []

    # Cache the results using the comprehensive cache key
    _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
    return all_news


def get_market_cap(
    ticker: str,
    end_date: str,
    api_key: str = None,
) -> float | None:
    """Fetch market cap from the API."""
    # Check if end_date is today
    if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
        # Get the market cap from company facts API
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key

        url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
        response = _make_api_request(url, headers)
        if response.status_code != 200:
            print(f"Error fetching company facts: {ticker} - {response.status_code}")
            return None

        data = response.json()
        response_model = CompanyFactsResponse(**data)
        return response_model.company_facts.market_cap

    financial_metrics = get_financial_metrics(ticker, end_date, api_key=api_key)
    if not financial_metrics:
        return None

    market_cap = financial_metrics[0].market_cap

    if not market_cap:
        return None

    return market_cap


def prices_to_df(prices: list[Price]) -> pd.DataFrame:
    """Convert prices to a DataFrame."""
    df = pd.DataFrame([p.model_dump() for p in prices])
    df["Date"] = pd.to_datetime(df["time"])
    df.set_index("Date", inplace=True)
    numeric_cols = ["open", "close", "high", "low", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.sort_index(inplace=True)
    return df


# Update the get_price_data function to use the new functions
def get_price_data(ticker: str, start_date: str, end_date: str, api_key: str = None) -> pd.DataFrame:
    prices = get_prices(ticker, start_date, end_date, api_key=api_key)
    return prices_to_df(prices)
