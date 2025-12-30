"""
Monitoring API Routes

API endpoints for querying monitoring data, alerts, system health,
and performance metrics.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AlertResponse(BaseModel):
    """Alert response model"""
    id: str
    timestamp: str
    priority: str
    category: str
    title: str
    details: Optional[Dict] = None
    acknowledged: bool = False
    resolved: bool = False


class HealthCheckResponse(BaseModel):
    """Health check response model"""
    timestamp: str
    overall_status: str
    failures: List[str] = []
    warnings: List[str] = []
    checks: Dict[str, Dict] = {}


class SystemStatusResponse(BaseModel):
    """System status response model"""
    scheduler: Dict[str, Any]
    redis: Dict[str, Any]
    database: Dict[str, Any]
    rate_limits: Dict[str, Dict[str, Any]]


class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response model"""
    date: str
    workflows_run: int = 0
    signals_generated: int = 0
    trades_executed: int = 0
    win_rate: float = 0.0
    avg_pipeline_latency_ms: float = 0.0
    avg_llm_latency_ms: float = 0.0


class AgentPerformanceResponse(BaseModel):
    """Agent performance response model"""
    agent_id: str
    total_signals: int = 0
    accuracy: float = 0.0
    avg_confidence: float = 0.0
    bullish_signals: int = 0
    bearish_signals: int = 0


# =============================================================================
# ALERTS ENDPOINTS
# =============================================================================

@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    priority: Optional[str] = Query(None, description="Filter by priority (P0, P1, P2)"),
    resolved: Optional[bool] = Query(False, description="Include resolved alerts"),
    limit: int = Query(50, ge=1, le=500),
):
    """Get active alerts."""
    try:
        from src.monitoring import get_alert_manager, AlertPriority
        
        alert_manager = get_alert_manager()
        
        if priority:
            try:
                priority_filter = AlertPriority(priority)
            except ValueError:
                raise HTTPException(400, f"Invalid priority: {priority}")
            alerts = alert_manager.get_active_alerts(priority=priority_filter)
        else:
            alerts = alert_manager.get_active_alerts()
        
        # Filter resolved if needed
        if not resolved:
            alerts = [a for a in alerts if not a.resolved]
        
        return [
            AlertResponse(
                id=str(a.id),
                timestamp=a.timestamp.isoformat(),
                priority=a.priority.value,
                category=a.category.value,
                title=a.title,
                details=a.details,
                acknowledged=a.acknowledged,
                resolved=a.resolved,
            )
            for a in alerts[:limit]
        ]
        
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(500, str(e))


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    try:
        from src.monitoring import get_alert_manager
        
        alert_manager = get_alert_manager()
        alert_manager.acknowledge_alert(alert_id, acknowledged_by="api")
        
        return {"status": "acknowledged", "alert_id": alert_id}
        
    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}")
        raise HTTPException(500, str(e))


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, resolution_notes: Optional[str] = None):
    """Resolve an alert."""
    try:
        from src.monitoring import get_alert_manager
        
        alert_manager = get_alert_manager()
        alert_manager.resolve_alert(alert_id, resolution_notes=resolution_notes)
        
        return {"status": "resolved", "alert_id": alert_id}
        
    except Exception as e:
        logger.error(f"Failed to resolve alert: {e}")
        raise HTTPException(500, str(e))


# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================

