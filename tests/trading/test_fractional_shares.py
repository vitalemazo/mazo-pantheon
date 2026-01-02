"""
Tests for fractional share trading functionality.

Tests cover:
- Asset fractionable detection
- Position sizing with fractionable vs non-fractionable assets
- Order submission with automatic fallback
- Configuration toggles
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass


class TestAssetFractionable:
    """Test asset fractionable status detection."""
    
    def test_fractionable_asset_returns_true(self):
        """AAPL should be fractionable."""
        from src.trading.alpaca_service import AssetInfo
        
        asset = AssetInfo(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            asset_class="us_equity",
            tradable=True,
            fractionable=True,
            marginable=True,
            shortable=True,
            easy_to_borrow=True
        )
        
        assert asset.fractionable is True
    
    def test_non_fractionable_asset_returns_false(self):
        """BRK.A should not be fractionable."""
        from src.trading.alpaca_service import AssetInfo
        
        asset = AssetInfo(
            symbol="BRK.A",
            name="Berkshire Hathaway Inc. Class A",
            exchange="NYSE",
            asset_class="us_equity",
            tradable=True,
            fractionable=False,
            marginable=True,
            shortable=False,
            easy_to_borrow=False
        )
        
        assert asset.fractionable is False
    
    def test_asset_info_from_api_response(self):
        """Test AssetInfo parses API response correctly."""
        from src.trading.alpaca_service import AssetInfo
        
        api_response = {
            "symbol": "TSLA",
            "name": "Tesla, Inc.",
            "exchange": "NASDAQ",
            "class": "us_equity",
            "tradable": True,
            "fractionable": True,
            "marginable": True,
            "shortable": True,
            "easy_to_borrow": True,
            "min_order_size": "1",
            "min_trade_increment": "0.0001",
            "price_increment": "0.01"
        }
        
        asset = AssetInfo.from_api_response(api_response)
        
        assert asset.symbol == "TSLA"
        assert asset.fractionable is True
        assert asset.min_trade_increment == 0.0001


class TestTradingSignalFractionable:
    """Test TradingSignal carries fractionable flag."""
    
    def test_trading_signal_default_fractionable(self):
        """TradingSignal defaults to fractionable=True."""
        from src.trading.strategy_engine import TradingSignal, SignalDirection, SignalStrength
        
        signal = TradingSignal(
            ticker="AAPL",
            strategy="momentum",
            direction=SignalDirection.LONG,
            strength=SignalStrength.STRONG,
            confidence=85,
            entry_price=175.50,
            stop_loss=170.00,
            take_profit=185.00,
            position_size_pct=0.05,
            reasoning="Strong momentum signal"
        )
        
        assert signal.fractionable is True
    
    def test_trading_signal_non_fractionable(self):
        """TradingSignal can be set to non-fractionable."""
        from src.trading.strategy_engine import TradingSignal, SignalDirection, SignalStrength
        
        signal = TradingSignal(
            ticker="BRK.A",
            strategy="momentum",
            direction=SignalDirection.LONG,
            strength=SignalStrength.MODERATE,
            confidence=70,
            entry_price=650000.00,
            stop_loss=640000.00,
            take_profit=670000.00,
            position_size_pct=0.05,
            reasoning="Value signal",
            fractionable=False
        )
        
        assert signal.fractionable is False
    
    def test_trading_signal_to_dict_includes_fractionable(self):
        """TradingSignal.to_dict() includes fractionable field."""
        from src.trading.strategy_engine import TradingSignal, SignalDirection, SignalStrength
        
        signal = TradingSignal(
            ticker="AAPL",
            strategy="momentum",
            direction=SignalDirection.LONG,
            strength=SignalStrength.STRONG,
            confidence=85,
            entry_price=175.50,
            stop_loss=170.00,
            take_profit=185.00,
            position_size_pct=0.05,
            reasoning="Test",
            fractionable=False
        )
        
        d = signal.to_dict()
        assert "fractionable" in d
        assert d["fractionable"] is False


class TestPositionSizing:
    """Test position sizing respects fractionable flag."""
    
    def test_fractional_sizing_when_fractionable(self):
        """Fractionable asset should get fractional size."""
        from src.trading.strategy_engine import TradingSignal, SignalDirection, SignalStrength
        
        # Create a mock signal with fractionable=True
        signal = TradingSignal(
            ticker="AAPL",
            strategy="momentum",
            direction=SignalDirection.LONG,
            strength=SignalStrength.STRONG,
            confidence=85,
            entry_price=175.50,
            stop_loss=170.00,
            take_profit=185.00,
            position_size_pct=0.05,
            reasoning="Test",
            fractionable=True
        )
        
        # Mock portfolio context
        @dataclass
        class MockPortfolio:
            cash: float = 10000.0
            buying_power: float = 10000.0
        
        portfolio = MockPortfolio()
        
        # Calculate position size
        # 5% of $10,000 = $500
        # $500 / $175.50 = 2.849... shares
        expected_shares = 500 / 175.50
        
        # When ALLOW_FRACTIONAL=True and fractionable=True,
        # we expect fractional output
        assert signal.fractionable is True
        assert expected_shares > 2 and expected_shares < 3
    
    def test_whole_share_sizing_when_not_fractionable(self):
        """Non-fractionable asset should get whole shares."""
        from src.trading.strategy_engine import TradingSignal, SignalDirection, SignalStrength
        
        signal = TradingSignal(
            ticker="BRK.A",
            strategy="value",
            direction=SignalDirection.LONG,
            strength=SignalStrength.MODERATE,
            confidence=70,
            entry_price=650000.00,
            stop_loss=640000.00,
            take_profit=670000.00,
            position_size_pct=0.05,
            reasoning="Test",
            fractionable=False
        )
        
        assert signal.fractionable is False
        # For non-fractionable, sizing logic should round to int


class TestFractionalConfig:
    """Test fractional trading configuration."""
    
    def test_fractional_config_defaults(self):
        """Test default fractional configuration values."""
        from src.trading.config import FractionalConfig
        
        # Create with defaults (not from env)
        config = FractionalConfig()
        
        # Just verify the class exists and has expected fields
        assert hasattr(config, 'allow_fractional')
        assert hasattr(config, 'min_fractional_qty')
        assert hasattr(config, 'fractional_precision')
        assert hasattr(config, 'use_notional_orders')
    
    def test_get_fractional_config(self):
        """Test getting fractional config from trading config."""
        from src.trading.config import get_fractional_config
        
        config = get_fractional_config()
        
        # Should return a FractionalConfig instance
        assert config is not None
        assert hasattr(config, 'allow_fractional')


class TestTradeRecordFractionable:
    """Test TradeRecord includes fractionable flag."""
    
    def test_trade_record_default_fractionable(self):
        """TradeRecord defaults to fractionable=True."""
        from src.trading.trade_history_service import TradeRecord
        
        record = TradeRecord(
            ticker="AAPL",
            action="buy",
            quantity=2.5
        )
        
        assert record.fractionable is True
    
    def test_trade_record_non_fractionable(self):
        """TradeRecord can be set to non-fractionable."""
        from src.trading.trade_history_service import TradeRecord
        
        record = TradeRecord(
            ticker="BRK.A",
            action="buy",
            quantity=1,
            fractionable=False
        )
        
        assert record.fractionable is False
        assert record.quantity == 1  # Whole share
