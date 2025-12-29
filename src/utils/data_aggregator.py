"""
Data Aggregator - Pre-fetch and share financial data across agents

This module aggregates all financial data needed by agents BEFORE they run,
preventing duplicate API calls and allowing agents to share cached data.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.tools.api import (
    get_financial_metrics,
    get_market_cap,
    search_line_items,
    get_prices,
    get_company_news,
    get_insider_trades,
)
from src.utils.api_key import get_api_key_from_state
from src.graph.state import AgentState


@dataclass
class AggregatedData:
    """Container for all aggregated financial data"""
    # Financial metrics (multiple periods)
    financial_metrics: Dict[str, List] = None  # ticker -> list of metrics
    
    # Line items (multiple periods)
    line_items: Dict[str, Dict] = None  # ticker -> {line_item_name: list of values}
    
    # Market data
    market_caps: Dict[str, float] = None  # ticker -> market_cap
    prices: Dict[str, List] = None  # ticker -> list of prices
    
    # News and sentiment
    news: Dict[str, List] = None  # ticker -> list of news articles
    insider_trades: Dict[str, List] = None  # ticker -> list of insider trades
    
    def __post_init__(self):
        """Initialize empty dicts if None"""
        if self.financial_metrics is None:
            self.financial_metrics = {}
        if self.line_items is None:
            self.line_items = {}
        if self.market_caps is None:
            self.market_caps = {}
        if self.prices is None:
            self.prices = {}
        if self.news is None:
            self.news = {}
        if self.insider_trades is None:
            self.insider_trades = {}


def aggregate_financial_data(
    state: AgentState,
    tickers: List[str],
    end_date: str,
    start_date: Optional[str] = None,
) -> AggregatedData:
    """
    Pre-fetch all financial data needed by agents.
    
    This function:
    1. Fetches all common financial data once
    2. Stores it in a shared structure
    3. Returns it for agents to use
    
    Args:
        state: AgentState containing API keys
        tickers: List of ticker symbols
        end_date: End date for data (YYYY-MM-DD)
        start_date: Optional start date (defaults to 1 year back)
    
    Returns:
        AggregatedData with all fetched data
    """
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    
    # Default start_date to 1 year back
    if start_date is None:
        start_date = (datetime.fromisoformat(end_date) - timedelta(days=365)).date().isoformat()
    
    aggregated = AggregatedData()
    
    print(f"\n{'='*60}")
    print("AGGREGATING FINANCIAL DATA")
    print(f"{'='*60}")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"{'='*60}\n")
    
    # Common line items needed by most agents
    common_line_items = [
        "revenue",
        "net_income",
        "earnings_per_share",
        "free_cash_flow",
        "total_assets",
        "total_liabilities",
        "shareholders_equity",
        "current_assets",
        "current_liabilities",
        "total_debt",
        "cash_and_equivalents",
        "outstanding_shares",
        "capital_expenditure",
        "depreciation_and_amortization",
        "operating_income",
        "ebit",
        "gross_profit",
        "operating_margin",
        "gross_margin",
        "dividends_and_other_cash_distributions",
        "issuance_or_purchase_of_equity_shares",
        "research_and_development",
        "operating_expense",
    ]
    
    for ticker in tickers:
        print(f"[{ticker}] Fetching data...")
        
        # Financial metrics (TTM and Annual)
        try:
            print(f"  - Financial metrics (TTM)...")
            aggregated.financial_metrics[ticker] = get_financial_metrics(
                ticker, end_date, period="ttm", limit=10, api_key=api_key
            )
        except Exception as e:
            print(f"    Error: {e}")
            aggregated.financial_metrics[ticker] = []
        
        # Line items (TTM)
        try:
            print(f"  - Line items (TTM)...")
            ttm_line_items = search_line_items(
                ticker, common_line_items, end_date,
                period="ttm", limit=10, api_key=api_key
            )
            aggregated.line_items[ticker] = ttm_line_items
        except Exception as e:
            print(f"    Error: {e}")
            aggregated.line_items[ticker] = {}
        
        # Market cap
        try:
            print(f"  - Market cap...")
            aggregated.market_caps[ticker] = get_market_cap(ticker, end_date, api_key=api_key)
        except Exception as e:
            print(f"    Error: {e}")
            aggregated.market_caps[ticker] = None
        
        # Prices
        try:
            print(f"  - Price history...")
            aggregated.prices[ticker] = get_prices(ticker, start_date, end_date)
        except Exception as e:
            print(f"    Error: {e}")
            aggregated.prices[ticker] = []
        
        # News (last year)
        try:
            print(f"  - Company news...")
            aggregated.news[ticker] = get_company_news(
                ticker, end_date=end_date, start_date=start_date, limit=250
            )
        except Exception as e:
            print(f"    Error: {e}")
            aggregated.news[ticker] = []
        
        # Insider trades (last year)
        try:
            print(f"  - Insider trades...")
            aggregated.insider_trades[ticker] = get_insider_trades(
                ticker, end_date=end_date, start_date=start_date
            )
        except Exception as e:
            print(f"    Error: {e}")
            aggregated.insider_trades[ticker] = []
        
        print(f"[{ticker}] ✓ Data aggregated\n")
    
    print(f"{'='*60}")
    print("DATA AGGREGATION COMPLETE")
    print(f"{'='*60}\n")
    
    return aggregated


def add_aggregated_data_to_state(
    state: AgentState,
    aggregated_data: AggregatedData
) -> AgentState:
    """
    Add aggregated data to the AgentState so agents can access it.
    
    Args:
        state: Current AgentState
        aggregated_data: Pre-fetched aggregated data
    
    Returns:
        Updated AgentState with aggregated data
    """
    # Store in state["data"] for easy access
    if "aggregated_data" not in state["data"]:
        state["data"]["aggregated_data"] = {}
    
    # Convert to dict for JSON serialization
    state["data"]["aggregated_data"] = {
        "financial_metrics": aggregated_data.financial_metrics,
        "line_items": aggregated_data.line_items,
        "market_caps": aggregated_data.market_caps,
        "prices": aggregated_data.prices,
        "news": aggregated_data.news,
        "insider_trades": aggregated_data.insider_trades,
    }
    
    return state
