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


class FallbackTracker:
    """
    Tracks fallback usage to detect when primary data sources are failing.
    
    Alerts when:
    - Fallback rate exceeds threshold (e.g., >50% of requests using fallback)
    - Consecutive fallbacks exceed limit (e.g., 5+ in a row)
    """
    
    def __init__(
        self,
        fallback_threshold: float = 0.5,  # Alert if >50% are fallbacks
        consecutive_limit: int = 5,  # Alert if 5+ consecutive fallbacks
        window_size: int = 20,  # Track last 20 requests
    ):
        self.fallback_threshold = fallback_threshold
        self.consecutive_limit = consecutive_limit
        self.window_size = window_size
        
        self._lock = Lock()
        self._history: list[tuple[str, str, bool]] = []  # (data_type, source, was_fallback)
        self._consecutive_fallbacks = 0
        self._alert_cooldown = 0  # Prevent alert spam
    
    def record_success(self, data_type: str, source: str, was_fallback: bool = False):
        """Record a successful data fetch."""
        with self._lock:
            self._history.append((data_type, source, was_fallback))
            if len(self._history) > self.window_size:
                self._history.pop(0)
            
            if was_fallback:
                self._consecutive_fallbacks += 1
                logger.warning(
                    f"Data fallback used: {data_type} from {source} "
                    f"(consecutive: {self._consecutive_fallbacks})"
                )
                self._check_alerts(data_type)
            else:
                self._consecutive_fallbacks = 0
                self._alert_cooldown = max(0, self._alert_cooldown - 1)
    
    def record_primary_failure(self, data_type: str, primary_source: str, error: str):
        """Record when the primary source fails."""
        logger.warning(f"Primary data source failed: {primary_source} for {data_type}: {error}")
        
        # Log to event logger if available
        event_logger = _get_event_logger()
        if event_logger:
            try:
                event_logger.log_event(
                    "data_source_failure",
                    {
                        "data_type": data_type,
                        "source": primary_source,
                        "error": str(error)[:200],
                    },
                    severity="warning"
                )
            except Exception:
                pass
    
    def _check_alerts(self, data_type: str):
        """Check if alert thresholds are exceeded."""
        if self._alert_cooldown > 0:
            return
        
        # Check consecutive fallbacks
        if self._consecutive_fallbacks >= self.consecutive_limit:
            self._trigger_alert(
                f"Primary data source appears down: {self._consecutive_fallbacks} "
                f"consecutive fallbacks for {data_type}"
            )
            self._alert_cooldown = 10  # Cool down for 10 requests
            return
        
        # Check fallback rate
        if len(self._history) >= self.window_size // 2:
            fallback_count = sum(1 for _, _, fb in self._history if fb)
            fallback_rate = fallback_count / len(self._history)
            
            if fallback_rate > self.fallback_threshold:
                self._trigger_alert(
                    f"High fallback rate: {fallback_rate:.0%} of last "
                    f"{len(self._history)} requests used fallback"
                )
                self._alert_cooldown = 10
    
    def _trigger_alert(self, message: str):
        """Trigger an alert for fallback issues."""
        logger.error(f"[DATA ALERT] {message}")
        
        # Log to event logger if available
        event_logger = _get_event_logger()
        if event_logger:
            try:
                event_logger.log_event(
                    "data_fallback_alert",
                    {"message": message, "consecutive": self._consecutive_fallbacks},
                    severity="error"
                )
            except Exception:
                pass
    
    def get_stats(self) -> dict:
        """Get fallback statistics."""
        with self._lock:
            if not self._history:
                return {"total": 0, "fallback_count": 0, "fallback_rate": 0.0}
            
            fallback_count = sum(1 for _, _, fb in self._history if fb)
            return {
                "total": len(self._history),
                "fallback_count": fallback_count,
                "fallback_rate": fallback_count / len(self._history),
                "consecutive_fallbacks": self._consecutive_fallbacks,
                "sources_used": list(set(src for _, src, _ in self._history)),
            }


# Global fallback tracker instance
_fallback_tracker = FallbackTracker()


def get_fallback_stats() -> dict:
    """Get current fallback statistics."""
    return _fallback_tracker.get_stats()


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


