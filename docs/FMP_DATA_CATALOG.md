# FMP Ultimate Data Catalog

This document describes the full FMP (Financial Modeling Prep) Ultimate data integration across the Mazo Pantheon stack.

## Overview

FMP Ultimate provides comprehensive financial data that enhances every stage of the autonomous trading pipeline:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       FMP DATA FLOW                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   FMP Gateway (src/data/fmp_gateway.py)                                │
│         ↓                                                               │
│   Python API Layer (src/tools/api.py)                                  │
│         ↓                                                               │
│   ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐               │
│   │ Strategy    │  │ 18 AI        │  │ Portfolio       │               │
│   │ Engine      │  │ Agents       │  │ Manager         │               │
│   └─────────────┘  └──────────────┘  └─────────────────┘               │
│         ↓                ↓                   ↓                          │
│                    Mazo TypeScript (fmp.ts)                            │
│                          ↓                                              │
│                    Trading Decisions                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Modules

Each FMP data family can be enabled/disabled independently via environment variables:

| Module | Env Variable | Default | Description |
|--------|-------------|---------|-------------|
| **Fundamentals** | `FMP_MODULE_FUNDAMENTALS` | `true` | Company profiles, peers, executives |
| **Analysts** | `FMP_MODULE_ANALYSTS` | `true` | Estimates, price targets, grades |
| **Filings** | `FMP_MODULE_FILINGS` | `true` | 13F holdings, SEC filings |
| **Insider** | `FMP_MODULE_INSIDER` | `true` | Insider trading activity |
| **Calendar** | `FMP_MODULE_CALENDAR` | `true` | Earnings, dividends, IPOs, economic |
| **Macro** | `FMP_MODULE_MACRO` | `true` | Economic indicators, treasury rates |
| **Market** | `FMP_MODULE_MARKET` | `true` | Sector performance, gainers/losers |
| **ETF** | `FMP_MODULE_ETF` | `true` | ETF holdings and constituents |
| **Commodities** | `FMP_MODULE_COMMODITIES` | `true` | Gold, oil, etc. quotes |
| **Forex** | `FMP_MODULE_FOREX` | `true` | Currency pair quotes |
| **Crypto** | `FMP_MODULE_CRYPTO` | `true` | Cryptocurrency quotes |
| **ESG** | `FMP_MODULE_ESG` | `true` | Environmental, Social, Governance |

## API Functions

### Python (src/tools/api.py)

```python
# Company Data
get_company_profile(ticker)      # Full company profile
get_company_peers(ticker)        # Peer company list

# Analyst Data
get_analyst_estimates(ticker)    # EPS/revenue estimates
get_price_targets(ticker)        # Analyst price targets
get_price_target_consensus(ticker)  # Consensus target
get_stock_grades(ticker)         # Upgrade/downgrade history
get_analyst_recommendations(ticker) # Buy/hold/sell counts

# Insider & Institutional
get_fmp_insider_trades(ticker)   # Insider trading activity
get_form_13f(ticker)             # 13F institutional holdings
get_institutional_holders(ticker) # Institutional owners

# Calendars
get_earnings_calendar(from, to)  # Upcoming earnings
get_economic_calendar(from, to)  # Economic events

# Market Data
get_sector_performance()         # Sector performance
get_market_movers("gainers")     # Top gainers
get_market_movers("losers")      # Top losers
get_market_movers("actives")     # Most active

# Multi-Asset
get_etf_holdings(etf_symbol)     # ETF constituents
get_commodity_quotes()           # Commodity prices
get_forex_quotes()               # Forex pairs
get_crypto_quotes()              # Crypto prices

# ESG
get_esg_score(ticker)            # ESG ratings

# Status
get_fmp_module_status()          # Module enable/disable status
```

### TypeScript (mazo/src/tools/finance/fmp.ts)

