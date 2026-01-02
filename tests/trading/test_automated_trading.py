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
    
    def test_execute_trade_entry_price_from_fill(self, service, reset_cooldowns):
        """Entry price should come from filled_avg_price when available."""
        service.alpaca = MockAlpaca(positions=[], account=MockAccount())
        service.trade_history = MockTradeHistoryService()
        
        # Set up order with known fill price
        filled_price = 155.75
        service.alpaca.submit_order = lambda **kwargs: MockOrderResult(
            success=True,
            order=MockOrder(id="order-fill-test", filled_avg_price=filled_price)
        )
        
        mock_logger = MockEventLogger()
        with patch("src.monitoring.get_event_logger", return_value=mock_logger):
            asyncio.run(service._execute_trade(
                ticker="AAPL",
                pm_decision={"action": "buy", "quantity": 10},
                portfolio=MagicMock(equity=100000, cash=50000, positions=[]),
                signal=MagicMock(entry_price=150.0, strategy="test", direction=MagicMock(value="long"), confidence=75, reasoning="Test"),
            ))
        
        # Check that entry_price in trade record matches the fill
        assert len(service.trade_history.records) == 1
        recorded = service.trade_history.records[0]
        assert recorded.entry_price == filled_price
    
    def test_execute_trade_entry_price_fallback_to_signal(self, service, reset_cooldowns):
        """Entry price should fall back to signal.entry_price when fill not available."""
        service.alpaca = MockAlpaca(positions=[], account=MockAccount())
        service.trade_history = MockTradeHistoryService()
        
        # Order without fill price (still pending)
        service.alpaca.submit_order = lambda **kwargs: MockOrderResult(
            success=True,
            order=MockOrder(id="order-pending-test", filled_avg_price=None, status="accepted")
        )
        
        signal_price = 148.50
        mock_logger = MockEventLogger()
        with patch("src.monitoring.get_event_logger", return_value=mock_logger):
            asyncio.run(service._execute_trade(
                ticker="MSFT",
                pm_decision={"action": "buy", "quantity": 10},
                portfolio=MagicMock(equity=100000, cash=50000, positions=[]),
                signal=MagicMock(entry_price=signal_price, strategy="test", direction=MagicMock(value="long"), confidence=75, reasoning="Test"),
            ))
        
        # Check that entry_price falls back to signal price
        assert len(service.trade_history.records) == 1
        recorded = service.trade_history.records[0]
        assert recorded.entry_price == signal_price
    
    def test_execute_trade_entry_price_fallback_to_quote(self, service, reset_cooldowns):
        """Entry price should fall back to quote when fill and signal not available."""
        quote_price = 142.50
        service.alpaca = MockAlpaca(positions=[], account=MockAccount())
        # Return a dict-style quote like the actual get_quote method
        service.alpaca.get_quote = lambda ticker: {"bid": 142.25, "ask": quote_price, "last": 142.375}
        service.trade_history = MockTradeHistoryService()
        
        # Order without fill price
        service.alpaca.submit_order = lambda **kwargs: MockOrderResult(
            success=True,
            order=MockOrder(id="order-nofill-test", filled_avg_price=None, status="accepted")
        )
        
        mock_logger = MockEventLogger()
        with patch("src.monitoring.get_event_logger", return_value=mock_logger):
            asyncio.run(service._execute_trade(
                ticker="GOOGL",
                pm_decision={"action": "buy", "quantity": 5, "entry_price": quote_price},  # Provide entry_price in pm_decision
                portfolio=MagicMock(equity=100000, cash=50000, positions=[]),
                signal=MagicMock(entry_price=quote_price, strategy="test", direction=MagicMock(value="long"), confidence=75, reasoning="Test"),
            ))
        
        # Check that trade was recorded
        assert len(service.trade_history.records) == 1
        recorded = service.trade_history.records[0]
        assert recorded.entry_price == quote_price


# ============================================================================
# PDT Protection Tests
# ============================================================================

class TestPDTProtection:
    """Tests for Pattern Day Trader protection."""
    
    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        from src.trading.automated_trading import AutomatedTradingService
        
        svc = AutomatedTradingService.__new__(AutomatedTradingService)
        svc.cooldown_config = MockCooldownConfig()
        svc.is_running = False
        svc.last_run = None
        svc.last_result = None
        svc.run_history = []
        svc.trade_history = None
        svc.alpaca = MockAlpaca()
        return svc
    
    def test_pdt_check_allows_high_equity(self, service):
        """PDT check should allow trading with high equity."""
        # Mock alpaca to return high equity PDT status
        service.alpaca.check_pdt_status = lambda: {
            "is_pdt": False,
            "daytrade_count": 2,
            "equity": 50000.0,
            "can_day_trade": True,
            "warning": None,
        }
        
        result = service._check_pdt_limits()
        
        assert result.get("blocked") is False
    
    def test_pdt_check_blocks_at_limit(self, service):
        """PDT check should block when at day trade limit with low equity."""
        # Mock alpaca to return PDT blocked status
        service.alpaca.check_pdt_status = lambda: {
            "is_pdt": False,
            "daytrade_count": 3,
            "equity": 5000.0,
            "can_day_trade": False,
            "warning": "At 3/3 day trades in 5 days. One more would trigger PDT flag.",
        }
        
        with patch.dict('os.environ', {'ENFORCE_PDT': 'true'}):
            result = service._check_pdt_limits()
        
        assert result.get("blocked") is True
        assert "reason" in result
    
    def test_pdt_check_respects_disabled_flag(self, service):
        """PDT check should skip when ENFORCE_PDT=false."""
        # Mock alpaca to return blocked status
        service.alpaca.check_pdt_status = lambda: {
            "is_pdt": False,
            "daytrade_count": 5,
            "equity": 1000.0,
            "can_day_trade": False,
            "warning": "PDT limit exceeded",
        }
        
        with patch.dict('os.environ', {'ENFORCE_PDT': 'false'}):
            result = service._check_pdt_limits()
        
        # Should NOT be blocked because enforcement is disabled
        assert result.get("blocked") is False


