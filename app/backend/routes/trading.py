"""
Trading API Routes

Comprehensive API for day trading features:
- Scheduler management
- Strategy execution
- Watchlist management
- Performance tracking
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.trading.scheduler import get_scheduler, TaskType
from src.trading.strategy_engine import get_strategy_engine
from src.trading.watchlist_service import get_watchlist_service
from src.trading.performance_tracker import get_performance_tracker
from src.trading.automated_trading import get_automated_trading_service
from src.trading.position_monitor import get_position_monitor


router = APIRouter(prefix="/trading", tags=["trading"])


# ==================== Request/Response Models ====================

class SchedulerStatusResponse(BaseModel):
    is_running: bool
    scheduled_tasks: List[dict]
    recent_history: List[dict]


class AddTaskRequest(BaseModel):
    task_type: str
    name: str
    hour: Optional[int] = None
    minute: Optional[int] = None
    interval_minutes: Optional[int] = None
    parameters: Optional[dict] = None


class WatchlistAddRequest(BaseModel):
    ticker: str
    entry_target: Optional[float] = None
    entry_condition: str = "below"
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size_pct: float = 0.05
    strategy: Optional[str] = None
    priority: int = 5
    notes: Optional[str] = None
    expires_in_days: int = 30


class WatchlistUpdateRequest(BaseModel):
    entry_target: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    priority: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class AnalyzeRequest(BaseModel):
    tickers: List[str]
    strategies: Optional[List[str]] = None
    min_confidence: float = 60


class RecordTradeRequest(BaseModel):
    ticker: str
    action: str
    quantity: float
    price: float
    strategy: Optional[str] = None


class CloseTradeRequest(BaseModel):
    trade_id: int
    exit_price: float


class AutomatedTradingRequest(BaseModel):
    tickers: Optional[List[str]] = None
    min_confidence: float = 65
    max_signals: int = 3
    execute_trades: bool = True
    dry_run: bool = False


# ==================== Scheduler Endpoints ====================

@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """Get scheduler status and scheduled tasks."""
    scheduler = get_scheduler()
    
    return SchedulerStatusResponse(
        is_running=scheduler.is_running,
        scheduled_tasks=scheduler.get_scheduled_tasks(),
        recent_history=scheduler.get_task_history(limit=20),
    )


@router.post("/scheduler/start")
async def start_scheduler():
    """Start the trading scheduler."""
    scheduler = get_scheduler()
    success = scheduler.start()
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start scheduler")
    
    return {"success": True, "message": "Scheduler started"}


@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the trading scheduler."""
    scheduler = get_scheduler()
    success = scheduler.stop()
    
    return {"success": success, "message": "Scheduler stopped" if success else "Failed to stop"}


@router.post("/scheduler/add-default-schedule")
async def add_default_schedule():
    """Add the default trading day schedule."""
    scheduler = get_scheduler()
    
    if not scheduler.is_running:
        scheduler.start()
    
    jobs = scheduler.add_default_schedule()
    
    return {
        "success": True,
        "jobs_added": jobs,
        "message": f"Added {len(jobs)} scheduled tasks"
    }


@router.post("/scheduler/add-task")
async def add_scheduled_task(request: AddTaskRequest):
    """Add a custom scheduled task."""
    scheduler = get_scheduler()
    
    try:
        task_type = TaskType(request.task_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task type. Valid types: {[t.value for t in TaskType]}"
        )
    
    if request.interval_minutes:
        job_id = scheduler.add_interval_task(
            task_type=task_type,
            name=request.name,
            minutes=request.interval_minutes,
            parameters=request.parameters,
        )
    elif request.hour is not None and request.minute is not None:
        job_id = scheduler.add_cron_task(
            task_type=task_type,
            name=request.name,
            hour=request.hour,
            minute=request.minute,
            parameters=request.parameters,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either interval_minutes or both hour and minute"
        )
    
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to add task")
    
    return {"success": True, "job_id": job_id}


@router.delete("/scheduler/task/{job_id}")
async def remove_scheduled_task(job_id: str):
    """Remove a scheduled task."""
    scheduler = get_scheduler()
    success = scheduler.remove_task(job_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"success": True, "message": f"Removed task {job_id}"}


# ==================== Strategy Endpoints ====================

