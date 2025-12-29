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