def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: dict = None, max_retries: int = 3, call_type: str = "general") -> requests.Response:
    """
    Make an API request with rate limiting handling and exponential backoff.
    
    Args:
        url: The URL to request
        headers: Headers to include in the request
        method: HTTP method (GET or POST)
        json_data: JSON data for POST requests
        max_retries: Maximum number of retries (default: 3)
        call_type: Type of call for telemetry (e.g., "prices", "financials")
    
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
                        call_type=call_type,
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
                    call_type=call_type,
                    success=False,
                    latency_ms=latency_ms,
                )
            raise
        except requests.exceptions.RequestException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            if rate_monitor:
                rate_monitor.record_call(
                    "financial_datasets",
                    call_type=call_type,
                    success=False,
                    latency_ms=latency_ms,
                )
            raise
        finally:
            _data_rate_limiter.release()


def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """Fetch price data from cache or API.
    
    Routes through data sources based on PRIMARY_DATA_SOURCE:
    - fmp: FMP → Alpaca → Financial Datasets
    - alpaca: Alpaca → FMP → Financial Datasets
    - financial_datasets: Financial Datasets API only
    """
    primary_source = os.environ.get("PRIMARY_DATA_SOURCE", "fmp")
    
    # Helper to fetch from FMP
    def try_fmp() -> list[Price] | None:
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
            logger.warning(f"FMP prices failed for {ticker}: {e}")
        return None
    
    # Helper to fetch from Alpaca
    def try_alpaca() -> list[Price] | None:
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
            logger.warning(f"Alpaca prices failed for {ticker}: {e}")
        return None
    
    # Route based on primary data source
    if primary_source == "fmp":
        # FMP → Alpaca → Financial Datasets
        result = try_fmp()
        if result:
            _fallback_tracker.record_success("prices", "FMP", was_fallback=False)
            return result
        _fallback_tracker.record_primary_failure("prices", "FMP", "No data returned")
        logger.info(f"FMP failed for {ticker}, trying Alpaca fallback...")
        result = try_alpaca()
        if result:
            _fallback_tracker.record_success("prices", "Alpaca", was_fallback=True)
            return result
        logger.info(f"Alpaca fallback failed for {ticker}, trying Financial Datasets...")
    elif primary_source == "alpaca":
        # Alpaca → FMP → Financial Datasets
        result = try_alpaca()
        if result:
            _fallback_tracker.record_success("prices", "Alpaca", was_fallback=False)
            return result
        _fallback_tracker.record_primary_failure("prices", "Alpaca", "No data returned")
        logger.info(f"Alpaca failed for {ticker}, trying FMP fallback...")
        result = try_fmp()
        if result:
            _fallback_tracker.record_success("prices", "FMP", was_fallback=True)
            return result
        logger.info(f"FMP fallback failed for {ticker}, trying Financial Datasets...")

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
    response = _make_api_request(url, headers, call_type="prices")
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

                    # Map FMP fields to FinancialMetrics model fields
                    # FMP uses camelCase with TTM suffix, we use snake_case
                    fmp_metrics = FinancialMetrics(
                        ticker=ticker,
                        report_period=end_date,
                        period=period,
                        currency="USD",  # FMP primarily covers US markets
                        
                        # Valuation metrics
                        market_cap=m.get("marketCap"),
                        enterprise_value=m.get("enterpriseValueTTM") or r.get("enterpriseValueTTM"),
                        price_to_earnings_ratio=r.get("priceToEarningsRatioTTM"),
                        price_to_book_ratio=r.get("priceToBookRatioTTM"),
                        price_to_sales_ratio=r.get("priceToSalesRatioTTM"),
                        enterprise_value_to_ebitda_ratio=m.get("evToEBITDATTM") or r.get("enterpriseValueMultipleTTM"),
                        enterprise_value_to_revenue_ratio=m.get("evToSalesTTM"),
                        free_cash_flow_yield=m.get("freeCashFlowYieldTTM"),
                        peg_ratio=r.get("priceToEarningsGrowthRatioTTM"),
                        
                        # Profitability margins
                        gross_margin=r.get("grossProfitMarginTTM"),
                        operating_margin=r.get("operatingProfitMarginTTM"),
                        net_margin=r.get("netProfitMarginTTM"),
                        
                        # Returns
                        return_on_equity=m.get("returnOnEquityTTM") or r.get("returnOnEquityTTM"),
                        return_on_assets=m.get("returnOnAssetsTTM") or r.get("returnOnAssetsTTM"),
                        return_on_invested_capital=m.get("returnOnInvestedCapitalTTM"),
                        
                        # Efficiency/Turnover
                        asset_turnover=r.get("assetTurnoverTTM"),
                        inventory_turnover=r.get("inventoryTurnoverTTM"),
                        receivables_turnover=r.get("receivablesTurnoverTTM"),
                        days_sales_outstanding=m.get("daysOfSalesOutstandingTTM"),
                        operating_cycle=m.get("operatingCycleTTM"),
                        working_capital_turnover=r.get("workingCapitalTurnoverRatioTTM"),
                        
                        # Liquidity
                        current_ratio=m.get("currentRatioTTM") or r.get("currentRatioTTM"),
                        quick_ratio=r.get("quickRatioTTM"),
                        cash_ratio=r.get("cashRatioTTM"),
                        operating_cash_flow_ratio=r.get("operatingCashFlowRatioTTM"),
                        
                        # Leverage/Solvency
                        debt_to_equity=r.get("debtToEquityRatioTTM"),
                        debt_to_assets=r.get("debtToAssetsRatioTTM"),
                        interest_coverage=r.get("interestCoverageRatioTTM"),
                        
                        # Per-share metrics
                        payout_ratio=r.get("dividendPayoutRatioTTM"),
                        earnings_per_share=r.get("netIncomePerShareTTM"),
                        book_value_per_share=r.get("bookValuePerShareTTM"),
                        free_cash_flow_per_share=r.get("freeCashFlowPerShareTTM"),
                        
                        # Note: FMP TTM endpoints don't provide growth metrics directly
                        # Growth metrics would require comparing multiple periods
                        # These are left as None for now
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
    response = _make_api_request(url, headers, call_type="metrics")
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
    response = _make_api_request(url, headers, method="POST", json_data=body, call_type="financials")
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

        response = _make_api_request(url, headers, call_type="insider")
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
    - fmp: FMP → Alpaca → Financial Datasets
    - alpaca: Alpaca → FMP → Financial Datasets
    - Others: Financial Datasets API only
    """
    primary_source = os.environ.get("PRIMARY_DATA_SOURCE", "fmp")

    # Helper to fetch from FMP
    def try_fmp() -> list[CompanyNews] | None:
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
            logger.warning(f"FMP news failed for {ticker}: {e}")
        return None

    # Helper to fetch from Alpaca
    def try_alpaca() -> list[CompanyNews] | None:
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
            logger.warning(f"Alpaca news failed for {ticker}: {e}")
        return None

    # Route based on primary data source
    if primary_source == "fmp":
        # FMP → Alpaca → Financial Datasets
        result = try_fmp()
        if result:
            _fallback_tracker.record_success("news", "FMP", was_fallback=False)
            return result
        _fallback_tracker.record_primary_failure("news", "FMP", "No data returned")
        logger.info(f"FMP news failed for {ticker}, trying Alpaca fallback...")
        result = try_alpaca()
        if result:
            _fallback_tracker.record_success("news", "Alpaca", was_fallback=True)
            return result
        logger.info(f"Alpaca news fallback failed for {ticker}, trying Financial Datasets...")
    elif primary_source == "alpaca":
        # Alpaca → FMP → Financial Datasets
        result = try_alpaca()
        if result:
            _fallback_tracker.record_success("news", "Alpaca", was_fallback=False)
            return result
        _fallback_tracker.record_primary_failure("news", "Alpaca", "No data returned")
        logger.info(f"Alpaca news failed for {ticker}, trying FMP fallback...")
        result = try_fmp()
        if result:
            _fallback_tracker.record_success("news", "FMP", was_fallback=True)
            return result
        logger.info(f"FMP news fallback failed for {ticker}, trying Financial Datasets...")

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

        response = _make_api_request(url, headers, call_type="news")
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
        response = _make_api_request(url, headers, call_type="company")
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


