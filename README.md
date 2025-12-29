# Mazo Hedge Fund

An AI-powered trading system that combines multi-agent signal generation with autonomous financial research and **live trading on Alpaca Markets**.

## 🎯 What This System Does

This system analyzes stocks using AI agents inspired by legendary investors, generates trading signals, performs deep financial research, and can execute trades automatically on Alpaca Markets (paper or live trading).

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MAZO HEDGE FUND SYSTEM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐                                                           │
│  │   USER      │  "Analyze AAPL and execute trades"                        │
│  │  Request    │                                                           │
│  └──────┬──────┘                                                           │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │         UNIFIED WORKFLOW ORCHESTRATOR                              │   │
│  │         (integration/unified_workflow.py)                           │   │
│  │                                                                     │   │
│  │  • Routes requests to AI Hedge Fund and/or Mazo                    │   │
│  │  • Manages data flow between systems                               │   │
│  │  • Aggregates results                                              │   │
│  │  • Executes trades on Alpaca                                       │   │
│  └──────┬─────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ├──────────────────────────┬──────────────────────────┐           │
│         │                          │                          │           │
│         ▼                          ▼                          ▼           │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐       │
│  │ AI HEDGE FUND│         │     MAZO     │         │   ALPACA     │       │
│  │              │         │              │         │   TRADING    │       │
│  │ 18 Agents    │         │  Research    │         │   Execution  │       │
│  │ Generate     │         │  Agent       │         │              │       │
│  │ Signals      │         │  Deep Dive   │         │  Paper/Live  │       │
│  └──────────────┘         └──────────────┘         └──────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📊 Complete Workflow Diagram

```
USER COMMAND
    │
    │ poetry run python -m integration.unified_workflow --tickers AAPL --mode full --execute
    │
    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 1: DATA AGGREGATION (Optional - if AGGREGATE_DATA=true)            │
│                                                                          │
│  • Fetch financial metrics (revenue, earnings, ratios)                  │
│  • Fetch price history                                                  │
│  • Fetch company news                                                    │
│  • Fetch insider trades                                                 │
│  • Store in shared state for all agents                                 │
└──────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 2: WORKFLOW MODE EXECUTION                                         │
│                                                                          │
│  Mode: signal-only    → Skip to Step 3                                  │
│  Mode: research-only  → Skip to Step 4                                  │
│  Mode: pre-research   → Step 4 → Step 3                                │
│  Mode: post-research  → Step 3 → Step 4                                │
│  Mode: full           → Step 4 → Step 3 → Step 4 (deep dive)          │
└──────────────────────────────────────────────────────────────────────────┘
    │
    ├──────────────────────────────────┬──────────────────────────────────┐
    │                                  │                                  │
    ▼                                  ▼                                  ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│ STEP 3: AI HEDGE FUND  │  │ STEP 4: MAZO RESEARCH  │  │ STEP 5: TRADE EXECUTION│
│                         │  │                         │  │                         │
│ 18 Agents Analyze:      │  │ Autonomous Research:    │  │ Alpaca API:            │
│                         │  │                         │  │                         │
│ ┌─────────────────────┐ │  │ • Company Analysis      │  │ • Connect to Alpaca     │
│ │ 1. Warren Buffett   │ │  │ • Financial Deep Dive    │  │ • Submit Order          │
│ │ 2. Ben Graham       │ │  │ • Signal Explanation    │  │ • Get Execution Status  │
│ │ 3. Bill Ackman      │ │  │ • Risk Assessment       │  │ • Update Positions      │
│ │ 4. Cathie Wood      │ │  │                         │  │                         │
│ │ 5. Charlie Munger   │ │  │ Uses:                   │  │ Mode: Paper (default)   │
│ │ 6. Michael Burry    │ │  │ • Financial Datasets API│  │ or Live (if configured) │
│ │ 7. Mohnish Pabrai   │ │  │ • Web Search (Tavily)   │  │                         │
│ │ 8. Peter Lynch     │ │  │ • LLM Reasoning          │  │                         │
│ │ 9. Phil Fisher      │ │  │                         │  │                         │
│ │ 10. Rakesh Jhunj... │ │  │                         │  │                         │
│ │ 11. Stanley Druck...│ │  │                         │  │                         │
│ │ 12. Aswath Damodaran│ │  │                         │  │                         │
│ │ 13. Technical       │ │  │                         │  │                         │
│ │ 14. Fundamentals    │ │  │                         │  │                         │
│ │ 15. Growth          │ │  │                         │  │                         │
│ │ 16. Valuation       │ │  │                         │  │                         │
│ │ 17. Sentiment       │ │  │                         │  │                         │
│ │ 18. News Sentiment  │ │  │                         │  │                         │
│ └─────────────────────┘ │  │                         │  │                         │
│                         │  │                         │  │                         │
│ Each Agent:             │  │                         │  │                         │
│ • Fetches data (or uses │  │                         │  │                         │
│   aggregated data)      │  │                         │  │                         │
│ • Analyzes with LLM     │  │                         │  │                         │
│ • Returns:              │  │                         │  │                         │
│   - Signal (BULLISH/    │  │                         │  │                         │
│     BEARISH/NEUTRAL)    │  │                         │  │                         │
│   - Confidence (0-100%) │  │                         │  │                         │
│   - Reasoning           │  │                         │  │                         │
│                         │  │                         │  │                         │
│ ┌─────────────────────┐ │  │                         │  │                         │
│ │ RISK MANAGER        │ │  │                         │  │                         │
│ │ • Calculates position│ │  │                         │  │                         │
│ │   limits            │ │  │                         │  │                         │
│ │ • Volatility adjust │ │  │                         │  │                         │
│ │ • Correlation check │ │  │                         │  │                         │
│ └─────────────────────┘ │  │                         │  │                         │
│         │               │  │                         │  │                         │
│         ▼               │  │                         │  │                         │
│ ┌─────────────────────┐ │  │                         │  │                         │
│ │ PORTFOLIO MANAGER   │ │  │                         │  │                         │
│ │ • Aggregates signals│ │  │                         │  │                         │
│ │ • Makes decision:   │ │  │                         │  │                         │
│ │   BUY/SELL/SHORT/   │ │  │                         │  │                         │
│ │   COVER/HOLD        │ │  │                         │  │                         │
│ │ • Calculates qty    │ │  │                         │  │                         │
│ └─────────────────────┘ │  │                         │  │                         │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
    │                                  │                                  │
    └──────────────────────────────────┴──────────────────────────────────┘
                                        │
                                        ▼
                            ┌───────────────────────────┐
                            │   FINAL RESULT            │
                            │                           │
                            │ • Trading Signal          │
                            │ • Agent Signals           │
                            │ • Research Report         │
                            │ • Trade Execution Status  │
                            │ • Recommendations         │
                            └───────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** (required)
- **Bun** (for Mazo - install from https://bun.sh)
  ```bash
  # Install Bun on macOS
  curl -fsSL https://bun.sh/install | bash
  ```
- **API Keys** (see Configuration section)

### 1. Installation

#### Option A: Using Poetry (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd mazo-hedge-fund

# Install Poetry if you don't have it
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install
```

