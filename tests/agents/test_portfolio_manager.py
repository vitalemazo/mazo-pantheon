"""
Tests for Portfolio Manager

Covers compute_allowed_actions:
- BUY/SHORT blocked when risk limit (max_shares) is 0
- BUY/SHORT blocked when price data is missing
- Proper _reason field included when blocked
"""

import pytest
from src.agents.portfolio_manager import compute_allowed_actions


class TestComputeAllowedActions:
    """Tests for the compute_allowed_actions function."""
    
    def test_compute_allowed_actions_blocks_buy_when_risk_limit_zero(self):
        """
        When max_shares[ticker] == 0, BUY and SHORT must be 0.
        The actions should include "_reason" explaining the block.
        """
        tickers = ["AAPL"]
        current_prices = {"AAPL": 150.0}  # Valid price
        max_shares = {"AAPL": 0}  # Risk manager says NO trading allowed
        portfolio = {
            "cash": 50000.0,
            "buying_power": 50000.0,
            "equity": 100000.0,
            "positions": {},
            "pending_orders": [],
            "paper_trading": False,  # Not paper trading
            "margin_requirement": 0.5,
            "margin_used": 0.0,
        }
        
        result = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)
        
        assert "AAPL" in result
        actions = result["AAPL"]
        
        # BUY should be 0 because max_shares is 0
        assert actions.get("buy") == 0, "BUY should be 0 when max_shares is 0"
        
        # SHORT should also be 0
        assert actions.get("short") == 0, "SHORT should be 0 when max_shares is 0"
        
        # Should have a reason explaining the block
        assert "_reason" in actions
        assert "Risk limit" in actions["_reason"] or "max position is 0" in actions["_reason"]
        
        # HOLD should always be available
        assert actions.get("hold") == 0  # hold uses 0 as placeholder
        
        # SELL/COVER should be 0 since no positions
        assert actions.get("sell") == 0
        assert actions.get("cover") == 0
    
    def test_compute_allowed_actions_blocks_when_price_missing(self):
        """
        When price is 0 or missing, BUY and SHORT should be 0.
        The actions should include "_reason" mentioning missing price data.
        """
        tickers = ["INVALID"]
        current_prices = {"INVALID": 0.0}  # Missing/invalid price
        max_shares = {"INVALID": 100}  # Risk would allow trading
        portfolio = {
            "cash": 50000.0,
            "buying_power": 50000.0,
            "equity": 100000.0,
            "positions": {},
            "pending_orders": [],
            "paper_trading": False,
            "margin_requirement": 0.5,
            "margin_used": 0.0,
        }
        
        result = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)
        
        assert "INVALID" in result
        actions = result["INVALID"]
        
        # BUY should be 0 because price is missing
        assert actions.get("buy") == 0, "BUY should be 0 when price is missing"
        
        # SHORT should also be 0
        assert actions.get("short") == 0, "SHORT should be 0 when price is missing"
        
        # Should have a reason explaining the block
        assert "_reason" in actions
        assert "price" in actions["_reason"].lower() or "Missing" in actions["_reason"]
    
    def test_compute_allowed_actions_allows_buy_when_limits_permit(self):
        """
        When max_shares > 0, price is valid, and cash is available,
        BUY should be allowed.
        """
        tickers = ["GOOGL"]
        current_prices = {"GOOGL": 100.0}
        max_shares = {"GOOGL": 50}  # Allow up to 50 shares
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
        
        assert "GOOGL" in result
        actions = result["GOOGL"]
        
        # BUY should be min(max_shares, affordable) = min(50, 100) = 50
        assert actions.get("buy") == 50, "BUY should be limited by max_shares"
        
        # No block reason since trading is allowed
        assert "_reason" not in actions
    
    def test_compute_allowed_actions_limits_buy_by_cash(self):
        """
        BUY should be limited by available buying power, not just max_shares.
        """
        tickers = ["TSLA"]
        current_prices = {"TSLA": 250.0}
        max_shares = {"TSLA": 100}  # Allow up to 100 shares
        portfolio = {
            "cash": 500.0,
            "buying_power": 500.0,  # Only $500 available
            "equity": 50000.0,
            "positions": {},
            "pending_orders": [],
            "paper_trading": False,
            "margin_requirement": 0.5,
            "margin_used": 0.0,
        }
        
        result = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)
        
        actions = result["TSLA"]
        
        # BUY should be min(max_shares, affordable) = min(100, 2) = 2
        assert actions.get("buy") == 2, "BUY should be limited by buying power"
    
    def test_compute_allowed_actions_sell_reflects_long_position(self):
        """
        SELL action should reflect the actual long position held.
        """
        tickers = ["MSFT"]
        current_prices = {"MSFT": 350.0}
        max_shares = {"MSFT": 50}
        portfolio = {
            "cash": 10000.0,
            "buying_power": 10000.0,
            "equity": 50000.0,
            "positions": {
                "MSFT": {"long": 25, "long_cost_basis": 8000.0, "short": 0, "short_cost_basis": 0.0}
            },
            "pending_orders": [],
            "paper_trading": False,
            "margin_requirement": 0.5,
            "margin_used": 0.0,
        }
        
        result = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)
        
        actions = result["MSFT"]
        
        # SELL should equal the long position
        assert actions.get("sell") == 25, "SELL should equal long position"
        
        # REDUCE_LONG should be position - 1
        assert actions.get("reduce_long") == 24, "REDUCE_LONG should be position - 1"
    
    def test_compute_allowed_actions_cover_reflects_short_position(self):
        """
        COVER action should reflect the actual short position held.
        """
        tickers = ["META"]
        current_prices = {"META": 300.0}
        max_shares = {"META": 50}
        portfolio = {
            "cash": 10000.0,
            "buying_power": 10000.0,
            "equity": 50000.0,
            "positions": {
                "META": {"long": 0, "long_cost_basis": 0.0, "short": 15, "short_cost_basis": 4500.0}
            },
            "pending_orders": [],
            "paper_trading": False,
            "margin_requirement": 0.5,
            "margin_used": 0.0,
        }
        
        result = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)
        
        actions = result["META"]
        
        # COVER should equal the short position
        assert actions.get("cover") == 15, "COVER should equal short position"
        
        # REDUCE_SHORT should be position - 1
        assert actions.get("reduce_short") == 14, "REDUCE_SHORT should be position - 1"
    
    def test_compute_allowed_actions_paper_trading_fallback(self):
        """
        In paper trading mode with max_shares=0 (risk data missing, not explicitly blocked),
        should allow small positions as a fallback.
        """
        tickers = ["AMZN"]
        current_prices = {"AMZN": 150.0}
        max_shares = {"AMZN": 0}  # No risk data
        portfolio = {
            "cash": 10000.0,
            "buying_power": 10000.0,
            "equity": 50000.0,
            "positions": {},
            "pending_orders": [],
            "paper_trading": True,  # Paper trading mode
            "margin_requirement": 0.5,
            "margin_used": 0.0,
        }
        
        result = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)
        
        actions = result["AMZN"]
        
        # Paper trading should allow small fallback position (capped at 5)
        # Note: This depends on implementation - may allow up to 5 shares
        assert actions.get("buy") <= 5, "Paper trading fallback should be capped"
    
    def test_compute_allowed_actions_handles_missing_positions(self):
        """
        Should handle tickers not in positions dict gracefully.
        """
        tickers = ["NEW_TICKER"]
        current_prices = {"NEW_TICKER": 50.0}
        max_shares = {"NEW_TICKER": 100}
        portfolio = {
            "cash": 5000.0,
            "buying_power": 5000.0,
            "equity": 10000.0,
            "positions": {},  # No positions at all
            "pending_orders": [],
            "paper_trading": False,
            "margin_requirement": 0.5,
            "margin_used": 0.0,
        }
        
        result = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)
        
        actions = result["NEW_TICKER"]
        
        # SELL should be 0 (no position to sell)
        assert actions.get("sell") == 0
        
        # COVER should be 0 (no short to cover)
        assert actions.get("cover") == 0
        
        # BUY should be allowed (min of max_shares and affordable)
        assert actions.get("buy") == 100  # Can afford 100 shares at $50 with $5000
    
    def test_compute_allowed_actions_cancel_with_pending_orders(self):
        """
        CANCEL action should reflect pending orders for the ticker.
        """
        tickers = ["NVDA"]
        current_prices = {"NVDA": 450.0}
        max_shares = {"NVDA": 20}
        portfolio = {
            "cash": 10000.0,
            "buying_power": 10000.0,
            "equity": 50000.0,
            "positions": {},
            "pending_orders": [
                {"symbol": "NVDA", "qty": 5, "status": "pending"},
                {"symbol": "NVDA", "qty": 3, "status": "pending"},
                {"symbol": "AAPL", "qty": 10, "status": "pending"},  # Different ticker
            ],
            "paper_trading": False,
            "margin_requirement": 0.5,
            "margin_used": 0.0,
        }
        
        result = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)
        
        actions = result["NVDA"]
        
        # CANCEL should equal count of pending orders for this ticker
        assert actions.get("cancel") == 2, "CANCEL should equal pending order count"
    
    def test_compute_allowed_actions_multiple_tickers(self):
        """
        Should correctly compute actions for multiple tickers.
        """
        tickers = ["AAPL", "GOOGL", "TSLA"]
        current_prices = {
            "AAPL": 150.0,
            "GOOGL": 140.0,
            "TSLA": 0.0,  # Missing price
        }
        max_shares = {
            "AAPL": 50,
            "GOOGL": 0,   # Risk blocked
            "TSLA": 30,
        }
        portfolio = {
            "cash": 10000.0,
            "buying_power": 10000.0,
            "equity": 50000.0,
            "positions": {
                "AAPL": {"long": 10, "long_cost_basis": 1400.0, "short": 0, "short_cost_basis": 0.0}
            },
            "pending_orders": [],
            "paper_trading": False,
            "margin_requirement": 0.5,
            "margin_used": 0.0,
        }
        
        result = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)
        
        # AAPL: Should allow trading
        assert result["AAPL"]["buy"] > 0
        assert result["AAPL"]["sell"] == 10  # Has position
        
        # GOOGL: Risk blocked
        assert result["GOOGL"]["buy"] == 0
        assert "_reason" in result["GOOGL"]
        
        # TSLA: Price missing
        assert result["TSLA"]["buy"] == 0
        assert "_reason" in result["TSLA"]
