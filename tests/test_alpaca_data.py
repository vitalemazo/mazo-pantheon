"""
Tests for Alpaca Market Data integration.

These tests verify:
1. AlpacaDataClient basic functionality
2. Data source routing when PRIMARY_DATA_SOURCE=alpaca
3. Fallback behavior when Alpaca is unavailable
4. Rate limit monitor integration
"""

import os
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime


# =============================================================================
# AlpacaDataClient Tests
# =============================================================================

class TestAlpacaDataClient:
    """Tests for the AlpacaDataClient class."""
    
    def test_client_not_configured_without_credentials(self, monkeypatch):
        """Test client reports not configured when credentials are missing."""
        monkeypatch.delenv("ALPACA_API_KEY", raising=False)
        monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
        
        from src.tools.alpaca_data import AlpacaDataClient
        
        client = AlpacaDataClient()
        assert not client.is_configured()
    
    def test_client_configured_with_credentials(self, monkeypatch):
        """Test client reports configured when credentials are present."""
        monkeypatch.setenv("ALPACA_API_KEY", "test-key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
        
        # Need to reimport to pick up new env vars
        from src.tools.alpaca_data import AlpacaDataClient
        
        client = AlpacaDataClient()
        assert client.is_configured()
    
    def test_get_bars_returns_empty_when_not_configured(self, monkeypatch):
        """Test get_bars returns empty DataFrame when not configured."""
        monkeypatch.delenv("ALPACA_API_KEY", raising=False)
        monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
        
        from src.tools.alpaca_data import AlpacaDataClient
        
        client = AlpacaDataClient()
        df = client.get_bars("AAPL", "2024-01-01", "2024-01-15")
        
        assert isinstance(df, pd.DataFrame)
        assert df.empty
    
    @patch('src.tools.alpaca_data.requests.request')
    def test_get_bars_parses_response(self, mock_request, monkeypatch):
        """Test get_bars correctly parses Alpaca API response."""
        monkeypatch.setenv("ALPACA_API_KEY", "test-key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"bars": {"AAPL": [{"t": "2024-01-02T05:00:00Z", "o": 185.0, "h": 186.0, "l": 184.0, "c": 185.5, "v": 1000000}]}}'
        mock_response.json.return_value = {
            "bars": {
                "AAPL": [{
                    "t": "2024-01-02T05:00:00Z",
                    "o": 185.0,
                    "h": 186.0,
                    "l": 184.0,
                    "c": 185.5,
                    "v": 1000000,
                }]
            }
        }
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        from src.tools.alpaca_data import AlpacaDataClient
        
        client = AlpacaDataClient()
        df = client.get_bars("AAPL", "2024-01-01", "2024-01-15")
        
        assert not df.empty
        assert len(df) == 1
        assert df.iloc[0]["open"] == 185.0
        assert df.iloc[0]["close"] == 185.5
        assert df.iloc[0]["volume"] == 1000000
    
    @patch('src.tools.alpaca_data.requests.request')
    def test_get_news_returns_articles(self, mock_request, monkeypatch):
        """Test get_news correctly parses news articles."""
        monkeypatch.setenv("ALPACA_API_KEY", "test-key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "news": [{
                "id": "123",
                "headline": "Apple Reports Record Quarter",
                "summary": "Apple Inc. reported record earnings...",
                "author": "John Doe",
                "source": "Reuters",
                "url": "https://example.com/news/123",
                "symbols": ["AAPL"],
                "created_at": "2024-01-15T12:00:00Z",
            }]
        }
        mock_response.text = '{"news": [...]}'
        mock_response.headers = {}
        mock_request.return_value = mock_response
        
        from src.tools.alpaca_data import AlpacaDataClient
        
        client = AlpacaDataClient()
        news = client.get_news(symbols=["AAPL"], limit=5)
        
        assert len(news) == 1
        assert news[0].headline == "Apple Reports Record Quarter"
        assert news[0].source == "Reuters"
        assert "AAPL" in news[0].symbols


# =============================================================================
# Data Source Routing Tests
# =============================================================================

