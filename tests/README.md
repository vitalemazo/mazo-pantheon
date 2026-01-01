# Mazo Pantheon Test Suite

This directory contains unit and integration tests for the Mazo Pantheon trading platform.

## Quick Start

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/trading/test_automated_trading.py
pytest tests/agents/test_portfolio_manager.py

# Run specific test class
pytest tests/trading/test_automated_trading.py::TestSerializeAgentSignals

# Run specific test
pytest tests/trading/test_automated_trading.py::TestCooldownMechanism::test_cooldown_blocks_repeat_trade_until_window_expires
```

## Running Tests in Docker

The tests require Python 3.10+ for union type syntax (`X | None`). Run tests inside the Docker container:

```bash
# From the docker/ directory
docker exec mazo-backend python3 -m pytest tests/ -v

# Run specific test modules
docker exec mazo-backend python3 -m pytest tests/trading/test_automated_trading.py -v
docker exec mazo-backend python3 -m pytest tests/agents/test_portfolio_manager.py -v
```

## Test Structure

```
tests/
├── README.md                           # This file
├── __init__.py
├── agents/
│   ├── __init__.py
│   └── test_portfolio_manager.py       # Portfolio Manager tests
├── monitoring/
│   ├── __init__.py
│   └── test_stale_detection.py         # Stale data detection tests
├── trading/
│   ├── __init__.py
│   └── test_automated_trading.py       # Automated Trading Service tests
├── test_alpaca_data.py                 # Alpaca data client tests
├── test_fmp_data.py                    # FMP data client tests
└── test_integration_data_providers.py  # Data provider integration tests
```

---

## Test Modules

### `tests/monitoring/test_stale_detection.py`

Tests for stale data detection across the monitoring system.

#### Test Classes

| Class | Description |
|-------|-------------|
| `TestSchedulerHeartbeatDetection` | Scheduler heartbeat freshness detection |
| `TestAlertManagerStaleAlerts` | P1/P0 alert generation for stale/down states |
| `TestAgentSignalStaleness` | Agent signal age threshold detection |
| `TestRateLimitStaleness` | Rate limit data freshness |
| `TestDataFreshnessResponse` | API response structure validation |
| `TestSystemStatusResponse` | System status response fields |
| `TestHealthCheckerIntegration` | HealthChecker integration tests |

#### Key Tests

```bash
# All stale detection tests
pytest tests/monitoring/test_stale_detection.py -v

# Scheduler heartbeat tests
pytest tests/monitoring/test_stale_detection.py::TestSchedulerHeartbeatDetection -v

# Alert generation tests
pytest tests/monitoring/test_stale_detection.py::TestAlertManagerStaleAlerts -v
```

#### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULER_STALE_THRESHOLD_MINUTES` | 10 | Minutes before scheduler is marked stale |
| `DATA_STALE_THRESHOLD_MINUTES` | 60 | Minutes before agent data is marked stale |

---

### 1. `tests/trading/test_automated_trading.py`

Tests for `AutomatedTradingService` including cooldown, concentration limits, and trade execution.

#### Test Classes

| Class | Description |
|-------|-------------|
| `TestSerializeAgentSignals` | Agent signal serialization to JSON-safe format |
| `TestCooldownMechanism` | Per-ticker cooldown tracking and enforcement |
| `TestConcentrationCheck` | Position concentration limit validation |
| `TestExecuteTrade` | End-to-end trade execution with guards |

#### Key Tests

```bash
# Serialization tests
pytest tests/trading/test_automated_trading.py::TestSerializeAgentSignals -v

# Cooldown tests
pytest tests/trading/test_automated_trading.py::TestCooldownMechanism -v

# Concentration tests  
pytest tests/trading/test_automated_trading.py::TestConcentrationCheck -v

# Trade execution tests
pytest tests/trading/test_automated_trading.py::TestExecuteTrade -v
```

#### What's Tested

- **`_serialize_agent_signals`**: Handles nested `{ticker: {agent: signal}}`, dataclasses, and flat dicts
- **`_check_cooldown`**: Blocks repeat trades until `TRADE_COOLDOWN_MINUTES` expires
- **`_record_cooldown`**: Records last trade time per ticker
- **`_check_concentration`**: Rejects trades exceeding `MAX_POSITION_PCT_PER_TICKER`
- **`_execute_trade`**: Skips on cooldown/concentration, records exactly one trade

---

### 2. `tests/agents/test_portfolio_manager.py`

Tests for `compute_allowed_actions` function in the Portfolio Manager.

#### Test Class

| Class | Description |
|-------|-------------|
| `TestComputeAllowedActions` | Validates action constraints based on risk/price/position |

#### Key Tests

```bash
# All Portfolio Manager tests
pytest tests/agents/test_portfolio_manager.py -v

# Specific risk limit tests
pytest tests/agents/test_portfolio_manager.py::TestComputeAllowedActions::test_compute_allowed_actions_blocks_buy_when_risk_limit_zero -v
```

#### What's Tested

