"""
Trade History and Agent Performance API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.backend.database.connection import get_db
from app.backend.database.models import TradeHistory, TradeDecisionContext, AgentPerformance

router = APIRouter(prefix="/history", tags=["Trade History"])


@router.get("/trades")
async def get_trade_history(
    ticker: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    include_context: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get trade history with full decision context.
    
    - ticker: Filter by stock symbol
    - status: Filter by trade status (pending, filled, closed)
    - limit: Max trades to return
    - include_context: Include agent signals and PM reasoning
    """
    try:
        query = db.query(TradeHistory)
        
        if ticker:
            query = query.filter(TradeHistory.ticker == ticker.upper())
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
                "created_at": trade.created_at.isoformat() if trade.created_at else None,
            }
            
            if include_context:
                context = db.query(TradeDecisionContext).filter_by(trade_id=trade.id).first()
                if context:
                    trade_dict["context"] = {
                        "trigger_source": context.trigger_source,
                        "workflow_mode": context.workflow_mode,
                        "strategy_signal": context.strategy_signal,
                        "strategy_confidence": context.strategy_confidence,
                        "mazo_sentiment": context.mazo_sentiment,
                        "mazo_key_points": context.mazo_key_points,
                        "consensus_direction": context.consensus_direction,
                        "consensus_confidence": context.consensus_confidence,
                        "bullish_count": context.bullish_count,
                        "bearish_count": context.bearish_count,
                        "neutral_count": context.neutral_count,
                        "pm_action": context.pm_action,
                        "pm_reasoning": context.pm_reasoning,
                        "pm_confidence": context.pm_confidence,
                        "agent_signals": context.agent_signals,
                        "was_profitable": context.was_profitable,
                        "portfolio_equity": context.portfolio_equity,
                    }
            
            results.append(trade_dict)
        
        return {
            "success": True,
            "trades": results,
            "count": len(results),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades/{trade_id}")
async def get_trade_detail(
    trade_id: int,
    db: Session = Depends(get_db)
):
    """Get full details for a specific trade."""
    try:
        trade = db.query(TradeHistory).filter_by(id=trade_id).first()
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        
        context = db.query(TradeDecisionContext).filter_by(trade_id=trade_id).first()
        
        return {
            "success": True,
            "trade": {
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
                "stop_loss_pct": trade.stop_loss_pct,
                "take_profit_pct": trade.take_profit_pct,
                "strategy": trade.strategy,
                "strategy_params": trade.strategy_params,
                "realized_pnl": trade.realized_pnl,
                "return_pct": trade.return_pct,
                "holding_period_hours": trade.holding_period_hours,
                "status": trade.status,
                "notes": trade.notes,
                "signals": trade.signals,
            },
            "context": {
                "trigger_source": context.trigger_source,
                "workflow_mode": context.workflow_mode,
                "strategy_signal": context.strategy_signal,
                "strategy_confidence": context.strategy_confidence,
                "strategy_reasoning": context.strategy_reasoning,
                "mazo_sentiment": context.mazo_sentiment,
                "mazo_confidence": context.mazo_confidence,
                "mazo_key_points": context.mazo_key_points,
                "mazo_full_response": context.mazo_full_response,
                "agent_signals": context.agent_signals,
                "bullish_count": context.bullish_count,
                "bearish_count": context.bearish_count,
                "neutral_count": context.neutral_count,
                "consensus_direction": context.consensus_direction,
                "consensus_confidence": context.consensus_confidence,
                "portfolio_equity": context.portfolio_equity,
                "portfolio_cash": context.portfolio_cash,
                "existing_positions": context.existing_positions,
                "pending_orders": context.pending_orders,
                "pm_action": context.pm_action,
                "pm_quantity": context.pm_quantity,
                "pm_confidence": context.pm_confidence,
                "pm_reasoning": context.pm_reasoning,
                "pm_stop_loss_pct": context.pm_stop_loss_pct,
                "pm_take_profit_pct": context.pm_take_profit_pct,
                "actual_return": context.actual_return,
                "was_profitable": context.was_profitable,
                "outcome_notes": context.outcome_notes,
            } if context else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_performance_summary(
    db: Session = Depends(get_db)
):
    """Get overall trading performance summary."""
    try:
        closed_trades = db.query(TradeHistory).filter(
            TradeHistory.status == "closed"
        ).all()
        
        if not closed_trades:
            return {
                "success": True,
                "has_data": False,
                "message": "No closed trades yet",
                "summary": {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": None,
                    "total_pnl": 0,
                    "avg_return_pct": None,
                }
            }
        
        total_pnl = sum(t.realized_pnl or 0 for t in closed_trades)
        winners = [t for t in closed_trades if (t.realized_pnl or 0) > 0]
        losers = [t for t in closed_trades if (t.realized_pnl or 0) < 0]
        
        avg_return = sum(t.return_pct or 0 for t in closed_trades) / len(closed_trades)
        avg_hold_time = sum(t.holding_period_hours or 0 for t in closed_trades) / len(closed_trades)
        
        best_trade = max(closed_trades, key=lambda t: t.realized_pnl or 0)
        worst_trade = min(closed_trades, key=lambda t: t.realized_pnl or 0)
        
        return {
            "success": True,
            "has_data": True,
            "summary": {
                "total_trades": len(closed_trades),
                "winning_trades": len(winners),
                "losing_trades": len(losers),
                "win_rate": round(len(winners) / len(closed_trades) * 100, 2) if closed_trades else None,
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
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def get_agent_performance(
    db: Session = Depends(get_db)
):
    """Get performance metrics for all AI agents."""
    try:
        agents = db.query(AgentPerformance).order_by(
            AgentPerformance.accuracy_rate.desc().nullslast()
        ).all()
        
        return {
            "success": True,
            "agents": [
                {
                    "name": a.agent_name,
                    "type": a.agent_type,
                    "total_signals": a.total_signals,
                    "bullish_signals": a.bullish_signals,
                    "bearish_signals": a.bearish_signals,
                    "neutral_signals": a.neutral_signals,
                    "accuracy_rate": round(a.accuracy_rate, 2) if a.accuracy_rate else None,
                    "correct_predictions": a.correct_predictions,
                    "incorrect_predictions": a.incorrect_predictions,
                    "trades_following": a.trades_following_signal,
                    "avg_return_when_followed": round(a.avg_return_when_followed, 2) if a.avg_return_when_followed else None,
                    "total_pnl_when_followed": round(a.total_pnl_when_followed, 2),
                    "best_call": {
                        "ticker": a.best_call_ticker,
                        "return": a.best_call_return,
                    } if a.best_call_ticker else None,
                    "worst_call": {
                        "ticker": a.worst_call_ticker,
                        "return": a.worst_call_return,
                    } if a.worst_call_ticker else None,
                    "last_signal": a.last_signal_date.isoformat() if a.last_signal_date else None,
                }
                for a in agents
            ],
            "count": len(agents),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_name}")
async def get_agent_detail(
    agent_name: str,
    db: Session = Depends(get_db)
):
    """Get detailed performance for a specific agent."""
    try:
        agent = db.query(AgentPerformance).filter_by(agent_name=agent_name).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Get trades where this agent gave signals
        contexts = db.query(TradeDecisionContext).filter(
            TradeDecisionContext.agent_signals.contains({agent_name: {}})
        ).order_by(TradeDecisionContext.created_at.desc()).limit(20).all()
        
        recent_signals = []
        for ctx in contexts:
            if ctx.agent_signals and agent_name in ctx.agent_signals:
                signal_data = ctx.agent_signals[agent_name]
                recent_signals.append({
                    "ticker": ctx.ticker,
                    "signal": signal_data.get("signal") if isinstance(signal_data, dict) else None,
                    "confidence": signal_data.get("confidence") if isinstance(signal_data, dict) else None,
                    "pm_action": ctx.pm_action,
                    "was_profitable": ctx.was_profitable,
                    "actual_return": ctx.actual_return,
                    "date": ctx.created_at.isoformat() if ctx.created_at else None,
                })
        
        return {
            "success": True,
            "agent": {
                "name": agent.agent_name,
                "type": agent.agent_type,
                "total_signals": agent.total_signals,
                "bullish_signals": agent.bullish_signals,
                "bearish_signals": agent.bearish_signals,
                "neutral_signals": agent.neutral_signals,
                "accuracy_rate": round(agent.accuracy_rate, 2) if agent.accuracy_rate else None,
                "correct_predictions": agent.correct_predictions,
                "incorrect_predictions": agent.incorrect_predictions,
                "trades_following": agent.trades_following_signal,
                "avg_return_when_followed": round(agent.avg_return_when_followed, 2) if agent.avg_return_when_followed else None,
                "total_pnl_when_followed": round(agent.total_pnl_when_followed, 2),
                "best_call": {
                    "ticker": agent.best_call_ticker,
                    "return": agent.best_call_return,
                } if agent.best_call_ticker else None,
                "worst_call": {
                    "ticker": agent.worst_call_ticker,
                    "return": agent.worst_call_return,
                } if agent.worst_call_ticker else None,
            },
            "recent_signals": recent_signals,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
