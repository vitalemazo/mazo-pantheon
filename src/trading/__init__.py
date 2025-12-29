"""
Trading Module

Handles trade execution and portfolio management.
"""

from src.trading.alpaca_service import (
    AlpacaService,
    AlpacaAccount,
    AlpacaPosition,
    AlpacaOrder,
    TradeResult,
    OrderSide,
    OrderType,
    TimeInForce,
    get_alpaca_service,
    execute_trade,
)

__all__ = [
    "AlpacaService",
    "AlpacaAccount",
    "AlpacaPosition",
    "AlpacaOrder",
    "TradeResult",
    "OrderSide",
    "OrderType",
    "TimeInForce",
    "get_alpaca_service",
    "execute_trade",
]
