"""
Watchlist Management Service

Manages trading watchlists with entry targets, stop-losses, and automatic monitoring.
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from src.tools.api import get_prices
from src.trading.alpaca_service import AlpacaService
from src.trading.strategy_engine import get_strategy_engine, TradingSignal

logger = logging.getLogger(__name__)


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
    Manages trading watchlists.
    
    Features:
    - Add/remove items from watchlist
    - Set entry targets and conditions
    - Monitor for triggers
    - Auto-analyze with strategies
    """
    
    def __init__(self):
        self.alpaca = AlpacaService()
        self.strategy_engine = get_strategy_engine()
        
        # In-memory watchlist (for now - will move to DB)
        self._watchlist: List[WatchlistItem] = []
        self._next_id = 1
    
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
    ) -> WatchlistItem:
        """
        Add an item to the watchlist.
        
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
            Created WatchlistItem
        """
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
        
        item = WatchlistItem(
            id=self._next_id,
            ticker=ticker.upper(),
            name=None,  # Could fetch from API
            sector=None,  # Could fetch from API
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
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=expires_in_days),
            triggered_at=None,
            triggered_price=None,
        )
        
        self._watchlist.append(item)
        self._next_id += 1
        
        logger.info(f"Added {ticker} to watchlist with target ${entry_target:.2f}")
        return item
    
    def remove_item(self, item_id: int) -> bool:
        """Remove an item from the watchlist."""
        for i, item in enumerate(self._watchlist):
            if item.id == item_id:
                del self._watchlist[i]
                logger.info(f"Removed item {item_id} from watchlist")
                return True
        return False
    
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
        """Update a watchlist item."""
        for item in self._watchlist:
            if item.id == item_id:
                if entry_target is not None:
                    item.entry_target = entry_target
                if stop_loss is not None:
                    item.stop_loss = stop_loss
                if take_profit is not None:
                    item.take_profit = take_profit
                if priority is not None:
                    item.priority = priority
                if notes is not None:
                    item.notes = notes
                if status is not None:
                    item.status = status
                return item
        return None
    
    def get_watchlist(
        self,
        status: Optional[str] = None,
        sort_by: str = "priority"
    ) -> List[WatchlistItem]:
        """
        Get the watchlist, optionally filtered and sorted.
        
        Args:
            status: Filter by status ("watching", "triggered", etc.)
            sort_by: Sort field ("priority", "created_at", "ticker")
        """
        items = self._watchlist
        
        if status:
            items = [i for i in items if i.status == status]
        
        # Sort
        if sort_by == "priority":
            items.sort(key=lambda x: x.priority, reverse=True)
        elif sort_by == "created_at":
            items.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
        elif sort_by == "ticker":
            items.sort(key=lambda x: x.ticker)
        
        return items
    
    def get_item(self, item_id: int) -> Optional[WatchlistItem]:
        """Get a specific watchlist item."""
        for item in self._watchlist:
            if item.id == item_id:
                return item
        return None
    
    def check_triggers(self) -> List[WatchlistItem]:
        """
        Check all watching items for triggered conditions.
        
        Returns list of newly triggered items.
        """
        triggered = []
        
        for item in self._watchlist:
            if item.status != "watching":
                continue
            
            # Check expiration
            if item.expires_at and datetime.now() > item.expires_at:
                item.status = "expired"
                continue
            
            try:
                # Get current price
                end = date.today()
                start = end - timedelta(days=5)
                prices = get_prices(item.ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
                if not prices:
                    continue
                
                current_price = prices[-1].close
                
                # Check trigger condition
                is_triggered = False
                
                if item.entry_condition == "below" and item.entry_target:
                    if current_price <= item.entry_target:
                        is_triggered = True
                        
                elif item.entry_condition == "above" and item.entry_target:
                    if current_price >= item.entry_target:
                        is_triggered = True
                        
                elif item.entry_condition == "breakout":
                    # Check for 20-day high breakout
                    start_20 = end - timedelta(days=30)
                    prices_20 = get_prices(item.ticker, start_20.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
                    if prices_20:
                        prices_20 = prices_20[-20:]  # Get last 20
                        high_20 = max(p.high for p in prices_20[:-1])
                        if current_price > high_20:
                            is_triggered = True
                
                if is_triggered:
                    item.status = "triggered"
                    item.triggered_at = datetime.now()
                    item.triggered_price = current_price
                    triggered.append(item)
                    logger.info(f"Watchlist trigger: {item.ticker} at ${current_price:.2f}")
                    
            except Exception as e:
                logger.error(f"Error checking {item.ticker}: {e}")
        
        return triggered
    
    def analyze_watchlist(self) -> List[Dict[str, Any]]:
        """
        Run strategy analysis on all watchlist items.
        
        Returns analysis results for each item.
        """
        results = []
        
        for item in self._watchlist:
            if item.status != "watching":
                continue
            
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
    
    def get_summary(self) -> Dict[str, Any]:
        """Get watchlist summary statistics."""
        watching = [i for i in self._watchlist if i.status == "watching"]
        triggered = [i for i in self._watchlist if i.status == "triggered"]
        expired = [i for i in self._watchlist if i.status == "expired"]
        
        return {
            "total_items": len(self._watchlist),
            "watching": len(watching),
            "triggered": len(triggered),
            "expired": len(expired),
            "high_priority": len([i for i in watching if i.priority >= 8]),
            "expiring_soon": len([
                i for i in watching 
                if i.expires_at and (i.expires_at - datetime.now()).days <= 3
            ]),
        }


# Global service instance
_watchlist_service: Optional[WatchlistService] = None


def get_watchlist_service() -> WatchlistService:
    """Get the global watchlist service instance."""
    global _watchlist_service
    if _watchlist_service is None:
        _watchlist_service = WatchlistService()
    return _watchlist_service
