"""
Event Logger Service

Central logging service for all trading events. Provides a unified interface
for logging workflow steps, agent signals, PM decisions, trade executions,
and system health metrics.

All events are stored in TimescaleDB hypertables for efficient time-series
querying and analysis.
"""

import logging
import os
import uuid
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger(__name__)

# Try to import database dependencies
try:
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("SQLAlchemy not available, using in-memory logging only")


@dataclass
class WorkflowContext:
    """Context for tracking a workflow execution"""
    workflow_id: uuid.UUID
    workflow_type: str
    started_at: datetime
    tickers: List[str] = field(default_factory=list)
    mode: str = "full"
    step_index: int = 0


class EventLogger:
    """
    Central logging service for all trading events.
    
    Usage:
        logger = get_event_logger()
        
        # Start a workflow
        with logger.workflow("trading_cycle", tickers=["AAPL", "MSFT"]) as wf:
            # Log steps
            with wf.step("strategy_screening"):
                # ... do screening ...
                pass
            
            # Log agent signals
            logger.log_agent_signal(
                workflow_id=wf.workflow_id,
                agent_id="warren_buffett",
                ticker="AAPL",
                signal="bullish",
                confidence=75.0,
                reasoning="Strong fundamentals..."
            )
    """
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self._session_factory = None
        self._in_memory_events: List[Dict] = []  # Fallback storage
        self._init_db()
    
    def _init_db(self):
        """Initialize database connection if available."""
        if not DB_AVAILABLE or not self.database_url:
            logger.info("Using in-memory event logging")
            return
        
        try:
            engine = create_engine(self.database_url)
            self._session_factory = sessionmaker(bind=engine)
            logger.info("EventLogger connected to database")
        except Exception as e:
            logger.warning(f"Failed to connect to database: {e}")
            self._session_factory = None
    
    def _get_session(self) -> Optional[Session]:
        """Get a database session if available."""
        if self._session_factory:
            return self._session_factory()
        return None
    
    def _store_event(self, table_name: str, event_data: Dict[str, Any]):
        """Store an event in the database or in-memory fallback."""
        event_data["timestamp"] = event_data.get("timestamp", datetime.now(timezone.utc))
        event_data["id"] = event_data.get("id", uuid.uuid4())
        
        session = self._get_session()
        if session:
            try:
                # Dynamic table insert
                from app.backend.database.monitoring_models import (
                    WorkflowEvent, AgentSignal, MazoResearch, PMDecision,
                    TradeExecution, PerformanceMetric, SystemHealth,
                    LLMAPICall, Alert, RateLimitTracking, SchedulerHeartbeat
                )
                
                table_map = {
                    "workflow_events": WorkflowEvent,
                    "agent_signals": AgentSignal,
                    "mazo_research": MazoResearch,
                    "pm_decisions": PMDecision,
                    "trade_executions": TradeExecution,
                    "performance_metrics": PerformanceMetric,
                    "system_health": SystemHealth,
                    "llm_api_calls": LLMAPICall,
                    "alerts": Alert,
                    "rate_limit_tracking": RateLimitTracking,
                    "scheduler_heartbeats": SchedulerHeartbeat,
                }
                
                model_class = table_map.get(table_name)
                if model_class:
                    record = model_class(**event_data)
                    session.add(record)
                    session.commit()
                    return
                    
            except Exception as e:
                logger.error(f"Failed to store event in {table_name}: {e}")
                session.rollback()
            finally:
                session.close()
        
        # Fallback to in-memory
        self._in_memory_events.append({
            "table": table_name,
            "data": event_data
        })
        
        # Keep in-memory buffer bounded
        if len(self._in_memory_events) > 10000:
            self._in_memory_events = self._in_memory_events[-5000:]
    
    # =========================================================================
    # WORKFLOW LOGGING
    # =========================================================================
    
    @contextmanager
    def workflow(self, workflow_type: str, tickers: List[str] = None, mode: str = "full"):
        """
        Context manager for tracking a complete workflow execution.
        
        Usage:
            with event_logger.workflow("trading_cycle", tickers=["AAPL"]) as wf:
                # ... workflow steps ...
                pass
        """
        ctx = WorkflowContext(
            workflow_id=uuid.uuid4(),
            workflow_type=workflow_type,
            started_at=datetime.now(timezone.utc),
            tickers=tickers or [],
            mode=mode,
        )
        
        # Log workflow start
        self.log_workflow_event(
            workflow_id=ctx.workflow_id,
            workflow_type=workflow_type,
            step_name="workflow_start",
            status="started",
            payload={"tickers": tickers, "mode": mode}
        )
        
        try:
            yield ctx
            
            # Log workflow completion
            duration_ms = int((datetime.now(timezone.utc) - ctx.started_at).total_seconds() * 1000)
            self.log_workflow_event(
                workflow_id=ctx.workflow_id,
                workflow_type=workflow_type,
                step_name="workflow_complete",
                status="completed",
                duration_ms=duration_ms,
                payload={"tickers": tickers, "steps_completed": ctx.step_index}
            )
            
        except Exception as e:
            # Log workflow failure
            duration_ms = int((datetime.now(timezone.utc) - ctx.started_at).total_seconds() * 1000)
            self.log_workflow_event(
                workflow_id=ctx.workflow_id,
                workflow_type=workflow_type,
                step_name="workflow_error",
                status="failed",
                duration_ms=duration_ms,
                error_message=str(e),
                payload={"tickers": tickers, "steps_completed": ctx.step_index}
            )
            raise
    
    @contextmanager
    def step(self, ctx: WorkflowContext, step_name: str, ticker: str = None):
        """
        Context manager for tracking a workflow step.
        
        Usage:
            with event_logger.step(wf, "strategy_screening") as step:
                # ... do work ...
                step.add_payload({"signals_found": 5})
        """
        ctx.step_index += 1
        step_ctx = {
            "workflow_id": ctx.workflow_id,
            "step_name": step_name,
            "step_index": ctx.step_index,
            "ticker": ticker,
            "started_at": datetime.now(timezone.utc),
            "payload": {},
        }
        
        # Log step start
        self.log_workflow_event(
            workflow_id=ctx.workflow_id,
            workflow_type=ctx.workflow_type,
            step_name=step_name,
            step_index=ctx.step_index,
            status="started",
            ticker=ticker,
        )
        
        class StepContext:
            def __init__(self, data):
                self._data = data
            
            def add_payload(self, payload: Dict):
                self._data["payload"].update(payload)
        
        try:
            yield StepContext(step_ctx)
            
            # Log step completion
            duration_ms = int((datetime.now(timezone.utc) - step_ctx["started_at"]).total_seconds() * 1000)
            self.log_workflow_event(
                workflow_id=ctx.workflow_id,
                workflow_type=ctx.workflow_type,
                step_name=step_name,
                step_index=ctx.step_index,
                status="completed",
                duration_ms=duration_ms,
                ticker=ticker,
                payload=step_ctx["payload"],
            )
            
        except Exception as e:
            # Log step failure
            duration_ms = int((datetime.now(timezone.utc) - step_ctx["started_at"]).total_seconds() * 1000)
            self.log_workflow_event(
                workflow_id=ctx.workflow_id,
                workflow_type=ctx.workflow_type,
                step_name=step_name,
                step_index=ctx.step_index,
                status="failed",
                duration_ms=duration_ms,
                ticker=ticker,
                error_message=str(e),
                payload=step_ctx["payload"],
            )
            raise
    
    def log_workflow_event(
        self,
        workflow_id: uuid.UUID,
        workflow_type: str,
        step_name: str,
        status: str,
        step_index: int = None,
        started_at: datetime = None,
        completed_at: datetime = None,
        duration_ms: int = None,
        ticker: str = None,
        error_message: str = None,
        payload: Dict = None,
    ):
        """Log a workflow event."""
        self._store_event("workflow_events", {
            "workflow_id": workflow_id,
            "workflow_type": workflow_type,
            "step_name": step_name,
            "step_index": step_index,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "status": status,
            "ticker": ticker,
            "error_message": error_message,
            "payload": payload,
        })
    
    # =========================================================================
    # AGENT SIGNAL LOGGING
    # =========================================================================
    
    def log_agent_signal(
        self,
        workflow_id: uuid.UUID,
        agent_id: str,
        ticker: str,
        signal: str,
        confidence: float = None,
        reasoning: str = None,
        key_metrics: Dict = None,
        latency_ms: int = None,
        agent_type: str = None,
    ):
        """Log an individual agent's signal."""
        self._store_event("agent_signals", {
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "agent_type": agent_type,
            "ticker": ticker,
            "signal": signal,
            "confidence": confidence,
            "reasoning": reasoning,
            "key_metrics": key_metrics,
            "latency_ms": latency_ms,
        })
    
    # =========================================================================
    # MAZO RESEARCH LOGGING
    # =========================================================================
    
    def log_mazo_research(
        self,
        workflow_id: uuid.UUID,
        ticker: str,
        query: str,
        mode: str = None,
        response: str = None,
        sources: List[Dict] = None,
        sentiment: str = None,
        sentiment_confidence: str = None,
        key_points: List[str] = None,
        success: bool = True,
        error: str = None,
        latency_ms: int = None,
    ):
        """Log a Mazo research query and response."""
        self._store_event("mazo_research", {
            "workflow_id": workflow_id,
            "ticker": ticker,
            "query": query,
            "mode": mode,
            "response": response[:5000] if response else None,  # Truncate long responses
            "response_length": len(response) if response else 0,
            "sources_count": len(sources) if sources else 0,
            "sources": sources,
            "sentiment": sentiment,
            "sentiment_confidence": sentiment_confidence,
            "key_points": key_points,
            "success": success,
            "error": error,
            "latency_ms": latency_ms,
        })
    
    def update_mazo_pm_follow(
        self,
        mazo_research_id: uuid.UUID,
        pm_followed: bool,
        pm_action: str,
    ):
        """Update Mazo research record with PM follow-through."""
        # This would update the existing record
        # For now, just log as a separate event
        logger.info(f"Mazo {mazo_research_id}: PM followed={pm_followed}, action={pm_action}")
    
    # =========================================================================
    # PM DECISION LOGGING
    # =========================================================================
    
    def log_pm_decision(
        self,
        workflow_id: uuid.UUID,
        ticker: str,
        action: str,
        quantity: int = None,
        stop_loss_pct: float = None,
        take_profit_pct: float = None,
        agents_received: Dict = None,
        bullish_count: int = None,
        bearish_count: int = None,
        neutral_count: int = None,
        consensus_direction: str = None,
        consensus_score: float = None,
        mazo_received: bool = False,
        mazo_considered: bool = False,
        mazo_sentiment: str = None,
        mazo_bypass_reason: str = None,
        action_matches_consensus: bool = None,
        override_reason: str = None,
        reasoning_raw: str = None,
        confidence: float = None,
        portfolio_equity: float = None,
        portfolio_cash: float = None,
        latency_ms: int = None,
    ):
        """Log a Portfolio Manager decision with full context."""
        self._store_event("pm_decisions", {
            "workflow_id": workflow_id,
            "ticker": ticker,
            "action": action,
            "quantity": quantity,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "agents_received": agents_received,
            "agents_considered": agents_received,  # Same for now
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "neutral_count": neutral_count,
            "consensus_direction": consensus_direction,
            "consensus_score": consensus_score,
            "mazo_received": mazo_received,
            "mazo_considered": mazo_considered,
            "mazo_sentiment": mazo_sentiment,
            "mazo_bypass_reason": mazo_bypass_reason,
            "action_matches_consensus": action_matches_consensus,
            "override_reason": override_reason,
            "reasoning_raw": reasoning_raw,
            "confidence": confidence,
            "portfolio_equity": portfolio_equity,
            "portfolio_cash": portfolio_cash,
            "latency_ms": latency_ms,
        })
    
    # =========================================================================
    # TRADE EXECUTION LOGGING
    # =========================================================================
    
    def log_trade_execution(
        self,
        order_id: str,
        ticker: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        status: str = "new",
        workflow_id: uuid.UUID = None,
        pm_decision_id: uuid.UUID = None,
        limit_price: float = None,
        stop_price: float = None,
        submitted_at: datetime = None,
        filled_at: datetime = None,
        filled_qty: float = None,
        filled_avg_price: float = None,
        expected_price: float = None,
        slippage_bps: float = None,
        fill_latency_ms: int = None,
        reject_reason: str = None,
        commission: float = None,
    ):
        """Log a trade execution event."""
        self._store_event("trade_executions", {
            "workflow_id": workflow_id,
            "pm_decision_id": pm_decision_id,
            "order_id": order_id,
            "ticker": ticker,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
            "limit_price": limit_price,
            "stop_price": stop_price,
            "submitted_at": submitted_at,
            "filled_at": filled_at,
            "filled_qty": filled_qty,
            "filled_avg_price": filled_avg_price,
            "expected_price": expected_price,
            "slippage_bps": slippage_bps,
            "fill_latency_ms": fill_latency_ms,
            "status": status,
            "reject_reason": reject_reason,
            "commission": commission,
        })
    
    # =========================================================================
    # LLM API CALL LOGGING
    # =========================================================================
    
    def log_llm_call(
        self,
        provider: str,
        model: str,
        success: bool,
        workflow_id: uuid.UUID = None,
        agent_id: str = None,
        call_purpose: str = None,
        prompt_tokens: int = None,
        completion_tokens: int = None,
        latency_ms: int = None,
        total_time_ms: int = None,
        error_type: str = None,
        error_message: str = None,
        retry_count: int = 0,
        estimated_cost_usd: float = None,
    ):
        """Log an LLM API call."""
        self._store_event("llm_api_calls", {
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "call_purpose": call_purpose,
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": (prompt_tokens or 0) + (completion_tokens or 0),
            "latency_ms": latency_ms,
            "total_time_ms": total_time_ms,
            "success": success,
            "error_type": error_type,
            "error_message": error_message,
            "retry_count": retry_count,
            "estimated_cost_usd": estimated_cost_usd,
        })
    
    # =========================================================================
    # SYSTEM HEALTH LOGGING
    # =========================================================================
    
    def log_system_health(
        self,
        service: str,
        status: str,
        latency_ms: int = None,
        error_count: int = 0,
        rate_limit_remaining: int = None,
        rate_limit_reset_at: datetime = None,
        details: Dict = None,
    ):
        """Log system health metrics."""
        self._store_event("system_health", {
            "service": service,
            "status": status,
            "latency_ms": latency_ms,
            "error_count": error_count,
            "rate_limit_remaining": rate_limit_remaining,
            "rate_limit_reset_at": rate_limit_reset_at,
            "details": details,
        })
    
    # =========================================================================
    # PERFORMANCE METRICS
    # =========================================================================
    
    def log_metric(
        self,
        metric_name: str,
        value: float,
        ticker: str = None,
        agent_id: str = None,
        tags: Dict = None,
    ):
        """Log a performance metric."""
        self._store_event("performance_metrics", {
            "metric_name": metric_name,
            "value": value,
            "ticker": ticker,
            "agent_id": agent_id,
            "tags": tags,
        })
    
    # =========================================================================
    # RATE LIMIT TRACKING
    # =========================================================================
    
    def log_rate_limit(
        self,
        api_name: str,
        calls_made: int,
        calls_remaining: int = None,
        window_start: datetime = None,
        window_resets_at: datetime = None,
        utilization_pct: float = None,
    ):
        """Log rate limit usage."""
        self._store_event("rate_limit_tracking", {
            "api_name": api_name,
            "calls_made": calls_made,
            "calls_remaining": calls_remaining,
            "window_start": window_start,
            "window_resets_at": window_resets_at,
            "utilization_pct": utilization_pct,
        })
    
    # =========================================================================
    # SCHEDULER HEARTBEAT
    # =========================================================================
    
    def log_heartbeat(
        self,
        scheduler_id: str,
        hostname: str = None,
        jobs_pending: int = None,
        jobs_running: int = None,
        memory_mb: float = None,
        cpu_percent: float = None,
    ):
        """Log scheduler heartbeat."""
        self._store_event("scheduler_heartbeats", {
            "scheduler_id": scheduler_id,
            "hostname": hostname,
            "jobs_pending": jobs_pending,
            "jobs_running": jobs_running,
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
        })
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_in_memory_events(self, table: str = None) -> List[Dict]:
        """Get in-memory events (for debugging)."""
        if table:
            return [e for e in self._in_memory_events if e["table"] == table]
        return self._in_memory_events


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_event_logger: Optional[EventLogger] = None


def get_event_logger() -> EventLogger:
    """Get the global EventLogger instance."""
    global _event_logger
    if _event_logger is None:
        _event_logger = EventLogger()
    return _event_logger


def reset_event_logger():
    """Reset the global EventLogger instance (for testing)."""
    global _event_logger
    _event_logger = None


# =============================================================================
# DECORATOR FOR TIMING
# =============================================================================

def timed_operation(operation_name: str):
    """Decorator to log operation timing."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = int((time.time() - start) * 1000)
                get_event_logger().log_metric(
                    metric_name=f"operation_duration_{operation_name}",
                    value=duration_ms,
                    tags={"operation": operation_name, "success": True}
                )
                return result
            except Exception as e:
                duration_ms = int((time.time() - start) * 1000)
                get_event_logger().log_metric(
                    metric_name=f"operation_duration_{operation_name}",
                    value=duration_ms,
                    tags={"operation": operation_name, "success": False, "error": str(e)[:100]}
                )
                raise
        return wrapper
    return decorator
