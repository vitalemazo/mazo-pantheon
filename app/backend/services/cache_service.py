"""
Redis Cache Service

Provides caching for expensive API calls to:
- LLM providers (OpenAI, Anthropic, etc.)
- Financial data APIs
- Alpaca broker API

This dramatically reduces response times and API costs by
caching responses for repeated queries.
"""

import os
import json
import hashlib
from typing import Optional, Any
from datetime import timedelta
import redis
from functools import wraps

# Redis connection
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Get or create Redis client."""
    global _redis_client
    
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            # Test connection
            _redis_client.ping()
            print(f"[Cache] Connected to Redis at {REDIS_URL}")
        except Exception as e:
            print(f"[Cache] Redis connection failed: {e}")
            _redis_client = None
    
    return _redis_client


def cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate a cache key from function arguments."""
    key_data = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
    return f"mazo:{prefix}:{key_hash}"


def get_cached(key: str) -> Optional[Any]:
    """Get value from cache."""
    client = get_redis_client()
    if client is None:
        return None
    
    try:
        value = client.get(key)
        if value:
            return json.loads(value)
    except Exception as e:
        print(f"[Cache] Get error: {e}")
    
    return None


def set_cached(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    """Set value in cache with TTL."""
    client = get_redis_client()
    if client is None:
        return False
    
    try:
        client.setex(key, ttl_seconds, json.dumps(value, default=str))
        return True
    except Exception as e:
        print(f"[Cache] Set error: {e}")
        return False


def delete_cached(pattern: str) -> int:
    """Delete keys matching pattern."""
    client = get_redis_client()
    if client is None:
        return 0
    
    try:
        keys = client.keys(f"mazo:{pattern}*")
        if keys:
            return client.delete(*keys)
    except Exception as e:
        print(f"[Cache] Delete error: {e}")
    
    return 0


def cached(prefix: str, ttl_seconds: int = 300):
    """
    Decorator to cache function results.
    
    Usage:
        @cached('financial_data', ttl_seconds=600)
        def get_stock_data(ticker: str):
            # Expensive API call
            return data
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_value = get_cached(key)
            if cached_value is not None:
                print(f"[Cache] HIT {key}")
                return cached_value
            
            # Call function
            print(f"[Cache] MISS {key}")
            result = func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                set_cached(key, result, ttl_seconds)
            
            return result
        
        return wrapper
    return decorator


def cached_async(prefix: str, ttl_seconds: int = 300):
    """
    Async version of cached decorator.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_value = get_cached(key)
            if cached_value is not None:
                print(f"[Cache] HIT {key}")
                return cached_value
            
            # Call function
            print(f"[Cache] MISS {key}")
            result = await func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                set_cached(key, result, ttl_seconds)
            
            return result
        
        return wrapper
    return decorator


# ==================== CACHE TTLs ====================

class CacheTTL:
    """Standard TTL values for different data types."""
    
    # Financial data (relatively stable)
    STOCK_QUOTE = 60  # 1 minute
    STOCK_METRICS = 300  # 5 minutes
    STOCK_NEWS = 180  # 3 minutes
    FINANCIAL_STATEMENTS = 3600  # 1 hour
    
    # Alpaca data
    ALPACA_ACCOUNT = 30  # 30 seconds
    ALPACA_POSITIONS = 15  # 15 seconds
    ALPACA_ASSETS = 3600  # 1 hour (rarely changes)
    
    # AI responses (expensive to regenerate)
    LLM_ANALYSIS = 600  # 10 minutes
    MAZO_RESEARCH = 1800  # 30 minutes
    
    # Aggregated data
    PERFORMANCE_METRICS = 60  # 1 minute
    AGENT_PERFORMANCE = 300  # 5 minutes


# ==================== CONVENIENCE FUNCTIONS ====================

def cache_alpaca_assets(assets: list) -> bool:
    """Cache Alpaca tradeable assets list."""
    return set_cached("mazo:alpaca:assets", assets, CacheTTL.ALPACA_ASSETS)


def get_cached_alpaca_assets() -> Optional[list]:
    """Get cached Alpaca assets."""
    return get_cached("mazo:alpaca:assets")


def cache_stock_data(ticker: str, data: dict, data_type: str = "quote") -> bool:
    """Cache stock data."""
    ttl = {
        "quote": CacheTTL.STOCK_QUOTE,
        "metrics": CacheTTL.STOCK_METRICS,
        "news": CacheTTL.STOCK_NEWS,
        "financials": CacheTTL.FINANCIAL_STATEMENTS,
    }.get(data_type, CacheTTL.STOCK_QUOTE)
    
    return set_cached(f"mazo:stock:{ticker}:{data_type}", data, ttl)


def get_cached_stock_data(ticker: str, data_type: str = "quote") -> Optional[dict]:
    """Get cached stock data."""
    return get_cached(f"mazo:stock:{ticker}:{data_type}")


def cache_analysis(ticker: str, analysis_type: str, result: dict) -> bool:
    """Cache AI analysis result."""
    ttl = CacheTTL.MAZO_RESEARCH if analysis_type == "mazo" else CacheTTL.LLM_ANALYSIS
    return set_cached(f"mazo:analysis:{ticker}:{analysis_type}", result, ttl)


def get_cached_analysis(ticker: str, analysis_type: str) -> Optional[dict]:
    """Get cached AI analysis."""
    return get_cached(f"mazo:analysis:{ticker}:{analysis_type}")


def invalidate_ticker_cache(ticker: str) -> int:
    """Invalidate all cache entries for a ticker."""
    return delete_cached(f"stock:{ticker}") + delete_cached(f"analysis:{ticker}")


def get_cache_stats() -> dict:
    """Get cache statistics."""
    client = get_redis_client()
    if client is None:
        return {"status": "disconnected"}
    
    try:
        info = client.info("stats")
        keys = client.keys("mazo:*")
        return {
            "status": "connected",
            "total_keys": len(keys),
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_rate": round(
                info.get("keyspace_hits", 0) / 
                max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0)) * 100,
                1
            ),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
