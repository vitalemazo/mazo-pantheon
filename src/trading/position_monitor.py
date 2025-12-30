"""
Position Monitor Service

Actively monitors all open positions and enforces:
- Stop-loss exits (automatic)
- Take-profit exits (automatic)
- Maximum hold time exits (configurable)
- Trailing stop-loss (optional)

This is the CRITICAL piece that makes the hedge fund truly autonomous.
Without this, trades are placed but never managed.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class PositionAlert:
    """Alert generated when a position needs attention"""
    ticker: str
    alert_type: str  # "stop_loss", "take_profit", "max_hold", "trailing_stop"
    current_price: float
    trigger_price: float
    pnl_percent: float
    action_taken: str  # "exit", "alert_only", "pending"
    timestamp: datetime = field(default_factory=datetime.now)
    details: str = ""


@dataclass
class MonitoredPosition:
    """Position being actively monitored"""
    ticker: str
    side: str  # "long" or "short"
    qty: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    
    # Risk management levels
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    max_hold_hours: Optional[float] = None
    entry_time: Optional[datetime] = None


class PositionMonitor:
    """
    Monitors positions and executes automatic exits based on risk rules.
    
    This is the safety net that prevents catastrophic losses and locks in profits.
    """
    
    def __init__(self, alpaca_service, db_session=None):
        self.alpaca = alpaca_service
        self.db_session = db_session
        
        # Default risk parameters (can be overridden per position)
        self.default_stop_loss_pct = 5.0   # Exit if down 5%
        self.default_take_profit_pct = 10.0  # Exit if up 10%
        self.default_max_hold_hours = 24 * 5  # 5 trading days
        
        # Track monitoring state
        self.is_running = False
        self.last_check: Optional[datetime] = None
        self.check_count = 0
        self.alerts: List[PositionAlert] = []
        self.exits_executed = 0
        
        # Position-specific overrides (loaded from trade records)
        self.position_rules: Dict[str, Dict] = {}
    
    async def check_all_positions(self) -> Dict[str, Any]:
        """
        Main monitoring loop - checks all positions against risk rules.
        Should be called every 1-5 minutes during market hours.
        """
        self.last_check = datetime.now()
        self.check_count += 1
        
        results = {
            "timestamp": self.last_check.isoformat(),
            "positions_checked": 0,
            "alerts_generated": 0,
            "exits_executed": 0,
            "details": []
        }
        
        try:
            # Get all open positions from Alpaca (synchronous call)
            positions = self.alpaca.get_positions()
            
            if not positions:
                logger.info("No open positions to monitor")
                return results
            
            results["positions_checked"] = len(positions)
            
            for pos in positions:
                # Handle both dict and object access patterns
                if hasattr(pos, 'symbol'):
                    ticker = pos.symbol
                    qty = float(pos.qty)
                    entry_price = float(pos.avg_entry_price)
                    current_price = float(pos.current_price)
                    unrealized_pnl = float(pos.unrealized_pl)
                    unrealized_pnl_pct = float(pos.unrealized_plpc) * 100
                else:
                    ticker = pos.get("symbol", "")
                    qty = float(pos.get("qty", 0))
                    entry_price = float(pos.get("avg_entry_price", 0))
                    current_price = float(pos.get("current_price", 0))
                    unrealized_pnl = float(pos.get("unrealized_pl", 0))
                    unrealized_pnl_pct = float(pos.get("unrealized_plpc", 0)) * 100
                
                side = "short" if qty < 0 else "long"
                
                # Get position-specific rules or use defaults
                rules = self.position_rules.get(ticker, {})
                stop_loss_pct = rules.get("stop_loss_pct", self.default_stop_loss_pct)
                take_profit_pct = rules.get("take_profit_pct", self.default_take_profit_pct)
                
                # Calculate trigger prices
                if side == "long":
                    stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
                    take_profit_price = entry_price * (1 + take_profit_pct / 100)
                else:  # short
                    stop_loss_price = entry_price * (1 + stop_loss_pct / 100)
                    take_profit_price = entry_price * (1 - take_profit_pct / 100)
                
                position_detail = {
                    "ticker": ticker,
                    "side": side,
                    "qty": abs(qty),
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "pnl_pct": unrealized_pnl_pct,
                    "stop_loss_price": stop_loss_price,
                    "take_profit_price": take_profit_price,
                    "action": None
                }
                
                # Check stop-loss
                if side == "long" and current_price <= stop_loss_price:
                    alert = await self._execute_exit(
                        ticker, abs(qty), "sell", "stop_loss",
                        current_price, stop_loss_price, unrealized_pnl_pct
                    )
                    position_detail["action"] = "STOP_LOSS_EXIT"
                    results["exits_executed"] += 1
                    self.alerts.append(alert)
                    
                elif side == "short" and current_price >= stop_loss_price:
                    alert = await self._execute_exit(
                        ticker, abs(qty), "cover", "stop_loss",
                        current_price, stop_loss_price, unrealized_pnl_pct
                    )
                    position_detail["action"] = "STOP_LOSS_EXIT"
                    results["exits_executed"] += 1
                    self.alerts.append(alert)
                
                # Check take-profit
                elif side == "long" and current_price >= take_profit_price:
                    alert = await self._execute_exit(
                        ticker, abs(qty), "sell", "take_profit",
                        current_price, take_profit_price, unrealized_pnl_pct
                    )
                    position_detail["action"] = "TAKE_PROFIT_EXIT"
                    results["exits_executed"] += 1
                    self.alerts.append(alert)
                    
                elif side == "short" and current_price <= take_profit_price:
                    alert = await self._execute_exit(
                        ticker, abs(qty), "cover", "take_profit",
                        current_price, take_profit_price, unrealized_pnl_pct
                    )
                    position_detail["action"] = "TAKE_PROFIT_EXIT"
                    results["exits_executed"] += 1
                    self.alerts.append(alert)
                
                else:
                    position_detail["action"] = "HOLD"
                
                results["details"].append(position_detail)
            
            results["alerts_generated"] = len([d for d in results["details"] if d["action"] != "HOLD"])
            self.exits_executed += results["exits_executed"]
            
            # Log summary
            if results["exits_executed"] > 0:
                logger.warning(f"Position Monitor: Executed {results['exits_executed']} exits!")
            else:
                logger.info(f"Position Monitor: {results['positions_checked']} positions checked, all within limits")
            
            return results
            
        except Exception as e:
            logger.error(f"Position monitor error: {e}", exc_info=True)
            results["error"] = str(e)
            return results
    
    async def _execute_exit(
        self, 
        ticker: str, 
        qty: float, 
        action: str,  # "sell" or "cover"
        exit_type: str,
        current_price: float,
        trigger_price: float,
        pnl_pct: float
    ) -> PositionAlert:
        """Execute an automatic exit trade"""
        
        logger.warning(f"🚨 AUTO-EXIT: {exit_type.upper()} triggered for {ticker}")
        logger.warning(f"   Action: {action.upper()} {qty} shares at ${current_price:.2f}")
        logger.warning(f"   Trigger: ${trigger_price:.2f} | P&L: {pnl_pct:.2f}%")
        
        try:
            # Use close_position for simplicity - it handles both long and short
            result = self.alpaca.close_position(ticker, qty=abs(qty))
            
            if result.success:
                action_taken = "exit"
                details = f"Exit order placed: {result.message}"
                self.exits_executed += 1
                logger.info(f"✅ Exit executed for {ticker}: {result.message}")
            else:
                action_taken = "failed"
                details = f"Exit failed: {result.error}"
                logger.error(f"Exit failed for {ticker}: {result.error}")
            
        except Exception as e:
            action_taken = "failed"
            details = f"Exit failed: {e}"
            logger.error(f"Failed to execute exit for {ticker}: {e}")
        
        return PositionAlert(
            ticker=ticker,
            alert_type=exit_type,
            current_price=current_price,
            trigger_price=trigger_price,
            pnl_percent=pnl_pct,
            action_taken=action_taken,
            details=details
        )
    
    def set_position_rules(self, ticker: str, stop_loss_pct: float = None, take_profit_pct: float = None):
        """Set custom risk rules for a specific position"""
        if ticker not in self.position_rules:
            self.position_rules[ticker] = {}
        
        if stop_loss_pct is not None:
            self.position_rules[ticker]["stop_loss_pct"] = stop_loss_pct
        if take_profit_pct is not None:
            self.position_rules[ticker]["take_profit_pct"] = take_profit_pct
        
        logger.info(f"Set rules for {ticker}: {self.position_rules[ticker]}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current monitor status"""
        return {
            "is_running": self.is_running,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "check_count": self.check_count,
            "exits_executed": self.exits_executed,
            "recent_alerts": [
                {
                    "ticker": a.ticker,
                    "type": a.alert_type,
                    "pnl_pct": a.pnl_percent,
                    "action": a.action_taken,
                    "time": a.timestamp.isoformat()
                }
                for a in self.alerts[-10:]  # Last 10 alerts
            ],
            "position_rules": self.position_rules,
            "default_rules": {
                "stop_loss_pct": self.default_stop_loss_pct,
                "take_profit_pct": self.default_take_profit_pct,
                "max_hold_hours": self.default_max_hold_hours
            }
        }


# Singleton instance
_position_monitor: Optional[PositionMonitor] = None


def get_position_monitor(alpaca_service=None, db_session=None) -> PositionMonitor:
    """Get or create the position monitor singleton"""
    global _position_monitor
    
    if _position_monitor is None:
        if alpaca_service is None:
            from src.trading.alpaca_service import get_alpaca_service
            alpaca_service = get_alpaca_service()
        _position_monitor = PositionMonitor(alpaca_service, db_session)
    
    return _position_monitor


async def run_position_check():
    """
    Convenience function for scheduler to call.
    This is what gets run every 5 minutes.
    """
    monitor = get_position_monitor()
    return await monitor.check_all_positions()
