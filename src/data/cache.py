"""
Redis-backed cache for API responses.

Provides persistent caching across container restarts using Redis.
Falls back to in-memory cache if Redis is unavailable.
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Try to import redis, fall back gracefully if not available
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not installed, using in-memory cache only")


class RedisCache:
    """Redis-backed cache for API responses with automatic fallback to in-memory."""
    
    # Cache TTL in seconds (24 hours for most data, 1 hour for prices)
    TTL_PRICES = 3600  # 1 hour - prices change frequently
    TTL_METRICS = 86400  # 24 hours - financial metrics are quarterly
    TTL_NEWS = 3600  # 1 hour - news is time-sensitive
    TTL_INSIDER = 86400  # 24 hours - insider trades are infrequent
    TTL_LINE_ITEMS = 86400  # 24 hours - line items are quarterly
    
    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._in_memory_fallback: Dict[str, Any] = {}
        self._connect_redis()
    
    def _connect_redis(self):
        """Connect to Redis server."""
        if not REDIS_AVAILABLE:
            return
        
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        
        try:
            self._redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            self._redis_client.ping()
            logger.info(f"Connected to Redis cache at {redis_url}")
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}. Using in-memory fallback.")
            self._redis_client = None
    
    def _get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        if self._redis_client:
            try:
                data = self._redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.debug(f"Redis get error for {key}: {e}")
        
        # Fallback to in-memory
        return self._in_memory_fallback.get(key)
    
    def _set(self, key: str, value: Any, ttl: int = 3600):
        """Set a value in cache with TTL."""
        # Always update in-memory fallback
        self._in_memory_fallback[key] = value
        
        if self._redis_client:
            try:
                self._redis_client.setex(key, ttl, json.dumps(value))
            except Exception as e:
                logger.debug(f"Redis set error for {key}: {e}")
    
    def _merge_data(self, existing: Optional[List[Dict]], new_data: List[Dict], key_field: str) -> List[Dict]:
        """Merge existing and new data, avoiding duplicates based on a key field."""
        if not existing:
            return new_data
        
        # Create a set of existing keys for O(1) lookup
        existing_keys = {item.get(key_field) for item in existing if item.get(key_field)}
        
        # Only add items that don't exist yet
        merged = existing.copy()
        merged.extend([item for item in new_data if item.get(key_field) not in existing_keys])
        return merged
    
    # === Prices ===
    def get_prices(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached price data if available."""
        return self._get(f"prices:{cache_key}")
    
    def set_prices(self, cache_key: str, data: List[Dict[str, Any]]):
        """Cache price data."""
        existing = self.get_prices(cache_key)
        merged = self._merge_data(existing, data, key_field="time")
        self._set(f"prices:{cache_key}", merged, self.TTL_PRICES)
    
    # === Financial Metrics ===
    def get_financial_metrics(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached financial metrics if available."""
        return self._get(f"metrics:{cache_key}")
    
    def set_financial_metrics(self, cache_key: str, data: List[Dict[str, Any]]):
        """Cache financial metrics."""
        existing = self.get_financial_metrics(cache_key)
        merged = self._merge_data(existing, data, key_field="report_period")
        self._set(f"metrics:{cache_key}", merged, self.TTL_METRICS)
    
    # === Line Items ===
    def get_line_items(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached line items if available."""
        return self._get(f"line_items:{cache_key}")
    
    def set_line_items(self, cache_key: str, data: List[Dict[str, Any]]):
        """Cache line items."""
        existing = self.get_line_items(cache_key)
        merged = self._merge_data(existing, data, key_field="report_period")
        self._set(f"line_items:{cache_key}", merged, self.TTL_LINE_ITEMS)
    
    # === Insider Trades ===
    def get_insider_trades(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached insider trades if available."""
        return self._get(f"insider:{cache_key}")
    
    def set_insider_trades(self, cache_key: str, data: List[Dict[str, Any]]):
        """Cache insider trades."""
        existing = self.get_insider_trades(cache_key)
        merged = self._merge_data(existing, data, key_field="filing_date")
        self._set(f"insider:{cache_key}", merged, self.TTL_INSIDER)
    
    # === Company News ===
    def get_company_news(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached company news if available."""
        return self._get(f"news:{cache_key}")
    
    def set_company_news(self, cache_key: str, data: List[Dict[str, Any]]):
        """Cache company news."""
        existing = self.get_company_news(cache_key)
        merged = self._merge_data(existing, data, key_field="date")
        self._set(f"news:{cache_key}", merged, self.TTL_NEWS)
    
    # === Cache Stats ===
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "backend": "redis" if self._redis_client else "in_memory",
            "in_memory_keys": len(self._in_memory_fallback),
        }
        
        if self._redis_client:
            try:
                info = self._redis_client.info("memory")
                stats["redis_used_memory"] = info.get("used_memory_human", "unknown")
                stats["redis_keys"] = self._redis_client.dbsize()
            except:
                pass
        
        return stats
    
    def clear(self):
        """Clear all cached data."""
        self._in_memory_fallback.clear()
        if self._redis_client:
            try:
                # Only clear our prefixed keys, not all of Redis
                for prefix in ["prices:", "metrics:", "line_items:", "insider:", "news:"]:
                    for key in self._redis_client.scan_iter(f"{prefix}*"):
                        self._redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Could not clear Redis cache: {e}")


# Backward compatibility alias
Cache = RedisCache

# Global cache instance
_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache


def reset_cache():
    """Reset the global cache instance (for testing)."""
    global _cache
    if _cache:
        _cache.clear()
    _cache = None
