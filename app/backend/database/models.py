from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, ForeignKey, Float, Enum
from sqlalchemy.sql import func
from .connection import Base
import enum


class TradeAction(enum.Enum):
    """Trade action types"""
    BUY = "buy"
    SELL = "sell"
    SHORT = "short"
    COVER = "cover"
    HOLD = "hold"


class TradeStatus(enum.Enum):
    """Trade execution status"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    FAILED = "failed"


class WatchlistStatus(enum.Enum):
    """Watchlist item status"""
    WATCHING = "watching"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ScheduledTaskStatus(enum.Enum):
    """Scheduled task status"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class HedgeFundFlow(Base):
    """Table to store React Flow configurations (nodes, edges, viewport)"""
    __tablename__ = "hedge_fund_flows"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Flow metadata
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # React Flow state
    nodes = Column(JSON, nullable=False)  # Store React Flow nodes as JSON
    edges = Column(JSON, nullable=False)  # Store React Flow edges as JSON
    viewport = Column(JSON, nullable=True)  # Store viewport state (zoom, x, y)
    data = Column(JSON, nullable=True)  # Store node internal states (tickers, models, etc.)
    
    # Additional metadata
    is_template = Column(Boolean, default=False)  # Mark as template for reuse
    tags = Column(JSON, nullable=True)  # Store tags for categorization


class HedgeFundFlowRun(Base):
    """Table to track individual execution runs of a hedge fund flow"""
    __tablename__ = "hedge_fund_flow_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(Integer, ForeignKey("hedge_fund_flows.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Run execution tracking
    status = Column(String(50), nullable=False, default="IDLE")  # IDLE, IN_PROGRESS, COMPLETE, ERROR
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Run configuration
    trading_mode = Column(String(50), nullable=False, default="one-time")  # one-time, continuous, advisory
    schedule = Column(String(50), nullable=True)  # hourly, daily, weekly (for continuous mode)
    duration = Column(String(50), nullable=True)  # 1day, 1week, 1month (for continuous mode)
    
    # Run data
    request_data = Column(JSON, nullable=True)  # Store the request parameters (tickers, agents, models, etc.)
    initial_portfolio = Column(JSON, nullable=True)  # Store initial portfolio state
    final_portfolio = Column(JSON, nullable=True)  # Store final portfolio state
    results = Column(JSON, nullable=True)  # Store the output/results from the run
    error_message = Column(Text, nullable=True)  # Store error details if run failed
    
    # Metadata
    run_number = Column(Integer, nullable=False, default=1)  # Sequential run number for this flow


class HedgeFundFlowRunCycle(Base):
    """Individual analysis cycles within a trading session"""
    __tablename__ = "hedge_fund_flow_run_cycles"
    
    id = Column(Integer, primary_key=True, index=True)
    flow_run_id = Column(Integer, ForeignKey("hedge_fund_flow_runs.id"), nullable=False, index=True)
    cycle_number = Column(Integer, nullable=False)  # 1, 2, 3, etc. within the run
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Analysis results
    analyst_signals = Column(JSON, nullable=True)  # All agent decisions/signals
    trading_decisions = Column(JSON, nullable=True)  # Portfolio manager decisions
    executed_trades = Column(JSON, nullable=True)  # Actual trades executed (paper trading)
    
    # Portfolio state after this cycle
    portfolio_snapshot = Column(JSON, nullable=True)  # Cash, positions, performance metrics
    
    # Performance metrics for this cycle
    performance_metrics = Column(JSON, nullable=True)  # Returns, sharpe ratio, etc.
    
    # Execution tracking
    status = Column(String(50), nullable=False, default="IN_PROGRESS")  # IN_PROGRESS, COMPLETED, ERROR
    error_message = Column(Text, nullable=True)  # Store error details if cycle failed
    
    # Cost tracking
    llm_calls_count = Column(Integer, nullable=True, default=0)  # Number of LLM calls made
    api_calls_count = Column(Integer, nullable=True, default=0)  # Number of financial API calls made
    estimated_cost = Column(String(20), nullable=True)  # Estimated cost in USD
    
    # Metadata
    trigger_reason = Column(String(100), nullable=True)  # scheduled, manual, market_event, etc.
    market_conditions = Column(JSON, nullable=True)  # Market data snapshot at cycle start


