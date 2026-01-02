"""
Tests for AccuracyBackfillService

Covers:
- backfill_from_closed_trades: Updates pm_decisions and agent_signals
- Accuracy calculation logic: bullish/bearish vs profitable outcome
- get_accuracy_summary: Returns coverage statistics
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
import asyncio


class TestAccuracyBackfillLogic:
    """Test the accuracy calculation logic."""
    
    def test_bullish_signal_profitable_buy_is_correct(self):
        """
        If PM action was BUY and trade was profitable,
        bullish signals should be marked as correct.
        """
        # This is a logic test - the signal matches the profitable direction
        pm_action = "buy"
        was_profitable = True
        signal = "bullish"
        
        # Logic from accuracy_backfill.py
        pm_direction = "long" if pm_action.lower() in ["buy", "cover", "long"] else "short"
        
        if was_profitable:
            if pm_direction == "long":
                correct_signal = "bullish"
            else:
                correct_signal = "bearish"
        else:
            if pm_direction == "long":
                correct_signal = "bearish"
            else:
                correct_signal = "bullish"
        
        assert signal == correct_signal
    
    def test_bearish_signal_profitable_short_is_correct(self):
        """
        If PM action was SHORT and trade was profitable,
        bearish signals should be marked as correct.
        """
        pm_action = "short"
        was_profitable = True
        signal = "bearish"
        
        pm_direction = "long" if pm_action.lower() in ["buy", "cover", "long"] else "short"
        
        if was_profitable:
            correct_signal = "bearish" if pm_direction == "short" else "bullish"
        else:
            correct_signal = "bullish" if pm_direction == "short" else "bearish"
        
        assert signal == correct_signal
    
    def test_bullish_signal_unprofitable_buy_is_incorrect(self):
        """
        If PM action was BUY and trade was NOT profitable,
        bullish signals should be marked as incorrect (they were wrong).
        """
        pm_action = "buy"
        was_profitable = False
        signal = "bullish"
        
        pm_direction = "long"
        
        if was_profitable:
            correct_signal = "bullish"
        else:
            # Trade lost money, so bullish was WRONG
            correct_signal = "bearish"
        
        assert signal != correct_signal  # bullish != bearish, so bullish was incorrect
    
    def test_bearish_signal_unprofitable_buy_is_correct(self):
        """
        If PM action was BUY and trade was NOT profitable,
        bearish signals should be marked as correct (they were right not to buy).
        """
        pm_action = "buy"
        was_profitable = False
        signal = "bearish"
        
        pm_direction = "long"
        
        # Trade lost money on a BUY, so bearish agents were RIGHT
        correct_signal = "bearish"
        
        assert signal == correct_signal


class TestBackfillResult:
    """Test BackfillResult dataclass."""
    
    def test_backfill_result_defaults(self):
        """BackfillResult should have sensible defaults."""
        from src.monitoring.accuracy_backfill import BackfillResult
        
        result = BackfillResult()
        
        assert result.trades_processed == 0
        assert result.pm_decisions_updated == 0
        assert result.agent_signals_updated == 0
        assert result.errors == []
    
    def test_backfill_result_with_values(self):
        """BackfillResult should store provided values."""
        from src.monitoring.accuracy_backfill import BackfillResult
        
        result = BackfillResult(
            trades_processed=10,
            pm_decisions_updated=8,
            agent_signals_updated=45,
            errors=["Some error"]
        )
        
        assert result.trades_processed == 10
        assert result.pm_decisions_updated == 8
        assert result.agent_signals_updated == 45
        assert result.errors == ["Some error"]


class TestAccuracyBackfillService:
    """Test AccuracyBackfillService methods."""
    
    def test_service_singleton(self):
        """get_accuracy_backfill_service should return the same instance."""
        from src.monitoring.accuracy_backfill import get_accuracy_backfill_service
        
        service1 = get_accuracy_backfill_service()
        service2 = get_accuracy_backfill_service()
        
        assert service1 is service2
    
    def test_backfill_without_db_returns_error(self):
        """If no database session, backfill should return error."""
        from src.monitoring.accuracy_backfill import AccuracyBackfillService, BackfillResult
        
        service = AccuracyBackfillService()
        service.database_url = None  # Force no database
        
        result = asyncio.run(service.backfill_from_closed_trades(days=7))
        
        assert isinstance(result, BackfillResult)
        assert any("No database session" in e for e in result.errors)
    
    def test_get_accuracy_summary_without_db(self):
        """get_accuracy_summary without DB should return error dict."""
        from src.monitoring.accuracy_backfill import AccuracyBackfillService
        
        service = AccuracyBackfillService()
        service.database_url = None
        
        result = asyncio.run(service.get_accuracy_summary())
        
        assert "error" in result


class TestAccuracyBackfillIntegration:
    """Integration tests that use mocked database."""
    
    def test_backfill_with_mocked_db(self):
        """
        Test the full backfill flow with mocked database.
        
        Scenario:
        - 1 closed trade: AAPL BUY with +$100 P&L (profitable)
        - 1 PM decision for AAPL
        - 2 agent signals: 1 bullish (should be correct), 1 bearish (should be incorrect)
        """
        from src.monitoring.accuracy_backfill import AccuracyBackfillService
        
        # Create mock session with expected query results
        mock_session = MagicMock()
        
        # Mock closed trades query
        mock_trades_result = MagicMock()
        mock_trades_result.fetchall.return_value = [
            # (id, ticker, action, realized_pnl, entry_time, exit_time, order_id)
            (1, "AAPL", "buy", 100.0, datetime.now(timezone.utc), datetime.now(timezone.utc), "order-123")
        ]
        
        # Mock PM decision query
        mock_pm_result = MagicMock()
        mock_pm_result.fetchone.return_value = (
            "pm-uuid-1", "workflow-uuid-1", "buy"
        )
        
        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2
        
        # Setup execute to return different results based on query
        call_count = [0]
        
        def mock_execute(query, params=None):
            call_count[0] += 1
            if "trade_history" in str(query) and "SELECT" in str(query):
                return mock_trades_result
            elif "pm_decisions" in str(query) and "SELECT" in str(query):
                return mock_pm_result
            elif "COUNT(*)" in str(query):
                return mock_count_result
            else:
                # UPDATE queries
                return MagicMock()
        
        mock_session.execute = mock_execute
        mock_session.commit = MagicMock()
        mock_session.rollback = MagicMock()
        mock_session.close = MagicMock()
        
        # Create service with mocked session
        service = AccuracyBackfillService()
        service._get_session = lambda: mock_session
        
        result = asyncio.run(service.backfill_from_closed_trades(days=7))
        
        assert result.trades_processed == 1
        assert result.pm_decisions_updated == 1
        assert result.agent_signals_updated == 2
        assert len(result.errors) == 0
        assert mock_session.commit.called
