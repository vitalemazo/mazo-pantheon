# System Architecture

**One Team. One Dream. One AI-Powered Hedge Fund.**

---

## Overview

Mazo Pantheon is an autonomous AI trading system designed to make intelligent investment decisions by combining multiple AI agents, deep research, and automated execution.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          THE AI TRADING PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    MARKET DATA        AI ANALYSIS           DECISION          EXECUTION    │
│    ───────────        ───────────           ────────          ─────────    │
│                                                                             │
│    ┌─────────┐      ┌─────────────┐      ┌──────────┐      ┌──────────┐   │
│    │ Financial│      │  18 Trading │      │ Portfolio│      │  Alpaca  │   │
│    │ Datasets │ ───▶ │    Agents   │ ───▶ │  Manager │ ───▶ │ Execution│   │
│    │   API    │      │             │      │          │      │          │   │
│    └─────────┘      └──────┬──────┘      └────┬─────┘      └──────────┘   │
│                            │                  │                            │
│                     ┌──────▼──────┐           │                            │
│                     │    Mazo     │───────────┘                            │
│                     │  Research   │                                        │
│                     │   Agent     │                                        │
│                     └─────────────┘                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Philosophy

### One Team
All 18 AI agents work together, each bringing a unique investment philosophy:
- Value investors (Graham, Buffett, Munger)
- Growth investors (Wood, Lynch, Fisher)
- Macro strategists (Druckenmiller, Damodaran)
- Technical analysts (Valuation, Sentiment, Fundamentals)

### One Dream
A single objective: **Generate alpha through intelligent, risk-managed trading decisions**.

### One Hedge Fund
Unified execution through the Portfolio Manager who:
- Aggregates all agent signals
- Weighs confidence levels
- Manages portfolio risk
- Executes final decisions

---

## Container Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOCKER NETWORK                                 │
│                            (mazo-network)                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐    ┌─────────────────────────────────────────────┐│
│  │   mazo-frontend     │    │              mazo-backend                   ││
│  │   (Nginx + React)   │    │              (FastAPI)                      ││
│  │                     │    │                                             ││
│  │   Port: 5173        │───▶│   Port: 8000                                ││
│  │                     │    │                                             ││
│  │   • Static UI       │    │   • REST API                                ││
│  │   • API proxy       │    │   • WebSocket (SSE)                         ││
│  │                     │    │   • 18 AI Agents                            ││
│  └─────────────────────┘    │   • Mazo Bridge (Bun)                       ││
│                              │   • Strategy Engine                         ││
│                              │   • Scheduler (APScheduler)                 ││
│                              │   • Alpaca Integration                      ││
│                              └───────────────┬───────────────────────────────┘│
│                                              │                               │
│  ┌─────────────────────┐    ┌───────────────▼───────────────────────────────┐│
│  │   mazo-redis        │    │              mazo-postgres                    ││
│  │   (Cache)           │◀───│              (Database)                       ││
│  │                     │    │                                               ││
│  │   Port: 6379        │    │   Port: 5432                                  ││
│  │                     │    │                                               ││
│  │   • API responses   │    │   • API keys                                  ││
│  │   • Market data     │    │   • Trade history                             ││
│  │   • Session state   │    │   • Workflow results                          ││
│  │                     │    │   • Agent performance                         ││
│  └─────────────────────┘    └───────────────────────────────────────────────┘│
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## AI Agent System

### Agent Categories

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           18 TRADING AGENTS                                 │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│   VALUE (5)      │   GROWTH (3)     │   MACRO (2)      │   TECHNICAL (5)   │
├──────────────────┼──────────────────┼──────────────────┼────────────────────┤
│ • Ben Graham     │ • Cathie Wood    │ • Druckenmiller  │ • Valuation       │
│ • Warren Buffett │ • Peter Lynch    │ • Damodaran      │ • Sentiment       │
│ • Charlie Munger │ • Phil Fisher    │                  │ • Fundamentals    │
│ • Mohnish Pabrai │                  │                  │ • Technicals      │
│ • Michael Burry  │                  │                  │ • Risk Manager    │
├──────────────────┴──────────────────┴──────────────────┴────────────────────┤
│                                                                              │
│   ACTIVIST (2)              RESEARCH (1)            DECISION (1)            │
├──────────────────┬──────────────────────────┬───────────────────────────────┤
│ • Bill Ackman    │ • Mazo Research Agent    │ • Portfolio Manager           │
│ • Rakesh J.      │   (Deep web research)    │   (Final trading decision)    │
└──────────────────┴──────────────────────────┴───────────────────────────────┘
```

### Agent Workflow

```
                         ┌─────────────┐
                         │   Ticker    │
                         │   Input     │
                         └──────┬──────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         DATA AGGREGATION                                  │
