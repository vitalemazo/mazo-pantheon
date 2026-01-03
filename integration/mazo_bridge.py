"""
Mazo Bridge - Python wrapper for calling Mazo from AI Hedge Fund

This module provides a clean interface for AI Hedge Fund agents to
request research from Mazo (TypeScript/Bun application).

Communication Methods:
1. Subprocess: Run Mazo CLI commands and capture output
2. File-based: Write queries to files, Mazo processes them
3. HTTP API: If Mazo server is running (future enhancement)

"""

import subprocess
import json
import os
import tempfile
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum

from integration.config import config


class ResearchDepth(Enum):
    """Research depth levels"""
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


@dataclass
class MazoResponse:
    """Response from Mazo research query"""
    query: str
    answer: str
    tasks_completed: List[str] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    confidence: float = 0.8
    execution_time: float = 0.0
    raw_output: str = ""
    success: bool = True
    error: Optional[str] = None
    chart_url: Optional[str] = None  # TradingView chart snapshot URL
    chart_analysis: Optional[Dict[str, Any]] = None  # AI chart pattern analysis

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "query": self.query,
            "answer": self.answer,
            "tasks_completed": self.tasks_completed,
            "data_sources": self.data_sources,
            "confidence": self.confidence,
            "execution_time": self.execution_time,
            "success": self.success,
            "error": self.error,
            "chart_url": self.chart_url,
            "chart_analysis": self.chart_analysis,
        }

    def to_context_string(self) -> str:
        """Convert to string suitable for LLM context"""
        return f"""
=== MAZO RESEARCH REPORT ===
Query: {self.query}

{self.answer}

Confidence: {self.confidence * 100:.0f}%
Sources: {', '.join(self.data_sources) if self.data_sources else 'Financial Datasets API'}
==============================
"""


