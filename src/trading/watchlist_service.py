"""
Watchlist Management Service

Manages trading watchlists with entry targets, stop-losses, and automatic monitoring.
Persists data to PostgreSQL/SQLite for durability across restarts.
"""

import logging
from datetime import datetime, timedelta, date, timezone
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from src.tools.api import get_prices
from src.trading.alpaca_service import AlpacaService
from src.trading.strategy_engine import get_strategy_engine, TradingSignal

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
class WatchlistItem:
    """A watchlist entry"""
    id: Optional[int]
    ticker: str
    name: Optional[str]
    sector: Optional[str]
    strategy: Optional[str]
    entry_target: Optional[float]
    entry_condition: str  # "above", "below", "breakout"
    stop_loss: Optional[float]
    take_profit: Optional[float]
    position_size_pct: float
    status: str  # "watching", "triggered", "expired", "cancelled"
    priority: int  # 1-10
    notes: Optional[str]
    signals: Optional[Dict]
    created_at: Optional[datetime]
    expires_at: Optional[datetime]
    triggered_at: Optional[datetime]
    triggered_price: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "name": self.name,
            "sector": self.sector,
            "strategy": self.strategy,
            "entry_target": self.entry_target,
            "entry_condition": self.entry_condition,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_size_pct": self.position_size_pct,
            "status": self.status,
            "priority": self.priority,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "triggered_price": self.triggered_price,
        }


