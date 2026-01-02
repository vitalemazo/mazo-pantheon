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

class GuardRailCheck(BaseModel):
    """Individual guard rail check result"""
    name: str
    status: str  # pass, fail, skip
    value: Optional[Any] = None
    threshold: Optional[Any] = None
    message: Optional[str] = None


class UniverseRiskStage(BaseModel):
    """Stage 1: Universe construction and risk preparation"""
    # Universe
    universe_size: int = 0
    universe_tickers: List[str] = []
    watchlist_count: int = 0
    watchlist_tickers: List[str] = []
    
    # Account status
    portfolio_value: Optional[float] = None
    buying_power: Optional[float] = None
    cash_available: Optional[float] = None
    day_trades_remaining: Optional[int] = None
    pdt_status: Optional[str] = None  # clear, warning, restricted
    
    # Guard rails
    auto_trading_enabled: bool = False
    market_hours: bool = False
    
    # Risk checks
    guard_rails: List[GuardRailCheck] = []
    concentration_check: Optional[str] = None  # pass, fail
    cooldown_tickers: List[str] = []
    blocked_tickers: List[str] = []
    
    timestamp: Optional[str] = None
    status: str = "pending"  # pending, pass, fail


class StrategyStage(BaseModel):
    """Stage 2: Strategy Engine screening results"""
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


class AgentAccuracyUpdate(BaseModel):
    """Agent accuracy change from this trade"""
    agent_id: str
    signal_was_correct: Optional[bool] = None
    previous_accuracy: Optional[float] = None
    new_accuracy: Optional[float] = None


