"""
Tests for AutomatedTradingService

Covers:
- _serialize_agent_signals: Flatten nested signals and dataclasses
- _record_cooldown / _check_cooldown: Block repeat trades within window
- _check_concentration: Reject trades exceeding position limits
- _execute_trade: Integration of skip paths and single-write behavior
"""

import pytest
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, Any, Optional
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


# ============================================================================
# Fixtures and Helpers
# ============================================================================

@dataclass
class MockCooldownConfig:
    """Minimal cooldown config for testing."""
    trade_cooldown_minutes: int = 30
    max_position_pct_per_ticker: float = 0.15
    cooldown_enabled: bool = True
    concentration_check_enabled: bool = True


@dataclass
class MockAccount:
    """Stub for Alpaca account."""
    portfolio_value: float = 100000.0
    buying_power: float = 50000.0
    equity: float = 100000.0
    cash: float = 50000.0


@dataclass
class MockPosition:
    """Stub for Alpaca position."""
    symbol: str = "AAPL"
    market_value: float = 10000.0
    qty: float = 50.0


@dataclass
class MockQuote:
    """Stub for Alpaca quote."""
    ask_price: float = 150.0
    bid_price: float = 149.5


@dataclass
class MockOrder:
    """Stub for Alpaca order result."""
    id: str = "order-123"
    status: str = "filled"
    filled_avg_price: float = 150.0
    filled_qty: float = 10.0


@dataclass
class MockOrderResult:
    """Stub for Alpaca submit_order result."""
    success: bool = True
    order: MockOrder = None
    message: str = "Order submitted"
    error: str = None
    
    def __post_init__(self):
        if self.order is None:
            self.order = MockOrder()


class MockAlpaca:
    """Stub Alpaca service for testing."""
    
    def __init__(self, positions=None, account=None):
        self._positions = positions or []
        self._account = account or MockAccount()
    
    def get_account(self):
        return self._account
    
    def get_positions(self):
        return self._positions
    
    def get_quote(self, ticker: str):
        return MockQuote()
    
    def submit_order(self, **kwargs):
        return MockOrderResult()


class MockTradeHistoryService:
    """Stub TradeHistoryService that captures recorded trades."""
    
    def __init__(self):
        self.records = []
    
    def record_trade(self, record):
        self.records.append(record)
        return len(self.records)


class MockEventLogger:
    """Stub event logger that captures log calls."""
    
    def __init__(self):
        self.trade_executions = []
        self.agent_signals = []
    
    def log_trade_execution(self, **kwargs):
        self.trade_executions.append(kwargs)
    
    def log_agent_signal(self, **kwargs):
        self.agent_signals.append(kwargs)
    
    def update_pm_execution(self, **kwargs):
        pass


@pytest.fixture
def reset_cooldowns():
    """Reset the module-level cooldown dict before/after each test."""
    import src.trading.automated_trading as atm
    original = atm._trade_cooldowns.copy()
    atm._trade_cooldowns.clear()
    yield
    atm._trade_cooldowns.clear()
    atm._trade_cooldowns.update(original)


@pytest.fixture
def service(reset_cooldowns):
    """
    Create an AutomatedTradingService without triggering DB/Alpaca connections.
    
    Uses __new__ to avoid __init__ side effects, then manually assigns required attributes.
    """
    from src.trading.automated_trading import AutomatedTradingService
    
    # Create instance without calling __init__
    svc = object.__new__(AutomatedTradingService)
    
    # Manually assign minimal required attributes
    svc.cooldown_config = MockCooldownConfig()
    svc.alpaca = MockAlpaca()
    svc.trade_history = MockTradeHistoryService()
    svc.performance_tracker = MagicMock()
    svc.strategy_engine = MagicMock()
    svc.mazo = MagicMock()
    svc.is_running = False
    svc.last_run = None
    svc.last_result = None
    svc.run_history = []
    svc._db_session = None
    
    return svc


# ============================================================================
# Prompt 1: Serialization + Guard Method Tests
# ============================================================================