# =============================================================================
# FMP Gateway Helper Functions
# =============================================================================
# These functions provide access to the full FMP Ultimate data catalog.
# Each data family can be toggled via environment variables (FMP_MODULE_*).

def get_company_profile(ticker: str) -> dict | None:
    """
    Get full company profile including sector, industry, description, CEO.
    
    Returns dict with: symbol, company_name, sector, industry, description,
    ceo, website, country, market_cap, employees, ipo_date
    """
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        gateway = get_fmp_gateway()
        profile = gateway.get_company_profile(ticker)
        if profile:
            from dataclasses import asdict
            return asdict(profile)
    except Exception as e:
        logger.debug(f"Failed to get company profile for {ticker}: {e}")
    return None


def get_company_peers(ticker: str) -> list[str]:
    """Get list of peer company symbols."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        gateway = get_fmp_gateway()
        peers = gateway.get_company_peers(ticker)
        return peers.peers if peers else []
    except Exception as e:
        logger.debug(f"Failed to get company peers for {ticker}: {e}")
    return []


def get_analyst_estimates(ticker: str, period: str = "annual", limit: int = 4) -> list[dict]:
    """
    Get analyst earnings and revenue estimates.
    
    Returns list of estimates with: date, estimated_eps_avg, estimated_revenue_avg, etc.
    """
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        estimates = gateway.get_analyst_estimates(ticker, period, limit)
        return [asdict(e) for e in estimates]
    except Exception as e:
        logger.debug(f"Failed to get analyst estimates for {ticker}: {e}")
    return []


def get_price_targets(ticker: str, limit: int = 10) -> list[dict]:
    """
    Get analyst price targets.
    
    Returns list of targets with: analyst_name, analyst_company, price_target, upside
    """
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        targets = gateway.get_price_targets(ticker, limit)
        return [asdict(t) for t in targets]
    except Exception as e:
        logger.debug(f"Failed to get price targets for {ticker}: {e}")
    return []


def get_price_target_consensus(ticker: str) -> dict | None:
    """Get consensus price target with average, high, low."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        gateway = get_fmp_gateway()
        return gateway.get_price_target_consensus(ticker)
    except Exception as e:
        logger.debug(f"Failed to get price target consensus for {ticker}: {e}")
    return None


