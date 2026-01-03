"""
Automated Trading Service

Integrates all components for autonomous AI-powered trading:
1. Strategy Engine - Quick technical screening
2. Mazo - Validates promising signals
3. AI Analysts - Deep analysis on top picks
4. Portfolio Manager - Final decision with full context
5. Alpaca Execution - Automatic trade execution
"""

import os
import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.trading.strategy_engine import get_strategy_engine, TradingSignal, SignalDirection
from src.trading.alpaca_service import AlpacaService
from src.trading.performance_tracker import get_performance_tracker
from src.trading.config import (
    get_signal_config, get_capital_config, get_scanner_config, get_cooldown_config,
    get_small_account_config, get_effective_trading_params, is_small_account_mode_active,
    get_danelfin_config
)
from src.graph.portfolio_context import build_portfolio_context, PortfolioContext
from integration.mazo_bridge import MazoBridge
from integration.unified_workflow import UnifiedWorkflow, execute_trades
from src.trading.trade_history_service import TradeHistoryService, TradeRecord, get_trade_history_service

logger = logging.getLogger(__name__)


# In-memory cooldown tracker (ticker -> last trade timestamp)
_trade_cooldowns: Dict[str, datetime] = {}


class TradeDecision(Enum):
    """Final trade decision"""
    EXECUTE = "execute"
    SKIP = "skip"
    HOLD = "hold"


@dataclass
class ScreeningResult:
    """Result from strategy engine screening"""
    ticker: str
    signal: TradingSignal
    passed_screening: bool
    screening_reason: str


@dataclass
class ValidationResult:
    """Result from Mazo validation"""
    ticker: str
    mazo_agrees: bool
    mazo_sentiment: str  # bullish, bearish, neutral
    mazo_confidence: str  # high, medium, low
    key_points: List[str]
    recommendation: str
    mazo_response: str = None  # Full Mazo response for trade history


@dataclass
class AnalysisResult:
    """Result from full AI analyst pipeline"""
    ticker: str
    analyst_signals: Dict[str, Any]
    consensus_direction: str
    consensus_confidence: float
    pm_decision: Dict[str, Any]
    reasoning: str
    workflow_id: str = None  # Added for PM decision tracking


@dataclass
class AutomatedTradeResult:
    """Complete result of automated trading cycle"""
    timestamp: datetime
    tickers_screened: int
    signals_found: int
    mazo_validated: int
    trades_analyzed: int
    trades_executed: int
    total_execution_time_ms: float
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "tickers_screened": self.tickers_screened,
            "signals_found": self.signals_found,
            "mazo_validated": self.mazo_validated,
            "trades_analyzed": self.trades_analyzed,
            "trades_executed": self.trades_executed,
            "total_execution_time_ms": self.total_execution_time_ms,
            "results": self.results,
            "errors": self.errors,
        }