class TestSerializeAgentSignals:
    """Tests for _serialize_agent_signals method."""
    
    def test_serialize_agent_signals_handles_nested_and_dataclass_inputs(self, service):
        """
        Verify _serialize_agent_signals flattens:
        - Nested {ticker: {agent: signal_data}} format
        - Dataclass agent signals
        - Plain dict agent signals
        
        Output should be {agent_name: {signal, confidence, reasoning}}.
        """
        # Create mock dataclass signal (like integration.unified_workflow.AgentSignal)
        @dataclass
        class AgentSignal:
            agent: str = "cathie_wood_agent"
            signal: str = "bullish"
            confidence: float = 85.0
            reasoning: str = "Innovation thesis supports growth"
        
        # Create mock AnalysisResult with mixed formats
        class MockAnalysis:
            analyst_signals = {
                # Nested format: {ticker: {agent: signal_data}}
                "AAPL": {
                    "warren_buffett_agent": {
                        "signal": "bullish",
                        "confidence": 80,
                        "reasoning": "Quality company with moat"
                    },
                    "michael_burry_agent": AgentSignal(
                        agent="michael_burry_agent",
                        signal="bearish",
                        confidence=75.0,
                        reasoning="Overvalued relative to fundamentals" * 20  # Long reasoning to test trimming
                    ),
                }
            }
        
        # Call the serializer
        result = service._serialize_agent_signals(MockAnalysis())
        
        # Assertions
        assert "warren_buffett_agent" in result
        assert "michael_burry_agent" in result
        
        # Check warren_buffett (dict input)
        wb = result["warren_buffett_agent"]
        assert wb["signal"] == "bullish"
        assert wb["confidence"] == 80.0
        assert wb["reasoning"] == "Quality company with moat"
        
        # Check michael_burry (dataclass input)
        mb = result["michael_burry_agent"]
        assert mb["signal"] == "bearish"
        assert mb["confidence"] == 75.0
        assert mb["reasoning"] is not None
        # Reasoning should be trimmed to 500 chars
        assert len(mb["reasoning"]) <= 500
    
    def test_serialize_agent_signals_handles_flat_dict(self, service):
        """Test serialization of flat {agent: signal_data} format."""
        
        class MockAnalysis:
            analyst_signals = {
                "valuation_analyst_agent": {
                    "signal": "bearish",
                    "confidence": 90,
                    "reasoning": "PE too high"
                },
                "technical_analyst_agent": {
                    "sig": "neutral",  # Alternative key
                    "conf": 50,        # Alternative key
                }
            }
        
        result = service._serialize_agent_signals(MockAnalysis())
        
        assert "valuation_analyst_agent" in result
        assert result["valuation_analyst_agent"]["signal"] == "bearish"
        
        assert "technical_analyst_agent" in result
        assert result["technical_analyst_agent"]["signal"] == "neutral"
        assert result["technical_analyst_agent"]["confidence"] == 50.0
    
    def test_serialize_agent_signals_handles_none(self, service):
        """Test serialization returns empty dict for None input."""
        result = service._serialize_agent_signals(None)
        assert result == {}
        
        class EmptyAnalysis:
            analyst_signals = None
        
        result = service._serialize_agent_signals(EmptyAnalysis())
        assert result == {}


class TestCooldownMechanism:
    """Tests for cooldown tracking and checking."""
    
    def test_cooldown_blocks_repeat_trade_until_window_expires(self, service, reset_cooldowns):
        """
        Verify:
        1. First trade is allowed
        2. Immediate second trade is blocked
        3. Trade after cooldown window expires is allowed
        """
        import src.trading.automated_trading as atm
        
        ticker = "GOOGL"
        
        # First check - no cooldown recorded yet
        can_trade, reason = service._check_cooldown(ticker)
        assert can_trade is True
        assert reason == ""
        
        # Record the cooldown (simulates trade execution)
        service._record_cooldown(ticker)
        
        # Second check - should be blocked
        can_trade, reason = service._check_cooldown(ticker)
        assert can_trade is False
        assert "Cooldown active" in reason
        assert "remaining" in reason.lower()
        
        # Manually expire the cooldown
        atm._trade_cooldowns[ticker] = datetime.now() - timedelta(minutes=35)
        
        # Third check - should be allowed again
        can_trade, reason = service._check_cooldown(ticker)
        assert can_trade is True
        assert reason == ""
    
    def test_cooldown_disabled_allows_all_trades(self, service, reset_cooldowns):
        """When cooldown_enabled=False, all trades should be allowed."""
        service.cooldown_config.cooldown_enabled = False
        
        # Record a cooldown
        service._record_cooldown("AAPL")
        
        # Check should still pass
        can_trade, reason = service._check_cooldown("AAPL")
        assert can_trade is True
    
    def test_cooldown_is_per_ticker(self, service, reset_cooldowns):
        """Cooldown for one ticker shouldn't affect another."""
        service._record_cooldown("AAPL")
        
        # AAPL should be blocked
        can_trade, _ = service._check_cooldown("AAPL")
        assert can_trade is False
        
        # GOOGL should be allowed
        can_trade, _ = service._check_cooldown("GOOGL")
        assert can_trade is True