@router.get("/strategies")
async def list_strategies():
    """List available trading strategies."""
    engine = get_strategy_engine()
    return {
        "strategies": engine.get_available_strategies()
    }


@router.post("/strategies/analyze")
async def analyze_tickers(request: AnalyzeRequest):
    """Analyze tickers with trading strategies."""
    engine = get_strategy_engine()
    
    results = engine.scan_universe(
        tickers=request.tickers,
        strategies=request.strategies,
        min_confidence=request.min_confidence,
    )
    
    # Convert signals to dicts
    signals_by_ticker = {}
    for ticker, signals in results.items():
        signals_by_ticker[ticker] = [s.to_dict() for s in signals]
    
    return {
        "success": True,
        "tickers_analyzed": len(request.tickers),
        "tickers_with_signals": len(results),
        "signals": signals_by_ticker,
    }


@router.get("/strategies/best-signals")
async def get_best_signals(
    tickers: str = "AAPL,MSFT,GOOGL,AMZN,TSLA",
    top_n: int = 5
):
    """Get the best trading signals across tickers."""
    engine = get_strategy_engine()
    
    ticker_list = [t.strip().upper() for t in tickers.split(",")]
    signals = engine.get_best_signals(ticker_list, top_n=top_n)
    
    return {
        "success": True,
        "signals": [s.to_dict() for s in signals],
    }


@router.get("/strategies/{strategy_name}/analyze/{ticker}")
async def analyze_single_ticker(strategy_name: str, ticker: str):
    """Analyze a single ticker with a specific strategy."""
    engine = get_strategy_engine()
    strategy = engine.get_strategy(strategy_name)
    
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")
    
    signal = strategy.analyze(ticker.upper())
    
    return {
        "success": True,
        "ticker": ticker.upper(),
        "strategy": strategy_name,
        "signal": signal.to_dict() if signal else None,
    }


# ==================== Watchlist Endpoints ====================

@router.get("/watchlist")
async def get_watchlist(status: Optional[str] = None, sort_by: str = "priority"):
    """Get the trading watchlist."""
    service = get_watchlist_service()
    items = service.get_watchlist(status=status, sort_by=sort_by)
    
    return {
        "success": True,
        "items": [i.to_dict() for i in items],
        "summary": service.get_summary(),
    }


@router.post("/watchlist")
async def add_to_watchlist(request: WatchlistAddRequest):
    """Add an item to the watchlist."""
    service = get_watchlist_service()
    
    item = service.add_item(
        ticker=request.ticker,
        entry_target=request.entry_target,
        entry_condition=request.entry_condition,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        position_size_pct=request.position_size_pct,
        strategy=request.strategy,
        priority=request.priority,
        notes=request.notes,
        expires_in_days=request.expires_in_days,
    )
    
    if item is None:
        raise HTTPException(status_code=500, detail="Failed to add item to watchlist")
    
    return {
        "success": True,
        "item": item.to_dict(),
    }


@router.get("/watchlist/{item_id}")
async def get_watchlist_item(item_id: int):
    """Get a specific watchlist item."""
    service = get_watchlist_service()
    item = service.get_item(item_id)
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return {
        "success": True,
        "item": item.to_dict(),
    }


@router.patch("/watchlist/{item_id}")
async def update_watchlist_item(item_id: int, request: WatchlistUpdateRequest):
    """Update a watchlist item."""
    service = get_watchlist_service()
    
    item = service.update_item(
        item_id=item_id,
        entry_target=request.entry_target,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        priority=request.priority,
        notes=request.notes,
        status=request.status,
    )
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return {
        "success": True,
        "item": item.to_dict(),
    }


