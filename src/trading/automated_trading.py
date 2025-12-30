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
from src.graph.portfolio_context import build_portfolio_context, PortfolioContext
from integration.mazo_bridge import MazoBridge
from integration.unified_workflow import UnifiedWorkflow, execute_trades

logger = logging.getLogger(__name__)


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


@dataclass
class AnalysisResult:
    """Result from full AI analyst pipeline"""
    ticker: str
    analyst_signals: Dict[str, Any]
    consensus_direction: str
    consensus_confidence: float
    pm_decision: Dict[str, Any]
    reasoning: str


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
    
    # Configuration
    MIN_SIGNAL_CONFIDENCE = 60  # Minimum strategy confidence to proceed
    MAX_SIGNALS_PER_CYCLE = 5   # Max signals to process per cycle
    MAZO_VALIDATION_DEPTH = "quick"  # quick, standard, deep
    
    def __init__(self):
        self.strategy_engine = get_strategy_engine()
        self.alpaca = AlpacaService()
        self.performance_tracker = get_performance_tracker()
        self.mazo = MazoBridge()
        
        # Track state
        self.is_running = False
        self.last_run: Optional[datetime] = None
        self.last_result: Optional[AutomatedTradeResult] = None
        self.run_history: List[AutomatedTradeResult] = []
    
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
        start_time = datetime.now()
        self.is_running = True
        
        min_conf = min_confidence or self.MIN_SIGNAL_CONFIDENCE
        max_sig = max_signals or self.MAX_SIGNALS_PER_CYCLE
        
        result = AutomatedTradeResult(
            timestamp=start_time,
            tickers_screened=0,
            signals_found=0,
            mazo_validated=0,
            trades_analyzed=0,
            trades_executed=0,
            total_execution_time_ms=0,
        )
        
        try:
            # Get tickers to screen
            if not tickers:
                tickers = self._get_screening_universe()
            
            result.tickers_screened = len(tickers)
            logger.info(f"🔍 Starting trading cycle - Screening {len(tickers)} tickers")
            
            # =============================================
            # STEP 1: Strategy Engine Quick Screening
            # =============================================
            logger.info("📊 Step 1: Strategy Engine Screening...")
            signals = await self._run_strategy_screening(tickers, min_conf)
            result.signals_found = len(signals)
            
            if not signals:
                logger.info("No signals found above confidence threshold")
                self._finalize_result(result, start_time)
                return result
            
            logger.info(f"Found {len(signals)} signals above {min_conf}% confidence")
            
            # Take top signals
            top_signals = signals[:max_sig]
            
            # =============================================
            # STEP 2: Mazo Validation
            # =============================================
            logger.info("🔬 Step 2: Mazo Validation...")
            validated_signals = await self._run_mazo_validation(top_signals)
            result.mazo_validated = len(validated_signals)
            
            if not validated_signals:
                logger.info("No signals validated by Mazo")
                self._finalize_result(result, start_time)
                return result
            
            logger.info(f"Mazo validated {len(validated_signals)} signals")
            
            # =============================================
            # STEP 3: Full AI Analyst Pipeline
            # =============================================
            logger.info("🧠 Step 3: AI Analyst Deep Analysis...")
            
            # Get portfolio context for PM
            portfolio_context = build_portfolio_context()
            
            for signal, validation in validated_signals:
                try:
                    analysis = await self._run_full_analysis(
                        signal, 
                        validation, 
                        portfolio_context
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
                                    portfolio_context
                                )
                                
                                if trade_result.get("success"):
                                    result.trades_executed += 1
                                    
                                    # Track in performance tracker
                                    self.performance_tracker.record_trade(
                                        ticker=signal.ticker,
                                        action=action,
                                        quantity=analysis.pm_decision.get("quantity", 0),
                                        price=trade_result.get("filled_price", signal.entry_price),
                                        strategy=signal.strategy,
                                    )
                                
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
            
        finally:
            self._finalize_result(result, start_time)
            self.is_running = False
            
        return result
    
    def _finalize_result(self, result: AutomatedTradeResult, start_time: datetime):
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
    
    def _get_screening_universe(self) -> List[str]:
        """
        Build a dynamic screening universe based on:
        1. Current portfolio positions (must always monitor)
        2. User watchlist
        3. Diversified sector picks based on buying power
        4. Trending/momentum stocks from various sectors
        
        This ensures we're not hardcoded to specific tickers and 
        the system discovers opportunities across the market.
        """
        tickers = []
        
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
        
        # PRIORITY 3: Diversified sector picks based on buying power
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
                            # Check if affordable based on buying power
                            try:
                                quote = self.alpaca.get_quote(stock)
                                if quote and float(quote.ask_price) < buying_power * 0.1:
                                    tickers.append(stock)
                            except:
                                tickers.append(stock)  # Add anyway, will filter later
                        if len(tickers) >= 25:
                            break
                if len(tickers) >= 25:
                    break
        except Exception as e:
            logger.debug(f"Diversification scanner not available: {e}")
        
        # PRIORITY 4: If still need more, add market leaders by sector rotation
        # Rotate through sectors based on day of week for variety
        from datetime import datetime
        day_of_week = datetime.now().weekday()
        
        sector_rotation = {
            0: ["NVDA", "AMD", "AVGO", "QCOM"],  # Monday: Semiconductors
            1: ["JPM", "GS", "MS", "BAC"],        # Tuesday: Financials
            2: ["UNH", "JNJ", "PFE", "ABBV"],     # Wednesday: Healthcare
            3: ["XOM", "CVX", "COP", "SLB"],      # Thursday: Energy
            4: ["AMZN", "HD", "MCD", "NKE"],      # Friday: Consumer
        }
        
        rotation_tickers = sector_rotation.get(day_of_week, [])
        for ticker in rotation_tickers:
            if ticker not in tickers and len(tickers) < 30:
                tickers.append(ticker)
        
        # Log the universe
        logger.info(f"Screening universe: {len(tickers)} tickers from positions, watchlist, and sector rotation")
        
        return tickers[:25]  # Limit to 25 tickers per cycle for efficiency
    
    async def _run_strategy_screening(
        self, 
        tickers: List[str], 
        min_confidence: float
    ) -> List[TradingSignal]:
        """Run strategy engine screening on tickers."""
        all_signals = []
        
        for ticker in tickers:
            try:
                signals = self.strategy_engine.analyze_ticker(ticker)
                for signal in signals:
                    if signal.confidence >= min_confidence:
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
                # Run quick Mazo research
                direction_str = signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction)
                research = self.mazo.research(
                    f"Should I {direction_str} {signal.ticker}? Current price is ${signal.entry_price:.2f}. Give a quick buy/sell/hold recommendation."
                )
                
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
                    recommendation=research.answer[:200] + "..." if len(research.answer) > 200 else research.answer
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
        portfolio_context: PortfolioContext
    ) -> Optional[AnalysisResult]:
        """Run full AI analyst pipeline."""
        try:
            # Create workflow
            workflow = UnifiedWorkflow()

            # Run the hedge fund analysis pipeline
            # This will run all AI agents and PM
            results = workflow.analyze(
                tickers=[signal.ticker],
                mode="signal",  # Just get signals from agents
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
            
            if hasattr(result, 'hedge_fund') and result.hedge_fund:
                agent_signals = result.hedge_fund.get("analyst_signals", {})
                
                # Calculate consensus
                bullish_count = 0
                bearish_count = 0
                total_confidence = 0
                
                for ticker_data in agent_signals.values():
                    for agent_name, agent_signal in ticker_data.items():
                        if isinstance(agent_signal, dict):
                            sig = agent_signal.get("signal", "").lower()
                            conf = agent_signal.get("confidence", 50)
                            
                            if "bullish" in sig or "buy" in sig:
                                bullish_count += 1
                                total_confidence += conf
                            elif "bearish" in sig or "sell" in sig or "short" in sig:
                                bearish_count += 1
                                total_confidence += conf
                
                total = bullish_count + bearish_count
                if total > 0:
                    if bullish_count > bearish_count:
                        consensus_direction = "bullish"
                    elif bearish_count > bullish_count:
                        consensus_direction = "bearish"
                    consensus_confidence = total_confidence / total
            
            return AnalysisResult(
                ticker=signal.ticker,
                analyst_signals=agent_signals,
                consensus_direction=consensus_direction,
                consensus_confidence=consensus_confidence,
                pm_decision=pm_decision or {},
                reasoning=result.portfolio_manager_reasoning if hasattr(result, 'portfolio_manager_reasoning') else ""
            )
            
        except Exception as e:
            logger.error(f"Full analysis failed for {signal.ticker}: {e}")
            
            # Fallback: Use strategy signal directly for PM decision
            # This allows trading even if full pipeline fails
            direction_value = signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction)
            action = "buy" if direction_value == "long" else "short"
            
            return AnalysisResult(
                ticker=signal.ticker,
                analyst_signals={},
                consensus_direction=direction_value,
                consensus_confidence=signal.confidence,
                pm_decision={
                    "action": action,
                    "quantity": self._calculate_position_size(signal, portfolio_context),
                    "confidence": signal.confidence,
                    "reasoning": f"Strategy: {signal.strategy} | {signal.reasoning}",
                    "stop_loss_pct": 5,
                    "take_profit_pct": 10,
                },
                reasoning=f"Fallback: {signal.reasoning}"
            )
    
    def _calculate_position_size(
        self, 
        signal: TradingSignal, 
        portfolio: PortfolioContext
    ) -> int:
        """Calculate position size based on signal and portfolio."""
        # Use signal's suggested size or default to 5%
        position_pct = signal.position_size_pct or 0.05
        
        # Calculate dollar amount
        available = min(portfolio.cash, portfolio.buying_power)
        position_value = available * position_pct
        
        # Convert to shares
        if signal.entry_price and signal.entry_price > 0:
            shares = int(position_value / signal.entry_price)
            return max(1, shares)  # At least 1 share
        
        return 1
    
    async def _execute_trade(
        self,
        ticker: str,
        pm_decision: Dict[str, Any],
        portfolio: PortfolioContext
    ) -> Dict[str, Any]:
        """Execute trade via Alpaca directly."""
        try:
            from src.trading.alpaca_service import OrderSide, OrderType, TimeInForce
            
            action = pm_decision.get("action", "hold")
            quantity = pm_decision.get("quantity", 0)
            
            if action == "hold" or quantity == 0:
                return {"success": True, "message": "No trade needed (hold)"}
            
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
                return {
                    "success": True,
                    "action": action,
                    "quantity": quantity,
                    "order_id": order.id if order else None,
                    "filled_price": order.filled_avg_price if order else None,
                    "status": order.status if order else "submitted",
                    "message": result.message,
                }
            else:
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
        return {
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