class ApiKey(Base):
    """Table to store API keys for various services"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # API key details
    provider = Column(String(100), nullable=False, unique=True, index=True)  # e.g., "ANTHROPIC_API_KEY"
    key_value = Column(Text, nullable=False)  # The actual API key (encrypted in production)
    is_active = Column(Boolean, default=True)  # Enable/disable without deletion
    
    # Optional metadata
    description = Column(Text, nullable=True)  # Human-readable description
    last_used = Column(DateTime(timezone=True), nullable=True)  # Track usage


class TradeHistory(Base):
    """Track all executed trades for performance analysis"""
    __tablename__ = "trade_history"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Trade identification
    order_id = Column(String(100), nullable=True, index=True)  # Alpaca order ID
    ticker = Column(String(20), nullable=False, index=True)
    
    # Trade details
    action = Column(String(20), nullable=False)  # buy, sell, short, cover
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    
    # Timing
    entry_time = Column(DateTime(timezone=True), nullable=True)
    exit_time = Column(DateTime(timezone=True), nullable=True)
    
    # Risk management
    stop_loss_price = Column(Float, nullable=True)
    take_profit_price = Column(Float, nullable=True)
    stop_loss_pct = Column(Float, nullable=True)
    take_profit_pct = Column(Float, nullable=True)
    
    # Strategy
    strategy = Column(String(50), nullable=True)  # momentum, mean_reversion, trend, etc.
    strategy_params = Column(JSON, nullable=True)  # Parameters used
    
    # Results
    realized_pnl = Column(Float, nullable=True)
    return_pct = Column(Float, nullable=True)
    holding_period_hours = Column(Float, nullable=True)
    
    # Status
    status = Column(String(20), nullable=False, default="pending")  # pending, filled, closed
    
    # Metadata
    notes = Column(Text, nullable=True)
    signals = Column(JSON, nullable=True)  # Agent signals that led to this trade


class DailyPerformance(Base):
    """Daily portfolio performance snapshots"""
    __tablename__ = "daily_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Portfolio state
    starting_equity = Column(Float, nullable=False)
    ending_equity = Column(Float, nullable=False)
    high_equity = Column(Float, nullable=True)
    low_equity = Column(Float, nullable=True)
    
    # P&L
    realized_pnl = Column(Float, nullable=False, default=0)
    unrealized_pnl = Column(Float, nullable=False, default=0)
    total_pnl = Column(Float, nullable=False, default=0)
    return_pct = Column(Float, nullable=False, default=0)
    
    # Trading activity
    trades_count = Column(Integer, nullable=False, default=0)
    winning_trades = Column(Integer, nullable=False, default=0)
    losing_trades = Column(Integer, nullable=False, default=0)
    win_rate = Column(Float, nullable=True)
    
    # Best/worst
    biggest_winner = Column(Float, nullable=True)
    biggest_winner_ticker = Column(String(20), nullable=True)
    biggest_loser = Column(Float, nullable=True)
    biggest_loser_ticker = Column(String(20), nullable=True)
    
    # Risk metrics
    max_drawdown = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    
    # Positions
    positions_count = Column(Integer, nullable=False, default=0)
    positions_snapshot = Column(JSON, nullable=True)


class Watchlist(Base):
    """Watchlist for potential trades"""
    __tablename__ = "watchlist"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Stock info
    ticker = Column(String(20), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    sector = Column(String(100), nullable=True)
    
    # Entry criteria
    strategy = Column(String(50), nullable=True)  # momentum, mean_reversion, trend
    entry_target = Column(Float, nullable=True)  # Target entry price
    entry_condition = Column(String(50), nullable=True)  # above, below, breakout
    
    # Risk management
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    position_size_pct = Column(Float, nullable=True)  # % of portfolio
    
    # Tracking
    status = Column(String(20), nullable=False, default="watching")
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    triggered_price = Column(Float, nullable=True)
    
    # Analysis
    notes = Column(Text, nullable=True)
    signals = Column(JSON, nullable=True)  # Agent analysis
    mazo_research = Column(Text, nullable=True)
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)
    priority = Column(Integer, nullable=False, default=5)  # 1-10, 10 = highest


class ScheduledTask(Base):
    """Scheduled trading tasks"""
    __tablename__ = "scheduled_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Task definition
    name = Column(String(200), nullable=False)
    task_type = Column(String(50), nullable=False)  # health_check, scan, analyze, trade, report
    description = Column(Text, nullable=True)
    
    # Schedule (cron-like)
    schedule_cron = Column(String(100), nullable=True)  # Cron expression
    schedule_interval = Column(Integer, nullable=True)  # Minutes between runs
    schedule_time = Column(String(10), nullable=True)  # HH:MM format for daily tasks
    
    # Configuration
    parameters = Column(JSON, nullable=True)  # Task-specific config
    tickers = Column(JSON, nullable=True)  # List of tickers to analyze
    
    # Execution tracking
    status = Column(String(20), nullable=False, default="active")
    last_run = Column(DateTime(timezone=True), nullable=True)
    next_run = Column(DateTime(timezone=True), nullable=True)
    run_count = Column(Integer, nullable=False, default=0)
    
    # Results
    last_result = Column(JSON, nullable=True)
    last_error = Column(Text, nullable=True)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    
    # Control
    is_enabled = Column(Boolean, nullable=False, default=True)
    max_retries = Column(Integer, nullable=False, default=3)


class AgentPerformance(Base):
    """Track individual agent signal accuracy over time"""
    __tablename__ = "agent_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Agent identification
    agent_name = Column(String(100), nullable=False, unique=True, index=True)
    agent_type = Column(String(50), nullable=True)  # fundamental, technical, sentiment, etc.
    
    # Signal tracking
    total_signals = Column(Integer, nullable=False, default=0)
    bullish_signals = Column(Integer, nullable=False, default=0)
    bearish_signals = Column(Integer, nullable=False, default=0)
    neutral_signals = Column(Integer, nullable=False, default=0)
    
    # Accuracy metrics (calculated from closed trades)
    correct_predictions = Column(Integer, nullable=False, default=0)
    incorrect_predictions = Column(Integer, nullable=False, default=0)
    accuracy_rate = Column(Float, nullable=True)  # % of correct predictions
    
    # Performance when followed
    trades_following_signal = Column(Integer, nullable=False, default=0)
    avg_return_when_followed = Column(Float, nullable=True)
    total_pnl_when_followed = Column(Float, nullable=False, default=0)
    
    # Best/worst calls
    best_call_ticker = Column(String(20), nullable=True)
    best_call_return = Column(Float, nullable=True)
    worst_call_ticker = Column(String(20), nullable=True)
    worst_call_return = Column(Float, nullable=True)
    
    # Recent activity
    last_signal_date = Column(DateTime(timezone=True), nullable=True)
    last_accuracy_update = Column(DateTime(timezone=True), nullable=True)


class TradeDecisionContext(Base):
    """Store full context for each trade decision (for learning and analysis)"""
    __tablename__ = "trade_decision_context"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Link to trade
    trade_id = Column(Integer, ForeignKey("trade_history.id"), nullable=True, index=True)
    order_id = Column(String(100), nullable=True)
    ticker = Column(String(20), nullable=False, index=True)
    
    # Trigger source
    trigger_source = Column(String(50), nullable=False)  # manual, scheduler, automated
    workflow_mode = Column(String(50), nullable=True)  # full, research, signal, pre-research, post-research
    
    # Strategy signals
    strategy_signal = Column(String(20), nullable=True)  # LONG, SHORT, NEUTRAL
    strategy_confidence = Column(Float, nullable=True)
    strategy_name = Column(String(50), nullable=True)
    strategy_reasoning = Column(Text, nullable=True)
    
    # Mazo research
    mazo_sentiment = Column(String(20), nullable=True)  # bullish, bearish, neutral
    mazo_confidence = Column(String(20), nullable=True)  # high, medium, low
    mazo_key_points = Column(JSON, nullable=True)
    mazo_full_response = Column(Text, nullable=True)
    
    # All agent signals (comprehensive)
    agent_signals = Column(JSON, nullable=False)  # {agent_name: {signal, confidence, reasoning}}
    
    # Consensus
    bullish_count = Column(Integer, nullable=True)
    bearish_count = Column(Integer, nullable=True)
    neutral_count = Column(Integer, nullable=True)
    consensus_direction = Column(String(20), nullable=True)
    consensus_confidence = Column(Float, nullable=True)
    
    # Portfolio context at decision time
    portfolio_equity = Column(Float, nullable=True)
    portfolio_cash = Column(Float, nullable=True)
    existing_positions = Column(JSON, nullable=True)  # Positions at time of decision
    pending_orders = Column(JSON, nullable=True)
    
    # PM decision
    pm_action = Column(String(20), nullable=True)  # buy, sell, short, cover, hold
    pm_quantity = Column(Float, nullable=True)  # Supports fractional shares
    pm_confidence = Column(Float, nullable=True)
    pm_reasoning = Column(Text, nullable=True)
    pm_stop_loss_pct = Column(Float, nullable=True)
    pm_take_profit_pct = Column(Float, nullable=True)
    
    # Outcome (filled in later when trade closes)
    actual_return = Column(Float, nullable=True)
    was_profitable = Column(Boolean, nullable=True)
    outcome_notes = Column(Text, nullable=True)


class TradingStrategy(Base):
    """Trading strategy configurations"""
    __tablename__ = "trading_strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Strategy info
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    strategy_type = Column(String(50), nullable=False)  # momentum, mean_reversion, trend, dividend, earnings
    
    # Parameters
    parameters = Column(JSON, nullable=False)  # Strategy-specific params
    
    # Risk limits
    max_position_size = Column(Float, nullable=False, default=0.10)  # % of portfolio
    stop_loss_pct = Column(Float, nullable=False, default=0.05)  # 5% default
    take_profit_pct = Column(Float, nullable=False, default=0.10)  # 10% default
    max_daily_trades = Column(Integer, nullable=False, default=5)
    
    # Performance
    total_trades = Column(Integer, nullable=False, default=0)
    winning_trades = Column(Integer, nullable=False, default=0)
    total_pnl = Column(Float, nullable=False, default=0)
    avg_return = Column(Float, nullable=True)
    
    # Status
    is_enabled = Column(Boolean, nullable=False, default=True)
    is_paper_only = Column(Boolean, nullable=False, default=True)  # Only for paper trading