class MazoBridge:
    """
    Bridge to communicate with Mazo from Python.

    Mazo is a TypeScript/Bun application, so we communicate via:
    1. Subprocess calls (primary method)
    2. Shared file system (for complex queries)
    """

    def __init__(
        self,
        mazo_path: str = None,
        bun_path: str = None,
        timeout: int = None,
        model: str = None
    ):
        """
        Initialize the Mazo bridge.

        Args:
            mazo_path: Path to Mazo installation
            bun_path: Path to Bun executable
            timeout: Max seconds to wait for response
            model: LLM model for Mazo to use
        """
        self.mazo_path = mazo_path or config.mazo_path
        self.bun_path = bun_path or config.bun_path
        self.timeout = timeout or config.mazo_timeout
        self.model = model or config.default_model

        # Verify paths exist
        self._verify_installation()

    def _verify_installation(self) -> None:
        """Verify Mazo and Bun are installed"""
        if not Path(self.mazo_path).exists():
            raise FileNotFoundError(
                f"Mazo not found at {self.mazo_path}. "
                "Run from the mazo-hedge-fund directory."
            )

        if not Path(self.bun_path).exists():
            raise FileNotFoundError(
                f"Bun not found at {self.bun_path}. "
                "Install via: curl -fsSL https://bun.sh/install | bash"
            )

    def _run_mazo_query(self, query: str) -> subprocess.CompletedProcess:
        """
        Run a query through Mazo using a temporary script.

        Since Mazo is an interactive CLI, we create a script that
        sends the query and exits.
        
        Uses unique temp files (UUID-based) to avoid race conditions
        when multiple queries run concurrently.
        """
        import uuid
        
        # Create a temporary script to run the query
        query_script = f"""
import {{ research }} from './src/agents/research.ts';

const query = {json.dumps(query)};

async function main() {{
    try {{
        const result = await research(query);
        console.log(JSON.stringify(result));
    }} catch (error) {{
        console.error(JSON.stringify({{ error: error.message }}));
        process.exit(1);
    }}
}}

main();
"""
        # Write temporary script with unique filename to avoid race conditions
        unique_id = uuid.uuid4().hex[:12]
        script_path = Path(self.mazo_path) / f"temp_query_{unique_id}.ts"
        try:
            with open(script_path, "w") as f:
                f.write(query_script)

            # Run the script
            result = subprocess.run(
                [self.bun_path, "run", str(script_path)],
                cwd=self.mazo_path,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**os.environ, "FORCE_COLOR": "0"}  # Disable colors
            )
            return result

        finally:
            # Clean up temp script
            if script_path.exists():
                try:
                    script_path.unlink()
                except OSError:
                    pass  # Ignore if file was already deleted

    def research(self, query: str) -> MazoResponse:
        """
        Send a research query to Mazo via the API mode.

        Calls Mazo's api.ts which runs the agent non-interactively
        and returns JSON output.

        Args:
            query: Natural language research question

        Returns:
            MazoResponse with answer and metadata
        """
        start_time = time.time()

        try:
            # Call Mazo's API mode directly
            api_script = Path(self.mazo_path) / "src" / "api.ts"

            result = subprocess.run(
                [
                    self.bun_path, "run", str(api_script),
                    "--query", query,
                    "--model", self.model
                ],
                cwd=self.mazo_path,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**os.environ, "FORCE_COLOR": "0"}  # Disable colors
            )

            execution_time = time.time() - start_time

            # Parse JSON response from Mazo
            try:
                response_json = json.loads(result.stdout.strip())
            except json.JSONDecodeError:
                # If JSON parsing fails, check if there's useful output
                if result.stderr:
                    return MazoResponse(
                        query=query,
                        answer="",
                        success=False,
                        error=f"Mazo error: {result.stderr[:500]}",
                        execution_time=execution_time,
                        raw_output=result.stdout
                    )
                return MazoResponse(
                    query=query,
                    answer="",
                    success=False,
                    error=f"Failed to parse Mazo response: {result.stdout[:500]}",
                    execution_time=execution_time,
                    raw_output=result.stdout
                )

            # Map Mazo API response to MazoResponse
            if response_json.get("success"):
                return MazoResponse(
                    query=query,
                    answer=response_json.get("answer", ""),
                    tasks_completed=["Research complete"],
                    data_sources=response_json.get("sources", ["Financial Datasets API"]),
                    confidence=response_json.get("confidence", 85) / 100,
                    execution_time=execution_time,
                    raw_output=result.stdout,
                    success=True,
                    error=None
                )
            else:
                return MazoResponse(
                    query=query,
                    answer="",
                    success=False,
                    error=response_json.get("error", "Unknown error from Mazo"),
                    execution_time=execution_time,
                    raw_output=result.stdout
                )

        except subprocess.TimeoutExpired:
            return MazoResponse(
                query=query,
                answer="",
                success=False,
                error=f"Mazo timed out after {self.timeout}s",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return MazoResponse(
                query=query,
                answer="",
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )

    def _generate_placeholder_response(self, query: str) -> str:
        """
        Generate a placeholder response.

        Note: This is temporary until Mazo is modified to support
        non-interactive mode. Replace with actual Mazo output parsing.
        """
        return f"""
[Mazo Research Bridge - Placeholder Response]

Query: {query}

Status: Bridge connection established. Mazo is available at {self.mazo_path}.

To run actual Mazo research interactively:
  cd {self.mazo_path}
  {self.bun_path} start

Then enter your query: "{query}"

Note: Full non-interactive mode requires Mazo modifications.
See docs/MAZO_INTEGRATION.md for implementation details.
"""

    def analyze_company(
        self,
        ticker: str,
        portfolio_context: str = None
    ) -> MazoResponse:
        """
        Request comprehensive company analysis with portfolio context.

        Args:
            ticker: Stock ticker symbol
            portfolio_context: Optional portfolio context for position-aware analysis

        Returns:
            MazoResponse with company analysis
        """
        portfolio_section = ""
        if portfolio_context:
            portfolio_section = f"""
=== CURRENT PORTFOLIO CONTEXT ===
{portfolio_context}
=================================

Consider the above portfolio context when providing analysis.
If we already have a position, evaluate whether to add, hold, or reduce.

"""
        
        query = f"""{portfolio_section}Provide a comprehensive analysis of {ticker} including:
1. Recent financial performance and trends
2. Competitive position and moat analysis
3. Key risks and opportunities
4. Management quality and strategy
5. Valuation relative to peers and history
6. {"Given our current position, should we add, hold, or reduce exposure?" if portfolio_context else "Is this a good entry point?"}
"""
        response = self.research(query)

        # Optionally enrich with chart analysis
        if self._is_chart_vision_enabled():
            response = self.enrich_with_chart_analysis(response, ticker)

        # Optionally enrich with Danelfin AI scores
        response = self.enrich_with_danelfin(response, ticker)

        return response
    
    def _is_chart_vision_enabled(self) -> bool:
        """
        Check if chart vision analysis is enabled.
        Checks environment variable first, then database setting.
        """
        # Check environment variable first
        env_value = os.environ.get("ENABLE_CHART_VISION_ANALYSIS", "").lower()
        if env_value in ("true", "1", "yes"):
            return True
        if env_value in ("false", "0", "no"):
            return False
        
        # Check database setting
        try:
            from sqlalchemy import create_engine, text
            db_url = os.environ.get(
                "DATABASE_URL",
                "postgresql://mazo:mazo@mazo-postgres:5432/mazo_pantheon"
            )
            engine = create_engine(db_url)
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT key_value FROM api_keys WHERE provider = 'ENABLE_CHART_VISION_ANALYSIS' AND is_active = true")
                )
                row = result.fetchone()
                if row and row[0]:
                    return row[0].lower() in ("true", "1", "yes")
        except Exception:
            pass
        
        return False
    
    def enrich_with_chart_analysis(
        self,
        response: MazoResponse,
        ticker: str,
        interval: str = "1D",
    ) -> MazoResponse:
        """
        Enrich a Mazo research response with chart analysis.
        
        Args:
            response: Existing MazoResponse to enrich
            ticker: Stock ticker for chart generation
            interval: Chart timeframe
        
        Returns:
            MazoResponse with chart_url and chart_analysis added
        """
        try:
            from src.tools.chart_analysis import analyze_ticker_chart
            
            chart_result = analyze_ticker_chart(
                ticker=ticker,
                interval=interval,
                exchange="NASDAQ",  # TODO: detect exchange
                include_vision_analysis=True,
            )
            
            if not chart_result.error:
                response.chart_url = chart_result.chart_url
                response.chart_analysis = {
                    "patterns_detected": chart_result.patterns_detected,
                    "trend_direction": chart_result.trend_direction,
                    "key_levels": chart_result.key_levels,
                    "signal": chart_result.signal,
                    "confidence": chart_result.confidence,
                    "summary": chart_result.analysis_summary,
                }
                
                # Append chart analysis to the answer
                if chart_result.analysis_summary:
                    response.answer += f"\n\n=== CHART ANALYSIS ===\n"
                    response.answer += f"Chart URL: {chart_result.chart_url}\n"
                    response.answer += f"Trend: {chart_result.trend_direction}\n"
                    if chart_result.patterns_detected:
                        response.answer += f"Patterns: {', '.join(chart_result.patterns_detected)}\n"
                    response.answer += f"AI Signal: {chart_result.signal} ({chart_result.confidence*100:.0f}% confidence)\n"
                    response.answer += f"Summary: {chart_result.analysis_summary}\n"
                    response.data_sources.append("Chart-img (TradingView)")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Chart enrichment failed for {ticker}: {e}")
        
        return response

    def enrich_with_danelfin(
        self,
        response: MazoResponse,
        ticker: str,
    ) -> MazoResponse:
        """
        Enrich a Mazo research response with Danelfin AI scoring.

        Args:
            response: Existing MazoResponse to enrich
            ticker: Stock ticker for Danelfin lookup

        Returns:
            MazoResponse with Danelfin data added to answer
        """
        try:
            from src.tools.danelfin_api import get_score, is_danelfin_enabled, format_for_agent_prompt
            from src.trading.config import get_danelfin_config

            danelfin_config = get_danelfin_config()
            
            if not is_danelfin_enabled() or not danelfin_config.include_in_agent_prompts:
                return response
            
            danelfin_score = get_score(ticker)
            
            if danelfin_score.success:
                # Add Danelfin data to response
                if not hasattr(response, 'danelfin') or response.danelfin is None:
                    # Store in chart_analysis dict since MazoResponse doesn't have danelfin field
                    if response.chart_analysis is None:
                        response.chart_analysis = {}
                    response.chart_analysis["danelfin"] = danelfin_score.to_dict()
                
                # Append Danelfin scores to the answer
                response.answer += f"\n\n=== DANELFIN AI VALIDATION ===\n"
                response.answer += f"External AI Score: {danelfin_score.ai_score}/10 → {danelfin_score.signal.upper().replace('_', ' ')}\n"
                response.answer += f"Breakdown:\n"
                response.answer += f"  • Technical: {danelfin_score.technical}/10\n"
                response.answer += f"  • Fundamental: {danelfin_score.fundamental}/10\n"
                response.answer += f"  • Sentiment: {danelfin_score.sentiment}/10\n"
                response.answer += f"  • Low Risk: {danelfin_score.low_risk}/10\n"
                
                # Add track record if available
                if danelfin_score.buy_track_record:
                    response.answer += f"  • Has BUY Track Record ✓\n"
                if danelfin_score.sell_track_record:
                    response.answer += f"  • Has SELL Track Record ✓\n"
                
                response.data_sources.append("Danelfin AI")
                
        except ImportError:
            pass  # Danelfin not available
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Danelfin enrichment skipped for {ticker}: {e}")

        return response

    def compare_companies(self, tickers: List[str]) -> MazoResponse:
        """
        Compare multiple companies.

        Args:
            tickers: List of stock ticker symbols

        Returns:
            MazoResponse with comparison analysis
        """
        tickers_str = ", ".join(tickers)
        query = f"""
Compare {tickers_str} across the following dimensions:
1. Revenue growth and profitability
2. Valuation metrics (P/E, P/S, EV/EBITDA)
3. Competitive advantages and moats
4. Risk profiles
5. Investment thesis for each
"""
        return self.research(query)

    def investigate_thesis(
        self,
        ticker: str,
        thesis: str,
        thesis_type: str = "bullish"
    ) -> MazoResponse:
        """
        Research a specific investment thesis.

        Args:
            ticker: Stock ticker symbol
            thesis: The investment thesis to investigate
            thesis_type: "bullish" or "bearish"

        Returns:
            MazoResponse with thesis investigation
        """
        query = f"""
Investigate this {thesis_type} thesis for {ticker}:

"{thesis}"

Please:
1. Find evidence supporting this thesis
2. Find evidence against this thesis
3. Identify key metrics to monitor
4. Assess probability of thesis playing out
5. Suggest trigger points for action
"""
        return self.research(query)

    def explain_signal(
        self,
        ticker: str,
        signal: str,
        confidence: float,
        reasoning: str,
        portfolio_context: str = None
    ) -> MazoResponse:
        """
        Get Mazo to explain/expand on an AI Hedge Fund signal with portfolio context.

        Args:
            ticker: Stock ticker symbol
            signal: The signal (BULLISH/BEARISH/NEUTRAL)
            confidence: Confidence percentage
            reasoning: Brief reasoning from AI Hedge Fund
            portfolio_context: Optional portfolio context for position-aware analysis

        Returns:
            MazoResponse with expanded analysis
        """
        portfolio_section = ""
        position_question = "6. Is this a good entry point?"
        
        if portfolio_context:
            portfolio_section = f"""
=== CURRENT PORTFOLIO CONTEXT ===
{portfolio_context}
=================================

"""
            position_question = """6. Given our current position:
   - Should we add to it, hold, or reduce exposure?
   - What's the optimal position size?
   - Are there any pending orders we should modify?"""
        
        query = f"""{portfolio_section}AI Hedge Fund generated a {signal} signal on {ticker} with
{confidence}% confidence. The reasoning was:

"{reasoning}"

Please provide:
1. Deeper analysis of why this signal makes sense (or doesn't)
2. Key data points supporting this view
3. What could invalidate this thesis
4. Specific metrics/events to watch
5. Timeline considerations
{position_question}
"""
        return self.research(query)

    def analyze_portfolio(
        self,
        portfolio_data: Dict[str, Any],
        positions: List[Dict[str, Any]],
        pending_orders: List[Dict[str, Any]] = None
    ) -> MazoResponse:
        """
        Analyze the entire portfolio for risks, opportunities, and health.
        
        This is a holistic analysis that looks at:
        - Overall portfolio composition and concentration
        - Correlation risks between positions
        - Individual position health
        - Rebalancing opportunities
        - Risk/reward assessment
        
        Args:
            portfolio_data: Portfolio summary (equity, cash, buying_power)
            positions: List of current positions with P&L
            pending_orders: Optional list of pending orders
            
        Returns:
            MazoResponse with portfolio health analysis
        """
        # Build position summary
        position_lines = []
        total_long_value = 0
        total_short_value = 0
        equity = float(portfolio_data.get("equity", 0))
        
        for pos in positions:
            ticker = pos.get("symbol", "???")
            qty = float(pos.get("qty", 0))
            market_value = float(pos.get("market_value", 0))
            unrealized_pl = float(pos.get("unrealized_pl", 0))
            unrealized_plpc = float(pos.get("unrealized_plpc", 0)) * 100
            avg_entry = float(pos.get("avg_entry_price", 0))
            current_price = float(pos.get("current_price", 0))
            
            concentration = (abs(market_value) / equity * 100) if equity > 0 else 0
            pl_sign = "+" if unrealized_pl >= 0 else ""
            side = "LONG" if qty > 0 else "SHORT"
            
            position_lines.append(
                f"  {ticker}: {side} {abs(qty):.0f} shares @ ${avg_entry:.2f} → ${current_price:.2f} "
                f"({pl_sign}{unrealized_plpc:.1f}%) | ${abs(market_value):,.0f} ({concentration:.1f}% of portfolio)"
            )
            
            if qty > 0:
                total_long_value += market_value
            else:
                total_short_value += abs(market_value)
        
        # Build pending orders summary
        order_lines = []
        if pending_orders:
            for order in pending_orders:
                order_lines.append(
                    f"  {order.get('symbol')}: {order.get('side', '?').upper()} "
                    f"{order.get('qty', '?')} shares ({order.get('status', 'unknown')})"
                )
        
        # Build the analysis query
        query = f"""
=== PORTFOLIO HEALTH CHECK REQUEST ===

PORTFOLIO SUMMARY:
  Total Equity: ${equity:,.2f}
  Cash: ${float(portfolio_data.get('cash', 0)):,.2f}
  Buying Power: ${float(portfolio_data.get('buying_power', 0)):,.2f}
  Long Exposure: ${total_long_value:,.2f} ({(total_long_value/equity*100) if equity > 0 else 0:.1f}%)
  Short Exposure: ${total_short_value:,.2f} ({(total_short_value/equity*100) if equity > 0 else 0:.1f}%)

CURRENT POSITIONS ({len(positions)}):
{chr(10).join(position_lines) if position_lines else '  No positions'}

PENDING ORDERS ({len(pending_orders) if pending_orders else 0}):
{chr(10).join(order_lines) if order_lines else '  No pending orders'}

=== ANALYSIS REQUESTED ===

Please provide a comprehensive portfolio health check:

1. CONCENTRATION RISK
   - Which positions are over-concentrated (>25% of portfolio)?
   - What is the recommended position sizing for each?
   - Are there any correlation risks (e.g., multiple tech shorts)?

2. POSITION-BY-POSITION ANALYSIS
   For each position, assess:
   - Is the thesis still valid?
   - Should we add, hold, or reduce?
   - What are the key risk factors?

3. REBALANCING RECOMMENDATIONS
   - Which positions should be trimmed?
   - Which positions could be added to?
   - What trades would improve portfolio balance?

4. PENDING ORDER REVIEW
   - Are the pending orders still aligned with current analysis?
   - Should any be cancelled or modified?

5. OVERALL PORTFOLIO HEALTH SCORE
   - Grade the portfolio (A/B/C/D/F)
   - Key strengths
   - Key weaknesses
   - Immediate action items (priority ordered)

6. RISK ASSESSMENT
   - Maximum drawdown potential in adverse scenario
   - Portfolio beta estimate
   - Recommended hedges or protective positions
"""
        return self.research(query)

    def get_agent_context(
        self,
        ticker: str,
        agent_type: str
    ) -> MazoResponse:
        """
        Get research context tailored for a specific AI Hedge Fund agent.

        Args:
            ticker: Stock ticker symbol
            agent_type: Type of agent (buffett, burry, wood, etc.)

        Returns:
            MazoResponse with agent-specific research
        """
        agent_queries = {
            "buffett": f"""
Analyze {ticker} from Warren Buffett's perspective:
1. What is the company's moat/competitive advantage?
2. How predictable are the earnings?
3. Is management owner-oriented?
4. What is the intrinsic value using owner earnings?
5. Is there a margin of safety at current prices?
""",
            "burry": f"""
Analyze {ticker} from Michael Burry's deep value perspective:
1. What hidden assets or value might the market be missing?
2. Are there any accounting red flags or concerns?
3. What is the downside risk scenario?
4. What is the liquidation value vs market cap?
5. Are insiders buying or selling?
""",
            "wood": f"""
Analyze {ticker} from Cathie Wood's innovation perspective:
1. What disruptive technology is the company building or using?
2. What is the total addressable market opportunity?
3. How is the company positioned in emerging trends?
4. What is the long-term growth potential (5+ years)?
5. How might this company transform its industry?
""",
            "graham": f"""
Analyze {ticker} from Ben Graham's value investing perspective:
1. What is the Graham Number for this stock?
2. What is the current ratio and quick ratio?
3. What is the debt-to-equity ratio?
4. Has the company paid dividends consistently?
5. What is the P/E ratio relative to growth?
""",
            "lynch": f"""
Analyze {ticker} from Peter Lynch's perspective:
1. What category is this company (slow grower, stalwart, fast grower, etc.)?
2. What is the PEG ratio?
3. Is this a company you can understand (circle of competence)?
4. What is the "story" for this stock?
5. Are there any "ten-bagger" characteristics?
"""
        }

        query = agent_queries.get(
            agent_type.lower(),
            f"Provide general investment research on {ticker}"
        )

        return self.research(query)


# Convenience functions

def mazo_research(query: str, **kwargs) -> MazoResponse:
    """Quick research query to Mazo"""
    bridge = MazoBridge(**kwargs)
    return bridge.research(query)


def analyze_company(ticker: str, **kwargs) -> MazoResponse:
    """Quick company analysis"""
    bridge = MazoBridge(**kwargs)
    return bridge.analyze_company(ticker)


def compare_companies(tickers: List[str], **kwargs) -> MazoResponse:
    """Quick company comparison"""
    bridge = MazoBridge(**kwargs)
    return bridge.compare_companies(tickers)


def analyze_portfolio(portfolio_data: Dict[str, Any], positions: List[Dict[str, Any]], pending_orders: List[Dict[str, Any]] = None, **kwargs) -> MazoResponse:
    """Portfolio health check analysis"""
    bridge = MazoBridge(**kwargs)
    return bridge.analyze_portfolio(portfolio_data, positions, pending_orders)
