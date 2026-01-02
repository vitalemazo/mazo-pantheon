"""
Trade History Service

Records all trades with full context including:
- Agent signals that led to the trade
- Mazo research summary
- PM reasoning
- Portfolio state at decision time
- Outcome tracking

This enables:
- Trade journaling
- Agent performance tracking
- Strategy analysis
- Learning from past decisions
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Complete record of a trade with full context"""
    ticker: str
    action: str
    quantity: float  # Supports fractional shares
    entry_price: Optional[float] = None
    order_id: Optional[str] = None
    fractionable: bool = True  # Whether the asset supports fractional trading
    
    # Trigger info
    trigger_source: str = "manual"  # manual, scheduler, automated
    workflow_mode: Optional[str] = None
    
    # Strategy signal
    strategy_name: Optional[str] = None
    strategy_signal: Optional[str] = None
    strategy_confidence: Optional[float] = None
    strategy_reasoning: Optional[str] = None
    
    # Mazo info
    mazo_sentiment: Optional[str] = None
    mazo_confidence: Optional[str] = None
    mazo_key_points: Optional[List[str]] = None
    mazo_response: Optional[str] = None
    
    # Agent signals
    agent_signals: Dict[str, Dict[str, Any]] = None
    
    # Consensus
    consensus_direction: Optional[str] = None
    consensus_confidence: Optional[float] = None
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    
    # Portfolio context
    portfolio_equity: Optional[float] = None
    portfolio_cash: Optional[float] = None
    existing_positions: Optional[List[Dict]] = None
    pending_orders: Optional[List[Dict]] = None
    
    # PM decision
    pm_action: Optional[str] = None
    pm_quantity: Optional[float] = None  # Supports fractional shares
    pm_confidence: Optional[float] = None
    pm_reasoning: Optional[str] = None
    pm_stop_loss_pct: Optional[float] = None
    pm_take_profit_pct: Optional[float] = None
    
    # Risk levels
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None


