# Day Trading Strategy Architecture

## Overview

This document outlines the architecture for automated intraday portfolio management using Mazo, the AI agents, and the Portfolio Manager (PM). The goal is systematic profit generation through diversified, affordable stock positions with intelligent entry/exit timing.

## Core Components

### 1. Trading Scheduler (`src/trading/scheduler.py`)

The scheduler orchestrates trading activities throughout the day:

```
┌─────────────────────────────────────────────────────────────┐
│                    TRADING SCHEDULER                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  6:30 AM ET  - Pre-Market Prep                              │
│  ├── Fetch overnight news & global markets                  │
│  ├── Run Portfolio Health Check                             │
│  └── Identify gaps and opportunities                        │
│                                                              │
│  9:30 AM ET  - Market Open                                  │
│  ├── Execute pending rebalancing actions                    │
│  ├── Review overnight order fills                           │
│  └── Adjust stop-losses based on opening prices             │
│                                                              │
│  10:00 AM ET - Morning Momentum Scan                        │
│  ├── Scan for momentum plays (post-open volatility)         │
│  ├── Identify mean-reversion opportunities                  │
│  └── Execute quick trades if high-confidence signals        │
│                                                              │
│  12:00 PM ET - Midday Review                                │
│  ├── Check P&L across all positions                         │
│  ├── Review stop-loss triggers                              │
│  └── Consider profit-taking on big winners                  │
│                                                              │
│  2:00 PM ET  - Afternoon Setup                              │
│  ├── Scan for end-of-day setups                             │
│  ├── Run full agent analysis on watchlist                   │
│  └── Prepare swing trade entries                            │
│                                                              │
│  3:30 PM ET  - Pre-Close Actions                            │
│  ├── Close any day trades (if applicable)                   │
│  ├── Place after-hours orders for next day                  │
│  └── Final portfolio health check                           │
│                                                              │
│  4:00 PM ET  - Market Close                                 │
│  ├── Generate daily performance report                      │
│  ├── Update position tracking database                      │
│  └── Set alerts for after-hours movements                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2. Trading Strategies

#### Strategy 1: Momentum Scalping (Intraday)
- **Goal**: Capture quick 1-3% moves on high-volume stocks
- **Entry**: Strong pre-market movement + positive news sentiment
- **Exit**: Time-based (1-2 hours max) or 2% profit target
- **Risk**: 0.5% stop-loss, max 5% of portfolio per trade

#### Strategy 2: Mean Reversion (Intraday)
- **Goal**: Fade extreme moves that are likely to reverse
- **Entry**: 2+ standard deviation move from VWAP with no fundamental catalyst
- **Exit**: Return to VWAP or 1% profit
- **Risk**: 1% stop-loss, max 5% of portfolio per trade

#### Strategy 3: Trend Following (Swing)
- **Goal**: Ride multi-day trends in strong stocks
- **Entry**: Breakout from consolidation with volume confirmation
- **Exit**: Trailing stop at 8-10% from highs
- **Risk**: 5% initial stop-loss, max 10% of portfolio per trade

#### Strategy 4: Dividend Capture
- **Goal**: Capture dividends with minimal price risk
- **Entry**: Buy 1-2 days before ex-dividend
- **Exit**: Sell on/after ex-dividend if price holds
- **Risk**: Only on stable, large-cap stocks

#### Strategy 5: Earnings Plays (Event-Driven)
- **Goal**: Trade around earnings announcements
- **Entry**: Based on Mazo research and agent consensus
- **Exit**: Within 24 hours of announcement
- **Risk**: Position sizing reduced to 3% of portfolio

### 3. Diversification Scanner

Finds affordable stocks that meet quality criteria:

```python
# Criteria for diversification scanning
DIVERSIFICATION_CRITERIA = {
    "max_price": 50.0,           # Affordable entry points
    "min_volume": 500_000,       # Sufficient liquidity
    "min_market_cap": 500_000_000,  # $500M+ (avoid penny stocks)
    "sectors": [                 # Sector diversification
        "Technology", "Healthcare", "Financials",
        "Consumer Discretionary", "Industrials",
        "Energy", "Utilities", "Materials"
    ],
    "max_correlation": 0.6,      # Max correlation with existing positions
    "min_analyst_rating": 3.0,   # Buy/Hold consensus
}
```

### 4. Position Management Rules

```python
POSITION_RULES = {
    # Size limits
    "max_single_position": 0.10,      # 10% of portfolio max
    "max_sector_exposure": 0.30,      # 30% in any sector
    "max_correlated_group": 0.40,     # 40% in correlated assets
    
    # Risk limits
    "max_daily_loss": 0.02,           # 2% daily stop
    "max_weekly_loss": 0.05,          # 5% weekly stop
    "max_drawdown": 0.10,             # 10% drawdown circuit breaker
    
    # Profit targets
    "take_profit_1": 0.05,            # Scale out 50% at 5%
    "take_profit_2": 0.10,            # Scale out remaining at 10%
    "trailing_stop": 0.08,            # 8% trailing stop on winners
    
    # Day trading specific
    "max_day_trades": 3,              # PDT rule consideration
    "day_trade_position_size": 0.05,  # 5% max for day trades
}
```

### 5. Agent Team Coordination

```
┌──────────────────────────────────────────────────────────────┐
│                    AGENT TEAM WORKFLOW                        │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  MAZO RESEARCH                                                │
│  ├── Deep company analysis                                    │
│  ├── News & sentiment synthesis                               │
│  └── Provides: Research context for all agents                │
│           ↓                                                   │
│  SIGNAL AGENTS (18 analysts)                                  │
│  ├── Technical, Fundamental, Sentiment, Growth, Valuation     │
│  ├── Warren Buffett, Peter Lynch, etc.                        │
│  └── Provides: Directional signals with confidence            │
│           ↓                                                   │
│  RISK MANAGER                                                 │
│  ├── Volatility assessment                                    │
│  ├── Position size recommendation                             │
│  └── Provides: Max position size, risk score                  │
│           ↓                                                   │
│  PORTFOLIO MANAGER (PM)                                       │
│  ├── Aggregates all signals                                   │
│  ├── Considers current portfolio state                        │
│  ├── Checks correlation with existing positions               │
│  └── Makes: Final trade decision (buy/sell/hold/rebalance)    │
│           ↓                                                   │
│  TRADE EXECUTOR                                               │
│  ├── Executes via Alpaca                                      │
│  ├── Sets stop-loss and take-profit                           │
│  └── Records: Trade details for tracking                      │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

