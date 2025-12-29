"""
Performance Tracking Service

Tracks and analyzes trading performance including:
- P&L tracking
- Win rate calculation
- Trade history
- Daily/weekly/monthly reports
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from collections import defaultdict

from src.trading.alpaca_service import AlpacaService

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """A completed trade record"""
    id: int
    ticker: str
    action: str  # buy, sell, short, cover
    quantity: float
    entry_price: float
    exit_price: Optional[float]
    entry_time: datetime
    exit_time: Optional[datetime]
    strategy: Optional[str]
    realized_pnl: Optional[float]
    return_pct: Optional[float]
    holding_period_hours: Optional[float]
    status: str  # open, closed
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "action": self.action,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "strategy": self.strategy,
            "realized_pnl": self.realized_pnl,
            "return_pct": self.return_pct,
            "holding_period_hours": self.holding_period_hours,
            "status": self.status,
        }


@dataclass  
class DailySnapshot:
    """Daily performance snapshot"""
    date: date
    starting_equity: float
    ending_equity: float
    high_equity: float
    low_equity: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    return_pct: float
    trades_count: int
    winning_trades: int
    losing_trades: int
    win_rate: Optional[float]
    biggest_winner: Optional[float]
    biggest_winner_ticker: Optional[str]
    biggest_loser: Optional[float]
    biggest_loser_ticker: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "starting_equity": self.starting_equity,
            "ending_equity": self.ending_equity,
            "high_equity": self.high_equity,
            "low_equity": self.low_equity,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_pnl": self.total_pnl,
            "return_pct": self.return_pct,
            "trades_count": self.trades_count,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "biggest_winner": self.biggest_winner,
            "biggest_winner_ticker": self.biggest_winner_ticker,
            "biggest_loser": self.biggest_loser,
            "biggest_loser_ticker": self.biggest_loser_ticker,
        }


class PerformanceTracker:
    """
    Tracks and analyzes trading performance.
    
    Features:
    - Real-time P&L from Alpaca
    - Trade history tracking
    - Win rate and metrics calculation
    - Daily/weekly/monthly reports
    """
    
    def __init__(self):
        self.alpaca = AlpacaService()
        
        # In-memory storage (will move to DB)
        self._trades: List[TradeRecord] = []
        self._daily_snapshots: List[DailySnapshot] = []
        self._next_trade_id = 1
        
        # Starting equity (set on first call)
        self._starting_equity: Optional[float] = None
    
    def get_current_performance(self) -> Dict[str, Any]:
        """
        Get current portfolio performance metrics.
        
        Returns real-time data from Alpaca.
        """
        try:
            account = self.alpaca.get_account()
            positions = self.alpaca.get_positions()
            
            if not account:
                return {"error": "Could not fetch account"}
            
            equity = float(account.equity)
            cash = float(account.cash)
            buying_power = float(account.buying_power)
            
            # Calculate total P&L
            total_unrealized = sum(
                float(p.unrealized_pl) for p in positions
            ) if positions else 0
            
            # Calculate by position
            position_pnl = []
            for pos in (positions or []):
                pnl = float(pos.unrealized_pl)
                pnl_pct = float(pos.unrealized_plpc) * 100
                position_pnl.append({
                    "ticker": pos.symbol,
                    "qty": float(pos.qty),
                    "side": "long" if float(pos.qty) > 0 else "short",
                    "entry_price": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value),
                    "unrealized_pnl": pnl,
                    "unrealized_pnl_pct": pnl_pct,
                })
            
            # Sort by P&L
            position_pnl.sort(key=lambda x: x["unrealized_pnl"], reverse=True)
            
            # Day's performance (from account)
            day_pnl = equity - float(account.last_equity) if hasattr(account, 'last_equity') else 0
            day_pnl_pct = (day_pnl / float(account.last_equity) * 100) if hasattr(account, 'last_equity') and float(account.last_equity) > 0 else 0
            
            return {
                "timestamp": datetime.now().isoformat(),
                "equity": equity,
                "cash": cash,
                "buying_power": buying_power,
                "day_pnl": round(day_pnl, 2),
                "day_pnl_pct": round(day_pnl_pct, 2),
                "total_unrealized_pnl": round(total_unrealized, 2),
                "positions_count": len(positions) if positions else 0,
                "positions": position_pnl,
                "best_position": position_pnl[0] if position_pnl else None,
                "worst_position": position_pnl[-1] if position_pnl else None,
            }
            
        except Exception as e:
            logger.error(f"Error getting performance: {e}")
            return {"error": str(e)}
    
    def record_trade(
        self,
        ticker: str,
        action: str,
        quantity: float,
        price: float,
        strategy: Optional[str] = None
    ) -> TradeRecord:
        """
        Record a new trade entry.
        
        Args:
            ticker: Stock ticker
            action: buy, sell, short, cover
            quantity: Number of shares
            price: Entry price
            strategy: Strategy used
            
        Returns:
            Created TradeRecord
        """
        trade = TradeRecord(
            id=self._next_trade_id,
            ticker=ticker.upper(),
            action=action,
            quantity=quantity,
            entry_price=price,
            exit_price=None,
            entry_time=datetime.now(),
            exit_time=None,
            strategy=strategy,
            realized_pnl=None,
            return_pct=None,
            holding_period_hours=None,
            status="open",
        )
        
        self._trades.append(trade)
        self._next_trade_id += 1
        
        logger.info(f"Recorded trade: {action} {quantity} {ticker} @ ${price:.2f}")
        return trade
    
    def close_trade(
        self,
        trade_id: int,
        exit_price: float
    ) -> Optional[TradeRecord]:
        """
        Close a trade and calculate P&L.
        
        Args:
            trade_id: ID of trade to close
            exit_price: Exit price
            
        Returns:
            Updated TradeRecord
        """
        for trade in self._trades:
            if trade.id == trade_id and trade.status == "open":
                trade.exit_price = exit_price
                trade.exit_time = datetime.now()
                trade.status = "closed"
                
                # Calculate P&L
                if trade.action in ["buy", "cover"]:
                    trade.realized_pnl = (exit_price - trade.entry_price) * trade.quantity
                else:  # sell, short
                    trade.realized_pnl = (trade.entry_price - exit_price) * trade.quantity
                
                trade.return_pct = (trade.realized_pnl / (trade.entry_price * trade.quantity)) * 100
                
                # Calculate holding period
                if trade.entry_time and trade.exit_time:
                    delta = trade.exit_time - trade.entry_time
                    trade.holding_period_hours = delta.total_seconds() / 3600
                
                logger.info(f"Closed trade {trade_id}: P&L ${trade.realized_pnl:.2f} ({trade.return_pct:.1f}%)")
                return trade
        
        return None
    
    def get_trade_history(
        self,
        limit: int = 50,
        status: Optional[str] = None,
        ticker: Optional[str] = None
    ) -> List[TradeRecord]:
        """
        Get trade history with optional filters.
        
        Args:
            limit: Max trades to return
            status: Filter by status (open, closed)
            ticker: Filter by ticker
        """
        trades = self._trades
        
        if status:
            trades = [t for t in trades if t.status == status]
        if ticker:
            trades = [t for t in trades if t.ticker == ticker.upper()]
        
        # Sort by time descending
        trades.sort(key=lambda x: x.entry_time, reverse=True)
        
        return trades[:limit]
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Calculate overall trading metrics.
        
        Returns win rate, average return, etc.
        """
        closed_trades = [t for t in self._trades if t.status == "closed"]
        
        if not closed_trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": None,
                "total_pnl": 0,
                "average_pnl": None,
                "average_return_pct": None,
                "biggest_winner": None,
                "biggest_loser": None,
                "profit_factor": None,
                "average_holding_hours": None,
            }
        
        winning = [t for t in closed_trades if t.realized_pnl and t.realized_pnl > 0]
        losing = [t for t in closed_trades if t.realized_pnl and t.realized_pnl < 0]
        
        total_pnl = sum(t.realized_pnl for t in closed_trades if t.realized_pnl)
        
        # Win rate
        win_rate = len(winning) / len(closed_trades) * 100 if closed_trades else 0
        
        # Average P&L
        avg_pnl = total_pnl / len(closed_trades) if closed_trades else 0
        
        # Average return %
        returns = [t.return_pct for t in closed_trades if t.return_pct]
        avg_return = sum(returns) / len(returns) if returns else 0
        
        # Biggest winner/loser
        biggest_winner = max(closed_trades, key=lambda t: t.realized_pnl or 0) if closed_trades else None
        biggest_loser = min(closed_trades, key=lambda t: t.realized_pnl or 0) if closed_trades else None
        
        # Profit factor (gross wins / gross losses)
        gross_wins = sum(t.realized_pnl for t in winning if t.realized_pnl)
        gross_losses = abs(sum(t.realized_pnl for t in losing if t.realized_pnl))
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else None
        
        # Average holding period
        holding_hours = [t.holding_period_hours for t in closed_trades if t.holding_period_hours]
        avg_holding = sum(holding_hours) / len(holding_hours) if holding_hours else None
        
        return {
            "total_trades": len(closed_trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "average_pnl": round(avg_pnl, 2),
            "average_return_pct": round(avg_return, 2),
            "biggest_winner": {
                "ticker": biggest_winner.ticker,
                "pnl": biggest_winner.realized_pnl,
                "return_pct": biggest_winner.return_pct,
            } if biggest_winner and biggest_winner.realized_pnl else None,
            "biggest_loser": {
                "ticker": biggest_loser.ticker,
                "pnl": biggest_loser.realized_pnl,
                "return_pct": biggest_loser.return_pct,
            } if biggest_loser and biggest_loser.realized_pnl else None,
            "profit_factor": round(profit_factor, 2) if profit_factor else None,
            "average_holding_hours": round(avg_holding, 1) if avg_holding else None,
        }
    
    def get_metrics_by_strategy(self) -> Dict[str, Dict[str, Any]]:
        """Get performance metrics broken down by strategy."""
        closed_trades = [t for t in self._trades if t.status == "closed"]
        
        by_strategy = defaultdict(list)
        for trade in closed_trades:
            strategy = trade.strategy or "unknown"
            by_strategy[strategy].append(trade)
        
        results = {}
        for strategy, trades in by_strategy.items():
            winning = [t for t in trades if t.realized_pnl and t.realized_pnl > 0]
            total_pnl = sum(t.realized_pnl for t in trades if t.realized_pnl)
            
            results[strategy] = {
                "total_trades": len(trades),
                "winning_trades": len(winning),
                "win_rate": round(len(winning) / len(trades) * 100, 1) if trades else 0,
                "total_pnl": round(total_pnl, 2),
                "average_pnl": round(total_pnl / len(trades), 2) if trades else 0,
            }
        
        return results
    
    def create_daily_snapshot(self) -> DailySnapshot:
        """
        Create a daily performance snapshot.
        
        Call this at end of trading day.
        """
        today = date.today()
        perf = self.get_current_performance()
        
        if "error" in perf:
            raise Exception(perf["error"])
        
        # Get today's trades
        today_trades = [
            t for t in self._trades
            if t.entry_time.date() == today
        ]
        
        winning = [t for t in today_trades if t.status == "closed" and t.realized_pnl and t.realized_pnl > 0]
        losing = [t for t in today_trades if t.status == "closed" and t.realized_pnl and t.realized_pnl < 0]
        
        # Find biggest winner/loser
        closed_today = [t for t in today_trades if t.status == "closed"]
        biggest_winner = max(closed_today, key=lambda t: t.realized_pnl or 0) if closed_today else None
        biggest_loser = min(closed_today, key=lambda t: t.realized_pnl or 0) if closed_today else None
        
        snapshot = DailySnapshot(
            date=today,
            starting_equity=self._starting_equity or perf["equity"],
            ending_equity=perf["equity"],
            high_equity=perf["equity"],  # Would track throughout day
            low_equity=perf["equity"],  # Would track throughout day
            realized_pnl=sum(t.realized_pnl for t in closed_today if t.realized_pnl) or 0,
            unrealized_pnl=perf.get("total_unrealized_pnl", 0),
            total_pnl=perf.get("day_pnl", 0),
            return_pct=perf.get("day_pnl_pct", 0),
            trades_count=len(today_trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=len(winning) / len(closed_today) * 100 if closed_today else None,
            biggest_winner=biggest_winner.realized_pnl if biggest_winner else None,
            biggest_winner_ticker=biggest_winner.ticker if biggest_winner else None,
            biggest_loser=biggest_loser.realized_pnl if biggest_loser else None,
            biggest_loser_ticker=biggest_loser.ticker if biggest_loser else None,
        )
        
        self._daily_snapshots.append(snapshot)
        logger.info(f"Created daily snapshot for {today}: P&L ${snapshot.total_pnl:.2f}")
        
        return snapshot
    
    def get_daily_snapshots(self, days: int = 30) -> List[DailySnapshot]:
        """Get recent daily snapshots."""
        cutoff = date.today() - timedelta(days=days)
        return [s for s in self._daily_snapshots if s.date >= cutoff]
    
    def get_summary_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive performance summary.
        
        Includes current state, metrics, and recent history.
        """
        current = self.get_current_performance()
        metrics = self.get_metrics()
        by_strategy = self.get_metrics_by_strategy()
        recent_trades = self.get_trade_history(limit=10)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "current_portfolio": current,
            "overall_metrics": metrics,
            "by_strategy": by_strategy,
            "recent_trades": [t.to_dict() for t in recent_trades],
            "open_positions_count": current.get("positions_count", 0),
            "total_realized_pnl": metrics.get("total_pnl", 0),
            "win_rate": metrics.get("win_rate"),
        }


# Global tracker instance
_tracker: Optional[PerformanceTracker] = None


def get_performance_tracker() -> PerformanceTracker:
    """Get the global performance tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = PerformanceTracker()
    return _tracker
