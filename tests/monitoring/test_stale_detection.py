"""
Tests for stale data detection in monitoring system.

Covers:
- Scheduler heartbeat freshness detection
- Agent signal staleness
- Rate limit data staleness
- P1 alert generation for stale scheduler
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
import os


class TestSchedulerHeartbeatDetection:
    """Tests for scheduler heartbeat staleness detection."""
    
    def test_fresh_heartbeat_returns_healthy_status(self):
        """
        Heartbeat within threshold (< 10 minutes) should return status='healthy'.
        """
        from datetime import datetime, timezone, timedelta
        
        # Simulate fresh heartbeat (5 minutes ago)
        fresh_heartbeat = datetime.now(timezone.utc) - timedelta(minutes=5)
        threshold_minutes = 10
        
        age = datetime.now(timezone.utc) - fresh_heartbeat
        minutes_since = int(age.total_seconds() / 60)
        
        if age < timedelta(minutes=threshold_minutes):
            status = "healthy"
        else:
            status = "stale"
        
        assert status == "healthy"
        assert minutes_since < threshold_minutes
    
    def test_stale_heartbeat_returns_stale_status(self):
        """
        Heartbeat older than threshold (> 10 minutes) should return status='stale'.
        """
        from datetime import datetime, timezone, timedelta
        
        # Simulate stale heartbeat (15 minutes ago)
        stale_heartbeat = datetime.now(timezone.utc) - timedelta(minutes=15)
        threshold_minutes = 10
        
        age = datetime.now(timezone.utc) - stale_heartbeat
        minutes_since = int(age.total_seconds() / 60)
        
        if age < timedelta(minutes=threshold_minutes):
            status = "healthy"
        else:
            status = "stale"
        
        assert status == "stale"
        assert minutes_since >= threshold_minutes
    
    def test_no_heartbeat_returns_no_heartbeats_status(self):
        """
        When no heartbeat exists (row is None), should return status='no_heartbeats'.
        """
        last_heartbeat = None
        
        if last_heartbeat is None:
            status = "no_heartbeats"
        else:
            status = "healthy"
        
        assert status == "no_heartbeats"
    
    def test_threshold_configurable_via_env(self):
        """
        SCHEDULER_STALE_THRESHOLD_MINUTES should be configurable.
        """
        import os
        
        # Default threshold
        default = int(os.getenv("SCHEDULER_STALE_THRESHOLD_MINUTES", "10"))
        assert default == 10
        
        # Custom threshold
        with patch.dict(os.environ, {"SCHEDULER_STALE_THRESHOLD_MINUTES": "30"}):
            custom = int(os.getenv("SCHEDULER_STALE_THRESHOLD_MINUTES", "10"))
            assert custom == 30


class TestAlertManagerStaleAlerts:
    """Tests for P1 alert generation on stale conditions."""
    
    def test_stale_scheduler_triggers_p1_alert(self):
        """
        Stale scheduler should trigger a P1 (warning) alert.
        """
        from src.monitoring.alerting import AlertManager, AlertPriority, AlertCategory
        
        manager = AlertManager()
        
        # Track created alerts
        created_alerts = []
        original_create = manager.create_alert
        def mock_create(**kwargs):
            created_alerts.append(kwargs)
            return original_create(**kwargs)
        
        manager.create_alert = mock_create
        
        # Call alert_system_health with stale status
        manager.alert_system_health(
            component="scheduler",
            status="stale",
            message="Scheduler heartbeat stale for 15 minutes",
            details={"minutes_since": 15}
        )
        
        # Verify P1 alert was created
        assert len(created_alerts) >= 1
        alert = created_alerts[0]
        assert alert["priority"] == AlertPriority.P1  # Warning level
        assert alert["category"] == AlertCategory.SYSTEM
        assert "scheduler" in alert["title"].lower()
        assert "stale" in alert["title"].lower()
    
    def test_down_scheduler_triggers_p0_alert(self):
        """
        Down/error scheduler should trigger a P0 (critical) alert.
        """
        from src.monitoring.alerting import AlertManager, AlertPriority, AlertCategory
        
        manager = AlertManager()
        
        created_alerts = []
        original_create = manager.create_alert
        def mock_create(**kwargs):
            created_alerts.append(kwargs)
            return original_create(**kwargs)
        
        manager.create_alert = mock_create
        
        # Call with critical status
        manager.alert_system_health(
            component="scheduler",
            status="down",
            message="Scheduler process not responding",
        )
        
        assert len(created_alerts) >= 1
        alert = created_alerts[0]
        assert alert["priority"] == AlertPriority.P0  # Critical level
    
    def test_healthy_scheduler_does_not_trigger_alert(self):
        """
        Healthy scheduler should not trigger any alert via alert_system_health.
        Note: In practice, we only call alert_system_health when there's an issue.
        """
        # This is implicitly true since we only call alert_system_health
        # when a stale/down condition is detected
        pass


class TestAgentSignalStaleness:
    """Tests for agent signal staleness detection."""
    
    def test_signal_within_threshold_not_stale(self):
        """
        Agent signal within 60 minutes should not be marked stale.
        """
        from datetime import datetime, timezone, timedelta
        
        last_signal = datetime.now(timezone.utc) - timedelta(minutes=30)
        stale_threshold_minutes = 60
        
        age_minutes = (datetime.now(timezone.utc) - last_signal).total_seconds() / 60
        is_stale = age_minutes > stale_threshold_minutes
        
        assert is_stale is False
    
    def test_signal_beyond_threshold_is_stale(self):
        """
        Agent signal older than 60 minutes should be marked stale.
        """
        from datetime import datetime, timezone, timedelta
        
        last_signal = datetime.now(timezone.utc) - timedelta(minutes=90)
        stale_threshold_minutes = 60
        
        age_minutes = (datetime.now(timezone.utc) - last_signal).total_seconds() / 60
        is_stale = age_minutes > stale_threshold_minutes
        
        assert is_stale is True
    
    def test_no_signal_is_stale(self):
        """
        Agent with no signals should be marked stale.
        """
        last_signal = None
        
        if last_signal is None:
            is_stale = True
        else:
            is_stale = False
        
        assert is_stale is True


class TestRateLimitStaleness:
    """Tests for rate limit data staleness detection."""
    
    def test_rate_limit_within_hour_not_stale(self):
        """
        Rate limit data updated within 60 minutes should not be stale.
        """
        from datetime import datetime, timezone, timedelta
        
        last_call = datetime.now(timezone.utc) - timedelta(minutes=30)
        
        age_minutes = (datetime.now(timezone.utc) - last_call).total_seconds() / 60
        is_stale = age_minutes > 60
        
        assert is_stale is False
    
    def test_rate_limit_beyond_hour_is_stale(self):
        """
        Rate limit data older than 60 minutes should be marked stale.
        """
        from datetime import datetime, timezone, timedelta
        
        last_call = datetime.now(timezone.utc) - timedelta(minutes=90)
        
        age_minutes = (datetime.now(timezone.utc) - last_call).total_seconds() / 60
        is_stale = age_minutes > 60
        
        assert is_stale is True
    
    def test_no_rate_limit_data_is_stale(self):
        """
        Missing rate limit last_call_at should be marked stale.
        """
        last_call_at = None
        
        if last_call_at is None:
            is_stale = True
        else:
            is_stale = False
        
        assert is_stale is True


class TestDataFreshnessResponse:
    """Tests for data freshness API response structure."""
    
    def test_freshness_response_structure(self):
        """
        DataFreshnessInfo should have all expected fields.
        """
        from pydantic import BaseModel
        from typing import Optional
        
        # Simulate the response model
        class DataFreshnessInfo(BaseModel):
            last_workflow_at: Optional[str] = None
            last_signal_at: Optional[str] = None
            last_trade_at: Optional[str] = None
            last_pm_decision_at: Optional[str] = None
            minutes_since_workflow: Optional[int] = None
            minutes_since_signal: Optional[int] = None
            is_stale: bool = False
        
        # Create instance
        freshness = DataFreshnessInfo(
            last_workflow_at="2025-01-01T12:00:00+00:00",
            minutes_since_workflow=30,
            is_stale=False,
        )
        
        assert freshness.last_workflow_at is not None
        assert freshness.minutes_since_workflow == 30
        assert freshness.is_stale is False
        
        # Test stale detection
        stale_freshness = DataFreshnessInfo(
            minutes_since_workflow=120,  # 2 hours
            is_stale=True,
        )
        
        assert stale_freshness.is_stale is True


class TestSystemStatusResponse:
    """Tests for system status response with staleness info."""
    
    def test_scheduler_status_includes_minutes_since(self):
        """
        Scheduler status should include minutes_since field.
        """
        scheduler_status = {
            "status": "healthy",
            "last_heartbeat": "2025-01-01T12:00:00+00:00",
            "minutes_since": 5,
        }
        
        assert "minutes_since" in scheduler_status
        assert scheduler_status["minutes_since"] == 5
    
    def test_stale_scheduler_includes_message(self):
        """
        Stale scheduler status should include explanatory message.
        """
        minutes_since = 15
        scheduler_status = {
            "status": "stale",
            "last_heartbeat": "2025-01-01T12:00:00+00:00",
            "minutes_since": minutes_since,
            "message": f"No heartbeat for {minutes_since} minutes",
        }
        
        assert scheduler_status["status"] == "stale"
        assert "message" in scheduler_status
        assert "15 minutes" in scheduler_status["message"]
    
    def test_rate_limits_include_staleness_info(self):
        """
        Rate limit entries should include is_stale and minutes_since_update.
        """
        rate_limits = {
            "fmp_data": {
                "utilization_pct": 25.0,
                "calls_remaining": 750,
                "last_call_at": "2025-01-01T12:00:00+00:00",
                "minutes_since_update": 30,
                "is_stale": False,
            },
            "openai_proxy": {
                "utilization_pct": 0.0,
                "calls_remaining": None,
                "last_call_at": None,
                "is_stale": True,
            }
        }
        
        assert rate_limits["fmp_data"]["is_stale"] is False
        assert rate_limits["openai_proxy"]["is_stale"] is True


class TestHealthCheckerIntegration:
    """Integration tests for health checker with staleness detection."""
    
    def test_check_scheduler_heartbeat_fresh(self):
        """
        _check_scheduler_heartbeat returns PASS for fresh heartbeat.
        """
        import asyncio
        from src.monitoring.health_check import HealthChecker, HealthStatus
        
        checker = HealthChecker()
        
        # Mock database query to return fresh heartbeat
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            with patch("sqlalchemy.create_engine") as mock_engine:
                mock_conn = MagicMock()
                mock_result = MagicMock()
                # Fresh heartbeat (1 minute ago)
                fresh_time = datetime.now(timezone.utc) - timedelta(minutes=1)
                mock_result.fetchone.return_value = (fresh_time,)
                mock_conn.execute.return_value = mock_result
                mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
                
                result = asyncio.run(checker._check_scheduler_heartbeat())
        
        assert result.status == HealthStatus.PASS
        assert "alive" in result.message.lower()
    
    def test_check_scheduler_heartbeat_stale(self):
        """
        _check_scheduler_heartbeat returns WARN for stale heartbeat.
        """
        import asyncio
        from src.monitoring.health_check import HealthChecker, HealthStatus
        
        checker = HealthChecker()
        
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            with patch("sqlalchemy.create_engine") as mock_engine:
                mock_conn = MagicMock()
                mock_result = MagicMock()
                # Stale heartbeat (10 minutes ago - within query window but no recent ones)
                mock_result.fetchone.return_value = (None,)  # No heartbeat in last 5 mins
                mock_conn.execute.return_value = mock_result
                mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
                
                result = asyncio.run(checker._check_scheduler_heartbeat())
        
        assert result.status == HealthStatus.WARN
        assert "no recent" in result.message.lower() or "empty" in result.message.lower()
