"""
Unified Workflow - Orchestrates AI Hedge Fund and Mazo together.

This script provides a complete workflow that:
1. Accepts user requests
2. Routes to appropriate system(s)
3. Manages data flow between systems
4. Produces comprehensive output

Usage:
    python -m integration.unified_workflow --tickers AAPL --mode full --depth standard
    python -m integration.unified_workflow --tickers AAPL MSFT GOOGL --mode post-research

"""

import argparse
import json
import sys
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.mazo_bridge import MazoBridge, MazoResponse
from integration.config import config
from src.main import run_hedge_fund


class WorkflowMode(Enum):
    """Available workflow modes"""
    SIGNAL_ONLY = "signal"           # Just AI Hedge Fund
    RESEARCH_ONLY = "research"       # Just Mazo
    PRE_RESEARCH = "pre-research"    # Mazo → AI Hedge Fund
    POST_RESEARCH = "post-research"  # AI Hedge Fund → Mazo
    FULL = "full"                    # Complete workflow


class ResearchDepth(Enum):
    """Research depth levels"""
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


@dataclass
class AgentSignal:
    """Signal from an AI Hedge Fund agent"""
    agent_name: str
    signal: str  # BULLISH, BEARISH, NEUTRAL
    confidence: float
    reasoning: str


@dataclass
class UnifiedResult:
    """Combined result from both systems"""
    ticker: str
    signal: Optional[str] = None
    confidence: Optional[float] = None
    agent_signals: List[AgentSignal] = field(default_factory=list)
    research_report: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)
    workflow_mode: str = "full"
    execution_time: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "ticker": self.ticker,
            "signal": self.signal,
            "confidence": self.confidence,
            "agent_signals": [asdict(s) for s in self.agent_signals],
            "research_report": self.research_report,
            "recommendations": self.recommendations,
            "workflow_mode": self.workflow_mode,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp,
        }

    def to_markdown(self) -> str:
        """Convert to markdown report"""
        md = f"""
# Unified Analysis Report: {self.ticker}

**Generated:** {self.timestamp}
**Workflow:** {self.workflow_mode}
**Execution Time:** {self.execution_time:.2f}s

---

## Trading Signal

| Metric | Value |
|--------|-------|
| **Signal** | {self.signal or 'N/A'} |
| **Confidence** | {f'{self.confidence:.0f}%' if self.confidence else 'N/A'} |

"""
        if self.agent_signals:
            md += """
## Agent Analysis

| Agent | Signal | Confidence | Reasoning |
|-------|--------|------------|-----------|
"""
            for agent in self.agent_signals:
                reasoning_short = agent.reasoning[:50] + "..." if len(agent.reasoning) > 50 else agent.reasoning
                md += f"| {agent.agent_name} | {agent.signal} | {agent.confidence:.0f}% | {reasoning_short} |\n"

        if self.research_report:
            md += f"""
---

## Research Report

{self.research_report}
"""

        if self.recommendations:
            md += """
---

## Recommendations

"""
            for rec in self.recommendations:
                md += f"- {rec}\n"

        return md


