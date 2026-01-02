"""
Transparency API Routes

Provides full visibility into the AI trading decision pipeline.
The "Round Table" endpoint aggregates all stages of a trading cycle.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transparency", tags=["Transparency"])


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class StrategyStage(BaseModel):
    """Strategy Engine screening results"""
    tickers_scanned: int = 0
    signals_found: int = 0
    signals: List[Dict[str, Any]] = []
    timestamp: Optional[str] = None
    duration_ms: Optional[int] = None


class MazoStage(BaseModel):
    """Mazo research results"""
    ticker: Optional[str] = None
    query: Optional[str] = None
    summary: Optional[str] = None
    sentiment: Optional[str] = None
    sentiment_confidence: Optional[str] = None
    key_points: List[str] = []
    sources_count: int = 0
    sources: List[Dict[str, Any]] = []
    timestamp: Optional[str] = None
    duration_ms: Optional[int] = None
    success: bool = False


class AgentSignalData(BaseModel):
    """Individual agent signal"""
    agent_id: str
    agent_type: Optional[str] = None
    signal: str  # bullish, bearish, neutral
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    key_metrics: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None
    was_correct: Optional[bool] = None
    accuracy_rate: Optional[float] = None  # Historical accuracy


class AgentsStage(BaseModel):
    """All 18 AI agent signals"""
    ticker: Optional[str] = None
    agents: List[AgentSignalData] = []
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    consensus: Optional[str] = None
    consensus_score: Optional[float] = None
    agreement_pct: Optional[float] = None
    timestamp: Optional[str] = None
    total_duration_ms: Optional[int] = None


class PortfolioManagerStage(BaseModel):
    """Portfolio Manager decision"""
    ticker: Optional[str] = None
    action: Optional[str] = None
    quantity: Optional[int] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    position_size_pct: Optional[float] = None
    reasoning: Optional[str] = None
    confidence: Optional[float] = None
    
    # Context
    portfolio_equity: Optional[float] = None
    portfolio_cash: Optional[float] = None
    existing_position: Optional[float] = None
    
    # Consensus alignment
    action_matches_consensus: Optional[bool] = None
    override_reason: Optional[str] = None
    
    # Agent weighting
    agents_considered: Optional[Dict[str, Any]] = None
    agents_ignored: Optional[Dict[str, Any]] = None
    
    timestamp: Optional[str] = None
    duration_ms: Optional[int] = None


class ExecutionStage(BaseModel):
    """Trade execution details"""
    order_id: Optional[str] = None
    ticker: Optional[str] = None
    side: Optional[str] = None
    order_type: Optional[str] = None
    quantity: Optional[float] = None
    limit_price: Optional[float] = None
    
    # Fill details
    status: Optional[str] = None
    filled_qty: Optional[float] = None
    filled_avg_price: Optional[float] = None
    slippage_bps: Optional[float] = None
    
    # Timing
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None
    fill_latency_ms: Optional[int] = None
    
    # Errors
    error: Optional[str] = None


class PostTradeStage(BaseModel):
    """Post-trade monitoring status"""
    trade_id: Optional[int] = None
    ticker: Optional[str] = None
    status: Optional[str] = None  # pending, open, closed
    
    # Position monitoring
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    
    # Stop/Take levels
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    stop_loss_triggered: bool = False
    take_profit_triggered: bool = False
    
    # Outcome (if closed)
    exit_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    return_pct: Optional[float] = None
    
    # Notes
    sync_status: Optional[str] = None
    notes: Optional[str] = None


class ConsensusMeter(BaseModel):
    """AI Consensus summary"""
    total_agents: int = 0
    bullish_pct: float = 0
    bearish_pct: float = 0
    neutral_pct: float = 0
    agreement_pct: float = 0
    conviction_met: bool = False
    conviction_threshold: float = 65
    recommendation: Optional[str] = None


class RoundTableResponse(BaseModel):
    """Complete Round Table transparency view"""
    workflow_id: Optional[str] = None
    workflow_type: Optional[str] = None
    ticker: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_duration_ms: Optional[int] = None
    status: str = "unknown"  # running, completed, failed, dry_run
    
    # Pipeline stages
    strategy: StrategyStage = StrategyStage()
    mazo: MazoStage = MazoStage()
    agents: AgentsStage = AgentsStage()
    portfolio_manager: PortfolioManagerStage = PortfolioManagerStage()
    execution: ExecutionStage = ExecutionStage()
    post_trade: PostTradeStage = PostTradeStage()
    
    # Summary
    consensus: ConsensusMeter = ConsensusMeter()
    
    # Errors
    errors: List[str] = []


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_agent_accuracy(agent_id: str, conn) -> Optional[float]:
    """Get historical accuracy rate for an agent."""
    try:
        from sqlalchemy import text
        result = conn.execute(text("""
            SELECT accuracy_rate FROM agent_performance 
            WHERE agent_name = :agent_id
        """), {"agent_id": agent_id})
        row = result.fetchone()
        return float(row[0]) if row and row[0] else None
    except:
        return None


def _get_agent_type(agent_id: str) -> str:
    """Map agent ID to type."""
    types = {
        "warren_buffett": "value",
        "charlie_munger": "value", 
        "ben_graham": "value",
        "peter_lynch": "growth",
        "cathie_wood": "growth",
        "phil_fisher": "growth",
        "stanley_druckenmiller": "macro",
        "michael_burry": "contrarian",
        "bill_ackman": "activist",
        "mohnish_pabrai": "value",
        "rakesh_jhunjhunwala": "growth",
        "aswath_damodaran": "valuation",
        "fundamentals_analyst": "fundamental",
        "technicals_analyst": "technical",
        "sentiment_analyst": "sentiment",
        "valuation_analyst": "valuation",
        "risk_manager": "risk",
        "news_sentiment_analyst": "sentiment",
    }
    return types.get(agent_id, "analyst")


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/round-table", response_model=RoundTableResponse)
async def get_round_table(
    workflow_id: Optional[str] = Query(None, description="Specific workflow ID to inspect"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
):
    """
    Get the complete Round Table view of a trading cycle.
    
    Aggregates all stages:
    1. Strategy Engine - tickers scanned, signals generated
    2. Mazo Research - sentiment analysis, key sources
    3. AI Agents - all 18 agent signals with reasoning
    4. Portfolio Manager - final decision with rationale
    5. Execution - order status and fill details
    6. Post-Trade - monitoring and P&L
    
    Returns the latest workflow by default, or a specific workflow_id if provided.
    """
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        response = RoundTableResponse()
        
        with engine.connect() as conn:
            # 1. Get the workflow to inspect
            if workflow_id:
                wf_query = """
                    SELECT DISTINCT workflow_id, workflow_type, ticker, 
                           MIN(timestamp) as started_at,
                           MAX(timestamp) as completed_at,
                           MAX(CASE WHEN step_name = 'trading_cycle_complete' THEN 'completed'
                                    WHEN step_name = 'trading_cycle_error' THEN 'failed'
                                    ELSE NULL END) as final_status
                    FROM workflow_events
                    WHERE workflow_id = :workflow_id
                    GROUP BY workflow_id, workflow_type, ticker
                """
                result = conn.execute(text(wf_query), {"workflow_id": workflow_id})
            else:
                # Get latest workflow
                wf_query = """
                    SELECT DISTINCT ON (workflow_id) 
                           workflow_id, workflow_type, ticker,
                           MIN(timestamp) OVER (PARTITION BY workflow_id) as started_at,
                           MAX(timestamp) OVER (PARTITION BY workflow_id) as completed_at,
                           status as final_status
                    FROM workflow_events
                    WHERE workflow_type = 'automated_trading'
                    ORDER BY workflow_id, timestamp DESC
                    LIMIT 1
                """
                if ticker:
                    wf_query = """
                        SELECT DISTINCT ON (workflow_id)
                               workflow_id, workflow_type, ticker,
                               MIN(timestamp) OVER (PARTITION BY workflow_id) as started_at,
                               MAX(timestamp) OVER (PARTITION BY workflow_id) as completed_at,
                               status as final_status
                        FROM workflow_events
                        WHERE workflow_type = 'automated_trading' AND ticker = :ticker
                        ORDER BY workflow_id, timestamp DESC
                        LIMIT 1
                    """
                    result = conn.execute(text(wf_query), {"ticker": ticker})
                else:
                    result = conn.execute(text(wf_query))
            
            wf_row = result.fetchone()
            if not wf_row:
                response.status = "no_data"
                response.errors.append("No workflow data found")
                return response
            
            wf_id = str(wf_row[0])
            response.workflow_id = wf_id
            response.workflow_type = wf_row[1]
            response.ticker = wf_row[2]
            response.started_at = wf_row[3].isoformat() if wf_row[3] else None
            response.completed_at = wf_row[4].isoformat() if wf_row[4] else None
            response.status = wf_row[5] or "running"
            
            if response.started_at and response.completed_at:
                start = datetime.fromisoformat(response.started_at.replace('Z', '+00:00'))
                end = datetime.fromisoformat(response.completed_at.replace('Z', '+00:00'))
                response.total_duration_ms = int((end - start).total_seconds() * 1000)
            
            # 2. Get Strategy Stage from workflow events
            strategy_query = """
                SELECT step_name, status, payload, duration_ms, timestamp
                FROM workflow_events
                WHERE workflow_id = :workflow_id
                  AND step_name IN ('strategy_screening', 'trading_cycle_start')
                ORDER BY timestamp ASC
            """
            result = conn.execute(text(strategy_query), {"workflow_id": wf_id})
            for row in result.fetchall():
                if row[2]:  # payload
                    payload = row[2] if isinstance(row[2], dict) else {}
                    response.strategy.tickers_scanned = payload.get("ticker_count", 0)
                    response.strategy.signals_found = payload.get("signals_found", 0)
                    response.strategy.signals = payload.get("signals", [])
                response.strategy.duration_ms = row[3]
                response.strategy.timestamp = row[4].isoformat() if row[4] else None
            
            # 3. Get Mazo Research Stage
            mazo_query = """
                SELECT ticker, query, response, sentiment, sentiment_confidence,
                       key_points, sources_count, sources, success, latency_ms, timestamp
                FROM mazo_research
                WHERE workflow_id = :workflow_id
                ORDER BY timestamp DESC
                LIMIT 1
            """
            result = conn.execute(text(mazo_query), {"workflow_id": wf_id})
            mazo_row = result.fetchone()
            if mazo_row:
                response.mazo = MazoStage(
                    ticker=mazo_row[0],
                    query=mazo_row[1],
                    summary=mazo_row[2][:500] if mazo_row[2] else None,  # Truncate
                    sentiment=mazo_row[3],
                    sentiment_confidence=mazo_row[4],
                    key_points=mazo_row[5] if mazo_row[5] else [],
                    sources_count=mazo_row[6] or 0,
                    sources=mazo_row[7] if mazo_row[7] else [],
                    success=mazo_row[8] or False,
                    duration_ms=mazo_row[9],
                    timestamp=mazo_row[10].isoformat() if mazo_row[10] else None,
                )
            
            # 4. Get Agent Signals Stage
            agents_query = """
                SELECT agent_id, agent_type, signal, confidence, reasoning,
                       key_metrics, latency_ms, was_correct, timestamp
                FROM agent_signals
                WHERE workflow_id = :workflow_id
                ORDER BY agent_id
            """
            result = conn.execute(text(agents_query), {"workflow_id": wf_id})
            
            agents_list = []
            bullish = bearish = neutral = 0
            total_latency = 0
            first_ts = None
            
            for row in result.fetchall():
                agent_id = row[0]
                signal = row[2].lower() if row[2] else "neutral"
                
                if signal == "bullish":
                    bullish += 1
                elif signal == "bearish":
                    bearish += 1
                else:
                    neutral += 1
                
                accuracy = _get_agent_accuracy(agent_id, conn)
                
                agents_list.append(AgentSignalData(
                    agent_id=agent_id,
                    agent_type=row[1] or _get_agent_type(agent_id),
                    signal=signal,
                    confidence=row[3],
                    reasoning=row[4][:300] if row[4] else None,  # Truncate
                    key_metrics=row[5],
                    latency_ms=row[6],
                    was_correct=row[7],
                    accuracy_rate=accuracy,
                ))
                
                if row[6]:
                    total_latency += row[6]
                if not first_ts and row[8]:
                    first_ts = row[8]
            
            total_agents = bullish + bearish + neutral
            if total_agents > 0:
                # Calculate consensus
                max_direction = max(bullish, bearish, neutral)
                if max_direction == bullish:
                    consensus = "bullish"
                elif max_direction == bearish:
                    consensus = "bearish"
                else:
                    consensus = "neutral"
                
                agreement_pct = (max_direction / total_agents) * 100
                
                response.agents = AgentsStage(
                    ticker=response.ticker,
                    agents=agents_list,
                    bullish_count=bullish,
                    bearish_count=bearish,
                    neutral_count=neutral,
                    consensus=consensus,
                    consensus_score=agreement_pct,
                    agreement_pct=agreement_pct,
                    timestamp=first_ts.isoformat() if first_ts else None,
                    total_duration_ms=total_latency,
                )
                
                # Build consensus meter
                response.consensus = ConsensusMeter(
                    total_agents=total_agents,
                    bullish_pct=(bullish / total_agents) * 100,
                    bearish_pct=(bearish / total_agents) * 100,
                    neutral_pct=(neutral / total_agents) * 100,
                    agreement_pct=agreement_pct,
                    conviction_met=agreement_pct >= 65,
                    conviction_threshold=65,
                    recommendation=consensus if agreement_pct >= 65 else "hold",
                )
            
            # 5. Get Portfolio Manager Decision
            pm_query = """
                SELECT ticker, action, quantity, stop_loss_pct, take_profit_pct,
                       position_size_pct, reasoning_raw, confidence,
                       portfolio_equity, portfolio_cash, existing_position_qty,
                       action_matches_consensus, override_reason,
                       agents_considered, agents_ignored, latency_ms, timestamp
                FROM pm_decisions
                WHERE workflow_id = :workflow_id
                ORDER BY timestamp DESC
                LIMIT 1
            """
            result = conn.execute(text(pm_query), {"workflow_id": wf_id})
            pm_row = result.fetchone()
            if pm_row:
                response.portfolio_manager = PortfolioManagerStage(
                    ticker=pm_row[0],
                    action=pm_row[1],
                    quantity=pm_row[2],
                    stop_loss_pct=pm_row[3],
                    take_profit_pct=pm_row[4],
                    position_size_pct=pm_row[5],
                    reasoning=pm_row[6][:500] if pm_row[6] else None,  # Truncate
                    confidence=pm_row[7],
                    portfolio_equity=pm_row[8],
                    portfolio_cash=pm_row[9],
                    existing_position=pm_row[10],
                    action_matches_consensus=pm_row[11],
                    override_reason=pm_row[12],
                    agents_considered=pm_row[13],
                    agents_ignored=pm_row[14],
                    duration_ms=pm_row[15],
                    timestamp=pm_row[16].isoformat() if pm_row[16] else None,
                )
            
            # 6. Get Execution Stage
            exec_query = """
                SELECT order_id, ticker, side, order_type, quantity,
                       limit_price, status, filled_qty, filled_avg_price,
                       slippage_bps, submitted_at, filled_at, fill_latency_ms,
                       reject_reason
                FROM trade_executions
                WHERE workflow_id = :workflow_id
                ORDER BY timestamp DESC
                LIMIT 1
            """
            result = conn.execute(text(exec_query), {"workflow_id": wf_id})
            exec_row = result.fetchone()
            if exec_row:
                response.execution = ExecutionStage(
                    order_id=exec_row[0],
                    ticker=exec_row[1],
                    side=exec_row[2],
                    order_type=exec_row[3],
                    quantity=exec_row[4],
                    limit_price=exec_row[5],
                    status=exec_row[6],
                    filled_qty=exec_row[7],
                    filled_avg_price=exec_row[8],
                    slippage_bps=exec_row[9],
                    submitted_at=exec_row[10].isoformat() if exec_row[10] else None,
                    filled_at=exec_row[11].isoformat() if exec_row[11] else None,
                    fill_latency_ms=exec_row[12],
                    error=exec_row[13],
                )
            
            # 7. Get Post-Trade Status from trade_history
            post_query = """
                SELECT th.id, th.ticker, th.status, th.entry_price, th.exit_price,
                       th.stop_loss_price, th.take_profit_price,
                       th.realized_pnl, th.return_pct
                FROM trade_history th
                JOIN trade_decision_context tdc ON th.id = tdc.trade_id
                WHERE tdc.workflow_id = :workflow_id
                ORDER BY th.created_at DESC
                LIMIT 1
            """
            try:
                result = conn.execute(text(post_query), {"workflow_id": wf_id})
                post_row = result.fetchone()
                if post_row:
                    response.post_trade = PostTradeStage(
                        trade_id=post_row[0],
                        ticker=post_row[1],
                        status=post_row[2],
                        stop_loss_price=post_row[5],
                        take_profit_price=post_row[6],
                        exit_price=post_row[4],
                        realized_pnl=post_row[7],
                        return_pct=post_row[8],
                        sync_status="synced" if post_row[2] else "pending",
                    )
            except Exception as e:
                logger.debug(f"Post-trade query failed: {e}")
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get round table: {e}")
        raise HTTPException(500, str(e))


@router.get("/round-table/history")
async def get_round_table_history(
    limit: int = Query(10, ge=1, le=50, description="Number of workflows to return"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
):
    """
    Get a list of recent workflows for the Round Table dropdown.
    """
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        with engine.connect() as conn:
            query = """
                SELECT 
                    workflow_id,
                    MAX(ticker) as ticker,
                    MIN(timestamp) as started_at,
                    MAX(timestamp) as completed_at,
                    MAX(CASE WHEN step_name = 'trading_cycle_complete' THEN 'completed'
                             WHEN step_name = 'trading_cycle_error' THEN 'failed'
                             ELSE 'running' END) as status
                FROM workflow_events
                WHERE workflow_type = 'automated_trading'
            """
            
            if ticker:
                query += " AND ticker = :ticker"
            
            query += """
                GROUP BY workflow_id
                ORDER BY MIN(timestamp) DESC
                LIMIT :limit
            """
            
            params = {"limit": limit}
            if ticker:
                params["ticker"] = ticker
            
            result = conn.execute(text(query), params)
            
            workflows = []
            for row in result.fetchall():
                workflows.append({
                    "workflow_id": str(row[0]),
                    "ticker": row[1],
                    "started_at": row[2].isoformat() if row[2] else None,
                    "completed_at": row[3].isoformat() if row[3] else None,
                    "status": row[4],
                })
            
            return {
                "success": True,
                "workflows": workflows,
                "count": len(workflows),
            }
            
    except Exception as e:
        logger.error(f"Failed to get round table history: {e}")
        raise HTTPException(500, str(e))
