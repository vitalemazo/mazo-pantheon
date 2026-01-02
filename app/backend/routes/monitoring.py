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
    last_updated: Optional[str] = None  # ISO timestamp of this response


class DataFreshnessInfo(BaseModel):
    """Data freshness timestamps for metrics"""
    last_workflow_at: Optional[str] = None
    last_signal_at: Optional[str] = None
    last_trade_at: Optional[str] = None
    last_pm_decision_at: Optional[str] = None
    minutes_since_workflow: Optional[int] = None
    minutes_since_signal: Optional[int] = None
    is_stale: bool = False  # True if data is older than threshold


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
    last_signal_at: Optional[str] = None
    is_stale: bool = False  # True if last signal > 1 hour ago


# =============================================================================
# ALERTS ENDPOINTS
# =============================================================================

@router.get("/alerts")
async def get_alerts(
    priority: Optional[str] = Query(None, description="Filter by priority (P0, P1, P2)"),
    resolved: Optional[bool] = Query(False, description="Include resolved alerts"),
    limit: int = Query(50, ge=1, le=500),
):
    """Get active alerts from database."""
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        query = """
            SELECT 
                id, timestamp, priority, category, title, 
                details, acknowledged, resolved
            FROM alerts
            WHERE 1=1
        """
        params = {"limit": limit}
        
        if priority:
            query += " AND priority = :priority"
            params["priority"] = priority
        
        if not resolved:
            query += " AND resolved = false"
        
        query += " ORDER BY timestamp DESC LIMIT :limit"
        
        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            rows = result.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append({
                "id": str(row[0]),
                "timestamp": row[1].isoformat() if row[1] else None,
                "priority": row[2],
                "category": row[3],
                "title": row[4],
                "details": row[5] if isinstance(row[5], dict) else {},
                "acknowledged": row[6] or False,
                "resolved": row[7] or False,
            })
        
        return alerts
        
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        return []


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        from src.monitoring import get_alert_manager
        from datetime import datetime, timezone

        # Update in database
        import uuid as uuid_module
        try:
            alert_uuid = uuid_module.UUID(alert_id)
        except ValueError:
            raise HTTPException(400, f"Invalid alert ID format: {alert_id}")
            
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    UPDATE alerts 
                    SET acknowledged = true, 
                        acknowledged_at = :acknowledged_at,
                        acknowledged_by = 'api'
                    WHERE id = :alert_id
                    RETURNING id
                """),
                {"alert_id": str(alert_uuid), "acknowledged_at": datetime.now(timezone.utc)}
            )
            row = result.fetchone()  # Must fetch before commit in SQLAlchemy 2.0
            conn.commit()
            
            if row is None:
                raise HTTPException(404, f"Alert {alert_id} not found")

        # Also update in-memory alert manager
        alert_manager = get_alert_manager()
        alert_manager.acknowledge_alert(alert_id, acknowledged_by="api")

        return {"status": "acknowledged", "alert_id": alert_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}")
        raise HTTPException(500, str(e))


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, resolution_notes: Optional[str] = None):
    """Resolve an alert."""
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        from src.monitoring import get_alert_manager
        from datetime import datetime, timezone
        
        # Update in database
        import uuid as uuid_module
        try:
            alert_uuid = uuid_module.UUID(alert_id)
        except ValueError:
            raise HTTPException(400, f"Invalid alert ID format: {alert_id}")
            
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    UPDATE alerts 
                    SET resolved = true, 
                        resolved_at = :resolved_at,
                        resolution_notes = :resolution_notes
                    WHERE id = :alert_id
                    RETURNING id
                """),
                {
                    "alert_id": str(alert_uuid), 
                    "resolved_at": datetime.now(timezone.utc),
                    "resolution_notes": resolution_notes
                }
            )
            row = result.fetchone()  # Must fetch before commit in SQLAlchemy 2.0
            conn.commit()
            
            if row is None:
                raise HTTPException(404, f"Alert {alert_id} not found")
        
        # Also update in-memory alert manager
        alert_manager = get_alert_manager()
        alert_manager.resolve_alert(alert_id, resolution_notes=resolution_notes)
        
        return {"status": "resolved", "alert_id": alert_id}
    
    except HTTPException:
        raise
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
        from src.monitoring import get_rate_limit_monitor, get_health_checker, get_alert_manager
        from src.data.cache import get_cache
        
        # Rate limits
        rate_monitor = get_rate_limit_monitor()
        rate_limits = rate_monitor.get_all_status()
        
        # Cache status
        cache = get_cache()
        cache_stats = cache.get_stats()
        
        # Stale threshold in minutes (configurable via env)
        import os
        stale_threshold_minutes = int(os.getenv("SCHEDULER_STALE_THRESHOLD_MINUTES", "10"))
        
        # Scheduler status - check heartbeat recency
        scheduler_status = {
            "status": "unknown",
            "message": "Check logs for scheduler status",
            "last_heartbeat": None,
            "minutes_since": None,
        }
        try:
            from sqlalchemy import text
            from app.backend.database.connection import engine
            from datetime import datetime, timezone, timedelta
            
            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT MAX(timestamp) FROM scheduler_heartbeats"
                ))
                row = result.fetchone()
                if row and row[0]:
                    last_heartbeat = row[0]
                    # Ensure timezone-aware comparison
                    if last_heartbeat.tzinfo is None:
                        last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
                    age = datetime.now(timezone.utc) - last_heartbeat
                    minutes_since = int(age.total_seconds() / 60)
                    
                    if age < timedelta(minutes=stale_threshold_minutes):
                        scheduler_status = {
                            "status": "healthy",
                            "last_heartbeat": last_heartbeat.isoformat(),
                            "minutes_since": minutes_since,
                        }
                    else:
                        scheduler_status = {
                            "status": "stale",
                            "last_heartbeat": last_heartbeat.isoformat(),
                            "minutes_since": minutes_since,
                            "message": f"No heartbeat for {minutes_since} minutes",
                        }
                        # Trigger P1 alert for stale scheduler
                        try:
                            alert_manager = get_alert_manager()
                            alert_manager.alert_system_health(
                                component="scheduler",
                                status="stale",
                                message=f"Scheduler heartbeat stale for {minutes_since} minutes",
                                details={
                                    "last_heartbeat": last_heartbeat.isoformat(),
                                    "minutes_since": minutes_since,
                                    "threshold_minutes": stale_threshold_minutes,
                                }
                            )
                        except Exception as alert_err:
                            logger.debug(f"Failed to create stale alert: {alert_err}")
                else:
                    scheduler_status = {
                        "status": "no_heartbeats",
                        "message": "No heartbeats recorded",
                        "last_heartbeat": None,
                        "minutes_since": None,
                    }
        except Exception as sched_err:
            logger.debug(f"Failed to check scheduler: {sched_err}")
        
        # Database status - simple ping
        db_status = {
            "status": "unknown",
            "message": "Run health check for full status",
            "last_updated": None,
        }
        try:
            from sqlalchemy import text
            from app.backend.database.connection import engine
            import time
            
            start = time.time()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                latency = int((time.time() - start) * 1000)
                db_status = {
                    "status": "healthy",
                    "latency_ms": latency,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as db_err:
            db_status = {"status": "error", "message": str(db_err)}
        
        # Redis status with last_updated
        redis_status = {
            "status": "healthy" if cache_stats.get("backend") == "redis" else "degraded",
            "backend": cache_stats.get("backend", "unknown"),
            "keys": cache_stats.get("redis_keys", 0),
            "memory": cache_stats.get("redis_used_memory", "unknown"),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add last_updated timestamps to rate limits
        for api_name in rate_limits:
            if "last_call_at" not in rate_limits[api_name] or rate_limits[api_name]["last_call_at"] is None:
                rate_limits[api_name]["is_stale"] = True
            else:
                # Check if rate limit data is stale (> 1 hour old)
                try:
                    last_call = datetime.fromisoformat(rate_limits[api_name]["last_call_at"].replace("Z", "+00:00"))
                    age_minutes = int((datetime.now(timezone.utc) - last_call).total_seconds() / 60)
                    rate_limits[api_name]["minutes_since_update"] = age_minutes
                    rate_limits[api_name]["is_stale"] = age_minutes > 60
                except Exception:
                    rate_limits[api_name]["is_stale"] = True
        
        return SystemStatusResponse(
            scheduler=scheduler_status,
            redis=redis_status,
            database=db_status,
            rate_limits=rate_limits,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(500, str(e))


@router.get("/system/rate-limits")
async def get_rate_limits():
    """Get current rate limit status for all APIs from database."""
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        # Get latest rate limit status for each API from database
        # Uses COALESCE to prefer last_call_at column, falling back to timestamp
        query = """
            WITH latest AS (
                SELECT DISTINCT ON (api_name) 
                    api_name, calls_made, calls_remaining, 
                    utilization_pct, window_resets_at, 
                    COALESCE(last_call_at, timestamp) as last_call_at
                FROM rate_limit_tracking
                ORDER BY api_name, timestamp DESC
            )
            SELECT * FROM latest ORDER BY api_name
        """
        
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
        
        rate_limits = {}
        for row in rows:
            rate_limits[row[0]] = {
                "calls_made": row[1],
                "calls_remaining": row[2],
                "utilization_pct": round(row[3], 2) if row[3] else 0.0,
                "resets_at": row[4].isoformat() if row[4] else None,
                "last_call_at": row[5].isoformat() if row[5] else None,
            }
        
        # Add LLM call counts from llm_api_calls table
        llm_query = """
            SELECT provider, COUNT(*), AVG(latency_ms), MAX(timestamp)
            FROM llm_api_calls 
            WHERE timestamp > NOW() - INTERVAL '1 hour'
            GROUP BY provider
        """
        with engine.connect() as conn:
            llm_result = conn.execute(text(llm_query))
            llm_rows = llm_result.fetchall()
        
        for row in llm_rows:
            provider = row[0].lower()
            api_key = f"{provider}_proxy" if provider == "openai" else provider
            if api_key not in rate_limits:
                rate_limits[api_key] = {}
            rate_limits[api_key]["calls_made"] = row[1] or 0
            rate_limits[api_key]["avg_latency_ms"] = round(row[2], 2) if row[2] else None
            rate_limits[api_key]["last_call_at"] = row[3].isoformat() if row[3] else None
            rate_limits[api_key]["utilization_pct"] = min(100, (row[1] or 0) / 5)  # Estimate
        
        # Add default entries for APIs not in database yet
        default_apis = ["openai", "openai_proxy", "anthropic", "financial_datasets", "alpaca", "fmp_data", "alpaca_data"]
        for api in default_apis:
            if api not in rate_limits:
                rate_limits[api] = {
                    "calls_made": 0,
                    "calls_remaining": None,
                    "utilization_pct": 0.0,
                    "resets_at": None,
                    "last_call_at": None,
                }
        
        # Supplement with in-memory data from rate limit monitor
        try:
            from src.monitoring import get_rate_limit_monitor
            monitor = get_rate_limit_monitor()
            in_memory_status = monitor.get_all_status()
            
            for api_name, status in in_memory_status.items():
                if api_name not in rate_limits or rate_limits[api_name].get("calls_made", 0) == 0:
                    rate_limits[api_name] = {
                        "calls_made": status.get("calls_made", 0),
                        "calls_remaining": status.get("calls_remaining"),
                        "utilization_pct": round(status.get("utilization_pct", 0), 2),
                        "resets_at": status.get("window_resets_at"),
                        "last_call_at": status.get("last_call_at"),
                        "source": "in_memory",
                    }
        except Exception as e:
            logger.debug(f"Could not get in-memory rate limits: {e}")

        return rate_limits

    except Exception as e:
        logger.error(f"Failed to get rate limits: {e}")
        raise HTTPException(500, str(e))


@router.get("/rate-limits/activity")
async def get_rate_limit_activity(
    window_minutes: int = Query(60, ge=1, le=1440, description="Time window in minutes"),
    limit: int = Query(20, ge=1, le=100, description="Max recent events to return"),
):
    """
    Get API call activity summary.
    
    Returns per-provider breakdown of call counts by type and recent events.
    Useful for understanding API usage patterns and debugging surges.
    
    Response includes:
    - Total calls in window
    - Per-provider breakdown with call types
    - Display strings like "Alpaca Trading – 62 calls (orders 40, account 12)"
    - Recent call events for audit trail
    """
    try:
        from src.monitoring import get_rate_limit_monitor
        
        monitor = get_rate_limit_monitor()
        activity = monitor.get_call_activity(window_minutes=window_minutes)
        
        # Limit recent events if requested
        if len(activity.get("recent_events", [])) > limit:
            activity["recent_events"] = activity["recent_events"][:limit]
        
        return {
            "success": True,
            **activity,
        }
        
    except Exception as e:
        logger.error(f"Failed to get rate limit activity: {e}")
        raise HTTPException(500, str(e))


@router.post("/rate-limits/test-call")
async def test_rate_limit_call(
    api_name: str = Query("openai_proxy", description="API name to simulate"),
    call_type: str = Query("chat_completion", description="Call type"),
    count: int = Query(1, ge=1, le=10, description="Number of test calls to record"),
):
    """
    Record test API calls for rate limit monitoring verification.
    
    This endpoint simulates API calls being recorded without actually
    making real API calls. Useful for testing the activity dashboard.
    """
    try:
        from src.monitoring import get_rate_limit_monitor
        import random
        
        monitor = get_rate_limit_monitor()
        
        for i in range(count):
            # Simulate realistic latency
            latency = random.randint(100, 500)
            monitor.record_call(
                api_name=api_name,
                call_type=call_type,
                success=True,
                latency_ms=latency,
            )
        
        return {
            "success": True,
            "message": f"Recorded {count} test call(s) to {api_name}/{call_type}",
        }
        
    except Exception as e:
        logger.error(f"Failed to record test call: {e}")
        raise HTTPException(500, str(e))


# =============================================================================
# TRADING GUARDRAILS STATUS
# =============================================================================

@router.get("/trading/guardrails")
async def get_trading_guardrails():
    """
    Get current trading guardrails status including PDT, risk limits, and quote health.
    
    Returns:
        - pdt_status: Pattern Day Trader protection status
        - risk_limits: Current position/concentration limits status
        - quote_health: Real-time quote API health
        - config: Current guardrail configuration
    """
    try:
        import os
        from src.trading.alpaca_service import get_alpaca_service
        from src.trading.config import get_risk_config, get_fractional_config, get_intraday_config
        
        result = {
            "pdt_status": None,
            "risk_limits": None,
            "quote_health": None,
            "config": {},
            "success": True,
        }
        
        # Get PDT status from Alpaca
        try:
            alpaca = get_alpaca_service()
            pdt = alpaca.check_pdt_status()
            result["pdt_status"] = {
                "is_pdt": pdt.get("is_pdt", False),
                "daytrade_count": pdt.get("daytrade_count", 0),
                "equity": pdt.get("equity", 0),
                "can_day_trade": pdt.get("can_day_trade", True),
                "warning": pdt.get("warning"),
                "pdt_threshold": pdt.get("pdt_threshold", 25000),
            }
            
            # Check quote health with a test quote
            try:
                quote = alpaca.get_quote("SPY")
                if quote and quote.get("bid") and quote.get("ask"):
                    result["quote_health"] = {
                        "status": "healthy",
                        "last_check": datetime.now(timezone.utc).isoformat(),
                        "sample_quote": {
                            "symbol": "SPY",
                            "bid": quote.get("bid"),
                            "ask": quote.get("ask"),
                        }
                    }
                else:
                    result["quote_health"] = {
                        "status": "degraded",
                        "message": "Quote returned incomplete data",
                    }
            except Exception as qe:
                result["quote_health"] = {
                    "status": "error",
                    "message": str(qe),
                }
            
            # Get current positions for risk limit status
            try:
                positions = alpaca.get_positions()
                account = alpaca.get_account()
                risk_config = get_risk_config()
                
                # Calculate position concentration
                position_details = []
                max_concentration = 0
                for pos in positions:
                    pct = abs(float(pos.market_value)) / account.portfolio_value * 100 if account.portfolio_value > 0 else 0
                    max_concentration = max(max_concentration, pct)
                    position_details.append({
                        "symbol": pos.symbol,
                        "market_value": float(pos.market_value),
                        "concentration_pct": round(pct, 2),
                    })
                
                result["risk_limits"] = {
                    "position_count": len(positions),
                    "max_positions": risk_config.max_total_positions,
                    "positions_available": max(0, risk_config.max_total_positions - len(positions)),
                    "max_concentration_pct": round(max_concentration, 2),
                    "max_position_pct": round(risk_config.max_position_pct * 100, 1),
                    "status": "healthy" if len(positions) < risk_config.max_total_positions else "at_limit",
                }
            except Exception as re:
                result["risk_limits"] = {"status": "error", "message": str(re)}
                
        except Exception as ae:
            result["pdt_status"] = {"status": "unavailable", "message": str(ae)}
        
        # Get configuration
        try:
            risk_config = get_risk_config()
            fractional_config = get_fractional_config()
            intraday_config = get_intraday_config()
            
            result["config"] = {
                "enforce_pdt": os.getenv("ENFORCE_PDT", "true").lower() == "true",
                "pdt_equity_threshold": float(os.getenv("PDT_EQUITY_THRESHOLD", "25000")),
                "use_intraday_data": intraday_config.use_intraday_data,
                "quote_cache_seconds": intraday_config.quote_cache_seconds,
                "allow_fractional": fractional_config.allow_fractional,
                "max_position_pct": risk_config.max_position_pct,
                "max_sector_pct": risk_config.max_sector_pct,
                "max_total_positions": risk_config.max_total_positions,
                "max_hold_hours": risk_config.max_hold_hours,
            }
        except Exception as ce:
            result["config"] = {"error": str(ce)}
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get trading guardrails: {e}")
        return {
            "success": False,
            "error": str(e),
            "pdt_status": None,
            "risk_limits": None,
            "quote_health": None,
            "config": {},
        }


@router.get("/data-sources/fmp")
async def get_fmp_module_status():
    """
    Get FMP Ultimate module status.
    
    Returns which FMP data modules are enabled and their health status.
    """
    try:
        from src.data.fmp_gateway import get_fmp_gateway, FMPModule, is_module_enabled
        
        gateway = get_fmp_gateway()
        
        # Get module status
        modules = {}
        for module in FMPModule:
            modules[module.name.lower()] = {
                "enabled": is_module_enabled(module),
                "env_var": module.value,
            }
        
        # Test a simple call to verify FMP is working
        health_status = "unknown"
        health_message = None
        
        if gateway.is_configured():
            try:
                # Quick health check - get a simple quote
                profile = gateway.get_company_profile("AAPL")
                if profile:
                    health_status = "healthy"
                    health_message = f"FMP responding ({profile.company_name})"
                else:
                    health_status = "degraded"
                    health_message = "FMP configured but no data returned"
            except Exception as he:
                health_status = "error"
                health_message = str(he)
        else:
            health_status = "not_configured"
            health_message = "FMP_API_KEY not set"
        
        return {
            "success": True,
            "configured": gateway.is_configured(),
            "health": {
                "status": health_status,
                "message": health_message,
            },
            "modules": modules,
            "enabled_count": sum(1 for m in modules.values() if m["enabled"]),
            "total_count": len(modules),
        }
        
    except Exception as e:
        logger.error(f"Failed to get FMP module status: {e}")
        return {
            "success": False,
            "error": str(e),
            "configured": False,
            "modules": {},
        }


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
    """Get agent performance metrics with freshness info."""
    try:
        from src.monitoring import get_analytics_service
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        analytics = get_analytics_service()
        metrics = await analytics.get_agent_performance(days=days, agent_id=agent_id)
        
        # Get last signal timestamps per agent
        agent_timestamps = {}
        stale_threshold_minutes = 60  # 1 hour
        try:
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT agent_id, MAX(timestamp) as last_signal
                    FROM agent_signals
                    WHERE timestamp > NOW() - INTERVAL :days_interval
                    GROUP BY agent_id
                """), {"days_interval": f"{days} days"})
                
                for row in result.fetchall():
                    agent_timestamps[row[0]] = row[1]
        except Exception as e:
            logger.debug(f"Could not get agent timestamps: {e}")
        
        responses = []
        for m in metrics.values():
            last_signal = agent_timestamps.get(m.agent_id)
            is_stale = False
            last_signal_iso = None
            
            if last_signal:
                if last_signal.tzinfo is None:
                    last_signal = last_signal.replace(tzinfo=timezone.utc)
                last_signal_iso = last_signal.isoformat()
                age_minutes = (datetime.now(timezone.utc) - last_signal).total_seconds() / 60
                is_stale = age_minutes > stale_threshold_minutes
            else:
                is_stale = True  # No signals = stale
            
            responses.append(AgentPerformanceResponse(
                agent_id=m.agent_id,
                total_signals=m.total_signals,
                accuracy=m.accuracy,
                avg_confidence=m.avg_confidence,
                bullish_signals=m.bullish_signals,
                bearish_signals=m.bearish_signals,
                last_signal_at=last_signal_iso,
                is_stale=is_stale,
            ))
        
        return responses
        
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


@router.get("/metrics/freshness", response_model=DataFreshnessInfo)
async def get_data_freshness():
    """Get data freshness timestamps for all key metrics."""
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        import os
        
        stale_threshold_minutes = int(os.getenv("DATA_STALE_THRESHOLD_MINUTES", "60"))
        now = datetime.now(timezone.utc)
        
        freshness = DataFreshnessInfo()
        
        with engine.connect() as conn:
            # Last workflow
            try:
                result = conn.execute(text("SELECT MAX(timestamp) FROM workflow_events"))
                row = result.fetchone()
                if row and row[0]:
                    last_workflow = row[0]
                    if last_workflow.tzinfo is None:
                        last_workflow = last_workflow.replace(tzinfo=timezone.utc)
                    freshness.last_workflow_at = last_workflow.isoformat()
                    freshness.minutes_since_workflow = int((now - last_workflow).total_seconds() / 60)
            except Exception:
                pass
            
            # Last agent signal
            try:
                result = conn.execute(text("SELECT MAX(timestamp) FROM agent_signals"))
                row = result.fetchone()
                if row and row[0]:
                    last_signal = row[0]
                    if last_signal.tzinfo is None:
                        last_signal = last_signal.replace(tzinfo=timezone.utc)
                    freshness.last_signal_at = last_signal.isoformat()
                    freshness.minutes_since_signal = int((now - last_signal).total_seconds() / 60)
            except Exception:
                pass
            
            # Last trade
            try:
                result = conn.execute(text("SELECT MAX(timestamp) FROM trade_executions"))
                row = result.fetchone()
                if row and row[0]:
                    last_trade = row[0]
                    if last_trade.tzinfo is None:
                        last_trade = last_trade.replace(tzinfo=timezone.utc)
                    freshness.last_trade_at = last_trade.isoformat()
            except Exception:
                pass
            
            # Last PM decision
            try:
                result = conn.execute(text("SELECT MAX(timestamp) FROM pm_decisions"))
                row = result.fetchone()
                if row and row[0]:
                    last_pm = row[0]
                    if last_pm.tzinfo is None:
                        last_pm = last_pm.replace(tzinfo=timezone.utc)
                    freshness.last_pm_decision_at = last_pm.isoformat()
            except Exception:
                pass
        
        # Determine if data is stale
        if freshness.minutes_since_workflow and freshness.minutes_since_workflow > stale_threshold_minutes:
            freshness.is_stale = True
        elif freshness.minutes_since_signal and freshness.minutes_since_signal > stale_threshold_minutes:
            freshness.is_stale = True
        elif freshness.last_workflow_at is None and freshness.last_signal_at is None:
            freshness.is_stale = True
        
        return freshness
        
    except Exception as e:
        logger.error(f"Failed to get data freshness: {e}")
        raise HTTPException(500, str(e))


# =============================================================================
# ACCURACY BACKFILL ENDPOINT
# =============================================================================

@router.post("/accuracy/backfill")
async def trigger_accuracy_backfill(
    days: int = Query(30, ge=1, le=365, description="Days to look back for closed trades"),
):
    """
    Trigger a backfill of agent accuracy metrics from closed trades.
    
    This updates:
    - pm_decisions.was_profitable (from realized P&L)
    - agent_signals.was_correct (bullish/bearish vs trade outcome)
    
    After running, /monitoring/metrics/agents will reflect real accuracy.
    """
    try:
        from src.monitoring.accuracy_backfill import get_accuracy_backfill_service
        
        service = get_accuracy_backfill_service()
        result = await service.backfill_from_closed_trades(days=days)
        
        return {
            "success": len(result.errors) == 0,
            "trades_processed": result.trades_processed,
            "pm_decisions_updated": result.pm_decisions_updated,
            "agent_signals_updated": result.agent_signals_updated,
            "errors": result.errors,
        }
        
    except Exception as e:
        logger.error(f"Accuracy backfill failed: {e}")
        raise HTTPException(500, str(e))


@router.get("/accuracy/summary")
async def get_accuracy_summary():
    """
    Get a summary of accuracy data coverage.
    
    Shows how many agent signals and PM decisions have outcome data populated.
    """
    try:
        from src.monitoring.accuracy_backfill import get_accuracy_backfill_service
        
        service = get_accuracy_backfill_service()
        summary = await service.get_accuracy_summary()
        
        return {
            "success": "error" not in summary,
            **summary,
        }
        
    except Exception as e:
        logger.error(f"Failed to get accuracy summary: {e}")
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
                workflow_id,
                workflow_type,
                step_name,
                status,
                started_at,
                completed_at,
                duration_ms,
                ticker
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
                "id": str(row[0]),  # Convert UUID to string
                "workflow_type": row[1],
                "step_name": row[2],
                "status": row[3],
                "started_at": row[4].isoformat() if row[4] else None,
                "completed_at": row[5].isoformat() if row[5] else None,
                "duration_ms": row[6],
                "ticker": row[7],
            })
        
        return {"workflows": workflows, "total": len(workflows)}
        
    except Exception as e:
        logger.error(f"Failed to get workflows: {e}")
        return {"workflows": [], "error": str(e)}


# NOTE: /workflows/latest MUST come before /workflows/{workflow_id}
# to avoid the path parameter catching "latest" as an ID
@router.get("/workflows/latest")
async def get_latest_workflow_for_sidebar():
    """
    Get the latest workflow data for populating sidebars.
    
    Returns data in format expected by Intelligence Panel:
    - Agent statuses and signals
    - Mazo research
    - PM decision
    - Console logs (last 50 workflow events)
    """
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        result = {
            "agentStatuses": {},
            "signals": {},
            "mazoResearch": None,
            "finalDecision": None,
            "consoleLogs": [],
        }
        
        with engine.connect() as conn:
            # Get latest workflow ID that has agent signals (more useful for sidebars)
            latest_query = """
                SELECT workflow_id, MAX(timestamp) as last_update
                FROM agent_signals
                WHERE timestamp > NOW() - INTERVAL '7 days'
                GROUP BY workflow_id
                ORDER BY last_update DESC
                LIMIT 1
            """
            latest_result = conn.execute(text(latest_query))
            latest_row = latest_result.fetchone()
            
            # Fall back to workflow_events if no agent signals
            if not latest_row:
                fallback_query = """
                    SELECT DISTINCT workflow_id, MAX(timestamp) as last_update
                    FROM workflow_events
                    WHERE timestamp > NOW() - INTERVAL '24 hours'
                    GROUP BY workflow_id
                    ORDER BY last_update DESC
                    LIMIT 1
                """
                latest_result = conn.execute(text(fallback_query))
                latest_row = latest_result.fetchone()
            
            if not latest_row:
                return result
            
            workflow_id = str(latest_row[0])
            result["workflowId"] = workflow_id
            
            # Get agent signals
            signals_query = """
                SELECT agent_id, ticker, signal, confidence, reasoning, timestamp
                FROM agent_signals
                WHERE workflow_id = CAST(:workflow_id AS uuid)
                ORDER BY timestamp DESC
            """
            signal_rows = conn.execute(text(signals_query), {"workflow_id": workflow_id}).fetchall()
            
            for row in signal_rows:
                agent_id = row[0]
                result["agentStatuses"][agent_id] = "complete"
                result["signals"][agent_id] = {
                    "signal": row[2],
                    "confidence": float(row[3]) if row[3] else 50,
                    "reasoning": row[4][:300] if row[4] else None,
                    "ticker": row[1],
                }
            
            # Get Mazo research
            mazo_query = """
                SELECT ticker, query, response, sources, sentiment, sentiment_confidence
                FROM mazo_research
                WHERE workflow_id = CAST(:workflow_id AS uuid)
                ORDER BY timestamp DESC
                LIMIT 1
            """
            try:
                mazo_result = conn.execute(text(mazo_query), {"workflow_id": workflow_id})
                mazo_row = mazo_result.fetchone()
                if mazo_row:
                    result["mazoResearch"] = {
                        "ticker": mazo_row[0],
                        "query": mazo_row[1],
                        "response": mazo_row[2][:2000] if mazo_row[2] else None,
                        "sources": mazo_row[3] or [],
                        "sentiment": mazo_row[4],
                        "confidence": mazo_row[5],
                    }
            except Exception:
                pass  # Table might not exist
            
            # Get PM decision
            pm_query = """
                SELECT ticker, action, confidence, reasoning_raw, bullish_count, bearish_count, neutral_count
                FROM pm_decisions
                WHERE workflow_id = CAST(:workflow_id AS uuid)
                ORDER BY timestamp DESC
                LIMIT 1
            """
            try:
                pm_result = conn.execute(text(pm_query), {"workflow_id": workflow_id})
                pm_row = pm_result.fetchone()
                if pm_row:
                    result["finalDecision"] = {
                        "ticker": pm_row[0],
                        "action": pm_row[1],
                        "confidence": float(pm_row[2]) if pm_row[2] else None,
                        "reasoning": pm_row[3][:500] if pm_row[3] else None,
                        "bullishCount": pm_row[4],
                        "bearishCount": pm_row[5],
                        "neutralCount": pm_row[6],
                    }
            except Exception:
                pass
            
            # Get recent workflow events as console logs
            events_query = """
                SELECT step_name, status, timestamp, duration_ms, ticker, error_message
                FROM workflow_events
                WHERE workflow_id = CAST(:workflow_id AS uuid)
                ORDER BY timestamp DESC
                LIMIT 50
            """
            event_rows = conn.execute(text(events_query), {"workflow_id": workflow_id}).fetchall()
            
            for row in event_rows:
                level = "info"
                if row[1] == "failed":
                    level = "error"
                elif row[1] == "started":
                    level = "debug"
                    
                result["consoleLogs"].append({
                    "id": f"log_{row[2].isoformat() if row[2] else 'unknown'}",
                    "timestamp": row[2].isoformat() if row[2] else None,
                    "level": level,
                    "source": row[0],
                    "message": f"{row[0]}: {row[1]}" + (f" ({row[3]}ms)" if row[3] else "") + (f" - {row[4]}" if row[4] else ""),
                })
            
            result["consoleLogs"].reverse()  # Chronological order
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get latest workflow: {e}")
        return {
            "agentStatuses": {},
            "signals": {},
            "mazoResearch": None,
            "finalDecision": None,
            "consoleLogs": [],
            "error": str(e),
        }


@router.get("/workflows/{workflow_id}")
async def get_workflow_detail(workflow_id: str):
    """Get detailed workflow execution with all steps."""
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        # Get workflow events
        workflow_query = """
            SELECT 
                workflow_id, workflow_type, step_name, status,
                started_at, completed_at, duration_ms, ticker, error_message
            FROM workflow_events
            WHERE workflow_id = :workflow_id::uuid
            ORDER BY started_at
        """
        
        # Get agent signals for this workflow
        signals_query = """
            SELECT 
                agent_id, ticker, signal, confidence, reasoning
            FROM agent_signals
            WHERE workflow_id = :workflow_id::uuid
            ORDER BY agent_id
        """
        
        # Get PM decisions for this workflow
        pm_query = """
            SELECT 
                ticker, decision, confidence, reasoning, agents_received
            FROM pm_decisions
            WHERE workflow_id = :workflow_id::uuid
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
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        query = """
            SELECT 
                order_id, ticker, side, quantity, order_type, status,
                submitted_at, filled_at, filled_qty, filled_avg_price,
                stop_loss_price, take_profit_price, reject_reason
            FROM trade_executions
            WHERE order_id = :order_id
        """
        
        with engine.connect() as conn:
            result = conn.execute(text(query), {"order_id": order_id})
            row = result.fetchone()
        
        if not row:
            return {"error": "Trade not found", "order_id": order_id}
        
        return {
            "order_id": row[0],
            "ticker": row[1],
            "side": row[2],
            "quantity": row[3],
            "order_type": row[4],
            "status": row[5],
            "submitted_at": row[6].isoformat() if row[6] else None,
            "filled_at": row[7].isoformat() if row[7] else None,
            "filled_qty": row[8],
            "filled_avg_price": row[9],
            "stop_loss_price": row[10],
            "take_profit_price": row[11],
            "reject_reason": row[12],
        }
        
    except Exception as e:
        logger.error(f"Failed to get trade detail: {e}")
        return {"error": str(e), "order_id": order_id}


# =============================================================================
# LIVE ACTIVITY FEED
# =============================================================================

@router.get("/activity/live")
async def get_live_activity(limit: int = Query(50, ge=1, le=200)):
    """
    Get recent activity events for the Live Activity feed.
    
    Returns a unified stream of:
    - Workflow events (cycle starts/stops)
    - Agent signals
    - PM decisions
    - Trade executions
    """
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        activities = []
        
        # Get recent workflow events
        workflow_query = """
            SELECT 
                'workflow' as type,
                timestamp,
                workflow_type,
                step_name,
                status,
                ticker,
                duration_ms,
                workflow_id
            FROM workflow_events
            WHERE timestamp > NOW() - INTERVAL '1 hour'
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        
        # Get recent agent signals
        signals_query = """
            SELECT 
                'agent_signal' as type,
                timestamp,
                agent_id,
                ticker,
                signal,
                confidence,
                reasoning
            FROM agent_signals
            WHERE timestamp > NOW() - INTERVAL '1 hour'
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        
        # Get recent PM decisions
        pm_query = """
            SELECT 
                'pm_decision' as type,
                timestamp,
                ticker,
                action,
                confidence,
                reasoning_raw
            FROM pm_decisions
            WHERE timestamp > NOW() - INTERVAL '1 hour'
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        
        # Get recent trade executions
        trades_query = """
            SELECT 
                'trade' as type,
                timestamp,
                ticker,
                side,
                quantity,
                status,
                filled_avg_price
            FROM trade_executions
            WHERE timestamp > NOW() - INTERVAL '1 hour'
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        
        with engine.connect() as conn:
            # Fetch workflow events
            try:
                result = conn.execute(text(workflow_query), {"limit": limit})
                for row in result.fetchall():
                    workflow_id_str = str(row[7]) if row[7] else None
                    activities.append({
                        "id": f"wf_{row[1].isoformat() if row[1] else 'unknown'}_{row[3]}",
                        "type": "workflow",
                        "timestamp": row[1].isoformat() if row[1] else None,
                        "message": f"{row[2]}: {row[3]} - {row[4]}",
                        "ticker": row[5],
                        "status": "complete" if row[4] == "completed" else "running" if row[4] == "started" else "error",
                        "workflow_id": workflow_id_str,
                        "details": {
                            "workflow_type": row[2],
                            "step_name": row[3],
                            "status": row[4],
                            "duration_ms": row[6],
                            "workflow_id": workflow_id_str,
                        },
                    })
            except Exception as e:
                logger.debug(f"No workflow events table: {e}")
            
            # Fetch agent signals
            try:
                result = conn.execute(text(signals_query), {"limit": limit})
                for row in result.fetchall():
                    activities.append({
                        "id": f"sig_{row[1].isoformat() if row[1] else 'unknown'}_{row[2]}",
                        "type": "analyze",
                        "timestamp": row[1].isoformat() if row[1] else None,
                        "message": f"{row[2]}: {row[4]} ({row[5]:.0f}% confidence)" if row[5] else f"{row[2]}: {row[4]}",
                        "ticker": row[3],
                        "status": "complete",
                        "details": {"agent": row[2], "signal": row[4], "confidence": row[5], "reasoning": row[6][:200] if row[6] else None},
                    })
            except Exception as e:
                logger.debug(f"No agent signals table: {e}")
            
            # Fetch PM decisions
            try:
                result = conn.execute(text(pm_query), {"limit": limit})
                for row in result.fetchall():
                    activities.append({
                        "id": f"pm_{row[1].isoformat() if row[1] else 'unknown'}_{row[2]}",
                        "type": "decision",
                        "timestamp": row[1].isoformat() if row[1] else None,
                        "message": f"PM: {row[3]} {row[2]}",
                        "ticker": row[2],
                        "status": "complete",
                        "details": {"action": row[3], "confidence": row[4], "reasoning": row[5][:200] if row[5] else None},
                    })
            except Exception as e:
                logger.debug(f"No PM decisions table: {e}")
            
            # Fetch trade executions
            try:
                result = conn.execute(text(trades_query), {"limit": limit})
                for row in result.fetchall():
                    price_str = f" @ ${row[6]:.2f}" if row[6] else ""
                    activities.append({
                        "id": f"trade_{row[1].isoformat() if row[1] else 'unknown'}_{row[2]}",
                        "type": "execute",
                        "timestamp": row[1].isoformat() if row[1] else None,
                        "message": f"{row[3].upper()} {row[4]} {row[2]}{price_str}",
                        "ticker": row[2],
                        "status": "complete" if row[5] == "filled" else "running" if row[5] == "new" else "error",
                        "details": {"side": row[3], "quantity": row[4], "status": row[5], "price": row[6]},
                    })
            except Exception as e:
                logger.debug(f"No trade executions table: {e}")
        
        # Sort all activities by timestamp
        activities.sort(key=lambda x: x["timestamp"] or "", reverse=True)
        
        return {
            "activities": activities[:limit],
            "total": len(activities),
        }
        
    except Exception as e:
        logger.error(f"Failed to get live activity: {e}")
        
        # Fallback to in-memory events from EventLogger
        try:
            from src.monitoring.event_logger import get_event_logger
            event_logger = get_event_logger()
            in_memory = event_logger.get_in_memory_events()
            
            activities = []
            for event in in_memory[-limit:]:
                data = event.get("data", {})
                activities.append({
                    "id": str(data.get("id", "unknown")),
                    "type": event.get("table", "unknown"),
                    "timestamp": data.get("timestamp", datetime.now(timezone.utc)).isoformat() if isinstance(data.get("timestamp"), datetime) else str(data.get("timestamp", "")),
                    "message": str(data.get("step_name", data.get("action", data.get("ticker", "Event"))))[:100],
                    "ticker": data.get("ticker"),
                    "status": data.get("status", "complete"),
                    "details": data,
                })
            
            activities.reverse()  # Most recent first
            
            return {
                "activities": activities,
                "total": len(activities),
                "source": "in_memory",
            }
        except Exception as e2:
            logger.error(f"Fallback also failed: {e2}")
            return {"activities": [], "total": 0, "error": str(e)}
