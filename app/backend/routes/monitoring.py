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
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        query = """
            SELECT 
                workflow_id::text as id,
                workflow_type,
                step_name,
                status,
                started_at,
                completed_at,
                duration_ms,
                tickers,
                mode
            FROM workflow_events
            ORDER BY started_at DESC
            LIMIT :limit
        """
        
        with engine.connect() as conn:
            result = conn.execute(text(query), {"limit": limit})
            rows = result.fetchall()
        
        if not rows:
            return {"workflows": [], "message": "No workflows recorded yet"}
        
        workflows = []
        for row in rows:
            workflows.append({
                "id": row[0],
                "workflow_type": row[1],
                "step_name": row[2],
                "status": row[3],
                "started_at": row[4].isoformat() if row[4] else None,
                "completed_at": row[5].isoformat() if row[5] else None,
                "duration_ms": row[6],
                "tickers": row[7],
                "mode": row[8],
            })
        
        return {"workflows": workflows, "total": len(workflows)}
        
    except Exception as e:
        logger.error(f"Failed to get workflows: {e}")
        return {"workflows": [], "error": str(e)}


@router.get("/workflows/{workflow_id}")
async def get_workflow_detail(workflow_id: str):
    """Get detailed workflow execution with all steps."""
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        # Get workflow events
        workflow_query = """
            SELECT 
                workflow_id::text, workflow_type, step_name, status,
                started_at, completed_at, duration_ms, tickers, mode, error_message
            FROM workflow_events
            WHERE workflow_id::text = :workflow_id
            ORDER BY started_at
        """
        
        # Get agent signals for this workflow
        signals_query = """
            SELECT 
                agent_id, ticker, signal, confidence, reasoning
            FROM agent_signals
            WHERE workflow_id::text = :workflow_id
            ORDER BY agent_id
        """
        
        # Get PM decisions for this workflow
        pm_query = """
            SELECT 
                ticker, decision, confidence, reasoning, agents_received
            FROM pm_decisions
            WHERE workflow_id::text = :workflow_id
        """
        
        with engine.connect() as conn:
            workflow_result = conn.execute(text(workflow_query), {"workflow_id": workflow_id})
            workflow_rows = workflow_result.fetchall()
            
            signals_result = conn.execute(text(signals_query), {"workflow_id": workflow_id})
            signal_rows = signals_result.fetchall()
            
            pm_result = conn.execute(text(pm_query), {"workflow_id": workflow_id})
            pm_rows = pm_result.fetchall()
        
        if not workflow_rows:
            return {"error": "Workflow not found", "workflow_id": workflow_id}
        
        # Build response
        events = []
        for row in workflow_rows:
            events.append({
                "step_name": row[2],
                "status": row[3],
                "started_at": row[4].isoformat() if row[4] else None,
                "completed_at": row[5].isoformat() if row[5] else None,
                "duration_ms": row[6],
                "error_message": row[9],
            })
        
        signals = []
        for row in signal_rows:
            signals.append({
                "agent_id": row[0],
                "ticker": row[1],
                "signal": row[2],
                "confidence": float(row[3]) if row[3] else None,
                "reasoning": row[4][:200] if row[4] else None,  # Truncate for display
            })
        
        decisions = []
        for row in pm_rows:
            decisions.append({
                "ticker": row[0],
                "decision": row[1],
                "confidence": float(row[2]) if row[2] else None,
                "reasoning": row[3][:200] if row[3] else None,
                "agents_received": row[4],
            })
        
        first_row = workflow_rows[0]
        return {
            "workflow_id": workflow_id,
            "workflow_type": first_row[1],
            "tickers": first_row[7],
            "mode": first_row[8],
            "events": events,
            "agent_signals": signals,
            "pm_decisions": decisions,
        }
        
    except Exception as e:
        logger.error(f"Failed to get workflow detail: {e}")
        return {"error": str(e), "workflow_id": workflow_id}


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
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        query = """
            SELECT 
                id,
                order_id,
                ticker,
                side,
                order_type,
                quantity,
                filled_qty,
                filled_avg_price,
                status,
                submitted_at,
                filled_at,
                reject_reason,
                slippage_bps
            FROM trade_executions
            WHERE 1=1
        """
        params = {"limit": limit}
        
        if ticker:
            query += " AND ticker = :ticker"
            params["ticker"] = ticker
        if status:
            query += " AND status = :status"
            params["status"] = status
        
        query += " ORDER BY submitted_at DESC LIMIT :limit"
        
        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            rows = result.fetchall()
        
        if not rows:
            return {"trades": [], "message": "No trades recorded yet"}
        
        trades = []
        for row in rows:
            trades.append({
                "id": row[0],
                "order_id": row[1],
                "ticker": row[2],
                "side": row[3],
                "order_type": row[4],
                "quantity": float(row[5]) if row[5] else 0,
                "filled_qty": float(row[6]) if row[6] else None,
                "filled_avg_price": float(row[7]) if row[7] else None,
                "status": row[8],
                "submitted_at": row[9].isoformat() if row[9] else None,
                "filled_at": row[10].isoformat() if row[10] else None,
                "reject_reason": row[11],
                "slippage_bps": float(row[12]) if row[12] else None,
            })
        
        return {"trades": trades, "total": len(trades)}
        
    except Exception as e:
        logger.error(f"Failed to get trades: {e}")
        return {"trades": [], "error": str(e)}


@router.get("/trades/{order_id}")
async def get_trade_detail(order_id: str):
    """Get full trade detail with decision chain."""
    # TODO: Implement when database is populated
    return {
        "message": "Trade detail will be available once monitoring data is collected",
        "order_id": order_id,
    }
