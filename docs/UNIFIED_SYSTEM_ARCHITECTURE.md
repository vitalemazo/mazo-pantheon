# Unified System Architecture

## The Vision: One Team, One Mission

All components work together as a unified hedge fund team:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        UNIFIED TRADING SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   TRIGGERS (Any of these can start the pipeline)                            │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│   │   Unified    │  │  Scheduler   │  │  Portfolio   │  │   Manual     │   │
│   │  Workflow UI │  │  (30 min)    │  │   Health     │  │   API Call   │   │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│          │                 │                 │                 │            │
│          └────────────────┬┴─────────────────┴─────────────────┘            │
│                           ▼                                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    UNIFIED PIPELINE                                  │   │
│   │                                                                      │   │
│   │   Step 1: MAZO RESEARCH                                             │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  • Deep company analysis                                     │   │   │
│   │   │  • News sentiment                                            │   │   │
│   │   │  • Competitive landscape                                     │   │   │
│   │   │  • Current portfolio context                                 │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                           ▼                                          │   │
│   │   Step 2: 18 AI AGENTS (in parallel)                                │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  Warren Buffett │ Ben Graham │ Cathie Wood │ Peter Lynch    │   │   │
│   │   │  Charlie Munger │ Bill Ackman │ Michael Burry │ Phil Fisher │   │   │
│   │   │  Stanley Druckenmiller │ Mohnish Pabrai │ Rakesh J. │ ...   │   │   │
│   │   │  Fundamentals │ Technicals │ Sentiment │ Growth │ Valuation │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                           ▼                                          │   │
│   │   Step 3: PORTFOLIO MANAGER                                         │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  • Weighs all 18 agent signals                              │   │   │
│   │   │  • Considers Mazo's research                                │   │   │
│   │   │  • Checks current portfolio (positions, P&L, concentration) │   │   │
│   │   │  • Checks pending orders                                    │   │   │
│   │   │  • Applies risk management (stop-loss, take-profit)         │   │   │
│   │   │  • Makes final decision: BUY/SELL/SHORT/COVER/HOLD/CANCEL   │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   │                           ▼                                          │   │
│   │   Step 4: ALPACA EXECUTION                                          │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  • Submit order to Alpaca                                   │   │   │
│   │   │  • Handle wash trade prevention                             │   │   │
│   │   │  • Set stop-loss/take-profit                                │   │   │
│   │   │  • Record in trade history                                  │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                           ▼                                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                 UNIFIED DATA STORE                                   │   │
│   │   (Zustand store - all tabs read from here)                         │   │
│   │                                                                      │   │
│   │   • Portfolio positions (real-time from Alpaca)                     │   │
│   │   • Trade history (every executed trade with full context)          │   │
│   │   • Agent performance (accuracy tracking)                           │   │
│   │   • Scheduler status                                                │   │
│   │   • Latest workflow result                                          │   │
│   │   • Portfolio health analysis                                       │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                           ▼                                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    UI TABS (All read from same store)                │   │
│   │                                                                      │   │
│   │   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │   │
│   │   │  Unified    │ │  Portfolio  │ │   Trading   │ │   Command   │   │   │
│   │   │  Workflow   │ │   Health    │ │  Dashboard  │ │   Center    │   │   │
│   │   ├─────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────┤   │   │
│   │   │ • Trigger   │ │ • Health    │ │ • Scheduler │ │ • Overview  │   │   │
│   │   │   analysis  │ │   grade     │ │   controls  │ │ • History   │   │   │
│   │   │ • See live  │ │ • Mazo      │ │ • Watchlist │ │ • Agent     │   │   │
│   │   │   progress  │ │   insights  │ │ • Positions │ │   rankings  │   │   │
│   │   │ • Review    │ │ • Risks     │ │ • AI cycle  │ │ • Trades    │   │   │
│   │   │   results   │ │             │ │   status    │ │             │   │   │
│   │   └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Integration Points

### 1. When Unified Workflow Runs:
- Results flow to Command Center's Trade History
- Agent signals flow to Agent Leaderboard
- New positions appear in Trading Dashboard
- Portfolio Health recommendations update

### 2. When Scheduler Runs AI Cycle:
- Same pipeline as Unified Workflow
- Results visible in all tabs
- Trade history updated
- Positions updated

### 3. When Portfolio Health Runs:
- Uses current portfolio context
- Can trigger rebalancing recommendations
- PM can act on health check insights

### 4. Real-Time Data Flow:
- Alpaca positions → All tabs (via hydration service)
- Trade executions → Trade History
- Agent predictions → Agent Performance tracker
- Scheduler status → Trading Dashboard

## Key Principle: Single Source of Truth

Every component reads from the same data store:

```typescript
// All tabs use this:
const { 
  performance,    // From Alpaca
  trades,         // From trade_history DB
  agents,         // From agent_performance DB  
  scheduler,      // From scheduler service
  portfolioHealth // From Mazo analysis
} = useHydratedData();
```

This ensures:
- Tab switches are instant (cached data)
- All tabs show consistent data
- Updates propagate everywhere
- No duplicate API calls