def get_stock_grades(ticker: str, limit: int = 10) -> list[dict]:
    """
    Get stock upgrade/downgrade history.
    
    Returns list with: grading_company, previous_grade, new_grade, action
    """
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        grades = gateway.get_stock_grades(ticker, limit)
        return [asdict(g) for g in grades]
    except Exception as e:
        logger.debug(f"Failed to get stock grades for {ticker}: {e}")
    return []


def get_analyst_recommendations(ticker: str) -> dict | None:
    """Get analyst recommendation summary (strong buy, buy, hold, sell, strong sell counts)."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        gateway = get_fmp_gateway()
        return gateway.get_analyst_recommendations(ticker)
    except Exception as e:
        logger.debug(f"Failed to get analyst recommendations for {ticker}: {e}")
    return None


def get_fmp_insider_trades(ticker: str, limit: int = 50) -> list[dict]:
    """
    Get insider trading activity from FMP.
    
    Returns list with: filing_date, transaction_date, reporting_name, 
    transaction_type (P=Purchase, S=Sale), securities_transacted, price
    """
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        trades = gateway.get_insider_trades(ticker, limit)
        return [asdict(t) for t in trades]
    except Exception as e:
        logger.debug(f"Failed to get insider trades for {ticker}: {e}")
    return []


def get_form_13f(ticker: str = None, cik: str = None, limit: int = 100) -> list[dict]:
    """
    Get 13F institutional holdings.
    
    Query by symbol (who holds it) or by CIK (what an institution holds).
    """
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        filings = gateway.get_form_13f(symbol=ticker, cik=cik, limit=limit)
        return [asdict(f) for f in filings]
    except Exception as e:
        logger.debug(f"Failed to get 13F data: {e}")
    return []


def get_institutional_holders(ticker: str) -> list[dict]:
    """Get institutional holders for a symbol."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        gateway = get_fmp_gateway()
        return gateway.get_institutional_holders(ticker)
    except Exception as e:
        logger.debug(f"Failed to get institutional holders for {ticker}: {e}")
    return []


