# Autonomous Hedge Fund - Improvement Roadmap

## Current State
- ✅ 18 AI Analyst Agents
- ✅ Mazo Research Agent  
- ✅ Portfolio Manager with full autonomy
- ✅ Alpaca trade execution
- ✅ Scheduler running every 30 minutes
- ✅ Portfolio Health Check
- ✅ Trading Dashboard
- ✅ Unified Workflow (manual)

## Priority 1: Position Lifecycle Management 🔴

**Problem**: Trades are placed but never managed. Stop-loss/take-profit are calculated but not enforced.

**Solution**: Implement Position Monitor Service

```python
# Every 5 minutes during market hours:
1. Fetch all open positions from Alpaca
2. For each position:
   - Check if current price hit stop-loss → SELL/COVER immediately
   - Check if current price hit take-profit → SELL/COVER immediately
   - Check if position age > max_hold_time → Evaluate for exit
3. Log all actions to trade history
```

**Files to create/modify**:
- `src/trading/position_monitor.py` - Active position monitoring
- `src/trading/exit_executor.py` - Automated exit logic
- Add to scheduler: Run every 5 minutes

---

## Priority 2: Trade History & Journaling 🔴

**Problem**: No record of what trades were made and why.

**Solution**: Comprehensive trade logging

**Database additions**:
```sql
-- Already have Trade model, enhance it:
ALTER TABLE trades ADD COLUMN agent_signals JSON;  -- Which agents said what
ALTER TABLE trades ADD COLUMN mazo_analysis TEXT;  -- Mazo's research summary
ALTER TABLE trades ADD COLUMN pm_reasoning TEXT;   -- PM's decision reasoning
ALTER TABLE trades ADD COLUMN outcome TEXT;        -- win/loss/pending
ALTER TABLE trades ADD COLUMN lessons_learned TEXT; -- Post-trade analysis
```

**Web UI additions**:
- New "Trade History" tab showing all trades with full context
- Filter by ticker, date, outcome, strategy
- Click trade to see full decision context

---

## Priority 3: Agent Performance Metrics 🟡

**Problem**: Don't know which agents are most accurate.

**Solution**: Track agent signal accuracy

```python
# For each closed trade:
1. Look up which agents gave signals
2. Compare signal direction to actual outcome
3. Update agent accuracy score

# Metrics per agent:
- Total signals given
- Accuracy rate (% correct direction)
- Average return when followed
- Best/worst calls
```

**Web UI additions**:
- "Agent Leaderboard" showing which agents are most accurate
- Use this to weight future decisions

---

## Priority 4: Unified Dashboard (Single View) 🟡

**Problem**: Information scattered across multiple tabs.

**Solution**: Create a unified "Command Center" view

```
┌─────────────────────────────────────────────────────────────────┐
│                    MAZO PANTHEON COMMAND CENTER                  │
├─────────────────────────────────────────────────────────────────┤
│ Portfolio: $4,988.02        │  Today's P&L: -$11.98            │
│ Cash: $4,497.45             │  Win Rate: N/A (no closed trades)│
├─────────────────────────────────────────────────────────────────┤
│ OPEN POSITIONS              │  PENDING SIGNALS                  │
│ ├─ AAPL SHORT 10 @ $255.02  │  └─ TSLA: BUY signal (65% conf)  │
│ └─ MSFT SHORT 9 @ $431.76   │  └─ GOOGL: BUY signal (72% conf) │
├─────────────────────────────────────────────────────────────────┤
│ NEXT SCHEDULED ACTIONS                                          │
│ ├─ 4:47 PM - AI Trading Cycle                                  │
│ ├─ 5:02 PM - Stop-Loss Monitor                                 │
│ └─ Tomorrow 6:30 AM - Pre-Market Health Check                  │
├─────────────────────────────────────────────────────────────────┤
│ RECENT ACTIVITY                                                 │
│ ├─ 4:19 PM - Position monitor: AAPL within limits              │
│ ├─ 4:15 PM - AI Cycle: Screened 15 tickers, 0 trades          │
│ └─ 3:45 PM - Stop-loss checked: All positions OK               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Priority 5: Diversification-Driven Trading 🟡

**Problem**: System doesn't actively diversify - may over-concentrate.

**Solution**: Integrate diversification into trading decisions

```python
# Before each trade:
1. Check current sector allocation
2. If ticker would cause >30% sector concentration → Reduce size or skip
3. Suggest alternative tickers in underweight sectors

# In automated cycle:
1. Include diversification scan results in PM prompt
2. PM considers sector balance in decisions
```

---

## Priority 6: Alert System 🟢

**Problem**: User doesn't know when trades happen.

**Solution**: Implement notification system

- WebSocket for real-time UI updates
- Optional: Browser notifications
- Optional: Webhook to Discord/Slack
- Log all significant events

---

## Priority 7: Earnings & Events Awareness 🟢

**Problem**: System doesn't know about upcoming earnings, dividends, splits.

**Solution**: Add calendar integration

```python
# Before trading any ticker:
1. Check if earnings within 3 days → Flag as high-risk
2. Check if ex-dividend date → Adjust strategy
3. Pass this context to PM
```

---

## Priority 8: Learning From Outcomes 🟢

**Problem**: System doesn't learn from past trades.

**Solution**: Feedback loop

```python
# Weekly analysis:
1. Review all closed trades
2. Identify patterns in wins vs losses
3. Adjust agent weights based on accuracy
4. Generate "lessons learned" report
```

---

## Implementation Order

### Phase 1 (This Week)
1. ✅ Position Monitor with auto-exit (stop-loss/take-profit)
2. ✅ Enhanced trade logging with full context
3. ✅ Trade History UI tab

### Phase 2 (Next Week)  
4. Agent performance tracking
5. Unified Command Center dashboard
6. Alert notifications

### Phase 3 (Following Week)
7. Diversification-driven trading
8. Earnings calendar integration
9. Learning/feedback loop

---

## Technical Debt to Address

1. **Merge Unified Workflow + Automated Trading** - They should be the same system
2. **Standardize agent output format** - Some return dicts, some return objects
3. **Better error recovery** - If one agent fails, continue with others
4. **Rate limiting improvements** - Prevent API throttling
5. **Caching optimization** - Reduce redundant data fetches

---

## Web UI Wishlist

1. **Command Center** - Single view of everything
2. **Trade History** - Full history with filtering
3. **Agent Leaderboard** - Performance rankings
4. **Live Activity Feed** - Real-time updates
5. **Manual Override** - Ability to approve/reject AI decisions
6. **Backtest View** - See how strategy would have performed historically
