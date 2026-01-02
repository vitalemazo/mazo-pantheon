"""
Performance Tracking Service

Tracks and analyzes trading performance including:
- P&L tracking
- Win rate calculation
- Trade history
- Daily/weekly/monthly reports

Now persists to PostgreSQL via SQLAlchemy for durability across restarts.
"""

import logging
from datetime import datetime, timedelta, date, timezone
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from collections import defaultdict

from src.trading.alpaca_service import AlpacaService

logger = logging.getLogger(__name__)


def _get_db_session():
    """Get a database session."""
    try:
        from app.backend.database.connection import SessionLocal
        return SessionLocal()
    except Exception as e:
        logger.warning(f"Could not create DB session: {e}")
        return None


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
            "date": self.date.isoformat() if isinstance(self.date, date) else str(self.date),
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
    Tracks and analyzes trading performance with database persistence.
    
    Features:
    - Real-time P&L from Alpaca
    - Trade history tracking (persisted to TradeHistory table)
    - Win rate and metrics calculation
    - Daily/weekly/monthly reports (persisted to DailyPerformance table)
    """
    
    def __init__(self, db_session=None):
        self.alpaca = AlpacaService()
        self._db_session = db_session
        
        # Starting equity (set on first call)
        self._starting_equity: Optional[float] = None
    
    def _get_session(self):
        """Get or create a database session."""
        if self._db_session:
            return self._db_session
        return _get_db_session()
    
    def _close_session(self, session):
        """Close session if we created it."""
        if session and session != self._db_session:
            session.close()
    
    def _db_trade_to_record(self, db_trade) -> TradeRecord:
        """Convert database TradeHistory row to TradeRecord."""
        return TradeRecord(
            id=db_trade.id,
            ticker=db_trade.ticker,
            action=db_trade.action or "unknown",
            quantity=db_trade.quantity or 0,
            entry_price=db_trade.entry_price or 0,
            exit_price=db_trade.exit_price,
            entry_time=db_trade.entry_time or db_trade.created_at,
            exit_time=db_trade.exit_time,
            strategy=db_trade.strategy,
            realized_pnl=db_trade.realized_pnl,
            return_pct=db_trade.return_pct,
            holding_period_hours=db_trade.holding_period_hours,
            status=db_trade.status or "pending",
        )
    
    def _db_snapshot_to_dataclass(self, db_snapshot) -> DailySnapshot:
        """Convert database DailyPerformance row to DailySnapshot."""
        snapshot_date = db_snapshot.date
        if isinstance(snapshot_date, datetime):
            snapshot_date = snapshot_date.date()
        
        return DailySnapshot(
            date=snapshot_date,
            starting_equity=db_snapshot.starting_equity or 0,
            ending_equity=db_snapshot.ending_equity or 0,
            high_equity=db_snapshot.high_equity or 0,
            low_equity=db_snapshot.low_equity or 0,
            realized_pnl=db_snapshot.realized_pnl or 0,
            unrealized_pnl=db_snapshot.unrealized_pnl or 0,
            total_pnl=db_snapshot.total_pnl or 0,
            return_pct=db_snapshot.return_pct or 0,
            trades_count=db_snapshot.trades_count or 0,
            winning_trades=db_snapshot.winning_trades or 0,
            losing_trades=db_snapshot.losing_trades or 0,
            win_rate=db_snapshot.win_rate,
            biggest_winner=db_snapshot.biggest_winner,
            biggest_winner_ticker=db_snapshot.biggest_winner_ticker,
            biggest_loser=db_snapshot.biggest_loser,
            biggest_loser_ticker=db_snapshot.biggest_loser_ticker,
        )
    
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
        strategy: Optional[str] = None,
        order_id: Optional[str] = None
    ) -> Optional[TradeRecord]:
        """
        Record a new trade entry (persisted to database).
        
        Args:
            ticker: Stock ticker
            action: buy, sell, short, cover
            quantity: Number of shares
            price: Entry price
            strategy: Strategy used
            order_id: Alpaca order ID
            
        Returns:
            Created TradeRecord or None on failure
        """
        session = self._get_session()
        if not session:
            logger.warning("No database session - trade not persisted")
            return None
        
        try:
            from app.backend.database.models import TradeHistory
            
            db_trade = TradeHistory(
                order_id=order_id,
                ticker=ticker.upper(),
                action=action,
                quantity=quantity,
                entry_price=price,
                entry_time=datetime.now(timezone.utc),
                strategy=strategy,
                status="pending",
            )
            
            session.add(db_trade)
            session.commit()
            session.refresh(db_trade)
            
            trade = self._db_trade_to_record(db_trade)
            logger.info(f"Recorded trade: {action} {quantity} {ticker} @ ${price:.2f} (ID: {trade.id})")
            return trade
            
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
            session.rollback()
            return None
        finally:
            self._close_session(session)
    
    def close_trade(
        self,
        trade_id: int,
        exit_price: float
    ) -> Optional[TradeRecord]:
        """
        Close a trade and calculate P&L (persisted to database).
        
        Args:
            trade_id: ID of trade to close
            exit_price: Exit price
            
        Returns:
            Updated TradeRecord or None on failure
        """
        session = self._get_session()
        if not session:
            return None
        
        try:
            from app.backend.database.models import TradeHistory
            
            db_trade = session.query(TradeHistory).filter_by(id=trade_id).first()
            if not db_trade or db_trade.status == "closed":
                return None
            
            db_trade.exit_price = exit_price
            db_trade.exit_time = datetime.now(timezone.utc)
            db_trade.status = "closed"
            
            # Calculate P&L
            if db_trade.action in ["buy", "cover"]:
                db_trade.realized_pnl = (exit_price - db_trade.entry_price) * db_trade.quantity
            else:  # sell, short
                db_trade.realized_pnl = (db_trade.entry_price - exit_price) * db_trade.quantity
            
            if db_trade.entry_price and db_trade.entry_price > 0:
                db_trade.return_pct = (db_trade.realized_pnl / (db_trade.entry_price * db_trade.quantity)) * 100
            
            # Calculate holding period
            if db_trade.entry_time and db_trade.exit_time:
                delta = db_trade.exit_time - db_trade.entry_time
                db_trade.holding_period_hours = delta.total_seconds() / 3600
            
            session.commit()
            session.refresh(db_trade)
            
            trade = self._db_trade_to_record(db_trade)
            logger.info(f"Closed trade {trade_id}: P&L ${trade.realized_pnl:.2f} ({trade.return_pct:.1f}%)")
            return trade
            
        except Exception as e:
            logger.error(f"Failed to close trade: {e}")
            session.rollback()
            return None
        finally:
            self._close_session(session)
    
    def get_trade_history(
        self,
        limit: int = 50,
        status: Optional[str] = None,
        ticker: Optional[str] = None
    ) -> List[TradeRecord]:
        """
        Get trade history from database with optional filters.
        
        Args:
            limit: Max trades to return
            status: Filter by status (pending, filled, closed)
            ticker: Filter by ticker
        """
        session = self._get_session()
        if not session:
            return []
        
        try:
            from app.backend.database.models import TradeHistory
            
            query = session.query(TradeHistory)
            
            if status:
                query = query.filter(TradeHistory.status == status)
            if ticker:
                query = query.filter(TradeHistory.ticker == ticker.upper())
            
            # Sort by time descending
            query = query.order_by(TradeHistory.created_at.desc())
            
            trades = [self._db_trade_to_record(t) for t in query.limit(limit).all()]
            return trades
            
        except Exception as e:
            logger.error(f"Failed to get trade history: {e}")
            return []
        finally:
            self._close_session(session)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Calculate overall trading metrics from database.
        
        Returns win rate, average return, etc.
        """
        session = self._get_session()
        if not session:
            return {"total_trades": 0, "error": "No database session"}
        
        try:
            from app.backend.database.models import TradeHistory
            
            closed_trades = session.query(TradeHistory).filter(
                TradeHistory.status == "closed"
            ).all()
            
            if not closed_trades:
                return {
                    "has_data": False,
                    "message": "No closed trades yet — run an AI trading cycle or wait for positions to close to populate metrics.",
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
            
            winning = [t for t in closed_trades if (t.realized_pnl or 0) > 0]
            losing = [t for t in closed_trades if (t.realized_pnl or 0) < 0]
            
            total_pnl = sum(t.realized_pnl or 0 for t in closed_trades)
            
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
                "has_data": True,
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
            
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {"total_trades": 0, "error": str(e)}
        finally:
            self._close_session(session)
    
    def get_metrics_by_strategy(self) -> Dict[str, Dict[str, Any]]:
        """Get performance metrics broken down by strategy from database."""
        session = self._get_session()
        if not session:
            return {}
        
        try:
            from app.backend.database.models import TradeHistory
            
            closed_trades = session.query(TradeHistory).filter(
                TradeHistory.status == "closed"
            ).all()
            
            by_strategy = defaultdict(list)
            for trade in closed_trades:
                strategy = trade.strategy or "unknown"
                by_strategy[strategy].append(trade)
            
            results = {}
            for strategy, trades in by_strategy.items():
                winning = [t for t in trades if (t.realized_pnl or 0) > 0]
                total_pnl = sum(t.realized_pnl or 0 for t in trades)
                
                results[strategy] = {
                    "total_trades": len(trades),
                    "winning_trades": len(winning),
                    "win_rate": round(len(winning) / len(trades) * 100, 1) if trades else 0,
                    "total_pnl": round(total_pnl, 2),
                    "average_pnl": round(total_pnl / len(trades), 2) if trades else 0,
                }
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get metrics by strategy: {e}")
            return {}
        finally:
            self._close_session(session)
    
    def create_daily_snapshot(self) -> Optional[DailySnapshot]:
        """
        Create a daily performance snapshot (persisted to database).
        
        Call this at end of trading day.
        """
        session = self._get_session()
        if not session:
            logger.warning("No database session - snapshot not persisted")
            return None
        
        try:
            from app.backend.database.models import DailyPerformance, TradeHistory
            
            today = date.today()
            today_dt = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
            
            # Check if snapshot already exists for today
            existing = session.query(DailyPerformance).filter(
                DailyPerformance.date >= today_dt,
                DailyPerformance.date < today_dt + timedelta(days=1)
            ).first()
            
            perf = self.get_current_performance()
            
            if "error" in perf:
                raise Exception(perf["error"])
            
            # Get today's trades from database
            today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
            today_end = today_start + timedelta(days=1)
            
            today_trades = session.query(TradeHistory).filter(
                TradeHistory.created_at >= today_start,
                TradeHistory.created_at < today_end
            ).all()
            
            closed_today = [t for t in today_trades if t.status == "closed"]
            winning = [t for t in closed_today if (t.realized_pnl or 0) > 0]
            losing = [t for t in closed_today if (t.realized_pnl or 0) < 0]
            
            # Find biggest winner/loser
            biggest_winner = max(closed_today, key=lambda t: t.realized_pnl or 0) if closed_today else None
            biggest_loser = min(closed_today, key=lambda t: t.realized_pnl or 0) if closed_today else None
            
            realized_pnl = sum(t.realized_pnl or 0 for t in closed_today)
            
            if existing:
                # Update existing snapshot
                existing.ending_equity = perf["equity"]
                existing.high_equity = max(existing.high_equity or 0, perf["equity"])
                existing.low_equity = min(existing.low_equity or perf["equity"], perf["equity"])
                existing.realized_pnl = realized_pnl
                existing.unrealized_pnl = perf.get("total_unrealized_pnl", 0)
                existing.total_pnl = perf.get("day_pnl", 0)
                existing.return_pct = perf.get("day_pnl_pct", 0)
                existing.trades_count = len(today_trades)
                existing.winning_trades = len(winning)
                existing.losing_trades = len(losing)
                existing.win_rate = len(winning) / len(closed_today) * 100 if closed_today else None
                existing.biggest_winner = biggest_winner.realized_pnl if biggest_winner else None
                existing.biggest_winner_ticker = biggest_winner.ticker if biggest_winner else None
                existing.biggest_loser = biggest_loser.realized_pnl if biggest_loser else None
                existing.biggest_loser_ticker = biggest_loser.ticker if biggest_loser else None
                existing.positions_count = perf.get("positions_count", 0)
                existing.positions_snapshot = perf.get("positions")
                
                session.commit()
                session.refresh(existing)
                
                snapshot = self._db_snapshot_to_dataclass(existing)
                logger.info(f"Updated daily snapshot for {today}: P&L ${snapshot.total_pnl:.2f}")
            else:
                # Create new snapshot
                db_snapshot = DailyPerformance(
                    date=today_dt,
                    starting_equity=self._starting_equity or perf["equity"],
                    ending_equity=perf["equity"],
                    high_equity=perf["equity"],
                    low_equity=perf["equity"],
                    realized_pnl=realized_pnl,
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
                    positions_count=perf.get("positions_count", 0),
                    positions_snapshot=perf.get("positions"),
                )
                
                session.add(db_snapshot)
                session.commit()
                session.refresh(db_snapshot)
                
                snapshot = self._db_snapshot_to_dataclass(db_snapshot)
                logger.info(f"Created daily snapshot for {today}: P&L ${snapshot.total_pnl:.2f}")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to create daily snapshot: {e}")
            session.rollback()
            return None
        finally:
            self._close_session(session)
    
    def get_daily_snapshots(self, days: int = 30) -> List[DailySnapshot]:
        """Get recent daily snapshots from database."""
        session = self._get_session()
        if not session:
            return []
        
        try:
            from app.backend.database.models import DailyPerformance
            
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            snapshots = session.query(DailyPerformance).filter(
                DailyPerformance.date >= cutoff
            ).order_by(DailyPerformance.date.desc()).all()
            
            return [self._db_snapshot_to_dataclass(s) for s in snapshots]
            
        except Exception as e:
            logger.error(f"Failed to get daily snapshots: {e}")
            return []
        finally:
            self._close_session(session)
    
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


def get_performance_tracker(db_session=None) -> PerformanceTracker:
    """Get the global performance tracker instance with optional DB session."""
    global _tracker
    if _tracker is None or db_session is not None:
        _tracker = PerformanceTracker(db_session)
    return _tracker