class AutomatedTradingService:
    """
    Orchestrates the full automated trading pipeline.
    
    Pipeline:
    1. Strategy Engine screens watchlist/universe for signals
    2. Mazo validates top signals with quick research
    3. Full AI analyst pipeline runs on validated tickers
    4. Portfolio Manager makes final decision with context
    5. Trades execute automatically on Alpaca
    """
    
    def __init__(self):
        self.strategy_engine = get_strategy_engine()
        self.alpaca = AlpacaService()
        self.performance_tracker = get_performance_tracker()
        self.mazo = MazoBridge()
        
        # Initialize trade history service with DB session
        try:
            from app.backend.database.connection import SessionLocal
            self._db_session = SessionLocal()
            self.trade_history = get_trade_history_service(self._db_session)
        except Exception as e:
            logger.warning(f"Could not initialize TradeHistoryService: {e}")
            self._db_session = None
            self.trade_history = None
        
        # Track state
        self.is_running = False
        self.last_run: Optional[datetime] = None
        self.last_result: Optional[AutomatedTradeResult] = None
        self.run_history: List[AutomatedTradeResult] = []
        
        # Cooldown config
        self.cooldown_config = get_cooldown_config()
    
    def _check_cooldown(self, ticker: str) -> Tuple[bool, str]:
        """
        Check if a ticker is in cooldown period.
        
        Returns:
            (can_trade, reason) - True if trade allowed, False with reason if blocked
        """
        global _trade_cooldowns
        
        if not self.cooldown_config.cooldown_enabled:
            return True, ""
        
        last_trade_time = _trade_cooldowns.get(ticker)
        if not last_trade_time:
            return True, ""
        
        cooldown_minutes = self.cooldown_config.trade_cooldown_minutes
        elapsed = (datetime.now() - last_trade_time).total_seconds() / 60
        
        if elapsed < cooldown_minutes:
            remaining = int(cooldown_minutes - elapsed)
            reason = f"Cooldown active: traded {int(elapsed)}m ago, {remaining}m remaining"
            return False, reason
        
        return True, ""
    
    def _check_concentration(self, ticker: str, quantity: float, price: float) -> Tuple[bool, str]:
        """
        Check if adding this position would exceed concentration limits.
        
        Args:
            ticker: Stock symbol
            quantity: Number of shares (supports fractional)
            price: Current price per share

        Returns:
            (can_trade, reason) - True if trade allowed, False with reason if blocked
        """
        if not self.cooldown_config.concentration_check_enabled:
            return True, ""
        
        try:
            account = self.alpaca.get_account()
            positions = self.alpaca.get_positions()
            
            if not account:
                return True, ""  # Can't check, allow trade
            
            portfolio_value = float(account.portfolio_value)
            max_pct = self.cooldown_config.max_position_pct_per_ticker
            max_value = portfolio_value * max_pct
            
            # Get current position value in this ticker
            current_value = 0.0
            for pos in (positions or []):
                if pos.symbol.upper() == ticker.upper():
                    current_value = abs(float(pos.market_value))
                    break
            
            # Calculate new total value
            new_trade_value = quantity * price
            total_value = current_value + new_trade_value
            
            if total_value > max_value:
                current_pct = (current_value / portfolio_value) * 100
                new_pct = (total_value / portfolio_value) * 100
                max_pct_display = max_pct * 100
                reason = (
                    f"Concentration limit: {ticker} would be {new_pct:.1f}% of portfolio "
                    f"(current: {current_pct:.1f}%, max: {max_pct_display:.1f}%)"
                )
                return False, reason
            
            return True, ""
            
        except Exception as e:
            logger.warning(f"Concentration check failed: {e}")
            return True, ""  # Allow on error
    
    def _record_cooldown(self, ticker: str):
        """Record that a trade was executed for cooldown tracking."""
        global _trade_cooldowns
        _trade_cooldowns[ticker] = datetime.now()
        logger.debug(f"Recorded cooldown for {ticker}")

    def _check_pdt_limits(self) -> Dict[str, Any]:
        """
        Check Pattern Day Trader limits.
        
        Returns:
            Dict with 'blocked' (bool) and 'reason' (str) if blocked
        """
        import os
        
        # Check if PDT enforcement is enabled
        enforce_pdt = os.getenv("ENFORCE_PDT", "true").lower() == "true"
        if not enforce_pdt:
            return {"blocked": False}
        
        try:
            pdt_status = self.alpaca.check_pdt_status()
            
            if not pdt_status.get("can_day_trade"):
                return {
                    "blocked": True,
                    "reason": pdt_status.get("warning") or "PDT limit reached - day trading restricted",
                    "daytrade_count": pdt_status.get("daytrade_count"),
                    "equity": pdt_status.get("equity"),
                }
            
            # Log warning if approaching limit
            if pdt_status.get("warning"):
                logger.warning(f"⚠️ PDT Warning: {pdt_status['warning']}")
            
            return {"blocked": False, "pdt_status": pdt_status}
            
        except Exception as e:
            logger.warning(f"PDT check failed: {e}")
            return {"blocked": False}  # Don't block on error

    def _check_risk_limits(self) -> Dict[str, Any]:
        """
        Check portfolio-wide risk limits.
        
        Uses small account mode parameters if active.
        
        Returns:
            Dict with violations and status
        """
        from src.trading.config import get_risk_config
        
        risk_config = get_risk_config()
        violations = []
        
        # Get effective params (may override risk config in small account mode)
        effective_params = getattr(self, '_effective_params', {})
        small_account_active = effective_params.get("active", False)
        
        if small_account_active:
            max_positions = effective_params.get("max_positions", 30)
            max_position_pct = effective_params.get("max_position_pct", 0.05)
            mode_label = "small-account"
        else:
            max_positions = risk_config.max_total_positions
            max_position_pct = risk_config.max_position_pct
            mode_label = "standard"
        
        try:
            positions = self.alpaca.get_positions()
            account = self.alpaca.get_account()
            portfolio_value = float(account.portfolio_value) if account else 0
            
            # Check total positions limit
            if len(positions) >= max_positions:
                violations.append(
                    f"Max positions reached ({mode_label}): {len(positions)}/{max_positions}"
                )
            
            # Check individual position concentration
            for pos in positions:
                pos_value = abs(float(pos.market_value))
                pos_pct = (pos_value / portfolio_value) * 100 if portfolio_value > 0 else 0
                max_pct_display = max_position_pct * 100
                
                if pos_pct > max_pct_display:
                    violations.append(
                        f"{pos.symbol} exceeds max position ({mode_label}): {pos_pct:.1f}% > {max_pct_display:.1f}%"
                    )
            
            return {
                "violations": violations,
                "position_count": len(positions),
                "max_positions": max_positions,
                "can_add_position": len(positions) < max_positions,
                "small_account_mode": small_account_active,
            }
            
        except Exception as e:
            logger.warning(f"Risk limit check failed: {e}")
            return {"violations": [], "can_add_position": True}

    def _check_hold_time_violations(self) -> List[Dict[str, Any]]:
        """
        Check for positions that have exceeded max hold time.
        
        Returns:
            List of positions that should be rotated out
        """
        from src.trading.config import get_risk_config
        
        risk_config = get_risk_config()
        max_hold_hours = risk_config.max_hold_hours
        violations = []
        
        try:
            # Check trade history for entry times
            if hasattr(self, 'trade_history') and self.trade_history:
                # Get open positions and their entry times
                positions = self.alpaca.get_positions()
                
                for pos in positions:
                    # Look up entry time from trade history
                    # For now, we'll use a simpler approach based on change_today
                    # Full implementation would query trade_history table
                    
                    # Placeholder: Log warning for positions held a long time
                    # This can be enhanced with actual entry time tracking
                    pass
                    
        except Exception as e:
            logger.warning(f"Hold time check failed: {e}")
        
        return violations
    
    def _serialize_agent_signals(self, analysis: Optional['AnalysisResult']) -> Dict[str, Any]:
        """
        Serialize agent signals to a JSON-friendly dict with real agent names.
        
        Handles various input formats:
        - Dataclasses (AgentSignal)
        - Nested dicts {ticker: {agent: signal_data}}
        - Flat dicts {agent: signal_data}
        
        Returns:
            Dict mapping agent_name -> {signal, confidence, reasoning}
        """
        from dataclasses import asdict, is_dataclass
        
        if not analysis or not hasattr(analysis, 'analyst_signals'):
            return {}
        
        raw_signals = analysis.analyst_signals or {}
        serialized = {}
        
        def extract_signal_data(obj) -> Optional[Dict[str, Any]]:
            """Extract signal, confidence, reasoning from various formats."""
            if obj is None:
                return None
            
            if is_dataclass(obj) and not isinstance(obj, type):
                # Convert dataclass to dict
                try:
                    obj = asdict(obj)
                except Exception:
                    obj = {
                        "signal": getattr(obj, 'signal', getattr(obj, 'sig', 'neutral')),
                        "confidence": getattr(obj, 'confidence', getattr(obj, 'conf', 50)),
                        "reasoning": getattr(obj, 'reasoning', ''),
                    }
            
            if isinstance(obj, dict):
                return {
                    "signal": str(obj.get("signal", obj.get("sig", "neutral"))),
                    "confidence": float(obj.get("confidence", obj.get("conf", 50)) or 50),
                    "reasoning": str(obj.get("reasoning", ""))[:500] if obj.get("reasoning") else None,
                }
            
            return None
        
        # Handle nested format: {ticker: {agent: signal_data}}
        for key, value in raw_signals.items():
            if isinstance(value, dict):
                # Check if this is a nested ticker->agent format
                first_val = next(iter(value.values()), None) if value else None
                if isinstance(first_val, dict) and any(k in first_val for k in ['signal', 'sig', 'confidence', 'conf']):
                    # This is {ticker: {agent: signal_data}} - extract agent level
                    for agent_name, agent_data in value.items():
                        signal_dict = extract_signal_data(agent_data)
                        if signal_dict:
                            serialized[agent_name] = signal_dict
                else:
                    # This might be {agent: signal_data} directly
                    signal_dict = extract_signal_data(value)
                    if signal_dict:
                        serialized[key] = signal_dict
            else:
                # Could be a dataclass
                signal_dict = extract_signal_data(value)
                if signal_dict:
                    serialized[key] = signal_dict
        
        return serialized
    
    async def run_trading_cycle(
        self,
        tickers: Optional[List[str]] = None,
        min_confidence: float = None,
        max_signals: int = None,
        execute_trades_flag: bool = True,
        dry_run: bool = False
    ) -> AutomatedTradeResult:
        """
        Run a complete automated trading cycle.
        
        Args:
            tickers: List of tickers to screen (default: watchlist + popular)
            min_confidence: Minimum strategy confidence (default: 60)
            max_signals: Max signals to process (default: 5)
            execute_trades_flag: Whether to execute trades (default: True)
            dry_run: If True, don't actually execute (default: False)
            
        Returns:
            AutomatedTradeResult with full cycle details
        """
        import uuid as uuid_module
        import os
        
        start_time = datetime.now()
        workflow_id = uuid_module.uuid4()
        
        # Check AUTO_TRADING_ENABLED flag (safety guardrail)
        auto_enabled = os.getenv("AUTO_TRADING_ENABLED", "false").lower() == "true"
        
        if not auto_enabled and execute_trades_flag and not dry_run:
            logger.warning("⚠️ AUTO_TRADING_ENABLED=false - blocking live trade execution")
            return AutomatedTradeResult(
                timestamp=start_time,
                tickers_screened=0,
                signals_found=0,
                mazo_validated=0,
                trades_analyzed=0,
                trades_executed=0,
                total_execution_time_ms=0,
                errors=["AUTO_TRADING_ENABLED=false - live trading blocked. Set to 'true' to enable."]
            )
        
        # Check Pattern Day Trader status before starting
        pdt_status = self._check_pdt_limits()
        if pdt_status.get("blocked"):
            logger.warning(f"⚠️ PDT limit reached - {pdt_status.get('reason')}")
            return AutomatedTradeResult(
                timestamp=start_time,
                tickers_screened=0,
                signals_found=0,
                mazo_validated=0,
                trades_analyzed=0,
                trades_executed=0,
                total_execution_time_ms=0,
                errors=[f"PDT protection: {pdt_status.get('reason')}"]
            )
        
        self.is_running = True
        
        # Check account equity for small account mode
        try:
            account = self.alpaca.get_account()
            current_equity = float(account.equity) if account else 0.0
        except Exception as e:
            logger.warning(f"Could not fetch account equity: {e}")
            current_equity = 0.0
        
        # Get effective parameters based on account size
        effective_params = get_effective_trading_params(current_equity)
        small_account_active = effective_params.get("active", False)
        
        if small_account_active:
            logger.info(
                f"💰 SMALL ACCOUNT MODE ACTIVE (equity: ${current_equity:,.2f}) - "
                f"targeting ${effective_params.get('target_notional_per_trade', 30):.0f}/trade, "
                f"max {effective_params.get('max_signals', 15)} signals"
            )
            min_conf = min_confidence or effective_params.get("min_confidence", 55)
            max_sig = max_signals or effective_params.get("max_signals", 15)
        else:
            signal_config = get_signal_config()
            min_conf = min_confidence or signal_config.min_signal_confidence
            max_sig = max_signals or signal_config.max_signals_per_cycle
        
        # Store for use in position sizing
        self._effective_params = effective_params
        
        result = AutomatedTradeResult(
            timestamp=start_time,
            tickers_screened=0,
            signals_found=0,
            mazo_validated=0,
            trades_analyzed=0,
            trades_executed=0,
            total_execution_time_ms=0,
        )
        
        # Log workflow start event
        try:
            from src.monitoring import get_event_logger
            event_logger = get_event_logger()
            # Check if market is open
            from src.trading.alpaca_service import get_alpaca_service
            alpaca = get_alpaca_service()
            market_open = alpaca.is_market_open() if alpaca else False
            
            event_logger.log_workflow_event(
                workflow_id=workflow_id,
                workflow_type="automated_trading",
                step_name="trading_cycle_start",
                status="started",
                payload={
                    "dry_run": dry_run,
                    "execute_trades": execute_trades_flag,
                    "small_account_mode": small_account_active,
                    "auto_trading_enabled": auto_enabled,
                    "market_hours": market_open,
                    "effective_params": {
                        "min_confidence": min_conf,
                        "max_signals": max_sig,
                        "target_notional": effective_params.get("target_notional_per_trade") if small_account_active else None,
                    },
                    "equity": current_equity,
                }
            )
        except Exception as e:
            logger.debug(f"Failed to log workflow start: {e}")
        
        try:
            # Get tickers to screen
            if not tickers:
                tickers = self._get_screening_universe()
            
            result.tickers_screened = len(tickers)
            logger.info(f"🔍 Starting trading cycle - Screening {len(tickers)} tickers")
            
            # Log universe data for Round Table
            try:
                from src.monitoring import get_event_logger
                from src.trading.watchlist_service import get_watchlist_service
                ws = get_watchlist_service()
                watchlist_items = ws.get_watchlist(status="watching")
                watchlist_tickers = [w.ticker for w in watchlist_items] if watchlist_items else []
                
                get_event_logger().log_workflow_event(
                    workflow_id=workflow_id,
                    workflow_type="automated_trading",
                    step_name="universe_prepared",
                    status="completed",
                    payload={
                        "tickers": tickers,
                        "universe_size": len(tickers),
                        "watchlist_tickers": watchlist_tickers,
                        "watchlist_count": len(watchlist_tickers),
                    }
                )
            except Exception:
                pass
            
            # Helper to log step events
            def log_step(step_name: str, status: str, ticker: str = None, payload: dict = None):
                try:
                    from src.monitoring import get_event_logger
                    get_event_logger().log_workflow_event(
                        workflow_id=workflow_id,
                        workflow_type="automated_trading",
                        step_name=step_name,
                        status=status,
                        ticker=ticker,
                        payload=payload
                    )
                except Exception:
                    pass
            
            # =============================================
            # STEP 0: Capital Management & Position Rotation
            # =============================================
            log_step("capital_rotation", "started")
            await self._manage_capital_rotation(result, execute_trades_flag, dry_run)
            
            # Log capital rotation with REAL portfolio data
            try:
                acct = self.alpaca.get_account()
                day_trades_remaining = 3 - int(getattr(acct, 'daytrade_count', 0))
                log_step("capital_rotation", "completed", payload={
                    "portfolio_value": float(acct.portfolio_value) if acct else None,
                    "buying_power": float(acct.buying_power) if acct else None,
                    "cash_available": float(acct.cash) if acct else None,
                    "day_trades_remaining": day_trades_remaining,
                })
            except Exception:
                log_step("capital_rotation", "completed")
            
            # =============================================
            # STEP 1: Strategy Engine Quick Screening
            # =============================================
            logger.info("📊 Step 1: Strategy Engine Screening...")
            log_step("strategy_screening", "started", payload={"ticker_count": len(tickers)})
            signals = await self._run_strategy_screening(tickers, min_conf)
            result.signals_found = len(signals)
            log_step("strategy_screening", "completed", payload={"signals_found": len(signals)})
            
            if not signals:
                logger.info("No signals found above confidence threshold")
                self._finalize_result(result, start_time, workflow_id=workflow_id)
                return result
            
            logger.info(f"Found {len(signals)} signals above {min_conf}% confidence")
            
            # Take top signals
            top_signals = signals[:max_sig]
            
            # =============================================
            # STEP 2: Mazo Validation
            # =============================================
            logger.info("🔬 Step 2: Mazo Validation...")
            log_step("mazo_validation", "started", payload={"signals_to_validate": len(top_signals)})
            validated_signals = await self._run_mazo_validation(top_signals)
            result.mazo_validated = len(validated_signals)
            log_step("mazo_validation", "completed", payload={"validated_count": len(validated_signals)})
            
            if not validated_signals:
                logger.info("No signals validated by Mazo")
                self._finalize_result(result, start_time, workflow_id=workflow_id)
                return result
            
            logger.info(f"Mazo validated {len(validated_signals)} signals")
            
            # =============================================
            # STEP 3: Full AI Analyst Pipeline
            # =============================================
            logger.info("🧠 Step 3: AI Analyst Deep Analysis...")
            log_step("ai_analyst_pipeline", "started", payload={"tickers_to_analyze": len(validated_signals)})
            
            # Get portfolio context for PM
            portfolio_context = build_portfolio_context()
            
            for signal, validation in validated_signals:
                try:
                    analysis = await self._run_full_analysis(
                        signal,
                        validation,
                        portfolio_context,
                        workflow_id=workflow_id  # Pass workflow_id for consistent logging
                    )
                    result.trades_analyzed += 1
                    
                    # =============================================
                    # STEP 4: Execute if PM decides
                    # =============================================
                    if analysis and analysis.pm_decision:
                        action = analysis.pm_decision.get("action", "hold")
                        
                        if action not in ["hold", "cancel"]:
                            logger.info(f"💹 Step 4: Executing {action} for {signal.ticker}")
                            
                            if execute_trades_flag and not dry_run:
                                trade_result = await self._execute_trade(
                                    signal.ticker,
                                    analysis.pm_decision,
                                    portfolio_context,
                                    workflow_id=analysis.workflow_id,
                                    signal=signal,
                                    validation=validation,
                                    analysis=analysis,
                                )
                                
                                if trade_result.get("success"):
                                    result.trades_executed += 1
                                    
                                    # Update PM decision with execution status
                                    if analysis.workflow_id:
                                        try:
                                            from src.monitoring import get_event_logger
                                            event_logger = get_event_logger()
                                            event_logger.update_pm_execution(
                                                workflow_id=analysis.workflow_id,
                                                ticker=signal.ticker,
                                                order_id=trade_result.get("order_id", ""),
                                                was_executed=True,
                                            )
                                        except Exception as pm_err:
                                            logger.debug(f"Failed to update PM execution: {pm_err}")
                                    
                                    # NOTE: Trade is now recorded via TradeHistoryService in _execute_trade
                                    # PerformanceTracker reads from the same table for metrics
                                    # (Removed duplicate record_trade call to prevent double inserts)
                                
                                result.results.append({
                                    "ticker": signal.ticker,
                                    "action": action,
                                    "signal": signal.to_dict(),
                                    "mazo_validation": {
                                        "agrees": validation.mazo_agrees,
                                        "sentiment": validation.mazo_sentiment,
                                        "key_points": validation.key_points[:3],
                                    },
                                    "pm_decision": analysis.pm_decision,
                                    "trade_result": trade_result,
                                })
                            else:
                                result.results.append({
                                    "ticker": signal.ticker,
                                    "action": action,
                                    "dry_run": True,
                                    "would_execute": True,
                                    "signal": signal.to_dict(),
                                    "pm_decision": analysis.pm_decision,
                                })
                        else:
                            result.results.append({
                                "ticker": signal.ticker,
                                "action": action,
                                "reason": analysis.reasoning,
                            })
                            
                except Exception as e:
                    error_msg = f"Error processing {signal.ticker}: {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
            
        except Exception as e:
            error_msg = f"Trading cycle failed: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            self._finalize_result(result, start_time, workflow_id=workflow_id, error_message=error_msg)
            self.is_running = False
            return result
            
        finally:
            # Only finalize if not already done (no errors)
            if self.is_running:
                self._finalize_result(result, start_time, workflow_id=workflow_id)
                self.is_running = False
            
        return result
    
    def _finalize_result(self, result: AutomatedTradeResult, start_time: datetime, workflow_id=None, error_message=None):
        """Finalize the result with timing and store in history."""
        result.total_execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        self.last_run = datetime.now()
        self.last_result = result
        self.run_history.append(result)

        # Keep last 50 runs
        if len(self.run_history) > 50:
            self.run_history = self.run_history[-50:]

        logger.info(
            f"✅ Trading cycle complete: "
            f"{result.signals_found} signals → "
            f"{result.mazo_validated} validated → "
            f"{result.trades_executed} executed "
            f"({result.total_execution_time_ms:.0f}ms)"
        )
        
        # Log workflow completion event
        if workflow_id:
            try:
                from src.monitoring import get_event_logger
                event_logger = get_event_logger()
                
                status = "completed" if not error_message else "error"
                event_logger.log_workflow_event(
                    workflow_id=workflow_id,
                    workflow_type="automated_trading",
                    step_name="trading_cycle_complete",
                    status=status,
                    duration_ms=int(result.total_execution_time_ms),
                    error_message=error_message,
                    payload={
                        "tickers_screened": result.tickers_screened,
                        "signals_found": result.signals_found,
                        "mazo_validated": result.mazo_validated,
                        "trades_executed": result.trades_executed,
                    }
                )
            except Exception as e:
                logger.debug(f"Failed to log workflow completion: {e}")
    
    async def _manage_capital_rotation(
        self, 
        result: AutomatedTradeResult, 
        execute_trades: bool,
        dry_run: bool
    ) -> None:
        """
        Capital Rotation - Industry Standard Intraday Practice
        
        Before looking for new opportunities, check if we need to free up capital
        by closing weak/stale positions. This is critical for active trading.
        
        Rotation Criteria (in priority order):
        1. Positions with negative P/L and low conviction
        2. Positions near breakeven with no momentum
        3. Oldest positions (capital has been tied up too long)
        """
        capital_config = get_capital_config()
        MIN_BUYING_POWER_PCT = capital_config.min_buying_power_pct
        MAX_POSITION_AGE_HOURS = capital_config.max_position_age_hours
        ROTATION_THRESHOLD_PCT = capital_config.rotation_threshold_pct
        
        try:
            account = self.alpaca.get_account()
            positions = self.alpaca.get_positions()
            
            if not positions or not account:
                return
            
            portfolio_value = float(account.portfolio_value)
            buying_power = float(account.buying_power)
            buying_power_pct = buying_power / portfolio_value if portfolio_value > 0 else 0
            
            logger.info(f"💰 Capital Check: ${buying_power:.2f} buying power ({buying_power_pct*100:.1f}% of portfolio)")
            
            # If we have enough buying power, no rotation needed
            if buying_power_pct >= MIN_BUYING_POWER_PCT:
                logger.info(f"✓ Sufficient buying power for new trades")
                return
            
            logger.warning(f"⚠️ Low buying power ({buying_power_pct*100:.1f}% < {MIN_BUYING_POWER_PCT*100}%) - evaluating positions for rotation")
            
            # Evaluate each position for rotation potential
            rotation_candidates = []
            
            for pos in positions:
                ticker = pos.symbol
                qty = float(pos.qty)
                entry_price = float(pos.avg_entry_price)
                current_price = float(pos.current_price)
                unrealized_pnl = float(pos.unrealized_pl)
                unrealized_pnl_pct = float(pos.unrealized_plpc) * 100
                market_value = abs(float(pos.market_value))
                side = "short" if qty < 0 else "long"
                
                # Calculate rotation score (lower = better candidate to close)
                # Factors: P/L %, position size, market value freed up
                score = 0
                reasons = []
                
                # Negative P/L = higher priority to close
                if unrealized_pnl_pct < 0:
                    score += 30 + abs(unrealized_pnl_pct) * 5  # More negative = higher score
                    reasons.append(f"losing {unrealized_pnl_pct:.1f}%")
                
                # Near breakeven (stale) = rotation candidate
                elif abs(unrealized_pnl_pct) < ROTATION_THRESHOLD_PCT * 100:
                    score += 20
                    reasons.append("near breakeven (stale)")
                
                # Positive P/L = lower priority (but small gains might still rotate)
                else:
                    score += 10 - min(unrealized_pnl_pct, 10)  # Lower score for bigger gains
                    reasons.append(f"profitable {unrealized_pnl_pct:.1f}%")
                
                # Larger positions free more capital
                capital_freed = market_value
                score += (capital_freed / portfolio_value) * 20  # Bonus for freeing more capital
                
                rotation_candidates.append({
                    "ticker": ticker,
                    "side": side,
                    "qty": abs(qty),
                    "pnl_pct": unrealized_pnl_pct,
                    "market_value": market_value,
                    "score": score,
                    "reasons": reasons,
                    "action": "cover" if side == "short" else "sell"
                })
            
            # Sort by score (highest = best rotation candidate)
            rotation_candidates.sort(key=lambda x: x["score"], reverse=True)
            
            if not rotation_candidates:
                logger.info("No rotation candidates found")
                return
            
            # Select the best candidate to rotate out
            best_candidate = rotation_candidates[0]
            
            logger.info(f"🔄 Best rotation candidate: {best_candidate['ticker']}")
            logger.info(f"   Side: {best_candidate['side']}, P/L: {best_candidate['pnl_pct']:.2f}%")
            logger.info(f"   Reasons: {', '.join(best_candidate['reasons'])}")
            logger.info(f"   Capital to free: ${best_candidate['market_value']:.2f}")
            
            # Execute the rotation (close the position)
            if execute_trades and not dry_run:
                try:
                    from src.monitoring import get_event_logger
                    event_logger = get_event_logger()
                    
                    submitted_at = datetime.now()
                    close_result = self.alpaca.close_position(
                        best_candidate["ticker"],
                        qty=best_candidate["qty"]
                    )

                    if close_result.success:
                        logger.info(f"✅ Rotated out of {best_candidate['ticker']}: {close_result.message}")
                        result.trades_executed += 1
                        result.results.append({
                            "ticker": best_candidate["ticker"],
                            "action": f"rotation_{best_candidate['action']}",
                            "reason": f"Capital rotation: {', '.join(best_candidate['reasons'])}",
                            "capital_freed": best_candidate["market_value"],
                            "pnl_pct": best_candidate["pnl_pct"]
                        })
                        
                        # Log rotation trade to monitoring
                        try:
                            event_logger.log_trade_execution(
                                order_id=f"rotation_{best_candidate['ticker']}_{submitted_at.timestamp()}",
                                ticker=best_candidate["ticker"],
                                side=best_candidate["action"],  # sell or cover
                                quantity=float(best_candidate["qty"]),
                                order_type="market",
                                status="filled",
                                submitted_at=submitted_at,
                                filled_at=datetime.now(),
                                filled_qty=float(best_candidate["qty"]),
                            )
                            logger.info(f"✓ Rotation trade logged to monitoring")
                        except Exception as log_err:
                            logger.warning(f"Failed to log rotation trade: {log_err}")
                    else:
                        logger.warning(f"Failed to rotate {best_candidate['ticker']}: {close_result.error}")
                        result.errors.append(f"Rotation failed for {best_candidate['ticker']}: {close_result.error}")
                        
                except Exception as e:
                    logger.error(f"Rotation execution error: {e}")
                    result.errors.append(f"Rotation error: {e}")
            else:
                logger.info(f"🔄 [DRY RUN] Would rotate out of {best_candidate['ticker']}")
                result.results.append({
                    "ticker": best_candidate["ticker"],
                    "action": f"rotation_{best_candidate['action']}_dry_run",
                    "reason": f"Capital rotation: {', '.join(best_candidate['reasons'])}",
                    "capital_freed": best_candidate["market_value"],
                    "pnl_pct": best_candidate["pnl_pct"]
                })
                
        except Exception as e:
            logger.error(f"Capital rotation check failed: {e}")
            # Don't fail the whole cycle if rotation check fails
    
    def _get_screening_universe(self) -> List[str]:
        """
        Build a dynamic screening universe based on:
        1. Current portfolio positions (must always monitor)
        2. User watchlist
        3. Diversified sector picks based on buying power
        4. Trending/momentum stocks from various sectors
        
        In small account mode, prioritizes affordable, liquid stocks and ETFs.

        This ensures we're not hardcoded to specific tickers and
        the system discovers opportunities across the market.
        """
        tickers = []
        
        # Check for small account mode
        effective_params = getattr(self, '_effective_params', {})
        small_account_active = effective_params.get("active", False)
        max_ticker_price = effective_params.get("max_ticker_price", 500.0) if small_account_active else 10000.0
        include_etfs = effective_params.get("include_etfs", False) if small_account_active else False
        
        if small_account_active:
            logger.info(f"🔍 Building small-account universe (max price: ${max_ticker_price:.0f}, ETFs: {include_etfs})")

        # PRIORITY 1: Current positions (ALWAYS monitor what we own)
        try:
            positions = self.alpaca.get_positions()
            account = self.alpaca.get_account()
            buying_power = float(account.buying_power) if account else 0

            for pos in positions or []:
                if pos.symbol not in tickers:
                    tickers.append(pos.symbol)
                    logger.debug(f"Added position: {pos.symbol}")
        except Exception as e:
            logger.warning(f"Could not fetch positions: {e}")
            buying_power = 10000  # Default assumption

        # PRIORITY 2: User watchlist
        try:
            from src.trading.watchlist_service import get_watchlist_service
            watchlist_service = get_watchlist_service()
            watchlist = watchlist_service.get_watchlist(status="watching")
            for item in watchlist:
                if item.ticker not in tickers:
                    tickers.append(item.ticker)
        except Exception as e:
            logger.debug(f"Watchlist not available: {e}")
        
        # PRIORITY 2.5: Small account ETFs (affordable, liquid, diversified)
        if small_account_active and include_etfs:
            small_account_etfs = [
                "SPY", "QQQ", "IWM",  # Major indexes
                "XLF", "XLK", "XLE", "XLV", "XLI",  # Sector ETFs
                "ARKK", "ARKG",  # Growth/Innovation
                "VTI", "VOO",  # Broad market
                "SOXL", "TQQQ",  # Leveraged (high volatility for small trades)
            ]
            for etf in small_account_etfs:
                if etf not in tickers and len(tickers) < 40:
                    tickers.append(etf)
            logger.debug(f"Added {len(small_account_etfs)} small-account ETFs to universe")

        # PRIORITY 3: Diversified sector picks based on buying power
        max_universe_size = 40 if small_account_active else 25
        
        try:
            from src.trading.diversification_scanner import DiversificationScanner
            scanner = DiversificationScanner()

            # Get current sector allocation
            current_sectors = scanner.get_current_portfolio_sectors()

            # Find underweight sectors and add stocks from them
            for sector, stocks in scanner.SECTOR_STOCKS.items():
                sector_weight = current_sectors.get(sector, 0)
                # Add stocks from underweight sectors
                if sector_weight < 0.15:  # Under 15% allocation
                    for stock in stocks[:2]:  # Add up to 2 per sector
                        if stock not in tickers:
                            # Check if affordable based on buying power and price limit
                            try:
                                quote = self.alpaca.get_quote(stock)
                                if quote:
                                    price = float(quote.ask_price) if quote.ask_price else 0
                                    # In small account mode, also check max price
                                    if small_account_active and price > max_ticker_price:
                                        continue
                                    if price < buying_power * 0.1:
                                        tickers.append(stock)
                            except Exception:
                                tickers.append(stock)  # Add anyway, will filter later
                        if len(tickers) >= max_universe_size:
                            break
                if len(tickers) >= max_universe_size:
                    break
        except Exception as e:
            logger.debug(f"Diversification scanner not available: {e}")
        
        # PRIORITY 4: If still need more, add market leaders by sector rotation
        # Rotate through sectors based on day of week for variety
        day_of_week = datetime.now().weekday()
        scanner_config = get_scanner_config()
        rotation_tickers = scanner_config.sector_rotation.get(day_of_week, [])
        for ticker in rotation_tickers:
            if ticker not in tickers and len(tickers) < max_universe_size + 5:
                tickers.append(ticker)
        
        # Log the universe
        mode_label = "small-account" if small_account_active else "standard"
        logger.info(f"Screening universe ({mode_label}): {len(tickers)} tickers from positions, watchlist, and sector rotation")
        
        # Cap initial universe before expensive filtering
        tickers = tickers[:max_universe_size]
        
        # Apply FMP liquidity filter (price/volume)
        if small_account_active:
            # Smaller accounts need more affordable, liquid stocks
            tickers = self._apply_liquidity_filter(
                tickers,
                min_price=1.0,
                max_price=100.0,  # Focus on sub-$100 for small accounts
                min_avg_volume=200000,  # Higher volume for better fills
            )
        else:
            tickers = self._apply_liquidity_filter(tickers)
        
        # Apply Danelfin AI scoring filter
        tickers, danelfin_scores = self._apply_danelfin_filter(tickers, small_account_active)

        # Store scores for downstream use
        self._universe_danelfin_scores = danelfin_scores

        return tickers
    
    def _apply_danelfin_filter(
        self,
        tickers: List[str],
        small_account_active: bool = False,
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Apply Danelfin AI scoring to filter and prioritize universe.
        
        Returns:
            Tuple of (filtered_tickers, danelfin_scores_dict)
        """
        try:
            from src.tools.danelfin_api import (
                is_danelfin_enabled,
                filter_universe_by_danelfin,
                prioritize_by_danelfin,
            )
            
            if not is_danelfin_enabled():
                logger.debug("Danelfin integration disabled, skipping filter")
                return tickers, {}
            
            danelfin_config = get_danelfin_config()
            
            # Determine minimum scores based on mode
            min_ai_score = danelfin_config.min_ai_score
            if small_account_active and danelfin_config.min_ai_score_small_account > 0:
                min_ai_score = danelfin_config.min_ai_score_small_account
            
            min_low_risk = danelfin_config.min_low_risk_score
            
            # Filter by Danelfin scores
            filtered_tickers, scores, filtered_out = filter_universe_by_danelfin(
                tickers,
                min_ai_score=min_ai_score,
                min_low_risk=min_low_risk,
            )
            
            if filtered_out:
                logger.info(
                    f"[Danelfin] Filtered {len(filtered_out)} tickers below thresholds "
                    f"(min AI={min_ai_score}, min LowRisk={min_low_risk})"
                )
            
            # Prioritize by Danelfin score if enabled
            if danelfin_config.prioritize_in_selection and scores:
                filtered_tickers = prioritize_by_danelfin(filtered_tickers, scores)
                logger.info(f"[Danelfin] Prioritized {len(filtered_tickers)} tickers by AI score")
            
            # Convert DanelfinScore objects to dicts for storage
            scores_dict = {}
            for ticker, score in scores.items():
                if hasattr(score, 'to_dict'):
                    scores_dict[ticker] = score.to_dict()
                else:
                    scores_dict[ticker] = score
            
            return filtered_tickers, scores_dict
            
        except ImportError as e:
            logger.debug(f"Danelfin not available: {e}")
            return tickers, {}
        except Exception as e:
            logger.warning(f"Danelfin filter error: {e}")
            return tickers, {}
    
    def _apply_liquidity_filter(
        self,
        tickers: List[str],
        min_price: float = 1.0,
        max_price: float = 500.0,
        min_avg_volume: int = 100000,
    ) -> List[str]:
        """
        Filter tickers by liquidity criteria using FMP data.
        
        Args:
            tickers: List of ticker symbols
            min_price: Minimum stock price (default $1)
            max_price: Maximum stock price (default $500)
            min_avg_volume: Minimum average daily volume (default 100k)
        
        Returns:
            List of tickers meeting liquidity requirements
        """
        if not tickers:
            return tickers
        
        try:
            from src.tools.api import get_prices
            from datetime import datetime, timedelta
            
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
            
            liquid_tickers = []
            illiquid_tickers = []
            
            for ticker in tickers[:50]:  # Limit API calls
                try:
                    prices = get_prices(ticker, start_date, end_date)
                    
                    if not prices:
                        illiquid_tickers.append((ticker, "no price data"))
                        continue
                    
                    # Get latest price and average volume
                    latest_price = prices[0].close if prices else 0
                    avg_volume = sum(p.volume for p in prices if p.volume) / len(prices) if prices else 0
                    
                    # Apply filters
                    if latest_price < min_price:
                        illiquid_tickers.append((ticker, f"price ${latest_price:.2f} < ${min_price}"))
                    elif latest_price > max_price:
                        illiquid_tickers.append((ticker, f"price ${latest_price:.2f} > ${max_price}"))
                    elif avg_volume < min_avg_volume:
                        illiquid_tickers.append((ticker, f"volume {avg_volume:.0f} < {min_avg_volume}"))
                    else:
                        liquid_tickers.append(ticker)
                        
                except Exception as e:
                    # Include ticker on error (don't filter out due to API issues)
                    liquid_tickers.append(ticker)
                    logger.debug(f"Liquidity check skipped for {ticker}: {e}")
            
            # Add remaining tickers that weren't checked (due to API limit)
            unchecked = [t for t in tickers[50:] if t not in liquid_tickers]
            liquid_tickers.extend(unchecked)
            
            if illiquid_tickers:
                logger.info(
                    f"[Liquidity] Filtered {len(illiquid_tickers)} illiquid tickers: "
                    f"{', '.join([f'{t[0]}({t[1]})' for t in illiquid_tickers[:5]])}"
                )
            
            logger.debug(f"[Liquidity] {len(liquid_tickers)}/{len(tickers)} tickers passed filter")
            return liquid_tickers
            
        except Exception as e:
            logger.debug(f"Liquidity filter error, returning all tickers: {e}")
            return tickers
    
    def _annotate_signal_with_danelfin(
        self,
        signal: TradingSignal,
        danelfin_data: Dict[str, Any],
        danelfin_config: Any,
    ) -> TradingSignal:
        """
        Annotate a trading signal with Danelfin data.
        
        - Adds Danelfin scores to signal metadata
        - Adjusts confidence if Danelfin disagrees
        - Flags signals for review if needed
        """
        if not danelfin_data or not danelfin_data.get('success', False):
            # No Danelfin data, return signal unchanged
            return signal
        
        try:
            # Add Danelfin data to signal metadata
            if not hasattr(signal, 'metadata') or signal.metadata is None:
                signal.metadata = {}
            
            signal.metadata['danelfin'] = {
                'ai_score': danelfin_data.get('ai_score', 0),
                'technical': danelfin_data.get('technical', 0),
                'fundamental': danelfin_data.get('fundamental', 0),
                'sentiment': danelfin_data.get('sentiment', 0),
                'low_risk': danelfin_data.get('low_risk', 0),
                'signal': danelfin_data.get('signal', 'unknown'),
            }
            
            # Check for disagreement
            ai_score = danelfin_data.get('ai_score', 5)
            signal_direction = signal.direction.value.lower() if hasattr(signal.direction, 'value') else str(signal.direction).lower()
            
            # If we're bullish but Danelfin score is very low, flag it
            if signal_direction in ('long', 'buy'):
                if ai_score < danelfin_config.disagreement_threshold:
                    # Apply confidence penalty
                    original_confidence = signal.confidence
                    signal.confidence = int(signal.confidence * danelfin_config.disagreement_confidence_penalty)
                    signal.metadata['danelfin']['disagreement'] = True
                    signal.metadata['danelfin']['confidence_adjusted'] = True
                    signal.metadata['danelfin']['original_confidence'] = original_confidence
                    logger.warning(
                        f"[Danelfin] Disagreement for {signal.ticker}: "
                        f"BUY signal but AI score is {ai_score}/10 (threshold: {danelfin_config.disagreement_threshold}). "
                        f"Confidence reduced {original_confidence}% → {signal.confidence}%"
                    )
                elif ai_score >= 8:
                    # Boost confidence slightly for strong agreement
                    signal.confidence = min(100, int(signal.confidence * 1.05))
                    signal.metadata['danelfin']['strong_agreement'] = True
            
            # For sell signals, low Danelfin score is actually agreement
            elif signal_direction in ('short', 'sell'):
                if ai_score >= 7:
                    # Danelfin thinks it's a good stock, but we want to sell - flag it
                    original_confidence = signal.confidence
                    signal.confidence = int(signal.confidence * 0.9)
                    signal.metadata['danelfin']['disagreement'] = True
                    signal.metadata['danelfin']['confidence_adjusted'] = True
                    logger.warning(
                        f"[Danelfin] Disagreement for {signal.ticker}: "
                        f"SELL signal but AI score is {ai_score}/10 (high). "
                        f"Confidence reduced {original_confidence}% → {signal.confidence}%"
                    )
            
            return signal
            
        except Exception as e:
            logger.debug(f"Error annotating signal with Danelfin: {e}")
            return signal
    
    async def _run_strategy_screening(
        self,
        tickers: List[str],
        min_confidence: float
    ) -> List[TradingSignal]:
        """Run strategy engine screening on tickers.
        
        Signals include fractionable status from Alpaca asset info.
        Annotates signals with Danelfin data if available.
        """
        all_signals = []
        
        # Get Danelfin scores (already fetched during universe building)
        danelfin_scores = getattr(self, '_universe_danelfin_scores', {})
        danelfin_config = get_danelfin_config()

        for ticker in tickers:
            try:
                # Pass alpaca service to get fractionable status
                signals = self.strategy_engine.analyze_ticker(
                    ticker, 
                    alpaca_service=self.alpaca
                )
                
                for signal in signals:
                    if signal.confidence >= min_confidence:
                        # Annotate with Danelfin data
                        signal = self._annotate_signal_with_danelfin(
                            signal, 
                            danelfin_scores.get(ticker),
                            danelfin_config
                        )
                        all_signals.append(signal)
            except Exception as e:
                logger.warning(f"Screening failed for {ticker}: {e}")

        # Sort by confidence
        all_signals.sort(key=lambda x: x.confidence, reverse=True)
        return all_signals
    
    async def _run_mazo_validation(
        self, 
        signals: List[TradingSignal]
    ) -> List[Tuple[TradingSignal, ValidationResult]]:
        """Validate signals with Mazo quick research."""
        validated = []
        mazo_available = True
        
        for signal in signals:
            try:
                import time
                import uuid as uuid_module
                mazo_start = time.time()
                
                # Run quick Mazo research
                direction_str = signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction)
                query = f"Should I {direction_str} {signal.ticker}? Current price is ${signal.entry_price:.2f}. Give a quick buy/sell/hold recommendation."
                research = self.mazo.research(query)
                mazo_latency_ms = int((time.time() - mazo_start) * 1000)
                
                # Log the Mazo research
                try:
                    from src.monitoring import get_event_logger
                    event_logger = get_event_logger()
                    workflow_id = uuid_module.uuid4()  # Generate ID for this validation
                    
                    # Parse sentiment early for logging
                    sentiment = "unknown"
                    if research and research.answer:
                        answer_lower = research.answer.lower()
                        if any(w in answer_lower for w in ["bullish", "buy", "strong buy"]):
                            sentiment = "bullish"
                        elif any(w in answer_lower for w in ["bearish", "sell", "short"]):
                            sentiment = "bearish"
                        else:
                            sentiment = "neutral"
                    
                    event_logger.log_mazo_research(
                        workflow_id=workflow_id,
                        ticker=signal.ticker,
                        query=query,
                        mode="automated_validation",
                        response=research.answer if research else None,
                        sources=[{"source": s} for s in (research.data_sources or [])] if research else None,
                        sentiment=sentiment,
                        sentiment_confidence="medium",
                        key_points=[],
                        success=research is not None and research.answer is not None,
                        error=None,
                        latency_ms=mazo_latency_ms,
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to log Mazo research: {log_err}")

                if not research or not research.answer:
                    # Mazo returned nothing - allow through if high confidence
                    if signal.confidence >= 65:
                        validated.append((signal, ValidationResult(
                            ticker=signal.ticker,
                            mazo_agrees=True,
                            mazo_sentiment="unknown",
                            mazo_confidence="unknown",
                            key_points=["Mazo returned no response - proceeding on technical signal"],
                            recommendation="Technical signal only"
                        )))
                        logger.info(f"⚡ {signal.ticker}: Mazo no response, proceeding on {signal.confidence:.0f}% confidence")
                    continue
                
                # Parse Mazo's sentiment from answer
                answer_lower = research.answer.lower()
                
                # Determine Mazo's sentiment
                if any(word in answer_lower for word in ["bullish", "buy", "strong buy", "upside"]):
                    mazo_sentiment = "bullish"
                elif any(word in answer_lower for word in ["bearish", "sell", "short", "downside"]):
                    mazo_sentiment = "bearish"
                else:
                    mazo_sentiment = "neutral"
                
                # Check if Mazo agrees with signal
                signal_bullish = signal.direction == SignalDirection.LONG
                mazo_agrees = (
                    (signal_bullish and mazo_sentiment == "bullish") or
                    (not signal_bullish and mazo_sentiment == "bearish")
                )
                
                # Determine confidence from answer length and keywords
                if any(word in answer_lower for word in ["strong", "confident", "clear", "definite"]):
                    mazo_confidence = "high"
                elif any(word in answer_lower for word in ["moderate", "some", "potential"]):
                    mazo_confidence = "medium"
                else:
                    mazo_confidence = "low"
                
                # Extract key points (first 3 sentences)
                sentences = research.answer.split(". ")
                key_points = [s.strip() + "." for s in sentences[:3] if s.strip()]
                
                validation = ValidationResult(
                    ticker=signal.ticker,
                    mazo_agrees=mazo_agrees,
                    mazo_sentiment=mazo_sentiment,
                    mazo_confidence=mazo_confidence,
                    key_points=key_points,
                    recommendation=research.answer[:200] + "..." if len(research.answer) > 200 else research.answer,
                    mazo_response=research.answer,
                )
                
                # Only proceed if Mazo agrees or is neutral with high confidence
                if mazo_agrees or (mazo_sentiment == "neutral" and signal.confidence >= 70):
                    validated.append((signal, validation))
                    logger.info(f"✓ {signal.ticker}: Mazo {mazo_sentiment} (agrees: {mazo_agrees})")
                else:
                    logger.info(f"✗ {signal.ticker}: Mazo {mazo_sentiment} disagrees with {direction_str}")
                    
            except Exception as e:
                logger.warning(f"Mazo validation failed for {signal.ticker}: {e}")
                mazo_available = False
                # On Mazo failure, allow signals through based on confidence
                if signal.confidence >= 60:
                    validated.append((signal, ValidationResult(
                        ticker=signal.ticker,
                        mazo_agrees=True,  # Assume agreement when Mazo unavailable
                        mazo_sentiment="unavailable",
                        mazo_confidence="unknown",
                        key_points=[f"Mazo unavailable ({str(e)[:50]})", "Proceeding on technical signal"],
                        recommendation="Technical signal only - Mazo bypass"
                    )))
                    logger.info(f"⚡ {signal.ticker}: Mazo failed, proceeding on {signal.confidence:.0f}% confidence")
        
        # If Mazo consistently fails, log a warning
        if not mazo_available and len(signals) > 0:
            logger.warning("⚠️ Mazo appears to be unavailable - signals proceeding on technical analysis only")
        
        return validated
    
    async def _run_full_analysis(
        self,
        signal: TradingSignal,
        validation: ValidationResult,
        portfolio_context: PortfolioContext,
        workflow_id: 'uuid.UUID' = None
    ) -> Optional[AnalysisResult]:
        """Run full AI analyst pipeline.
        
        Args:
            signal: Trading signal to analyze
            validation: Mazo validation result
            portfolio_context: Portfolio context
            workflow_id: Workflow ID for logging (passed from run_trading_cycle)
        """
        try:
            # Create workflow
            workflow = UnifiedWorkflow()

            # Run the hedge fund analysis pipeline
            # This will run all AI agents and PM
            from integration.unified_workflow import WorkflowMode
            results = workflow.analyze(
                tickers=[signal.ticker],
                mode=WorkflowMode.SIGNAL_ONLY,  # Just get signals from agents
            )
            
            # Get first result
            result = results[0] if results else None
            
            if not result:
                return None
            
            # Extract PM decision
            pm_decision = result.pm_decision if hasattr(result, 'pm_decision') else None
            
            # Get consensus from agent signals
            agent_signals = {}
            consensus_direction = "neutral"
            consensus_confidence = 0.0
            
            # Try to get event logger for monitoring
            event_logger = None
            try:
                from src.monitoring import get_event_logger
                event_logger = get_event_logger()
            except ImportError:
                pass
            
            # Use passed workflow_id or generate one
            import uuid as uuid_module
            if workflow_id is None:
                workflow_id = uuid_module.uuid4()
            
            # Get agent signals from result - can be in different formats
            result_agent_signals = []
            if hasattr(result, 'agent_signals') and result.agent_signals:
                result_agent_signals = result.agent_signals
            elif hasattr(result, 'hedge_fund') and result.hedge_fund:
                # Old format - dict of dicts
                hf_signals = result.hedge_fund.get("analyst_signals", {})
                for ticker_data in hf_signals.values():
                    for agent_name, agent_data in ticker_data.items():
                        if isinstance(agent_data, dict):
                            result_agent_signals.append({
                                "agent": agent_name,
                                "signal": agent_data.get("signal", "neutral"),
                                "confidence": agent_data.get("confidence", 50),
                                "reasoning": agent_data.get("reasoning", ""),
                            })
            
            # Calculate consensus and log agent signals
            bullish_count = 0
            bearish_count = 0
            total_confidence = 0
            
            for agent_signal in result_agent_signals:
                # Handle both dict and dataclass formats
                if hasattr(agent_signal, 'agent_name'):
                    # AgentSignal dataclass
                    agent_name = agent_signal.agent_name
                    sig = getattr(agent_signal, 'signal', 'neutral')
                    sig = sig.lower() if sig else 'neutral'
                    conf = getattr(agent_signal, 'confidence', 50) or 50
                    reasoning = getattr(agent_signal, 'reasoning', '') or ''
                elif hasattr(agent_signal, 'agent'):
                    # Alternative dataclass format
                    agent_name = agent_signal.agent
                    sig = getattr(agent_signal, 'signal', 'neutral')
                    sig = sig.lower() if sig else 'neutral'
                    conf = getattr(agent_signal, 'confidence', 50) or 50
                    reasoning = getattr(agent_signal, 'reasoning', '') or ''
                elif isinstance(agent_signal, dict):
                    agent_name = agent_signal.get("agent", agent_signal.get("agent_name", "unknown"))
                    sig = agent_signal.get("signal", "neutral")
                    sig = sig.lower() if sig else 'neutral'
                    conf = agent_signal.get("confidence", 50) or 50
                    reasoning = agent_signal.get("reasoning", "") or ""
                else:
                    continue
                
                # Log agent signal to monitoring
                if event_logger:
                    try:
                        event_logger.log_agent_signal(
                            workflow_id=workflow_id,
                            agent_id=agent_name,
                            ticker=signal.ticker,
                            signal=sig if sig else "neutral",
                            confidence=conf,
                            reasoning=str(reasoning)[:500] if reasoning else None,
                        )
                    except Exception:
                        pass  # Don't fail analysis if signal logging fails
                
                if "bullish" in sig or "buy" in sig:
                    bullish_count += 1
                    total_confidence += conf
                elif "bearish" in sig or "sell" in sig or "short" in sig:
                    bearish_count += 1
                    total_confidence += conf
            
            # Convert back to dict for compatibility
            def get_agent_name(s):
                if hasattr(s, 'agent'):
                    return s.agent
                elif hasattr(s, 'agent_name'):
                    return s.agent_name
                elif isinstance(s, dict):
                    return s.get('agent', s.get('agent_name', 'unknown'))
                return 'unknown'
            
            agent_signals = {signal.ticker: {get_agent_name(s): s for s in result_agent_signals}} if result_agent_signals else {}
            
            total = bullish_count + bearish_count
            neutral_count = len(result_agent_signals) - bullish_count - bearish_count
            if total > 0:
                if bullish_count > bearish_count:
                    consensus_direction = "bullish"
                elif bearish_count > bullish_count:
                    consensus_direction = "bearish"
                consensus_confidence = total_confidence / total
            
            # Log PM decision with full context
            if event_logger and pm_decision:
                try:
                    # Get portfolio context for logging
                    portfolio_equity = None
                    portfolio_cash = None
                    try:
                        acct = self.alpaca.get_account()
                        portfolio_equity = float(acct.equity) if acct else None
                        portfolio_cash = float(acct.cash) if acct else None
                    except Exception:
                        pass
                    
                    event_logger.log_pm_decision(
                        workflow_id=workflow_id,
                        ticker=signal.ticker,
                        action=pm_decision.get("action", "hold"),
                        quantity=pm_decision.get("quantity"),
                        stop_loss_pct=pm_decision.get("stop_loss_pct"),
                        take_profit_pct=pm_decision.get("take_profit_pct"),
                        confidence=pm_decision.get("confidence"),
                        reasoning=pm_decision.get("reasoning") or (result.portfolio_manager_reasoning if hasattr(result, 'portfolio_manager_reasoning') else None),
                        bullish_count=bullish_count,
                        bearish_count=bearish_count,
                        neutral_count=neutral_count,
                        consensus_direction=consensus_direction,
                        consensus_score=consensus_confidence,
                        portfolio_equity=portfolio_equity,
                        portfolio_cash=portfolio_cash,
                        mazo_sentiment=validation.mazo_sentiment if validation else None,
                    )
                except Exception as pm_log_err:
                    logger.debug(f"Failed to log PM decision: {pm_log_err}")
            
            return AnalysisResult(
                ticker=signal.ticker,
                analyst_signals=agent_signals,
                consensus_direction=consensus_direction,
                consensus_confidence=consensus_confidence,
                pm_decision=pm_decision or {},
                reasoning=result.portfolio_manager_reasoning if hasattr(result, 'portfolio_manager_reasoning') else "",
                workflow_id=result.workflow_id if hasattr(result, 'workflow_id') else None
            )
            
        except Exception as e:
            logger.error(f"Full analysis failed for {signal.ticker}: {e}")
            
            # Fallback: Use strategy signal directly for PM decision
            # This allows trading even if full pipeline fails
            direction_value = signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction)
            action = "buy" if direction_value == "long" else "short"
            
            import uuid as uuid_module
            
            # Get effective params for position sizing
            effective_params = getattr(self, '_effective_params', {})
            use_notional = effective_params.get("use_notional_sizing", False)
            target_notional = effective_params.get("target_notional_per_trade", 30.0)
            
            return AnalysisResult(
                ticker=signal.ticker,
                analyst_signals={},
                consensus_direction=direction_value,
                consensus_confidence=signal.confidence,
                pm_decision={
                    "action": action,
                    "quantity": self._calculate_position_size(
                        signal, portfolio_context,
                        use_notional_sizing=use_notional,
                        target_notional=target_notional
                    ),
                    "confidence": signal.confidence,
                    "reasoning": f"Strategy: {signal.strategy} | {signal.reasoning}",
                    "stop_loss_pct": 5,
                    "take_profit_pct": 10,
                    "small_account_mode": use_notional,
                    "target_notional": target_notional if use_notional else None,
                },
                reasoning=f"Fallback: {signal.reasoning}",
                workflow_id=str(uuid_module.uuid4())  # Generate new ID for fallback
            )
    
    def _calculate_position_size(
        self,
        signal: TradingSignal,
        portfolio: PortfolioContext,
        use_notional_sizing: bool = False,
        target_notional: float = 30.0
    ) -> float:
        """
        Calculate position size based on signal and portfolio.

        Supports two modes:
        1. Standard mode: Uses signal.position_size_pct of available capital
        2. Small account mode: Uses fixed notional (dollar) amount per trade

        Also applies Danelfin-based size adjustments:
        - High Danelfin score (AI >= 8, Low Risk >= 6): boost size
        - Low Danelfin score (AI <= 4): reduce size

        Supports fractional shares when:
        - ALLOW_FRACTIONAL=true (global setting)
        - AND signal.fractionable=True (asset-specific)

        Returns float with up to 4 decimal places for Alpaca compatibility.
        """
        from src.trading.config import get_fractional_config

        fractional_config = get_fractional_config()

        # Determine if fractional trading is allowed for this specific asset
        use_fractional = (
            fractional_config.allow_fractional and
            getattr(signal, 'fractionable', True)  # Default True for backwards compat
        )

        # Calculate dollar amount to invest
        if use_notional_sizing:
            # Small account mode: use fixed notional amount
            position_value = target_notional
            logger.debug(
                f"[{signal.ticker}] Small account sizing: targeting ${target_notional:.2f} notional"
            )
        else:
            # Standard mode: use percentage of available capital
            position_pct = signal.position_size_pct or 0.05
            available = min(portfolio.cash, portfolio.buying_power)
            position_value = available * position_pct
        
        # Apply Danelfin-based size adjustment
        position_value = self._apply_danelfin_size_adjustment(signal.ticker, position_value)

        # Convert to shares
        if signal.entry_price and signal.entry_price > 0:
            shares = position_value / signal.entry_price

            if use_fractional:
                # Round to configured precision (default 4 decimal places)
                shares = round(shares, fractional_config.fractional_precision)
                # Ensure minimum quantity
                result = max(fractional_config.min_fractional_qty, shares)
                
                if use_notional_sizing:
                    logger.info(
                        f"[{signal.ticker}] Notional sizing: "
                        f"${target_notional:.2f} @ ${signal.entry_price:.2f} = {result:.4f} shares"
                    )
                return result
            else:
                # Whole shares only - log if we're rounding due to non-fractionable asset
                whole_shares = max(1, int(shares))
                if fractional_config.allow_fractional and not getattr(signal, 'fractionable', True):
                    logger.info(f"[{signal.ticker}] Asset not fractionable, using whole shares: {shares:.4f} → {whole_shares}")
                return whole_shares

        # Fallback: return minimum
        return fractional_config.min_fractional_qty if use_fractional else 1
    
    def _apply_danelfin_size_adjustment(
        self,
        ticker: str,
        base_value: float,
    ) -> float:
        """
        Apply Danelfin-based position size adjustment.

        - High AI score (>=8) + High Low Risk (>=6): boost by config factor
        - Low AI score (<=4): reduce by config factor
        - Otherwise: no adjustment
        
        Also stores allocation reason for Round Table logging.
        """
        try:
            danelfin_config = get_danelfin_config()

            if not danelfin_config.enabled:
                return base_value

            # Get Danelfin score from cached universe data
            danelfin_scores = getattr(self, '_universe_danelfin_scores', {})
            score_data = danelfin_scores.get(ticker)

            if not score_data or not score_data.get('success', False):
                return base_value

            ai_score = score_data.get('ai_score', 5)
            low_risk = score_data.get('low_risk', 5)

            # Track allocation reasons for Round Table
            allocation_reasons = getattr(self, '_allocation_reasons', {})

            # High conviction: AI >= 8 AND Low Risk >= 6
            if ai_score >= 8 and low_risk >= 6:
                boost = danelfin_config.high_score_size_boost
                adjusted = base_value * boost
                reason = f"Selected for boosted allocation: Danelfin AI={ai_score}/10, LowRisk={low_risk}/10 → +{int((boost-1)*100)}% size"
                allocation_reasons[ticker] = {
                    "type": "danelfin_boost",
                    "ai_score": ai_score,
                    "low_risk": low_risk,
                    "adjustment": boost,
                    "reason": reason,
                }
                self._allocation_reasons = allocation_reasons
                logger.info(f"[Danelfin] {ticker}: {reason} (${base_value:.2f} → ${adjusted:.2f})")
                return adjusted

            # Low conviction: AI <= 4
            if ai_score <= 4:
                reduction = danelfin_config.low_score_size_reduction
                adjusted = base_value * reduction
                reason = f"Reduced allocation: Danelfin AI={ai_score}/10 (low) → -{int((1-reduction)*100)}% size"
                allocation_reasons[ticker] = {
                    "type": "danelfin_reduce",
                    "ai_score": ai_score,
                    "low_risk": low_risk,
                    "adjustment": reduction,
                    "reason": reason,
                }
                self._allocation_reasons = allocation_reasons
                logger.info(f"[Danelfin] {ticker}: {reason} (${base_value:.2f} → ${adjusted:.2f})")
                return adjusted

            return base_value

        except Exception as e:
            logger.debug(f"Danelfin size adjustment skipped for {ticker}: {e}")
            return base_value
    
    def get_allocation_reasons(self) -> Dict[str, Dict]:
        """Get Danelfin allocation reasons for Round Table logging."""
        return getattr(self, '_allocation_reasons', {})
    
    async def _execute_trade(
        self,
        ticker: str,
        pm_decision: Dict[str, Any],
        portfolio: PortfolioContext,
        workflow_id: str = None,
        signal: 'TradingSignal' = None,
        validation: 'ValidationResult' = None,
        analysis: 'AnalysisResult' = None,
    ) -> Dict[str, Any]:
        """Execute trade via Alpaca directly and log to monitoring system and trade history."""
        try:
            from src.trading.alpaca_service import OrderSide, OrderType, TimeInForce
            from src.monitoring import get_event_logger
            
            event_logger = get_event_logger()
            
            action = pm_decision.get("action", "hold")
            quantity = pm_decision.get("quantity", 0)
            
            if action == "hold" or quantity == 0:
                return {"success": True, "message": "No trade needed (hold)"}
            
            # =============================================
            # COOLDOWN CHECK - Prevent duplicate trades
            # =============================================
            if action in ["buy", "short"]:  # Only check on opening positions
                can_trade, cooldown_reason = self._check_cooldown(ticker)
                if not can_trade:
                    logger.info(f"⏳ Skipping {ticker}: {cooldown_reason}")
                    try:
                        event_logger.log_trade_execution(
                            order_id=f"cooldown_skip_{ticker}_{datetime.now().timestamp()}",
                            ticker=ticker,
                            side=action,
                            quantity=float(quantity),
                            order_type="market",
                            status="skipped",
                            submitted_at=datetime.now(),
                            reject_reason=cooldown_reason,
                        )
                    except Exception:
                        pass
                    return {"success": False, "message": cooldown_reason, "skipped": True, "reason": "cooldown"}
            
            # =============================================
            # CONCENTRATION CHECK - Prevent over-exposure
            # =============================================
            if action in ["buy", "short"]:
                entry_price = signal.entry_price if signal and signal.entry_price else pm_decision.get("entry_price", 0)
                if not entry_price or entry_price <= 0:
                    # Try to get current price
                    try:
                        quote = self.alpaca.get_quote(ticker)
                        entry_price = float(quote.ask_price) if quote else 0
                    except Exception:
                        entry_price = 100  # Fallback
                
                can_trade, concentration_reason = self._check_concentration(ticker, quantity, entry_price)
                if not can_trade:
                    logger.info(f"📊 Skipping {ticker}: {concentration_reason}")
                    try:
                        event_logger.log_trade_execution(
                            order_id=f"concentration_skip_{ticker}_{datetime.now().timestamp()}",
                            ticker=ticker,
                            side=action,
                            quantity=float(quantity),
                            order_type="market",
                            status="skipped",
                            submitted_at=datetime.now(),
                            reject_reason=concentration_reason,
                        )
                    except Exception:
                        pass
                    return {"success": False, "message": concentration_reason, "skipped": True, "reason": "concentration"}
            
            # Map action to order side
            if action in ["buy", "cover"]:
                side = OrderSide.BUY
            elif action in ["sell", "short"]:
                side = OrderSide.SELL
            elif action == "reduce_long":
                side = OrderSide.SELL
            elif action == "reduce_short":
                side = OrderSide.BUY
            else:
                return {"success": False, "message": f"Unknown action: {action}"}
            
            submitted_at = datetime.now()
            
            # Submit order via Alpaca
            result = self.alpaca.submit_order(
                symbol=ticker,
                qty=quantity,
                side=side,
                order_type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY
            )
            
            if result and result.success:
                order = result.order
                order_id = order.id if order else f"manual_{ticker}_{submitted_at.timestamp()}"
                
                # Get fill price from order, or fallback to quote/signal price
                filled_price = None
                if order and order.filled_avg_price:
                    filled_price = float(order.filled_avg_price)
                else:
                    # Fallback: use the entry_price we calculated for concentration check
                    # or get fresh quote if we don't have it
                    fallback_price = signal.entry_price if signal and signal.entry_price else None
                    if not fallback_price:
                        try:
                            quote = self.alpaca.get_quote(ticker)
                            fallback_price = float(quote.last_price) if quote and quote.last_price else None
                            if not fallback_price:
                                fallback_price = float(quote.ask_price) if quote and quote.ask_price else None
                        except Exception:
                            pass
                    filled_price = fallback_price
                    if filled_price:
                        logger.debug(f"Using fallback price {filled_price} for {ticker} (order fill not yet available)")
                
                # Log successful trade execution to monitoring
                try:
                    event_logger.log_trade_execution(
                        order_id=order_id,
                        ticker=ticker,
                        side=side.value if hasattr(side, 'value') else str(side),
                        quantity=float(quantity),
                        order_type="market",
                        status=order.status if order else "submitted",
                        submitted_at=submitted_at,
                        filled_at=datetime.now() if order and order.filled_avg_price else None,
                        filled_qty=float(order.filled_qty) if order and order.filled_qty else None,
                        filled_avg_price=filled_price,
                    )
                    logger.info(f"✓ Trade logged to monitoring: {ticker} {action} {quantity}")
                except Exception as log_err:
                    logger.warning(f"Failed to log trade execution: {log_err}")
                
                # Record cooldown for this ticker
                self._record_cooldown(ticker)
                
                # Record trade with full context to TradeHistory (SINGLE SOURCE OF TRUTH)
                try:
                    if self.trade_history:
                        # Build agent signals dict - properly serialize to JSON-friendly format
                        agent_signals = self._serialize_agent_signals(analysis)
                        
                        # Get consensus info from serialized signals
                        bullish_count = 0
                        bearish_count = 0
                        neutral_count = 0
                        for agent_name, sig_data in agent_signals.items():
                            if isinstance(sig_data, dict):
                                sig = str(sig_data.get("signal", "")).lower()
                                if "bullish" in sig or "buy" in sig:
                                    bullish_count += 1
                                elif "bearish" in sig or "sell" in sig or "short" in sig:
                                    bearish_count += 1
                                else:
                                    neutral_count += 1
                        
                        # Create trade record with full context
                        trade_record = TradeRecord(
                            ticker=ticker,
                            action=action,
                            quantity=quantity,
                            entry_price=filled_price,
                            order_id=order_id,
                            trigger_source="automated",
                            workflow_mode="autonomous_trading",
                            strategy_name=signal.strategy if signal else None,
                            strategy_signal=signal.direction.value if signal and hasattr(signal.direction, 'value') else str(signal.direction) if signal else None,
                            strategy_confidence=signal.confidence if signal else None,
                            strategy_reasoning=signal.reasoning if signal else None,
                            mazo_sentiment=validation.mazo_sentiment if validation else None,
                            mazo_confidence=validation.mazo_confidence if validation else None,
                            mazo_response=validation.mazo_response if validation else None,
                            agent_signals=agent_signals,
                            consensus_direction="bullish" if bullish_count > bearish_count else "bearish" if bearish_count > bullish_count else "neutral",
                            consensus_confidence=pm_decision.get("confidence"),
                            bullish_count=bullish_count,
                            bearish_count=bearish_count,
                            neutral_count=neutral_count,
                            portfolio_equity=portfolio.equity if portfolio else None,
                            portfolio_cash=portfolio.cash if portfolio else None,
                            existing_positions=[{"ticker": p.ticker, "qty": p.quantity} for p in (portfolio.positions or [])] if portfolio else None,
                            pm_action=action,
                            pm_quantity=quantity,
                            pm_confidence=pm_decision.get("confidence"),
                            pm_reasoning=pm_decision.get("reasoning"),
                            pm_stop_loss_pct=pm_decision.get("stop_loss_pct"),
                            pm_take_profit_pct=pm_decision.get("take_profit_pct"),
                            stop_loss_price=pm_decision.get("stop_loss_price"),
                            take_profit_price=pm_decision.get("take_profit_price"),
                        )
                        
                        trade_id = self.trade_history.record_trade(trade_record)
                        if trade_id > 0:
                            logger.info(f"✓ Trade recorded to TradeHistory: ID {trade_id}")
                except Exception as hist_err:
                    logger.warning(f"Failed to record trade to TradeHistory: {hist_err}")
                
                # =============================================
                # SET POSITION RULES FOR POSITION MONITOR
                # =============================================
                # If PM specified stop_loss/take_profit, set them in the position monitor
                if action in ["buy", "short"]:  # Only for opening positions
                    try:
                        from src.trading.position_monitor import get_position_monitor
                        position_monitor = get_position_monitor()
                        
                        stop_loss_pct = pm_decision.get("stop_loss_pct")
                        take_profit_pct = pm_decision.get("take_profit_pct")
                        
                        if stop_loss_pct or take_profit_pct:
                            position_monitor.set_position_rules(
                                ticker=ticker,
                                stop_loss_pct=stop_loss_pct,
                                take_profit_pct=take_profit_pct
                            )
                            logger.info(f"✓ Set position rules for {ticker}: SL={stop_loss_pct}%, TP={take_profit_pct}%")
                    except Exception as pm_err:
                        logger.warning(f"Failed to set position rules: {pm_err}")
                
                return {
                    "success": True,
                    "action": action,
                    "quantity": quantity,
                    "order_id": order_id,
                    "filled_price": order.filled_avg_price if order else None,
                    "status": order.status if order else "submitted",
                    "message": result.message,
                }
            else:
                # Log failed trade execution
                try:
                    event_logger.log_trade_execution(
                        order_id=f"failed_{ticker}_{submitted_at.timestamp()}",
                        ticker=ticker,
                        side=side.value if hasattr(side, 'value') else str(side),
                        quantity=float(quantity),
                        order_type="market",
                        status="rejected",
                        submitted_at=submitted_at,
                        reject_reason=result.error if result else "Order submission failed",
                    )
                except Exception as log_err:
                    logger.warning(f"Failed to log rejected trade: {log_err}")
                
                return {
                    "success": False, 
                    "message": result.message if result else "Order submission failed",
                    "error": result.error if result else None,
                }
                
        except Exception as e:
            logger.error(f"Trade execution failed for {ticker}: {e}")
            return {"success": False, "message": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get current service status."""
        import os
        auto_enabled = os.getenv("AUTO_TRADING_ENABLED", "false").lower() == "true"
        return {
            "auto_trading_enabled": auto_enabled,
            "is_running": self.is_running,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "total_runs": len(self.run_history),
            "last_result": self.last_result.to_dict() if self.last_result else None,
        }
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent run history."""
        return [r.to_dict() for r in self.run_history[-limit:]]


# Global instance
_automated_trading_service: Optional[AutomatedTradingService] = None


def get_automated_trading_service() -> AutomatedTradingService:
    """Get the global automated trading service instance."""
    global _automated_trading_service
    if _automated_trading_service is None:
        _automated_trading_service = AutomatedTradingService()
    return _automated_trading_service
