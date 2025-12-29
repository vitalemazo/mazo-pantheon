"""
Alpaca Trading Service

Handles all interactions with Alpaca's Trading API for:
- Account information
- Position management
- Order execution
- Portfolio synchronization

Supports both paper trading and live trading modes.
"""

import os
import requests
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"  # Good til cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill
    OPG = "opg"  # Market on open
    CLS = "cls"  # Market on close


class OrderStatus(str, Enum):
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    DONE_FOR_DAY = "done_for_day"
    CANCELED = "canceled"
    EXPIRED = "expired"
    REPLACED = "replaced"
    PENDING_CANCEL = "pending_cancel"
    PENDING_REPLACE = "pending_replace"
    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    PENDING_NEW = "pending_new"
    ACCEPTED_FOR_BIDDING = "accepted_for_bidding"
    STOPPED = "stopped"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    CALCULATED = "calculated"


@dataclass
class AlpacaAccount:
    """Alpaca account information"""
    id: str
    account_number: str
    status: str
    currency: str
    cash: float
    buying_power: float
    portfolio_value: float
    equity: float
    long_market_value: float
    short_market_value: float
    initial_margin: float
    maintenance_margin: float
    pattern_day_trader: bool
    trading_blocked: bool
    shorting_enabled: bool
    daytrade_count: int
    multiplier: str

    @classmethod
    def from_api_response(cls, data: Dict) -> "AlpacaAccount":
        return cls(
            id=data.get("id", ""),
            account_number=data.get("account_number", ""),
            status=data.get("status", ""),
            currency=data.get("currency", "USD"),
            cash=float(data.get("cash", 0)),
            buying_power=float(data.get("buying_power", 0)),
            portfolio_value=float(data.get("portfolio_value", 0)),
            equity=float(data.get("equity", 0)),
            long_market_value=float(data.get("long_market_value", 0)),
            short_market_value=float(data.get("short_market_value", 0)),
            initial_margin=float(data.get("initial_margin", 0)),
            maintenance_margin=float(data.get("maintenance_margin", 0)),
            pattern_day_trader=data.get("pattern_day_trader", False),
            trading_blocked=data.get("trading_blocked", False),
            shorting_enabled=data.get("shorting_enabled", True),
            daytrade_count=int(data.get("daytrade_count", 0)),
            multiplier=data.get("multiplier", "1"),
        )


@dataclass
class AlpacaPosition:
    """Alpaca position information"""
    asset_id: str
    symbol: str
    exchange: str
    qty: float
    qty_available: float
    side: str  # 'long' or 'short'
    market_value: float
    cost_basis: float
    avg_entry_price: float
    unrealized_pl: float
    unrealized_plpc: float  # Unrealized P/L percentage
    current_price: float
    change_today: float

    @classmethod
    def from_api_response(cls, data: Dict) -> "AlpacaPosition":
        return cls(
            asset_id=data.get("asset_id", ""),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            qty=float(data.get("qty", 0)),
            qty_available=float(data.get("qty_available", 0)),
            side=data.get("side", "long"),
            market_value=float(data.get("market_value", 0)),
            cost_basis=float(data.get("cost_basis", 0)),
            avg_entry_price=float(data.get("avg_entry_price", 0)),
            unrealized_pl=float(data.get("unrealized_pl", 0)),
            unrealized_plpc=float(data.get("unrealized_plpc", 0)),
            current_price=float(data.get("current_price", 0)),
            change_today=float(data.get("change_today", 0)),
        )


@dataclass
class AlpacaOrder:
    """Alpaca order information"""
    id: str
    client_order_id: str
    symbol: str
    side: str
    type: str
    qty: float
    filled_qty: float
    filled_avg_price: Optional[float]
    status: str
    time_in_force: str
    limit_price: Optional[float]
    stop_price: Optional[float]
    created_at: str
    submitted_at: str
    filled_at: Optional[str]

    @classmethod
    def from_api_response(cls, data: Dict) -> "AlpacaOrder":
        return cls(
            id=data.get("id", ""),
            client_order_id=data.get("client_order_id", ""),
            symbol=data.get("symbol", ""),
            side=data.get("side", ""),
            type=data.get("type", ""),
            qty=float(data.get("qty", 0)),
            filled_qty=float(data.get("filled_qty", 0)),
            filled_avg_price=float(data["filled_avg_price"]) if data.get("filled_avg_price") else None,
            status=data.get("status", ""),
            time_in_force=data.get("time_in_force", ""),
            limit_price=float(data["limit_price"]) if data.get("limit_price") else None,
            stop_price=float(data["stop_price"]) if data.get("stop_price") else None,
            created_at=data.get("created_at", ""),
            submitted_at=data.get("submitted_at", ""),
            filled_at=data.get("filled_at"),
        )