class TradeHistoryService:
    """
    Service for recording and querying trade history.
    
    Every trade should be recorded with full context so we can:
    1. See what signals led to each trade
    2. Track which agents were accurate
    3. Learn from winning and losing trades
    """
    
    def __init__(self, db_session: Session = None):
        self.db_session = db_session
    
    def record_trade(self, record: TradeRecord) -> int:
        """
        Record a new trade with full context.
        
        Returns:
            Trade ID in database
        """
        if not self.db_session:
            logger.warning("No database session - trade not persisted")
            return -1
        
        try:
            from app.backend.database.models import TradeHistory, TradeDecisionContext
            
            # Create trade history record
            trade = TradeHistory(
                order_id=record.order_id,
                ticker=record.ticker,
                action=record.action,
                quantity=record.quantity,
                entry_price=record.entry_price,
                entry_time=datetime.now(),
                stop_loss_price=record.stop_loss_price,
                take_profit_price=record.take_profit_price,
                stop_loss_pct=record.pm_stop_loss_pct,
                take_profit_pct=record.pm_take_profit_pct,
                strategy=record.strategy_name,
                status="pending",
                signals=record.agent_signals or {},
            )
            
            self.db_session.add(trade)
            self.db_session.flush()  # Get the ID
            
            # Create decision context record
            context = TradeDecisionContext(
                trade_id=trade.id,
                order_id=record.order_id,
                ticker=record.ticker,
                trigger_source=record.trigger_source,
                workflow_mode=record.workflow_mode,
                strategy_signal=record.strategy_signal,
                strategy_confidence=record.strategy_confidence,
                strategy_name=record.strategy_name,
                strategy_reasoning=record.strategy_reasoning,
                mazo_sentiment=record.mazo_sentiment,
                mazo_confidence=record.mazo_confidence,
                mazo_key_points=record.mazo_key_points,
                mazo_full_response=record.mazo_response,
                agent_signals=record.agent_signals or {},
                bullish_count=record.bullish_count,
                bearish_count=record.bearish_count,
                neutral_count=record.neutral_count,
                consensus_direction=record.consensus_direction,
                consensus_confidence=record.consensus_confidence,
                portfolio_equity=record.portfolio_equity,
                portfolio_cash=record.portfolio_cash,
                existing_positions=record.existing_positions,
                pending_orders=record.pending_orders,
                pm_action=record.pm_action,
                pm_quantity=record.pm_quantity,
                pm_confidence=record.pm_confidence,
                pm_reasoning=record.pm_reasoning,
                pm_stop_loss_pct=record.pm_stop_loss_pct,
                pm_take_profit_pct=record.pm_take_profit_pct,
            )
            
            self.db_session.add(context)
            self.db_session.commit()
            
            logger.info(f"Recorded trade {trade.id}: {record.action} {record.quantity} {record.ticker}")
            
            # Update agent performance stats
            self._update_agent_stats(record)
            
            return trade.id
            
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
            if self.db_session:
                self.db_session.rollback()
            return -1
    
    def close_trade(
        self, 
        trade_id: int, 
        exit_price: float,
        realized_pnl: float = None,
        notes: str = None
    ) -> bool:
        """
        Mark a trade as closed and calculate returns.
        
        This also updates agent accuracy metrics.
        """
        if not self.db_session:
            return False
        
        try:
            from app.backend.database.models import TradeHistory, TradeDecisionContext
            
            trade = self.db_session.query(TradeHistory).filter_by(id=trade_id).first()
            if not trade:
                logger.warning(f"Trade {trade_id} not found")
                return False
            
            # Update trade
            trade.exit_price = exit_price
            trade.exit_time = datetime.now()
            trade.status = "closed"
            
            # Calculate P&L if not provided
            if realized_pnl is not None:
                trade.realized_pnl = realized_pnl
            elif trade.entry_price:
                if trade.action in ["buy", "cover"]:
                    trade.realized_pnl = (exit_price - trade.entry_price) * trade.quantity
                else:  # sell, short
                    trade.realized_pnl = (trade.entry_price - exit_price) * trade.quantity
            
            # Calculate return percentage
            if trade.entry_price and trade.entry_price > 0:
                trade.return_pct = ((exit_price - trade.entry_price) / trade.entry_price) * 100
                if trade.action in ["sell", "short"]:
                    trade.return_pct = -trade.return_pct
            
            # Calculate holding period
            if trade.entry_time:
                holding_delta = datetime.now() - trade.entry_time
                trade.holding_period_hours = holding_delta.total_seconds() / 3600
            
            if notes:
                trade.notes = notes
            
            # Update decision context with outcome
            context = self.db_session.query(TradeDecisionContext).filter_by(trade_id=trade_id).first()
            if context:
                context.actual_return = trade.return_pct
                context.was_profitable = (trade.realized_pnl or 0) > 0
                context.outcome_notes = notes
                
                # Update agent accuracy
                self._update_agent_accuracy(context, was_profitable=context.was_profitable)
            
            self.db_session.commit()
            logger.info(f"Closed trade {trade_id}: ${trade.realized_pnl:.2f} ({trade.return_pct:.2f}%)")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to close trade: {e}")
            if self.db_session:
                self.db_session.rollback()
            return False
    
    def get_trade_history(
        self, 
        ticker: str = None,
        status: str = None,
        limit: int = 50,
        include_context: bool = True
    ) -> List[Dict[str, Any]]:
        """Get trade history with optional filtering."""
        if not self.db_session:
            return []
        
        try:
            from app.backend.database.models import TradeHistory, TradeDecisionContext
            
            query = self.db_session.query(TradeHistory)
            
            if ticker:
                query = query.filter(TradeHistory.ticker == ticker)
            if status:
                query = query.filter(TradeHistory.status == status)
            
            trades = query.order_by(TradeHistory.created_at.desc()).limit(limit).all()
            
            results = []
            for trade in trades:
                trade_dict = {
                    "id": trade.id,
                    "order_id": trade.order_id,
                    "ticker": trade.ticker,
                    "action": trade.action,
                    "quantity": trade.quantity,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "entry_time": trade.entry_time.isoformat() if trade.entry_time else None,
                    "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
                    "stop_loss_price": trade.stop_loss_price,
                    "take_profit_price": trade.take_profit_price,
                    "strategy": trade.strategy,
                    "realized_pnl": trade.realized_pnl,
                    "return_pct": trade.return_pct,
                    "holding_period_hours": trade.holding_period_hours,
                    "status": trade.status,
                    "notes": trade.notes,
                }
                
                # Add context if requested
                if include_context:
                    context = self.db_session.query(TradeDecisionContext).filter_by(
                        trade_id=trade.id
                    ).first()
                    
                    if context:
                        trade_dict["context"] = {
                            "trigger_source": context.trigger_source,
                            "workflow_mode": context.workflow_mode,
                            "strategy_signal": context.strategy_signal,
                            "strategy_confidence": context.strategy_confidence,
                            "mazo_sentiment": context.mazo_sentiment,
                            "consensus_direction": context.consensus_direction,
                            "consensus_confidence": context.consensus_confidence,
                            "bullish_count": context.bullish_count,
                            "bearish_count": context.bearish_count,
                            "neutral_count": context.neutral_count,
                            "pm_reasoning": context.pm_reasoning,
                            "agent_signals": context.agent_signals,
                            "was_profitable": context.was_profitable,
                        }
                
                results.append(trade_dict)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get trade history: {e}")
            return []
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall trading performance summary."""
        if not self.db_session:
            return {}
        
        try:
            from app.backend.database.models import TradeHistory
            from sqlalchemy import func
            
            # Get closed trades
            closed_trades = self.db_session.query(TradeHistory).filter(
                TradeHistory.status == "closed"
            ).all()
            
            if not closed_trades:
                return {
                    "total_trades": 0,
                    "message": "No closed trades yet"
                }
            
            total_pnl = sum(t.realized_pnl or 0 for t in closed_trades)
            winners = [t for t in closed_trades if (t.realized_pnl or 0) > 0]
            losers = [t for t in closed_trades if (t.realized_pnl or 0) < 0]
            
            avg_return = sum(t.return_pct or 0 for t in closed_trades) / len(closed_trades)
            avg_hold_time = sum(t.holding_period_hours or 0 for t in closed_trades) / len(closed_trades)
            
            # Best and worst trades
            best_trade = max(closed_trades, key=lambda t: t.realized_pnl or 0)
            worst_trade = min(closed_trades, key=lambda t: t.realized_pnl or 0)
            
            return {
                "total_trades": len(closed_trades),
                "winning_trades": len(winners),
                "losing_trades": len(losers),
                "win_rate": len(winners) / len(closed_trades) * 100 if closed_trades else 0,
                "total_pnl": round(total_pnl, 2),
                "avg_return_pct": round(avg_return, 2),
                "avg_holding_hours": round(avg_hold_time, 2),
                "best_trade": {
                    "ticker": best_trade.ticker,
                    "pnl": best_trade.realized_pnl,
                    "return_pct": best_trade.return_pct,
                },
                "worst_trade": {
                    "ticker": worst_trade.ticker,
                    "pnl": worst_trade.realized_pnl,
                    "return_pct": worst_trade.return_pct,
                },
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {}
    
    def _update_agent_stats(self, record: TradeRecord):
        """Update agent signal statistics when a trade is recorded."""
        if not self.db_session or not record.agent_signals:
            return
        
        try:
            from app.backend.database.models import AgentPerformance
            
            for agent_name, signal_data in record.agent_signals.items():
                # Get or create agent record
                agent = self.db_session.query(AgentPerformance).filter_by(
                    agent_name=agent_name
                ).first()
                
                if not agent:
                    agent = AgentPerformance(agent_name=agent_name)
                    self.db_session.add(agent)
                
                # Update signal counts
                agent.total_signals += 1
                signal = signal_data.get("signal", "").lower() if isinstance(signal_data, dict) else ""
                
                if "bullish" in signal or "buy" in signal:
                    agent.bullish_signals += 1
                elif "bearish" in signal or "sell" in signal or "short" in signal:
                    agent.bearish_signals += 1
                else:
                    agent.neutral_signals += 1
                
                agent.last_signal_date = datetime.now()
            
            self.db_session.commit()
            
        except Exception as e:
            logger.error(f"Failed to update agent stats: {e}")
    
    def _update_agent_accuracy(self, context, was_profitable: bool):
        """Update agent accuracy when a trade closes."""
        if not self.db_session or not context.agent_signals:
            return
        
        try:
            from app.backend.database.models import AgentPerformance
            
            for agent_name, signal_data in context.agent_signals.items():
                agent = self.db_session.query(AgentPerformance).filter_by(
                    agent_name=agent_name
                ).first()
                
                if not agent:
                    continue
                
                # Determine if agent's signal was "correct"
                signal = signal_data.get("signal", "").lower() if isinstance(signal_data, dict) else ""
                action = context.pm_action or ""
                
                # Agent was right if:
                # - Bullish signal + profitable buy/cover
                # - Bearish signal + profitable sell/short
                agent_bullish = "bullish" in signal or "buy" in signal
                action_bullish = action in ["buy", "cover"]
                
                if agent_bullish == action_bullish:
                    # Agent agreed with action
                    agent.trades_following_signal += 1
                    
                    if was_profitable:
                        agent.correct_predictions += 1
                        
                        # Update best call if this is better
                        actual_return = context.actual_return or 0
                        if agent.best_call_return is None or actual_return > agent.best_call_return:
                            agent.best_call_return = actual_return
                            agent.best_call_ticker = context.ticker
                        
                        agent.total_pnl_when_followed += actual_return
                    else:
                        agent.incorrect_predictions += 1
                        
                        # Update worst call
                        actual_return = context.actual_return or 0
                        if agent.worst_call_return is None or actual_return < agent.worst_call_return:
                            agent.worst_call_return = actual_return
                            agent.worst_call_ticker = context.ticker
                
                # Calculate accuracy rate
                total_predictions = agent.correct_predictions + agent.incorrect_predictions
                if total_predictions > 0:
                    agent.accuracy_rate = agent.correct_predictions / total_predictions * 100
                
                # Calculate avg return when followed
                if agent.trades_following_signal > 0:
                    agent.avg_return_when_followed = agent.total_pnl_when_followed / agent.trades_following_signal
                
                agent.last_accuracy_update = datetime.now()
            
            self.db_session.commit()
            
        except Exception as e:
            logger.error(f"Failed to update agent accuracy: {e}")


# Global instance
_trade_history_service: Optional[TradeHistoryService] = None


def get_trade_history_service(db_session: Session = None) -> TradeHistoryService:
    """Get or create the trade history service."""
    global _trade_history_service
    if _trade_history_service is None or db_session is not None:
        _trade_history_service = TradeHistoryService(db_session)
    return _trade_history_service