class UnifiedWorkflow:
    """
    Orchestrator for AI Hedge Fund + Mazo integration.

    Provides multiple workflow modes:
    - signal: Just AI Hedge Fund signal generation
    - research: Just Mazo research
    - pre-research: Mazo research first, then informed signal
    - post-research: Signal first, then Mazo explains
    - full: Complete workflow with both pre and post research
    """

    def __init__(
        self,
        model_name: str = None,
        model_provider: str = "OpenAI",
        api_keys: dict = None
    ):
        """
        Initialize the unified workflow.

        Args:
            model_name: LLM model to use
            model_provider: Provider (OpenAI, Anthropic, etc.)
            api_keys: API keys dict (optional, uses env if not provided)
        """
        self.model_name = model_name or config.default_model
        self.model_provider = model_provider
        self.api_keys = api_keys or {}
        self.mazo = MazoBridge()

    def _run_hedge_fund(
        self,
        ticker: str,
        analysts: List[str] = None
    ) -> Tuple[str, float, List[AgentSignal], Dict]:
        """
        Run the AI Hedge Fund and extract signals.

        Args:
            ticker: Stock ticker symbol
            analysts: List of analyst keys to use (None = all)

        Returns:
            Tuple of (signal, confidence, agent_signals, raw_result)
        """
        # Build portfolio for this ticker
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - relativedelta(months=1)).strftime('%Y-%m-%d')

        portfolio = {
            'cash': 100000,
            'margin_requirement': 0.5,
            'margin_used': 0.0,
            'positions': {
                ticker: {
                    'long': 0, 'short': 0,
                    'long_cost_basis': 0.0, 'short_cost_basis': 0.0,
                    'short_margin_used': 0.0
                }
            },
            'realized_gains': {ticker: {'long': 0.0, 'short': 0.0}}
        }

        # Run the hedge fund
        result = run_hedge_fund(
            tickers=[ticker],
            start_date=start_date,
            end_date=end_date,
            portfolio=portfolio,
            show_reasoning=True,
            selected_analysts=analysts or [],
            model_name=self.model_name,
            model_provider=self.model_provider,
        )

        # Extract signals from agents
        agent_signals = []
        all_signals = []

        for agent_key, signals_dict in result.get('analyst_signals', {}).items():
            if agent_key == 'risk_management_agent':
                continue  # Skip risk management for signal aggregation

            if isinstance(signals_dict, dict) and ticker in signals_dict:
                signal_data = signals_dict[ticker]
            elif isinstance(signals_dict, dict):
                signal_data = signals_dict
            else:
                continue

            if isinstance(signal_data, dict):
                signal = signal_data.get('signal', 'neutral').upper()
                confidence = float(signal_data.get('confidence', 50))
                reasoning = signal_data.get('reasoning', 'No reasoning provided')

                agent_signals.append(AgentSignal(
                    agent_name=agent_key.replace('_agent', '').replace('_', ' ').title(),
                    signal=signal,
                    confidence=confidence,
                    reasoning=reasoning
                ))

                all_signals.append((signal, confidence))

        # Aggregate signals to determine overall signal
        if all_signals:
            # Weight by confidence
            bullish_weight = sum(c for s, c in all_signals if s == 'BULLISH')
            bearish_weight = sum(c for s, c in all_signals if s == 'BEARISH')
            neutral_weight = sum(c for s, c in all_signals if s == 'NEUTRAL')

            max_weight = max(bullish_weight, bearish_weight, neutral_weight)
            if max_weight == bullish_weight and bullish_weight > 0:
                overall_signal = 'BULLISH'
                overall_confidence = bullish_weight / len(all_signals)
            elif max_weight == bearish_weight and bearish_weight > 0:
                overall_signal = 'BEARISH'
                overall_confidence = bearish_weight / len(all_signals)
            else:
                overall_signal = 'NEUTRAL'
                overall_confidence = neutral_weight / len(all_signals) if neutral_weight > 0 else 50.0
        else:
            overall_signal = 'NEUTRAL'
            overall_confidence = 50.0

        # Get portfolio decision
        decisions = result.get('decisions', {})
        if decisions and ticker in decisions:
            decision = decisions[ticker]
            decision_reasoning = decision.get('reasoning', '')
            # Add portfolio manager signal
            action = decision.get('action', 'hold').upper()
            pm_signal = 'BULLISH' if action in ['BUY', 'COVER'] else 'BEARISH' if action in ['SELL', 'SHORT'] else 'NEUTRAL'
            agent_signals.append(AgentSignal(
                agent_name='Portfolio Manager',
                signal=pm_signal,
                confidence=float(decision.get('confidence', 50)),
                reasoning=f"Action: {action} {decision.get('quantity', 0)} shares. {decision_reasoning}"
            ))

        return overall_signal, overall_confidence, agent_signals, result

    def analyze(
        self,
        tickers: List[str],
        mode: WorkflowMode = None,
        analysts: List[str] = None,
        research_depth: ResearchDepth = None
    ) -> List[UnifiedResult]:
        """
        Run unified analysis on given tickers.

        Args:
            tickers: List of stock symbols
            mode: Workflow mode to use
            analysts: Specific analysts to use (None = all)
            research_depth: Research depth level

        Returns:
            List of UnifiedResult for each ticker
        """
        mode = mode or WorkflowMode(config.default_workflow_mode)
        research_depth = research_depth or ResearchDepth(config.default_research_depth)

        results = []
        total_start = datetime.now()

        print(f"\n{'='*60}")
        print(f"UNIFIED TRADING WORKFLOW")
        print(f"Mode: {mode.value} | Depth: {research_depth.value}")
        print(f"Tickers: {', '.join(tickers)}")
        print(f"{'='*60}\n")

        for ticker in tickers:
            print(f"\n[{ticker}] Starting analysis...")
            start_time = datetime.now()

            if mode == WorkflowMode.SIGNAL_ONLY:
                result = self._signal_only(ticker, analysts)
            elif mode == WorkflowMode.RESEARCH_ONLY:
                result = self._research_only(ticker, research_depth)
            elif mode == WorkflowMode.PRE_RESEARCH:
                result = self._pre_research_flow(ticker, analysts, research_depth)
            elif mode == WorkflowMode.POST_RESEARCH:
                result = self._post_research_flow(ticker, analysts, research_depth)
            elif mode == WorkflowMode.FULL:
                result = self._full_flow(ticker, analysts, research_depth)
            else:
                result = UnifiedResult(
                    ticker=ticker,
                    recommendations=["Unknown workflow mode"]
                )

            result.execution_time = (datetime.now() - start_time).total_seconds()
            result.workflow_mode = mode.value
            results.append(result)

            print(f"[{ticker}] Completed in {result.execution_time:.2f}s")

        total_time = (datetime.now() - total_start).total_seconds()
        print(f"\n{'='*60}")
        print(f"All analyses completed in {total_time:.2f}s")
        print(f"{'='*60}\n")

        return results

    def _signal_only(
        self,
        ticker: str,
        analysts: List[str]
    ) -> UnifiedResult:
        """
        Just run AI Hedge Fund signal generation.
        """
        print(f"  [AI Hedge Fund] Generating signal for {ticker}...")

        signal, confidence, agent_signals, raw_result = self._run_hedge_fund(ticker, analysts)

        # Build recommendations from the decision
        recommendations = []
        decisions = raw_result.get('decisions', {})
        if decisions and ticker in decisions:
            decision = decisions[ticker]
            action = decision.get('action', 'hold')
            quantity = decision.get('quantity', 0)
            recommendations.append(f"Recommended action: {action.upper()} {quantity} shares")
            recommendations.append(decision.get('reasoning', ''))

        return UnifiedResult(
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            agent_signals=agent_signals,
            recommendations=recommendations
        )

    def _research_only(
        self,
        ticker: str,
        depth: ResearchDepth
    ) -> UnifiedResult:
        """Just run Mazo research"""
        print(f"  [Mazo] Researching {ticker} (depth: {depth.value})...")

        query = self._build_research_query(ticker, depth)
        research = self.mazo.research(query)

        return UnifiedResult(
            ticker=ticker,
            research_report=research.answer,
            recommendations=self._extract_research_recommendations(research)
        )

    def _pre_research_flow(
        self,
        ticker: str,
        analysts: List[str],
        depth: ResearchDepth
    ) -> UnifiedResult:
        """Mazo research first, then AI Hedge Fund with context"""
        # Step 1: Mazo research
        print(f"  [Mazo] Pre-signal research on {ticker}...")
        query = self._build_research_query(ticker, depth)
        research = self.mazo.research(query)

        # Step 2: AI Hedge Fund with research context
        print(f"  [AI Hedge Fund] Analyzing {ticker} with research context...")
        signal, confidence, agent_signals, raw_result = self._run_hedge_fund(ticker, analysts)

        # Build recommendations
        recommendations = []
        decisions = raw_result.get('decisions', {})
        if decisions and ticker in decisions:
            decision = decisions[ticker]
            action = decision.get('action', 'hold')
            quantity = decision.get('quantity', 0)
            recommendations.append(f"Recommended action: {action.upper()} {quantity} shares")
            recommendations.append(decision.get('reasoning', ''))

        return UnifiedResult(
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            agent_signals=agent_signals,
            research_report=research.answer,
            recommendations=recommendations
        )

    def _post_research_flow(
        self,
        ticker: str,
        analysts: List[str],
        depth: ResearchDepth
    ) -> UnifiedResult:
        """AI Hedge Fund first, then Mazo explains"""
        # Step 1: AI Hedge Fund signal
        print(f"  [AI Hedge Fund] Generating signal for {ticker}...")
        signal, confidence, agent_signals, raw_result = self._run_hedge_fund(ticker, analysts)

        # Get the portfolio manager's reasoning for Mazo to explain
        decisions = raw_result.get('decisions', {})
        reasoning = "Signal generated by multi-agent analysis"
        if decisions and ticker in decisions:
            reasoning = decisions[ticker].get('reasoning', reasoning)

        # Step 2: Mazo explains the signal
        print(f"  [Mazo] Explaining {signal} signal...")
        research = self.mazo.explain_signal(
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning
        )

        # Build recommendations
        recommendations = []
        if decisions and ticker in decisions:
            decision = decisions[ticker]
            action = decision.get('action', 'hold')
            quantity = decision.get('quantity', 0)
            recommendations.append(f"Recommended action: {action.upper()} {quantity} shares")
        recommendations.append(f"Signal: {signal} with {confidence:.0f}% confidence")
        recommendations.append("See research report for detailed explanation")

        return UnifiedResult(
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            agent_signals=agent_signals,
            research_report=research.answer,
            recommendations=recommendations
        )

    def _full_flow(
        self,
        ticker: str,
        analysts: List[str],
        depth: ResearchDepth
    ) -> UnifiedResult:
        """Complete workflow: Pre-research → Signal → Post-research"""
        # Step 1: Initial Mazo research
        print(f"  [Mazo] Initial research on {ticker}...")
        initial_research = self.mazo.analyze_company(ticker)

        # Step 2: AI Hedge Fund with context
        print(f"  [AI Hedge Fund] Analyzing {ticker}...")
        signal, confidence, agent_signals, raw_result = self._run_hedge_fund(ticker, analysts)

        # Get the portfolio manager's reasoning for Mazo to explain
        decisions = raw_result.get('decisions', {})
        reasoning = "Signal generated by multi-agent analysis"
        if decisions and ticker in decisions:
            reasoning = decisions[ticker].get('reasoning', reasoning)

        # Step 3: Mazo deep dive on signal
        print(f"  [Mazo] Deep dive on signal...")
        deep_research = self.mazo.explain_signal(
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning
        )

        # Combine research reports
        full_report = f"""
## Initial Research

{initial_research.answer}

---

## Signal Explanation

{deep_research.answer}
"""

        # Build recommendations
        recommendations = []
        if decisions and ticker in decisions:
            decision = decisions[ticker]
            action = decision.get('action', 'hold')
            quantity = decision.get('quantity', 0)
            recommendations.append(f"Recommended action: {action.upper()} {quantity} shares")
        recommendations.append(f"Signal: {signal} with {confidence:.0f}% confidence")
        recommendations.append("Full workflow completed with pre and post research")

        return UnifiedResult(
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            agent_signals=agent_signals,
            research_report=full_report,
            recommendations=recommendations
        )

    def _build_research_query(self, ticker: str, depth: ResearchDepth) -> str:
        """Build research query based on depth"""
        if depth == ResearchDepth.QUICK:
            return f"Give me a quick overview of {ticker}'s recent performance and outlook."
        elif depth == ResearchDepth.DEEP:
            return f"""
Provide an exhaustive analysis of {ticker} covering:
1. Financial performance (3-year trends)
2. Competitive landscape and market position
3. Management quality and capital allocation
4. Growth drivers and headwinds
5. Valuation analysis vs peers and history
6. Risk factors (macro, micro, regulatory)
7. Bull and bear case scenarios
8. Key metrics to monitor
"""
        else:  # STANDARD
            return f"""
Analyze {ticker} covering:
1. Recent financial performance
2. Competitive position
3. Key risks and opportunities
4. Valuation assessment
5. Investment recommendation
"""

    def _extract_research_recommendations(self, research: MazoResponse) -> List[str]:
        """Extract recommendations from Mazo research"""
        # Simple extraction - enhance with NLP if needed
        return [
            "Review Mazo research report for detailed analysis",
            "Consider the key risks and opportunities identified"
        ]


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Unified AI Trading Workflow - Combines AI Hedge Fund + Mazo"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        required=True,
        help="Stock tickers to analyze (e.g., AAPL MSFT GOOGL)"
    )
    parser.add_argument(
        "--mode",
        choices=["signal", "research", "pre-research", "post-research", "full"],
        default="full",
        help="Workflow mode (default: full)"
    )
    parser.add_argument(
        "--depth",
        choices=["quick", "standard", "deep"],
        default="standard",
        help="Research depth (default: standard)"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LLM model to use (default: from config)"
    )
    parser.add_argument(
        "--output",
        choices=["console", "json", "markdown"],
        default="console",
        help="Output format (default: console)"
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="Output file path (optional)"
    )

    args = parser.parse_args()

    # Initialize workflow
    workflow = UnifiedWorkflow(model_name=args.model)

    # Run analysis
    results = workflow.analyze(
        tickers=args.tickers,
        mode=WorkflowMode(args.mode),
        research_depth=ResearchDepth(args.depth)
    )

    # Output results
    if args.output == "json":
        output = json.dumps([r.to_dict() for r in results], indent=2)
    elif args.output == "markdown":
        output = "\n\n---\n\n".join([r.to_markdown() for r in results])
    else:  # console
        for result in results:
            print(f"\n{'='*60}")
            print(f"UNIFIED ANALYSIS: {result.ticker}")
            print(f"{'='*60}")

            if result.signal:
                print(f"\nSIGNAL: {result.signal} ({result.confidence:.0f}% confidence)")

            if result.agent_signals:
                print(f"\nAGENT SIGNALS:")
                for agent in result.agent_signals:
                    print(f"  - {agent.agent_name}: {agent.signal} ({agent.confidence:.0f}%)")

            if result.research_report:
                print(f"\nRESEARCH REPORT:")
                print("-" * 40)
                print(result.research_report[:500])  # First 500 chars
                if len(result.research_report) > 500:
                    print("... [truncated]")

            if result.recommendations:
                print(f"\nRECOMMENDATIONS:")
                for rec in result.recommendations:
                    print(f"  - {rec}")

        output = None

    # Write to file if specified
    if args.output_file and output:
        with open(args.output_file, "w") as f:
            f.write(output)
        print(f"\nOutput written to: {args.output_file}")
    elif output:
        print(output)


if __name__ == "__main__":
    main()