class TestConcentrationCheck:
    """Tests for concentration limit checking."""
    
    def test_concentration_rejects_when_position_would_exceed_pct(self, service):
        """
        Given:
        - Portfolio value: $100,000
        - Max position: 15% ($15,000)
        - Current position in AAPL: $10,000
        - New trade: 50 shares @ $150 = $7,500
        - Total would be: $17,500 (17.5%) > 15% limit
        
        Should reject the trade.
        """
        # Setup existing position
        service.alpaca = MockAlpaca(
            positions=[MockPosition(symbol="AAPL", market_value=10000.0)],
            account=MockAccount(portfolio_value=100000.0)
        )
        
        # Check concentration for 50 shares at $150
        can_trade, reason = service._check_concentration("AAPL", 50, 150.0)
        
        assert can_trade is False
        assert "Concentration limit" in reason
        assert "17.5%" in reason or "17.5" in reason
    
    def test_concentration_allows_within_limit(self, service):
        """
        Given:
        - Portfolio value: $100,000
        - Max position: 15% ($15,000)
        - Current position in AAPL: $5,000
        - New trade: 50 shares @ $150 = $7,500
        - Total would be: $12,500 (12.5%) < 15% limit
        
        Should allow the trade.
        """
        service.alpaca = MockAlpaca(
            positions=[MockPosition(symbol="AAPL", market_value=5000.0)],
            account=MockAccount(portfolio_value=100000.0)
        )
        
        can_trade, reason = service._check_concentration("AAPL", 50, 150.0)
        
        assert can_trade is True
        assert reason == ""
    
    def test_concentration_allows_new_position_within_limit(self, service):
        """Trade for ticker with no existing position should be allowed if within limit."""
        service.alpaca = MockAlpaca(
            positions=[],  # No existing positions
            account=MockAccount(portfolio_value=100000.0)
        )
        
        # New position: 50 shares @ $150 = $7,500 (7.5% < 15%)
        can_trade, reason = service._check_concentration("GOOGL", 50, 150.0)
        
        assert can_trade is True
    
    def test_concentration_disabled_allows_all(self, service):
        """When concentration_check_enabled=False, all trades allowed."""
        service.cooldown_config.concentration_check_enabled = False
        
        service.alpaca = MockAlpaca(
            positions=[MockPosition(symbol="AAPL", market_value=50000.0)],  # Already 50%!
            account=MockAccount(portfolio_value=100000.0)
        )
        
        # This would exceed limit but check is disabled
        can_trade, _ = service._check_concentration("AAPL", 100, 500.0)
        assert can_trade is True


# ============================================================================
# Prompt 2: _execute_trade Integration Tests
# ============================================================================