#### Option B: Using pip (Simpler for Mac users)

```bash
# Clone the repository
git clone <repository-url>
cd mazo-hedge-fund

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

**Note:** Python 3.11 or higher is required.

#### Mac-Specific Notes

On macOS, you may need to install Python 3.11+ if you don't have it:

```bash
# Using Homebrew (recommended)
brew install python@3.11

# Or download from python.org
# https://www.python.org/downloads/
```

If you have multiple Python versions, use:
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required: LLM API (use proxy or direct)
OPENAI_API_KEY=your-key
OPENAI_API_BASE=https://your-proxy-url  # If using proxy

# Required: Financial Data
FINANCIAL_DATASETS_API_KEY=your-key

# Required: Alpaca Trading
ALPACA_API_KEY=your-key
ALPACA_SECRET_KEY=your-secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets/v2  # Paper trading
ALPACA_TRADING_MODE=paper  # or "live" for real trading

# Optional: Rate Limiting (recommended)
AGGREGATE_DATA=true              # Pre-fetch data once
LLM_MAX_CONCURRENT=3            # Max concurrent LLM calls
LLM_REQUESTS_PER_MINUTE=50       # Rate limit per minute

# Optional: Mazo Configuration
MAZO_PATH=./mazo
BUN_PATH=~/.bun/bin/bun
MAZO_TIMEOUT=300
```

### 3. Run Your First Analysis

**If using Poetry:**
```bash
# Signal-only mode (just AI Hedge Fund)
poetry run python -m integration.unified_workflow \
  --tickers AAPL \
  --mode signal

# Full workflow (AI Hedge Fund + Mazo research)
poetry run python -m integration.unified_workflow \
  --tickers AAPL \
  --mode full \
  --depth standard

# Execute paper trades
poetry run python -m integration.unified_workflow \
  --tickers AAPL \
  --mode signal \
  --execute
```