```typescript
// Company Data
getFmpCompanyProfile(ticker)
getFmpCompanyPeers(ticker)

// Analyst Data
getFmpAnalystEstimates(ticker, period, limit)
getFmpPriceTargets(ticker, limit)
getFmpPriceTargetConsensus(ticker)
getFmpStockGrades(ticker, limit)

// Insider & Institutional
getFmpInsiderTrades(ticker, limit)
getFmpInstitutionalHolders(ticker)

// Calendars
getFmpEarningsCalendar(fromDate, toDate)
getFmpEconomicCalendar(fromDate, toDate)

// Market Data
getFmpSectorPerformance()
getFmpMarketMovers("gainers" | "losers" | "actives", limit)

// Multi-Asset
getFmpCommodityQuotes()
getFmpCryptoQuotes(limit)

// ESG
getFmpEsgScore(ticker)

// Status
getFmpModuleStatus()
```

## Integration Points

### Strategy Engine

The strategy engine uses FMP data for:
- Sector rotation signals
- Earnings calendar (avoid trading before announcements)
- Analyst estimate revisions

### 18 AI Agents

Each analyst agent can access:
- Company fundamentals and profiles
- Peer comparisons
- Analyst price targets
- Insider trading patterns
- ESG scores (for relevant strategies)

### Portfolio Manager

The PM receives enriched context including:
- Analyst consensus (buy/hold/sell counts)
- Price target consensus
- Recent insider activity
- Sector performance
- Upcoming earnings warnings

Example PM context:
```
=== MARKET INTELLIGENCE (FMP) ===
SECTOR PERFORMANCE:
  Top: Technology (+1.5%), Healthcare (+0.8%), Financials (+0.5%)
  Bottom: Energy (-2.1%), Utilities (-1.2%), Real Estate (-0.8%)

AAPL: Analysts: 32 buy, 8 hold, 2 sell | Price Target: $195.00 (range: $170-$220)
MSFT: Analysts: 40 buy, 5 hold, 0 sell | Insider Activity: 2 buys, 1 sells

EARNINGS THIS WEEK:
  AAPL on 2024-01-25 (amc)
  MSFT on 2024-01-25 (amc)
```

### Monitoring UI

The Monitoring dashboard shows:
- FMP module status (enabled/disabled per module)
- FMP API health (connectivity test)
- Rate limit usage
- Recent call activity

Access via: `GET /monitoring/data-sources/fmp`

## Configuration

### Minimum Setup

```bash
# .env
FMP_API_KEY=your-fmp-api-key
PRIMARY_DATA_SOURCE=fmp
```

### Disable Specific Modules

```bash
# Disable modules you don't need
FMP_MODULE_CRYPTO=false
FMP_MODULE_FOREX=false
FMP_MODULE_ESG=false
```

### Rate Limiting

FMP calls are rate-limited and cached:
- Quotes/prices: 60s cache
- Fundamentals: 1 hour cache
- Profiles: 24 hour cache
- Calendar data: 5 minute cache

All calls are tracked in the rate limit monitor for observability.

## Caching Strategy

| Data Type | Cache TTL | Reason |
|-----------|-----------|--------|
| Quotes | 60s | Real-time data |
| Sector performance | 5 min | Intraday changes |
| Earnings calendar | 5 min | Event proximity |
| Company profile | 24 hr | Rarely changes |
| Analyst estimates | 1 hr | Updates with filings |
| Insider trades | 30 min | Filed daily |
| ESG scores | 24 hr | Quarterly updates |

## Fallback Behavior

If FMP fails or a module is disabled:
1. Return empty list/None for optional data
2. Log warning (not error) for missing data
3. PM/agents continue with available signals
4. Never block trading due to FMP unavailability

## Troubleshooting

### Check FMP Status

```bash
curl http://localhost:8000/monitoring/data-sources/fmp
```

### Verify API Key

```python
from src.data.fmp_gateway import get_fmp_gateway
gw = get_fmp_gateway()
print(f"Configured: {gw.is_configured()}")
print(f"Modules: {gw.get_module_status()}")
```

### Test Specific Endpoint

```python
from src.tools.api import get_company_profile
profile = get_company_profile("AAPL")
print(profile)
```

## Best Practices

1. **Enable only needed modules** - Reduces API calls
2. **Monitor rate limits** - Check Monitoring tab
3. **Use caching** - Don't bypass cache for repeated calls
4. **Graceful degradation** - PM works without FMP data
5. **Log FMP influence** - Track when FMP data affects decisions
