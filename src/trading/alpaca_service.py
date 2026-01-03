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
import time
import requests
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


# Lazy import for monitoring to avoid circular imports
_rate_limit_monitor = None


def _get_rate_limit_monitor():
    """Lazy load the rate limit monitor."""
    global _rate_limit_monitor
    if _rate_limit_monitor is None:
        try:
            from src.monitoring import get_rate_limit_monitor
            _rate_limit_monitor = get_rate_limit_monitor()
        except Exception:
            pass
    return _rate_limit_monitor


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


@dataclass
class AssetInfo:
    """Asset information from Alpaca including fractionable status"""
    symbol: str
    name: str
    exchange: str
    asset_class: str
    tradable: bool
    fractionable: bool
    marginable: bool
    shortable: bool
    easy_to_borrow: bool
    min_order_size: float = 1.0
    min_trade_increment: float = 1.0
    price_increment: float = 0.01
    
    @classmethod
    def from_api_response(cls, data: Dict) -> "AssetInfo":
        return cls(
            symbol=data.get("symbol", ""),
            name=data.get("name", ""),
            exchange=data.get("exchange", ""),
            asset_class=data.get("class", "us_equity"),
            tradable=data.get("tradable", False),
            fractionable=data.get("fractionable", False),
            marginable=data.get("marginable", False),
            shortable=data.get("shortable", False),
            easy_to_borrow=data.get("easy_to_borrow", False),
            min_order_size=float(data.get("min_order_size", 1)),
            min_trade_increment=float(data.get("min_trade_increment", 1)),
            price_increment=float(data.get("price_increment", 0.01)),
        )


