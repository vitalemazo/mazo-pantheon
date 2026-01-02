"""
Tests for AlpacaService - quotes, PDT checks, and asset info.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestGetQuote:
    """Tests for AlpacaService.get_quote()"""
    
    def test_get_quote_success(self):
        """Test successful quote fetch."""
        from src.trading.alpaca_service import AlpacaService
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "quote": {
                "bp": 150.00,  # bid price
                "ap": 150.05,  # ask price
                "bs": 100,     # bid size
                "as": 200,     # ask size
                "t": "2024-01-01T10:00:00Z"
            }
        }
        
        with patch('src.trading.alpaca_service.requests.get', return_value=mock_response):
            service = AlpacaService.__new__(AlpacaService)
            service.api_key = "test-key"
            service.secret_key = "test-secret"
            service.base_url = "https://paper-api.alpaca.markets/v2"
            
            quote = service.get_quote("AAPL")
            
            assert quote is not None
            assert quote["symbol"] == "AAPL"
            assert quote["bid"] == 150.00
            assert quote["ask"] == 150.05
            assert quote["last"] == 150.025  # midpoint
            assert quote["bid_size"] == 100
            assert quote["ask_size"] == 200
    
    def test_get_quote_api_error(self):
        """Test quote returns None on API error."""
        from src.trading.alpaca_service import AlpacaService
        
        mock_response = Mock()
        mock_response.status_code = 404
        
        with patch('src.trading.alpaca_service.requests.get', return_value=mock_response):
            service = AlpacaService.__new__(AlpacaService)
            service.api_key = "test-key"
            service.secret_key = "test-secret"
            service.base_url = "https://paper-api.alpaca.markets/v2"
            
            quote = service.get_quote("INVALID")
            
            assert quote is None
    
    def test_get_quote_network_error(self):
        """Test quote returns None on network error."""
        from src.trading.alpaca_service import AlpacaService
        
        with patch('src.trading.alpaca_service.requests.get', side_effect=Exception("Network error")):
            service = AlpacaService.__new__(AlpacaService)
            service.api_key = "test-key"
            service.secret_key = "test-secret"
            service.base_url = "https://paper-api.alpaca.markets/v2"
            
            quote = service.get_quote("AAPL")
            
            assert quote is None


class TestGetLastTrade:
    """Tests for AlpacaService.get_last_trade()"""
    
    def test_get_last_trade_success(self):
        """Test successful last trade fetch."""
        from src.trading.alpaca_service import AlpacaService
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "trade": {
                "p": 150.50,  # price
                "s": 100,     # size
                "t": "2024-01-01T10:00:00Z"
            }
        }
        
        with patch('src.trading.alpaca_service.requests.get', return_value=mock_response):
            service = AlpacaService.__new__(AlpacaService)
            service.api_key = "test-key"
            service.secret_key = "test-secret"
            service.base_url = "https://paper-api.alpaca.markets/v2"
            
            trade = service.get_last_trade("AAPL")
            
            assert trade is not None
            assert trade["symbol"] == "AAPL"
            assert trade["price"] == 150.50
            assert trade["size"] == 100


class TestGetCurrentPrice:
    """Tests for AlpacaService.get_current_price()"""
    
    def test_get_current_price_from_trade(self):
        """Test current price uses last trade when available."""
        from src.trading.alpaca_service import AlpacaService
        
        service = AlpacaService.__new__(AlpacaService)
        service.api_key = "test-key"
        service.secret_key = "test-secret"
        service.base_url = "https://paper-api.alpaca.markets/v2"
        
        # Mock get_last_trade to return a price
        service.get_last_trade = Mock(return_value={"price": 155.00})
        service.get_quote = Mock()  # Should not be called
        
        price = service.get_current_price("AAPL")
        
        assert price == 155.00
        service.get_last_trade.assert_called_once_with("AAPL")
        service.get_quote.assert_not_called()
    
    def test_get_current_price_fallback_to_quote(self):
        """Test current price falls back to quote midpoint."""
        from src.trading.alpaca_service import AlpacaService
        
        service = AlpacaService.__new__(AlpacaService)
        service.api_key = "test-key"
        service.secret_key = "test-secret"
        service.base_url = "https://paper-api.alpaca.markets/v2"
        
        # Mock get_last_trade to return None
        service.get_last_trade = Mock(return_value=None)
        service.get_quote = Mock(return_value={"bid": 150.00, "ask": 150.10})
        service.get_position = Mock(return_value=None)
        
        price = service.get_current_price("AAPL")
        
        assert price == 150.05  # midpoint
        service.get_quote.assert_called_once_with("AAPL")


class TestCheckPDTStatus:
    """Tests for AlpacaService.check_pdt_status()"""
    
    def test_pdt_no_restrictions_high_equity(self):
        """Test no PDT restrictions with equity >= $25k."""
        from src.trading.alpaca_service import AlpacaService, AlpacaAccount
        
        service = AlpacaService.__new__(AlpacaService)
        
        # Mock account with high equity
        mock_account = AlpacaAccount(
            id="test",
            status="ACTIVE",
            currency="USD",
            cash=30000.0,
            portfolio_value=50000.0,
            equity=50000.0,
            buying_power=100000.0,
            initial_margin=0,
            maintenance_margin=0,
            pattern_day_trader=False,
            trading_blocked=False,
            shorting_enabled=True,
            daytrade_count=5,  # Even with 5 day trades
            multiplier="2"
        )
        service.get_account = Mock(return_value=mock_account)
        
        status = service.check_pdt_status()
        
        assert status["can_day_trade"] is True
        assert status["equity"] == 50000.0
        assert status["warning"] is None
    
    def test_pdt_blocked_low_equity_at_limit(self):
        """Test PDT blocked with equity < $25k and 3+ day trades."""
        from src.trading.alpaca_service import AlpacaService, AlpacaAccount
        
        service = AlpacaService.__new__(AlpacaService)
        
        # Mock account with low equity and at day trade limit
        mock_account = AlpacaAccount(
            id="test",
            status="ACTIVE",
            currency="USD",
            cash=5000.0,
            portfolio_value=5000.0,
            equity=5000.0,
            buying_power=10000.0,
            initial_margin=0,
            maintenance_margin=0,
            pattern_day_trader=False,
            trading_blocked=False,
            shorting_enabled=True,
            daytrade_count=3,  # At the limit
            multiplier="2"
        )
        service.get_account = Mock(return_value=mock_account)
        
        status = service.check_pdt_status()
        
        assert status["can_day_trade"] is False
        assert status["daytrade_count"] == 3
        assert "3/3" in status["warning"] or "3 day trades" in status["warning"].lower()
    
    def test_pdt_warning_approaching_limit(self):
        """Test PDT warning when approaching limit."""
        from src.trading.alpaca_service import AlpacaService, AlpacaAccount
        
        service = AlpacaService.__new__(AlpacaService)
        
        # Mock account approaching limit
        mock_account = AlpacaAccount(
            id="test",
            status="ACTIVE",
            currency="USD",
            cash=10000.0,
            portfolio_value=10000.0,
            equity=10000.0,
            buying_power=20000.0,
            initial_margin=0,
            maintenance_margin=0,
            pattern_day_trader=False,
            trading_blocked=False,
            shorting_enabled=True,
            daytrade_count=2,  # Approaching limit
            multiplier="2"
        )
        service.get_account = Mock(return_value=mock_account)
        
        status = service.check_pdt_status()
        
        assert status["can_day_trade"] is True  # Still allowed
        assert status["warning"] is not None  # But with warning
        assert "2" in status["warning"]
    
    def test_pdt_flagged_restricted(self):
        """Test PDT restricted when already flagged."""
        from src.trading.alpaca_service import AlpacaService, AlpacaAccount
        
        service = AlpacaService.__new__(AlpacaService)
        
        # Mock account already PDT flagged with low equity
        mock_account = AlpacaAccount(
            id="test",
            status="ACTIVE",
            currency="USD",
            cash=5000.0,
            portfolio_value=5000.0,
            equity=5000.0,
            buying_power=10000.0,
            initial_margin=0,
            maintenance_margin=0,
            pattern_day_trader=True,  # Already flagged
            trading_blocked=False,
            shorting_enabled=True,
            daytrade_count=0,
            multiplier="2"
        )
        service.get_account = Mock(return_value=mock_account)
        
        status = service.check_pdt_status()
        
        assert status["can_day_trade"] is False
        assert status["is_pdt"] is True
        assert "PDT flagged" in status["warning"]


class TestAssetInfo:
    """Tests for asset info and fractionable detection."""
    
    def test_is_fractionable_true(self):
        """Test fractionable detection for supported asset."""
        from src.trading.alpaca_service import AlpacaService, AssetInfo
        
        service = AlpacaService.__new__(AlpacaService)
        service.api_key = "test-key"
        service.secret_key = "test-secret"
        service.base_url = "https://paper-api.alpaca.markets/v2"
        
        # Mock get_asset to return fractionable
        service.get_asset = Mock(return_value=AssetInfo(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            asset_class="us_equity",
            fractionable=True,
            tradable=True,
            marginable=True,
            shortable=True,
            min_order_size=None,
            min_trade_increment=None
        ))
        
        assert service.is_fractionable("AAPL") is True
    
    def test_is_fractionable_false(self):
        """Test fractionable detection for unsupported asset."""
        from src.trading.alpaca_service import AlpacaService, AssetInfo
        
        service = AlpacaService.__new__(AlpacaService)
        service.api_key = "test-key"
        service.secret_key = "test-secret"
        service.base_url = "https://paper-api.alpaca.markets/v2"
        
        # Mock get_asset to return non-fractionable
        service.get_asset = Mock(return_value=AssetInfo(
            symbol="BRK.A",
            name="Berkshire Hathaway",
            exchange="NYSE",
            asset_class="us_equity",
            fractionable=False,
            tradable=True,
            marginable=True,
            shortable=True,
            min_order_size=None,
            min_trade_increment=None
        ))
        
        assert service.is_fractionable("BRK.A") is False