| Test | Validates |
|------|-----------|
| `test_compute_allowed_actions_blocks_buy_when_risk_limit_zero` | BUY/SHORT = 0 when `max_shares = 0` |
| `test_compute_allowed_actions_blocks_when_price_missing` | BUY/SHORT = 0 when price = 0 |
| `test_compute_allowed_actions_allows_buy_when_limits_permit` | BUY respects `max_shares` |
| `test_compute_allowed_actions_limits_buy_by_cash` | BUY limited by buying power |
| `test_compute_allowed_actions_sell_reflects_long_position` | SELL = current long position |
| `test_compute_allowed_actions_cover_reflects_short_position` | COVER = current short position |
| `test_compute_allowed_actions_paper_trading_fallback` | Paper trading allows small positions |
| `test_compute_allowed_actions_handles_missing_positions` | New tickers handled gracefully |
| `test_compute_allowed_actions_cancel_with_pending_orders` | CANCEL = pending order count |
| `test_compute_allowed_actions_multiple_tickers` | Multi-ticker portfolio handling |

---

## Test Fixtures & Mocks

### Stubs in `test_automated_trading.py`

| Stub | Purpose |
|------|---------|
| `MockCooldownConfig` | Configurable cooldown/concentration settings |
| `MockAccount` | Alpaca account with portfolio_value, buying_power |
| `MockPosition` | Alpaca position with symbol, market_value |
| `MockQuote` | Alpaca quote with ask/bid prices |
| `MockOrder` / `MockOrderResult` | Order submission response |
| `MockAlpaca` | Complete Alpaca service stub |
| `MockTradeHistoryService` | Captures recorded trades |
| `MockEventLogger` | Captures log calls |

### Key Fixtures

```python
@pytest.fixture
def reset_cooldowns():
    """Reset module-level _trade_cooldowns between tests."""
    
@pytest.fixture
def service(reset_cooldowns):
    """Create AutomatedTradingService without DB/Alpaca connections."""
```

---

## Writing New Tests

### 1. Adding a Trading Test

```python
# tests/trading/test_automated_trading.py

def test_my_new_feature(self, service, reset_cooldowns):
    """Test description."""
    # Arrange
    service.alpaca = MockAlpaca(
        positions=[MockPosition(symbol="AAPL", market_value=5000.0)],
        account=MockAccount(portfolio_value=100000.0)
    )
    
    # Act
    result = service._my_method("AAPL")
    
    # Assert
    assert result == expected_value
```

### 2. Adding an Async Test

```python
def test_async_method(self, service, reset_cooldowns):
    """Test async method using asyncio.run()."""
    mock_logger = MockEventLogger()
    
    with patch("src.monitoring.get_event_logger", return_value=mock_logger):
        result = asyncio.run(service._execute_trade(
            ticker="AAPL",
            pm_decision={"action": "buy", "quantity": 10},
            portfolio=MagicMock(equity=100000, cash=50000, positions=[]),
        ))
    
    assert result.get("success") is True
```

### 3. Adding a Portfolio Manager Test

```python
# tests/agents/test_portfolio_manager.py

def test_my_action_constraint(self):
    """Test description."""
    tickers = ["AAPL"]
    current_prices = {"AAPL": 150.0}
    max_shares = {"AAPL": 50}
    portfolio = {
        "cash": 10000.0,
        "buying_power": 10000.0,
        "equity": 50000.0,
        "positions": {},
        "pending_orders": [],
        "paper_trading": False,
        "margin_requirement": 0.5,
        "margin_used": 0.0,
    }
    
    result = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)
    
    assert result["AAPL"]["buy"] == 50
```

---

## Environment Variables for Testing

Tests use mocked services by default. For integration tests that need real services:

| Variable | Description |
|----------|-------------|
| `FMP_API_KEY` | FinancialModelingPrep API key |
| `ALPACA_API_KEY` | Alpaca trading API key |
| `ALPACA_SECRET_KEY` | Alpaca secret key |
| `REDIS_URL` | Redis connection (for cache tests) |

---

## Troubleshooting

### Python Version Error
```
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```
**Solution**: Run tests in Docker (Python 3.11+) or upgrade local Python to 3.10+.

### Module Not Found
```
ModuleNotFoundError: No module named 'src'
```
**Solution**: Run from project root or ensure `PYTHONPATH` includes project root.

### Async Tests Skipped
```
PytestUnhandledCoroutineWarning: async def functions are not natively supported
```
**Solution**: Tests use `asyncio.run()` instead of `pytest.mark.asyncio`. This is intentional to avoid requiring `pytest-asyncio`.

---

## Coverage Report

```bash
# Generate coverage report
docker exec mazo-backend python3 -m pytest tests/ --cov=src --cov-report=html

# View report (after copying from container)
open htmlcov/index.html
```

---

## CI/CD Integration

These tests are designed to run in CI pipelines:

```yaml
# Example GitHub Actions step
- name: Run Tests
  run: |
    docker exec mazo-backend python3 -m pytest tests/ -v --tb=short
```