**If using pip (with virtual environment activated):**
```bash
# Signal-only mode (just AI Hedge Fund)
python -m integration.unified_workflow \
  --tickers AAPL \
  --mode signal

# Full workflow (AI Hedge Fund + Mazo research)
python -m integration.unified_workflow \
  --tickers AAPL \
  --mode full \
  --depth standard

# Execute paper trades
python -m integration.unified_workflow \
  --tickers AAPL \
  --mode signal \
  --execute
```

## 📖 How It Works

### Component Overview

| Component | Purpose | When Used | Why |
|-----------|---------|-----------|-----|
| **Unified Workflow** | Orchestrates entire system | Every request | Routes to AI Hedge Fund and/or Mazo, manages data flow |
| **AI Hedge Fund** | Generates trading signals | Signal generation needed | 18 agents provide diverse perspectives on stock |
| **Mazo** | Deep financial research | Research/explanation needed | Provides comprehensive analysis and explanations |
| **Alpaca Service** | Executes trades | When `--execute` flag used | Connects to Alpaca API for paper/live trading |

### AI Hedge Fund Agents

The system uses 18 specialized agents, each with a unique investment philosophy:

#### Legendary Investor Agents (12)
1. **Warren Buffett** - Value investing, wonderful companies at fair prices
2. **Ben Graham** - Deep value, margin of safety, defensive investing
3. **Bill Ackman** - Activist investing, contrarian positions
4. **Cathie Wood** - Growth investing, disruptive innovation
5. **Charlie Munger** - Quality businesses, rational decision-making
6. **Michael Burry** - Contrarian, deep value, short overvalued markets
7. **Mohnish Pabrai** - Value investing, margin of safety, doubles at low risk
8. **Peter Lynch** - Growth at reasonable price, "buy what you know"
9. **Phil Fisher** - Growth investing, scuttlebutt research
10. **Rakesh Jhunjhunwala** - Macro insights, emerging markets
11. **Stanley Druckenmiller** - Macro trends, asymmetric opportunities
12. **Aswath Damodaran** - Valuation expert, story + numbers

#### Analysis Agents (4)
13. **Technical Analyst** - Chart patterns, momentum, mean reversion
14. **Fundamentals Analyst** - Financial statements, ratios, health
15. **Growth Analyst** - Revenue growth, margin expansion, PEG ratios
16. **Valuation Analyst** - DCF, owner earnings, EV/EBITDA, intrinsic value

#### Sentiment Agents (2)
17. **Sentiment Analyst** - Insider trading, news sentiment, market psychology
18. **News Sentiment Analyst** - News article analysis, market sentiment

#### Management Agents (2)
19. **Risk Manager** - Position limits, volatility adjustment, correlation
20. **Portfolio Manager** - Aggregates all signals, makes final decision

### Workflow Modes

| Mode | Flow | Use Case |
|------|------|----------|
| **signal** | AI Hedge Fund only | Quick trading signals |
| **research** | Mazo only | Deep research without signals |
| **pre-research** | Mazo → AI Hedge Fund | Research informs signal generation |
| **post-research** | AI Hedge Fund → Mazo | Signal explained by research |
| **full** | Mazo → AI Hedge Fund → Mazo | Complete analysis with explanation |

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA AGGREGATION                         │
│  (Happens once if AGGREGATE_DATA=true)                      │
│                                                             │
│  Financial Datasets API                                     │
│  ├── Financial Metrics (revenue, earnings, ratios)          │
│  ├── Line Items (balance sheet, cash flow)                 │
│  ├── Market Cap                                            │
│  ├── Price History                                         │
│  ├── Company News                                          │
│  └── Insider Trades                                        │
│                                                             │
│  ↓ Stored in shared state                                  │
│                                                             │
│  All agents access this data (no duplicate API calls)      │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              AGENT EXECUTION (Rate Limited)                 │
│                                                             │
│  Agents run in batches (3 concurrent max)                  │
│  Each agent:                                                │
│  1. Uses aggregated data (or fetches if needed)             │
│  2. Makes LLM call (rate limited)                          │
│  3. Returns signal + confidence + reasoning                │
│                                                             │
│  Rate Limiter:                                              │
│  • Semaphore: 3 concurrent LLM calls                        │
│  • Token Bucket: 50 requests/minute                         │
│  • Prevents 429 errors                                     │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              SIGNAL AGGREGATION                             │
│                                                             │
│  Portfolio Manager:                                         │
│  • Collects all agent signals                               │
│  • Weights by confidence                                    │
│  • Determines overall signal (BULLISH/BEARISH/NEUTRAL)     │
│  • Calculates action (BUY/SELL/SHORT/COVER/HOLD)           │
│  • Calculates quantity based on risk limits                 │
└─────────────────────────────────────────────────────────────┘
```

## 💻 Usage Examples

### Example 1: Quick Signal Generation

```bash
poetry run python -m integration.unified_workflow \
  --tickers AAPL MSFT GOOGL \
  --mode signal
