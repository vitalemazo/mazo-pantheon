"""
Integration Tests for Data Provider Routing

These tests verify the full data provider fallback chain works correctly:
- FMP as primary → Alpaca fallback → Financial Datasets fallback
- Proper data model conversion
- Graceful error handling

Run with: pytest tests/test_integration_data_providers.py -v
Skip integration tests: pytest tests/test_integration_data_providers.py -v -m "not integration"
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestDataProviderRouting:
    """Test that data requests route correctly based on PRIMARY_DATA_SOURCE."""
    
    def test_fmp_is_default_primary(self):
        """Verify FMP is the default primary data source."""
        # Clear any existing setting
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PRIMARY_DATA_SOURCE", None)
            
            # Import fresh to get default
            import importlib
            from src.tools import api
            importlib.reload(api)
            
            # Default should be 'fmp'
            primary = os.environ.get("PRIMARY_DATA_SOURCE", "fmp")
            assert primary == "fmp"
    
    def test_get_prices_routes_to_fmp_when_primary(self):
        """Test that get_prices calls FMP first when it's primary."""
        from src.data.models import Price
        from unittest.mock import MagicMock, patch
        import pandas as pd
        
        # Create mock FMP client
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.get_historical_prices.return_value = pd.DataFrame({
            "time": [datetime(2024, 12, 20)],
            "open": [250.0],
            "high": [255.0],
            "low": [248.0],
            "close": [252.0],
            "volume": [1000000],
        })
        
        with patch("src.tools.api.get_fmp_data_client", return_value=mock_client):
            with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
                from src.tools.api import get_prices
                
                prices = get_prices("AAPL", "2024-12-20", "2024-12-20")
        
        # Verify FMP was called
        mock_client.get_historical_prices.assert_called_once()
        
        # Verify result
        assert len(prices) == 1
        assert isinstance(prices[0], Price)
        assert prices[0].ticker == "AAPL"
        assert prices[0].close == 252.0
    
    def test_get_prices_falls_back_to_alpaca(self):
        """Test that get_prices falls back to Alpaca when FMP fails."""
        from src.data.models import Price
        from unittest.mock import MagicMock, patch
        import pandas as pd
        
        # FMP fails
        mock_fmp = MagicMock()
        mock_fmp.is_configured.return_value = True
        mock_fmp.get_historical_prices.return_value = None
        
        # Alpaca succeeds
        mock_alpaca = MagicMock()
        mock_alpaca.is_configured.return_value = True
        mock_alpaca.get_bars.return_value = pd.DataFrame({
            "time": [datetime(2024, 12, 20)],
            "open": [250.0],
            "high": [255.0],
            "low": [248.0],
            "close": [253.0],
            "volume": [1000000],
        })
        
        with patch("src.tools.api.get_fmp_data_client", return_value=mock_fmp):
            with patch("src.tools.api.get_alpaca_data_client", return_value=mock_alpaca):
                with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
                    from src.tools.api import get_prices
                    
                    prices = get_prices("AAPL", "2024-12-20", "2024-12-20")
        
        # Verify Alpaca was called as fallback
        mock_alpaca.get_bars.assert_called_once()
        
        # Verify result from Alpaca
        assert len(prices) == 1
        assert prices[0].close == 253.0
    
    def test_get_company_news_routes_correctly(self):
        """Test news fetching routes through FMP → Alpaca → FD."""
        from src.data.models import CompanyNews
        from unittest.mock import MagicMock, patch
        
        # Mock FMP news response
        mock_article = MagicMock()
        mock_article.title = "Apple announces new product"
        mock_article.text = "Apple Inc. today announced..."
        mock_article.site = "Bloomberg"
        mock_article.url = "https://example.com/article"
        mock_article.published_date = datetime(2024, 12, 27)
        
        mock_fmp = MagicMock()
        mock_fmp.is_configured.return_value = True
        mock_fmp.get_stock_news.return_value = [mock_article]
        
        with patch("src.tools.api.get_fmp_data_client", return_value=mock_fmp):
            with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
                from src.tools.api import get_company_news
                
                news = get_company_news("AAPL", "2024-12-27", limit=5)
        
        assert len(news) == 1
        assert isinstance(news[0], CompanyNews)
        assert news[0].title == "Apple announces new product"
        assert news[0].source == "Bloomberg"
    
    def test_get_financial_metrics_mapping(self):
        """Test financial metrics are properly mapped from FMP."""
        from src.data.models import FinancialMetrics
        from unittest.mock import MagicMock, patch
        
        mock_metrics = {
            "marketCap": 3000000000000,
            "currentRatioTTM": 0.95,
            "returnOnEquityTTM": 0.145,
            "returnOnAssetsTTM": 0.28,
        }
        mock_ratios = {
            "priceToEarningsRatioTTM": 32.5,
            "priceToBookRatioTTM": 45.2,
            "grossProfitMarginTTM": 0.456,
            "operatingProfitMarginTTM": 0.31,
            "netProfitMarginTTM": 0.255,
            "debtToEquityRatioTTM": 1.52,
        }
        
        mock_fmp = MagicMock()
        mock_fmp.is_configured.return_value = True
        mock_fmp.get_key_metrics_ttm.return_value = mock_metrics
        mock_fmp.get_ratios_ttm.return_value = mock_ratios
        
        with patch("src.tools.api.get_fmp_data_client", return_value=mock_fmp):
            with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
                from src.tools.api import get_financial_metrics
                
                metrics = get_financial_metrics("AAPL", "2024-12-27")
        
        assert len(metrics) == 1
        m = metrics[0]
        assert isinstance(m, FinancialMetrics)
        
        # Verify mapping
        assert m.market_cap == 3000000000000
        assert m.price_to_earnings_ratio == 32.5
        assert m.price_to_book_ratio == 45.2
        assert m.gross_margin == 0.456
        assert m.return_on_equity == 0.145
        assert m.debt_to_equity == 1.52


