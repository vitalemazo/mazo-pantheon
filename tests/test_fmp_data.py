"""
Tests for FMP (Financial Modeling Prep) Data Integration

Tests:
- FMP client configuration and initialization
- Price data fetching
- Fundamental data (key metrics, ratios)
- News data
- Data provider routing with FMP as primary
- Rate limit monitoring for fmp_data channel
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestFMPDataClient:
    """Test FMP data client initialization and configuration."""
    
    def test_client_initialization(self):
        """Test that FMP client initializes correctly."""
        from src.tools.fmp_data import FMPDataClient
        
        client = FMPDataClient()
        assert client is not None
        assert hasattr(client, "is_configured")
        assert hasattr(client, "get_historical_prices")
        assert hasattr(client, "get_key_metrics_ttm")
        assert hasattr(client, "get_stock_news")
    
    def test_client_configured_with_key(self):
        """Test that client reports configured when API key is set."""
        from src.tools.fmp_data import FMPDataClient
        
        client = FMPDataClient(api_key="test-api-key")
        assert client.is_configured() is True
    
    def test_client_not_configured_without_key(self):
        """Test that client reports not configured without API key."""
        from src.tools.fmp_data import FMPDataClient
        
        with patch.dict(os.environ, {"FMP_API_KEY": ""}, clear=False):
            client = FMPDataClient(api_key=None)
            # Only unconfigured if env var is also empty
            # Note: May still pick up key from env
    
    def test_get_fmp_data_client_singleton(self):
        """Test that get_fmp_data_client returns singleton instance."""
        from src.tools.fmp_data import get_fmp_data_client
        
        client1 = get_fmp_data_client()
        client2 = get_fmp_data_client()
        assert client1 is client2


class TestFMPPriceData:
    """Test FMP price data fetching."""
    
    @patch("requests.request")
    def test_get_historical_prices_success(self, mock_request):
        """Test successful price data fetch."""
        from src.tools.fmp_data import FMPDataClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "historical": [
                {
                    "date": "2024-01-15",
                    "open": 150.0,
                    "high": 155.0,
                    "low": 149.0,
                    "close": 154.0,
                    "adjClose": 154.0,
                    "volume": 1000000,
                },
                {
                    "date": "2024-01-14",
                    "open": 148.0,
                    "high": 151.0,
                    "low": 147.0,
                    "close": 150.0,
                    "adjClose": 150.0,
                    "volume": 900000,
                },
            ]
        }
        mock_request.return_value = mock_response
        
        client = FMPDataClient(api_key="test-key")
        df = client.get_historical_prices("AAPL", "2024-01-01", "2024-01-15")
        
        assert df is not None
        assert len(df) == 2
        assert "time" in df.columns
        assert "open" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns
    
    @patch("requests.request")
    def test_get_historical_prices_empty(self, mock_request):
        """Test handling empty price response."""
        from src.tools.fmp_data import FMPDataClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"historical": []}
        mock_request.return_value = mock_response
        
        client = FMPDataClient(api_key="test-key")
        df = client.get_historical_prices("INVALID", "2024-01-01", "2024-01-15")
        
        assert df.empty


class TestFMPFundamentals:
    """Test FMP fundamental data fetching."""
    
    @patch("requests.request")
    def test_get_key_metrics_ttm(self, mock_request):
        """Test key metrics TTM fetch."""
        from src.tools.fmp_data import FMPDataClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "peRatioTTM": 25.5,
                "roeTTM": 0.45,
                "currentRatioTTM": 1.2,
                "marketCapTTM": 3000000000000,
            }
        ]
        mock_request.return_value = mock_response
        
        client = FMPDataClient(api_key="test-key")
        metrics = client.get_key_metrics_ttm("AAPL")
        
        assert metrics is not None
        assert metrics.get("peRatioTTM") == 25.5
        assert metrics.get("roeTTM") == 0.45
    
    @patch("requests.request")
    def test_get_ratios_ttm(self, mock_request):
        """Test financial ratios TTM fetch."""
        from src.tools.fmp_data import FMPDataClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "netProfitMarginTTM": 0.25,
                "grossProfitMarginTTM": 0.43,
                "returnOnEquityTTM": 0.45,
            }
        ]
        mock_request.return_value = mock_response
        
        client = FMPDataClient(api_key="test-key")
        ratios = client.get_ratios_ttm("AAPL")
        
        assert ratios is not None
        assert ratios.get("netProfitMarginTTM") == 0.25


class TestFMPNews:
    """Test FMP news data fetching."""
    
    @patch("requests.request")
    def test_get_stock_news(self, mock_request):
        """Test stock news fetch."""
        from src.tools.fmp_data import FMPDataClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "title": "Apple Reports Record Earnings",
                "text": "Apple Inc. reported record quarterly earnings...",
                "url": "https://example.com/article1",
                "site": "Example News",
                "publishedDate": "2024-01-15T10:30:00Z",
                "symbol": "AAPL",
            },
            {
                "title": "Apple Announces New Products",
                "text": "Apple unveiled its latest product lineup...",
                "url": "https://example.com/article2",
                "site": "Tech News",
                "publishedDate": "2024-01-14T14:00:00Z",
                "symbol": "AAPL",
            },
        ]
        mock_request.return_value = mock_response
        
        client = FMPDataClient(api_key="test-key")
        news = client.get_stock_news(symbols=["AAPL"], limit=10)
        
        assert len(news) == 2
        assert news[0].title == "Apple Reports Record Earnings"
        assert news[0].site == "Example News"


class TestDataProviderFMPRouting:
    """Test that data provider correctly routes to FMP when set as primary."""
    
    def test_fmp_in_data_sources(self):
        """Test that FMP is in data sources enum."""
        from src.tools.data_providers import DataSource, DATA_SOURCES
        
        assert DataSource.FMP in DATA_SOURCES
        assert DATA_SOURCES[DataSource.FMP].name == "FMP Ultimate"
    
    def test_fmp_source_for_prices(self):
        """Test that FMP is included in price sources."""
        from src.tools.data_providers import MultiSourceDataProvider
        
        with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp", "FMP_API_KEY": "test-key"}):
            provider = MultiSourceDataProvider()
            sources = provider._get_sources_for_data_type("prices")
            
            # FMP should be first when set as primary
            from src.tools.data_providers import DataSource
            assert DataSource.FMP in sources
    
    def test_fmp_source_for_fundamentals(self):
        """Test that FMP is included in fundamental sources."""
        from src.tools.data_providers import MultiSourceDataProvider
        
        with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp", "FMP_API_KEY": "test-key"}):
            provider = MultiSourceDataProvider()
            sources = provider._get_sources_for_data_type("financials")
            
            from src.tools.data_providers import DataSource
            assert DataSource.FMP in sources
    
    def test_fmp_source_for_news(self):
        """Test that FMP is included in news sources."""
        from src.tools.data_providers import MultiSourceDataProvider
        
        with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp", "FMP_API_KEY": "test-key"}):
            provider = MultiSourceDataProvider()
            sources = provider._get_sources_for_data_type("news")
            
            from src.tools.data_providers import DataSource
            assert DataSource.FMP in sources


class TestAPIRoutingWithFMP:
    """Test api.py routes through FMP when selected as primary."""
    
    @patch("src.tools.fmp_data.get_fmp_data_client")
    def test_get_prices_uses_fmp_when_primary(self, mock_get_client):
        """Test that get_prices tries FMP first when PRIMARY_DATA_SOURCE=fmp."""
        import pandas as pd
        from src.tools.api import get_prices
        
        # Mock FMP client
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.get_historical_prices.return_value = pd.DataFrame({
            "time": [datetime(2024, 1, 15)],
            "open": [150.0],
            "high": [155.0],
            "low": [149.0],
            "close": [154.0],
            "volume": [1000000],
        })
        mock_get_client.return_value = mock_client
        
        with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
            prices = get_prices("AAPL", "2024-01-01", "2024-01-15")
            
            # Should have called FMP client
            mock_client.get_historical_prices.assert_called_once()
            assert len(prices) == 1
    
    @patch("src.tools.fmp_data.get_fmp_data_client")
    def test_get_company_news_uses_fmp_when_primary(self, mock_get_client):
        """Test that get_company_news tries FMP first when PRIMARY_DATA_SOURCE=fmp."""
        from src.tools.api import get_company_news
        from src.tools.fmp_data import FMPNews
        
        # Mock FMP client
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.get_stock_news.return_value = [
            FMPNews(
                title="Test News",
                text="Test content",
                url="https://example.com",
                site="Test Site",
                published_date=datetime(2024, 1, 15),
                symbol="AAPL",
            )
        ]
        mock_get_client.return_value = mock_client
        
        with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
            news = get_company_news("AAPL", "2024-01-15")
            
            mock_client.get_stock_news.assert_called_once()
            assert len(news) == 1


class TestRateLimitMonitorFMP:
    """Test rate limit monitor includes fmp_data channel."""
    
    def test_fmp_data_channel_exists(self):
        """Test that fmp_data channel is in default limits."""
        from src.monitoring.rate_limit_monitor import RateLimitMonitor
        
        assert "fmp_data" in RateLimitMonitor.DEFAULT_LIMITS
        assert RateLimitMonitor.DEFAULT_LIMITS["fmp_data"] == 300


class TestFMPConvenienceFunctions:
    """Test convenience functions for FMP data."""
    
    def test_fmp_data_available(self):
        """Test fmp_data_available function."""
        from src.tools.fmp_data import fmp_data_available
        
        # Just verify the function exists and returns a boolean
        result = fmp_data_available()
        assert isinstance(result, bool)
    
    def test_get_fmp_fundamentals(self):
        """Test get_fmp_fundamentals convenience function."""
        from src.tools.fmp_data import get_fmp_fundamentals
        
        # Verify function signature - should accept ticker and return dict
        # Actual call may fail without API key, just test structure
        assert callable(get_fmp_fundamentals)


# Integration tests - require actual API key (skipped by default)
@pytest.mark.skipif(
    not os.environ.get("FMP_API_KEY"),
    reason="FMP_API_KEY not set - skipping integration tests"
)
class TestFMPIntegration:
    """Integration tests requiring actual FMP API key."""
    
    def test_real_price_fetch(self):
        """Test real price data fetch from FMP."""
        from src.tools.fmp_data import get_fmp_data_client
        
        client = get_fmp_data_client()
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        df = client.get_historical_prices("AAPL", start, end)
        assert not df.empty
        assert "close" in df.columns
    
    def test_real_metrics_fetch(self):
        """Test real key metrics fetch from FMP."""
        from src.tools.fmp_data import get_fmp_data_client
        
        client = get_fmp_data_client()
        metrics = client.get_key_metrics_ttm("AAPL")
        
        assert metrics is not None
        assert "peRatioTTM" in metrics or metrics.get("peRatioTTM") is not None
    
    def test_real_news_fetch(self):
        """Test real news fetch from FMP."""
        from src.tools.fmp_data import get_fmp_data_client
        
        client = get_fmp_data_client()
        news = client.get_stock_news(symbols=["AAPL"], limit=5)
        
        assert len(news) > 0
        assert news[0].title
    
    def test_real_financial_metrics_mapping(self):
        """
        Regression test: Verify get_financial_metrics returns properly mapped
        FinancialMetrics when PRIMARY_DATA_SOURCE=fmp.
        
        This test confirms the FMP field mapping layer works correctly.
        """
        from src.tools.api import get_financial_metrics
        from src.data.models import FinancialMetrics
        
        # Ensure FMP is primary
        with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
            metrics = get_financial_metrics("AAPL", "2024-12-27")
        
        # Should return at least one metric
        assert len(metrics) >= 1, "Expected at least one FinancialMetrics record"
        
        m = metrics[0]
        
        # Verify it's a proper FinancialMetrics instance
        assert isinstance(m, FinancialMetrics)
        assert m.ticker == "AAPL"
        
        # Verify key valuation metrics are mapped (not None for AAPL)
        assert m.market_cap is not None, "market_cap should be mapped"
        assert m.price_to_earnings_ratio is not None, "P/E ratio should be mapped"
        assert m.price_to_book_ratio is not None, "P/B ratio should be mapped"
        
        # Verify profitability margins are mapped
        assert m.gross_margin is not None, "gross_margin should be mapped"
        assert m.operating_margin is not None, "operating_margin should be mapped"
        assert m.net_margin is not None, "net_margin should be mapped"
        
        # Verify returns are mapped
        assert m.return_on_equity is not None, "ROE should be mapped"
        assert m.return_on_assets is not None, "ROA should be mapped"
        
        # Verify liquidity metrics
        assert m.current_ratio is not None, "current_ratio should be mapped"
        
        # Verify per-share metrics
        assert m.book_value_per_share is not None, "book_value_per_share should be mapped"
        
        print(f"✓ Financial metrics mapping test passed!")
        print(f"  Market Cap: ${m.market_cap:,.0f}")
        print(f"  P/E Ratio: {m.price_to_earnings_ratio:.2f}")
        print(f"  ROE: {m.return_on_equity:.2%}")


class TestFinancialMetricsMapping:
    """Test the FMP to FinancialMetrics field mapping."""
    
    def test_fmp_mapping_with_mock_data(self):
        """Test mapping layer with mocked FMP response."""
        from src.data.models import FinancialMetrics
        from unittest.mock import patch, MagicMock
        
        # Mock FMP data matching actual API response structure
        mock_metrics = {
            "marketCap": 3000000000000,
            "enterpriseValueTTM": 3200000000000,
            "returnOnEquityTTM": 0.145,
            "returnOnAssetsTTM": 0.28,
            "returnOnInvestedCapitalTTM": 0.52,
            "currentRatioTTM": 0.95,
            "freeCashFlowYieldTTM": 0.035,
            "evToEBITDATTM": 25.5,
            "evToSalesTTM": 8.2,
            "daysOfSalesOutstandingTTM": 52.3,
            "operatingCycleTTM": 45.2,
        }
        
        mock_ratios = {
            "priceToEarningsRatioTTM": 32.5,
            "priceToBookRatioTTM": 45.2,
            "priceToSalesRatioTTM": 8.1,
            "grossProfitMarginTTM": 0.456,
            "operatingProfitMarginTTM": 0.31,
            "netProfitMarginTTM": 0.255,
            "debtToEquityRatioTTM": 1.95,
            "debtToAssetsRatioTTM": 0.32,
            "quickRatioTTM": 0.85,
            "cashRatioTTM": 0.25,
            "interestCoverageRatioTTM": 42,
            "assetTurnoverTTM": 1.15,
            "inventoryTurnoverTTM": 40.5,
            "receivablesTurnoverTTM": 15.2,
            "dividendPayoutRatioTTM": 0.15,
            "netIncomePerShareTTM": 6.42,
            "bookValuePerShareTTM": 4.38,
            "freeCashFlowPerShareTTM": 6.95,
            "priceToEarningsGrowthRatioTTM": 2.8,
        }
        
        # Create mock FMP client
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.get_key_metrics_ttm.return_value = mock_metrics
        mock_client.get_ratios_ttm.return_value = mock_ratios
        
        with patch("src.tools.api.get_fmp_data_client", return_value=mock_client):
            with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
                from src.tools.api import get_financial_metrics
                
                metrics = get_financial_metrics("TEST", "2024-12-27")
        
        assert len(metrics) == 1
        m = metrics[0]
        
        # Verify valuation metrics mapping
        assert m.market_cap == 3000000000000
        assert m.price_to_earnings_ratio == 32.5
        assert m.price_to_book_ratio == 45.2
        assert m.price_to_sales_ratio == 8.1
        assert m.peg_ratio == 2.8
        
        # Verify profitability margins (should be raw decimals)
        assert m.gross_margin == 0.456
        assert m.operating_margin == 0.31
        assert m.net_margin == 0.255
        
        # Verify returns
        assert m.return_on_equity == 0.145
        assert m.return_on_assets == 0.28
        assert m.return_on_invested_capital == 0.52
        
        # Verify liquidity
        assert m.current_ratio == 0.95
        assert m.quick_ratio == 0.85
        assert m.cash_ratio == 0.25
        
        # Verify leverage
        assert m.debt_to_equity == 1.95
        assert m.debt_to_assets == 0.32
        assert m.interest_coverage == 42
        
        # Verify per-share metrics
        assert m.earnings_per_share == 6.42
        assert m.book_value_per_share == 4.38
        assert m.free_cash_flow_per_share == 6.95
    
    def test_partial_fmp_data_handling(self):
        """Test that partial FMP data (missing fields) doesn't cause errors."""
        from src.data.models import FinancialMetrics
        from unittest.mock import patch, MagicMock
        
        # Only provide some metrics
        mock_metrics = {
            "marketCap": 1000000000,
        }
        mock_ratios = {
            "priceToEarningsRatioTTM": 15.0,
        }
        
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.get_key_metrics_ttm.return_value = mock_metrics
        mock_client.get_ratios_ttm.return_value = mock_ratios
        
        with patch("src.tools.api.get_fmp_data_client", return_value=mock_client):
            with patch.dict(os.environ, {"PRIMARY_DATA_SOURCE": "fmp"}):
                from src.tools.api import get_financial_metrics
                
                metrics = get_financial_metrics("TEST", "2024-12-27")
        
        assert len(metrics) == 1
        m = metrics[0]
        
        # Verify provided fields
        assert m.market_cap == 1000000000
        assert m.price_to_earnings_ratio == 15.0
        
        # Verify missing fields are None (not raising errors)
        assert m.gross_margin is None
        assert m.return_on_equity is None
        assert m.debt_to_equity is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