```

**What happens:**
1. Data aggregated for all 3 tickers
2. 18 agents analyze each ticker
3. Signals aggregated
4. Recommendations provided

**Output:**
- Signal: BULLISH/BEARISH/NEUTRAL
- Confidence: 0-100%
- Agent signals with reasoning
- Recommended action

### Example 2: Full Analysis with Research

```bash
poetry run python -m integration.unified_workflow \
  --tickers AAPL \
  --mode full \
  --depth standard
```

**What happens:**
1. Mazo performs initial research
2. AI Hedge Fund generates signals with research context
3. Mazo explains the signal in detail
4. Comprehensive report generated

**Output:**
- Initial research report
- Trading signal with confidence
- Agent signals
- Signal explanation
- Recommendations

### Example 3: Paper Trading Execution

```bash
poetry run python -m integration.unified_workflow \
  --tickers AAPL \
  --mode signal \
  --execute
```

**What happens:**
1. AI Hedge Fund generates signal
2. Portfolio Manager decides: BUY 100 shares
3. Alpaca Service connects to paper trading account
4. Order submitted
5. Execution status reported

**Output:**
- Trading signal
- Order ID
- Filled price
- Updated positions

### Example 4: Dry Run (Preview Trades)

```bash
poetry run python -m integration.unified_workflow \
  --tickers AAPL MSFT \
  --mode signal \
  --dry-run
```

**What happens:**
- Same as execution, but no actual trades
- Shows what would be traded

## 📁 Project Structure

```
mazo-hedge-fund/
├── integration/              # Unified workflow orchestrator
│   ├── unified_workflow.py   # Main entry point, orchestrates everything
│   ├── mazo_bridge.py        # Bridge to Mazo research agent
│   └── config.py             # Configuration management
│
├── src/                      # AI Hedge Fund core
│   ├── main.py               # Hedge fund entry point
│   ├── agents/               # 18 trading agents
│   │   ├── warren_buffett.py
│   │   ├── michael_burry.py
│   │   ├── portfolio_manager.py
│   │   └── ... (18 total)
│   ├── trading/              # Alpaca trading integration
│   │   └── alpaca_service.py # Alpaca API client
│   ├── tools/                # Data fetching
│   │   └── api.py            # Financial Datasets API
│   ├── utils/                # Utilities
│   │   ├── llm.py            # LLM calls with rate limiting
│   │   ├── rate_limiter.py   # Rate limiting implementation
│   │   ├── data_aggregator.py # Data pre-fetching
│   │   └── analysts.py       # Agent configuration
│   ├── graph/                # Workflow graph
│   │   └── state.py          # Agent state management
│   └── llm/                  # LLM model configuration
│       └── models.py         # Supported models
│
├── mazo/                     # Mazo research agent
│   └── src/                  # Mazo TypeScript codebase
│
├── .env.example              # Environment variables template
├── pyproject.toml            # Python dependencies
└── README.md                 # This file
```

## 🔧 Key Components Explained

### 1. Unified Workflow (`integration/unified_workflow.py`)

**What:** Main orchestrator that routes requests and manages data flow

**When:** Every time you run the system

**Why:** Provides a single entry point for all workflows

**How:**
- Accepts command-line arguments
- Routes to AI Hedge Fund and/or Mazo based on mode
- Aggregates results
- Executes trades if requested

### 2. AI Hedge Fund Agents (`src/agents/`)

**What:** 18 specialized agents that analyze stocks

**When:** Signal generation mode (signal, pre-research, post-research, full)

**Why:** Each agent provides a unique perspective based on different investment philosophies

**How:**
- Each agent fetches relevant data (or uses aggregated data)
- Makes LLM call with agent-specific prompt
- Returns signal (BULLISH/BEARISH/NEUTRAL), confidence, and reasoning

### 3. Mazo Research Agent (`mazo/`)

**What:** Autonomous financial research agent

**When:** Research modes (research, pre-research, post-research, full)

**Why:** Provides deep, comprehensive financial analysis and explanations

**How:**
- Uses autonomous agent architecture
- Decomposes research questions into tasks
- Fetches data from multiple sources
- Generates comprehensive research reports

### 4. Alpaca Trading Service (`src/trading/alpaca_service.py`)

**What:** Connects to Alpaca Markets API for trade execution

**When:** When `--execute` flag is used

**Why:** Executes trades based on AI-generated signals

**How:**
- Connects to Alpaca API (paper or live)
- Submits market orders
- Tracks positions
- Reports execution status

### 5. Rate Limiter (`src/utils/rate_limiter.py`)

**What:** Prevents API rate limit errors

**When:** Always active (if configured)

**Why:** Prevents 429 errors from too many concurrent requests

**How:**
- Semaphore limits concurrent LLM calls (default: 3)
- Token bucket limits requests per minute (default: 50)
- Exponential backoff on errors

### 6. Data Aggregator (`src/utils/data_aggregator.py`)

**What:** Pre-fetches all financial data before agents run

**When:** If `AGGREGATE_DATA=true`

**Why:** Eliminates duplicate API calls (18 agents × 5 calls = 90 → 5 calls)

**How:**
- Fetches all data once at start
- Stores in shared state
- Agents access cached data

## 🎛️ Configuration Options

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGGREGATE_DATA` | `false` | Pre-fetch data once (recommended: `true`) |
| `LLM_MAX_CONCURRENT` | `3` | Max concurrent LLM calls |
| `LLM_REQUESTS_PER_MINUTE` | `60` | Rate limit per minute |
| `ALPACA_TRADING_MODE` | `paper` | Paper or live trading |
| `DEFAULT_WORKFLOW_MODE` | `full` | Default workflow mode |
| `DEFAULT_RESEARCH_DEPTH` | `standard` | Default research depth |

