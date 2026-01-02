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
    """
    Get performance metrics for all AI agents.
    
    Merges data from two sources:
    - agent_signals: Real-time signal counts, confidence averages
    - agent_performance: Accuracy metrics computed from closed trades (via accuracy backfill)
    
    Agents that only appear in agent_signals will have accuracy fields set to null.
    """
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        agents_data = {}
        
        with engine.connect() as conn:
            # Query 1: Aggregate signal data from agent_signals (all signals ever logged)
            signals_query = """
                SELECT 
                    agent_id,
                    COUNT(*) as total_signals,
                    AVG(confidence) as avg_confidence,
                    COUNT(CASE WHEN LOWER(signal) = 'bullish' THEN 1 END) as bullish_count,
                    COUNT(CASE WHEN LOWER(signal) = 'bearish' THEN 1 END) as bearish_count,
                    COUNT(CASE WHEN LOWER(signal) IN ('neutral', 'hold') THEN 1 END) as neutral_count,
                    COUNT(CASE WHEN was_correct = true THEN 1 END) as correct_count,
                    COUNT(CASE WHEN was_correct = false THEN 1 END) as incorrect_count,
                    AVG(actual_return) FILTER (WHERE actual_return IS NOT NULL) as avg_return,
                    MAX(timestamp) as last_signal
                FROM agent_signals
                GROUP BY agent_id
                ORDER BY total_signals DESC
            """
            
            result = conn.execute(text(signals_query))
            for row in result.fetchall():
                agent_id = row[0]
                correct = row[6] or 0
                incorrect = row[7] or 0
                
                # Calculate accuracy from was_correct if available
                accuracy = None
                if correct + incorrect > 0:
                    accuracy = round((correct / (correct + incorrect)) * 100, 2)
                
                agents_data[agent_id] = {
                    "name": agent_id,
                    "type": _get_agent_type(agent_id),
                    "total_signals": row[1] or 0,
                    "avg_confidence": round(float(row[2]), 2) if row[2] else None,
                    "bullish_signals": row[3] or 0,
                    "bearish_signals": row[4] or 0,
                    "neutral_signals": row[5] or 0,
                    "correct_predictions": correct,
                    "incorrect_predictions": incorrect,
                    "accuracy_rate": accuracy,
                    "avg_return_when_followed": round(float(row[8]), 2) if row[8] else None,
                    "last_signal": row[9].isoformat() if row[9] else None,
                    "best_call": None,
                    "worst_call": None,
                }
            
            # Query 2: Get pre-computed accuracy metrics from agent_performance (if any exist)
            # This table is populated by the accuracy backfill service
            perf_query = """
                SELECT 
                    agent_name,
                    agent_type,
                    accuracy_rate,
                    correct_predictions,
                    incorrect_predictions,
                    avg_return_when_followed,
                    total_pnl_when_followed,
                    best_call_ticker,
                    best_call_return,
                    worst_call_ticker,
                    worst_call_return,
                    last_accuracy_update
                FROM agent_performance
            """
            
            try:
                result = conn.execute(text(perf_query))
                for row in result.fetchall():
                    agent_name = row[0]
                    
                    if agent_name in agents_data:
                        # Merge: prefer agent_performance accuracy if available
                        if row[2] is not None:
                            agents_data[agent_name]["accuracy_rate"] = round(float(row[2]), 2)
                        if row[3] is not None:
                            agents_data[agent_name]["correct_predictions"] = row[3]
                        if row[4] is not None:
                            agents_data[agent_name]["incorrect_predictions"] = row[4]
                        if row[5] is not None:
                            agents_data[agent_name]["avg_return_when_followed"] = round(float(row[5]), 2)
                        
                        # Best/worst calls only if both ticker and return present
                        if row[7] and row[8] is not None:
                            agents_data[agent_name]["best_call"] = {
                                "ticker": row[7],
                                "return": round(float(row[8]), 2)
                            }
                        if row[9] and row[10] is not None:
                            agents_data[agent_name]["worst_call"] = {
                                "ticker": row[9],
                                "return": round(float(row[10]), 2)
                            }
                    else:
                        # Agent exists in performance table but not in signals
                        agents_data[agent_name] = {
                            "name": agent_name,
                            "type": row[1] or _get_agent_type(agent_name),
                            "total_signals": 0,
                            "avg_confidence": None,
                            "bullish_signals": 0,
                            "bearish_signals": 0,
                            "neutral_signals": 0,
                            "correct_predictions": row[3] or 0,
                            "incorrect_predictions": row[4] or 0,
                            "accuracy_rate": round(float(row[2]), 2) if row[2] else None,
                            "avg_return_when_followed": round(float(row[5]), 2) if row[5] else None,
                            "last_signal": None,
                            "best_call": {"ticker": row[7], "return": round(float(row[8]), 2)} if row[7] and row[8] is not None else None,
                            "worst_call": {"ticker": row[9], "return": round(float(row[10]), 2)} if row[9] and row[10] is not None else None,
                        }
            except Exception as e:
                # agent_performance table might not exist or be empty - that's OK
                import logging
                logging.debug(f"No agent_performance data: {e}")
        
        # Sort by total_signals descending
        agents = sorted(agents_data.values(), key=lambda x: x["total_signals"], reverse=True)
        
        return {
            "success": True,
            "agents": agents,
            "count": len(agents),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_agent_type(agent_id: str) -> str:
    """Map agent ID to human-readable type/style."""
    type_map = {
        "warren_buffett": "Value Investing",
        "ben_graham": "Deep Value",
        "charlie_munger": "Quality/Moats",
        "peter_lynch": "GARP",
        "cathie_wood": "Disruptive Innovation",
        "michael_burry": "Contrarian",
        "bill_ackman": "Activist Value",
        "stanley_druckenmiller": "Macro/Momentum",
        "aswath_damodaran": "Valuation Expert",
        "mohnish_pabrai": "Dhandho Value",
        "phil_fisher": "Scuttlebutt",
        "rakesh_jhunjhunwala": "Bull Momentum",
        "fundamentals": "Financial Analysis",
        "technicals": "Technical Analysis",
        "valuation": "DCF/Relative",
        "growth": "Growth Analysis",
        "sentiment": "Market Sentiment",
        "news_sentiment": "News Analysis",
        "risk_manager": "Risk Management",
        "portfolio_manager": "Portfolio Decisions",
    }
    
    # Normalize agent_id by removing common suffixes
    normalized = agent_id.lower().replace("_agent", "").replace("_analyst", "")
    
    for key, value in type_map.items():
        if key in normalized or normalized in key:
            return value
    
    return "AI Analyst"


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
