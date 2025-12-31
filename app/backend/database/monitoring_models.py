"""
Monitoring Models for TimescaleDB

These tables use TimescaleDB hypertables for efficient time-series storage
and querying of monitoring data.

Tables:
- workflow_events: Every step in a workflow execution
- agent_signals: All agent outputs with full context
- mazo_research: Mazo queries, responses, and usage tracking
- pm_decisions: Portfolio Manager decisions with full transparency
- trade_executions: Order lifecycle tracking with quality metrics
- performance_metrics: Time-series metrics (P&L, Sharpe, etc.)
- system_health: API latency, rate limits, connectivity
- llm_api_calls: LLM call tracking for cost and performance
- alerts: Priority-based alerting system
- rate_limit_tracking: Real-time API quota monitoring
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean, 
    JSON, Float, Index, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from .connection import Base
import uuid


# =============================================================================
# WORKFLOW EVENTS - Track every step in the trading pipeline
# =============================================================================
class WorkflowEvent(Base):
    """Every step in a workflow execution - hypertable on timestamp"""
    __tablename__ = "workflow_events"
    
    # Primary key is composite: timestamp + id for TimescaleDB
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Workflow identification
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    workflow_type = Column(String(50), nullable=False)  # trading_cycle, analysis, backtest
    
    # Step tracking
    step_name = Column(String(100), nullable=False)  # strategy_screening, mazo_research, agent_analysis, pm_decision, execution
    step_index = Column(Integer, nullable=True)  # Order in pipeline
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Status
    status = Column(String(20), nullable=False)  # started, completed, failed, skipped
    error_message = Column(Text, nullable=True)
    
    # Context
    ticker = Column(String(20), nullable=True)  # If step is ticker-specific
    payload = Column(JSONB, nullable=True)  # Step-specific data
    
    __table_args__ = (
        Index('idx_workflow_events_workflow', 'workflow_id'),
        Index('idx_workflow_events_step', 'step_name'),
        Index('idx_workflow_events_ticker', 'ticker'),
    )


# =============================================================================
# AGENT SIGNALS - All agent outputs with reasoning
# =============================================================================
class AgentSignal(Base):
    """Individual agent signal with full context - hypertable on timestamp"""
    __tablename__ = "agent_signals"
    
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Links
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Agent info
    agent_id = Column(String(50), nullable=False, index=True)  # warren_buffett, cathie_wood, etc.
    agent_type = Column(String(50), nullable=True)  # fundamental, technical, sentiment, valuation
    
    # Signal
    ticker = Column(String(20), nullable=False, index=True)
    signal = Column(String(20), nullable=False)  # bullish, bearish, neutral
    confidence = Column(Float, nullable=True)  # 0-100
    
    # Reasoning
    reasoning = Column(Text, nullable=True)
    key_metrics = Column(JSONB, nullable=True)  # Agent-specific metrics used
    
    # Timing
    latency_ms = Column(Integer, nullable=True)  # How long this agent took
    
    # Accuracy (filled in later when trade closes)
    was_correct = Column(Boolean, nullable=True)
    actual_return = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('idx_agent_signals_agent', 'agent_id'),
        Index('idx_agent_signals_ticker', 'ticker'),
    )


# =============================================================================
# MAZO RESEARCH - Track Mazo usage and effectiveness
# =============================================================================
class MazoResearch(Base):
    """Mazo research queries and responses - hypertable on timestamp"""
    __tablename__ = "mazo_research"
    
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Links
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Query
    ticker = Column(String(20), nullable=False, index=True)
    query = Column(Text, nullable=False)
    mode = Column(String(20), nullable=True)  # Workflow mode when called
    
    # Response
    response = Column(Text, nullable=True)
    response_length = Column(Integer, nullable=True)
    sources_count = Column(Integer, nullable=True)
    sources = Column(JSONB, nullable=True)
    
    # Sentiment extraction
    sentiment = Column(String(20), nullable=True)  # bullish, bearish, neutral
    sentiment_confidence = Column(String(20), nullable=True)  # high, medium, low
    key_points = Column(JSONB, nullable=True)
    
    # Status
    success = Column(Boolean, nullable=False, default=False)
    error = Column(String(200), nullable=True)  # timeout, rate_limit, empty_response, etc.
    
    # Timing
    latency_ms = Column(Integer, nullable=True)
    
    # PM follow-through (filled in after PM decision)
    pm_followed = Column(Boolean, nullable=True)  # Did PM agree with Mazo?
    pm_action = Column(String(20), nullable=True)  # What PM actually did
    
    __table_args__ = (
        Index('idx_mazo_research_ticker', 'ticker'),
    )


# =============================================================================
# PM DECISIONS - Full transparency on Portfolio Manager decisions
# =============================================================================
class PMDecision(Base):
    """Portfolio Manager decision with full agent context - hypertable on timestamp"""
    __tablename__ = "pm_decisions"
    
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Links
    workflow_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Decision
    ticker = Column(String(20), nullable=False, index=True)
    action = Column(String(20), nullable=False)  # buy, sell, short, cover, hold
    quantity = Column(Integer, nullable=True)
    
    # Risk parameters
    stop_loss_pct = Column(Float, nullable=True)
    take_profit_pct = Column(Float, nullable=True)
    position_size_pct = Column(Float, nullable=True)
    
    # Agent inputs
    agents_received = Column(JSONB, nullable=True)  # All agent signals received
    agents_considered = Column(JSONB, nullable=True)  # Which were actually weighted
    agents_ignored = Column(JSONB, nullable=True)  # Which were ignored and why
    
    # Consensus analysis
    bullish_count = Column(Integer, nullable=True)
    bearish_count = Column(Integer, nullable=True)
    neutral_count = Column(Integer, nullable=True)
    consensus_direction = Column(String(20), nullable=True)
    consensus_score = Column(Float, nullable=True)  # 0-100 weighted consensus
    
    # Mazo context
    mazo_received = Column(Boolean, nullable=False, default=False)
    mazo_considered = Column(Boolean, nullable=False, default=False)
    mazo_sentiment = Column(String(20), nullable=True)
    mazo_bypass_reason = Column(String(100), nullable=True)
    
    # Decision transparency
    action_matches_consensus = Column(Boolean, nullable=True)
    override_reason = Column(Text, nullable=True)  # If PM overrode consensus
    reasoning_raw = Column(Text, nullable=True)  # Full PM reasoning
    confidence = Column(Float, nullable=True)
    
    # Portfolio context
    portfolio_equity = Column(Float, nullable=True)
    portfolio_cash = Column(Float, nullable=True)
    existing_position_qty = Column(Float, nullable=True)
    
    # Timing
    latency_ms = Column(Integer, nullable=True)
    
    # Outcome (filled in later)
    was_executed = Column(Boolean, nullable=True)
    execution_order_id = Column(String(100), nullable=True)
    actual_return = Column(Float, nullable=True)
    was_profitable = Column(Boolean, nullable=True)
    
    __table_args__ = (
        Index('idx_pm_decisions_ticker', 'ticker'),
        Index('idx_pm_decisions_action', 'action'),
    )


# =============================================================================
# TRADE EXECUTIONS - Order lifecycle with quality metrics
# =============================================================================
class TradeExecution(Base):
    """Order execution with quality metrics - hypertable on timestamp"""
    __tablename__ = "trade_executions"
    
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Links
    workflow_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    pm_decision_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Order identification
    order_id = Column(String(100), nullable=False, index=True)  # Alpaca order ID
    client_order_id = Column(String(100), nullable=True)
    
    # Order details
    ticker = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # buy, sell
    order_type = Column(String(20), nullable=False)  # market, limit, stop, stop_limit
    quantity = Column(Float, nullable=False)
    limit_price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)
    
    # Timing
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    filled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    
    # Fill details
    filled_qty = Column(Float, nullable=True)
    filled_avg_price = Column(Float, nullable=True)
    
    # Quality metrics
    expected_price = Column(Float, nullable=True)  # Price at time of decision
    slippage_bps = Column(Float, nullable=True)  # Basis points slippage
    fill_latency_ms = Column(Integer, nullable=True)  # Time from submit to fill
    
    # Status
    status = Column(String(20), nullable=False)  # new, accepted, filled, partial, cancelled, rejected, expired
    reject_reason = Column(String(200), nullable=True)
    
    # Fees
    commission = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('idx_trade_executions_order', 'order_id'),
        Index('idx_trade_executions_ticker', 'ticker'),
        Index('idx_trade_executions_status', 'status'),
    )


# =============================================================================
# PERFORMANCE METRICS - Time-series metrics
# =============================================================================
class PerformanceMetric(Base):
    """Time-series performance metrics - hypertable on timestamp"""
    __tablename__ = "performance_metrics"
    
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Metric identification
    metric_name = Column(String(100), nullable=False, index=True)
    # e.g., daily_pnl, sharpe_ratio, win_rate, agent_accuracy, total_equity
    
    # Value
    value = Column(Float, nullable=False)
    
    # Optional context
    ticker = Column(String(20), nullable=True)  # If ticker-specific
    agent_id = Column(String(50), nullable=True)  # If agent-specific
    tags = Column(JSONB, nullable=True)  # Additional tags for filtering
    
    __table_args__ = (
        Index('idx_performance_metrics_name', 'metric_name'),
    )


# =============================================================================
# SYSTEM HEALTH - API latency, rate limits, connectivity
# =============================================================================
class SystemHealth(Base):
    """System health metrics - hypertable on timestamp"""
    __tablename__ = "system_health"
    
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Service identification
    service = Column(String(50), nullable=False, index=True)
    # e.g., alpaca, openai, anthropic, financial_datasets, redis, postgres, scheduler
    
    # Health metrics
    status = Column(String(20), nullable=False)  # healthy, degraded, down
    latency_ms = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True, default=0)
    
    # Rate limiting
    rate_limit_remaining = Column(Integer, nullable=True)
    rate_limit_reset_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional context
    details = Column(JSONB, nullable=True)
    
    __table_args__ = (
        Index('idx_system_health_service', 'service'),
    )


# =============================================================================
# LLM API CALLS - Track LLM usage for cost and performance
# =============================================================================
class LLMAPICall(Base):
    """LLM API call tracking - hypertable on timestamp"""
    __tablename__ = "llm_api_calls"
    
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Links
    workflow_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Call identification
    agent_id = Column(String(50), nullable=True, index=True)  # Which agent made the call
    call_purpose = Column(String(100), nullable=True)  # analysis, decision, summary
    
    # Model info
    provider = Column(String(50), nullable=False)  # openai, anthropic, ollama
    model = Column(String(100), nullable=False)  # gpt-4, claude-3-opus, etc.
    
    # Token usage
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    
    # Timing
    latency_ms = Column(Integer, nullable=True)  # Time to first token
    total_time_ms = Column(Integer, nullable=True)  # Total response time
    
    # Status
    success = Column(Boolean, nullable=False, default=False)
    error_type = Column(String(50), nullable=True)  # timeout, rate_limit, invalid_response, context_length
    error_message = Column(Text, nullable=True)
    
    # Retry tracking
    retry_count = Column(Integer, nullable=False, default=0)
    
    # Cost estimation
    estimated_cost_usd = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('idx_llm_api_calls_agent', 'agent_id'),
        Index('idx_llm_api_calls_model', 'model'),
    )


# =============================================================================
# ALERTS - Priority-based alerting
# =============================================================================
class Alert(Base):
    """Priority-based alerts - hypertable on timestamp"""
    __tablename__ = "alerts"
    
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Alert classification
    priority = Column(String(5), nullable=False, index=True)  # P0, P1, P2
    category = Column(String(50), nullable=False, index=True)  # rate_limit, pipeline, execution, system
    
    # Content
    title = Column(String(200), nullable=False)
    details = Column(JSONB, nullable=True)
    
    # Status
    acknowledged = Column(Boolean, nullable=False, default=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    
    resolved = Column(Boolean, nullable=False, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Context
    workflow_id = Column(UUID(as_uuid=True), nullable=True)
    ticker = Column(String(20), nullable=True)
    service = Column(String(50), nullable=True)
    
    __table_args__ = (
        Index('idx_alerts_priority', 'priority'),
        Index('idx_alerts_category', 'category'),
        Index('idx_alerts_unresolved', 'resolved'),
    )


# =============================================================================
# RATE LIMIT TRACKING - Real-time API quota monitoring
# =============================================================================
class RateLimitTracking(Base):
    """API rate limit tracking - hypertable on timestamp"""
    __tablename__ = "rate_limit_tracking"
    
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # API identification
    api_name = Column(String(50), nullable=False, index=True)
    # e.g., financial_datasets, openai, anthropic, alpaca
    
    # Usage
    calls_made = Column(Integer, nullable=False, default=0)
    calls_remaining = Column(Integer, nullable=True)
    
    # Window
    window_start = Column(DateTime(timezone=True), nullable=True)
    window_resets_at = Column(DateTime(timezone=True), nullable=True)
    
    # Utilization
    utilization_pct = Column(Float, nullable=True)  # 0-100
    
    __table_args__ = (
        Index('idx_rate_limit_api', 'api_name'),
    )


# =============================================================================
# SCHEDULER HEARTBEAT - Track scheduler liveness
# =============================================================================
class SchedulerHeartbeat(Base):
    """Scheduler heartbeat for liveness detection - hypertable on timestamp"""
    __tablename__ = "scheduler_heartbeats"

    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Status - matches actual table schema
    status = Column(Text, nullable=False, default="running")
    active_jobs = Column(Integer, nullable=True, default=0)
    details = Column(JSONB, nullable=True)  # Store extra info as JSON


# =============================================================================
# SQL for creating TimescaleDB hypertables
# =============================================================================
HYPERTABLE_SQL = """
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Convert tables to hypertables (time-series optimized)
SELECT create_hypertable('workflow_events', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('agent_signals', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('mazo_research', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('pm_decisions', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('trade_executions', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('performance_metrics', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('system_health', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('llm_api_calls', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('alerts', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('rate_limit_tracking', 'timestamp', if_not_exists => TRUE);
SELECT create_hypertable('scheduler_heartbeats', 'timestamp', if_not_exists => TRUE);

-- Set up retention policies (automatic data expiration)
SELECT add_retention_policy('workflow_events', INTERVAL '30 days', if_not_exists => TRUE);
SELECT add_retention_policy('agent_signals', INTERVAL '90 days', if_not_exists => TRUE);
-- trade_executions: no retention (keep forever)
-- pm_decisions: no retention (keep forever for audit)
SELECT add_retention_policy('performance_metrics', INTERVAL '365 days', if_not_exists => TRUE);
SELECT add_retention_policy('system_health', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('llm_api_calls', INTERVAL '30 days', if_not_exists => TRUE);
SELECT add_retention_policy('alerts', INTERVAL '30 days', if_not_exists => TRUE);
SELECT add_retention_policy('rate_limit_tracking', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('scheduler_heartbeats', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('mazo_research', INTERVAL '90 days', if_not_exists => TRUE);

-- Create continuous aggregates for common queries
-- Daily agent performance
CREATE MATERIALIZED VIEW IF NOT EXISTS agent_daily_performance
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', timestamp) AS day,
    agent_id,
    COUNT(*) as signal_count,
    COUNT(*) FILTER (WHERE signal = 'bullish') as bullish_count,
    COUNT(*) FILTER (WHERE signal = 'bearish') as bearish_count,
    AVG(confidence) as avg_confidence,
    COUNT(*) FILTER (WHERE was_correct = TRUE) as correct_count,
    COUNT(*) FILTER (WHERE was_correct = FALSE) as incorrect_count
FROM agent_signals
GROUP BY day, agent_id
WITH NO DATA;

-- Hourly system health summary
CREATE MATERIALIZED VIEW IF NOT EXISTS system_health_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', timestamp) AS hour,
    service,
    AVG(latency_ms) as avg_latency_ms,
    MAX(latency_ms) as max_latency_ms,
    SUM(error_count) as total_errors,
    MIN(rate_limit_remaining) as min_rate_limit_remaining
FROM system_health
GROUP BY hour, service
WITH NO DATA;

-- Refresh policies for continuous aggregates
SELECT add_continuous_aggregate_policy('agent_daily_performance',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('system_health_hourly',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE);
"""
