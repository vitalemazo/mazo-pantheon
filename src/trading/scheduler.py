"""
Trading Scheduler

APScheduler-based job runner for automated intraday trading activities.
Manages scheduled tasks like health checks, scans, and trade execution.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.jobstores.memory import MemoryJobStore
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    AsyncIOScheduler = None

from src.trading.alpaca_service import AlpacaService

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of scheduled tasks"""
    HEALTH_CHECK = "health_check"
    DIVERSIFICATION_SCAN = "diversification_scan"
    MOMENTUM_SCAN = "momentum_scan"
    MEAN_REVERSION_SCAN = "mean_reversion_scan"
    PORTFOLIO_ANALYSIS = "portfolio_analysis"
    TRADE_EXECUTION = "trade_execution"
    DAILY_REPORT = "daily_report"
    STOP_LOSS_CHECK = "stop_loss_check"
    WATCHLIST_MONITOR = "watchlist_monitor"
    AUTOMATED_TRADING = "automated_trading"  # Full AI pipeline


@dataclass
class ScheduledTaskResult:
    """Result of a scheduled task execution"""
    task_id: str
    task_type: TaskType
    success: bool
    execution_time_ms: float
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class TradingScheduler:
    """
    Manages scheduled trading activities throughout the trading day.
    
    Default Schedule (Eastern Time):
    - 6:30 AM: Pre-market prep (news, health check)
    - 9:30 AM: Market open tasks
    - 10:00 AM: Morning momentum scan
    - 12:00 PM: Midday review
    - 2:00 PM: Afternoon setup
    - 3:30 PM: Pre-close actions
    - 4:00 PM: Market close report
    """
    
    # Trading hours (Eastern Time)
    MARKET_OPEN = "09:30"
    MARKET_CLOSE = "16:00"
    
    def __init__(self):
        if not HAS_APSCHEDULER:
            logger.warning("APScheduler not installed. Scheduler will not function.")
            self.scheduler = None
            return
            
        self.scheduler = AsyncIOScheduler(
            jobstores={
                'default': MemoryJobStore()
            },
            job_defaults={
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 300  # 5 minutes
            },
            timezone='America/New_York'
        )
        
        self.alpaca = AlpacaService()
        self.is_running = False
        self.task_history: List[ScheduledTaskResult] = []
        self._task_handlers: Dict[TaskType, Callable] = {}
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default task handlers."""
        self._task_handlers = {
            TaskType.HEALTH_CHECK: self._run_health_check,
            TaskType.DIVERSIFICATION_SCAN: self._run_diversification_scan,
            TaskType.MOMENTUM_SCAN: self._run_momentum_scan,
            TaskType.STOP_LOSS_CHECK: self._run_stop_loss_check,
            TaskType.DAILY_REPORT: self._run_daily_report,
            TaskType.WATCHLIST_MONITOR: self._run_watchlist_monitor,
            TaskType.AUTOMATED_TRADING: self._run_automated_trading,
        }
    
    def start(self) -> bool:
        """Start the scheduler."""
        if not self.scheduler:
            logger.error("Scheduler not available (APScheduler not installed)")
            return False
            
        if self.is_running:
            logger.warning("Scheduler already running")
            return True
            
        try:
            self.scheduler.start()
            self.is_running = True
            logger.info("Trading scheduler started")
            return True
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop the scheduler."""
        if not self.scheduler or not self.is_running:
            return True
            
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Trading scheduler stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
            return False
    
    def add_default_schedule(self) -> Dict[str, str]:
        """Add the default trading day schedule."""
        if not self.scheduler:
            return {"error": "Scheduler not available"}
            
        jobs_added = {}
        
        # Pre-market prep (6:30 AM ET)
        job_id = self.add_cron_task(
            task_type=TaskType.HEALTH_CHECK,
            name="Pre-Market Health Check",
            hour=6, minute=30,
            parameters={"depth": "quick"}
        )
        jobs_added["pre_market"] = job_id
        
        # Market open momentum scan (9:35 AM ET - 5 min after open)
        job_id = self.add_cron_task(
            task_type=TaskType.MOMENTUM_SCAN,
            name="Market Open Momentum",
            hour=9, minute=35,
            parameters={"scan_type": "opening_momentum"}
        )
        jobs_added["market_open"] = job_id
        
        # Morning scan (10:00 AM ET)
        job_id = self.add_cron_task(
            task_type=TaskType.DIVERSIFICATION_SCAN,
            name="Morning Diversification Scan",
            hour=10, minute=0,
            parameters={"max_price": 50}
        )
        jobs_added["morning_scan"] = job_id
        
        # Midday stop-loss check (12:00 PM ET)
        job_id = self.add_cron_task(
            task_type=TaskType.STOP_LOSS_CHECK,
            name="Midday Stop-Loss Review",
            hour=12, minute=0,
            parameters={}
        )
        jobs_added["midday_check"] = job_id
        
        # Afternoon health check (2:00 PM ET)
        job_id = self.add_cron_task(
            task_type=TaskType.HEALTH_CHECK,
            name="Afternoon Health Check",
            hour=14, minute=0,
            parameters={"depth": "standard"}
        )
        jobs_added["afternoon_check"] = job_id
        
        # Pre-close watchlist monitor (3:30 PM ET)
        job_id = self.add_cron_task(
            task_type=TaskType.WATCHLIST_MONITOR,
            name="Pre-Close Watchlist",
            hour=15, minute=30,
            parameters={"close_day_trades": True}
        )
        jobs_added["pre_close"] = job_id
        
        # Market close report (4:05 PM ET)
        job_id = self.add_cron_task(
            task_type=TaskType.DAILY_REPORT,
            name="Daily Performance Report",
            hour=16, minute=5,
            parameters={}
        )
        jobs_added["daily_report"] = job_id
        
        # Frequent stop-loss monitoring (every 15 minutes during market hours)
        job_id = self.add_interval_task(
            task_type=TaskType.STOP_LOSS_CHECK,
            name="Stop-Loss Monitor",
            minutes=15,
            parameters={"during_market_hours": True}
        )
        jobs_added["stop_loss_monitor"] = job_id
        
        # AI-powered automated trading (every 30 minutes during market hours)
        job_id = self.add_interval_task(
            task_type=TaskType.AUTOMATED_TRADING,
            name="AI Trading Cycle",
            minutes=30,
            parameters={
                "during_market_hours": True,
                "min_confidence": 65,
                "max_signals": 3,
                "execute_trades": True
            }
        )
        jobs_added["ai_trading"] = job_id
        
        logger.info(f"Added {len(jobs_added)} default scheduled tasks")
        return jobs_added
    
    def add_cron_task(
        self,
        task_type: TaskType,
        name: str,
        hour: int,
        minute: int,
        day_of_week: str = "mon-fri",
        parameters: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Add a cron-scheduled task.
        
        Args:
            task_type: Type of task to run
            name: Human-readable name
            hour: Hour (0-23) in Eastern Time
            minute: Minute (0-59)
            day_of_week: Days to run (default: weekdays)
            parameters: Task-specific parameters
            
        Returns:
            Job ID or None if failed
        """
        if not self.scheduler:
            return None
            
        try:
            job = self.scheduler.add_job(
                self._execute_task,
                trigger=CronTrigger(
                    hour=hour,
                    minute=minute,
                    day_of_week=day_of_week,
                    timezone='America/New_York'
                ),
                args=[task_type, name, parameters or {}],
                id=f"{task_type.value}_{hour:02d}{minute:02d}",
                name=name,
                replace_existing=True
            )
            logger.info(f"Added cron task: {name} at {hour:02d}:{minute:02d} ET")
            return job.id
        except Exception as e:
            logger.error(f"Failed to add cron task {name}: {e}")
            return None
    
    def add_interval_task(
        self,
        task_type: TaskType,
        name: str,
        minutes: int = 15,
        parameters: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Add an interval-scheduled task.
        
        Args:
            task_type: Type of task to run
            name: Human-readable name
            minutes: Interval in minutes
            parameters: Task-specific parameters
            
        Returns:
            Job ID or None if failed
        """
        if not self.scheduler:
            return None
            
        try:
            job = self.scheduler.add_job(
                self._execute_task,
                trigger=IntervalTrigger(minutes=minutes),
                args=[task_type, name, parameters or {}],
                id=f"{task_type.value}_interval_{minutes}m",
                name=name,
                replace_existing=True
            )
            logger.info(f"Added interval task: {name} every {minutes} minutes")
            return job.id
        except Exception as e:
            logger.error(f"Failed to add interval task {name}: {e}")
            return None
    
    def add_one_time_task(
        self,
        task_type: TaskType,
        name: str,
        run_at: datetime,
        parameters: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Add a one-time scheduled task.
        
        Args:
            task_type: Type of task to run
            name: Human-readable name
            run_at: When to run the task
            parameters: Task-specific parameters
            
        Returns:
            Job ID or None if failed
        """
        if not self.scheduler:
            return None
            
        try:
            job = self.scheduler.add_job(
                self._execute_task,
                trigger=DateTrigger(run_date=run_at),
                args=[task_type, name, parameters or {}],
                id=f"{task_type.value}_once_{run_at.strftime('%Y%m%d%H%M')}",
                name=name,
                replace_existing=True
            )
            logger.info(f"Added one-time task: {name} at {run_at}")
            return job.id
        except Exception as e:
            logger.error(f"Failed to add one-time task {name}: {e}")
            return None
    
    def remove_task(self, job_id: str) -> bool:
        """Remove a scheduled task by ID."""
        if not self.scheduler:
            return False
            
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed task: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove task {job_id}: {e}")
            return False
    
    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks."""
        if not self.scheduler:
            return []
            
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs
    
    def get_task_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent task execution history."""
        history = sorted(
            self.task_history,
            key=lambda x: x.timestamp,
            reverse=True
        )[:limit]
        
        return [
            {
                "task_id": h.task_id,
                "task_type": h.task_type.value,
                "success": h.success,
                "execution_time_ms": h.execution_time_ms,
                "timestamp": h.timestamp.isoformat(),
                "error": h.error,
            }
            for h in history
        ]
    
    async def _execute_task(
        self,
        task_type: TaskType,
        name: str,
        parameters: Dict[str, Any]
    ):
        """Execute a scheduled task."""
        start_time = datetime.now()
        logger.info(f"Executing task: {name} ({task_type.value})")
        
        # Check if market is open for market-hours-only tasks
        if parameters.get("during_market_hours", False):
            if not self._is_market_hours():
                logger.info(f"Skipping {name} - outside market hours")
                return
        
        try:
            handler = self._task_handlers.get(task_type)
            if not handler:
                raise ValueError(f"No handler for task type: {task_type}")
                
            result = await handler(parameters)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            task_result = ScheduledTaskResult(
                task_id=f"{task_type.value}_{start_time.strftime('%Y%m%d%H%M%S')}",
                task_type=task_type,
                success=True,
                execution_time_ms=execution_time,
                result=result
            )
            
            logger.info(f"Task {name} completed in {execution_time:.0f}ms")
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            task_result = ScheduledTaskResult(
                task_id=f"{task_type.value}_{start_time.strftime('%Y%m%d%H%M%S')}",
                task_type=task_type,
                success=False,
                execution_time_ms=execution_time,
                error=str(e)
            )
            
            logger.error(f"Task {name} failed: {e}")
        
        # Keep last 100 results in memory
        self.task_history.append(task_result)
        if len(self.task_history) > 100:
            self.task_history = self.task_history[-100:]
    
    def _is_market_hours(self) -> bool:
        """Check if current time is during market hours."""
        from datetime import timezone
        import pytz
        
        try:
            et = pytz.timezone('America/New_York')
            now = datetime.now(et)
            
            # Check if weekday
            if now.weekday() >= 5:  # Saturday or Sunday
                return False
                
            # Check time
            market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
            
            return market_open <= now <= market_close
            
        except Exception:
            # Default to True if can't determine
            return True
    
    # ==================== Task Handlers ====================
    
    async def _run_health_check(self, params: Dict) -> Dict:
        """Run portfolio health check."""
        from integration.mazo_bridge import MazoBridge
        from src.graph.portfolio_context import build_portfolio_context
        
        try:
            # Get portfolio context
            portfolio = build_portfolio_context()
            
            # Get tickers from positions
            tickers = [p.symbol for p in portfolio.positions] if portfolio.positions else []
            
            if not tickers:
                return {"status": "no_positions", "message": "No positions to analyze"}
            
            # Run health check via Mazo
            mazo = MazoBridge()
            result = mazo.portfolio_health_check(
                portfolio.to_llm_summary(),
                tickers
            )
            
            return {
                "status": "completed",
                "tickers": tickers,
                "equity": portfolio.total_equity,
                "positions_count": len(portfolio.positions),
                "analysis_length": len(result.answer) if result.answer else 0,
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _run_diversification_scan(self, params: Dict) -> Dict:
        """Run diversification scan for new opportunities."""
        from src.trading.diversification_scanner import DiversificationScanner, ScanCriteria
        
        try:
            scanner = DiversificationScanner()
            criteria = ScanCriteria(
                max_price=params.get("max_price", 50.0),
                min_volume=params.get("min_volume", 500_000),
            )
            
            candidates = scanner.scan_for_opportunities(criteria, limit=10)
            
            return {
                "status": "completed",
                "candidates_found": len(candidates),
                "top_candidates": [
                    {"ticker": c.ticker, "sector": c.sector, "score": c.score}
                    for c in candidates[:5]
                ]
            }
            
        except Exception as e:
            logger.error(f"Diversification scan failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _run_momentum_scan(self, params: Dict) -> Dict:
        """Run momentum scan for high-momentum stocks."""
        # Placeholder - will integrate with strategy engine
        return {
            "status": "completed",
            "scan_type": params.get("scan_type", "standard"),
            "message": "Momentum scan placeholder - integrate with strategy engine"
        }
    
    async def _run_stop_loss_check(self, params: Dict) -> Dict:
        """Check all positions against stop-loss levels."""
        try:
            positions = self.alpaca.get_positions()
            
            if not positions:
                return {"status": "no_positions"}
            
            alerts = []
            for pos in positions:
                current_price = float(pos.current_price)
                entry_price = float(pos.avg_entry_price)
                qty = float(pos.qty)
                
                # Calculate loss percentage
                if qty > 0:  # Long position
                    loss_pct = (entry_price - current_price) / entry_price * 100
                else:  # Short position
                    loss_pct = (current_price - entry_price) / entry_price * 100
                
                # Alert if loss > 5%
                if loss_pct > 5:
                    alerts.append({
                        "ticker": pos.symbol,
                        "loss_pct": round(loss_pct, 2),
                        "current_price": current_price,
                        "entry_price": entry_price,
                    })
            
            return {
                "status": "completed",
                "positions_checked": len(positions),
                "alerts": alerts,
                "alerts_count": len(alerts),
            }
            
        except Exception as e:
            logger.error(f"Stop-loss check failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _run_watchlist_monitor(self, params: Dict) -> Dict:
        """Monitor watchlist for triggered entries."""
        # Placeholder - will integrate with watchlist service
        return {
            "status": "completed",
            "message": "Watchlist monitor placeholder - integrate with watchlist service"
        }
    
    async def _run_daily_report(self, params: Dict) -> Dict:
        """Generate daily performance report."""
        try:
            account = self.alpaca.get_account()
            positions = self.alpaca.get_positions()
            
            if not account:
                return {"status": "error", "error": "Could not fetch account"}
            
            total_pnl = sum(float(p.unrealized_pl) for p in positions) if positions else 0
            
            return {
                "status": "completed",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "equity": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "positions_count": len(positions) if positions else 0,
                "total_unrealized_pnl": round(total_pnl, 2),
            }
            
        except Exception as e:
            logger.error(f"Daily report failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _run_automated_trading(self, params: Dict) -> Dict:
        """
        Run full AI-powered automated trading cycle.
        
        Pipeline:
        1. Strategy Engine screens for technical signals
        2. Mazo validates promising signals
        3. AI Analysts provide deep analysis
        4. Portfolio Manager makes final decision
        5. Trades execute on Alpaca
        """
        from src.trading.automated_trading import get_automated_trading_service
        
        try:
            service = get_automated_trading_service()
            
            result = await service.run_trading_cycle(
                tickers=params.get("tickers"),
                min_confidence=params.get("min_confidence", 65),
                max_signals=params.get("max_signals", 3),
                execute_trades_flag=params.get("execute_trades", True),
                dry_run=params.get("dry_run", False),
            )
            
            return {
                "status": "completed",
                "tickers_screened": result.tickers_screened,
                "signals_found": result.signals_found,
                "mazo_validated": result.mazo_validated,
                "trades_analyzed": result.trades_analyzed,
                "trades_executed": result.trades_executed,
                "execution_time_ms": result.total_execution_time_ms,
                "results": result.results[:5],  # Top 5 results
                "errors": result.errors,
            }
            
        except Exception as e:
            logger.error(f"Automated trading failed: {e}")
            return {"status": "error", "error": str(e)}


# Global scheduler instance
_scheduler: Optional[TradingScheduler] = None


def get_scheduler() -> TradingScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = TradingScheduler()
    return _scheduler