def get_earnings_calendar(from_date: str = None, to_date: str = None) -> list[dict]:
    """
    Get earnings calendar.
    
    Returns list with: symbol, date, eps_estimated, eps_actual, revenue_estimated, time
    """
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        events = gateway.get_earnings_calendar(from_date, to_date)
        return [asdict(e) for e in events]
    except Exception as e:
        logger.debug(f"Failed to get earnings calendar: {e}")
    return []


def get_economic_calendar(from_date: str = None, to_date: str = None) -> list[dict]:
    """Get economic events calendar."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        gateway = get_fmp_gateway()
        return gateway.get_economic_calendar(from_date, to_date)
    except Exception as e:
        logger.debug(f"Failed to get economic calendar: {e}")
    return []


def get_macro_indicators(indicator: str = None) -> list[dict]:
    """
    Get macroeconomic indicators (GDP, CPI, unemployment, etc.).
    
    Common indicators: GDP, CPI, UNRATE (unemployment), PAYEMS (nonfarm payrolls)
    """
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        indicators = gateway.get_economic_indicators(indicator)
        return [asdict(i) for i in indicators]
    except Exception as e:
        logger.debug(f"Failed to get macro indicators: {e}")
    return []


def get_sector_performance() -> list[dict]:
    """Get sector performance (change percentages)."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        sectors = gateway.get_sector_performance()
        return [asdict(s) for s in sectors]
    except Exception as e:
        logger.debug(f"Failed to get sector performance: {e}")
    return []


def get_market_movers(mover_type: str = "gainers", limit: int = 10) -> list[dict]:
    """
    Get market movers (gainers, losers, most active).
    
    Args:
        mover_type: "gainers", "losers", or "actives"
    """
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        
        if mover_type == "gainers":
            movers = gateway.get_gainers(limit)
        elif mover_type == "losers":
            movers = gateway.get_losers(limit)
        else:
            movers = gateway.get_most_active(limit)
        
        return [asdict(m) for m in movers]
    except Exception as e:
        logger.debug(f"Failed to get market movers: {e}")
    return []


def get_etf_holdings(etf_symbol: str) -> list[dict]:
    """Get ETF constituent holdings."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        holdings = gateway.get_etf_holdings(etf_symbol)
        return [asdict(h) for h in holdings]
    except Exception as e:
        logger.debug(f"Failed to get ETF holdings for {etf_symbol}: {e}")
    return []


def get_commodity_quotes() -> list[dict]:
    """Get commodity quotes (gold, oil, etc.)."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        quotes = gateway.get_commodity_quotes()
        return [asdict(q) for q in quotes]
    except Exception as e:
        logger.debug(f"Failed to get commodity quotes: {e}")
    return []


def get_forex_quotes() -> list[dict]:
    """Get forex quotes."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        quotes = gateway.get_forex_quotes()
        return [asdict(q) for q in quotes]
    except Exception as e:
        logger.debug(f"Failed to get forex quotes: {e}")
    return []


def get_crypto_quotes(limit: int = 20) -> list[dict]:
    """Get cryptocurrency quotes."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        quotes = gateway.get_crypto_quotes(limit)
        return [asdict(q) for q in quotes]
    except Exception as e:
        logger.debug(f"Failed to get crypto quotes: {e}")
    return []


def get_esg_score(ticker: str) -> dict | None:
    """Get ESG (Environmental, Social, Governance) score."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        from dataclasses import asdict
        gateway = get_fmp_gateway()
        score = gateway.get_esg_score(ticker)
        return asdict(score) if score else None
    except Exception as e:
        logger.debug(f"Failed to get ESG score for {ticker}: {e}")
    return None


def get_fmp_module_status() -> dict:
    """Get status of all FMP modules (enabled/disabled)."""
    try:
        from src.data.fmp_gateway import get_fmp_gateway
        gateway = get_fmp_gateway()
        return {
            "configured": gateway.is_configured(),
            "modules": gateway.get_module_status(),
        }
    except Exception as e:
        logger.debug(f"Failed to get FMP module status: {e}")
    return {"configured": False, "modules": {}}