@dataclass
class TradeResult:
    """Result of a trade execution"""
    success: bool
    order: Optional[AlpacaOrder] = None
    error: Optional[str] = None
    message: str = ""


class AlpacaService:
    """
    Service for interacting with Alpaca Trading API.

    Supports paper trading and live trading modes.
    """

    def __init__(
        self,
        api_key: str = None,
        secret_key: str = None,
        base_url: str = None,
        paper: bool = True
    ):
        """
        Initialize the Alpaca service.

        Args:
            api_key: Alpaca API key (defaults to env var)
            secret_key: Alpaca secret key (defaults to env var)
            base_url: API base URL (defaults to env var or paper trading)
            paper: If True, use paper trading API
        """
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")

        if base_url:
            self.base_url = base_url
        elif os.environ.get("ALPACA_BASE_URL"):
            self.base_url = os.environ.get("ALPACA_BASE_URL")
        else:
            self.base_url = (
                "https://paper-api.alpaca.markets/v2" if paper
                else "https://api.alpaca.markets/v2"
            )

        self.paper = paper or "paper" in self.base_url

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca API credentials not found. "
                "Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables."
            )

    def _headers(self) -> Dict[str, str]:
        """Get API headers"""
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None
    ) -> Dict:
        """Make API request"""
        url = f"{self.base_url}/{endpoint}"

        response = requests.request(
            method=method,
            url=url,
            headers=self._headers(),
            params=params,
            json=data,
        )

        if response.status_code >= 400:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("message", response.text)
            except:
                pass
            raise Exception(f"Alpaca API error ({response.status_code}): {error_msg}")

        if response.text:
            return response.json()
        return {}

    # ==================== Account ====================

    def get_account(self) -> AlpacaAccount:
        """Get account information"""
        data = self._request("GET", "account")
        return AlpacaAccount.from_api_response(data)

    def get_buying_power(self) -> float:
        """Get current buying power"""
        account = self.get_account()
        return account.buying_power

    def get_cash(self) -> float:
        """Get available cash"""
        account = self.get_account()
        return account.cash

    def get_portfolio_value(self) -> float:
        """Get total portfolio value"""
        account = self.get_account()
        return account.portfolio_value

    # ==================== Positions ====================

    def get_positions(self) -> List[AlpacaPosition]:
        """Get all open positions"""
        data = self._request("GET", "positions")
        return [AlpacaPosition.from_api_response(p) for p in data]

    def get_position(self, symbol: str) -> Optional[AlpacaPosition]:
        """Get position for a specific symbol"""
        try:
            data = self._request("GET", f"positions/{symbol}")
            return AlpacaPosition.from_api_response(data)
        except Exception as e:
            if "404" in str(e) or "position does not exist" in str(e).lower():
                return None
            raise

    def close_position(self, symbol: str, qty: float = None) -> TradeResult:
        """
        Close a position.

        Args:
            symbol: Stock symbol
            qty: Quantity to close (None = close entire position)
        """
        try:
            params = {}
            if qty is not None:
                params["qty"] = str(qty)

            data = self._request("DELETE", f"positions/{symbol}", params=params)
            order = AlpacaOrder.from_api_response(data)

            return TradeResult(
                success=True,
                order=order,
                message=f"Closed position: {symbol}"
            )
        except Exception as e:
            return TradeResult(
                success=False,
                error=str(e),
                message=f"Failed to close position: {symbol}"
            )

    def close_all_positions(self) -> List[TradeResult]:
        """Close all open positions"""
        try:
            data = self._request("DELETE", "positions")
            results = []
            for order_data in data:
                order = AlpacaOrder.from_api_response(order_data)
                results.append(TradeResult(
                    success=True,
                    order=order,
                    message=f"Closed: {order.symbol}"
                ))
            return results
        except Exception as e:
            return [TradeResult(
                success=False,
                error=str(e),
                message="Failed to close all positions"
            )]

    # ==================== Orders ====================

    def get_orders(
        self,
        status: str = "open",
        limit: int = 50,
        symbols: List[str] = None
    ) -> List[AlpacaOrder]:
        """Get orders"""
        params = {
            "status": status,
            "limit": limit,
        }
        if symbols:
            params["symbols"] = ",".join(symbols)

        data = self._request("GET", "orders", params=params)
        return [AlpacaOrder.from_api_response(o) for o in data]

    def get_order(self, order_id: str) -> AlpacaOrder:
        """Get a specific order by ID"""
        data = self._request("GET", f"orders/{order_id}")
        return AlpacaOrder.from_api_response(data)

    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSide,
        order_type: OrderType = OrderType.MARKET,
        time_in_force: TimeInForce = TimeInForce.DAY,
        limit_price: float = None,
        stop_price: float = None,
        client_order_id: str = None,
    ) -> TradeResult:
        """
        Submit a new order.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: 'buy' or 'sell'
            order_type: Market, limit, stop, etc.
            time_in_force: Day, GTC, IOC, etc.
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            client_order_id: Custom order ID

        Returns:
            TradeResult with order details
        """
        try:
            order_data = {
                "symbol": symbol.upper(),
                "qty": str(qty),
                "side": side.value if isinstance(side, OrderSide) else side,
                "type": order_type.value if isinstance(order_type, OrderType) else order_type,
                "time_in_force": time_in_force.value if isinstance(time_in_force, TimeInForce) else time_in_force,
            }

            if limit_price is not None:
                order_data["limit_price"] = str(limit_price)

            if stop_price is not None:
                order_data["stop_price"] = str(stop_price)

            if client_order_id:
                order_data["client_order_id"] = client_order_id

            data = self._request("POST", "orders", data=order_data)
            order = AlpacaOrder.from_api_response(data)

            return TradeResult(
                success=True,
                order=order,
                message=f"Order submitted: {side.value if isinstance(side, OrderSide) else side} {qty} {symbol}"
            )
        except Exception as e:
            return TradeResult(
                success=False,
                error=str(e),
                message=f"Failed to submit order: {symbol}"
            )

    def cancel_order(self, order_id: str) -> TradeResult:
        """Cancel an order"""
        try:
            self._request("DELETE", f"orders/{order_id}")
            return TradeResult(
                success=True,
                message=f"Order cancelled: {order_id}"
            )
        except Exception as e:
            return TradeResult(
                success=False,
                error=str(e),
                message=f"Failed to cancel order: {order_id}"
            )

    def cancel_all_orders(self) -> TradeResult:
        """Cancel all open orders"""
        try:
            self._request("DELETE", "orders")
            return TradeResult(
                success=True,
                message="All orders cancelled"
            )
        except Exception as e:
            return TradeResult(
                success=False,
                error=str(e),
                message="Failed to cancel all orders"
            )

    # ==================== Trading Actions ====================

    def buy(
        self,
        symbol: str,
        qty: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float = None
    ) -> TradeResult:
        """
        Buy shares of a stock.

        Args:
            symbol: Stock symbol
            qty: Number of shares to buy
            order_type: Market or limit
            limit_price: Price for limit orders

        Returns:
            TradeResult
        """
        return self.submit_order(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            order_type=order_type,
            limit_price=limit_price,
        )

    def sell(
        self,
        symbol: str,
        qty: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float = None
    ) -> TradeResult:
        """
        Sell shares of a stock.

        Args:
            symbol: Stock symbol
            qty: Number of shares to sell
            order_type: Market or limit
            limit_price: Price for limit orders

        Returns:
            TradeResult
        """
        return self.submit_order(
            symbol=symbol,
            qty=qty,
            side=OrderSide.SELL,
            order_type=order_type,
            limit_price=limit_price,
        )

    def short(
        self,
        symbol: str,
        qty: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float = None
    ) -> TradeResult:
        """
        Short sell shares of a stock.

        Args:
            symbol: Stock symbol
            qty: Number of shares to short
            order_type: Market or limit
            limit_price: Price for limit orders

        Returns:
            TradeResult
        """
        # Short selling is just a sell order when you don't own the shares
        return self.submit_order(
            symbol=symbol,
            qty=qty,
            side=OrderSide.SELL,
            order_type=order_type,
            limit_price=limit_price,
        )

    def cover(
        self,
        symbol: str,
        qty: float = None,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float = None
    ) -> TradeResult:
        """
        Cover (buy back) a short position.

        Args:
            symbol: Stock symbol
            qty: Number of shares to cover (None = cover all)
            order_type: Market or limit
            limit_price: Price for limit orders

        Returns:
            TradeResult
        """
        # If qty not specified, get current short position
        if qty is None:
            position = self.get_position(symbol)
            if position and position.side == "short":
                qty = abs(position.qty)
            else:
                return TradeResult(
                    success=False,
                    error="No short position found",
                    message=f"No short position to cover for {symbol}"
                )

        return self.submit_order(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            order_type=order_type,
            limit_price=limit_price,
        )

    # ==================== Portfolio Manager Integration ====================

    def execute_decision(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: OrderType = OrderType.MARKET
    ) -> TradeResult:
        """
        Execute a trading decision from the Portfolio Manager.

        Maps AI Hedge Fund actions to Alpaca orders:
        - buy: Buy shares (long)
        - sell: Sell long position
        - short: Short sell
        - cover: Cover short position
        - hold: No action

        Args:
            symbol: Stock symbol
            action: Trading action (buy, sell, short, cover, hold)
            quantity: Number of shares
            order_type: Order type (market, limit)

        Returns:
            TradeResult
        """
        action = action.lower()

        if action == "hold" or quantity <= 0:
            return TradeResult(
                success=True,
                message=f"No action taken for {symbol} (hold)"
            )

        if action == "buy":
            return self.buy(symbol, quantity, order_type)
        elif action == "sell":
            return self.sell(symbol, quantity, order_type)
        elif action == "short":
            return self.short(symbol, quantity, order_type)
        elif action == "cover":
            return self.cover(symbol, quantity, order_type)
        else:
            return TradeResult(
                success=False,
                error=f"Unknown action: {action}",
                message=f"Invalid action '{action}' for {symbol}"
            )

    def sync_portfolio(self) -> Dict[str, Any]:
        """
        Get current portfolio state from Alpaca.

        Returns a portfolio dict compatible with AI Hedge Fund format.
        """
        account = self.get_account()
        positions = self.get_positions()

        portfolio = {
            "cash": account.cash,
            "buying_power": account.buying_power,
            "portfolio_value": account.portfolio_value,
            "equity": account.equity,
            "margin_requirement": 0.5,  # Default 50% margin
            "margin_used": account.initial_margin,
            "positions": {},
            "realized_gains": {},
        }

        for pos in positions:
            portfolio["positions"][pos.symbol] = {
                "long": pos.qty if pos.side == "long" else 0,
                "short": abs(pos.qty) if pos.side == "short" else 0,
                "long_cost_basis": pos.cost_basis if pos.side == "long" else 0,
                "short_cost_basis": pos.cost_basis if pos.side == "short" else 0,
                "short_margin_used": abs(pos.market_value) * 0.5 if pos.side == "short" else 0,
                "current_price": pos.current_price,
                "market_value": pos.market_value,
                "unrealized_pl": pos.unrealized_pl,
                "unrealized_plpc": pos.unrealized_plpc,
            }
            portfolio["realized_gains"][pos.symbol] = {
                "long": 0.0,  # Not available from position data
                "short": 0.0,
            }

        return portfolio

    def get_status(self) -> Dict[str, Any]:
        """Get trading service status"""
        try:
            account = self.get_account()
            return {
                "connected": True,
                "mode": "paper" if self.paper else "live",
                "account_status": account.status,
                "trading_blocked": account.trading_blocked,
                "buying_power": account.buying_power,
                "cash": account.cash,
                "portfolio_value": account.portfolio_value,
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
            }


