"""
Event Logger - Persists pipeline data to database for Round Table transparency.

This logger writes to the monitoring tables (workflow_events, agent_signals, 
mazo_research, pm_decisions, trade_executions) so the Round Table UI can 
display real data from actual trading cycles.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Singleton instance
_event_logger_instance = None


def get_event_logger() -> 'EventLogger':
    """Get or create the singleton EventLogger instance."""
    global _event_logger_instance
    if _event_logger_instance is None:
        _event_logger_instance = EventLogger()
    return _event_logger_instance


class EventLogger:
    """
    Logs pipeline events to the database for Round Table transparency.
    
    Uses raw SQL for simplicity and to avoid ORM session management issues
    when called from async contexts.
    """
    
    def __init__(self):
        self._engine = None
        self._initialized = False
    
    def _get_engine(self):
        """Lazily get the database engine."""
        if self._engine is None:
            try:
                # Try to import the engine from the backend
                from app.backend.database.connection import engine
                self._engine = engine
                self._initialized = True
                logger.info("EventLogger connected to database")
            except Exception as e:
                logger.warning(f"EventLogger could not connect to database: {e}")
                self._initialized = False
        return self._engine
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection context."""
        engine = self._get_engine()
        if engine is None:
            yield None
            return
        
        try:
            conn = engine.connect()
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            yield None
    
    def log_workflow_event(
        self,
        workflow_id: uuid.UUID,
        workflow_type: str,
        step_name: str,
        status: str,
        ticker: str = None,
        payload: Dict[str, Any] = None,
        duration_ms: int = None,
        error_message: str = None,
    ):
        """Log a workflow event (start, complete, error, etc.)."""
        with self._get_connection() as conn:
            if conn is None:
                return
            
            try:
                from sqlalchemy import text
                import json
                
                conn.execute(text("""
                    INSERT INTO workflow_events 
                    (timestamp, id, workflow_id, workflow_type, step_name, status, ticker, payload, duration_ms, error_message)
                    VALUES (NOW(), :id, :workflow_id, :workflow_type, :step_name, :status, :ticker, :payload, :duration_ms, :error_message)
                """), {
                    "id": str(uuid.uuid4()),
                    "workflow_id": str(workflow_id),
                    "workflow_type": workflow_type,
                    "step_name": step_name,
                    "status": status,
                    "ticker": ticker,
                    "payload": json.dumps(payload) if payload else None,
                    "duration_ms": duration_ms,
                    "error_message": error_message,
                })
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to log workflow event: {e}")
    
    def log_agent_signal(
        self,
        workflow_id: uuid.UUID,
        agent_id: str,
        ticker: str,
        signal: str,
        confidence: float = None,
        reasoning: str = None,
        key_metrics: Dict[str, Any] = None,
        agent_type: str = None,
        latency_ms: int = None,
    ):
        """Log an individual agent's signal with full reasoning."""
        with self._get_connection() as conn:
            if conn is None:
                return
            
            try:
                from sqlalchemy import text
                import json
                
                conn.execute(text("""
                    INSERT INTO agent_signals 
                    (timestamp, id, workflow_id, agent_id, agent_type, ticker, signal, confidence, reasoning, key_metrics, latency_ms)
                    VALUES (NOW(), :id, :workflow_id, :agent_id, :agent_type, :ticker, :signal, :confidence, :reasoning, :key_metrics, :latency_ms)
                """), {
                    "id": str(uuid.uuid4()),
                    "workflow_id": str(workflow_id),
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "ticker": ticker,
                    "signal": signal.lower() if signal else "neutral",
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "key_metrics": json.dumps(key_metrics) if key_metrics else None,
                    "latency_ms": latency_ms,
                })
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to log agent signal: {e}")
    
    def log_mazo_research(
        self,
        workflow_id: uuid.UUID,
        ticker: str,
        query: str,
        mode: str = None,
        response: str = None,
        sources: List[Dict[str, Any]] = None,
        sentiment: str = None,
        sentiment_confidence: str = None,
        key_points: List[str] = None,
        success: bool = False,
        error: str = None,
        latency_ms: int = None,
    ):
        """Log Mazo research query and response."""
        with self._get_connection() as conn:
            if conn is None:
                return
            
            try:
                from sqlalchemy import text
                import json
                
                conn.execute(text("""
                    INSERT INTO mazo_research 
                    (timestamp, id, workflow_id, ticker, query, mode, response, response_length, sources_count, sources, 
                     sentiment, sentiment_confidence, key_points, success, error, latency_ms)
                    VALUES (NOW(), :id, :workflow_id, :ticker, :query, :mode, :response, :response_length, :sources_count, :sources,
                            :sentiment, :sentiment_confidence, :key_points, :success, :error, :latency_ms)
                """), {
                    "id": str(uuid.uuid4()),
                    "workflow_id": str(workflow_id),
                    "ticker": ticker,
                    "query": query[:500] if query else "",
                    "mode": mode,
                    "response": response[:5000] if response else None,  # Limit response size
                    "response_length": len(response) if response else 0,
                    "sources_count": len(sources) if sources else 0,
                    "sources": json.dumps(sources) if sources else None,
                    "sentiment": sentiment,
                    "sentiment_confidence": sentiment_confidence,
                    "key_points": json.dumps(key_points) if key_points else None,
                    "success": success,
                    "error": error,
                    "latency_ms": latency_ms,
                })
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to log Mazo research: {e}")
    
    def log_pm_decision(
        self,
        workflow_id: uuid.UUID,
        ticker: str,
        action: str,
        quantity: float = None,
        stop_loss_pct: float = None,
        take_profit_pct: float = None,
        confidence: float = None,
        reasoning: str = None,
        bullish_count: int = None,
        bearish_count: int = None,
        neutral_count: int = None,
        consensus_direction: str = None,
        consensus_score: float = None,
        portfolio_equity: float = None,
        portfolio_cash: float = None,
        mazo_sentiment: str = None,
        latency_ms: int = None,
        danelfin_ai_score: int = None,
        danelfin_technical: int = None,
        danelfin_fundamental: int = None,
        danelfin_sentiment: int = None,
        danelfin_low_risk: int = None,
        danelfin_signal: str = None,
    ):
        """Log Portfolio Manager decision with full context."""
        with self._get_connection() as conn:
            if conn is None:
                return
            
            try:
                from sqlalchemy import text
                
                conn.execute(text("""
                    INSERT INTO pm_decisions 
                    (timestamp, id, workflow_id, ticker, action, quantity, stop_loss_pct, take_profit_pct, confidence,
                     reasoning_raw, bullish_count, bearish_count, neutral_count, consensus_direction, consensus_score,
                     portfolio_equity, portfolio_cash, mazo_sentiment, latency_ms)
                    VALUES (NOW(), :id, :workflow_id, :ticker, :action, :quantity, :stop_loss_pct, :take_profit_pct, :confidence,
                            :reasoning, :bullish_count, :bearish_count, :neutral_count, :consensus_direction, :consensus_score,
                            :portfolio_equity, :portfolio_cash, :mazo_sentiment, :latency_ms)
                """), {
                    "id": str(uuid.uuid4()),
                    "workflow_id": str(workflow_id),
                    "ticker": ticker,
                    "action": action.lower() if action else "hold",
                    "quantity": quantity,
                    "stop_loss_pct": stop_loss_pct,
                    "take_profit_pct": take_profit_pct,
                    "confidence": confidence,
                    "reasoning": reasoning[:2000] if reasoning else None,
                    "bullish_count": bullish_count,
                    "bearish_count": bearish_count,
                    "neutral_count": neutral_count,
                    "consensus_direction": consensus_direction,
                    "consensus_score": consensus_score,
                    "portfolio_equity": portfolio_equity,
                    "portfolio_cash": portfolio_cash,
                    "mazo_sentiment": mazo_sentiment,
                    "latency_ms": latency_ms,
                })
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to log PM decision: {e}")
    
    def log_danelfin_scores(
        self,
        workflow_id: uuid.UUID,
        tickers: List[str],
        scores: Dict[str, Dict[str, Any]],
    ):
        """
        Log Danelfin AI scores for workflow tickers.
        
        Stores as a workflow_event with step_name='danelfin_validation'
        so it appears in Round Table as external AI validation.
        """
        with self._get_connection() as conn:
            if conn is None:
                return
            
            try:
                from sqlalchemy import text
                import json
                
                # Build summary payload
                summary = {}
                for ticker in tickers:
                    score_data = scores.get(ticker, {})
                    if score_data.get('success', False):
                        summary[ticker] = {
                            "ai_score": score_data.get('ai_score'),
                            "technical": score_data.get('technical'),
                            "fundamental": score_data.get('fundamental'),
                            "sentiment": score_data.get('sentiment'),
                            "low_risk": score_data.get('low_risk'),
                            "signal": score_data.get('signal'),
                        }
                
                if summary:
                    conn.execute(text("""
                        INSERT INTO workflow_events
                        (timestamp, id, workflow_id, workflow_type, step_name, status, ticker, payload, duration_ms, error_message)
                        VALUES (NOW(), :id, :workflow_id, 'autonomous', 'danelfin_validation', 'completed', NULL, :payload, NULL, NULL)
                    """), {
                        "id": str(uuid.uuid4()),
                        "workflow_id": str(workflow_id),
                        "payload": json.dumps({
                            "source": "danelfin",
                            "tickers_scored": len(summary),
                            "scores": summary,
                        }),
                    })
                    conn.commit()
                    logger.debug(f"Logged Danelfin scores for {len(summary)} tickers")
            except Exception as e:
                logger.error(f"Failed to log Danelfin scores: {e}")
    
    def log_trade_execution(
        self,
        workflow_id: uuid.UUID,
        order_id: str,
        ticker: str,
        side: str,
        order_type: str,
        quantity: float,
        status: str,
        filled_qty: float = None,
        filled_avg_price: float = None,
        expected_price: float = None,
        slippage_bps: float = None,
        fill_latency_ms: int = None,
        reject_reason: str = None,
    ):
        """Log trade execution details."""
        with self._get_connection() as conn:
            if conn is None:
                return
            
            try:
                from sqlalchemy import text
                
                conn.execute(text("""
                    INSERT INTO trade_executions 
                    (timestamp, id, workflow_id, order_id, ticker, side, order_type, quantity, status,
                     filled_qty, filled_avg_price, expected_price, slippage_bps, fill_latency_ms, reject_reason)
                    VALUES (NOW(), :id, :workflow_id, :order_id, :ticker, :side, :order_type, :quantity, :status,
                            :filled_qty, :filled_avg_price, :expected_price, :slippage_bps, :fill_latency_ms, :reject_reason)
                """), {
                    "id": str(uuid.uuid4()),
                    "workflow_id": str(workflow_id),
                    "order_id": order_id,
                    "ticker": ticker,
                    "side": side.lower() if side else "buy",
                    "order_type": order_type.lower() if order_type else "market",
                    "quantity": quantity,
                    "status": status.lower() if status else "new",
                    "filled_qty": filled_qty,
                    "filled_avg_price": filled_avg_price,
                    "expected_price": expected_price,
                    "slippage_bps": slippage_bps,
                    "fill_latency_ms": fill_latency_ms,
                    "reject_reason": reject_reason,
                })
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to log trade execution: {e}")
    
    def update_agent_accuracy(
        self,
        workflow_id: uuid.UUID,
        ticker: str,
        actual_return: float,
    ):
        """Update agent signals with actual outcome for accuracy tracking."""
        with self._get_connection() as conn:
            if conn is None:
                return
            
            try:
                from sqlalchemy import text
                
                # Mark bullish signals as correct if return > 0, bearish if return < 0
                conn.execute(text("""
                    UPDATE agent_signals
                    SET was_correct = CASE 
                        WHEN signal = 'bullish' AND :actual_return > 0 THEN TRUE
                        WHEN signal = 'bearish' AND :actual_return < 0 THEN TRUE
                        WHEN signal = 'neutral' THEN NULL
                        ELSE FALSE
                    END,
                    actual_return = :actual_return
                    WHERE workflow_id = :workflow_id AND ticker = :ticker
                """), {
                    "workflow_id": str(workflow_id),
                    "ticker": ticker,
                    "actual_return": actual_return,
                })
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to update agent accuracy: {e}")
    
    def update_pm_execution(
        self,
        workflow_id: uuid.UUID,
        ticker: str,
        order_id: str,
        was_executed: bool,
    ):
        """Update PM decision with execution status."""
        with self._get_connection() as conn:
            if conn is None:
                return
            
            try:
                from sqlalchemy import text
                
                conn.execute(text("""
                    UPDATE pm_decisions
                    SET was_executed = :was_executed,
                        execution_order_id = :order_id
                    WHERE workflow_id = :workflow_id AND ticker = :ticker
                """), {
                    "workflow_id": str(workflow_id),
                    "ticker": ticker,
                    "order_id": order_id,
                    "was_executed": was_executed,
                })
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to update PM execution: {e}")
    
    def log_heartbeat(
        self,
        status: str = "running",
        active_jobs: int = 0,
        details: Dict[str, Any] = None,
    ):
        """Log scheduler heartbeat."""
        with self._get_connection() as conn:
            if conn is None:
                return
            
            try:
                from sqlalchemy import text
                import json
                
                conn.execute(text("""
                    INSERT INTO scheduler_heartbeats (timestamp, id, status, active_jobs, details)
                    VALUES (NOW(), :id, :status, :active_jobs, :details)
                """), {
                    "id": str(uuid.uuid4()),
                    "status": status,
                    "active_jobs": active_jobs,
                    "details": json.dumps(details) if details else None,
                })
                conn.commit()
            except Exception as e:
                logger.debug(f"Failed to log heartbeat: {e}")