class WatchlistService:
    """
    Manages trading watchlists with database persistence.
    
    Features:
    - Add/remove items from watchlist
    - Set entry targets and conditions
    - Monitor for triggers
    - Auto-analyze with strategies
    - Persists to PostgreSQL/SQLite for durability
    """
    
    def __init__(self, db_session=None):
        self.alpaca = AlpacaService()
        self.strategy_engine = get_strategy_engine()
        self._db_session = db_session
    
    def _get_session(self):
        """Get or create a database session."""
        if self._db_session:
            return self._db_session
        return _get_db_session()
    
    def _close_session(self, session):
        """Close session if we created it."""
        if session and session != self._db_session:
            session.close()
    
    def _db_to_item(self, db_row) -> WatchlistItem:
        """Convert database row to WatchlistItem."""
        return WatchlistItem(
            id=db_row.id,
            ticker=db_row.ticker,
            name=db_row.name,
            sector=db_row.sector,
            strategy=db_row.strategy,
            entry_target=db_row.entry_target,
            entry_condition=db_row.entry_condition or "below",
            stop_loss=db_row.stop_loss,
            take_profit=db_row.take_profit,
            position_size_pct=db_row.position_size_pct or 0.05,
            status=db_row.status or "watching",
            priority=db_row.priority or 5,
            notes=db_row.notes,
            signals=db_row.signals,
            created_at=db_row.created_at,
            expires_at=db_row.expires_at,
            triggered_at=db_row.triggered_at,
            triggered_price=db_row.triggered_price,
        )
    
    def add_item(
        self,
        ticker: str,
        entry_target: Optional[float] = None,
        entry_condition: str = "below",  # buy below target
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_size_pct: float = 0.05,
        strategy: Optional[str] = None,
        priority: int = 5,
        notes: Optional[str] = None,
        expires_in_days: int = 30
    ) -> Optional[WatchlistItem]:
        """
        Add an item to the watchlist (persisted to database).
        
        Args:
            ticker: Stock ticker
            entry_target: Target entry price
            entry_condition: "above", "below", "breakout"
            stop_loss: Stop-loss price
            take_profit: Take-profit price
            position_size_pct: % of portfolio to allocate
            strategy: Strategy name for analysis
            priority: 1-10 (10 = highest)
            notes: Additional notes
            expires_in_days: Days until expiration
            
        Returns:
            Created WatchlistItem or None on failure
        """
        session = self._get_session()
        if not session:
            logger.error("No database session available for watchlist")
            return None
        
        try:
            from app.backend.database.models import Watchlist
            
            # Get current price if no entry target
            if entry_target is None:
                end = date.today()
                start = end - timedelta(days=5)
                prices = get_prices(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
                if prices:
                    current_price = prices[-1].close
                    # Default to 2% below current for buying
                    entry_target = current_price * 0.98
            
            # Calculate stop/profit if not provided
            if entry_target and not stop_loss:
                stop_loss = entry_target * 0.95  # 5% stop
            if entry_target and not take_profit:
                take_profit = entry_target * 1.10  # 10% target
            
            # Get strategy signals
            signals = None
            if strategy:
                strat = self.strategy_engine.get_strategy(strategy)
                if strat:
                    signal = strat.analyze(ticker)
                    if signal:
                        signals = signal.to_dict()
            
            # Create database record
            db_item = Watchlist(
                ticker=ticker.upper(),
                name=None,
                sector=None,
                strategy=strategy,
                entry_target=entry_target,
                entry_condition=entry_condition,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size_pct=position_size_pct,
                status="watching",
                priority=priority,
                notes=notes,
                signals=signals,
                expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days),
            )
            
            session.add(db_item)
            session.commit()
            session.refresh(db_item)
            
            item = self._db_to_item(db_item)
            target_str = f"${entry_target:.2f}" if entry_target else "not set"
            logger.info(f"Added {ticker} to watchlist with target {target_str}")
            return item
            
        except Exception as e:
            logger.error(f"Failed to add watchlist item: {e}")
            session.rollback()
            return None
        finally:
            self._close_session(session)
    
    def remove_item(self, item_id: int) -> bool:
        """Remove an item from the watchlist (deletes from database)."""
        session = self._get_session()
        if not session:
            return False
        
        try:
            from app.backend.database.models import Watchlist
            
            db_item = session.query(Watchlist).filter_by(id=item_id).first()
            if db_item:
                session.delete(db_item)
                session.commit()
                logger.info(f"Removed item {item_id} from watchlist")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove watchlist item: {e}")
            session.rollback()
            return False
        finally:
            self._close_session(session)
    
    def update_item(
        self,
        item_id: int,
        entry_target: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        priority: Optional[int] = None,
        notes: Optional[str] = None,
        status: Optional[str] = None
    ) -> Optional[WatchlistItem]:
        """Update a watchlist item (persisted to database)."""
        session = self._get_session()
        if not session:
            return None
        
        try:
            from app.backend.database.models import Watchlist
            
            db_item = session.query(Watchlist).filter_by(id=item_id).first()
            if not db_item:
                return None
            
            if entry_target is not None:
                db_item.entry_target = entry_target
            if stop_loss is not None:
                db_item.stop_loss = stop_loss
            if take_profit is not None:
                db_item.take_profit = take_profit
            if priority is not None:
                db_item.priority = priority
            if notes is not None:
                db_item.notes = notes
            if status is not None:
                db_item.status = status
            
            session.commit()
            session.refresh(db_item)
            return self._db_to_item(db_item)
        except Exception as e:
            logger.error(f"Failed to update watchlist item: {e}")
            session.rollback()
            return None
        finally:
            self._close_session(session)
    
    def get_watchlist(
        self,
        status: Optional[str] = None,
        sort_by: str = "priority"
    ) -> List[WatchlistItem]:
        """
        Get the watchlist from database, optionally filtered and sorted.
        
        Args:
            status: Filter by status ("watching", "triggered", etc.)
            sort_by: Sort field ("priority", "created_at", "ticker")
        """
        session = self._get_session()
        if not session:
            return []
        
        try:
            from app.backend.database.models import Watchlist
            
            query = session.query(Watchlist)
            
            if status:
                query = query.filter(Watchlist.status == status)
            
            # Sort
            if sort_by == "priority":
                query = query.order_by(Watchlist.priority.desc())
            elif sort_by == "created_at":
                query = query.order_by(Watchlist.created_at.desc())
            elif sort_by == "ticker":
                query = query.order_by(Watchlist.ticker)
            
            items = [self._db_to_item(row) for row in query.all()]
            return items
        except Exception as e:
            logger.error(f"Failed to get watchlist: {e}")
            return []
        finally:
            self._close_session(session)
    
    def get_item(self, item_id: int) -> Optional[WatchlistItem]:
        """Get a specific watchlist item from database."""
        session = self._get_session()
        if not session:
            return None
        
        try:
            from app.backend.database.models import Watchlist
            
            db_item = session.query(Watchlist).filter_by(id=item_id).first()
            if db_item:
                return self._db_to_item(db_item)
            return None
        except Exception as e:
            logger.error(f"Failed to get watchlist item: {e}")
            return None
        finally:
            self._close_session(session)
    
    def check_triggers(self) -> List[WatchlistItem]:
        """
        Check all watching items for triggered conditions.
        Updates database and returns list of newly triggered items.
        """
        session = self._get_session()
        if not session:
            return []
        
        triggered = []
        
        try:
            from app.backend.database.models import Watchlist
            
            # Get all watching items
            watching_items = session.query(Watchlist).filter(
                Watchlist.status == "watching"
            ).all()
            
            for db_item in watching_items:
                # Check expiration
                if db_item.expires_at and datetime.now(timezone.utc) > db_item.expires_at:
                    db_item.status = "expired"
                    continue
                
                try:
                    # Get current price
                    end = date.today()
                    start = end - timedelta(days=5)
                    prices = get_prices(db_item.ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
                    if not prices:
                        continue
                    
                    current_price = prices[-1].close
                    
                    # Check trigger condition
                    is_triggered = False
                    
                    if db_item.entry_condition == "below" and db_item.entry_target:
                        if current_price <= db_item.entry_target:
                            is_triggered = True
                            
                    elif db_item.entry_condition == "above" and db_item.entry_target:
                        if current_price >= db_item.entry_target:
                            is_triggered = True
                            
                    elif db_item.entry_condition == "breakout":
                        # Check for 20-day high breakout
                        start_20 = end - timedelta(days=30)
                        prices_20 = get_prices(db_item.ticker, start_20.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
                        if prices_20:
                            prices_20 = prices_20[-20:]  # Get last 20
                            high_20 = max(p.high for p in prices_20[:-1])
                            if current_price > high_20:
                                is_triggered = True
                    
                    if is_triggered:
                        db_item.status = "triggered"
                        db_item.triggered_at = datetime.now(timezone.utc)
                        db_item.triggered_price = current_price
                        triggered.append(self._db_to_item(db_item))
                        logger.info(f"Watchlist trigger: {db_item.ticker} at ${current_price:.2f}")
                        
                except Exception as e:
                    logger.error(f"Error checking {db_item.ticker}: {e}")
            
            session.commit()
            return triggered
            
        except Exception as e:
            logger.error(f"Failed to check triggers: {e}")
            session.rollback()
            return []
        finally:
            self._close_session(session)
    
    def analyze_watchlist(self) -> List[Dict[str, Any]]:
        """
        Run strategy analysis on all watchlist items.
        
        Returns analysis results for each item.
        """
        items = self.get_watchlist(status="watching")
        results = []
        
        for item in items:
            try:
                signals = self.strategy_engine.analyze_ticker(item.ticker)
                
                # Get current price
                end = date.today()
                start = end - timedelta(days=5)
                prices = get_prices(item.ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
                current_price = prices[-1].close if prices else None
                
                results.append({
                    "ticker": item.ticker,
                    "current_price": current_price,
                    "entry_target": item.entry_target,
                    "distance_to_target_pct": (
                        ((current_price - item.entry_target) / item.entry_target * 100)
                        if current_price and item.entry_target else None
                    ),
                    "signals": [s.to_dict() for s in signals],
                    "priority": item.priority,
                })
                
            except Exception as e:
                logger.error(f"Error analyzing {item.ticker}: {e}")
        
        return results
    
    def add_from_signal(self, signal: TradingSignal) -> WatchlistItem:
        """
        Add a watchlist item from a trading signal.
        
        Automatically sets entry, stop, and target from signal.
        """
        entry_condition = "below" if signal.direction.value == "long" else "above"
        
        return self.add_item(
            ticker=signal.ticker,
            entry_target=signal.entry_price,
            entry_condition=entry_condition,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            position_size_pct=signal.position_size_pct,
            strategy=signal.strategy,
            priority=8 if signal.strength.value == "strong" else 5,
            notes=signal.reasoning,
        )
    
    def auto_enrich_from_danelfin(
        self,
        min_ai_score: int = 8,
        stocks_per_sector: int = 2,
        max_total: int = 10,
    ) -> Dict[str, Any]:
        """
        Auto-populate watchlist with high-scoring Danelfin picks.
        
        Adds top AI-scored stocks from underrepresented sectors.
        Items are tagged as 'auto_generated' so users can manage them.
        
        Args:
            min_ai_score: Minimum Danelfin AI score (default 8)
            stocks_per_sector: Max stocks to add per sector (default 2)
            max_total: Maximum total stocks to add (default 10)
        
        Returns:
            Dict with added, skipped, and error counts
        """
        try:
            from src.tools.danelfin_api import get_top_stocks, get_scores_batch, is_danelfin_enabled
            from src.trading.config import get_danelfin_config
            
            danelfin_config = get_danelfin_config()
            
            if not is_danelfin_enabled() or not danelfin_config.enabled:
                return {"added": 0, "skipped": 0, "error": "Danelfin not enabled"}
            
            # Get existing watchlist tickers
            watchlist = self.get_watchlist()
            existing = {item.ticker for item in watchlist if item.status == "watching"}
            
            # Try to get Danelfin top stocks (may fail on basic plan)
            top_stocks = get_top_stocks(min_ai_score=min_ai_score, limit=max_total * 2)
            
            # Fallback: score popular tickers individually if ranking API unavailable
            if not top_stocks:
                logger.info("[Watchlist Auto] Ranking API unavailable, scoring popular tickers...")
                popular_tickers = [
                    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
                    "AMD", "PLTR", "SOFI", "COIN", "HOOD", "NU", "RBLX",
                    "F", "GM", "NIO", "RIVN", "XOM", "JPM"
                ]
                scores = get_scores_batch(popular_tickers)
                # Filter by min_ai_score and convert to dict
                top_stocks = {
                    ticker: score for ticker, score in scores.items()
                    if score.success and score.ai_score >= min_ai_score
                }
            
            if not top_stocks:
                return {"added": 0, "skipped": 0, "error": "No stocks met the AI score threshold"}
            
            added = []
            skipped = []
            sector_counts = {}
            
            # Sort by AI score
            sorted_tickers = sorted(
                top_stocks.keys(),
                key=lambda t: top_stocks[t].ai_score,
                reverse=True
            )
            
            for ticker in sorted_tickers:
                if len(added) >= max_total:
                    break
                
                score = top_stocks[ticker]
                
                # Skip if already watching
                if ticker in existing:
                    skipped.append((ticker, "already watching"))
                    continue
                
                # Limit per sector (inferred from score data)
                sector = "General"  # Danelfin basic plan may not include sector
                if sector_counts.get(sector, 0) >= stocks_per_sector:
                    skipped.append((ticker, f"sector limit ({sector})"))
                    continue
                
                # Add to watchlist with auto-generated note
                try:
                    self.add_item(
                        ticker=ticker,
                        entry_target=None,  # No specific target
                        entry_condition="below",
                        priority=min(10, 5 + score.ai_score // 2),  # Higher AI = higher priority
                        notes=f"[Auto-Danelfin] AI:{score.ai_score}/10, Tech:{score.technical}, Fund:{score.fundamental}, Risk:{score.low_risk}",
                        expires_in_days=14,  # Short expiry for auto items
                    )
                    added.append(ticker)
                    sector_counts[sector] = sector_counts.get(sector, 0) + 1
                    logger.info(f"[Watchlist Auto] Added {ticker} (AI score: {score.ai_score})")
                except Exception as e:
                    logger.warning(f"Failed to add {ticker} to watchlist: {e}")
                    skipped.append((ticker, str(e)))
            
            result = {
                "added": len(added),
                "added_tickers": added,
                "skipped": len(skipped),
                "skipped_details": skipped[:5],  # Limit details
            }
            
            logger.info(f"[Watchlist Auto] Enriched watchlist: {len(added)} added, {len(skipped)} skipped")
            return result
            
        except ImportError as e:
            return {"added": 0, "skipped": 0, "error": f"Danelfin not available: {e}"}
        except Exception as e:
            logger.error(f"Watchlist auto-enrich error: {e}")
            return {"added": 0, "skipped": 0, "error": str(e)}
    
    def get_summary(self) -> Dict[str, Any]:
        """Get watchlist summary statistics from database."""
        session = self._get_session()
        if not session:
            return {"total_items": 0, "watching": 0, "triggered": 0, "expired": 0}
        
        try:
            from app.backend.database.models import Watchlist
            from sqlalchemy import func
            
            # Count by status
            total = session.query(func.count(Watchlist.id)).scalar() or 0
            watching = session.query(func.count(Watchlist.id)).filter(
                Watchlist.status == "watching"
            ).scalar() or 0
            triggered = session.query(func.count(Watchlist.id)).filter(
                Watchlist.status == "triggered"
            ).scalar() or 0
            expired = session.query(func.count(Watchlist.id)).filter(
                Watchlist.status == "expired"
            ).scalar() or 0
            
            # High priority watching
            high_priority = session.query(func.count(Watchlist.id)).filter(
                Watchlist.status == "watching",
                Watchlist.priority >= 8
            ).scalar() or 0
            
            # Expiring soon (within 3 days)
            soon = datetime.now(timezone.utc) + timedelta(days=3)
            expiring_soon = session.query(func.count(Watchlist.id)).filter(
                Watchlist.status == "watching",
                Watchlist.expires_at <= soon
            ).scalar() or 0
            
            return {
                "total_items": total,
                "watching": watching,
                "triggered": triggered,
                "expired": expired,
                "high_priority": high_priority,
                "expiring_soon": expiring_soon,
            }
        except Exception as e:
            logger.error(f"Failed to get watchlist summary: {e}")
            return {"total_items": 0, "watching": 0, "triggered": 0, "expired": 0}
        finally:
            self._close_session(session)


# Global service instance
_watchlist_service: Optional[WatchlistService] = None


def get_watchlist_service(db_session=None) -> WatchlistService:
    """Get the global watchlist service instance with optional DB session."""
    global _watchlist_service
    if _watchlist_service is None or db_session is not None:
        _watchlist_service = WatchlistService(db_session)
    return _watchlist_service
