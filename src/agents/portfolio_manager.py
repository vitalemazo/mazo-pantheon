import json
import time
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from src.graph.state import AgentState, show_agent_reasoning
from src.graph.portfolio_context import PortfolioContext
from pydantic import BaseModel, Field
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm


class PortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "short", "cover", "hold", "cancel"]
    quantity: int = Field(description="Number of shares to trade (0 for cancel/hold)")
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


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

        # HOLD: Always available
        actions["hold"] = 0
        
        # CANCEL: Available if there are pending orders
        if has_pending:
            actions["cancel"] = len(ticker_pending)  # Number of orders that can be cancelled

        allowed[ticker] = actions

    return allowed


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


def _build_position_context(portfolio: dict, tickers: list[str], current_prices: dict[str, float]) -> str:
    """Build a rich position context string for the LLM."""
    lines = []
    
    # Portfolio summary
    cash = float(portfolio.get("cash", 0))
    buying_power = float(portfolio.get("buying_power", cash))
    portfolio_value = float(portfolio.get("portfolio_value", cash))
    
    lines.append(f"Portfolio: ${portfolio_value:,.0f} total | ${cash:,.0f} cash | ${buying_power:,.0f} buying power")
    
    # Current positions
    positions = portfolio.get("positions", {})
    position_lines = []
    for ticker in tickers:
        pos = positions.get(ticker, {})
        long_shares = int(pos.get("long", 0) or 0)
        short_shares = int(pos.get("short", 0) or 0)
        
        if long_shares > 0:
            entry = float(pos.get("long_cost_basis", 0) or 0)
            current = float(current_prices.get(ticker, entry))
            pl = (current - entry) * long_shares if entry > 0 else 0
            pl_pct = ((current / entry) - 1) * 100 if entry > 0 else 0
            pl_sign = "+" if pl >= 0 else ""
            position_lines.append(f"  {ticker}: LONG {long_shares} shares @ ${entry:.2f} → ${current:.2f} ({pl_sign}{pl_pct:.1f}%)")
        elif short_shares > 0:
            entry = float(pos.get("short_cost_basis", 0) or 0)
            current = float(current_prices.get(ticker, entry))
            pl = (entry - current) * short_shares if entry > 0 else 0
            pl_pct = ((entry / current) - 1) * 100 if current > 0 else 0
            pl_sign = "+" if pl >= 0 else ""
            position_lines.append(f"  {ticker}: SHORT {short_shares} shares @ ${entry:.2f} → ${current:.2f} ({pl_sign}{pl_pct:.1f}%)")
        else:
            position_lines.append(f"  {ticker}: No position")
    
    if position_lines:
        lines.append("Positions:")
        lines.extend(position_lines)
    
    # Pending orders
    pending = portfolio.get("pending_orders", [])
    if pending:
        order_lines = [f"  {o['symbol']}: {o['side'].upper()} {o['qty']} shares ({o['status']})" for o in pending if o['symbol'] in tickers]
        if order_lines:
            lines.append("Pending Orders:")
            lines.extend(order_lines)
    
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
            "You are an intelligent portfolio manager making trading decisions in PAPER TRADING mode.\n\n"
            "PAPER TRADING STRATEGY (be more aggressive to learn from the market):\n"
            "1. If you have NO position and signals lean in any direction, TAKE A POSITION to test the thesis\n"
            "2. Don't be afraid to act on signals - this is paper money for learning\n"
            "3. If majority of analysts agree (even with moderate confidence), act on it\n"
            "4. Use reasonable position sizes (10-30% of buying power per trade)\n"
            "5. Only HOLD if signals are truly contradictory (roughly equal bullish vs bearish)\n"
            "6. If Mazo research disagrees with analysts, consider the counter-arguments before deciding\n"
            "7. CANCEL pending orders if new analysis contradicts them (e.g., pending SELL but new signals are bullish)\n\n"
            "AVAILABLE ACTIONS:\n"
            "- buy/sell: For long positions\n"
            "- short/cover: For short positions\n"
            "- hold: Keep current state, no action\n"
            "- cancel: CANCEL all pending orders for this ticker (use when analysis changed since order was placed)\n\n"
            "GOAL: Generate trades to validate signals. Being wrong with paper money teaches more than doing nothing.\n\n"
            "Inputs: analyst signals, current positions, Mazo research (if any), and allowed actions with max qty.\n"
            "Pick one action per ticker. Quantity must be ≤ max shown (0 for cancel/hold).\n"
            "Keep reasoning concise (max 150 chars). Return JSON only."
        )
    else:
        system_prompt = (
            "You are an intelligent portfolio manager making trading decisions with REAL MONEY.\n\n"
            "IMPORTANT CONSIDERATIONS:\n"
            "1. Consider existing positions - don't double-down on losing trades without strong conviction\n"
            "2. If you have a profitable position, consider taking profits or letting it ride based on signals\n"
            "3. Check for pending orders - if new analysis contradicts them, CANCEL them\n"
            "4. Consider position sizing relative to portfolio value\n"
            "5. If signals are mixed or low confidence, prefer HOLD to avoid overtrading\n"
            "6. If Mazo research disagrees with analysts, carefully weigh the counter-arguments\n\n"
            "AVAILABLE ACTIONS:\n"
            "- buy/sell: For long positions\n"
            "- short/cover: For short positions\n"
            "- hold: Keep current state, no action\n"
            "- cancel: CANCEL all pending orders for this ticker (use when analysis changed since order was placed)\n\n"
            "Inputs: analyst signals, current positions, Mazo research (if any), and allowed actions with max qty.\n"
            "Pick one action per ticker. Quantity must be ≤ max shown (0 for cancel/hold).\n"
            "Keep reasoning concise (max 150 chars). Return JSON only."
        )
    
    # Enhanced prompt with portfolio awareness and Mazo research
    template = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "human",
                "=== PORTFOLIO STATE ===\n{portfolio_context}\n\n"
                "=== ANALYST SIGNALS ===\n{signals}\n\n"
                "{mazo_research}"
                "=== ALLOWED ACTIONS (max qty validated) ===\n{allowed}\n\n"
                "Format:\n"
                "{{\n"
                '  "decisions": {{\n'
                '    "TICKER": {{"action":"buy|sell|short|cover|hold|cancel","quantity":int,"confidence":0-100,"reasoning":"..."}}\n'
                "  }}\n"
                "}}"
            ),
        ]
    )

    prompt_data = {
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

    llm_out = call_llm(
        prompt=prompt,
        pydantic_model=PortfolioManagerOutput,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_portfolio_output,
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
