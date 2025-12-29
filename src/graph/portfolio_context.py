"""
Portfolio Context - Rich portfolio state for intelligent trading decisions.

This module provides a comprehensive view of the portfolio state including:
- Current positions with P&L
- Pending orders
- Cash and margin availability
- Portfolio allocation percentages
- Position history and recent trades
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Position:
    """Represents a single position in the portfolio."""
    symbol: str
    quantity: float
    side: PositionSide
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float
    cost_basis: float
    
    # Portfolio allocation
    allocation_pct: float = 0.0
    
    # Additional context
    days_held: int = 0
    last_trade_date: Optional[str] = None
    
    def to_summary(self) -> str:
        """Generate a human-readable summary for LLM context."""
        pl_sign = "+" if self.unrealized_pl >= 0 else ""
        return (
            f"{self.symbol}: {self.quantity:.0f} shares {self.side.value} @ ${self.avg_entry_price:.2f} "
            f"(current: ${self.current_price:.2f}, P&L: {pl_sign}${self.unrealized_pl:.2f} / {pl_sign}{self.unrealized_pl_pct:.1f}%, "
            f"allocation: {self.allocation_pct:.1f}%)"
        )
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "side": self.side.value,
            "avg_entry_price": self.avg_entry_price,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pl": self.unrealized_pl,
            "unrealized_pl_pct": self.unrealized_pl_pct,
            "cost_basis": self.cost_basis,
            "allocation_pct": self.allocation_pct,
            "days_held": self.days_held,
        }


@dataclass
class PendingOrder:
    """Represents a pending order."""
    order_id: str
    symbol: str
    side: str  # buy, sell
    quantity: float
    order_type: str  # market, limit, stop
    limit_price: Optional[float]
    status: str
    submitted_at: str
    
    def to_summary(self) -> str:
        """Generate a human-readable summary for LLM context."""
        price_str = f" @ ${self.limit_price:.2f}" if self.limit_price else " @ market"
        return f"{self.symbol}: {self.side.upper()} {self.quantity:.0f} shares{price_str} ({self.status})"
    
    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "limit_price": self.limit_price,
            "status": self.status,
            "submitted_at": self.submitted_at,
        }


@dataclass
class PortfolioContext:
    """
    Comprehensive portfolio context for intelligent trading decisions.
    
    This is passed to all agents so they can make informed decisions
    based on the current portfolio state.
    """
    
    # Account summary
    total_equity: float = 0.0
    cash: float = 0.0
    buying_power: float = 0.0
    
    # Margin info
    margin_used: float = 0.0
    margin_available: float = 0.0
    margin_requirement: float = 0.5
    
    # Positions
    positions: Dict[str, Position] = field(default_factory=dict)
    
    # Pending orders
    pending_orders: List[PendingOrder] = field(default_factory=list)
    
    # Allocation summary
    cash_allocation_pct: float = 0.0
    invested_allocation_pct: float = 0.0
    
    # Performance
    total_unrealized_pl: float = 0.0
    total_unrealized_pl_pct: float = 0.0
    
    # Metadata
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    account_status: str = "active"
    trading_blocked: bool = False
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol."""
        return self.positions.get(symbol.upper())
    
    def has_position(self, symbol: str) -> bool:
        """Check if we have a position in this symbol."""
        return symbol.upper() in self.positions
    
    def get_pending_orders_for(self, symbol: str) -> List[PendingOrder]:
        """Get pending orders for a specific symbol."""
        return [o for o in self.pending_orders if o.symbol.upper() == symbol.upper()]
    
    def has_pending_orders_for(self, symbol: str) -> bool:
        """Check if there are pending orders for this symbol."""
        return len(self.get_pending_orders_for(symbol)) > 0
    
    def to_llm_summary(self, include_positions: bool = True) -> str:
        """
        Generate a concise summary for LLM prompts.
        
        This summary helps agents understand the current portfolio state
        when making trading decisions.
        """
        lines = [
            "=== CURRENT PORTFOLIO STATE ===",
            f"Total Equity: ${self.total_equity:,.2f}",
            f"Cash: ${self.cash:,.2f} ({self.cash_allocation_pct:.1f}%)",
            f"Buying Power: ${self.buying_power:,.2f}",
        ]
        
        if self.margin_used > 0:
            lines.append(f"Margin Used: ${self.margin_used:,.2f} (Available: ${self.margin_available:,.2f})")
        
        if self.total_unrealized_pl != 0:
            pl_sign = "+" if self.total_unrealized_pl >= 0 else ""
            lines.append(f"Unrealized P&L: {pl_sign}${self.total_unrealized_pl:,.2f} ({pl_sign}{self.total_unrealized_pl_pct:.1f}%)")
        
        if include_positions and self.positions:
            lines.append("")
            lines.append("=== CURRENT POSITIONS ===")
            for pos in self.positions.values():
                lines.append(f"  • {pos.to_summary()}")
        elif not self.positions:
            lines.append("")
            lines.append("=== NO CURRENT POSITIONS ===")
        
        if self.pending_orders:
            lines.append("")
            lines.append("=== PENDING ORDERS ===")
            for order in self.pending_orders:
                lines.append(f"  • {order.to_summary()}")
        
        return "\n".join(lines)
    
    def to_ticker_context(self, ticker: str) -> str:
        """
        Generate ticker-specific context for an agent analyzing this ticker.
        """
        lines = []
        ticker = ticker.upper()
        
        # Current position
        pos = self.get_position(ticker)
        if pos:
            pl_sign = "+" if pos.unrealized_pl >= 0 else ""
            lines.append(f"CURRENT POSITION: {pos.quantity:.0f} shares {pos.side.value}")
            lines.append(f"  Entry: ${pos.avg_entry_price:.2f} | Current: ${pos.current_price:.2f}")
            lines.append(f"  P&L: {pl_sign}${pos.unrealized_pl:.2f} ({pl_sign}{pos.unrealized_pl_pct:.1f}%)")
            lines.append(f"  Portfolio Allocation: {pos.allocation_pct:.1f}%")
        else:
            lines.append(f"CURRENT POSITION: None (no {ticker} holdings)")
        
        # Pending orders
        pending = self.get_pending_orders_for(ticker)
        if pending:
            lines.append("")
            lines.append("PENDING ORDERS:")
            for order in pending:
                lines.append(f"  • {order.to_summary()}")
        
        # Available capital
        lines.append("")
        lines.append(f"AVAILABLE CAPITAL: ${self.buying_power:,.2f} buying power")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_equity": self.total_equity,
            "cash": self.cash,
            "buying_power": self.buying_power,
            "margin_used": self.margin_used,
            "margin_available": self.margin_available,
            "cash_allocation_pct": self.cash_allocation_pct,
            "invested_allocation_pct": self.invested_allocation_pct,
            "total_unrealized_pl": self.total_unrealized_pl,
            "total_unrealized_pl_pct": self.total_unrealized_pl_pct,
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "pending_orders": [o.to_dict() for o in self.pending_orders],
            "last_updated": self.last_updated,
            "account_status": self.account_status,
            "trading_blocked": self.trading_blocked,
        }
    
    @classmethod
    def from_alpaca(cls, account, positions, orders) -> "PortfolioContext":
        """
        Create PortfolioContext from Alpaca API data.
        
        Args:
            account: AlpacaAccount object
            positions: List of AlpacaPosition objects
            orders: List of AlpacaOrder objects (open orders)
        """
        total_equity = float(account.portfolio_value)
        cash = float(account.cash)
        
        # Calculate allocations
        cash_allocation = (cash / total_equity * 100) if total_equity > 0 else 100
        invested_allocation = 100 - cash_allocation
        
        # Process positions
        positions_dict = {}
        total_unrealized_pl = 0.0
        total_cost_basis = 0.0
        
        for pos in positions:
            qty = float(pos.qty)
            side = PositionSide.LONG if qty > 0 else PositionSide.SHORT
            market_value = float(pos.market_value)
            cost_basis = float(pos.cost_basis) if hasattr(pos, 'cost_basis') else abs(qty) * float(pos.avg_entry_price)
            unrealized_pl = float(pos.unrealized_pl)
            unrealized_pl_pct = float(pos.unrealized_plpc) * 100 if hasattr(pos, 'unrealized_plpc') else (
                (unrealized_pl / cost_basis * 100) if cost_basis > 0 else 0
            )
            
            allocation_pct = (abs(market_value) / total_equity * 100) if total_equity > 0 else 0
            
            positions_dict[pos.symbol] = Position(
                symbol=pos.symbol,
                quantity=abs(qty),
                side=side,
                avg_entry_price=float(pos.avg_entry_price),
                current_price=float(pos.current_price),
                market_value=market_value,
                unrealized_pl=unrealized_pl,
                unrealized_pl_pct=unrealized_pl_pct,
                cost_basis=cost_basis,
                allocation_pct=allocation_pct,
            )
            
            total_unrealized_pl += unrealized_pl
            total_cost_basis += cost_basis
        
        total_unrealized_pl_pct = (total_unrealized_pl / total_cost_basis * 100) if total_cost_basis > 0 else 0
        
        # Process pending orders
        pending_orders = []
        for order in orders:
            pending_orders.append(PendingOrder(
                order_id=order.id,
                symbol=order.symbol,
                side=order.side,
                quantity=float(order.qty),
                order_type=order.type,
                limit_price=float(order.limit_price) if order.limit_price else None,
                status=order.status,
                submitted_at=order.submitted_at,
            ))
        
        return cls(
            total_equity=total_equity,
            cash=cash,
            buying_power=float(account.buying_power),
            margin_used=float(account.initial_margin) if account.initial_margin else 0.0,
            margin_available=float(account.buying_power) - float(account.initial_margin) if account.initial_margin else float(account.buying_power),
            positions=positions_dict,
            pending_orders=pending_orders,
            cash_allocation_pct=cash_allocation,
            invested_allocation_pct=invested_allocation,
            total_unrealized_pl=total_unrealized_pl,
            total_unrealized_pl_pct=total_unrealized_pl_pct,
            account_status=account.status,
            trading_blocked=account.trading_blocked,
        )


def build_portfolio_context() -> PortfolioContext:
    """
    Convenience function to build PortfolioContext from live Alpaca data.
    
    Returns:
        PortfolioContext populated with current account, positions, and orders
    """
    from src.trading.alpaca_service import AlpacaService
    
    alpaca = AlpacaService()
    
    # Get account info
    account = alpaca.get_account()
    if not account:
        raise ValueError("Could not fetch Alpaca account")
    
    # Get positions
    positions = alpaca.get_positions() or []
    
    # Get open orders
    orders = alpaca.get_orders(status="open") or []
    
    return PortfolioContext.from_alpaca(account, positions, orders)