### Command-Line Arguments

```bash
--tickers AAPL MSFT        # Stock symbols to analyze
--mode signal              # Workflow mode
--depth quick              # Research depth (quick/standard/deep)
--model gpt-4              # LLM model to use
--output console           # Output format (console/json/markdown)
--output-file result.md    # Save output to file
--execute                  # Execute trades on Alpaca
--dry-run                  # Preview trades without executing
```

## 🔐 API Keys Required

1. **LLM API** - OpenAI/Anthropic or proxy
2. **Financial Datasets API** - Market data
3. **Alpaca API** - Trading execution
4. **Tavily API** (optional) - Web search for Mazo

## 📊 Output Formats

### Console (Default)
Human-readable output with signals, confidence, and recommendations

### JSON
Structured JSON for programmatic use:
```json
{
  "ticker": "AAPL",
  "signal": "BEARISH",
  "confidence": 75.0,
  "agent_signals": [...],
  "recommendations": [...],
  "trade": {...}
}
```

### Markdown
Formatted markdown report suitable for documentation

## 🚨 Important Notes

1. **Paper Trading First**: Always test with paper trading before live trading
2. **Rate Limiting**: Enable `AGGREGATE_DATA=true` and rate limiting to prevent API errors
3. **API Costs**: LLM calls can be expensive - monitor usage
4. **Not Financial Advice**: This is a tool, not financial advice. Use at your own risk.

## 🐛 Troubleshooting

### Rate Limit Errors (429)

**Solution:** Enable rate limiting:
```bash
export AGGREGATE_DATA=true
export LLM_MAX_CONCURRENT=3
export LLM_REQUESTS_PER_MINUTE=50
```

### Mazo Not Found

**Solution:** Ensure Bun is installed and MAZO_PATH is correct:
```bash
which bun
export MAZO_PATH=./mazo
```

### Alpaca Connection Errors

**Solution:** Check API keys and base URL:
```bash
export ALPACA_API_KEY=your-key
export ALPACA_SECRET_KEY=your-secret
export ALPACA_BASE_URL=https://paper-api.alpaca.markets/v2
```

## 📚 Additional Resources

- **Alpaca Markets**: https://alpaca.markets/
- **Financial Datasets**: https://financialdatasets.ai/
- **LangGraph**: https://langchain-ai.github.io/langgraph/

## 📝 License

MIT License - See LICENSE file for details

## ⚠️ Disclaimer

This software is for educational purposes only. Trading involves risk. Past performance does not guarantee future results. Use at your own risk.