class TestExecuteTrade:
    """Integration tests for _execute_trade method."""
    
    def test_execute_trade_skips_when_cooldown_blocks(self, service, reset_cooldowns):
        """
        When _check_cooldown returns (False, reason), _execute_trade should:
        - NOT call alpaca.submit_order
        - Return {"skipped": True, "reason": "cooldown"}
        """
        # Setup: record cooldown so check will fail
        service._record_cooldown("AAPL")
        
        # Track if submit_order is called
        submit_order_called = False
        def mock_submit_order(**kwargs):
            nonlocal submit_order_called
            submit_order_called = True
            return MockOrderResult()
        
        service.alpaca.submit_order = mock_submit_order
        
        # Mock event logger - patch where it's imported (src.monitoring)
        mock_logger = MockEventLogger()
        with patch("src.monitoring.get_event_logger", return_value=mock_logger):
            result = asyncio.run(service._execute_trade(
                ticker="AAPL",
                pm_decision={"action": "buy", "quantity": 10},
                portfolio=MagicMock(equity=100000, cash=50000, positions=[]),
            ))
        
        # Assertions
        assert submit_order_called is False, "submit_order should not be called when cooldown blocks"
        assert result.get("skipped") is True
        assert result.get("reason") == "cooldown"
        assert result.get("success") is False
    
    def test_execute_trade_skips_when_concentration_blocks(self, service, reset_cooldowns):
        """
        When _check_concentration returns (False, reason), _execute_trade should:
        - NOT call alpaca.submit_order
        - Return {"skipped": True, "reason": "concentration"}
        """
        # Setup: high existing position so concentration check fails
        service.alpaca = MockAlpaca(
            positions=[MockPosition(symbol="AAPL", market_value=14000.0)],  # 14% of 100k
            account=MockAccount(portfolio_value=100000.0)
        )
        
        submit_order_called = False
        def mock_submit_order(**kwargs):
            nonlocal submit_order_called
            submit_order_called = True
            return MockOrderResult()
        
        service.alpaca.submit_order = mock_submit_order
        
        mock_logger = MockEventLogger()
        with patch("src.monitoring.get_event_logger", return_value=mock_logger):
            result = asyncio.run(service._execute_trade(
                ticker="AAPL",
                pm_decision={"action": "buy", "quantity": 20},  # 20 * 150 = $3000, total = $17000 > 15%
                portfolio=MagicMock(equity=100000, cash=50000, positions=[]),
                signal=MagicMock(entry_price=150.0),
            ))
        
        assert submit_order_called is False
        assert result.get("skipped") is True
        assert result.get("reason") == "concentration"
    
    def test_execute_trade_records_trade_once_with_serialized_agent_signals(self, service, reset_cooldowns):
        """
        On successful BUY, _execute_trade should:
        - Call trade_history.record_trade ONCE
        - agent_signals should be flattened (no dataclasses/ticker nesting)
        - Event logger should receive one log_trade_execution call
        """
        @dataclass
        class AgentSignal:
            agent: str
            signal: str
            confidence: float
            reasoning: str
        
        class MockAnalysis:
            analyst_signals = {
                "AAPL": {
                    "valuation_analyst_agent": {"signal": "bullish", "confidence": 90, "reasoning": "Undervalued"},
                    "growth_analyst_agent": AgentSignal(
                        agent="growth_analyst_agent",
                        signal="neutral",
                        confidence=55,
                        reasoning="Mixed signals"
                    ),
                }
            }
            workflow_id = "test-workflow-123"
        
        # Setup: no cooldown, low concentration
        service.alpaca = MockAlpaca(
            positions=[],
            account=MockAccount(portfolio_value=100000.0)
        )
        
        # Track calls
        service.trade_history = MockTradeHistoryService()
        mock_logger = MockEventLogger()
        
        with patch("src.monitoring.get_event_logger", return_value=mock_logger):
            result = asyncio.run(service._execute_trade(
                ticker="AAPL",
                pm_decision={"action": "buy", "quantity": 10, "confidence": 85},
                portfolio=MagicMock(equity=100000, cash=50000, positions=[]),
                signal=MagicMock(entry_price=150.0, strategy="momentum", direction=MagicMock(value="long"), confidence=75, reasoning="Strong trend"),
                validation=MagicMock(mazo_sentiment="bullish", mazo_confidence="high", mazo_response="Buy signal confirmed"),
                analysis=MockAnalysis(),
            ))
        
        # Assertions
        assert result.get("success") is True
        
        # Trade recorded exactly once
        assert len(service.trade_history.records) == 1, "Should record trade exactly once"
        
        # Check agent_signals are serialized correctly
        recorded = service.trade_history.records[0]
        agent_signals = recorded.agent_signals
        
        assert "valuation_analyst_agent" in agent_signals
        assert agent_signals["valuation_analyst_agent"]["signal"] == "bullish"
        assert agent_signals["valuation_analyst_agent"]["confidence"] == 90.0
        
        assert "growth_analyst_agent" in agent_signals
        assert agent_signals["growth_analyst_agent"]["signal"] == "neutral"
        
        # Verify no ticker nesting remains
        assert "AAPL" not in agent_signals
        
        # Event logger called
        assert len(mock_logger.trade_executions) >= 1
    
    def test_execute_trade_records_cooldown_on_success(self, service, reset_cooldowns):
        """Successful trade should record cooldown for the ticker."""
        import src.trading.automated_trading as atm
        
        service.alpaca = MockAlpaca(positions=[], account=MockAccount())
        service.trade_history = MockTradeHistoryService()
        
        mock_logger = MockEventLogger()
        with patch("src.monitoring.get_event_logger", return_value=mock_logger):
            asyncio.run(service._execute_trade(
                ticker="NVDA",
                pm_decision={"action": "buy", "quantity": 5},
                portfolio=MagicMock(equity=100000, cash=50000, positions=[]),
            ))
        
        # Cooldown should now be recorded
        assert "NVDA" in atm._trade_cooldowns
        can_trade, _ = service._check_cooldown("NVDA")
        assert can_trade is False