# Convenience functions

def get_alpaca_service() -> AlpacaService:
    """Get a configured Alpaca service instance"""
    return AlpacaService()


def execute_trade(
    symbol: str,
    action: str,
    quantity: int
) -> TradeResult:
    """Execute a trade using the default Alpaca service"""
    service = get_alpaca_service()
    return service.execute_decision(symbol, action, quantity)


if __name__ == "__main__":
    # Test the service
    import json

    service = AlpacaService()

    print("=" * 60)
    print("ALPACA TRADING SERVICE TEST")
    print("=" * 60)

    # Get status
    status = service.get_status()
    print(f"\nStatus: {json.dumps(status, indent=2)}")

    # Get account
    account = service.get_account()
    print(f"\nAccount:")
    print(f"  Status: {account.status}")
    print(f"  Cash: ${account.cash:,.2f}")
    print(f"  Buying Power: ${account.buying_power:,.2f}")
    print(f"  Portfolio Value: ${account.portfolio_value:,.2f}")
    print(f"  Mode: {'Paper' if service.paper else 'Live'}")

    # Get positions
    positions = service.get_positions()
    print(f"\nPositions: {len(positions)}")
    for pos in positions:
        print(f"  {pos.symbol}: {pos.qty} shares @ ${pos.avg_entry_price:.2f}")

    # Get open orders
    orders = service.get_orders(status="open")
    print(f"\nOpen Orders: {len(orders)}")
    for order in orders:
        print(f"  {order.symbol}: {order.side} {order.qty} ({order.status})")

    print("\n" + "=" * 60)
