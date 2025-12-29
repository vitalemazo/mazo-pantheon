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
        """
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
        # Write temporary script
        script_path = Path(self.mazo_path) / "temp_query.ts"
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
                script_path.unlink()

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

    def analyze_company(self, ticker: str) -> MazoResponse:
        """
        Request comprehensive company analysis.

        Args:
            ticker: Stock ticker symbol

        Returns:
            MazoResponse with company analysis
        """
        query = f"""
Provide a comprehensive analysis of {ticker} including:
1. Recent financial performance and trends
2. Competitive position and moat analysis
3. Key risks and opportunities
4. Management quality and strategy
5. Valuation relative to peers and history
"""
        return self.research(query)

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
        reasoning: str
    ) -> MazoResponse:
        """
        Get Mazo to explain/expand on an AI Hedge Fund signal.

        Args:
            ticker: Stock ticker symbol
            signal: The signal (BULLISH/BEARISH/NEUTRAL)
            confidence: Confidence percentage
            reasoning: Brief reasoning from AI Hedge Fund

        Returns:
            MazoResponse with expanded analysis
        """
        query = f"""
AI Hedge Fund generated a {signal} signal on {ticker} with
{confidence}% confidence. The reasoning was:

"{reasoning}"

Please provide:
1. Deeper analysis of why this signal makes sense (or doesn't)
2. Key data points supporting this view
3. What could invalidate this thesis
4. Specific metrics/events to watch
5. Timeline considerations
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