│  Fetch: prices, metrics, news, insider trades, financials                 │
└───────────────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
         ┌───────────┐   ┌───────────┐   ┌───────────┐
         │  Agent 1  │   │  Agent 2  │   │  Agent N  │
         │  (Graham) │   │ (Buffett) │   │  (...)    │
         └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
               │               │               │
               │   Signal:     │   Signal:     │   Signal:
               │   BUY 75%     │   HOLD 60%    │   BUY 80%
               │               │               │
               └───────────────┼───────────────┘
                               ▼
                    ┌─────────────────────┐
                    │  MAZO RESEARCH      │
                    │  (Deep Analysis)    │
                    │                     │
                    │  • Web search       │
                    │  • Sentiment        │
                    │  • Risk factors     │
                    │  • Investment thesis│
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  PORTFOLIO MANAGER  │
                    │                     │
                    │  Weighs all signals │
                    │  + research findings│
                    │  + risk limits      │
                    │  + portfolio state  │
                    │                     │
                    │  Decision: BUY      │
                    │  Quantity: 10 shares│
                    │  Confidence: 78%    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  ALPACA EXECUTION   │
                    │                     │
                    │  • Place order      │
                    │  • Monitor fill     │
                    │  • Update portfolio │
                    └─────────────────────┘
```

---

## Mazo Research Agent

The deep research component powered by TypeScript/Bun:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MAZO RESEARCH AGENT                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Input: Ticker + Context (signals, strategy)                                │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         RESEARCH PIPELINE                             │  │
│  │                                                                       │  │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │  │
│  │   │  Web Search │    │  Financial  │    │  Sentiment  │              │  │
│  │   │  (Tavily)   │    │  Analysis   │    │  Analysis   │              │  │
│  │   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘              │  │
│  │          │                  │                  │                      │  │
│  │          └──────────────────┼──────────────────┘                      │  │
│  │                             ▼                                         │  │
│  │                   ┌─────────────────────┐                             │  │
│  │                   │  LLM Synthesis      │                             │  │
│  │                   │  (Claude/GPT)       │                             │  │
│  │                   └──────────┬──────────┘                             │  │
│  │                              │                                        │  │
│  │                              ▼                                        │  │
│  │                   ┌─────────────────────┐                             │  │
│  │                   │  Research Report    │                             │  │
│  │                   │  • Executive Summary│                             │  │
│  │                   │  • Bull/Bear Cases  │                             │  │
│  │                   │  • Risk Factors     │                             │  │
│  │                   │  • Price Targets    │                             │  │
│  │                   │  • Recommendation   │                             │  │
│  │                   └─────────────────────┘                             │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  Research Depths:                                                           │
│  • Quick (30-60s): Basic analysis                                           │
│  • Standard (2-5min): Comprehensive research                                │
│  • Deep (5-15min): Exhaustive due diligence                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Trading Strategies

The Strategy Engine scans for opportunities using:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          STRATEGY ENGINE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │     MOMENTUM        │  │   MEAN REVERSION    │  │   TREND FOLLOWING   │ │
│  │                     │  │                     │  │                     │ │
│  │ • RSI extremes      │  │ • Oversold bounces  │  │ • Moving average    │ │
│  │ • Price breakouts   │  │ • Mean reversion    │  │   crossovers        │ │
│  │ • Volume surges     │  │ • Bollinger bands   │  │ • Trend strength    │ │
│  │                     │  │                     │  │ • Support/resistance│ │
│  └──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘ │
│             │                        │                        │             │
│             └────────────────────────┼────────────────────────┘             │
│                                      │                                      │
│                                      ▼                                      │
│                         ┌─────────────────────────┐                         │
│                         │     SIGNAL FILTER       │                         │
│                         │                         │                         │
│                         │  • Min confidence: 60%  │                         │
│                         │  • Volume threshold     │                         │
│                         │  • Sector diversity     │                         │
│                         │  • Position limits      │                         │
│                         └─────────────────────────┘                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Autonomous Scheduler

Runs trading cycles automatically during market hours:

```
Market Hours (ET)          Task
─────────────────────────────────────────────────
09:35                      Morning market scan
11:00                      Mid-morning health check
14:00                      Afternoon analysis
15:30                      Pre-close watchlist
16:05                      Daily performance report
─────────────────────────────────────────────────
Every 5 min                Position monitor
                           (stop-loss / take-profit)