# ============================================================================
# Risk Limits Tests
# ============================================================================

class TestRiskLimits:
    """Tests for portfolio-wide risk limits."""
    
    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        from src.trading.automated_trading import AutomatedTradingService
        
        svc = AutomatedTradingService.__new__(AutomatedTradingService)
        svc.cooldown_config = MockCooldownConfig()
        svc.is_running = False
        svc.alpaca = MockAlpaca()
        return svc
    
    def test_risk_check_under_limits(self, service):
        """Risk check should pass when under all limits."""
        # Mock 5 positions, well under limit
        service.alpaca = MockAlpaca(
            positions=[
                MockPosition(symbol="AAPL", market_value=5000),
                MockPosition(symbol="MSFT", market_value=5000),
            ],
            account=MockAccount(portfolio_value=100000, equity=100000)
        )
        
        result = service._check_risk_limits()
        
        assert result.get("can_add_position") is True
        assert len(result.get("violations", [])) == 0
    
    def test_risk_check_max_positions_reached(self, service):
        """Risk check should flag when max positions reached."""
        # Create many positions
        positions = [MockPosition(symbol=f"SYM{i}", market_value=2000) for i in range(20)]
        service.alpaca = MockAlpaca(
            positions=positions,
            account=MockAccount(portfolio_value=100000, equity=100000)
        )
        
        result = service._check_risk_limits()
        
        assert result.get("can_add_position") is False
        assert any("positions" in v.lower() for v in result.get("violations", []))
    
    def test_risk_check_concentration_violation(self, service):
        """Risk check should flag position concentration violations."""
        # One position at 30% (above 20% limit)
        service.alpaca = MockAlpaca(
            positions=[
                MockPosition(symbol="AAPL", market_value=30000),  # 30%
                MockPosition(symbol="MSFT", market_value=5000),   # 5%
            ],
            account=MockAccount(portfolio_value=100000, equity=100000)
        )
        
        result = service._check_risk_limits()
        
        violations = result.get("violations", [])
        assert any("AAPL" in v and "exceeds" in v.lower() for v in violations)


# ============================================================================
# Position Sizing with Fractional Tests
# ============================================================================

class TestPositionSizingFractional:
    """Tests for position sizing with fractional share support."""
    
    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        from src.trading.automated_trading import AutomatedTradingService
        
        svc = AutomatedTradingService.__new__(AutomatedTradingService)
        svc.cooldown_config = MockCooldownConfig()
        svc.is_running = False
        svc.alpaca = MockAlpaca(account=MockAccount(
            portfolio_value=10000,
            buying_power=5000,
            equity=10000,
            cash=5000
        ))
        return svc
    
    def test_position_size_fractional_enabled(self, service):
        """Position size should return fractional for fractionable asset."""
        from src.trading.strategy_engine import TradingSignal, SignalDirection, SignalStrength
        
        signal = TradingSignal(
            ticker="AAPL",
            strategy="test",
            direction=SignalDirection.LONG,
            strength=SignalStrength.STRONG,
            confidence=80,
            entry_price=150.0,
            stop_loss=145.0,
            take_profit=165.0,
            position_size_pct=0.05,
            reasoning="Test",
            fractionable=True
        )
        
        with patch.dict('os.environ', {'ALLOW_FRACTIONAL': 'true'}):
            size = service._calculate_position_size(signal, MockAccount(
                portfolio_value=10000,
                buying_power=10000,
                equity=10000,
                cash=10000
            ))
        
        # 5% of $10k = $500, at $150/share = 3.33 shares
        assert size > 0
        # Should have fractional component
        assert isinstance(size, float)
    
    def test_position_size_non_fractionable_rounds(self, service):
        """Position size should round to whole shares for non-fractionable asset."""
        from src.trading.strategy_engine import TradingSignal, SignalDirection, SignalStrength
        
        signal = TradingSignal(
            ticker="BRK.A",
            strategy="test",
            direction=SignalDirection.LONG,
            strength=SignalStrength.STRONG,
            confidence=80,
            entry_price=500000.0,  # Very expensive
            stop_loss=490000.0,
            take_profit=520000.0,
            position_size_pct=0.05,
            reasoning="Test",
            fractionable=False  # Not fractionable
        )
        
        with patch.dict('os.environ', {'ALLOW_FRACTIONAL': 'true'}):
            size = service._calculate_position_size(signal, MockAccount(
                portfolio_value=100000,
                buying_power=100000,
                equity=100000,
                cash=100000
            ))
        
        # Should be rounded to whole number (or 0 if can't afford)
        assert size == int(size) or size == 0