@router.get("/health", response_model=HealthCheckResponse)
async def get_health_status():
    """Get current system health status."""
    try:
        from src.monitoring import run_continuous_health_check
        
        report = await run_continuous_health_check()
        
        return HealthCheckResponse(
            timestamp=report.timestamp.isoformat(),
            overall_status=report.overall_status,
            failures=report.failures,
            warnings=report.warnings,
            checks={
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "value": check.value,
                    "latency_ms": check.latency_ms,
                }
                for name, check in report.checks.items()
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get health status: {e}")
        raise HTTPException(500, str(e))


@router.post("/health/pre-market")
async def run_pre_market_check():
    """Run comprehensive pre-market health check."""
    try:
        from src.monitoring import run_pre_market_health_check
        
        report = await run_pre_market_health_check()
        
        return HealthCheckResponse(
            timestamp=report.timestamp.isoformat(),
            overall_status=report.overall_status,
            failures=report.failures,
            warnings=report.warnings,
            checks={
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "value": check.value,
                    "latency_ms": check.latency_ms,
                }
                for name, check in report.checks.items()
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to run pre-market check: {e}")
        raise HTTPException(500, str(e))


# =============================================================================
# SYSTEM STATUS ENDPOINTS
# =============================================================================

@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status():
    """Get comprehensive system status including rate limits."""
    try:
        from src.monitoring import get_rate_limit_monitor, get_health_checker
        from src.data.cache import get_cache
        
        # Rate limits
        rate_monitor = get_rate_limit_monitor()
        rate_limits = rate_monitor.get_all_status()
        
        # Cache status
        cache = get_cache()
        cache_stats = cache.get_stats()
        
        # Scheduler status (basic)
        scheduler_status = {
            "status": "unknown",
            "message": "Check logs for scheduler status",
        }
        
        # Database status (basic)
        db_status = {
            "status": "unknown",
            "message": "Run health check for full status",
        }
        
        return SystemStatusResponse(
            scheduler=scheduler_status,
            redis={
                "status": "healthy" if cache_stats.get("backend") == "redis" else "degraded",
                "backend": cache_stats.get("backend", "unknown"),
                "keys": cache_stats.get("redis_keys", 0),
                "memory": cache_stats.get("redis_used_memory", "unknown"),
            },
            database=db_status,
            rate_limits=rate_limits,
        )
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(500, str(e))


@router.get("/system/rate-limits")
async def get_rate_limits():
    """Get current rate limit status for all APIs."""
    try:
        from src.monitoring import get_rate_limit_monitor
        
        monitor = get_rate_limit_monitor()
        return monitor.get_all_status()
        
    except Exception as e:
        logger.error(f"Failed to get rate limits: {e}")
        raise HTTPException(500, str(e))


# =============================================================================
# PERFORMANCE METRICS ENDPOINTS
# =============================================================================

@router.get("/metrics/daily", response_model=PerformanceMetricsResponse)
async def get_daily_metrics(
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
):
    """Get daily performance metrics."""
    try:
        from src.monitoring import get_analytics_service
        
        if target_date:
            try:
                dt = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")
        else:
            dt = date.today()
        
        analytics = get_analytics_service()
        summary = await analytics.get_daily_summary(dt)
        
        if summary:
            return PerformanceMetricsResponse(
                date=summary.date.isoformat(),
                workflows_run=summary.workflows_run,
                signals_generated=summary.signals_generated,
                trades_executed=summary.trades_executed,
                win_rate=summary.win_rate,
                avg_pipeline_latency_ms=summary.avg_pipeline_latency_ms,
                avg_llm_latency_ms=summary.avg_llm_latency_ms,
            )
        else:
            return PerformanceMetricsResponse(date=dt.isoformat())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get daily metrics: {e}")
        raise HTTPException(500, str(e))


@router.get("/metrics/agents", response_model=List[AgentPerformanceResponse])
async def get_agent_performance(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    agent_id: Optional[str] = Query(None, description="Filter by specific agent"),
):
    """Get agent performance metrics."""
    try:
        from src.monitoring import get_analytics_service
        
        analytics = get_analytics_service()
        metrics = await analytics.get_agent_performance(days=days, agent_id=agent_id)
        
        return [
            AgentPerformanceResponse(
                agent_id=m.agent_id,
                total_signals=m.total_signals,
                accuracy=m.accuracy,
                avg_confidence=m.avg_confidence,
                bullish_signals=m.bullish_signals,
                bearish_signals=m.bearish_signals,
            )
            for m in metrics.values()
        ]
        
    except Exception as e:
        logger.error(f"Failed to get agent performance: {e}")
        raise HTTPException(500, str(e))


@router.get("/metrics/mazo")
async def get_mazo_effectiveness(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
):
    """Get Mazo research effectiveness metrics."""
    try:
        from src.monitoring import get_analytics_service
        
        analytics = get_analytics_service()
        metrics = await analytics.get_mazo_effectiveness(days=days)
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get Mazo metrics: {e}")
        raise HTTPException(500, str(e))


@router.get("/metrics/execution")
async def get_execution_quality(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
):
    """Get trade execution quality metrics."""
    try:
        from src.monitoring import get_analytics_service
        
        analytics = get_analytics_service()
        metrics = await analytics.get_execution_quality(days=days)
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get execution quality: {e}")
        raise HTTPException(500, str(e))


# =============================================================================
# DAILY REPORT ENDPOINT
# =============================================================================

@router.get("/report/daily")
async def get_daily_report(
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
):
    """Get comprehensive daily report."""
    try:
        from src.monitoring import get_analytics_service
        
        if target_date:
            try:
                dt = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")
        else:
            dt = date.today()
        
        analytics = get_analytics_service()
        report = await analytics.generate_daily_report(dt)
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate daily report: {e}")
        raise HTTPException(500, str(e))


# =============================================================================
# WORKFLOW HISTORY ENDPOINTS
# =============================================================================

@router.get("/workflows")
async def get_recent_workflows(
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Get recent workflow executions."""
    # TODO: Implement when database is populated
    return {
        "message": "Workflow history will be available once monitoring data is collected",
        "workflows": []
    }


@router.get("/workflows/{workflow_id}")
async def get_workflow_detail(workflow_id: str):
    """Get detailed workflow execution with all steps."""
    # TODO: Implement when database is populated
    return {
        "message": "Workflow detail will be available once monitoring data is collected",
        "workflow_id": workflow_id,
    }


# =============================================================================
# TRADE JOURNAL ENDPOINTS
# =============================================================================

@router.get("/trades")
async def get_trade_journal(
    limit: int = Query(50, ge=1, le=500),
    ticker: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """Get trade journal with execution details."""
    # TODO: Implement when database is populated
    return {
        "message": "Trade journal will be available once monitoring data is collected",
        "trades": []
    }


@router.get("/trades/{order_id}")
async def get_trade_detail(order_id: str):
    """Get full trade detail with decision chain."""
    # TODO: Implement when database is populated
    return {
        "message": "Trade detail will be available once monitoring data is collected",
        "order_id": order_id,
    }
