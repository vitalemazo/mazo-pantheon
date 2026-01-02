"""
Agent Accuracy Backfill Service

This service calculates and updates accuracy metrics for agents based on actual trade outcomes.

When a trade closes with realized P&L:
1. Find the pm_decision that triggered the trade
2. Mark it as was_profitable = (realized_pnl > 0)
3. Find all agent_signals for that workflow_id + ticker
4. Mark each as was_correct based on:
   - Bullish signal + profitable BUY = correct
   - Bearish signal + profitable SELL/SHORT = correct
   - Otherwise incorrect

Usage:
    from src.monitoring.accuracy_backfill import get_accuracy_backfill_service
    service = get_accuracy_backfill_service()
    updated = await service.backfill_from_closed_trades(days=7)
"""

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BackfillResult:
    """Result of a backfill operation."""
    trades_processed: int = 0
    pm_decisions_updated: int = 0
    agent_signals_updated: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class AccuracyBackfillService:
    """
    Service to backfill accuracy metrics based on actual trade outcomes.
    
    This connects the dots between:
    - trade_history (actual P&L)
    - pm_decisions (was the decision profitable?)
    - agent_signals (did the agent predict correctly?)
    """
    
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
    
    def _get_session(self):
        """Get database session if available."""
        if not self.database_url:
            return None
        
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            engine = create_engine(self.database_url)
            Session = sessionmaker(bind=engine)
            return Session()
        except Exception as e:
            logger.warning(f"Failed to get database session: {e}")
            return None
    
    async def backfill_from_closed_trades(self, days: int = 30) -> BackfillResult:
        """
        Backfill accuracy metrics from closed trades in the last N days.
        
        1. Find closed trades with realized_pnl
        2. Match to pm_decisions via order_id or (ticker, timestamp proximity)
        3. Update was_profitable on pm_decisions
        4. Update was_correct on agent_signals
        
        Args:
            days: Number of days to look back for closed trades
            
        Returns:
            BackfillResult with counts of updated records
        """
        result = BackfillResult()
        session = self._get_session()
        
        if not session:
            result.errors.append("No database session available")
            return result
        
        try:
            from sqlalchemy import text
            
            # Step 1: Find closed trades with realized P&L
            closed_trades_query = """
                SELECT 
                    id, ticker, action, realized_pnl, entry_time, exit_time,
                    order_id
                FROM trade_history
                WHERE status = 'closed'
                AND realized_pnl IS NOT NULL
                AND exit_time > NOW() - INTERVAL :days_interval
            """
            
            trades = session.execute(
                text(closed_trades_query), 
                {"days_interval": f"{days} days"}
            ).fetchall()
            
            logger.info(f"Found {len(trades)} closed trades to process")
            
            for trade in trades:
                trade_id, ticker, action, realized_pnl, entry_time, exit_time, order_id = trade
                was_profitable = realized_pnl > 0
                
                result.trades_processed += 1
                
                # Step 2: Find matching pm_decision
                # Try by order_id first, then by ticker + timestamp proximity
                pm_decision = None
                
                if order_id:
                    pm_query = """
                        SELECT id, workflow_id, action
                        FROM pm_decisions
                        WHERE execution_order_id = :order_id
                        LIMIT 1
                    """
                    pm_result = session.execute(
                        text(pm_query), 
                        {"order_id": order_id}
                    ).fetchone()
                    
                    if pm_result:
                        pm_decision = pm_result
                
                # Fallback: match by ticker and time proximity (within 5 minutes)
                if not pm_decision and entry_time:
                    pm_query = """
                        SELECT id, workflow_id, action
                        FROM pm_decisions
                        WHERE ticker = :ticker
                        AND action NOT IN ('hold', 'cancel')
                        AND timestamp BETWEEN :start_time AND :end_time
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """
                    pm_result = session.execute(
                        text(pm_query),
                        {
                            "ticker": ticker,
                            "start_time": entry_time - timedelta(minutes=5),
                            "end_time": entry_time + timedelta(minutes=5),
                        }
                    ).fetchone()
                    
                    if pm_result:
                        pm_decision = pm_result
                
                if not pm_decision:
                    logger.debug(f"No pm_decision found for trade {trade_id} ({ticker})")
                    continue
                
                pm_id, workflow_id, pm_action = pm_decision
                
                # Step 3: Update pm_decision.was_profitable
                update_pm_query = """
                    UPDATE pm_decisions
                    SET was_profitable = :was_profitable,
                        actual_return = :actual_return
                    WHERE id = :pm_id
                """
                session.execute(
                    text(update_pm_query),
                    {
                        "was_profitable": was_profitable,
                        "actual_return": float(realized_pnl),
                        "pm_id": pm_id,
                    }
                )
                result.pm_decisions_updated += 1
                
                # Step 4: Update agent_signals.was_correct for this workflow + ticker
                # Logic:
                # - If PM action was BUY/COVER/LONG and profitable:
                #   - Bullish signals are correct
                #   - Bearish signals are incorrect
                # - If PM action was SELL/SHORT and profitable:
                #   - Bearish signals are correct
                #   - Bullish signals are incorrect
                # - If trade was NOT profitable, invert the above
                
                pm_direction = "long" if pm_action.lower() in ["buy", "cover", "long"] else "short"
                
                if was_profitable:
                    # Trade was profitable
                    if pm_direction == "long":
                        # Bullish signals were correct, bearish were wrong
                        correct_signal = "bullish"
                        incorrect_signal = "bearish"
                    else:
                        # Bearish signals were correct, bullish were wrong
                        correct_signal = "bearish"
                        incorrect_signal = "bullish"
                else:
                    # Trade was NOT profitable - invert
                    if pm_direction == "long":
                        correct_signal = "bearish"  # They were right not to buy
                        incorrect_signal = "bullish"  # They were wrong to suggest buy
                    else:
                        correct_signal = "bullish"
                        incorrect_signal = "bearish"
                
                # Update signals that match
                update_correct_query = """
                    UPDATE agent_signals
                    SET was_correct = TRUE,
                        actual_return = :actual_return
                    WHERE workflow_id = :workflow_id
                    AND ticker = :ticker
                    AND LOWER(signal) = :signal
                """
                session.execute(
                    text(update_correct_query),
                    {
                        "workflow_id": workflow_id,
                        "ticker": ticker,
                        "signal": correct_signal,
                        "actual_return": float(realized_pnl),
                    }
                )
                
                update_incorrect_query = """
                    UPDATE agent_signals
                    SET was_correct = FALSE,
                        actual_return = :actual_return
                    WHERE workflow_id = :workflow_id
                    AND ticker = :ticker
                    AND LOWER(signal) = :signal
                """
                session.execute(
                    text(update_incorrect_query),
                    {
                        "workflow_id": workflow_id,
                        "ticker": ticker,
                        "signal": incorrect_signal,
                        "actual_return": float(realized_pnl),
                    }
                )
                
                # Count how many agent signals were updated
                count_query = """
                    SELECT COUNT(*) FROM agent_signals
                    WHERE workflow_id = :workflow_id
                    AND ticker = :ticker
                    AND was_correct IS NOT NULL
                """
                count = session.execute(
                    text(count_query),
                    {"workflow_id": workflow_id, "ticker": ticker}
                ).scalar()
                
                result.agent_signals_updated += count or 0
            
            # Commit all updates
            session.commit()
            
            logger.info(
                f"Backfill complete: {result.trades_processed} trades, "
                f"{result.pm_decisions_updated} PM decisions, "
                f"{result.agent_signals_updated} agent signals updated"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Backfill failed: {e}", exc_info=True)
            session.rollback()
            result.errors.append(str(e))
            return result
        finally:
            session.close()
    
    async def get_accuracy_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current accuracy data.
        
        Returns counts of:
        - Total agent signals
        - Signals with was_correct populated
        - PM decisions with was_profitable populated
        """
        session = self._get_session()
        if not session:
            return {"error": "No database session"}
        
        try:
            from sqlalchemy import text
            
            # Agent signals summary
            agent_query = """
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE was_correct IS NOT NULL) as with_outcome,
                    COUNT(*) FILTER (WHERE was_correct = TRUE) as correct,
                    COUNT(*) FILTER (WHERE was_correct = FALSE) as incorrect
                FROM agent_signals
                WHERE timestamp > NOW() - INTERVAL '30 days'
            """
            agent_result = session.execute(text(agent_query)).fetchone()
            
            # PM decisions summary
            pm_query = """
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE was_profitable IS NOT NULL) as with_outcome,
                    COUNT(*) FILTER (WHERE was_profitable = TRUE) as profitable,
                    COUNT(*) FILTER (WHERE was_profitable = FALSE) as unprofitable
                FROM pm_decisions
                WHERE timestamp > NOW() - INTERVAL '30 days'
            """
            pm_result = session.execute(text(pm_query)).fetchone()
            
            # Trade history summary
            trade_query = """
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'closed') as closed,
                    COUNT(*) FILTER (WHERE realized_pnl > 0) as profitable,
                    COUNT(*) FILTER (WHERE realized_pnl < 0) as unprofitable
                FROM trade_history
                WHERE created_at > NOW() - INTERVAL '30 days'
            """
            trade_result = session.execute(text(trade_query)).fetchone()
            
            return {
                "agent_signals": {
                    "total": agent_result[0] if agent_result else 0,
                    "with_outcome": agent_result[1] if agent_result else 0,
                    "correct": agent_result[2] if agent_result else 0,
                    "incorrect": agent_result[3] if agent_result else 0,
                    "coverage_pct": round((agent_result[1] / agent_result[0] * 100) if agent_result and agent_result[0] > 0 else 0, 1),
                },
                "pm_decisions": {
                    "total": pm_result[0] if pm_result else 0,
                    "with_outcome": pm_result[1] if pm_result else 0,
                    "profitable": pm_result[2] if pm_result else 0,
                    "unprofitable": pm_result[3] if pm_result else 0,
                    "coverage_pct": round((pm_result[1] / pm_result[0] * 100) if pm_result and pm_result[0] > 0 else 0, 1),
                },
                "trades": {
                    "total": trade_result[0] if trade_result else 0,
                    "closed": trade_result[1] if trade_result else 0,
                    "profitable": trade_result[2] if trade_result else 0,
                    "unprofitable": trade_result[3] if trade_result else 0,
                },
            }
            
        except Exception as e:
            logger.error(f"Failed to get accuracy summary: {e}")
            return {"error": str(e)}
        finally:
            session.close()


# Singleton instance
_accuracy_backfill_service = None


def get_accuracy_backfill_service() -> AccuracyBackfillService:
    """Get the global accuracy backfill service instance."""
    global _accuracy_backfill_service
    if _accuracy_backfill_service is None:
        _accuracy_backfill_service = AccuracyBackfillService()
    return _accuracy_backfill_service