# Asset cache for fractionable lookups (in-memory, cleared on restart)
_asset_cache: Dict[str, AssetInfo] = {}


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
        # Try to get credentials from database first (Settings UI), then fall back to env vars
        self.api_key = api_key or self._get_key_from_db("ALPACA_API_KEY") or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or self._get_key_from_db("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY")

        if base_url:
            self.base_url = base_url
        else:
            db_base_url = self._get_key_from_db("ALPACA_BASE_URL")
            env_base_url = os.environ.get("ALPACA_BASE_URL")
            if db_base_url:
                self.base_url = db_base_url
            elif env_base_url:
                self.base_url = env_base_url
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

    @staticmethod
    def _get_key_from_db(key_name: str) -> Optional[str]:
        """Try to get an API key from the database (Settings UI)."""
        try:
            from sqlalchemy import create_engine, text
            db_url = os.environ.get("DATABASE_URL", "postgresql://mazo:mazo@mazo-postgres:5432/mazo_pantheon")
            engine = create_engine(db_url)
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT key_value FROM api_keys WHERE provider = :key AND is_active = true"),
                    {"key": key_name}
                )
                row = result.fetchone()
                if row and row[0]:
                    return row[0]
        except Exception:
            pass  # Fall back to env vars
        return None

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
        """Make API request with monitoring."""
        url = f"{self.base_url}/{endpoint}"
        rate_monitor = _get_rate_limit_monitor()
        
        # Determine call type from endpoint for telemetry
        call_type = self._get_call_type(endpoint)
        
        start_time = time.time()
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                params=params,
                json=data,
            )
            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 429:
                # Rate limited
                if rate_monitor:
                    retry_after = response.headers.get("Retry-After")
                    rate_monitor.record_rate_limit_hit(
                        "alpaca",
                        retry_after=int(retry_after) if retry_after else None
                    )
                raise Exception(f"Alpaca API rate limited (429)")

            if response.status_code >= 400:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", response.text)
                except (ValueError, KeyError):
                    pass  # Keep original error_msg if JSON parsing fails
                
                # Log failed call
                if rate_monitor:
                    rate_monitor.record_call(
                        "alpaca",
                        call_type=call_type,
                        success=False,
                        latency_ms=latency_ms,
                    )
                raise Exception(f"Alpaca API error ({response.status_code}): {error_msg}")

            # Log successful call with rate limit headers
            if rate_monitor:
                remaining = response.headers.get("X-RateLimit-Remaining")
                rate_monitor.record_call(
                    "alpaca",
                    call_type=call_type,
                    success=True,
                    rate_limit_remaining=int(remaining) if remaining else None,
                    latency_ms=latency_ms,
                )

            if response.text:
                return response.json()
            return {}
            
        except requests.exceptions.RequestException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            if rate_monitor:
                rate_monitor.record_call(
                    "alpaca",
                    call_type=call_type,
                    success=False,
                    latency_ms=latency_ms,
                )
            raise
    
    def _get_call_type(self, endpoint: str) -> str:
        """Map endpoint to call type for telemetry."""
        endpoint_lower = endpoint.lower()
        if "orders" in endpoint_lower:
            return "orders"
        elif "positions" in endpoint_lower:
            return "positions"
        elif "account" in endpoint_lower:
            return "account"
        elif "assets" in endpoint_lower:
            return "assets"
        elif "clock" in endpoint_lower:
            return "clock"
        elif "calendar" in endpoint_lower:
            return "calendar"
        elif "watchlist" in endpoint_lower:
            return "watchlist"
        elif "activities" in endpoint_lower:
            return "activities"
        else:
            return "general"

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

    def check_pdt_status(self) -> Dict[str, Any]:
        """
        Check Pattern Day Trader status and limits.
        
        Returns:
            Dict with:
            - is_pdt: bool - Account flagged as PDT
            - daytrade_count: int - Day trades in rolling 5 days
            - equity: float - Account equity
            - can_day_trade: bool - Whether new day trades are allowed
            - warning: str or None - Warning message if near limit
        """
        account = self.get_account()
        
        equity = account.equity
        is_pdt = account.pattern_day_trader
        daytrade_count = account.daytrade_count
        
        # PDT rules:
        # - If equity >= $25k, no restrictions
        # - If equity < $25k and not PDT flagged, max 3 day trades in 5 business days
        # - If PDT flagged and equity < $25k, account is restricted
        
        can_day_trade = True
        warning = None
        
        if equity >= 25000:
            # No PDT restrictions with $25k+ equity
            can_day_trade = True
        elif is_pdt:
            # Already flagged as PDT with < $25k - restricted
            can_day_trade = False
            warning = f"PDT flagged with ${equity:,.2f} equity (< $25k). Day trading restricted."
        elif daytrade_count >= 3:
            # Would trigger PDT if one more day trade
            can_day_trade = False
            warning = f"At {daytrade_count}/3 day trades in 5 days. One more would trigger PDT flag."
        elif daytrade_count >= 2:
            # Warning - approaching limit
            warning = f"At {daytrade_count}/3 day trades. Approaching PDT limit."
        
        return {
            "is_pdt": is_pdt,
            "daytrade_count": daytrade_count,
            "equity": equity,
            "can_day_trade": can_day_trade,
            "warning": warning,
            "pdt_threshold": 25000,
        }

    # ==================== Assets ====================

    def get_asset(self, symbol: str, use_cache: bool = True) -> Optional[AssetInfo]:
        """
        Get asset information including fractionable status.
        
        Args:
            symbol: Stock symbol
            use_cache: If True, use cached asset info if available
            
        Returns:
            AssetInfo with tradable, fractionable, etc. flags
        """
        symbol = symbol.upper()
        
        # Check cache first
        if use_cache and symbol in _asset_cache:
            return _asset_cache[symbol]
        
        try:
            data = self._request("GET", f"assets/{symbol}")
            asset = AssetInfo.from_api_response(data)
            
            # Cache for future lookups
            _asset_cache[symbol] = asset
            
            return asset
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                return None
            print(f"[Alpaca] ⚠️ Error fetching asset info for {symbol}: {e}")
            return None

    def is_fractionable(self, symbol: str) -> bool:
        """
        Check if a symbol supports fractional trading.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if fractional trading is supported, False otherwise
        """
        asset = self.get_asset(symbol)
        if asset is None:
            # Unknown asset - assume not fractionable for safety
            print(f"[Alpaca] ⚠️ Could not determine if {symbol} is fractionable, assuming no")
            return False
        return asset.fractionable

    def clear_asset_cache(self):
        """Clear the asset info cache."""
        global _asset_cache
        _asset_cache.clear()

    # ==================== Market Data (Quotes) ====================

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get latest quote for a symbol.
        
        Uses Alpaca's data API for real-time quotes.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with bid, ask, last, timestamp, or None on error
        """
        symbol = symbol.upper()
        
        try:
            # Use the market data API endpoint
            # Paper trading uses the same data API as live
            data_url = "https://data.alpaca.markets/v2"
            
            response = requests.get(
                f"{data_url}/stocks/{symbol}/quotes/latest",
                headers=self._headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                quote = data.get("quote", {})
                
                return {
                    "symbol": symbol,
                    "bid": float(quote.get("bp", 0)),
                    "ask": float(quote.get("ap", 0)),
                    "bid_size": int(quote.get("bs", 0)),
                    "ask_size": int(quote.get("as", 0)),
                    "last": float(quote.get("bp", 0) + quote.get("ap", 0)) / 2 if quote.get("bp") else None,
                    "timestamp": quote.get("t"),
                }
            else:
                print(f"[Alpaca] ⚠️ Quote API returned {response.status_code} for {symbol}")
                return None
                
        except Exception as e:
            print(f"[Alpaca] ⚠️ Error fetching quote for {symbol}: {e}")
            return None

    def get_last_trade(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get last trade for a symbol (more reliable than quotes for last price).
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with price, size, timestamp, or None on error
        """
        symbol = symbol.upper()
        
        try:
            data_url = "https://data.alpaca.markets/v2"
            
            response = requests.get(
                f"{data_url}/stocks/{symbol}/trades/latest",
                headers=self._headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                trade = data.get("trade", {})
                
                return {
                    "symbol": symbol,
                    "price": float(trade.get("p", 0)),
                    "size": int(trade.get("s", 0)),
                    "timestamp": trade.get("t"),
                }
            else:
                print(f"[Alpaca] ⚠️ Trade API returned {response.status_code} for {symbol}")
                return None
                
        except Exception as e:
            print(f"[Alpaca] ⚠️ Error fetching last trade for {symbol}: {e}")
            return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol using best available method.
        
        Tries last trade first, then quote midpoint.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Current price or None
        """
        # Try last trade first (most accurate)
        trade = self.get_last_trade(symbol)
        if trade and trade.get("price"):
            return trade["price"]
        
        # Fallback to quote midpoint
        quote = self.get_quote(symbol)
        if quote and quote.get("bid") and quote.get("ask"):
            return (quote["bid"] + quote["ask"]) / 2
        
        # Try position current price
        try:
            position = self.get_position(symbol)
            if position and position.current_price:
                return position.current_price
        except Exception:
            pass
        
        return None

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

        Supports fractional shares for fractionable assets.
        Non-fractionable assets will be automatically rounded to whole shares.

        Args:
            symbol: Stock symbol
            qty: Number of shares (supports fractional)
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
            from src.trading.config import get_fractional_config
            
            fractional_config = get_fractional_config()
            symbol = symbol.upper()
            
            # Round quantity to Alpaca's precision (4 decimal places)
            qty = round(float(qty), fractional_config.fractional_precision)
            
            # Check if fractional trading is enabled and quantity is fractional
            is_fractional = qty != int(qty)
            original_qty = qty
            
            if is_fractional and not fractional_config.allow_fractional:
                # Fractional disabled globally - round to whole shares
                qty = max(1, int(qty))
                print(f"[Alpaca] ⚠️ Fractional trading disabled. Rounded {original_qty:.4f} → {qty} shares for {symbol}")
                is_fractional = False
            
            # Check if asset is fractionable before attempting fractional order
            if is_fractional and fractional_config.allow_fractional:
                asset_fractionable = self.is_fractionable(symbol)
                if not asset_fractionable:
                    # Asset doesn't support fractional - round to whole shares
                    qty = max(1, int(qty))
                    print(f"[Alpaca] ⚠️ Asset {symbol} not fractionable. Rounded {original_qty:.4f} → {qty} shares")
                    is_fractional = False
            
            # For fractional orders, Alpaca requires market orders with DAY time in force
            if is_fractional:
                if order_type != OrderType.MARKET:
                    print(f"[Alpaca] ⚠️ Fractional orders require market order type. Converting from {order_type.value}")
                    order_type = OrderType.MARKET
                if time_in_force != TimeInForce.DAY:
                    print(f"[Alpaca] ⚠️ Fractional orders require DAY time in force. Converting from {time_in_force.value}")
                    time_in_force = TimeInForce.DAY
            
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
            
            # Log fractional order success
            qty_display = f"{qty:.4f}" if is_fractional else str(int(qty))

            return TradeResult(
                success=True,
                order=order,
                message=f"Order submitted: {side.value if isinstance(side, OrderSide) else side} {qty_display} {symbol}"
            )
        except Exception as e:
            error_msg = str(e)
            
            # Check if error is due to non-fractionable asset
            if "fractional" in error_msg.lower() or "not fractionable" in error_msg.lower():
                # Retry with whole shares
                whole_qty = max(1, int(qty))
                print(f"[Alpaca] ⚠️ Asset {symbol} not fractionable. Retrying with {whole_qty} whole shares")
                try:
                    order_data["qty"] = str(whole_qty)
                    data = self._request("POST", "orders", data=order_data)
                    order = AlpacaOrder.from_api_response(data)
                    return TradeResult(
                        success=True,
                        order=order,
                        message=f"Order submitted (rounded): {side.value if isinstance(side, OrderSide) else side} {whole_qty} {symbol}"
                    )
                except Exception as retry_error:
                    error_msg = str(retry_error)
            
            print(f"[Alpaca] ❌ Order error for {symbol}: {error_msg}")
            return TradeResult(
                success=False,
                error=error_msg,
                message=f"Failed to submit order for {symbol}: {error_msg}"
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
        quantity: float,
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

        Supports fractional shares for fractionable assets.
        Non-fractionable assets will be rounded to whole shares.

        Args:
            symbol: Stock symbol
            action: Trading action (buy, sell, short, cover, hold)
            quantity: Number of shares (supports fractional)
            order_type: Order type (market, limit)

        Returns:
            TradeResult
        """
        action = action.lower()

        # Round quantity to 4 decimal places (Alpaca's precision)
        quantity = round(float(quantity), 4)

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
    quantity: float
) -> TradeResult:
    """Execute a trade using the default Alpaca service.
    
    Args:
        symbol: Stock symbol
        action: Trade action (buy, sell, short, cover)
        quantity: Number of shares (supports fractional)
    """
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
