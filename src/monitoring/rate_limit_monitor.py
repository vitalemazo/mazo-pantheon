"""
Rate Limit Monitor

Real-time tracking of API quota usage across all APIs.

Features:
- Track calls made per API
- Track remaining quota
- Calculate utilization percentage
- Alert when approaching limits
- Persist tracking data to TimescaleDB
- Track call activity by type with ring buffer history
"""

import logging
import os
import time
from collections import deque, defaultdict
from datetime import datetime, timezone, timedelta
from threading import Lock
from typing import Dict, Optional, Any, List, Deque, Tuple
from dataclasses import dataclass, field

from .event_logger import get_event_logger
from .alerting import get_alert_manager, AlertPriority, AlertCategory

logger = logging.getLogger(__name__)


# =============================================================================
# CALL ACTIVITY TRACKING
# =============================================================================

@dataclass
class CallEvent:
    """A single API call event for activity tracking."""
    api_name: str
    call_type: str
    timestamp: datetime
    success: bool = True
    latency_ms: Optional[int] = None


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
            
            # After API call - now with call_type for activity tracking
            monitor.record_call(
                "openai",
                call_type="chat_completion",  # NEW: specific call type
                success=True,
                rate_limit_remaining=response.headers.get("x-ratelimit-remaining")
            )
    """
    
    # Default rate limits (requests per minute)
    DEFAULT_LIMITS = {
        "fmp_data": 300,  # FMP Ultimate - generous limits
        "financial_datasets": 60,  # ~1 per second
        "openai": 500,
        "openai_proxy": 500,  # Custom proxy (e.g., xcmfai)
        "anthropic": 60,
        "alpaca": 200,  # Trading API
        "alpaca_data": 200,  # Market Data API (separate endpoint)
    }
    
    # Max events to keep in ring buffer (bounded memory)
    MAX_CALL_HISTORY = 1000
    
    # Default activity window in minutes
    DEFAULT_ACTIVITY_WINDOW_MINUTES = 60
    
    def __init__(self):
        self.event_logger = get_event_logger()
        self.alert_manager = get_alert_manager()
        
        self._quotas: Dict[str, APIQuotaStatus] = {}
        self._lock = Lock()
        
        # Ring buffer for call events (bounded memory)
        self._call_history: Deque[CallEvent] = deque(maxlen=self.MAX_CALL_HISTORY)
        
        # Precomputed counts per (api_name, call_type) for fast lookups
        # These are rolling counts that get recalculated periodically
        self._activity_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._last_activity_recount: Optional[datetime] = None
        
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
        call_type: str = "general",
        success: bool = True,
        rate_limit_remaining: int = None,
        rate_limit_reset: datetime = None,
        latency_ms: int = None,
    ):
        """
        Record an API call with call type tracking.
        
        Args:
            api_name: Name of the API (e.g., "alpaca", "openai_proxy")
            call_type: Type of call (e.g., "orders", "account", "chat_completion")
            success: Whether the call succeeded
            rate_limit_remaining: Remaining quota from response headers
            rate_limit_reset: When quota resets from response headers
            latency_ms: Call latency in milliseconds
        """
        now = datetime.now(timezone.utc)
        
        with self._lock:
            if api_name not in self._quotas:
                self._quotas[api_name] = APIQuotaStatus(
                    api_name=api_name,
                    window_start=now,
                )
            
            quota = self._quotas[api_name]
            
            # Auto-reset window after 1 minute
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
                quota.last_error_at = now
            
            # --- NEW: Track call event in ring buffer ---
            event = CallEvent(
                api_name=api_name,
                call_type=call_type,
                timestamp=now,
                success=success,
                latency_ms=latency_ms,
            )
            self._call_history.append(event)
            
            # Increment precomputed count
            self._activity_counts[api_name][call_type] += 1
            
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
                last_call_at=quota.last_call_at,
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
    
    def get_call_activity(
        self,
        window_minutes: int = None,
    ) -> Dict[str, Any]:
        """
        Get call activity summary for the specified time window.
        
        This is the main method for the /monitoring/rate-limits/activity endpoint.
        Returns per-provider breakdown of call counts by type.
        
        Args:
            window_minutes: Time window in minutes (default: 60)
            
        Returns:
            {
                "window_minutes": 60,
                "total_calls": 150,
                "providers": {
                    "alpaca": {
                        "total": 62,
                        "by_type": {"orders": 40, "account": 12, "positions": 10},
                        "display": "Alpaca Trading – 62 calls (orders 40, account 12, positions 10)"
                    },
                    ...
                },
                "recent_events": [
                    {"api": "alpaca", "type": "orders", "time": "14:32:15", "success": true},
                    ...
                ]
            }
        """
        if window_minutes is None:
            window_minutes = self.DEFAULT_ACTIVITY_WINDOW_MINUTES
            
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=window_minutes)
        
        with self._lock:
            # Filter events within window
            events_in_window: List[CallEvent] = [
                e for e in self._call_history
                if e.timestamp >= cutoff
            ]
            
            # Aggregate by provider and call type
            providers: Dict[str, Dict[str, Any]] = {}
            
            for event in events_in_window:
                api = event.api_name
                if api not in providers:
                    providers[api] = {
                        "total": 0,
                        "by_type": defaultdict(int),
                        "errors": 0,
                    }
                
                providers[api]["total"] += 1
                providers[api]["by_type"][event.call_type] += 1
                if not event.success:
                    providers[api]["errors"] += 1
            
            # Build display strings
            for api, data in providers.items():
                by_type_str = ", ".join(
                    f"{t} {c}" for t, c in sorted(data["by_type"].items(), key=lambda x: -x[1])
                )
                display_name = self._get_display_name(api)
                data["display"] = f"{display_name} – {data['total']} calls ({by_type_str})"
                # Convert defaultdict to regular dict for JSON
                data["by_type"] = dict(data["by_type"])
            
            # Get recent events (last 20)
            recent = sorted(events_in_window, key=lambda e: e.timestamp, reverse=True)[:20]
            recent_events = [
                {
                    "api": e.api_name,
                    "type": e.call_type,
                    "time": e.timestamp.strftime("%H:%M:%S"),
                    "timestamp": e.timestamp.isoformat(),
                    "success": e.success,
                    "latency_ms": e.latency_ms,
                }
                for e in recent
            ]
            
            return {
                "window_minutes": window_minutes,
                "total_calls": len(events_in_window),
                "providers": providers,
                "recent_events": recent_events,
            }
    
    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get the most recent call events.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of event dicts with api, type, time, success
        """
        with self._lock:
            recent = list(self._call_history)[-limit:]
            recent.reverse()  # Most recent first
            
            return [
                {
                    "api": e.api_name,
                    "type": e.call_type,
                    "time": e.timestamp.strftime("%H:%M:%S"),
                    "timestamp": e.timestamp.isoformat(),
                    "success": e.success,
                    "latency_ms": e.latency_ms,
                }
                for e in recent
            ]
    
    def _get_display_name(self, api_name: str) -> str:
        """Get friendly display name for an API."""
        display_names = {
            "fmp_data": "FMP Ultimate",
            "openai_proxy": "OpenAI Proxy",
            "openai": "OpenAI Direct",
            "anthropic": "Anthropic",
            "alpaca": "Alpaca Trading",
            "alpaca_data": "Alpaca Market Data",
            "financial_datasets": "Financial Datasets",
        }
        return display_names.get(api_name, api_name.replace("_", " ").title())


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