class FeedbackLoopStage(BaseModel):
    """Stage 8: Feedback loop - trade results and accuracy updates"""
    # Trade outcome
    trade_recorded: bool = False
    trade_id: Optional[int] = None
    order_id: Optional[str] = None
    
    # P&L
    realized_pnl: Optional[float] = None
    return_pct: Optional[float] = None
    was_profitable: Optional[bool] = None
    
    # Agent accuracy adjustments
    agents_updated: int = 0
    accuracy_updates: List[AgentAccuracyUpdate] = []
    
    # System updates
    cooldown_set: bool = False
    cooldown_until: Optional[str] = None
    position_added: bool = False
    
    # Performance tracking
    session_pnl: Optional[float] = None
    session_trades: int = 0
    session_win_rate: Optional[float] = None
    
    timestamp: Optional[str] = None
    status: str = "pending"  # pending, updated, skipped


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
    """Complete Round Table transparency view - 8 stages"""
    workflow_id: Optional[str] = None
    workflow_type: Optional[str] = None
    ticker: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_duration_ms: Optional[int] = None
    status: str = "unknown"  # running, completed, failed, dry_run
    
    # All 8 Pipeline stages
    universe_risk: UniverseRiskStage = UniverseRiskStage()  # Stage 1
    strategy: StrategyStage = StrategyStage()               # Stage 2
    mazo: MazoStage = MazoStage()                           # Stage 3
    agents: AgentsStage = AgentsStage()                     # Stage 4
    portfolio_manager: PortfolioManagerStage = PortfolioManagerStage()  # Stage 5
    execution: ExecutionStage = ExecutionStage()            # Stage 6
    post_trade: PostTradeStage = PostTradeStage()           # Stage 7
    feedback_loop: FeedbackLoopStage = FeedbackLoopStage()  # Stage 8
    
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
                # Get latest workflow - order by MAX timestamp
                wf_query = """
                    SELECT 
                        workflow_id, workflow_type, 
                        MAX(ticker) as ticker,
                        MIN(timestamp) as started_at,
                        MAX(timestamp) as completed_at,
                        MAX(CASE WHEN step_name = 'trading_cycle_complete' THEN 'completed'
                                 WHEN step_name = 'trading_cycle_error' THEN 'failed'
                                 ELSE 'running' END) as final_status
                    FROM workflow_events
                    WHERE workflow_type = 'automated_trading'
                    GROUP BY workflow_id, workflow_type
                    ORDER BY MAX(timestamp) DESC
                    LIMIT 1
                """
                if ticker:
                    wf_query = """
                        SELECT 
                            workflow_id, workflow_type,
                            MAX(ticker) as ticker,
                            MIN(timestamp) as started_at,
                            MAX(timestamp) as completed_at,
                            MAX(CASE WHEN step_name = 'trading_cycle_complete' THEN 'completed'
                                     WHEN step_name = 'trading_cycle_error' THEN 'failed'
                                     ELSE 'running' END) as final_status
                        FROM workflow_events
                        WHERE workflow_type = 'automated_trading' AND ticker = :ticker
                        GROUP BY workflow_id, workflow_type
                        ORDER BY MAX(timestamp) DESC
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
            
            # =================================================================
            # STAGE 1: Universe & Risk Preparation
            # =================================================================
            universe_query = """
                SELECT step_name, status, payload, timestamp
                FROM workflow_events
                WHERE workflow_id = :workflow_id
                  AND step_name IN ('trading_cycle_start', 'capital_rotation', 'risk_check')
                ORDER BY timestamp ASC
            """
            result = conn.execute(text(universe_query), {"workflow_id": wf_id})
            
            guard_rails = []
            for row in result.fetchall():
                payload = row[2] if isinstance(row[2], dict) else {}
                
                if row[0] == 'trading_cycle_start':
                    response.universe_risk.timestamp = row[3].isoformat() if row[3] else None
                    response.universe_risk.auto_trading_enabled = payload.get("auto_trading_enabled", False)
                    response.universe_risk.market_hours = payload.get("market_hours", False)
                    
                    # Parse tickers
                    tickers = payload.get("tickers", [])
                    if isinstance(tickers, list):
                        response.universe_risk.universe_tickers = tickers[:20]  # Limit
                        response.universe_risk.universe_size = len(tickers)
                
                if row[0] == 'capital_rotation':
                    response.universe_risk.portfolio_value = payload.get("portfolio_value")
                    response.universe_risk.buying_power = payload.get("buying_power")
                    response.universe_risk.cash_available = payload.get("cash_available")
                    response.universe_risk.day_trades_remaining = payload.get("day_trades_remaining")
                    
                    # PDT check
                    if response.universe_risk.day_trades_remaining is not None:
                        if response.universe_risk.day_trades_remaining <= 0:
                            response.universe_risk.pdt_status = "restricted"
                        elif response.universe_risk.day_trades_remaining <= 1:
                            response.universe_risk.pdt_status = "warning"
                        else:
                            response.universe_risk.pdt_status = "clear"
                    
                    # Cooldown tickers
                    response.universe_risk.cooldown_tickers = payload.get("cooldown_tickers", [])
                    response.universe_risk.blocked_tickers = payload.get("blocked_tickers", [])
                    response.universe_risk.concentration_check = payload.get("concentration_check", "pass")
            
            # Add guard rail checks
            guard_rails.append(GuardRailCheck(
                name="AUTO_TRADING_ENABLED",
                status="pass" if response.universe_risk.auto_trading_enabled else "fail",
                value=response.universe_risk.auto_trading_enabled,
                message="Automated trading is enabled" if response.universe_risk.auto_trading_enabled else "Auto-trading disabled"
            ))
            guard_rails.append(GuardRailCheck(
                name="Market Hours",
                status="pass" if response.universe_risk.market_hours else "skip",
                value=response.universe_risk.market_hours,
                message="Market is open" if response.universe_risk.market_hours else "Outside market hours"
            ))
            if response.universe_risk.pdt_status:
                guard_rails.append(GuardRailCheck(
                    name="PDT Status",
                    status="pass" if response.universe_risk.pdt_status == "clear" else ("fail" if response.universe_risk.pdt_status == "restricted" else "skip"),
                    value=response.universe_risk.day_trades_remaining,
                    threshold=3,
                    message=f"{response.universe_risk.day_trades_remaining} day trades remaining"
                ))
            if response.universe_risk.cooldown_tickers:
                guard_rails.append(GuardRailCheck(
                    name="Cooldown Check",
                    status="skip",
                    value=response.universe_risk.cooldown_tickers,
                    message=f"{len(response.universe_risk.cooldown_tickers)} tickers on cooldown"
                ))
            
            response.universe_risk.guard_rails = guard_rails
            response.universe_risk.status = "pass" if response.universe_risk.auto_trading_enabled else "fail"
            
            # =================================================================
            # STAGE 2: Strategy Engine
            # =================================================================
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
            
            # 7. Get Post-Trade Status from trade_history (join via order_id from execution)
            post_query = """
                SELECT th.id, th.ticker, th.status, th.entry_price, th.exit_price,
                       th.stop_loss_price, th.take_profit_price,
                       th.realized_pnl, th.return_pct
                FROM trade_history th
                WHERE th.order_id = :order_id
                ORDER BY th.created_at DESC
                LIMIT 1
            """
            try:
                # Get order_id from execution stage
                exec_order_id = response.execution.order_id
                if exec_order_id:
                    result = conn.execute(text(post_query), {"order_id": exec_order_id})
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
            
            # =================================================================
            # STAGE 8: Feedback Loop
            # =================================================================
            try:
                # Get trade outcome from trade_history (via order_id from execution)
                if exec_order_id:
                    feedback_query = """
                        SELECT
                            th.id, th.order_id, th.realized_pnl, th.return_pct,
                            th.status
                        FROM trade_history th
                        WHERE th.order_id = :order_id
                        ORDER BY th.created_at DESC
                        LIMIT 1
                    """
                    result = conn.execute(text(feedback_query), {"order_id": exec_order_id})
                    fb_row = result.fetchone()
                else:
                    fb_row = None
                
                if fb_row:
                    response.feedback_loop.trade_recorded = True
                    response.feedback_loop.trade_id = fb_row[0]
                    response.feedback_loop.order_id = fb_row[1]
                    response.feedback_loop.realized_pnl = fb_row[2]
                    response.feedback_loop.return_pct = fb_row[3]
                    # Calculate was_profitable from realized_pnl
                    response.feedback_loop.was_profitable = (fb_row[2] or 0) > 0 if fb_row[2] is not None else None
                    response.feedback_loop.status = "updated" if fb_row[4] == "closed" else "pending"
                    
                    # Get agent accuracy updates for this trade
                    accuracy_query = """
                        SELECT agent_id, was_correct
                        FROM agent_signals
                        WHERE workflow_id = :workflow_id AND was_correct IS NOT NULL
                    """
                    result = conn.execute(text(accuracy_query), {"workflow_id": wf_id})
                    accuracy_updates = []
                    for row in result.fetchall():
                        accuracy_updates.append(AgentAccuracyUpdate(
                            agent_id=row[0],
                            signal_was_correct=row[1],
                        ))
                    response.feedback_loop.accuracy_updates = accuracy_updates
                    response.feedback_loop.agents_updated = len(accuracy_updates)
                    
                    # Cooldown tracking
                    if response.feedback_loop.trade_recorded:
                        response.feedback_loop.cooldown_set = True
                        response.feedback_loop.position_added = True
                else:
                    response.feedback_loop.status = "skipped"
                
                # Get session performance
                session_query = """
                    SELECT 
                        COUNT(*) as trade_count,
                        SUM(realized_pnl) as total_pnl,
                        AVG(CASE WHEN realized_pnl > 0 THEN 1.0 ELSE 0.0 END) as win_rate
                    FROM trade_history
                    WHERE DATE(created_at) = CURRENT_DATE
                      AND status = 'closed'
                """
                result = conn.execute(text(session_query))
                session_row = result.fetchone()
                if session_row:
                    response.feedback_loop.session_trades = session_row[0] or 0
                    response.feedback_loop.session_pnl = session_row[1]
                    response.feedback_loop.session_win_rate = session_row[2]
                    
                response.feedback_loop.timestamp = response.completed_at
                
            except Exception as e:
                logger.debug(f"Feedback loop query failed: {e}")
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get round table: {e}")
        raise HTTPException(500, str(e))


@router.post("/round-table/test-populate")
async def populate_test_data():
    """
    Populate test data for Round Table demonstration.
    Creates a complete workflow with all 8 stages for testing the UI.
    """
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        import uuid
        import json
        from datetime import datetime, timedelta, timezone
        
        workflow_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        ticker = "AAPL"
        
        with engine.connect() as conn:
            # 1. Workflow Events - Start
            conn.execute(text("""
                INSERT INTO workflow_events (timestamp, id, workflow_id, workflow_type, step_name, status, ticker, payload)
                VALUES (:ts, :id, :wf_id, 'automated_trading', 'trading_cycle_start', 'started', :ticker, :payload)
            """), {
                "ts": now - timedelta(minutes=5),
                "id": uuid.uuid4(),
                "wf_id": workflow_id,
                "ticker": ticker,
                "payload": json.dumps({"auto_trading_enabled": True, "market_hours": True, "tickers": ["AAPL", "GOOGL", "MSFT"]})
            })
            
            # Capital rotation
            conn.execute(text("""
                INSERT INTO workflow_events (timestamp, id, workflow_id, workflow_type, step_name, status, ticker, payload)
                VALUES (:ts, :id, :wf_id, 'automated_trading', 'capital_rotation', 'completed', :ticker, :payload)
            """), {
                "ts": now - timedelta(minutes=4, seconds=30),
                "id": uuid.uuid4(),
                "wf_id": workflow_id,
                "ticker": ticker,
                "payload": json.dumps({"portfolio_value": 100000, "buying_power": 45000, "day_trades_remaining": 3})
            })
            
            # Strategy screening
            conn.execute(text("""
                INSERT INTO workflow_events (timestamp, id, workflow_id, workflow_type, step_name, status, ticker, payload)
                VALUES (:ts, :id, :wf_id, 'automated_trading', 'strategy_screening', 'completed', :ticker, :payload)
            """), {
                "ts": now - timedelta(minutes=4),
                "id": uuid.uuid4(),
                "wf_id": workflow_id,
                "ticker": ticker,
                "payload": json.dumps({"ticker_count": 10, "signals_found": 3, "signals": [{"ticker": "AAPL", "signal": "bullish"}]})
            })
            
            # Complete event
            conn.execute(text("""
                INSERT INTO workflow_events (timestamp, id, workflow_id, workflow_type, step_name, status, ticker, payload)
                VALUES (:ts, :id, :wf_id, 'automated_trading', 'trading_cycle_complete', 'completed', :ticker, :payload)
            """), {
                "ts": now,
                "id": uuid.uuid4(),
                "wf_id": workflow_id,
                "ticker": ticker,
                "payload": json.dumps({"total_duration_ms": 300000})
            })
            
            # 2. Agent Signals
            agents = [
                ("warren_buffett", "value", "bullish", 78),
                ("charlie_munger", "value", "bullish", 82),
                ("ben_graham", "value", "neutral", 55),
                ("peter_lynch", "growth", "bullish", 85),
                ("cathie_wood", "growth", "bullish", 90),
                ("michael_burry", "contrarian", "bearish", 65),
                ("bill_ackman", "activist", "bullish", 72),
                ("stanley_druckenmiller", "macro", "bullish", 68),
                ("fundamentals_analyst", "fundamental", "bullish", 75),
                ("technicals_analyst", "technical", "bullish", 80),
                ("sentiment_analyst", "sentiment", "bullish", 70),
                ("valuation_analyst", "valuation", "neutral", 50),
            ]
            
            for agent_id, agent_type, signal, confidence in agents:
                conn.execute(text("""
                    INSERT INTO agent_signals (timestamp, id, workflow_id, agent_id, agent_type, ticker, signal, confidence, reasoning)
                    VALUES (:ts, :id, :wf_id, :agent_id, :agent_type, :ticker, :signal, :confidence, :reasoning)
                """), {
                    "ts": now - timedelta(minutes=2),
                    "id": uuid.uuid4(),
                    "wf_id": workflow_id,
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "ticker": ticker,
                    "signal": signal,
                    "confidence": confidence,
                    "reasoning": f"{agent_id.replace('_', ' ').title()} analysis indicates {signal} outlook based on key metrics."
                })
            
            # 3. PM Decision
            conn.execute(text("""
                INSERT INTO pm_decisions (timestamp, id, workflow_id, ticker, action, quantity, stop_loss_pct, take_profit_pct,
                                         reasoning_raw, confidence, portfolio_equity, portfolio_cash, consensus_direction, consensus_score,
                                         bullish_count, bearish_count, neutral_count)
                VALUES (:ts, :id, :wf_id, :ticker, 'buy', 50, 5.0, 15.0, :reasoning, 75, 100000, 45000, 'bullish', 75, 9, 1, 2)
            """), {
                "ts": now - timedelta(minutes=1),
                "id": uuid.uuid4(),
                "wf_id": workflow_id,
                "ticker": ticker,
                "reasoning": "Strong bullish consensus from value and growth analysts. Cathie Wood and Peter Lynch highly confident. Risk-adjusted position size with 5% stop loss."
            })
            
            # 4. Mazo Research
            conn.execute(text("""
                INSERT INTO mazo_research (timestamp, id, workflow_id, ticker, query, mode, response, sentiment, 
                                          sentiment_confidence, key_points, sources, success)
                VALUES (:ts, :id, :wf_id, :ticker, :query, 'deep', :response, 'bullish', 75, :key_points, :sources, true)
            """), {
                "ts": now - timedelta(minutes=3),
                "id": uuid.uuid4(),
                "wf_id": workflow_id,
                "ticker": ticker,
                "query": f"Comprehensive analysis of {ticker} investment opportunity",
                "response": f"Based on thorough analysis of {ticker}, the outlook is positive. Strong fundamentals, growing market share, and favorable industry trends support a bullish stance. The company shows consistent revenue growth and margin expansion.",
                "key_points": json.dumps([
                    "Revenue growth of 15% YoY",
                    "Market leadership in key segments",
                    "Strong balance sheet with low debt",
                    "Expanding into new markets"
                ]),
                "sources": json.dumps([
                    {"title": "Q3 Earnings Report", "type": "SEC Filing"},
                    {"title": "Industry Analysis", "type": "Research Report"},
                    {"title": "Recent News", "type": "News Article"}
                ])
            })
            
            # 5. Trade Execution
            order_id = f"test-order-{uuid.uuid4().hex[:8]}"
            conn.execute(text("""
                INSERT INTO trade_executions (timestamp, id, workflow_id, order_id, ticker, side, order_type, quantity,
                                             status, filled_qty, filled_avg_price, submitted_at, filled_at)
                VALUES (:ts, :id, :wf_id, :order_id, :ticker, 'buy', 'market', 50, 'filled', 50, 185.50, :submitted, :filled)
            """), {
                "ts": now - timedelta(seconds=30),
                "id": uuid.uuid4(),
                "wf_id": workflow_id,
                "order_id": order_id,
                "ticker": ticker,
                "submitted": now - timedelta(seconds=35),
                "filled": now - timedelta(seconds=30)
            })
            
            # 6. Trade History (for Post-Trade Monitoring)
            conn.execute(text("""
                INSERT INTO trade_history (created_at, ticker, action, quantity, entry_price, exit_price, status,
                                          order_id, stop_loss_pct, take_profit_pct, realized_pnl, return_pct,
                                          entry_time, exit_time)
                VALUES (:ts, :ticker, 'buy', 50, 185.50, 192.00, 'closed', :order_id, 5.0, 15.0, 325.00, 3.5,
                        :entry_time, :exit_time)
            """), {
                "ts": now - timedelta(seconds=20),
                "ticker": ticker,
                "order_id": order_id,
                "entry_time": now - timedelta(hours=2),
                "exit_time": now - timedelta(seconds=20)
            })

            conn.commit()

        return {
            "success": True,
            "workflow_id": str(workflow_id),
            "message": f"Created complete test workflow with all 8 stages. View at /transparency/round-table?workflow_id={workflow_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to populate test data: {e}")
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
