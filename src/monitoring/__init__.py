"""
Monitoring Package

Provides comprehensive logging, alerting, and analytics for the trading system.

Components:
- EventLogger: Central logging service for all trading events
- AlertManager: Priority-based alerting system
- RateLimitMonitor: Real-time API quota tracking
- HealthChecker: Pre-market and continuous health checks
- Analytics: Metrics calculation and aggregation
"""

from .event_logger import EventLogger, get_event_logger, timed_operation
from .alerting import AlertManager, AlertPriority, AlertCategory, get_alert_manager
from .rate_limit_monitor import RateLimitMonitor, get_rate_limit_monitor
from .health_check import (
    HealthChecker, HealthReport, HealthStatus, 
    get_health_checker, run_pre_market_health_check, run_continuous_health_check
)
from .analytics import AnalyticsService, get_analytics_service

__all__ = [
    # Event Logger
    "EventLogger",
    "get_event_logger",
    "timed_operation",
    
    # Alerting
    "AlertManager",
    "AlertPriority",
    "AlertCategory",
    "get_alert_manager",
    
    # Rate Limit Monitor
    "RateLimitMonitor",
    "get_rate_limit_monitor",
    
    # Health Check
    "HealthChecker",
    "HealthReport",
    "HealthStatus",
    "get_health_checker",
    "run_pre_market_health_check",
    "run_continuous_health_check",
    
    # Analytics
    "AnalyticsService",
    "get_analytics_service",
]