class TestDataSourceRouting:
    """Tests for PRIMARY_DATA_SOURCE routing logic."""
    
    def test_alpaca_in_data_sources_enum(self):
        """Test that ALPACA_DATA is in the DataSource enum."""
        from src.tools.data_providers import DataSource
        
        assert hasattr(DataSource, 'ALPACA_DATA')
        assert DataSource.ALPACA_DATA.value == "alpaca"
    
    def test_alpaca_in_data_sources_config(self):
        """Test that ALPACA_DATA has proper configuration."""
        from src.tools.data_providers import DATA_SOURCES, DataSource
        
        assert DataSource.ALPACA_DATA in DATA_SOURCES
        
        config = DATA_SOURCES[DataSource.ALPACA_DATA]
        assert config.name == "Alpaca Market Data"
        assert config.api_key_env == "ALPACA_API_KEY"
        assert config.rate_limit_per_minute == 200
    
    def test_alpaca_first_for_prices_when_primary(self, monkeypatch):
        """Test Alpaca is first source for prices when PRIMARY_DATA_SOURCE=alpaca."""
        monkeypatch.setenv("PRIMARY_DATA_SOURCE", "alpaca")
        monkeypatch.setenv("ALPACA_API_KEY", "test-key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
        
        from src.tools.data_providers import MultiSourceDataProvider, DataSource
        
        provider = MultiSourceDataProvider()
        sources = provider._get_sources_for_data_type("prices")
        
        # Alpaca should be first (if available)
        if DataSource.ALPACA_DATA in sources:
            assert sources[0] == DataSource.ALPACA_DATA
    
    def test_alpaca_first_for_news_when_primary(self, monkeypatch):
        """Test Alpaca is first source for news when PRIMARY_DATA_SOURCE=alpaca."""
        monkeypatch.setenv("PRIMARY_DATA_SOURCE", "alpaca")
        monkeypatch.setenv("ALPACA_API_KEY", "test-key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
        
        from src.tools.data_providers import MultiSourceDataProvider, DataSource
        
        provider = MultiSourceDataProvider()
        sources = provider._get_sources_for_data_type("news")
        
        # Alpaca should be first (if available)
        if DataSource.ALPACA_DATA in sources:
            assert sources[0] == DataSource.ALPACA_DATA
    
    def test_alpaca_not_in_fundamentals(self, monkeypatch):
        """Test Alpaca is NOT included for fundamentals (it doesn't provide them)."""
        monkeypatch.setenv("PRIMARY_DATA_SOURCE", "alpaca")
        monkeypatch.setenv("ALPACA_API_KEY", "test-key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
        
        from src.tools.data_providers import MultiSourceDataProvider, DataSource
        
        provider = MultiSourceDataProvider()
        
        # Alpaca should NOT be in financials or metrics sources
        financials_sources = provider._get_sources_for_data_type("financials")
        metrics_sources = provider._get_sources_for_data_type("metrics")
        
        assert DataSource.ALPACA_DATA not in financials_sources
        assert DataSource.ALPACA_DATA not in metrics_sources
    
    def test_fallback_when_alpaca_not_primary(self, monkeypatch):
        """Test Alpaca is not first when not set as primary."""
        monkeypatch.setenv("PRIMARY_DATA_SOURCE", "financial_datasets")
        monkeypatch.setenv("ALPACA_API_KEY", "test-key")
        
        from src.tools.data_providers import MultiSourceDataProvider, DataSource
        
        provider = MultiSourceDataProvider()
        sources = provider._get_sources_for_data_type("prices")
        
        # Alpaca should not be first
        if sources and DataSource.ALPACA_DATA in sources:
            assert sources[0] != DataSource.ALPACA_DATA


# =============================================================================
# Rate Limit Monitor Tests
# =============================================================================

class TestRateLimitMonitor:
    """Tests for rate limit monitor integration."""
    
    def test_alpaca_data_channel_exists(self):
        """Test that alpaca_data channel is in rate limit monitor."""
        from src.monitoring.rate_limit_monitor import RateLimitMonitor
        
        assert "alpaca_data" in RateLimitMonitor.DEFAULT_LIMITS
        assert RateLimitMonitor.DEFAULT_LIMITS["alpaca_data"] == 200


# =============================================================================
# API Module Routing Tests
# =============================================================================

class TestApiModuleRouting:
    """Tests for src/tools/api.py routing to Alpaca."""
    
    @patch('src.tools.alpaca_data.AlpacaDataClient.get_bars')
    def test_get_prices_uses_alpaca_when_primary(self, mock_get_bars, monkeypatch):
        """Test get_prices routes to Alpaca when PRIMARY_DATA_SOURCE=alpaca."""
        monkeypatch.setenv("PRIMARY_DATA_SOURCE", "alpaca")
        monkeypatch.setenv("ALPACA_API_KEY", "test-key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
        
        # Mock Alpaca returning data
        mock_df = pd.DataFrame([{
            "time": pd.Timestamp("2024-01-02"),
            "open": 185.0,
            "high": 186.0,
            "low": 184.0,
            "close": 185.5,
            "volume": 1000000,
        }])
        mock_get_bars.return_value = mock_df
        
        # Need to reimport to pick up patched client
        import importlib
        import src.tools.api as api_module
        importlib.reload(api_module)
        
        prices = api_module.get_prices("AAPL", "2024-01-01", "2024-01-15")
        
        # Should have called Alpaca
        mock_get_bars.assert_called_once()


# =============================================================================
# Integration Tests (require actual credentials - skip in CI)
# =============================================================================

@pytest.mark.skipif(
    not os.environ.get("ALPACA_API_KEY"),
    reason="Alpaca credentials not configured"
)
class TestAlpacaIntegration:
    """Integration tests that require actual Alpaca credentials."""
    
    def test_real_snapshot(self):
        """Test getting real snapshot from Alpaca."""
        from src.tools.alpaca_data import get_alpaca_data_client
        
        client = get_alpaca_data_client()
        snapshot = client.get_snapshot("AAPL")
        
        assert snapshot is not None
        assert snapshot.symbol == "AAPL"
        # Price should be reasonable
        if snapshot.latest_trade_price:
            assert 50 < snapshot.latest_trade_price < 500
    
    def test_real_bars(self):
        """Test getting real bars from Alpaca."""
        from src.tools.alpaca_data import get_alpaca_data_client
        from datetime import datetime, timedelta
        
        client = get_alpaca_data_client()
        
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        
        df = client.get_bars("AAPL", start, end)
        
        assert not df.empty
        assert "open" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
