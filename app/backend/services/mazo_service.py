"""
Mazo Research Service - Backend service for Mazo research agent integration.

This service provides async methods to interact with the Mazo TypeScript agent
from the FastAPI backend.
"""

import asyncio
import json
import os
from typing import Optional, List, AsyncGenerator, Dict, Any
from pathlib import Path
from enum import Enum
from datetime import datetime


class ResearchDepth(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


# Research templates for common analysis types
RESEARCH_TEMPLATES = {
    "fundamental_analysis": {
        "name": "Fundamental Analysis",
        "description": "Deep dive into company financials and business model",
        "template": """Perform a comprehensive fundamental analysis of {ticker}:
1. Revenue and earnings growth trends (5-year)
2. Profit margins and efficiency ratios
3. Balance sheet strength (debt levels, liquidity)
4. Cash flow analysis
5. Valuation metrics (P/E, P/S, EV/EBITDA) vs peers
6. Management quality and capital allocation
7. Competitive moat assessment"""
    },
    "technical_analysis": {
        "name": "Technical Analysis",
        "description": "Chart patterns and price action analysis",
        "template": """Analyze the technical setup for {ticker}:
1. Current trend direction and strength
2. Key support and resistance levels
3. Moving average analysis (50, 100, 200 day)
4. Volume patterns and accumulation/distribution
5. RSI and momentum indicators
6. Recent chart patterns
7. Potential entry and exit points"""
    },
    "risk_assessment": {
        "name": "Risk Assessment",
        "description": "Identify key risks and potential downsides",
        "template": """Provide a comprehensive risk assessment for {ticker}:
1. Business model risks
2. Competitive threats
3. Regulatory and legal risks
4. Macroeconomic sensitivity
5. Key person dependencies
6. Financial leverage risks
7. ESG concerns
8. Worst-case scenario analysis"""
    },
    "growth_catalyst": {
        "name": "Growth Catalysts",
        "description": "Identify upcoming events that could move the stock",
        "template": """Identify growth catalysts and upcoming events for {ticker}:
1. Upcoming earnings and guidance expectations
2. New product launches or expansions
3. M&A potential (acquirer or target)
4. Industry tailwinds
5. Management initiatives
6. Analyst rating changes
7. Institutional buying patterns
8. Short interest and squeeze potential"""
    },
    "competitor_analysis": {
        "name": "Competitor Analysis",
        "description": "Compare against key competitors",
        "template": """Analyze {ticker} against its main competitors:
1. Identify top 3-5 competitors
2. Market share comparison
3. Growth rate comparison
4. Profitability comparison
5. Valuation comparison
6. Competitive advantages/disadvantages
7. Strategic positioning
8. Winner/loser assessment"""
    },
    "earnings_preview": {
        "name": "Earnings Preview",
        "description": "Pre-earnings analysis and expectations",
        "template": """Provide an earnings preview for {ticker}:
1. Consensus estimates (revenue, EPS)
2. Key metrics to watch
3. Guidance expectations
4. Historical beat/miss record
5. Options market implied move
6. Analyst sentiment changes
7. Risk/reward into earnings
8. Post-earnings trading strategy"""
    },
    "sector_overview": {
        "name": "Sector Overview",
        "description": "Analyze the sector/industry dynamics",
        "template": """Analyze the sector dynamics for {ticker}'s industry:
1. Industry growth outlook
2. Key sector trends
3. Regulatory environment
4. Competitive landscape
5. Supply chain dynamics
6. Top performers in sector
7. Sector rotation signals
8. Best positioned companies"""
    },
    "quick_summary": {
        "name": "Quick Summary",
        "description": "Fast 2-minute overview",
        "template": """Provide a quick 2-minute summary of {ticker}:
1. What the company does (1 sentence)
2. Bull case (3 bullets)
3. Bear case (3 bullets)
4. Current valuation assessment
5. Key number to watch
6. Buy/Hold/Sell recommendation"""
    }
}


class MazoService:
    """Service for interacting with the Mazo research agent."""

    def __init__(self, api_keys: Optional[Dict[str, Any]] = None):
        # Get absolute path to mazo directory (relative to this file's location)
        default_mazo_path = Path(__file__).parent.parent.parent.parent / "mazo"
        self.mazo_path = os.getenv("MAZO_PATH", str(default_mazo_path.resolve()))
        self.timeout = int(os.getenv("MAZO_TIMEOUT", "300"))
        self.api_keys = api_keys or {}

    def _get_env_with_api_keys(self) -> Dict[str, str]:
        """Get environment variables with API keys merged in."""
        env = {**os.environ}
        # Add API keys from database
        for key, value in self.api_keys.items():
            if value:
                env[key] = value
        # Ensure bun is in PATH
        home = os.path.expanduser("~")
        bun_path = os.path.join(home, ".bun", "bin")
        if bun_path not in env.get("PATH", ""):
            env["PATH"] = f"{bun_path}:{env.get('PATH', '')}"
        return env

    async def research(self, query: str, depth: ResearchDepth = ResearchDepth.STANDARD) -> dict:
        """
        Execute a research query using Mazo.

        Args:
            query: The research question to investigate
            depth: Research depth level (quick, standard, deep)

        Returns:
            Dict containing answer, confidence, and sources
        """
        return await self._run_mazo_query(query, depth)

    async def analyze_company(self, ticker: str, depth: ResearchDepth = ResearchDepth.STANDARD) -> dict:
        """
        Run comprehensive company analysis.

        Args:
            ticker: Stock ticker symbol
            depth: Analysis depth level

        Returns:
            Dict containing company analysis results
        """
        query = f"Provide a comprehensive analysis of {ticker} including: business model, competitive position, financial health, growth prospects, and key risks."
        return await self._run_mazo_query(query, depth)

    async def compare_companies(self, tickers: List[str], depth: ResearchDepth = ResearchDepth.STANDARD) -> dict:
        """
        Compare multiple companies.

        Args:
            tickers: List of stock ticker symbols to compare
            depth: Analysis depth level

        Returns:
            Dict containing comparison analysis
        """
        ticker_str = ", ".join(tickers)
        query = f"Compare the following companies: {ticker_str}. Analyze their relative strengths, weaknesses, valuations, and investment merits."
        return await self._run_mazo_query(query, depth)

    async def explain_signal(
        self,
        ticker: str,
        signal: str,
        confidence: float,
        reasoning: str
    ) -> dict:
        """
        Use Mazo to explain a trading signal.

        Args:
            ticker: Stock ticker symbol
            signal: The trading signal (BUY, SELL, HOLD)
            confidence: Confidence score (0-100)
            reasoning: Brief reasoning from the trading agent

        Returns:
            Dict containing detailed explanation
        """
        query = f"""The AI trading system generated a {signal} signal for {ticker} with {confidence}% confidence.

The brief reasoning was: {reasoning}

Please provide a detailed explanation of why this signal makes sense (or doesn't), including:
1. Current market context for {ticker}
2. Key fundamental factors supporting or contradicting this signal
3. Technical factors to consider
4. Potential risks and catalysts
5. Overall assessment of the signal quality"""

        return await self._run_mazo_query(query, ResearchDepth.STANDARD)

    async def pre_research(self, tickers: List[str], depth: ResearchDepth = ResearchDepth.STANDARD) -> dict:
        """
        Pre-workflow research to provide context for trading agents.

        Args:
            tickers: List of stock ticker symbols
            depth: Research depth level

        Returns:
            Dict containing research context for each ticker
        """
        results = {}
        for ticker in tickers:
            query = f"""Provide key context for analyzing {ticker} as a potential investment:
1. Recent news and developments
2. Current valuation metrics vs historical averages
3. Key upcoming events or catalysts
4. Market sentiment summary
5. Critical factors to watch"""

            result = await self._run_mazo_query(query, depth)
            results[ticker] = result

        return {"pre_research": results}

    async def batch_analyze(
        self,
        tickers: List[str],
        template_id: str = "quick_summary",
        depth: ResearchDepth = ResearchDepth.QUICK
    ) -> dict:
        """
        Analyze multiple tickers using a template.

        Args:
            tickers: List of stock ticker symbols
            template_id: Template to use for analysis
            depth: Research depth level

        Returns:
            Dict containing analysis for each ticker
        """
        template = RESEARCH_TEMPLATES.get(template_id)
        if not template:
            return {
                "success": False,
                "error": f"Template '{template_id}' not found",
                "results": {}
            }

        results = {}
        for ticker in tickers:
            query = template["template"].format(ticker=ticker)
            result = await self._run_mazo_query(query, depth)
            results[ticker] = {
                "template": template_id,
                "template_name": template["name"],
                **result
            }

        return {
            "success": True,
            "template_id": template_id,
            "template_name": template["name"],
            "results": results
        }

    async def research_with_template(
        self,
        ticker: str,
        template_id: str,
        depth: ResearchDepth = ResearchDepth.STANDARD
    ) -> dict:
        """
        Run research using a predefined template.

        Args:
            ticker: Stock ticker symbol
            template_id: ID of the template to use
            depth: Research depth level

        Returns:
            Dict containing research results
        """
        template = RESEARCH_TEMPLATES.get(template_id)
        if not template:
            return {
                "success": False,
                "error": f"Template '{template_id}' not found",
                "answer": None,
                "confidence": 0,
                "sources": []
            }

        query = template["template"].format(ticker=ticker)
        result = await self._run_mazo_query(query, depth)
        result["template_id"] = template_id
        result["template_name"] = template["name"]
        return result

    def get_templates(self) -> List[dict]:
        """
        Get all available research templates.

        Returns:
            List of template definitions
        """
        return [
            {
                "id": template_id,
                "name": template["name"],
                "description": template["description"]
            }
            for template_id, template in RESEARCH_TEMPLATES.items()
        ]

    async def research_stream(
        self,
        query: str,
        depth: ResearchDepth = ResearchDepth.STANDARD
    ) -> AsyncGenerator[dict, None]:
        """
        Stream research results as they become available.

        Args:
            query: The research question
            depth: Research depth level

        Yields:
            Dict events with type and data
        """
        try:
            # Send start event
            yield {
                "type": "start",
                "data": {
                    "query": query,
                    "depth": depth.value,
                    "timestamp": datetime.now().isoformat()
                }
            }

            # Build the command - use api.ts for non-interactive mode
            cmd = ["bun", "run", "src/api.ts", "--query", query]

            # Start the process with API keys from database
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.mazo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._get_env_with_api_keys()
            )

            # Send progress event
            yield {
                "type": "progress",
                "data": {
                    "status": "researching",
                    "message": "Mazo is analyzing your query..."
                }
            }

            # Read output
            stdout_data = b""
            try:
                while True:
                    chunk = await asyncio.wait_for(
                        process.stdout.read(1024),
                        timeout=5.0
                    )
                    if not chunk:
                        break
                    stdout_data += chunk

                    # Try to parse partial output for progress updates
                    partial_output = stdout_data.decode(errors='ignore')
                    if "Task" in partial_output or "Step" in partial_output:
                        yield {
                            "type": "progress",
                            "data": {
                                "status": "processing",
                                "message": "Processing research tasks..."
                            }
                        }
            except asyncio.TimeoutError:
                # Continue reading if timeout on chunk
                pass

            # Wait for process to complete
            await process.wait()

            # Get any remaining output
            remaining_stdout, stderr = await process.communicate()
            stdout_data += remaining_stdout

            output = stdout_data.decode()

            if process.returncode != 0:
                yield {
                    "type": "error",
                    "data": {
                        "message": stderr.decode() if stderr else "Research failed"
                    }
                }
                return

            # Parse result
            result = None
            try:
                json_start = output.find("{")
                json_end = output.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = output[json_start:json_end]
                    result = json.loads(json_str)
            except json.JSONDecodeError:
                result = {
                    "answer": output.strip(),
                    "confidence": 70,
                    "sources": []
                }

            # Send complete event
            yield {
                "type": "complete",
                "data": {
                    "success": True,
                    "answer": result.get("answer", output.strip()),
                    "confidence": result.get("confidence", 70),
                    "sources": result.get("sources", []),
                    "timestamp": datetime.now().isoformat()
                }
            }

        except Exception as e:
            yield {
                "type": "error",
                "data": {
                    "message": str(e)
                }
            }

    async def _run_mazo_query(self, query: str, depth: ResearchDepth) -> dict:
        """
        Internal method to execute a Mazo query.

        Args:
            query: The research query
            depth: Research depth level

        Returns:
            Dict containing the research results
        """
        try:
            # Build the command - use api.ts for non-interactive mode
            cmd = ["bun", "run", "src/api.ts", "--query", query]

            # Run the command asynchronously with API keys from database
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.mazo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._get_env_with_api_keys()
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "success": False,
                    "error": "Research query timed out",
                    "answer": None,
                    "confidence": 0,
                    "sources": []
                }

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                return {
                    "success": False,
                    "error": error_msg,
                    "answer": None,
                    "confidence": 0,
                    "sources": []
                }

            # Parse the output
            output = stdout.decode()

            # Try to extract JSON from the output
            try:
                # Look for JSON in the output
                json_start = output.find("{")
                json_end = output.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = output[json_start:json_end]
                    result = json.loads(json_str)
                    result["success"] = True
                    return result
            except json.JSONDecodeError:
                pass

            # If no JSON found, return the raw output
            return {
                "success": True,
                "answer": output.strip(),
                "confidence": 70,  # Default confidence for raw output
                "sources": []
            }

        except FileNotFoundError as e:
            # Log debug info
            import logging
            logging.error(f"Mazo FileNotFoundError: {e}")
            logging.error(f"Mazo path: {self.mazo_path}")
            logging.error(f"PATH: {self._get_env_with_api_keys().get('PATH', '')[:200]}")
            return {
                "success": False,
                "error": f"Mazo not found: {e}. Bun path: ~/.bun/bin/bun, Mazo path: {self.mazo_path}",
                "answer": None,
                "confidence": 0,
                "sources": []
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "answer": None,
                "confidence": 0,
                "sources": []
            }


def get_mazo_service(api_keys: Optional[Dict[str, Any]] = None) -> MazoService:
    """Get a Mazo service instance with the given API keys."""
    return MazoService(api_keys=api_keys)
