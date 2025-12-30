import json
import logging
import time
import uuid
from datetime import datetime, date
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from src.graph.state import AgentState, show_agent_reasoning

logger = logging.getLogger(__name__)
from src.graph.portfolio_context import PortfolioContext
from pydantic import BaseModel, Field
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm

# Lazy import for monitoring
_event_logger = None


def _get_event_logger():
    """Get event logger lazily."""
    global _event_logger
    if _event_logger is None:
        try:
            from src.monitoring import get_event_logger
            _event_logger = get_event_logger()
        except ImportError:
            pass
    return _event_logger


class PortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "short", "cover", "hold", "cancel", "reduce_long", "reduce_short"]
    quantity: int = Field(description="Number of shares to trade (0 for cancel/hold)")
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")
    # Optional rebalancing context
    rebalance_target: str | None = Field(default=None, description="If reducing to make room for another ticker")
    # Risk management targets (optional)
    stop_loss_pct: float | None = Field(default=None, description="Stop loss as % from entry (e.g., 5.0 = 5% loss)")
    take_profit_pct: float | None = Field(default=None, description="Take profit as % from entry (e.g., 10.0 = 10% gain)")


class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision] = Field(description="Dictionary of ticker to trading decisions")


##### Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState, agent_id: str = "portfolio_manager"):
    """Makes final trading decisions and generates orders for multiple tickers"""

    portfolio = state["data"]["portfolio"]
    analyst_signals = state["data"]["analyst_signals"]
    tickers = state["data"]["tickers"]
    
    # Get Mazo research if available (for counter-argument consideration)
    mazo_research = state["data"].get("mazo_research", None)

    position_limits = {}
    current_prices = {}
    max_shares = {}
    signals_by_ticker = {}
    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Processing analyst signals")

        # Find the corresponding risk manager for this portfolio manager
        if agent_id.startswith("portfolio_manager_"):
            suffix = agent_id.split('_')[-1]
            risk_manager_id = f"risk_management_agent_{suffix}"
        else:
            risk_manager_id = "risk_management_agent"  # Fallback for CLI

        risk_data = analyst_signals.get(risk_manager_id, {}).get(ticker, {})
        position_limits[ticker] = risk_data.get("remaining_position_limit", 0.0)
        current_prices[ticker] = float(risk_data.get("current_price", 0.0))

        # Calculate maximum shares allowed based on position limit and price
        if current_prices[ticker] > 0:
            max_shares[ticker] = int(position_limits[ticker] // current_prices[ticker])
        else:
            max_shares[ticker] = 0

        # Compress analyst signals to {sig, conf}
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            if not agent.startswith("risk_management_agent") and ticker in signals:
                sig = signals[ticker].get("signal")
                conf = signals[ticker].get("confidence")
                if sig is not None and conf is not None:
                    ticker_signals[agent] = {"sig": sig, "conf": conf}
        signals_by_ticker[ticker] = ticker_signals

    state["data"]["current_prices"] = current_prices

    progress.update_status(agent_id, None, "Generating trading decisions")

    result = generate_trading_decision(
        tickers=tickers,
        signals_by_ticker=signals_by_ticker,
        current_prices=current_prices,
        max_shares=max_shares,
        portfolio=portfolio,
        agent_id=agent_id,
        state=state,
        mazo_research=mazo_research,
    )
    message = HumanMessage(
        content=json.dumps({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}),
        name=agent_id,
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning({ticker: decision.model_dump() for ticker, decision in result.decisions.items()},
                             "Portfolio Manager")

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }


def compute_allowed_actions(
        tickers: list[str],
        current_prices: dict[str, float],
        max_shares: dict[str, int],
        portfolio: dict[str, float],
) -> dict[str, dict[str, int]]:
    """Compute allowed actions and max quantities for each ticker.
    
    NOTE: We always include ALL actions to give the LLM full autonomy.
    The LLM can decide to take any action based on its analysis.
    Quantity constraints are advisory, not blocking.
    """
    allowed = {}
    cash = float(portfolio.get("cash", 0.0))
    buying_power = float(portfolio.get("buying_power", cash))
    positions = portfolio.get("positions", {}) or {}
    pending_orders = portfolio.get("pending_orders", []) or []
    is_paper = portfolio.get("paper_trading", True)
    margin_requirement = float(portfolio.get("margin_requirement", 0.5))
    margin_used = float(portfolio.get("margin_used", 0.0))
    equity = float(portfolio.get("equity", cash))

    for ticker in tickers:
        price = float(current_prices.get(ticker, 0.0))
        pos = positions.get(
            ticker,
            {"long": 0, "long_cost_basis": 0.0, "short": 0, "short_cost_basis": 0.0},
        )
        long_shares = int(pos.get("long", 0) or 0)
        short_shares = int(pos.get("short", 0) or 0)
        max_qty = int(max_shares.get(ticker, 0) or 0)
        
        # Check for pending orders on this ticker
        ticker_pending = [o for o in pending_orders if o.get('symbol') == ticker]
        has_pending = len(ticker_pending) > 0

        # ALWAYS include all actions - let LLM decide
        actions = {}

        # BUY: Limited by cash/buying power and risk limits
        if price > 0:
            max_buy_cash = int(buying_power // price)
            max_buy = max(1, min(max_qty, max_buy_cash)) if max_buy_cash > 0 else 0
            # For paper trading, allow at least some shares if we have any buying power
            if is_paper and max_buy == 0 and buying_power > price:
                max_buy = int(buying_power // price)
            actions["buy"] = max_buy

        # SELL: Can sell whatever long position we have
        actions["sell"] = long_shares if long_shares > 0 else 0

        # SHORT: Limited by margin
        if price > 0:
            if margin_requirement <= 0.0:
                max_short = max_qty
            else:
                available_margin = max(0.0, (equity / margin_requirement) - margin_used)
                max_short_margin = int(available_margin // price)
                max_short = max(0, min(max_qty, max_short_margin))
            # For paper trading, be more generous
            if is_paper and max_short == 0 and equity > 0:
                max_short = max(1, int(equity * 0.3 / price))  # Allow up to 30% of equity
            actions["short"] = max_short

        # COVER: Can cover whatever short position we have  
        actions["cover"] = short_shares if short_shares > 0 else 0

        # REDUCE_LONG: Partial sell of long position (for rebalancing)
        if long_shares > 1:
            actions["reduce_long"] = long_shares - 1  # Can reduce down to 1 share
        
        # REDUCE_SHORT: Partial cover of short position (for rebalancing)
        if short_shares > 1:
            actions["reduce_short"] = short_shares - 1  # Can reduce down to 1 share

        # HOLD: Always available
        actions["hold"] = 0
        
        # CANCEL: Available if there are pending orders
        if has_pending:
            actions["cancel"] = len(ticker_pending)  # Number of orders that can be cancelled

        allowed[ticker] = actions

    return allowed


def compute_portfolio_concentration(portfolio: dict, current_prices: dict[str, float]) -> dict:
    """Compute portfolio concentration metrics for rebalancing decisions."""
    positions = portfolio.get("positions", {}) or {}
    equity = float(portfolio.get("equity", portfolio.get("cash", 0)))
    
    if equity <= 0:
        return {"concentrations": {}, "total_long_pct": 0, "total_short_pct": 0}
    
    concentrations = {}
    total_long_value = 0
    total_short_value = 0
    
    for ticker, pos in positions.items():
        long_shares = int(pos.get("long", 0) or 0)
        short_shares = int(pos.get("short", 0) or 0)
        price = float(current_prices.get(ticker, 0))
        
        if price > 0:
            long_value = long_shares * price
            short_value = short_shares * price
            total_value = long_value + short_value
            
            if total_value > 0:
                concentrations[ticker] = {
                    "value": total_value,
                    "pct": (total_value / equity) * 100,
                    "long_shares": long_shares,
                    "short_shares": short_shares,
                    "side": "long" if long_shares > 0 else "short"
                }
                total_long_value += long_value
                total_short_value += short_value
    
    return {
        "concentrations": concentrations,
        "total_long_pct": (total_long_value / equity) * 100 if equity > 0 else 0,
        "total_short_pct": (total_short_value / equity) * 100 if equity > 0 else 0,
        "equity": equity
    }


def _compact_signals(signals_by_ticker: dict[str, dict]) -> dict[str, dict]:
    """Keep only {agent: {sig, conf}} and drop empty agents."""
    out = {}
    for t, agents in signals_by_ticker.items():
        if not agents:
            out[t] = {}
            continue
        compact = {}
        for agent, payload in agents.items():
            sig = payload.get("sig") or payload.get("signal")
            conf = payload.get("conf") if "conf" in payload else payload.get("confidence")
            if sig is not None and conf is not None:
                compact[agent] = {"sig": sig, "conf": conf}
        out[t] = compact
    return out


def _build_historical_context(portfolio: dict, tickers: list[str]) -> str:
    """
    Build historical context including today's trades and performance.
    This helps the PM understand past decisions and optimize for daily profit.
    """
    lines = []
    
    try:
        from src.trading.alpaca_service import AlpacaService
        alpaca = AlpacaService()
        
        # Get today's date info
        now = datetime.now()
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        time_remaining = (market_close - now).total_seconds() / 3600 if now < market_close else 0
        
        lines.append(f"=== TODAY'S PERFORMANCE ({now.strftime('%Y-%m-%d %H:%M ET')}) ===")
        
        if time_remaining > 0:
            lines.append(f"⏰ Time until market close: {time_remaining:.1f} hours")
        else:
            lines.append("⏰ Market is closed")
        
        # Get account performance
        account = alpaca.get_account()
        if account:
            equity = float(account.equity)
            last_equity = float(account.last_equity) if hasattr(account, 'last_equity') and account.last_equity else equity
            day_pl = equity - last_equity
            day_pl_pct = (day_pl / last_equity * 100) if last_equity > 0 else 0
            pl_sign = "+" if day_pl >= 0 else ""
            
            lines.append(f"\n📊 Today's P&L: {pl_sign}${day_pl:,.2f} ({pl_sign}{day_pl_pct:.2f}%)")
            
            # Goal for the day
            if day_pl >= 0:
                lines.append(f"✅ Currently PROFITABLE today - protect gains")
            else:
                lines.append(f"⚠️ Currently at LOSS today - focus on recovery")
        
        # Get today's executed orders
        orders = alpaca.get_orders(status="closed", limit=20)
        today = date.today()
        today_orders = []
        for o in (orders or []):
            if hasattr(o, 'filled_at') and o.filled_at:
                try:
                    # Handle both datetime objects and ISO strings
                    if isinstance(o.filled_at, str):
                        filled_date = datetime.fromisoformat(o.filled_at.replace('Z', '+00:00')).date()
                    else:
                        filled_date = o.filled_at.date()
                    if filled_date == today:
                        today_orders.append(o)
                except:
                    pass
        
        if today_orders:
            lines.append(f"\n📜 Today's Executed Trades ({len(today_orders)}):")
            for order in today_orders[:5]:  # Show last 5
                side = order.side.upper() if hasattr(order, 'side') else 'UNKNOWN'
                qty = float(order.qty) if hasattr(order, 'qty') else 0
                symbol = order.symbol if hasattr(order, 'symbol') else 'UNKNOWN'
                filled_price = float(order.filled_avg_price) if hasattr(order, 'filled_avg_price') and order.filled_avg_price else 0
                lines.append(f"  • {symbol}: {side} {qty:.0f} @ ${filled_price:.2f}")
        else:
            lines.append("\n📜 No trades executed today yet")
        
        # Get current positions with P&L for relevant tickers
        positions = alpaca.get_positions()
        relevant_positions = [p for p in (positions or []) if p.symbol in tickers]
        
        if relevant_positions:
            lines.append("\n📈 Position Performance (for analysis tickers):")
            for pos in relevant_positions:
                pl = float(pos.unrealized_pl) if hasattr(pos, 'unrealized_pl') else 0
                pl_pct = float(pos.unrealized_plpc) * 100 if hasattr(pos, 'unrealized_plpc') else 0
                pl_sign = "+" if pl >= 0 else ""
                entry = float(pos.avg_entry_price) if hasattr(pos, 'avg_entry_price') else 0
                current = float(pos.current_price) if hasattr(pos, 'current_price') else 0
                qty = float(pos.qty) if hasattr(pos, 'qty') else 0
                side = "LONG" if qty > 0 else "SHORT"
                lines.append(f"  • {pos.symbol} ({side}): Entry ${entry:.2f} → Now ${current:.2f} | P&L: {pl_sign}${pl:.2f} ({pl_sign}{pl_pct:.1f}%)")
                
                # Add actionable insights
                if pl_pct > 5:
                    lines.append(f"    → Consider taking profits (>{5}% gain)")
                elif pl_pct < -5:
                    lines.append(f"    → Consider cutting losses (>{5}% loss)")
        
        # Add strategy reminders based on time of day
        lines.append("\n🎯 DAILY PROFIT STRATEGY:")
        if time_remaining > 5:
            lines.append("  • Early session: Be selective, look for strong signals")
            lines.append("  • Build positions gradually, don't over-commit")
        elif time_remaining > 2:
            lines.append("  • Mid-day: Monitor positions, adjust stops")
            lines.append("  • Lock in profits on winners, cut losers quickly")
        elif time_remaining > 0:
            lines.append("  • Late session: Focus on closing positions")
            lines.append("  • Don't open new positions close to market close")
            lines.append("  • Secure daily profits, avoid overnight risk")
        else:
            lines.append("  • Market closed: Review today's performance")
            lines.append("  • Plan for tomorrow based on after-hours movement")
        
    except Exception as e:
        lines.append(f"(Historical context unavailable: {str(e)[:50]})")
    
    return "\n".join(lines)


def _build_position_context(portfolio: dict, tickers: list[str], current_prices: dict[str, float]) -> str:
    """Build a rich position context string for the LLM with concentration analysis."""
    lines = []
    
    # Portfolio summary
    cash = float(portfolio.get("cash", 0))
    buying_power = float(portfolio.get("buying_power", cash))
    portfolio_value = float(portfolio.get("portfolio_value", cash))
    equity = float(portfolio.get("equity", portfolio_value))
    
    lines.append(f"Portfolio: ${portfolio_value:,.0f} total | ${cash:,.0f} cash | ${buying_power:,.0f} buying power")
    
    # Compute concentration metrics
    concentration_data = compute_portfolio_concentration(portfolio, current_prices)
    concentrations = concentration_data["concentrations"]
    
    # Current positions with concentration %
    positions = portfolio.get("positions", {})
    position_lines = []
    concentration_warnings = []
    
    for ticker in tickers:
        pos = positions.get(ticker, {})
        long_shares = int(pos.get("long", 0) or 0)
        short_shares = int(pos.get("short", 0) or 0)
        conc = concentrations.get(ticker, {})
        conc_pct = conc.get("pct", 0)
        
        if long_shares > 0:
            entry = float(pos.get("long_cost_basis", 0) or 0)
            current = float(current_prices.get(ticker, entry))
            pl = (current - entry) * long_shares if entry > 0 else 0
            pl_pct = ((current / entry) - 1) * 100 if entry > 0 else 0
            pl_sign = "+" if pl >= 0 else ""
            position_lines.append(f"  {ticker}: LONG {long_shares} @ ${entry:.2f}→${current:.2f} ({pl_sign}{pl_pct:.1f}%) | {conc_pct:.1f}% of portfolio")
            if conc_pct > 25:
                concentration_warnings.append(f"  ⚠️ {ticker}: {conc_pct:.1f}% concentration is HIGH (>25%)")
        elif short_shares > 0:
            entry = float(pos.get("short_cost_basis", 0) or 0)
            current = float(current_prices.get(ticker, entry))
            pl = (entry - current) * short_shares if entry > 0 else 0
            pl_pct = ((entry / current) - 1) * 100 if current > 0 else 0
            pl_sign = "+" if pl >= 0 else ""
            position_lines.append(f"  {ticker}: SHORT {short_shares} @ ${entry:.2f}→${current:.2f} ({pl_sign}{pl_pct:.1f}%) | {conc_pct:.1f}% of portfolio")
            if conc_pct > 25:
                concentration_warnings.append(f"  ⚠️ {ticker}: {conc_pct:.1f}% concentration is HIGH (>25%)")
        else:
            position_lines.append(f"  {ticker}: No position")
    
    if position_lines:
        lines.append("Positions:")
        lines.extend(position_lines)
    
    # Show concentration warnings
    if concentration_warnings:
        lines.append("\nCONCENTRATION WARNINGS:")
        lines.extend(concentration_warnings)
        lines.append("Consider using 'reduce_long' or 'reduce_short' to rebalance before adding new positions.")
    
    # Pending orders
    pending = portfolio.get("pending_orders", [])
    if pending:
        order_lines = [f"  {o['symbol']}: {o['side'].upper()} {o['qty']} shares ({o['status']})" for o in pending if o['symbol'] in tickers]
        if order_lines:
            lines.append("\nPending Orders:")
            lines.extend(order_lines)
    
    # Rebalancing opportunity check
    if len(tickers) > 1 and concentration_warnings:
        lines.append("\nREBALANCING OPPORTUNITY:")
        lines.append("You can reduce an over-concentrated position to free up capital for other tickers.")
    
    return "\n".join(lines)


def generate_trading_decision(
        tickers: list[str],
        signals_by_ticker: dict[str, dict],
        current_prices: dict[str, float],
        max_shares: dict[str, int],
        portfolio: dict[str, float],
        agent_id: str,
        state: AgentState,
        mazo_research: str = None,
) -> PortfolioManagerOutput:
    """Get decisions from the LLM with deterministic constraints and portfolio context."""

    # Get action constraints (advisory, not blocking)
    allowed_actions_full = compute_allowed_actions(tickers, current_prices, max_shares, portfolio)

    # ALWAYS send ALL tickers to LLM - let it decide based on full analysis
    # Don't pre-fill holds - the LLM should make ALL decisions
    prefilled_decisions: dict[str, PortfolioDecision] = {}
    tickers_for_llm = list(tickers)  # ALL tickers go to LLM

    if not tickers_for_llm:
        return PortfolioManagerOutput(decisions=prefilled_decisions)

    # Build compact payloads only for tickers sent to LLM
    compact_signals = _compact_signals({t: signals_by_ticker.get(t, {}) for t in tickers_for_llm})
    compact_allowed = {t: allowed_actions_full[t] for t in tickers_for_llm}
    
    # Build rich position context
    position_context = _build_position_context(portfolio, tickers_for_llm, current_prices)
    
    # Build historical context (today's trades, P&L, strategy)
    historical_context = _build_historical_context(portfolio, tickers_for_llm)

    # Check if paper trading mode (more aggressive)
    is_paper_trading = portfolio.get("paper_trading", True)  # Default to paper for safety
    
    # Build Mazo research section if available
    mazo_section = ""
    if mazo_research:
        # Truncate if too long to keep prompt efficient
        research_summary = mazo_research[:2000] if len(mazo_research) > 2000 else mazo_research
        mazo_section = f"\n\n=== INDEPENDENT RESEARCH (Mazo AI) ===\n{research_summary}\n\nIMPORTANT: Consider this research carefully. If it contradicts analyst signals, weigh both perspectives."
    
    # Different prompts for paper vs live trading
    if is_paper_trading:
        system_prompt = (
            "You are an INTELLIGENT portfolio manager in PAPER TRADING mode. Your PRIMARY GOAL is to END EACH DAY PROFITABLE.\n\n"
            "DAILY PROFIT STRATEGY:\n"
            "1. You have access to TODAY'S PERFORMANCE data - use it to make smart decisions\n"
            "2. If today's P&L is positive → protect gains, be more conservative\n"
            "3. If today's P&L is negative → look for recovery opportunities\n"
            "4. Track your previous trades today - learn from wins and losses\n"
            "5. Consider TIME OF DAY: less aggressive near market close\n\n"
            "SIGNAL INTERPRETATION (18 AI Agents + Mazo Research):\n"
            "1. If majority of agents say BEARISH → SHORT the stock\n"
            "2. If majority of agents say BULLISH → BUY the stock\n"
            "3. Weight agent confidence scores - higher confidence = stronger signal\n"
            "4. Mazo provides independent research - use it as a second opinion\n"
            "5. ONLY use HOLD if signals are truly 50/50 split\n\n"
            "POSITION MANAGEMENT:\n"
            "- Position with +5% gain → Consider taking profits (sell/cover)\n"
            "- Position with -5% loss → Consider cutting losses (sell/cover)\n"
            "- If a position is >25% of portfolio → reduce_long or reduce_short\n"
            "- Diversify: Don't put all capital in one stock\n\n"
            "AVAILABLE ACTIONS:\n"
            "- buy: Open LONG (stock goes UP)\n"
            "- sell: Close entire LONG position\n"
            "- short: Open SHORT (stock goes DOWN)\n"
            "- cover: Close entire SHORT position\n"
            "- reduce_long: PARTIAL sell of long (keep some shares, reduce concentration)\n"
            "- reduce_short: PARTIAL cover of short (keep some shares, reduce concentration)\n"
            "- hold: NO TRADE (only use if truly 50/50 split)\n"
            "- cancel: Cancel pending orders\n\n"
            "RISK MANAGEMENT (for new positions):\n"
            "- stop_loss_pct: Set a stop loss as % from entry (typically 3-8%)\n"
            "- take_profit_pct: Set a profit target as % from entry (typically 5-15%)\n"
            "- For SHORTS: stop_loss triggers if price goes UP by X%, take_profit if price goes DOWN\n"
            "- For LONGS: stop_loss triggers if price goes DOWN by X%, take_profit if price goes UP\n\n"
            "Return JSON only. Include stop_loss_pct and take_profit_pct for new positions."
        )
    else:
        system_prompt = (
            "You are an INTELLIGENT portfolio manager making trading decisions with REAL MONEY.\n"
            "Your PRIMARY GOAL is to END EACH DAY PROFITABLE while managing risk.\n\n"
            "DAILY PROFIT STRATEGY:\n"
            "1. Review TODAY'S PERFORMANCE data before every decision\n"
            "2. If today's P&L is positive → protect gains, tighten stops\n"
            "3. If today's P&L is negative → be selective, only high-confidence trades\n"
            "4. Track previous trades today - don't repeat losing strategies\n"
            "5. Consider TIME OF DAY: reduce position sizes near market close\n\n"
            "SIGNAL INTERPRETATION (18 AI Agents + Mazo Research):\n"
            "1. Require STRONG consensus (>70% agents agree) for new positions\n"
            "2. Weight agent confidence scores heavily\n"
            "3. Mazo research provides independent validation\n"
            "4. If agents and Mazo disagree → HOLD and wait for clarity\n\n"
            "POSITION MANAGEMENT:\n"
            "- Position with +5% gain → Consider taking profits\n"
            "- Position with -3% loss → Consider cutting losses (real money = tighter stops)\n"
            "- If a position is >25% of portfolio → reduce_long or reduce_short\n"
            "- Diversify: Max 4-5 positions at any time\n\n"
            "AVAILABLE ACTIONS:\n"
            "- buy/sell: For long positions (full close)\n"
            "- short/cover: For short positions (full close)\n"
            "- reduce_long: PARTIAL sell (keep some shares)\n"
            "- reduce_short: PARTIAL cover (keep some shares)\n"
            "- hold: No action\n"
            "- cancel: Cancel pending orders\n\n"
            "RISK MANAGEMENT (REQUIRED for new positions):\n"
            "- stop_loss_pct: Set a stop loss as % from entry (typically 2-5%)\n"
            "- take_profit_pct: Set a profit target as % from entry (typically 5-10%)\n"
            "- ALWAYS set these for new positions to limit downside risk\n\n"
            "Inputs: today's performance, analyst signals, positions, Mazo research.\n"
            "Pick one action per ticker. Include stop_loss_pct and take_profit_pct.\n"
            "Keep reasoning concise (max 150 chars). Return JSON only."
        )
    
    # Enhanced prompt with portfolio awareness, historical context, and Mazo research
    template = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "human",
                "{historical_context}\n\n"
                "=== PORTFOLIO STATE ===\n{portfolio_context}\n\n"
                "=== ANALYST SIGNALS (18 AI Agents) ===\n{signals}\n\n"
                "{mazo_research}"
                "=== ALLOWED ACTIONS (max qty per action) ===\n{allowed}\n\n"
                "DECISION REQUIRED: For each ticker, pick ONE action.\n"
                "Priority order:\n"
                "1. PROTECT PROFITS: If position is +5% or more, consider taking profits\n"
                "2. CUT LOSSES: If position is -5% or more, consider closing\n"
                "3. If CONCENTRATION WARNING: use reduce_long/reduce_short first to free capital\n"
                "4. If majority BEARISH + no position → 'short'\n"
                "5. If majority BULLISH + no position → 'buy'\n"
                "6. If position exists + signal agrees → hold or add\n"
                "7. quantity=0 only for hold/cancel\n\n"
                "DAILY PROFIT FOCUS: Your goal is to END THE DAY PROFITABLE.\n"
                "- Lock in gains on winning positions\n"
                "- Cut losses quickly on losing positions\n"
                "- Diversify across multiple tickers\n"
                "- Consider time of day (less aggressive near close)\n\n"
                "JSON Format (include risk targets for new positions):\n"
                "{{\n"
                '  "decisions": {{\n'
                '    "AAPL": {{"action":"reduce_short","quantity":5,"confidence":70,"reasoning":"50%→25% to fund MSFT","rebalance_target":"MSFT","stop_loss_pct":null,"take_profit_pct":null}},\n'
                '    "MSFT": {{"action":"short","quantity":3,"confidence":65,"reasoning":"bearish thesis","rebalance_target":null,"stop_loss_pct":5.0,"take_profit_pct":10.0}}\n'
                "  }}\n"
                "}}"
            ),
        ]
    )

    prompt_data = {
        "historical_context": historical_context,
        "portfolio_context": position_context,
        "signals": json.dumps(compact_signals, indent=2, ensure_ascii=False),
        "allowed": json.dumps(compact_allowed, indent=2, ensure_ascii=False),
        "mazo_research": mazo_section,
    }
    prompt = template.invoke(prompt_data)

    # Default factory fills remaining tickers as hold if the LLM fails
    def create_default_portfolio_output():
        # start from prefilled
        decisions = dict(prefilled_decisions)
        for t in tickers_for_llm:
            decisions[t] = PortfolioDecision(
                action="hold", quantity=0, confidence=0.0, reasoning="Default decision: hold"
            )
        return PortfolioManagerOutput(decisions=decisions)

    # Track start time for PM decision latency
    pm_start_time = time.time()
    
    llm_out = call_llm(
        prompt=prompt,
        pydantic_model=PortfolioManagerOutput,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_portfolio_output,
    )
    
    pm_latency_ms = int((time.time() - pm_start_time) * 1000)
    
    # Log PM decision to monitoring system
    _log_pm_decisions(
        tickers=tickers_for_llm,
        signals_by_ticker=signals_by_ticker,
        llm_out=llm_out,
        mazo_research=mazo_research,
        portfolio=portfolio,
        state=state,
        latency_ms=pm_latency_ms,
    )

    # CRITICAL FIX: Validate and convert decisions immediately after call_llm returns
    # Pydantic's with_structured_output can create a model with invalid data types
    # (e.g., decisions as a list instead of dict[str, PortfolioDecision]).
    # We must validate and convert BEFORE any serialization occurs.
    validated_decisions = {}
    
    if isinstance(llm_out.decisions, list):
        # Convert list to dict - assume list items are dicts with ticker keys
        for item in llm_out.decisions:
            if isinstance(item, dict):
                ticker = item.get("ticker") or item.get("TICKER")
                if ticker:
                    try:
                        validated_decisions[ticker] = PortfolioDecision(**item)
                    except Exception:
                        validated_decisions[ticker] = PortfolioDecision(
                            action="hold", quantity=0, confidence=50, reasoning="Validation error"
                        )
    elif isinstance(llm_out.decisions, dict):
        # Validate each decision value
        for ticker, decision in llm_out.decisions.items():
            if isinstance(decision, list):
                if len(decision) > 0 and isinstance(decision[0], dict):
                    try:
                        validated_decisions[ticker] = PortfolioDecision(**decision[0])
                    except Exception:
                        validated_decisions[ticker] = PortfolioDecision(
                            action="hold", quantity=0, confidence=50, reasoning="List conversion error"
                        )
                else:
                    validated_decisions[ticker] = PortfolioDecision(
                        action="hold", quantity=0, confidence=50, reasoning="Invalid list format"
                    )
            elif isinstance(decision, dict) and not isinstance(decision, PortfolioDecision):
                try:
                    validated_decisions[ticker] = PortfolioDecision(**decision)
                except Exception:
                    validated_decisions[ticker] = PortfolioDecision(
                        action="hold", quantity=0, confidence=50, reasoning="Validation error"
                    )
            elif isinstance(decision, PortfolioDecision):
                validated_decisions[ticker] = decision
            else:
                validated_decisions[ticker] = PortfolioDecision(
                    action="hold", quantity=0, confidence=50, reasoning="Invalid decision type"
                )
    else:
        validated_decisions = dict(prefilled_decisions)

    # Merge prefilled holds with validated LLM results
    merged = dict(prefilled_decisions)
    merged.update(validated_decisions)
    return PortfolioManagerOutput(decisions=merged)


def _log_pm_decisions(
    tickers: list[str],
    signals_by_ticker: dict[str, dict],
    llm_out: PortfolioManagerOutput,
    mazo_research: str,
    portfolio: dict,
    state: AgentState,
    latency_ms: int,
):
    """Log PM decisions to monitoring system with full transparency."""
    event_logger = _get_event_logger()
    if not event_logger:
        return
    
    # Extract workflow_id from state if available
    workflow_id = state.get("metadata", {}).get("workflow_id")
    if not workflow_id:
        workflow_id = uuid.uuid4()
    
    # Extract Mazo sentiment if available
    mazo_sentiment = None
    mazo_received = mazo_research is not None and len(mazo_research.strip()) > 0
    if mazo_received:
        mazo_lower = mazo_research.lower()
        if "bullish" in mazo_lower or "positive" in mazo_lower or "buy" in mazo_lower:
            mazo_sentiment = "bullish"
        elif "bearish" in mazo_lower or "negative" in mazo_lower or "sell" in mazo_lower:
            mazo_sentiment = "bearish"
        else:
            mazo_sentiment = "neutral"
    
    # Log decision for each ticker
    for ticker in tickers:
        decision = llm_out.decisions.get(ticker)
        if not decision:
            continue
        
        ticker_signals = signals_by_ticker.get(ticker, {})
        
        # Count bullish/bearish/neutral signals
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        
        agents_received = {}
        for agent_name, signal_data in ticker_signals.items():
            sig = signal_data.get("sig", "").lower()
            conf = signal_data.get("conf", 0)
            reasoning = signal_data.get("reasoning", "")
            
            agents_received[agent_name] = {
                "signal": sig,
                "confidence": conf,
            }
            
            # Log individual agent signal
            try:
                event_logger.log_agent_signal(
                    workflow_id=workflow_id,
                    agent_id=agent_name,
                    ticker=ticker,
                    signal=sig if sig else "neutral",
                    confidence=conf,
                    reasoning=reasoning[:500] if reasoning else None,
                )
            except Exception:
                pass  # Don't fail PM logging if agent signal logging fails
            
            if "bullish" in sig or "buy" in sig or "long" in sig:
                bullish_count += 1
            elif "bearish" in sig or "sell" in sig or "short" in sig:
                bearish_count += 1
            else:
                neutral_count += 1
        
        # Determine consensus
        if bullish_count > bearish_count:
            consensus_direction = "bullish"
        elif bearish_count > bullish_count:
            consensus_direction = "bearish"
        else:
            consensus_direction = "neutral"
        
        # Calculate consensus score (0-100)
        total_signals = bullish_count + bearish_count + neutral_count
        if total_signals > 0:
            consensus_score = max(bullish_count, bearish_count) / total_signals * 100
        else:
            consensus_score = 0
        
        # Determine if PM action matches consensus
        action = decision.action if isinstance(decision, PortfolioDecision) else decision.get("action", "hold")
        action_is_bullish = action in ["buy", "cover", "reduce_short"]
        action_is_bearish = action in ["sell", "short", "reduce_long"]
        
        if action == "hold" or action == "cancel":
            action_matches_consensus = True  # Neutral actions always "match"
        elif consensus_direction == "bullish":
            action_matches_consensus = action_is_bullish
        elif consensus_direction == "bearish":
            action_matches_consensus = action_is_bearish
        else:
            action_matches_consensus = True  # Neutral consensus matches anything
        
        # Determine if PM followed Mazo
        mazo_considered = mazo_received
        if mazo_received and mazo_sentiment:
            mazo_is_bullish = mazo_sentiment == "bullish"
            mazo_is_bearish = mazo_sentiment == "bearish"
            
            if mazo_is_bullish and action_is_bullish:
                pm_followed_mazo = True
            elif mazo_is_bearish and action_is_bearish:
                pm_followed_mazo = True
            elif mazo_sentiment == "neutral" and action == "hold":
                pm_followed_mazo = True
            else:
                pm_followed_mazo = False
        else:
            pm_followed_mazo = None
        
        # Get portfolio context
        portfolio_equity = float(portfolio.get("equity", 0))
        portfolio_cash = float(portfolio.get("cash", 0))
        positions = portfolio.get("positions", {})
        existing_qty = 0
        if ticker in positions:
            pos = positions[ticker]
            existing_qty = float(pos.get("long", 0) or 0) - float(pos.get("short", 0) or 0)
        
        # Extract decision fields
        if isinstance(decision, PortfolioDecision):
            quantity = decision.quantity
            stop_loss_pct = decision.stop_loss_pct
            take_profit_pct = decision.take_profit_pct
            confidence = decision.confidence
            reasoning_raw = decision.reasoning
        else:
            quantity = decision.get("quantity", 0)
            stop_loss_pct = decision.get("stop_loss_pct")
            take_profit_pct = decision.get("take_profit_pct")
            confidence = decision.get("confidence", 0)
            reasoning_raw = decision.get("reasoning", "")
        
        # Log to monitoring
        try:
            event_logger.log_pm_decision(
                workflow_id=workflow_id,
                ticker=ticker,
                action=action,
                quantity=quantity,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                agents_received=agents_received,
                bullish_count=bullish_count,
                bearish_count=bearish_count,
                neutral_count=neutral_count,
                consensus_direction=consensus_direction,
                consensus_score=consensus_score,
                mazo_received=mazo_received,
                mazo_considered=mazo_considered,
                mazo_sentiment=mazo_sentiment,
                mazo_bypass_reason=None if mazo_received else "not_available",
                action_matches_consensus=action_matches_consensus,
                override_reason=reasoning_raw if not action_matches_consensus else None,
                reasoning_raw=reasoning_raw,
                confidence=confidence,
                portfolio_equity=portfolio_equity,
                portfolio_cash=portfolio_cash,
                latency_ms=latency_ms,
            )
        except Exception as e:
            # Don't let logging errors break trading
            pass