─────────────────────────────────────────────────
Every 30 min               Full AI trading cycle
                           (scan → research → decide → execute)
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EXTERNAL APIs                    INTERNAL                    OUTPUT        │
│  ─────────────                    ────────                    ──────        │
│                                                                             │
│  ┌─────────────┐                                                            │
│  │ Financial   │──────┐                                                     │
│  │ Datasets    │      │                                                     │
│  └─────────────┘      │                                                     │
│                       │          ┌─────────────┐                            │
│  ┌─────────────┐      │          │             │         ┌─────────────┐   │
│  │   Alpaca    │──────┼─────────▶│   Backend   │────────▶│  Frontend   │   │
│  │   (Broker)  │      │          │   (FastAPI) │         │   (React)   │   │
│  └─────────────┘      │          │             │         └─────────────┘   │
│                       │          └──────┬──────┘                            │
│  ┌─────────────┐      │                 │                                   │
│  │   LLM APIs  │──────┤                 │                                   │
│  │ (OpenAI,    │      │          ┌──────▼──────┐         ┌─────────────┐   │
│  │  Anthropic) │      │          │  PostgreSQL │         │   Alpaca    │   │
│  └─────────────┘      │          │  (Storage)  │         │   (Trades)  │   │
│                       │          └─────────────┘         └─────────────┘   │
│  ┌─────────────┐      │                                                     │
│  │   Tavily    │──────┘                                                     │
│  │ (Web Search)│                                                            │
│  └─────────────┘                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | React, TypeScript, Tailwind, shadcn/ui | User interface |
| **Backend** | FastAPI, Python 3.11 | API server |
| **AI Agents** | LangGraph, LangChain | Agent orchestration |
| **Research** | Bun, TypeScript | Mazo research agent |
| **Database** | PostgreSQL | Persistent storage |
| **Cache** | Redis | Performance caching |
| **Scheduler** | APScheduler | Autonomous trading |
| **Trading** | Alpaca API | Order execution |
| **Container** | Docker, Docker Compose | Deployment |

---

## Security Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SECURITY LAYERS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. API Keys stored in:                                                     │
│     • .env file (source of truth)                                           │
│     • PostgreSQL (synced from .env)                                         │
│     • Never in code or git                                                  │
│                                                                             │
│  2. Trading Safety:                                                         │
│     • Paper trading by default                                              │
│     • Position size limits                                                  │
│     • Stop-loss enforcement                                                 │
│     • Daily loss limits                                                     │
│                                                                             │
│  3. Network:                                                                │
│     • CORS configured                                                       │
│     • Internal Docker network                                               │
│     • No external ports except 5173/8000                                    │
│                                                                             │
│  4. Database:                                                               │
│     • Password protected                                                    │
│     • Internal network only                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Scaling Considerations

### Horizontal Scaling

- Backend is stateless (scale replicas)
- Redis for shared cache
- PostgreSQL for shared state

### Performance Optimization

- Data aggregation before agents run
- Parallel agent execution
- Response caching (Redis)
- SSE for real-time updates

### High Availability

- Multiple backend replicas
- PostgreSQL replication
- Redis clustering
- Kubernetes deployment
