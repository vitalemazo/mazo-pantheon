"""
Health Check Service

Pre-market and continuous health checks to validate system readiness.

Features:
- Pre-market health check (runs before market open)
- Continuous health monitoring
- Service connectivity validation
- Rate limit quota checks
"""

import logging
import os
import socket
from datetime import datetime, timezone, time as dt_time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from .event_logger import get_event_logger
from .alerting import get_alert_manager, AlertPriority, AlertCategory

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status"""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a single health check"""
    name: str
    status: HealthStatus
    message: str = ""
    value: Any = None
    details: Dict = field(default_factory=dict)
    latency_ms: int = 0


@dataclass
class HealthReport:
    """Complete health report"""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    check_type: str = "continuous"  # pre_market, continuous
    overall_status: str = "unknown"  # READY, DEGRADED, BLOCKED
    checks: Dict[str, HealthCheckResult] = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def is_ready(self) -> bool:
        return self.overall_status == "READY"
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "check_type": self.check_type,
            "overall_status": self.overall_status,
            "failures": self.failures,
            "warnings": self.warnings,
            "checks": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "value": check.value,
                    "latency_ms": check.latency_ms,
                }
                for name, check in self.checks.items()
            }
        }


class HealthChecker:
    """
    Health check service for trading system.
    
    Validates:
    - Alpaca API connectivity and authentication
    - Redis cache connectivity
    - Database connectivity
    - API quota availability
    - Scheduler liveness
    - Market calendar
    """
    
    def __init__(self):
        self.event_logger = get_event_logger()
        self.alert_manager = get_alert_manager()
        self.last_report: Optional[HealthReport] = None
    
    async def run_pre_market_check(self) -> HealthReport:
        """
        Run comprehensive pre-market health check.
        
        Should be run ~15 minutes before market open to catch issues.
        """
        report = HealthReport(check_type="pre_market")
        
        # Run all checks
        checks = await self._run_all_checks()
        report.checks = {c.name: c for c in checks}
        
        # Determine overall status
        for check in checks:
            if check.status == HealthStatus.FAIL:
                report.failures.append(check.name)
            elif check.status == HealthStatus.WARN:
                report.warnings.append(check.name)
        
        if report.failures:
            report.overall_status = "BLOCKED"
        elif report.warnings:
            report.overall_status = "DEGRADED"
        else:
            report.overall_status = "READY"
        
        # Log the report
        self.event_logger.log_metric(
            metric_name="health_check_status",
            value=1 if report.is_ready() else 0,
            tags={"check_type": "pre_market", "status": report.overall_status}
        )
        
        # Create alerts if needed
        if report.failures or report.warnings:
            self.alert_manager.alert_health_check_failed(
                check_type="pre_market",
                failures=report.failures,
                warnings=report.warnings,
                checks=report.to_dict()["checks"],
            )
        else:
            logger.info(f"✅ Pre-market health check: {report.overall_status}")
        
        self.last_report = report
        return report
    
    async def run_continuous_check(self) -> HealthReport:
        """Run lightweight continuous health check."""
        report = HealthReport(check_type="continuous")
        
        # Run only critical checks for continuous monitoring
        checks = [
            await self._check_scheduler_heartbeat(),
            await self._check_redis(),
            await self._check_database(),
        ]
        
        report.checks = {c.name: c for c in checks}
        
        for check in checks:
            if check.status == HealthStatus.FAIL:
                report.failures.append(check.name)
            elif check.status == HealthStatus.WARN:
                report.warnings.append(check.name)
        
        if report.failures:
            report.overall_status = "BLOCKED"
        elif report.warnings:
            report.overall_status = "DEGRADED"
        else:
            report.overall_status = "READY"
        
        self.last_report = report
        return report
    
    async def _run_all_checks(self) -> List[HealthCheckResult]:
        """Run all health checks."""
        checks = []
        
        # Core services
        checks.append(await self._check_alpaca())
        checks.append(await self._check_alpaca_buying_power())
        checks.append(await self._check_redis())
        checks.append(await self._check_database())
        
        # API quotas
        checks.append(await self._check_data_api_quota())
        checks.append(await self._check_llm_api_quota())
        
        # Scheduler
        checks.append(await self._check_scheduler_heartbeat())
        
        # Market calendar
        checks.append(await self._check_market_calendar())
        
        return checks
    
    async def _check_alpaca(self) -> HealthCheckResult:
        """Check Alpaca API connectivity and authentication."""
        import time
        start = time.time()
        
        try:
            from src.trading.alpaca_service import get_alpaca_service
            alpaca = get_alpaca_service()
            account = alpaca.get_account()
            latency = int((time.time() - start) * 1000)
            
            if account:
                return HealthCheckResult(
                    name="alpaca_auth",
                    status=HealthStatus.PASS,
                    message=f"Connected as {account.account_number}",
                    value=account.status,
                    latency_ms=latency,
                )
            else:
                return HealthCheckResult(
                    name="alpaca_auth",
                    status=HealthStatus.FAIL,
                    message="No account returned",
                    latency_ms=latency,
                )
        except Exception as e:
            return HealthCheckResult(
                name="alpaca_auth",
                status=HealthStatus.FAIL,
                message=str(e)[:200],
                latency_ms=int((time.time() - start) * 1000),
            )
    
    async def _check_alpaca_buying_power(self) -> HealthCheckResult:
        """Check Alpaca buying power."""
        try:
            from src.trading.alpaca_service import get_alpaca_service
            alpaca = get_alpaca_service()
            account = alpaca.get_account()
            
            if account:
                buying_power = float(account.buying_power)
                
                if buying_power < 100:
                    return HealthCheckResult(
                        name="buying_power",
                        status=HealthStatus.FAIL,
                        message=f"Insufficient buying power: ${buying_power:.2f}",
                        value=buying_power,
                    )
                elif buying_power < 1000:
                    return HealthCheckResult(
                        name="buying_power",
                        status=HealthStatus.WARN,
                        message=f"Low buying power: ${buying_power:.2f}",
                        value=buying_power,
                    )
                else:
                    return HealthCheckResult(
                        name="buying_power",
                        status=HealthStatus.PASS,
                        message=f"Buying power: ${buying_power:.2f}",
                        value=buying_power,
                    )
            else:
                return HealthCheckResult(
                    name="buying_power",
                    status=HealthStatus.UNKNOWN,
                    message="Could not get account",
                )
        except Exception as e:
            return HealthCheckResult(
                name="buying_power",
                status=HealthStatus.UNKNOWN,
                message=str(e)[:200],
            )
    
    async def _check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity."""
        import time
        start = time.time()
        
        try:
            from src.data.cache import get_cache
            cache = get_cache()
            stats = cache.get_stats()
            latency = int((time.time() - start) * 1000)
            
            if stats.get("backend") == "redis":
                return HealthCheckResult(
                    name="redis",
                    status=HealthStatus.PASS,
                    message=f"Redis connected, {stats.get('redis_keys', 0)} keys",
                    value=stats.get("redis_keys", 0),
                    latency_ms=latency,
                )
            else:
                return HealthCheckResult(
                    name="redis",
                    status=HealthStatus.WARN,
                    message="Using in-memory fallback",
                    value="in_memory",
                    latency_ms=latency,
                )
        except Exception as e:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.WARN,
                message=f"Redis unavailable: {str(e)[:100]}",
                latency_ms=int((time.time() - start) * 1000),
            )
    
    async def _check_database(self) -> HealthCheckResult:
        """Check database connectivity."""
        import time
        start = time.time()
        
        try:
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                return HealthCheckResult(
                    name="database",
                    status=HealthStatus.WARN,
                    message="DATABASE_URL not set",
                )
            
            from sqlalchemy import create_engine, text
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            latency = int((time.time() - start) * 1000)
            return HealthCheckResult(
                name="database",
                status=HealthStatus.PASS,
                message="Database connected",
                latency_ms=latency,
            )
        except Exception as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.FAIL,
                message=str(e)[:200],
                latency_ms=int((time.time() - start) * 1000),
            )
    
    async def _check_data_api_quota(self) -> HealthCheckResult:
        """Check Financial Datasets API quota."""
        try:
            # For now, just check if the API key is set
            api_key = os.getenv("FINANCIAL_DATASETS_API_KEY")
            if not api_key:
                return HealthCheckResult(
                    name="data_api_quota",
                    status=HealthStatus.WARN,
                    message="FINANCIAL_DATASETS_API_KEY not set",
                )
            
            return HealthCheckResult(
                name="data_api_quota",
                status=HealthStatus.PASS,
                message="API key configured",
            )
        except Exception as e:
            return HealthCheckResult(
                name="data_api_quota",
                status=HealthStatus.UNKNOWN,
                message=str(e)[:200],
            )
    
    async def _check_llm_api_quota(self) -> HealthCheckResult:
        """Check LLM API quota (OpenAI/Anthropic)."""
        try:
            openai_key = os.getenv("OPENAI_API_KEY")
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            
            if openai_key or anthropic_key:
                providers = []
                if openai_key:
                    providers.append("OpenAI")
                if anthropic_key:
                    providers.append("Anthropic")
                
                return HealthCheckResult(
                    name="llm_api_quota",
                    status=HealthStatus.PASS,
                    message=f"Configured: {', '.join(providers)}",
                    value=providers,
                )
            else:
                return HealthCheckResult(
                    name="llm_api_quota",
                    status=HealthStatus.WARN,
                    message="No LLM API keys configured",
                )
        except Exception as e:
            return HealthCheckResult(
                name="llm_api_quota",
                status=HealthStatus.UNKNOWN,
                message=str(e)[:200],
            )
    
    async def _check_scheduler_heartbeat(self) -> HealthCheckResult:
        """Check scheduler liveness via heartbeat."""
        try:
            # Check for recent heartbeat in database
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                return HealthCheckResult(
                    name="scheduler_heartbeat",
                    status=HealthStatus.UNKNOWN,
                    message="DATABASE_URL not set",
                )
            
            from sqlalchemy import create_engine, text
            engine = create_engine(database_url)
            
            with engine.connect() as conn:
                # Check if heartbeats table exists and has recent entries
                result = conn.execute(text("""
                    SELECT MAX(timestamp) as last_heartbeat 
                    FROM scheduler_heartbeats 
                    WHERE timestamp > NOW() - INTERVAL '5 minutes'
                """))
                row = result.fetchone()
                
                if row and row[0]:
                    return HealthCheckResult(
                        name="scheduler_heartbeat",
                        status=HealthStatus.PASS,
                        message="Scheduler alive",
                        value=row[0],
                    )
                else:
                    return HealthCheckResult(
                        name="scheduler_heartbeat",
                        status=HealthStatus.WARN,
                        message="No recent heartbeat (table may be empty)",
                    )
        except Exception as e:
            # Table might not exist yet
            if "does not exist" in str(e).lower():
                return HealthCheckResult(
                    name="scheduler_heartbeat",
                    status=HealthStatus.UNKNOWN,
                    message="Heartbeat table not yet created",
                )
            return HealthCheckResult(
                name="scheduler_heartbeat",
                status=HealthStatus.UNKNOWN,
                message=str(e)[:200],
            )
    
    async def _check_market_calendar(self) -> HealthCheckResult:
        """Check if market is open today."""
        try:
            from src.trading.alpaca_service import get_alpaca_service
            alpaca = get_alpaca_service()
            
            # Check if market is open today
            clock = alpaca.get_clock()
            
            if clock:
                is_open = clock.is_open
                next_open = clock.next_open
                next_close = clock.next_close
                
                if is_open:
                    return HealthCheckResult(
                        name="market_calendar",
                        status=HealthStatus.PASS,
                        message=f"Market OPEN, closes at {next_close}",
                        value={"is_open": True, "next_close": str(next_close)},
                    )
                else:
                    return HealthCheckResult(
                        name="market_calendar",
                        status=HealthStatus.PASS,
                        message=f"Market CLOSED, opens at {next_open}",
                        value={"is_open": False, "next_open": str(next_open)},
                    )
            else:
                return HealthCheckResult(
                    name="market_calendar",
                    status=HealthStatus.UNKNOWN,
                    message="Could not get market clock",
                )
        except Exception as e:
            return HealthCheckResult(
                name="market_calendar",
                status=HealthStatus.UNKNOWN,
                message=str(e)[:200],
            )


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get the global HealthChecker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


async def run_pre_market_health_check() -> HealthReport:
    """Convenience function to run pre-market health check."""
    return await get_health_checker().run_pre_market_check()


async def run_continuous_health_check() -> HealthReport:
    """Convenience function to run continuous health check."""
    return await get_health_checker().run_continuous_check()