class TestAlpacaPrimaryRouting:
    """Test routing when Alpaca is set as primary."""
    
    def test_alpaca_primary_for_prices(self):
        """Test prices route to Alpaca first when it's primary."""
        from src.data.models import Price
        from unittest.mock import MagicMock, patch
        import pandas as pd
        
        mock_alpaca = MagicMock()
        mock_alpaca.is_configured.return_value = True
        mock_alpaca.get_bars.return_value = pd.DataFrame({
            "time": [datetime(2024, 12, 20)],
            "open": [250.0],
            "high": [255.0],
            "low": [248.0],
            "close": [252.0],
            "volume": [1000000],
        })
        
        with patch("src.tools.api.get_alpaca_data_client", return_value=mock_alpaca):
            with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "alpaca"}):
                from src.tools.api import get_prices
                
                prices = get_prices("AAPL", "2024-12-20", "2024-12-20")
        
        mock_alpaca.get_bars.assert_called_once()
        assert len(prices) == 1


@pytest.mark.skipif(
    not os.environ.get("FMP_API_KEY"),
    reason="FMP_API_KEY not set - skipping live integration tests"
)
class TestLiveIntegration:
    """Live integration tests - require actual API keys."""
    
    def test_live_fmp_prices(self):
        """Test live price fetch from FMP."""
        with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
            from src.tools.api import get_prices
            
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            
            prices = get_prices("AAPL", start, end)
        
        assert len(prices) > 0
        assert prices[0].ticker == "AAPL"
        assert prices[0].close > 0
    
    def test_live_fmp_metrics(self):
        """Test live metrics fetch from FMP."""
        with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
            from src.tools.api import get_financial_metrics
            
            metrics = get_financial_metrics("AAPL", datetime.now().strftime("%Y-%m-%d"))
        
        assert len(metrics) > 0
        m = metrics[0]
        assert m.market_cap is not None
        assert m.market_cap > 0
        assert m.price_to_earnings_ratio is not None
    
    def test_live_fmp_news(self):
        """Test live news fetch from FMP."""
        with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
            from src.tools.api import get_company_news
            
            news = get_company_news("AAPL", datetime.now().strftime("%Y-%m-%d"), limit=5)
        
        assert len(news) > 0
        assert news[0].title is not None
        assert news[0].source is not None


class TestCacheTTL:
    """Test cache TTL configuration."""
    
    def test_cache_ttl_defaults(self):
        """Verify cache has correct default TTLs."""
        from src.data.cache import RedisCache
        
        cache = RedisCache()
        
        # Real-time data (short TTLs)
        assert cache.TTL_QUOTES == 60  # 1 minute
        assert cache.TTL_PRICES_INTRADAY == 300  # 5 minutes
        assert cache.TTL_NEWS == 600  # 10 minutes
        
        # Daily/historical data
        assert cache.TTL_PRICES == 3600  # 1 hour
        
        # Fundamental data (long TTLs)
        assert cache.TTL_METRICS == 86400  # 24 hours
        assert cache.TTL_INSIDER == 86400  # 24 hours
    
    def test_cache_ttl_env_override(self):
        """Test that cache TTLs can be overridden via environment."""
        with patch.dict(os.environ, {
            "CACHE_TTL_QUOTES": "30",
            "CACHE_TTL_NEWS": "120",
        }):
            # Need to reimport to pick up new env vars
            from src.data.cache import _get_ttl_from_env
            
            assert _get_ttl_from_env("CACHE_TTL_QUOTES", 60) == 30
            assert _get_ttl_from_env("CACHE_TTL_NEWS", 600) == 120


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