@router.delete("/watchlist/{item_id}")
async def remove_from_watchlist(item_id: int):
    """Remove an item from the watchlist."""
    service = get_watchlist_service()
    success = service.remove_item(item_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return {"success": True, "message": f"Removed item {item_id}"}


@router.post("/watchlist/auto-enrich")
async def auto_enrich_watchlist(
    min_ai_score: int = 6,
    stocks_per_sector: int = 5,
    max_total: int = 15,
):
    """
    Auto-populate watchlist with high-scoring Danelfin picks.
    
    Uses Danelfin AI scoring to find top-rated stocks and adds them
    to the watchlist with appropriate entry targets and stop losses.
    """
    service = get_watchlist_service()
    result = service.auto_enrich_from_danelfin(
        min_ai_score=min_ai_score,
        stocks_per_sector=stocks_per_sector,
        max_total=max_total,
    )
    
    return {
        "success": True,
        "added": result.get("added", 0),
        "added_tickers": result.get("added_tickers", []),
        "skipped": result.get("skipped", 0),
        "error": result.get("error"),
    }


@router.post("/watchlist/check-triggers")
async def check_watchlist_triggers():
    """Check all watchlist items for triggered conditions."""
    service = get_watchlist_service()
    triggered = service.check_triggers()
    
    return {
        "success": True,
        "triggered_count": len(triggered),
        "triggered_items": [i.to_dict() for i in triggered],
    }


@router.get("/watchlist/analyze")
async def analyze_watchlist():
    """Run strategy analysis on all watchlist items."""
    service = get_watchlist_service()
    results = service.analyze_watchlist()
    
    return {
        "success": True,
        "analysis": results,
    }


# ==================== Performance Endpoints ====================

@router.get("/performance")
async def get_current_performance():
    """Get current portfolio performance."""
    tracker = get_performance_tracker()
    return tracker.get_current_performance()


@router.get("/performance/metrics")
async def get_performance_metrics():
    """Get overall trading metrics."""
    tracker = get_performance_tracker()
    return {
        "success": True,
        "metrics": tracker.get_metrics(),
    }


@router.get("/performance/by-strategy")
async def get_performance_by_strategy():
    """Get performance metrics by strategy."""
    tracker = get_performance_tracker()
    return {
        "success": True,
        "by_strategy": tracker.get_metrics_by_strategy(),
    }


@router.get("/performance/summary")
async def get_performance_summary():
    """Get comprehensive performance summary."""
    tracker = get_performance_tracker()
    return tracker.get_summary_report()


@router.get("/performance/trades")
async def get_trade_history(
    limit: int = 50,
    status: Optional[str] = None,
    ticker: Optional[str] = None
):
    """Get trade history."""
    tracker = get_performance_tracker()
    trades = tracker.get_trade_history(limit=limit, status=status, ticker=ticker)
    
    return {
        "success": True,
        "trades": [t.to_dict() for t in trades],
    }


@router.post("/performance/trades")
async def record_trade(request: RecordTradeRequest):
    """Record a new trade."""
    tracker = get_performance_tracker()
    
    trade = tracker.record_trade(
        ticker=request.ticker,
        action=request.action,
        quantity=request.quantity,
        price=request.price,
        strategy=request.strategy,
    )
    
    return {
        "success": True,
        "trade": trade.to_dict(),
    }


@router.post("/performance/trades/close")
async def close_trade(request: CloseTradeRequest):
    """Close a trade and calculate P&L."""
    tracker = get_performance_tracker()
    
    trade = tracker.close_trade(
        trade_id=request.trade_id,
        exit_price=request.exit_price,
    )
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found or already closed")
    
    return {
        "success": True,
        "trade": trade.to_dict(),
    }


@router.post("/performance/snapshot")
async def create_daily_snapshot():
    """Create a daily performance snapshot."""
    tracker = get_performance_tracker()
    
    try:
        snapshot = tracker.create_daily_snapshot()
        return {
            "success": True,
            "snapshot": snapshot.to_dict(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/snapshots")
async def get_daily_snapshots(days: int = 30):
    """Get daily performance snapshots."""
    tracker = get_performance_tracker()
    snapshots = tracker.get_daily_snapshots(days=days)
    
    return {
        "success": True,
        "snapshots": [s.to_dict() for s in snapshots],
    }


# ==================== Automated Trading Endpoints ====================

def _check_alpaca_credentials() -> tuple[bool, dict]:
    """
    Check if Alpaca credentials are configured.
    
    Returns:
        (is_configured, error_response) - If not configured, error_response has details.
    """
    import os
    
    api_key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "").strip()
    
    if not api_key or not secret_key:
        return False, {
            "success": False,
            "error": "Alpaca credentials not configured",
            "message": "Autonomous trading requires Alpaca API credentials. Please set ALPACA_API_KEY and ALPACA_SECRET_KEY in Settings > API Keys.",
            "requires_setup": {
                "alpaca": True,
                "missing_keys": [
                    k for k, v in [("ALPACA_API_KEY", api_key), ("ALPACA_SECRET_KEY", secret_key)]
                    if not v
                ],
            },
        }
    
    return True, {}


def _get_safe_trading_service():
    """
    Safely get the automated trading service, returning (service, error_response).
    
    If service creation fails, returns (None, error_dict).
    """
    try:
        service = get_automated_trading_service()
        # Verify the service has valid Alpaca connection
        if not service.alpaca or not service.alpaca.api_key:
            return None, {
                "success": False,
                "error": "Alpaca service not properly initialized",
                "message": "The trading service could not connect to Alpaca. Please verify your API credentials in Settings > API Keys.",
                "requires_setup": {"alpaca": True},
            }
        return service, None
    except Exception as e:
        logger.error(f"Failed to create automated trading service: {e}")
        return None, {
            "success": False,
            "error": f"Trading service initialization failed: {str(e)[:200]}",
            "message": "Could not initialize the trading service. Please check your Alpaca credentials and try again.",
            "requires_setup": {"alpaca": True},
        }


@router.get("/automated/status")
async def get_automated_trading_status():
    """Get automated trading service status including latest cycle metrics."""
    # First check if credentials are configured
    is_configured, error_response = _check_alpaca_credentials()
    if not is_configured:
        return {
            **error_response,
            "auto_trading_enabled": False,
            "is_running": False,
            "last_run": None,
            "total_runs": 0,
            "latest_cycle": None,
        }
    
    # Try to get the service
    service, error = _get_safe_trading_service()
    if error:
        return {
            **error,
            "auto_trading_enabled": False,
            "is_running": False,
            "last_run": None,
            "total_runs": 0,
            "latest_cycle": None,
        }
    
    status = service.get_status()
    
    # Try to get latest cycle metrics from database (service.last_result is in-memory only)
    latest_cycle = None
    last_run = None
    total_runs = 0
    
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        with engine.connect() as conn:
            # Get the latest completed trading cycle from workflow_events
            query = """
                SELECT 
                    workflow_id,
                    MIN(timestamp) as started_at,
                    MAX(timestamp) as completed_at,
                    MAX(CASE WHEN payload IS NOT NULL AND payload::text LIKE '%"tickers_screened"%' 
                             THEN (payload->>'tickers_screened')::int ELSE 0 END) as tickers_screened,
                    MAX(CASE WHEN payload IS NOT NULL AND payload::text LIKE '%"signals_found"%' 
                             THEN (payload->>'signals_found')::int ELSE 0 END) as signals_found,
                    MAX(CASE WHEN payload IS NOT NULL AND payload::text LIKE '%"mazo_validated"%' 
                             THEN (payload->>'mazo_validated')::int ELSE 0 END) as mazo_validated,
                    MAX(CASE WHEN payload IS NOT NULL AND payload::text LIKE '%"trades_executed"%'
                             THEN (payload->>'trades_executed')::int ELSE 0 END) as trades_executed
                FROM workflow_events
                WHERE workflow_type = 'automated_trading'
                  AND step_name = 'trading_cycle_complete'
                GROUP BY workflow_id
                ORDER BY MAX(timestamp) DESC
                LIMIT 1
            """
            result = conn.execute(text(query))
            row = result.fetchone()
            
            if row:
                started = row[1]
                completed = row[2]
                duration_ms = None
                if started and completed:
                    duration_ms = int((completed - started).total_seconds() * 1000)
                
                latest_cycle = {
                    "workflow_id": str(row[0]),
                    "tickers_screened": row[3] or 0,
                    "signals_found": row[4] or 0,
                    "mazo_validated": row[5] or 0,
                    "trades_analyzed": 0,  # Not tracked in workflow_events payload
                    "trades_executed": row[6] or 0,
                    "total_execution_time_ms": duration_ms or 0,
                    "timestamp": completed.isoformat() if completed else None,
                }
                last_run = completed.isoformat() if completed else None
            
            # Count total runs
            count_query = """
                SELECT COUNT(DISTINCT workflow_id) 
                FROM workflow_events 
                WHERE workflow_type = 'automated_trading'
                  AND step_name = 'trading_cycle_complete'
            """
            count_result = conn.execute(text(count_query))
            total_runs = count_result.scalar() or 0
            
    except Exception as e:
        logger.warning(f"Failed to fetch latest cycle from DB: {e}")
        # Fall back to in-memory last_result if available
        if service.last_result:
            latest_cycle = {
                "tickers_screened": service.last_result.tickers_screened,
                "signals_found": service.last_result.signals_found,
                "mazo_validated": service.last_result.mazo_validated,
                "trades_analyzed": service.last_result.trades_analyzed,
                "trades_executed": service.last_result.trades_executed,
                "total_execution_time_ms": service.last_result.total_execution_time_ms,
                "timestamp": service.last_result.timestamp.isoformat() if service.last_result.timestamp else None,
            }
    
    return {
        "success": True,
        **status,
        "last_run": last_run or status.get("last_run"),
        "total_runs": total_runs or status.get("total_runs", 0),
        "latest_cycle": latest_cycle,
    }


@router.get("/small-account-mode")
async def get_small_account_mode_status():
    """
    Get Small Account Mode status and effective trading parameters.
    
    Returns current equity, whether mode is active, and all effective
    parameters that will be used in the next trading cycle.
    """
    from src.trading.config import (
        get_small_account_config, 
        get_effective_trading_params,
        is_small_account_mode_active,
        get_dynamic_risk_params,
        RISK_PRESETS,
    )
    from src.trading.strategy_engine import get_strategy_engine, STRATEGY_METADATA
    
    # Get account equity
    current_equity = 0.0
    try:
        is_configured, _ = _check_alpaca_credentials()
        if is_configured:
            from src.trading.alpaca_service import AlpacaService
            alpaca = AlpacaService()
            account = alpaca.get_account()
            if account:
                current_equity = float(account.equity)
    except Exception as e:
        logger.warning(f"Could not fetch equity for small account mode check: {e}")
    
    # Get config and effective params
    config = get_small_account_config()
    effective_params = get_effective_trading_params(current_equity)
    is_active = is_small_account_mode_active(current_equity)
    
    # Get strategy info
    engine = get_strategy_engine()
    enabled_strategies = list(engine.strategies.keys())
    
    # If small account mode is active, show which strategies would be enabled
    small_account_strategies = []
    if is_active and config.enabled_strategies:
        small_account_strategies = config.enabled_strategies
    
    return {
        "success": True,
        "small_account_mode": {
            "enabled_in_config": config.enabled,
            "active": is_active,
            "equity_threshold": config.equity_threshold,
            "current_equity": current_equity,
            "below_threshold": current_equity <= config.equity_threshold if current_equity > 0 else None,
        },
        "effective_params": effective_params,
        "strategies": {
            "currently_enabled": enabled_strategies,
            "small_account_enabled": small_account_strategies,
            "available": list(STRATEGY_METADATA.keys()),
        },
        "config_details": {
            "target_notional_per_trade": config.target_notional_per_trade,
            "max_signals": config.max_signals,
            "min_confidence": config.min_confidence,
            "max_positions": config.max_positions,
            "max_position_pct": config.max_position_pct,
            "min_buying_power_pct": config.min_buying_power_pct,
            "trade_cooldown_minutes": config.trade_cooldown_minutes,
            "max_ticker_price": config.max_ticker_price,
            "include_etfs": config.include_etfs,
            "enable_scalping_strategies": config.enable_scalping_strategies,
        },
        "dynamic_risk": {
            # Example: what risk params would be for a $30 micro-trade
            "example_micro_trade": get_dynamic_risk_params(
                notional_value=30.0, 
                atr_pct=0.025,  # Assume 2.5% ATR
                equity=current_equity
            ),
            # Example: what risk params would be for a $100 trade
            "example_medium_trade": get_dynamic_risk_params(
                notional_value=100.0,
                atr_pct=0.02,
                equity=current_equity
            ),
            # Example: what risk params would be for a $300 trade
            "example_large_trade": get_dynamic_risk_params(
                notional_value=300.0,
                atr_pct=0.015,
                equity=current_equity
            ),
            "small_account_risk_config": {
                "use_atr_stops": config.use_atr_stops,
                "atr_stop_multiplier": config.atr_stop_multiplier,
                "atr_take_profit_multiplier": config.atr_take_profit_multiplier,
                "stop_loss_pct_small": config.stop_loss_pct_small,
                "stop_loss_pct_medium": config.stop_loss_pct_medium,
                "stop_loss_pct_large": config.stop_loss_pct_large,
                "take_profit_pct_small": config.take_profit_pct_small,
                "take_profit_pct_medium": config.take_profit_pct_medium,
                "take_profit_pct_large": config.take_profit_pct_large,
            },
        },
        "risk_presets": RISK_PRESETS,
    }


@router.post("/automated/run")
async def run_automated_trading_cycle(request: AutomatedTradingRequest):
    """
    Manually trigger an automated trading cycle.
    
    This runs the full AI pipeline:
    1. Strategy Engine screens for signals
    2. Mazo validates promising signals  
    3. AI Analysts provide deep analysis
    4. Portfolio Manager makes final decision
    5. Trades execute on Alpaca
    """
    # Check credentials first
    is_configured, error_response = _check_alpaca_credentials()
    if not is_configured:
        raise HTTPException(
            status_code=400,
            detail=error_response.get("message", "Alpaca credentials not configured")
        )
    
    service, error = _get_safe_trading_service()
    if error:
        raise HTTPException(
            status_code=400,
            detail=error.get("message", "Trading service unavailable")
        )
    
    if service.is_running:
        raise HTTPException(
            status_code=409, 
            detail="A trading cycle is already running"
        )
    
    # Run the cycle
    result = await service.run_trading_cycle(
        tickers=request.tickers,
        min_confidence=request.min_confidence,
        max_signals=request.max_signals,
        execute_trades_flag=request.execute_trades,
        dry_run=request.dry_run,
    )
    
    return {
        "success": True,
        "result": result.to_dict(),
    }


@router.get("/automated/history")
async def get_automated_trading_history(limit: int = 10):
    """Get automated trading run history from database."""
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        with engine.connect() as conn:
            # Query workflow_events for trading cycles
            # Use BOOL_OR to properly detect completion status (MAX on strings is alphabetical)
            query = """
                SELECT 
                    workflow_id,
                    MIN(timestamp) as started_at,
                    MAX(timestamp) as completed_at,
                    CASE 
                        WHEN BOOL_OR(step_name = 'trading_cycle_complete') THEN 'completed'
                        WHEN BOOL_OR(step_name = 'trading_cycle_error') THEN 'failed'
                        WHEN BOOL_OR(step_name LIKE '%dry%') THEN 'dry_run'
                        ELSE 'running' 
                    END as status,
                    MAX(CASE WHEN payload IS NOT NULL AND payload::text LIKE '%"signals_found"%' 
                             THEN (payload->>'signals_found')::int ELSE 0 END) as signals_found,
                    MAX(CASE WHEN payload IS NOT NULL AND payload::text LIKE '%"trades_executed"%'
                             THEN (payload->>'trades_executed')::int ELSE 0 END) as trades_executed,
                    COUNT(DISTINCT ticker) as tickers_analyzed
                FROM workflow_events
                WHERE workflow_type = 'automated_trading'
                GROUP BY workflow_id
                ORDER BY MIN(timestamp) DESC
                LIMIT :limit
            """
            result = conn.execute(text(query), {"limit": limit})
            
            history = []
            for row in result.fetchall():
                started = row[1]
                completed = row[2]
                duration_ms = None
                if started and completed:
                    duration_ms = int((completed - started).total_seconds() * 1000)
                
                history.append({
                    "workflow_id": str(row[0]),
                    "timestamp": started.isoformat() if started else None,
                    "completed_at": completed.isoformat() if completed else None,
                    "status": row[3],
                    "signals_found": row[4] or 0,
                    "trades_executed": row[5] or 0,
                    "tickers_analyzed": row[6] or 0,
                    "duration_ms": duration_ms,
                })
            
            return {
                "success": True,
                "history": history,
                "count": len(history),
            }
    except Exception as e:
        trade_sync_logger.error(f"Failed to get cycle history: {e}")
        # Fall back to in-memory history
        is_configured, error_response = _check_alpaca_credentials()
        if not is_configured:
            return {"success": False, "history": [], **error_response}
        
        service, error = _get_safe_trading_service()
        if error:
            return {"success": False, "history": [], **error}
        
        return {
            "success": True,
            "history": service.get_history(limit=limit),
        }


@router.post("/automated/dry-run")
async def run_automated_trading_dry_run(request: AutomatedTradingRequest):
    """
    Run automated trading in dry-run mode (no actual trades).
    
    Useful for testing the pipeline without executing.
    """
    # Check credentials first
    is_configured, error_response = _check_alpaca_credentials()
    if not is_configured:
        raise HTTPException(
            status_code=400,
            detail=error_response.get("message", "Alpaca credentials not configured")
        )
    
    service, error = _get_safe_trading_service()
    if error:
        raise HTTPException(
            status_code=400,
            detail=error.get("message", "Trading service unavailable")
        )
    
    if service.is_running:
        raise HTTPException(
            status_code=409,
            detail="A trading cycle is already running"
        )
    
    # Force dry run
    result = await service.run_trading_cycle(
        tickers=request.tickers,
        min_confidence=request.min_confidence,
        max_signals=request.max_signals,
        execute_trades_flag=True,
        dry_run=True,  # Force dry run
    )
    
    return {
        "success": True,
        "dry_run": True,
        "result": result.to_dict(),
    }


# ==================== Position Monitor Endpoints ====================

@router.get("/position-monitor/status")
async def get_position_monitor_status():
    """Get position monitor status and recent activity."""
    try:
        monitor = get_position_monitor()
        status = monitor.get_status()
        
        return {
            "success": True,
            "is_running": status.get("is_running", False),
            "last_check": status.get("last_check"),
            "check_count": status.get("check_count", 0),
            "exits_executed": status.get("exits_executed", 0),
            "recent_alerts": status.get("recent_alerts", []),
            "position_rules": status.get("position_rules", {}),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/position-monitor/set-rules")
async def set_position_rules(
    ticker: str,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
):
    """Set custom risk rules for a specific position."""
    try:
        monitor = get_position_monitor()
        monitor.set_position_rules(ticker.upper(), stop_loss_pct, take_profit_pct)
        
        return {
            "success": True,
            "ticker": ticker.upper(),
            "rules": {
                "stop_loss_pct": stop_loss_pct,
                "take_profit_pct": take_profit_pct,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== Trade Status Sync ====================

import logging
trade_sync_logger = logging.getLogger(__name__)


@router.post("/trades/sync")
async def sync_trade_statuses():
    """
    Sync trade statuses from Alpaca.
    
    Updates pending trades in the database with current status from Alpaca.
    """
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        from src.trading.alpaca_service import get_alpaca_service
        
        alpaca = get_alpaca_service()
        if not alpaca:
            return {"success": False, "error": "Alpaca service not configured"}
        
        # Get pending orders from database
        with engine.connect() as conn:
            pending_query = """
                SELECT order_id, ticker, side, quantity, status
                FROM trade_executions
                WHERE status IN ('pending_new', 'new', 'accepted', 'pending_cancel', 'partially_filled')
                  AND submitted_at > NOW() - INTERVAL '7 days'
            """
            result = conn.execute(text(pending_query))
            pending_trades = result.fetchall()
        
        updated = 0
        errors = []
        
        for trade in pending_trades:
            order_id = trade[0]
            try:
                # Get current status from Alpaca
                order = alpaca.get_order(order_id)
                
                if order:
                    # Update in database
                    with engine.connect() as conn:
                        update_query = """
                            UPDATE trade_executions
                            SET status = :status,
                                filled_qty = :filled_qty,
                                filled_avg_price = :filled_avg_price,
                                filled_at = :filled_at
                            WHERE order_id = :order_id
                        """
                        conn.execute(text(update_query), {
                            "order_id": order_id,
                            "status": order.status,
                            "filled_qty": order.filled_qty if order.filled_qty else None,
                            "filled_avg_price": order.filled_avg_price if order.filled_avg_price else None,
                            "filled_at": order.filled_at if order.filled_at else None,
                        })
                        conn.commit()
                    
                    if order.status in ('filled', 'canceled', 'expired', 'rejected'):
                        updated += 1
                        trade_sync_logger.info(f"Updated trade {order_id}: {order.status}")
                        
            except Exception as e:
                error_msg = f"Failed to sync {order_id}: {str(e)[:100]}"
                errors.append(error_msg)
                trade_sync_logger.warning(error_msg)
        
        return {
            "success": True,
            "pending_trades": len(pending_trades),
            "updated": updated,
            "errors": errors[:5] if errors else [],
        }
        
    except Exception as e:
        trade_sync_logger.error(f"Trade sync failed: {e}")
        return {"success": False, "error": str(e)}