## Database Schema Extensions

```sql
-- Trade history and performance tracking
CREATE TABLE trade_history (
    id INTEGER PRIMARY KEY,
    order_id TEXT,
    ticker TEXT,
    action TEXT,          -- buy, sell, short, cover
    quantity REAL,
    entry_price REAL,
    exit_price REAL,
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    stop_loss_price REAL,
    take_profit_price REAL,
    strategy TEXT,        -- momentum, mean_reversion, trend, etc.
    realized_pnl REAL,
    return_pct REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily performance snapshots
CREATE TABLE daily_performance (
    id INTEGER PRIMARY KEY,
    date DATE,
    starting_equity REAL,
    ending_equity REAL,
    realized_pnl REAL,
    unrealized_pnl REAL,
    trades_count INTEGER,
    win_rate REAL,
    biggest_winner REAL,
    biggest_loser REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Watchlist for potential trades
CREATE TABLE watchlist (
    id INTEGER PRIMARY KEY,
    ticker TEXT,
    added_date TIMESTAMP,
    strategy TEXT,
    entry_target REAL,
    stop_loss REAL,
    take_profit REAL,
    notes TEXT,
    status TEXT,          -- watching, triggered, expired
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Scheduled tasks
CREATE TABLE scheduled_tasks (
    id INTEGER PRIMARY KEY,
    task_name TEXT,
    schedule_cron TEXT,   -- Cron expression
    task_type TEXT,       -- health_check, scan, trade, report
    parameters TEXT,      -- JSON config
    last_run TIMESTAMP,
    next_run TIMESTAMP,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoints

```python
# Scheduler endpoints
POST /api/scheduler/start          # Start automated trading
POST /api/scheduler/stop           # Stop automated trading
GET  /api/scheduler/status         # Get scheduler status
GET  /api/scheduler/tasks          # List scheduled tasks
POST /api/scheduler/task           # Add custom task

# Strategy endpoints
GET  /api/strategies               # List available strategies
POST /api/strategies/{id}/run      # Run strategy manually
GET  /api/strategies/{id}/backtest # Backtest strategy

# Diversification endpoints
POST /api/scan/diversification     # Scan for affordable stocks
GET  /api/portfolio/correlation    # Get correlation matrix
GET  /api/portfolio/sectors        # Get sector breakdown

# Performance endpoints
GET  /api/performance/daily        # Daily P&L report
GET  /api/performance/trades       # Trade history
GET  /api/performance/metrics      # Win rate, Sharpe, etc.
```

## UI Components

### 1. Trading Dashboard (new tab)
- Live P&L display
- Position cards with real-time prices
- Trade execution buttons
- Alert notifications

### 2. Strategy Manager
- Enable/disable strategies
- Set parameters per strategy
- View strategy performance

### 3. Diversification Scanner
- Search affordable stocks
- Filter by sector, price, volume
- Add to watchlist

### 4. Performance Reports
- Daily/weekly/monthly P&L charts
- Trade journal with notes
- Win rate and metrics

## Implementation Priority

1. **Phase 1**: Basic Scheduler
   - Implement trading scheduler with cron-like timing
   - Add health check automation
   - Create basic API endpoints

2. **Phase 2**: Diversification Scanner
   - Build stock screener with criteria
   - Sector analysis
   - Correlation checking

3. **Phase 3**: Strategy Engine
   - Implement momentum and mean-reversion strategies
   - Backtesting framework
   - Strategy selection UI

4. **Phase 4**: Performance Tracking
   - Trade history database
   - P&L calculations
   - Dashboard visualizations

5. **Phase 5**: Full Automation
   - End-to-end automated trading
   - Risk controls and circuit breakers
   - Alerting system
