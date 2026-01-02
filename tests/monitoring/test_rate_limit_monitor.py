"""
Tests for RateLimitMonitor call activity tracking.

Tests the new call_type tracking and activity aggregation features.
"""

import pytest
from datetime import datetime, timezone, timedelta


def test_record_call_with_type():
    """Test recording calls with specific call types."""
    # Reset and get fresh monitor
    from src.monitoring.rate_limit_monitor import (
        RateLimitMonitor, reset_rate_limit_monitor
    )
    
    reset_rate_limit_monitor()
    monitor = RateLimitMonitor()
    
    # Record some calls with different types
    monitor.record_call("alpaca", call_type="orders", success=True)
    monitor.record_call("alpaca", call_type="account", success=True)
    monitor.record_call("alpaca", call_type="orders", success=True)
    monitor.record_call("openai_proxy", call_type="chat_completion", success=True)
    monitor.record_call("openai_proxy", call_type="chat_completion", success=False)
    
    # Get activity
    activity = monitor.get_call_activity(window_minutes=60)
    
    assert activity["total_calls"] == 5
    assert "alpaca" in activity["providers"]
    assert "openai_proxy" in activity["providers"]
    
    # Check alpaca breakdown
    alpaca = activity["providers"]["alpaca"]
    assert alpaca["total"] == 3
    assert alpaca["by_type"]["orders"] == 2
    assert alpaca["by_type"]["account"] == 1
    assert alpaca["errors"] == 0
    
    # Check openai_proxy breakdown
    openai = activity["providers"]["openai_proxy"]
    assert openai["total"] == 2
    assert openai["by_type"]["chat_completion"] == 2
    assert openai["errors"] == 1  # One failed call


def test_record_call_default_type():
    """Test that calls without call_type use 'general'."""
    from src.monitoring.rate_limit_monitor import (
        RateLimitMonitor, reset_rate_limit_monitor
    )
    
    reset_rate_limit_monitor()
    monitor = RateLimitMonitor()
    
    # Record without specifying call_type
    monitor.record_call("fmp_data", success=True)
    
    activity = monitor.get_call_activity(window_minutes=60)
    
    assert activity["providers"]["fmp_data"]["by_type"]["general"] == 1


def test_recent_events():
    """Test getting recent events."""
    from src.monitoring.rate_limit_monitor import (
        RateLimitMonitor, reset_rate_limit_monitor
    )
    
    reset_rate_limit_monitor()
    monitor = RateLimitMonitor()
    
    # Record several calls
    monitor.record_call("alpaca", call_type="orders", success=True, latency_ms=50)
    monitor.record_call("alpaca", call_type="positions", success=True, latency_ms=30)
    
    events = monitor.get_recent_events(limit=10)
    
    assert len(events) == 2
    # Most recent first
    assert events[0]["type"] == "positions"
    assert events[1]["type"] == "orders"
    assert events[0]["latency_ms"] == 30


def test_ring_buffer_bounded():
    """Test that call history is bounded by MAX_CALL_HISTORY."""
    from src.monitoring.rate_limit_monitor import (
        RateLimitMonitor, reset_rate_limit_monitor
    )
    
    reset_rate_limit_monitor()
    monitor = RateLimitMonitor()
    
    # Record more than MAX_CALL_HISTORY events
    for i in range(monitor.MAX_CALL_HISTORY + 100):
        monitor.record_call("test_api", call_type=f"type_{i % 10}", success=True)
    
    # Should not exceed max
    assert len(monitor._call_history) == monitor.MAX_CALL_HISTORY


def test_activity_window_filtering():
    """Test that activity respects the time window."""
    from src.monitoring.rate_limit_monitor import (
        RateLimitMonitor, CallEvent, reset_rate_limit_monitor
    )
    
    reset_rate_limit_monitor()
    monitor = RateLimitMonitor()
    
    now = datetime.now(timezone.utc)
    
    # Manually add old event (simulating 2 hours ago)
    old_event = CallEvent(
        api_name="old_api",
        call_type="old_type",
        timestamp=now - timedelta(hours=2),
        success=True,
    )
    monitor._call_history.append(old_event)
    
    # Add recent event
    monitor.record_call("new_api", call_type="new_type", success=True)
    
    # Get activity for last hour - should only see new_api
    activity = monitor.get_call_activity(window_minutes=60)
    
    assert "new_api" in activity["providers"]
    assert "old_api" not in activity["providers"]
    assert activity["total_calls"] == 1


def test_display_name_formatting():
    """Test that display names are user-friendly."""
    from src.monitoring.rate_limit_monitor import (
        RateLimitMonitor, reset_rate_limit_monitor
    )
    
    reset_rate_limit_monitor()
    monitor = RateLimitMonitor()
    
    monitor.record_call("alpaca", call_type="orders", success=True)
    monitor.record_call("alpaca", call_type="account", success=True)
    
    activity = monitor.get_call_activity(window_minutes=60)
    
    # Check display string contains friendly name
    display = activity["providers"]["alpaca"]["display"]
    assert "Alpaca Trading" in display
    assert "2 calls" in display
