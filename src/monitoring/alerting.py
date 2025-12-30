"""
Alerting System

Priority-based alerting for critical trading system issues.

Alert Priorities:
- P0 CRITICAL: Trading blocked, immediate action required
- P1 WARNING: Trading degraded, action within 30 minutes
- P2 INFO: Potential issues, review at end of day
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field

from .event_logger import get_event_logger

logger = logging.getLogger(__name__)


class AlertPriority(Enum):
    """Alert priority levels"""
    P0 = "P0"  # Critical - trading blocked
    P1 = "P1"  # Warning - trading degraded
    P2 = "P2"  # Info - potential issues


class AlertCategory(Enum):
    """Alert categories"""
    RATE_LIMIT = "rate_limit"
    PIPELINE = "pipeline"
    EXECUTION = "execution"
    SYSTEM = "system"
    DATA = "data"
    HEALTH = "health"


@dataclass
class Alert:
    """An alert instance"""
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: AlertPriority = AlertPriority.P2
    category: AlertCategory = AlertCategory.SYSTEM
    title: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Context
    workflow_id: Optional[uuid.UUID] = None
    ticker: Optional[str] = None
    service: Optional[str] = None
    
    # Status
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "priority": self.priority.value,
            "category": self.category.value,
            "title": self.title,
            "details": self.details,
            "workflow_id": self.workflow_id,
            "ticker": self.ticker,
            "service": self.service,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
        }


# =============================================================================
# ALERT THRESHOLDS
# =============================================================================

PIPELINE_THRESHOLDS = {
    "strategy_screening": {"warning_ms": 15000, "critical_ms": 30000},
    "mazo_research": {"warning_ms": 30000, "critical_ms": 60000},
    "agent_analysis": {"warning_ms": 10000, "critical_ms": 20000},  # Per agent
    "pm_decision": {"warning_ms": 15000, "critical_ms": 30000},
    "order_execution": {"warning_ms": 5000, "critical_ms": 10000},
}

RATE_LIMIT_THRESHOLDS = {
    "warning_pct": 80,  # Alert at 80% utilization
    "critical_pct": 95,  # Critical at 95% utilization
}

EXECUTION_THRESHOLDS = {
    "rejection_rate_warning": 0.10,  # 10% rejection rate
    "slippage_warning_bps": 50,  # 50 basis points
    "fill_latency_warning_ms": 5000,  # 5 seconds for market orders
}


class AlertManager:
    """
    Manages alerts for the trading system.
    
    Features:
    - Priority-based alert creation
    - Deduplication of similar alerts
    - Notification callbacks
    - Alert persistence via EventLogger
    """
    
    def __init__(self):
        self.event_logger = get_event_logger()
        self.active_alerts: Dict[str, Alert] = {}  # key -> alert
        self.notification_handlers: List[Callable[[Alert], None]] = []
        
        # Deduplication: track recent alerts to avoid spam
        self._recent_alerts: Dict[str, datetime] = {}
        self._dedup_window_seconds = 300  # 5 minutes
    
    def add_notification_handler(self, handler: Callable[[Alert], None]):
        """Add a notification handler (e.g., Discord, email)."""
        self.notification_handlers.append(handler)
    
    def _get_alert_key(self, priority: AlertPriority, category: AlertCategory, title: str) -> str:
        """Generate a deduplication key for an alert."""
        return f"{priority.value}:{category.value}:{title}"
    
    def _should_dedupe(self, key: str) -> bool:
        """Check if we should skip this alert due to deduplication."""
        if key in self._recent_alerts:
            last_alert = self._recent_alerts[key]
            age = (datetime.now(timezone.utc) - last_alert).total_seconds()
            if age < self._dedup_window_seconds:
                return True
        return False
    
    def create_alert(
        self,
        priority: AlertPriority,
        category: AlertCategory,
        title: str,
        details: Dict = None,
        workflow_id: uuid.UUID = None,
        ticker: str = None,
        service: str = None,
        skip_dedup: bool = False,
    ) -> Optional[Alert]:
        """
        Create and log a new alert.
        
        Returns the alert if created, None if deduplicated.
        """
        key = self._get_alert_key(priority, category, title)
        
        # Check deduplication
        if not skip_dedup and self._should_dedupe(key):
            logger.debug(f"Alert deduplicated: {title}")
            return None
        
        # Create alert
        alert = Alert(
            priority=priority,
            category=category,
            title=title,
            details=details or {},
            workflow_id=workflow_id,
            ticker=ticker,
            service=service,
        )
        
        # Store in active alerts
        self.active_alerts[str(alert.id)] = alert
        self._recent_alerts[key] = alert.timestamp
        
        # Log to database
        self.event_logger._store_event("alerts", {
            "id": alert.id,
            "timestamp": alert.timestamp,
            "priority": priority.value,
            "category": category.value,
            "title": title,
            "details": details,
            "workflow_id": workflow_id,
            "ticker": ticker,
            "service": service,
            "acknowledged": False,
            "resolved": False,
        })
        
        # Log to console with appropriate level
        if priority == AlertPriority.P0:
            logger.critical(f"🚨 P0 ALERT: {title} | {details}")
        elif priority == AlertPriority.P1:
            logger.warning(f"⚠️ P1 ALERT: {title} | {details}")
        else:
            logger.info(f"ℹ️ P2 ALERT: {title} | {details}")
        
        # Notify handlers
        for handler in self.notification_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Notification handler failed: {e}")
        
        return alert
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system"):
        """Mark an alert as acknowledged."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.acknowledged = True
            alert.acknowledged_at = datetime.now(timezone.utc)
            alert.acknowledged_by = acknowledged_by
            logger.info(f"Alert acknowledged: {alert.title}")
    
    def resolve_alert(self, alert_id: str, resolution_notes: str = None):
        """Mark an alert as resolved."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.now(timezone.utc)
            alert.resolution_notes = resolution_notes
            logger.info(f"Alert resolved: {alert.title}")
            # Remove from active alerts
            del self.active_alerts[alert_id]
    
    def get_active_alerts(self, priority: AlertPriority = None) -> List[Alert]:
        """Get all active (unresolved) alerts, optionally filtered by priority."""
        alerts = list(self.active_alerts.values())
        if priority:
            alerts = [a for a in alerts if a.priority == priority]
        return sorted(alerts, key=lambda a: (a.priority.value, a.timestamp), reverse=True)
    
    # =========================================================================
    # CONVENIENCE METHODS FOR COMMON ALERTS
    # =========================================================================
    
    def alert_rate_limit(
        self,
        api_name: str,
        utilization_pct: float,
        remaining: int = None,
    ):
        """Create an alert for rate limit issues."""
        if utilization_pct >= RATE_LIMIT_THRESHOLDS["critical_pct"]:
            self.create_alert(
                priority=AlertPriority.P0,
                category=AlertCategory.RATE_LIMIT,
                title=f"{api_name} rate limit critical: {utilization_pct:.0f}%",
                details={"api": api_name, "utilization_pct": utilization_pct, "remaining": remaining},
                service=api_name,
            )
        elif utilization_pct >= RATE_LIMIT_THRESHOLDS["warning_pct"]:
            self.create_alert(
                priority=AlertPriority.P1,
                category=AlertCategory.RATE_LIMIT,
                title=f"{api_name} rate limit warning: {utilization_pct:.0f}%",
                details={"api": api_name, "utilization_pct": utilization_pct, "remaining": remaining},
                service=api_name,
            )
    
    def alert_pipeline_slow(
        self,
        stage_name: str,
        duration_ms: int,
        workflow_id: uuid.UUID = None,
        ticker: str = None,
    ):
        """Create an alert for slow pipeline stages."""
        thresholds = PIPELINE_THRESHOLDS.get(stage_name, {})
        critical_ms = thresholds.get("critical_ms", 60000)
        warning_ms = thresholds.get("warning_ms", 30000)
        
        if duration_ms >= critical_ms:
            self.create_alert(
                priority=AlertPriority.P0,
                category=AlertCategory.PIPELINE,
                title=f"Pipeline stage critically slow: {stage_name}",
                details={"stage": stage_name, "duration_ms": duration_ms, "threshold_ms": critical_ms},
                workflow_id=workflow_id,
                ticker=ticker,
            )
        elif duration_ms >= warning_ms:
            self.create_alert(
                priority=AlertPriority.P1,
                category=AlertCategory.PIPELINE,
                title=f"Pipeline stage slow: {stage_name}",
                details={"stage": stage_name, "duration_ms": duration_ms, "threshold_ms": warning_ms},
                workflow_id=workflow_id,
                ticker=ticker,
            )
    
    def alert_execution_issue(
        self,
        issue_type: str,  # rejection, slippage, latency
        ticker: str,
        order_id: str,
        value: float,
        details: Dict = None,
    ):
        """Create an alert for execution quality issues."""
        if issue_type == "rejection":
            self.create_alert(
                priority=AlertPriority.P1,
                category=AlertCategory.EXECUTION,
                title=f"Order rejected: {ticker}",
                details={"order_id": order_id, "reason": details.get("reason", "unknown"), **(details or {})},
                ticker=ticker,
            )
        elif issue_type == "slippage" and value > EXECUTION_THRESHOLDS["slippage_warning_bps"]:
            self.create_alert(
                priority=AlertPriority.P2,
                category=AlertCategory.EXECUTION,
                title=f"High slippage on {ticker}: {value:.0f} bps",
                details={"order_id": order_id, "slippage_bps": value, **(details or {})},
                ticker=ticker,
            )
        elif issue_type == "latency" and value > EXECUTION_THRESHOLDS["fill_latency_warning_ms"]:
            self.create_alert(
                priority=AlertPriority.P2,
                category=AlertCategory.EXECUTION,
                title=f"Slow fill on {ticker}: {value:.0f}ms",
                details={"order_id": order_id, "latency_ms": value, **(details or {})},
                ticker=ticker,
            )
    
    def alert_system_health(
        self,
        service: str,
        issue: str,
        details: Dict = None,
    ):
        """Create an alert for system health issues."""
        critical_issues = ["auth_failed", "connection_failed", "scheduler_dead"]
        
        if issue in critical_issues:
            self.create_alert(
                priority=AlertPriority.P0,
                category=AlertCategory.SYSTEM,
                title=f"{service} critical: {issue}",
                details=details or {},
                service=service,
            )
        else:
            self.create_alert(
                priority=AlertPriority.P1,
                category=AlertCategory.SYSTEM,
                title=f"{service} issue: {issue}",
                details=details or {},
                service=service,
            )
    
    def alert_health_check_failed(
        self,
        check_type: str,  # pre_market, continuous
        failures: List[str],
        warnings: List[str],
        checks: Dict = None,
    ):
        """Create an alert for failed health checks."""
        if failures:
            self.create_alert(
                priority=AlertPriority.P0,
                category=AlertCategory.HEALTH,
                title=f"{check_type.replace('_', ' ').title()} health check FAILED",
                details={"failures": failures, "warnings": warnings, "checks": checks},
                skip_dedup=True,  # Always alert on health check failures
            )
        elif warnings:
            self.create_alert(
                priority=AlertPriority.P1,
                category=AlertCategory.HEALTH,
                title=f"{check_type.replace('_', ' ').title()} health check has warnings",
                details={"warnings": warnings, "checks": checks},
            )


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get the global AlertManager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def reset_alert_manager():
    """Reset the global AlertManager instance (for testing)."""
    global _alert_manager
    _alert_manager = None
