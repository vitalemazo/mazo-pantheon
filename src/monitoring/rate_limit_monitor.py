"""
Rate Limit Monitor

Real-time tracking of API quota usage across all APIs.

Features:
- Track calls made per API
- Track remaining quota
- Calculate utilization percentage
- Alert when approaching limits
- Persist tracking data to TimescaleDB
"""

import logging
import os
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

from .event_logger import get_event_logger
from .alerting import get_alert_manager, AlertPriority, AlertCategory

logger = logging.getLogger(__name__)


@dataclass
class APIQuotaStatus:
    """Current quota status for an API"""
    api_name: str
    calls_made: int = 0
    calls_remaining: Optional[int] = None
    limit: Optional[int] = None
    window_start: Optional[datetime] = None
    window_resets_at: Optional[datetime] = None
    last_call_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    consecutive_errors: int = 0
    
    @property
    def utilization_pct(self) -> float:
        """Calculate utilization percentage."""
        if self.limit and self.limit > 0:
            return (self.calls_made / self.limit) * 100
        if self.calls_remaining is not None and self.calls_made > 0:
            total = self.calls_made + self.calls_remaining
            return (self.calls_made / total) * 100
        return 0.0


class RateLimitMonitor:
    """
    Monitors rate limit usage across all APIs.
    
    Usage:
        monitor = get_rate_limit_monitor()
        
        # Before API call
        if monitor.can_call("openai"):
            # Make call
            response = api.call()
            
            # After API call
            monitor.record_call(
                "openai",
                success=True,
                rate_limit_remaining=response.headers.get("x-ratelimit-remaining")
            )
    """
    
    # Default rate limits (requests per minute)
    DEFAULT_LIMITS = {
        "financial_datasets": 60,  # ~1 per second
        "openai": 500,
        "openai_proxy": 500,  # Custom proxy (e.g., xcmfai)
        "anthropic": 60,
        "alpaca": 200,  # Trading API
        "alpaca_data": 200,  # Market Data API (separate endpoint)
    }
    
    def __init__(self):
        self.event_logger = get_event_logger()
        self.alert_manager = get_alert_manager()
        
        self._quotas: Dict[str, APIQuotaStatus] = {}
        self._lock = Lock()
        
        # Initialize known APIs
        for api_name, limit in self.DEFAULT_LIMITS.items():
            self._quotas[api_name] = APIQuotaStatus(
                api_name=api_name,
                limit=limit,
                window_start=datetime.now(timezone.utc),
            )
    
    def record_call(
        self,
        api_name: str,
        success: bool = True,
        rate_limit_remaining: int = None,
        rate_limit_reset: datetime = None,
        latency_ms: int = None,
    ):
        """
        Record an API call.
        
        Args:
            api_name: Name of the API
            success: Whether the call succeeded
            rate_limit_remaining: Remaining quota from response headers
            rate_limit_reset: When quota resets from response headers
            latency_ms: Call latency in milliseconds
        """
        with self._lock:
            if api_name not in self._quotas:
                self._quotas[api_name] = APIQuotaStatus(
                    api_name=api_name,
                    window_start=datetime.now(timezone.utc),
                )
            
            quota = self._quotas[api_name]
            
            # Auto-reset window after 1 minute
            now = datetime.now(timezone.utc)
            if quota.window_start:
                elapsed = (now - quota.window_start).total_seconds()
                if elapsed >= 60:  # 1 minute window
                    quota.calls_made = 0
                    quota.window_start = now
                    quota.consecutive_errors = 0
                    logger.debug(f"Auto-reset rate limit window for {api_name} after {elapsed:.0f}s")
            
            quota.calls_made += 1
            quota.last_call_at = now
            
            if rate_limit_remaining is not None:
                quota.calls_remaining = rate_limit_remaining
            
            if rate_limit_reset:
                quota.window_resets_at = rate_limit_reset
            
            if success:
                quota.consecutive_errors = 0
            else:
                quota.consecutive_errors += 1
                quota.last_error_at = datetime.now(timezone.utc)
            
            # Check for alerts
            utilization = quota.utilization_pct
            if utilization > 0:
                self.alert_manager.alert_rate_limit(
                    api_name=api_name,
                    utilization_pct=utilization,
                    remaining=quota.calls_remaining,
                )
            
            # Log to database
            self.event_logger.log_rate_limit(
                api_name=api_name,
                calls_made=quota.calls_made,
                calls_remaining=quota.calls_remaining,
                window_start=quota.window_start,
                window_resets_at=quota.window_resets_at,
                utilization_pct=utilization,
            )
            
            # Log system health
            self.event_logger.log_system_health(
                service=api_name,
                status="healthy" if success else "degraded",
                latency_ms=latency_ms,
                rate_limit_remaining=quota.calls_remaining,
                rate_limit_reset_at=quota.window_resets_at,
            )
    
    def record_rate_limit_hit(self, api_name: str, retry_after: int = None):
        """Record a rate limit error (429)."""
        with self._lock:
            if api_name not in self._quotas:
                self._quotas[api_name] = APIQuotaStatus(api_name=api_name)
            
            quota = self._quotas[api_name]
            quota.calls_remaining = 0
            quota.consecutive_errors += 1
            quota.last_error_at = datetime.now(timezone.utc)
            
            # Always alert on rate limit hit
            self.alert_manager.create_alert(
                priority=AlertPriority.P1,
                category=AlertCategory.RATE_LIMIT,
                title=f"{api_name} rate limit hit (429)",
                details={
                    "api": api_name,
                    "retry_after": retry_after,
                    "consecutive_errors": quota.consecutive_errors,
                },
                service=api_name,
            )
    
    def can_call(self, api_name: str, threshold_pct: float = 95) -> bool:
        """
        Check if it's safe to make an API call.
        
        Args:
            api_name: Name of the API
            threshold_pct: Don't call if utilization is above this
            
        Returns:
            True if safe to call, False if should wait
        """
        with self._lock:
            if api_name not in self._quotas:
                return True
            
            quota = self._quotas[api_name]
            
            # Check remaining quota if known
            if quota.calls_remaining is not None and quota.calls_remaining <= 0:
                return False
            
            # Check utilization
            if quota.utilization_pct >= threshold_pct:
                return False
            
            return True
    
    def get_status(self, api_name: str) -> Optional[APIQuotaStatus]:
        """Get current quota status for an API."""
        return self._quotas.get(api_name)
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all tracked APIs."""
        with self._lock:
            now = datetime.now(timezone.utc)
            result = {}
            
            for name, quota in self._quotas.items():
                # Auto-reset window if expired
                if quota.window_start:
                    elapsed = (now - quota.window_start).total_seconds()
                    if elapsed >= 60:  # 1 minute window
                        quota.calls_made = 0
                        quota.window_start = now
                        quota.consecutive_errors = 0
                
                result[name] = {
                    "calls_made": quota.calls_made,
                    "calls_remaining": quota.calls_remaining,
                    "limit": quota.limit,
                    "utilization_pct": quota.utilization_pct,
                    "last_call_at": quota.last_call_at.isoformat() if quota.last_call_at else None,
                    "consecutive_errors": quota.consecutive_errors,
                }
            
            return result
    
    def reset_window(self, api_name: str):
        """Reset the tracking window for an API (e.g., when quota resets)."""
        with self._lock:
            if api_name in self._quotas:
                quota = self._quotas[api_name]
                quota.calls_made = 0
                quota.window_start = datetime.now(timezone.utc)
                quota.consecutive_errors = 0
                logger.info(f"Reset rate limit window for {api_name}")


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_rate_limit_monitor: Optional[RateLimitMonitor] = None


def get_rate_limit_monitor() -> RateLimitMonitor:
    """Get the global RateLimitMonitor instance."""
    global _rate_limit_monitor
    if _rate_limit_monitor is None:
        _rate_limit_monitor = RateLimitMonitor()
    return _rate_limit_monitor


def reset_rate_limit_monitor():
    """Reset the global RateLimitMonitor instance (for testing)."""
    global _rate_limit_monitor
    _rate_limit_monitor = None
