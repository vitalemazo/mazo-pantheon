"""
Unified Workflow API Route

Provides streaming API endpoint for the unified workflow that combines
AI Hedge Fund and Mazo with real-time progress updates.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path for integration imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.backend.database import get_db
from app.backend.models.events import StartEvent, ProgressUpdateEvent, ErrorEvent, CompleteEvent
from app.backend.services.api_key_service import ApiKeyService

# Import integration modules (these are at project root)
try:
    from integration.unified_workflow import UnifiedWorkflow, WorkflowMode, ResearchDepth
    from integration.config import config
    # execute_trades may not exist, import it separately if available
    try:
        from integration.unified_workflow import execute_trades
    except (ImportError, AttributeError):
        execute_trades = None
except ImportError:
    # Fallback if imports fail
    import importlib.util
    integration_path = project_root / "integration" / "unified_workflow.py"
    if integration_path.exists():
        spec = importlib.util.spec_from_file_location("unified_workflow", integration_path)
        unified_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(unified_module)
        UnifiedWorkflow = unified_module.UnifiedWorkflow
        WorkflowMode = unified_module.WorkflowMode
        ResearchDepth = unified_module.ResearchDepth
        execute_trades = getattr(unified_module, 'execute_trades', None)
        
        config_path = project_root / "integration" / "config.py"
        spec = importlib.util.spec_from_file_location("config", config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        config = config_module.config
    else:
        raise ImportError("Could not find integration modules")

import os

router = APIRouter(prefix="/unified-workflow", tags=["unified-workflow"])


class UnifiedWorkflowRequest(BaseModel):
    """Request model for unified workflow"""
    tickers: List[str]
    mode: str = "full"  # signal, research, pre-research, post-research, full
    depth: str = "standard"  # quick, standard, deep
    model_name: Optional[str] = None
    model_provider: str = "OpenAI"
    execute_trades: bool = False
    dry_run: bool = False
    force_refresh: bool = False  # Force fresh data, bypass cache
    api_keys: Optional[dict] = None


class WorkflowProgress:
    """Tracks workflow progress for streaming"""
    def __init__(self):
        self.queue = asyncio.Queue()
        self.current_step = None
        self.step_details = {}
    
    def update_step(self, step: str, details: dict = None):
        """Update current step"""
        self.current_step = step
        if details:
            self.step_details[step] = details
        # Convert details dict to JSON string for analysis field
        analysis_str = json.dumps(details) if details else None
        event = ProgressUpdateEvent(
            agent=step,
            ticker=None,
            status="running",
            timestamp=None,
            analysis=analysis_str
        )
        self.queue.put_nowait(event)
    
    def complete_step(self, step: str, result: dict = None):
        """Mark step as complete"""
        # Convert result dict to JSON string for analysis field
        analysis_str = json.dumps(result) if result else None
        event = ProgressUpdateEvent(
            agent=step,
            ticker=None,
            status="completed",
            timestamp=None,
            analysis=analysis_str
        )
        self.queue.put_nowait(event)


@router.post("/run")
async def run_unified_workflow(
    request_data: UnifiedWorkflowRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Run unified workflow with real-time streaming progress.
    
    Streams progress updates showing:
    - Data aggregation
    - AI Hedge Fund agent execution
    - Mazo research
    - Trade execution (if requested)
    """
    try:
        # Get API keys from database if not provided
        if not request_data.api_keys:
            api_key_service = ApiKeyService(db)
            request_data.api_keys = api_key_service.get_api_keys_dict()
        
        # Validate workflow mode
        try:
            workflow_mode = WorkflowMode(request_data.mode)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: {request_data.mode}. Must be one of: signal, research, pre-research, post-research, full"
            )
        
        # Validate research depth
        try:
            research_depth = ResearchDepth(request_data.depth)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid depth: {request_data.depth}. Must be one of: quick, standard, deep"
            )
        
        # Create progress tracker
        progress_tracker = WorkflowProgress()
        
        async def wait_for_disconnect():
            """Wait for client disconnect"""
            try:
                while True:
                    message = await request.receive()
                    if message["type"] == "http.disconnect":
                        return True
            except Exception:
                return True
        
        async def event_generator():
            """Generate SSE events for workflow execution"""
            disconnect_task = None
            workflow_future = None
            
            try:
                # Start disconnect detection
                disconnect_task = asyncio.create_task(wait_for_disconnect())
                
                # Send start event
                yield StartEvent().to_sse()
                
                # Update: Starting workflow
                progress_tracker.update_step("workflow_start", {
                    "tickers": request_data.tickers,
                    "mode": request_data.mode,
                    "depth": request_data.depth
                })
                
                # Create workflow instance
                workflow = UnifiedWorkflow(
                    model_name=request_data.model_name,
                    model_provider=request_data.model_provider,
                    api_keys=request_data.api_keys
                )
                
                # Track Mazo research by wrapping the workflow's mazo calls
                # IMPORTANT: Do this BEFORE running the workflow so all calls are tracked
                original_mazo_research = workflow.mazo.research
                original_mazo_analyze = workflow.mazo.analyze_company
                original_mazo_explain = workflow.mazo.explain_signal
                
                mazo_research_details = []
                
                def tracked_research(query: str):
                    """Track Mazo research with detailed information"""
                    start_time = time.time()
                    # Update the appropriate step based on mode
                    step_id = "mazo_research" if workflow_mode == WorkflowMode.RESEARCH_ONLY else "mazo_research_active"
                    progress_tracker.update_step(step_id, {
                        "status": "running",
                        "query": query,
                        "ticker": request_data.tickers[0] if request_data.tickers else "N/A",
                        "depth": request_data.depth
                    })
                    
                    try:
                        result = original_mazo_research(query)
                        elapsed = (time.time() - start_time) * 1000
                        
                        detail = {
                            "query": query,
                            "ticker": request_data.tickers[0] if request_data.tickers else "N/A",
                            "depth": request_data.depth,
                            "method": "research",
                            "execution_time_ms": elapsed,
                            "success": result.success,
                            "answer_length": len(result.answer) if result.answer else 0,
                            "confidence": result.confidence,
                            "tasks_completed": result.tasks_completed,
                            "data_sources": result.data_sources,
                            "error": result.error,
                            "answer_preview": result.answer[:500] + "..." if result.answer and len(result.answer) > 500 else result.answer,
                            "timestamp": datetime.now().isoformat()
                        }
                        mazo_research_details.append(detail)
                        
                        progress_tracker.complete_step(step_id, {
                            "status": "complete",
                            "mazo_research": detail,
                            "summary": {
                                "execution_time_ms": elapsed,
                                "answer_length": len(result.answer) if result.answer else 0,
                                "success": result.success
                            }
                        })
                        return result
                    except Exception as e:
                        elapsed = (time.time() - start_time) * 1000
                        detail = {
                            "query": query,
                            "ticker": request_data.tickers[0] if request_data.tickers else "N/A",
                            "method": "research",
                            "execution_time_ms": elapsed,
                            "success": False,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                        mazo_research_details.append(detail)
                        progress_tracker.complete_step(step_id, {
                            "status": "error",
                            "mazo_research": detail,
                            "error": str(e)
                        })
                        raise
                
                def tracked_analyze_company(ticker: str):
                    """Track Mazo analyze_company with detailed information"""
                    start_time = time.time()
                    progress_tracker.update_step("mazo_initial_research", {
                        "status": "running",
                        "ticker": ticker,
                        "method": "analyze_company",
                        "message": f"Analyzing {ticker} with Mazo..."
                    })
                    
                    try:
                        result = original_mazo_analyze(ticker)
                        elapsed = (time.time() - start_time) * 1000
                        
                        detail = {
                            "ticker": ticker,
                            "method": "analyze_company",
                            "query": f"Comprehensive analysis of {ticker}",
                            "execution_time_ms": elapsed,
                            "success": result.success,
                            "answer_length": len(result.answer) if result.answer else 0,
                            "confidence": result.confidence,
                            "tasks_completed": result.tasks_completed,
                            "data_sources": result.data_sources,
                            "error": result.error,
                            "answer_preview": result.answer[:500] + "..." if result.answer and len(result.answer) > 500 else result.answer,
                            "timestamp": datetime.now().isoformat()
                        }
                        mazo_research_details.append(detail)
                        
                        progress_tracker.complete_step("mazo_initial_research", {
                            "status": "complete",
                            "mazo_research": detail,
                            "summary": {
                                "execution_time_ms": elapsed,
                                "answer_length": len(result.answer) if result.answer else 0,
                                "success": result.success
                            }
                        })
                        return result
                    except Exception as e:
                        elapsed = (time.time() - start_time) * 1000
                        detail = {
                            "ticker": ticker,
                            "method": "analyze_company",
                            "execution_time_ms": elapsed,
                            "success": False,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                        mazo_research_details.append(detail)
                        progress_tracker.complete_step("mazo_initial_research", {
                            "status": "error",
                            "mazo_research": detail,
                            "error": str(e)
                        })
                        raise
                
                def tracked_explain_signal(ticker: str, signal: str, confidence: float, reasoning: str):
                    """Track Mazo explain_signal with detailed information"""
                    start_time = time.time()
                    progress_tracker.update_step("mazo_deep_dive", {
                        "status": "running",
                        "ticker": ticker,
                        "signal": signal,
                        "confidence": confidence,
                        "method": "explain_signal",
                        "message": f"Explaining {signal} signal for {ticker}..."
                    })
                    
                    try:
                        result = original_mazo_explain(ticker, signal, confidence, reasoning)
                        elapsed = (time.time() - start_time) * 1000
                        
                        detail = {
                            "ticker": ticker,
                            "method": "explain_signal",
                            "signal": signal,
                            "confidence": confidence,
                            "reasoning": reasoning[:200] + "..." if reasoning and len(reasoning) > 200 else reasoning,
                            "query": f"Explain {signal} signal for {ticker}",
                            "execution_time_ms": elapsed,
                            "success": result.success,
                            "answer_length": len(result.answer) if result.answer else 0,
                            "confidence": result.confidence,
                            "tasks_completed": result.tasks_completed,
                            "data_sources": result.data_sources,
                            "error": result.error,
                            "answer_preview": result.answer[:500] + "..." if result.answer and len(result.answer) > 500 else result.answer,
                            "timestamp": datetime.now().isoformat()
                        }
                        mazo_research_details.append(detail)
                        
                        progress_tracker.complete_step("mazo_deep_dive", {
                            "status": "complete",
                            "mazo_research": detail,
                            "summary": {
                                "execution_time_ms": elapsed,
                                "answer_length": len(result.answer) if result.answer else 0,
                                "success": result.success
                            }
                        })
                        return result
                    except Exception as e:
                        elapsed = (time.time() - start_time) * 1000
                        detail = {
                            "ticker": ticker,
                            "method": "explain_signal",
                            "execution_time_ms": elapsed,
                            "success": False,
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                        mazo_research_details.append(detail)
                        progress_tracker.complete_step("mazo_deep_dive", {
                            "status": "error",
                            "mazo_research": detail,
                            "error": str(e)
                        })
                        raise
                
                # Replace Mazo methods with tracked versions
                workflow.mazo.research = tracked_research
                workflow.mazo.analyze_company = tracked_analyze_company
                workflow.mazo.explain_signal = tracked_explain_signal
                
                # Helper function to aggregate data with detailed tracking
                def aggregate_data_with_details(tickers, end_date, start_date, api_key, force_refresh: bool = False):
                    """Aggregate data and return detailed breakdown with cache tracking"""
                    from datetime import timedelta
                    from datetime import datetime as dt
                    import time
                    
                    detailed_results = {
                        "tickers": tickers,
                        "date_range": {"start": start_date or "auto", "end": end_date},
                        "data_retrievals": [],
                        "api_calls": [],
                        "cache_stats": {
                            "total_calls": 0,
                            "cache_hits": 0,
                            "cache_misses": 0,
                            "fresh_data_percent": 0
                        }
                    }
                    
                    for ticker in tickers:
                        ticker_data = {}
                        
                        # Financial Metrics
                        start_time = time.time()
                        try:
                            from src.tools.api import get_financial_metrics
                            metrics, cache_hit = get_financial_metrics(ticker, end_date, period="ttm", limit=10, api_key=api_key, force_refresh=force_refresh)
                            elapsed = (time.time() - start_time) * 1000
                            detailed_results["cache_stats"]["total_calls"] += 1
                            if cache_hit:
                                detailed_results["cache_stats"]["cache_hits"] += 1
                            else:
                                detailed_results["cache_stats"]["cache_misses"] += 1
                            
                            ticker_data["financial_metrics"] = {
                                "count": len(metrics),
                                "sample": [
                                    {
                                        "report_period": getattr(m, 'report_period', 'N/A'),
                                        "revenue": getattr(m, 'revenue', None),
                                        "net_income": getattr(m, 'net_income', None),
                                    }
                                    for m in metrics[:2]
                                ] if metrics else []
                            }
                            detailed_results["api_calls"].append({
                                "url": f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}",
                                "method": "GET",
                                "status_code": 200,
                                "response_time_ms": elapsed,
                                "cache_hit": cache_hit,
                                "data_fresh": not cache_hit
                            })
                            detailed_results["data_retrievals"].append({
                                "data_type": "financial_metrics",
                                "ticker": ticker,
                                "records_retrieved": len(metrics),
                                "details": ticker_data["financial_metrics"]
                            })
                        except Exception as e:
                            detailed_results["api_calls"].append({
                                "url": f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}",
                                "method": "GET",
                                "status_code": 500,
                                "error": str(e)
                            })
                        
                        # Prices
                        start_time = time.time()
                        try:
                            from src.tools.api import get_prices
                            prices, cache_hit = get_prices(ticker, start_date or (dt.fromisoformat(end_date) - timedelta(days=365)).date().isoformat(), end_date, api_key=api_key, force_refresh=force_refresh)
                            elapsed = (time.time() - start_time) * 1000
                            detailed_results["cache_stats"]["total_calls"] += 1
                            if cache_hit:
                                detailed_results["cache_stats"]["cache_hits"] += 1
                            else:
                                detailed_results["cache_stats"]["cache_misses"] += 1
                            
                            ticker_data["prices"] = {
                                "count": len(prices),
                                "date_range": {
                                    "first": getattr(prices[0], 'date', None) if prices else None,
                                    "last": getattr(prices[-1], 'date', None) if prices else None,
                                    "latest_price": getattr(prices[-1], 'close', None) if prices else None,
                                } if prices else None
                            }
                            detailed_results["api_calls"].append({
                                "url": f"https://api.financialdatasets.ai/prices/?ticker={ticker}",
                                "method": "GET",
                                "status_code": 200,
                                "response_time_ms": elapsed,
                                "cache_hit": cache_hit,
                                "data_fresh": not cache_hit
                            })
                            detailed_results["data_retrievals"].append({
                                "data_type": "prices",
                                "ticker": ticker,
                                "records_retrieved": len(prices),
                                "details": ticker_data["prices"]
                            })
                        except Exception as e:
                            pass
                        
                        # News
                        start_time = time.time()
                        try:
                            from src.tools.api import get_company_news
                            news, cache_hit = get_company_news(ticker, end_date=end_date, start_date=start_date, limit=250, api_key=api_key, force_refresh=force_refresh)
                            elapsed = (time.time() - start_time) * 1000
                            detailed_results["cache_stats"]["total_calls"] += 1
                            if cache_hit:
                                detailed_results["cache_stats"]["cache_hits"] += 1
                            else:
                                detailed_results["cache_stats"]["cache_misses"] += 1
                            
                            ticker_data["news"] = {
                                "count": len(news),
                                "sample_articles": [
                                    {
                                        "title": getattr(n, 'title', 'N/A')[:100],
                                        "date": getattr(n, 'published_date', None),
                                        "source": getattr(n, 'source', None),
                                    }
                                    for n in news[:3]
                                ] if news else []
                            }
                            detailed_results["api_calls"].append({
                                "url": f"https://api.financialdatasets.ai/news/?ticker={ticker}",
                                "method": "GET",
                                "status_code": 200,
                                "response_time_ms": elapsed,
                                "cache_hit": cache_hit,
                                "data_fresh": not cache_hit
                            })
                            detailed_results["data_retrievals"].append({
                                "data_type": "news",
                                "ticker": ticker,
                                "records_retrieved": len(news),
                                "details": ticker_data["news"]
                            })
                        except Exception as e:
                            pass
                        
                        # Insider Trades
                        start_time = time.time()
                        try:
                            from src.tools.api import get_insider_trades
                            trades, cache_hit = get_insider_trades(ticker, end_date=end_date, start_date=start_date, api_key=api_key, force_refresh=force_refresh)
                            elapsed = (time.time() - start_time) * 1000
                            detailed_results["cache_stats"]["total_calls"] += 1
                            if cache_hit:
                                detailed_results["cache_stats"]["cache_hits"] += 1
                            else:
                                detailed_results["cache_stats"]["cache_misses"] += 1
                            
                            ticker_data["insider_trades"] = {
                                "count": len(trades),
                                "sample_trades": [
                                    {
                                        "transaction_type": getattr(t, 'transaction_type', 'N/A'),
                                        "shares": getattr(t, 'shares', None),
                                        "filing_date": getattr(t, 'filing_date', None),
                                    }
                                    for t in trades[:3]
                                ] if trades else []
                            }
                            detailed_results["api_calls"].append({
                                "url": f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}",
                                "method": "GET",
                                "status_code": 200,
                                "response_time_ms": elapsed,
                                "cache_hit": cache_hit,
                                "data_fresh": not cache_hit
                            })
                            detailed_results["data_retrievals"].append({
                                "data_type": "insider_trades",
                                "ticker": ticker,
                                "records_retrieved": len(trades),
                                "details": ticker_data["insider_trades"]
                            })
                        except Exception as e:
                            pass
                    
                    # Calculate fresh data percentage
                    if detailed_results["cache_stats"]["total_calls"] > 0:
                        detailed_results["cache_stats"]["fresh_data_percent"] = round(
                            (detailed_results["cache_stats"]["cache_misses"] / detailed_results["cache_stats"]["total_calls"]) * 100, 
                            1
                        )
                    
                    return detailed_results
                
                # Run workflow in background (synchronous, but we'll wrap it)
                def run_workflow_sync():
                    """Run the workflow synchronously with detailed progress updates"""
                    import os
                    import time
                    from app.backend.repositories.api_key_repository import ApiKeyRepository
                    from app.backend.database.connection import SessionLocal
                    
                    # Helper to get AGGREGATE_DATA setting from DB or env
                    def get_aggregate_data_setting() -> bool:
                        """Check if AGGREGATE_DATA is enabled in DB or environment."""
                        # First check environment variable
                        env_value = os.getenv("AGGREGATE_DATA", "").lower()
                        if env_value in ("true", "false"):
                            # Also check database for override
                            try:
                                db = SessionLocal()
                                repo = ApiKeyRepository(db)
                                db_key = repo.get_api_key_by_provider("AGGREGATE_DATA")
                                db.close()
                                if db_key and db_key.key_value:
                                    return db_key.key_value.lower() == "true"
                            except Exception:
                                pass
                            return env_value == "true"
                        # Fallback to database only
                        try:
                            db = SessionLocal()
                            repo = ApiKeyRepository(db)
                            db_key = repo.get_api_key_by_provider("AGGREGATE_DATA")
                            db.close()
                            if db_key and db_key.key_value:
                                return db_key.key_value.lower() == "true"
                        except Exception:
                            pass
                        return False
                    
                    try:
                        # Step 1: Data Aggregation with DETAILED tracking
                        aggregate_data_enabled = get_aggregate_data_setting()
                        if aggregate_data_enabled:
                            progress_tracker.update_step("data_aggregation", {
                                "status": "fetching",
                                "tickers": request_data.tickers,
                                "message": "Starting detailed data aggregation..."
                            })
                            
                            # Get API key
                            api_key = request_data.api_keys.get("FINANCIAL_DATASETS_API_KEY") if request_data.api_keys else os.environ.get("FINANCIAL_DATASETS_API_KEY")
                            end_date = datetime.now().strftime('%Y-%m-%d')
                            
                            # Use force_refresh from request
                            force_refresh = request_data.force_refresh if hasattr(request_data, 'force_refresh') else False
                            
                            # Aggregate with detailed tracking
                            detailed_data = aggregate_data_with_details(
                                request_data.tickers,
                                end_date,
                                None,
                                api_key,
                                force_refresh=force_refresh
                            )
                            
                            # Send COMPLETE detailed information with cache stats
                            cache_stats = detailed_data.get("cache_stats", {})
                            progress_tracker.complete_step("data_aggregation", {
                                "status": "complete",
                                "summary": {
                                    "total_api_calls": len(detailed_data.get("api_calls", [])),
                                    "total_data_retrievals": len(detailed_data.get("data_retrievals", [])),
                                    "tickers_processed": len(request_data.tickers),
                                    "cache_hits": cache_stats.get("cache_hits", 0),
                                    "cache_misses": cache_stats.get("cache_misses", 0),
                                    "fresh_data_percent": cache_stats.get("fresh_data_percent", 0),
                                    "data_freshness": "Fresh" if cache_stats.get("fresh_data_percent", 0) >= 50 else "Partially Cached" if cache_stats.get("fresh_data_percent", 0) > 0 else "All Cached"
                                },
                                "data_retrievals": detailed_data.get("data_retrievals", []),
                                "api_calls": detailed_data.get("api_calls", []),
                                "cache_stats": cache_stats,
                                "detailed_breakdown": detailed_data
                            })
                        
                        # Step 2: Execute workflow based on mode
                        # Send initial status updates for AI Hedge Fund steps
                        # NOTE: For FULL and PRE_RESEARCH modes, AI Hedge Fund runs AFTER Mazo Initial Research,
                        # so we don't send the update here - it will be sent after Mazo completes.
                        # For SIGNAL_ONLY and POST_RESEARCH, AI Hedge Fund runs first, so we send the update now.
                        if workflow_mode == WorkflowMode.SIGNAL_ONLY:
                            progress_tracker.update_step("ai_hedge_fund", {
                                "status": "running",
                                "agents": 18,
                                "message": "Starting AI Hedge Fund analysis...",
                                "start_time": time.time()
                            })
                            progress_tracker.update_step("agents", {
                                "status": "running",
                                "count": 18,
                                "message": "Processing with 18 specialized agents..."
                            })
                        elif workflow_mode == WorkflowMode.POST_RESEARCH:
                            # POST_RESEARCH: AI Hedge Fund runs first, then Mazo explains
                            progress_tracker.update_step("ai_hedge_fund", {
                                "status": "running",
                                "agents": 18,
                                "message": "Starting AI Hedge Fund analysis...",
                                "start_time": time.time()
                            })
                            progress_tracker.update_step("agents", {
                                "status": "running",
                                "count": 18,
                                "message": "Processing with 18 specialized agents..."
                            })
                        # For FULL and PRE_RESEARCH modes, AI Hedge Fund status will be updated
                        # after Mazo Initial Research completes (handled in tracked_analyze_company completion)
                        
                        # Track Mazo research by wrapping the workflow's mazo calls
                        # IMPORTANT: Do this BEFORE running the workflow so all calls are tracked
                        # We'll intercept Mazo calls to capture detailed information
                        original_mazo_research = workflow.mazo.research
                        original_mazo_analyze = workflow.mazo.analyze_company
                        original_mazo_explain = workflow.mazo.explain_signal
                        
                        mazo_research_details = []
                        
                        def tracked_research(query: str):
                            """Track Mazo research with detailed information"""
                            start_time = time.time()
                            # Use the correct step ID based on mode
                            step_id = "mazo_research" if workflow_mode == WorkflowMode.RESEARCH_ONLY else "mazo_research_active"
                            progress_tracker.update_step(step_id, {
                                "status": "running",
                                "query": query,
                                "ticker": request_data.tickers[0] if request_data.tickers else "N/A",
                                "depth": request_data.depth,
                                "message": f"Executing Mazo research query..."
                            })
                            
                            try:
                                result = original_mazo_research(query)
                                elapsed = (time.time() - start_time) * 1000
                                
                                detail = {
                                    "query": query,
                                    "ticker": request_data.tickers[0] if request_data.tickers else "N/A",
                                    "depth": request_data.depth,
                                    "method": "research",
                                    "execution_time_ms": elapsed,
                                    "success": result.success,
                                    "answer_length": len(result.answer) if result.answer else 0,
                                    "confidence": result.confidence,
                                    "tasks_completed": result.tasks_completed,
                                    "data_sources": result.data_sources,
                                    "error": result.error,
                                    "answer": result.answer,  # Full answer - always include complete content for transparency
                                    "answer_preview": result.answer[:500] + "..." if result.answer and len(result.answer) > 500 else result.answer,  # Keep preview for quick reference, but full answer is primary
                                    "timestamp": datetime.now().isoformat()
                                }
                                mazo_research_details.append(detail)
                                
                                # Send completion with status explicitly set to "complete"
                                completion_data = {
                                    "status": "complete",  # Explicitly set to complete
                                    "mazo_research": detail,
                                    "summary": {
                                        "execution_time_ms": elapsed,
                                        "answer_length": len(result.answer) if result.answer else 0,
                                        "success": result.success
                                    }
                                }
                                progress_tracker.complete_step(step_id, completion_data)
                                return result
                            except Exception as e:
                                elapsed = (time.time() - start_time) * 1000
                                step_id = "mazo_research" if workflow_mode == WorkflowMode.RESEARCH_ONLY else "mazo_research_active"
                                detail = {
                                    "query": query,
                                    "ticker": request_data.tickers[0] if request_data.tickers else "N/A",
                                    "method": "research",
                                    "execution_time_ms": elapsed,
                                    "success": False,
                                    "error": str(e),
                                    "timestamp": datetime.now().isoformat()
                                }
                                mazo_research_details.append(detail)
                                progress_tracker.complete_step(step_id, {
                                    "status": "error",
                                    "mazo_research": detail,
                                    "error": str(e)
                                })
                                raise
                        
                        def tracked_analyze_company(ticker: str):
                            """Track Mazo analyze_company with detailed information"""
                            start_time = time.time()
                            progress_tracker.update_step("mazo_initial_research", {
                                "status": "running",
                                "ticker": ticker,
                                "method": "analyze_company"
                            })
                            
                            try:
                                result = original_mazo_analyze(ticker)
                                elapsed = (time.time() - start_time) * 1000
                                
                                detail = {
                                    "ticker": ticker,
                                    "method": "analyze_company",
                                    "query": f"Comprehensive analysis of {ticker}",
                                    "execution_time_ms": elapsed,
                                    "success": result.success,
                                    "answer_length": len(result.answer) if result.answer else 0,
                                    "confidence": result.confidence,
                                    "tasks_completed": result.tasks_completed,
                                    "data_sources": result.data_sources,
                                    "error": result.error,
                                    "answer": result.answer,  # Full answer
                                    "timestamp": datetime.now().isoformat()
                                }
                                mazo_research_details.append(detail)
                                
                                progress_tracker.complete_step("mazo_initial_research", {
                                    "status": "complete",
                                    "mazo_research": detail,
                                    "summary": {
                                        "execution_time_ms": elapsed,
                                        "answer_length": len(result.answer) if result.answer else 0,
                                        "success": result.success
                                    }
                                })
                                
                                # For FULL and PRE_RESEARCH modes, AI Hedge Fund runs after Mazo Initial Research
                                # Send the update now that Mazo Initial Research is complete
                                if workflow_mode in [WorkflowMode.FULL, WorkflowMode.PRE_RESEARCH]:
                                    progress_tracker.update_step("ai_hedge_fund", {
                                        "status": "running",
                                        "agents": 18,
                                        "message": "Starting AI Hedge Fund analysis after initial research...",
                                        "start_time": time.time()
                                    })
                                    progress_tracker.update_step("agents", {
                                        "status": "running",
                                        "count": 18,
                                        "message": "Processing with 18 specialized agents..."
                                    })
                                
                                return result
                            except Exception as e:
                                elapsed = (time.time() - start_time) * 1000
                                detail = {
                                    "ticker": ticker,
                                    "method": "analyze_company",
                                    "execution_time_ms": elapsed,
                                    "success": False,
                                    "error": str(e),
                                    "timestamp": datetime.now().isoformat()
                                }
                                mazo_research_details.append(detail)
                                progress_tracker.complete_step("mazo_initial_research", {
                                    "status": "error",
                                    "mazo_research": detail,
                                    "error": str(e)
                                })
                                raise
                        
                        def tracked_explain_signal(ticker: str, signal: str, confidence: float, reasoning: str):
                            """Track Mazo explain_signal with detailed information"""
                            start_time = time.time()
                            progress_tracker.update_step("mazo_deep_dive", {
                                "status": "running",
                                "ticker": ticker,
                                "signal": signal,
                                "confidence": confidence,
                                "method": "explain_signal"
                            })
                            
                            try:
                                result = original_mazo_explain(ticker, signal, confidence, reasoning)
                                elapsed = (time.time() - start_time) * 1000
                                
                                detail = {
                                    "ticker": ticker,
                                    "method": "explain_signal",
                                    "signal": signal,
                                    "confidence": confidence,
                                    "reasoning": reasoning,  # Full reasoning - no truncation for transparency
                                    "query": f"Explain {signal} signal for {ticker}",
                                    "execution_time_ms": elapsed,
                                    "success": result.success,
                                    "answer_length": len(result.answer) if result.answer else 0,
                                    "confidence": result.confidence,
                                    "tasks_completed": result.tasks_completed,
                                    "data_sources": result.data_sources,
                                    "error": result.error,
                                    "answer": result.answer,  # Full answer - always include complete content
                                    "timestamp": datetime.now().isoformat()
                                }
                                mazo_research_details.append(detail)
                                
                                progress_tracker.complete_step("mazo_deep_dive", {
                                    "status": "complete",
                                    "mazo_research": detail,
                                    "summary": {
                                        "execution_time_ms": elapsed,
                                        "answer_length": len(result.answer) if result.answer else 0,
                                        "success": result.success
                                    }
                                })
                                return result
                            except Exception as e:
                                elapsed = (time.time() - start_time) * 1000
                                detail = {
                                    "ticker": ticker,
                                    "method": "explain_signal",
                                    "execution_time_ms": elapsed,
                                    "success": False,
                                    "error": str(e),
                                    "timestamp": datetime.now().isoformat()
                                }
                                mazo_research_details.append(detail)
                                progress_tracker.complete_step("mazo_deep_dive", {
                                    "status": "error",
                                    "mazo_research": detail,
                                    "error": str(e)
                                })
                                raise
                        
                        # Replace Mazo methods with tracked versions
                        workflow.mazo.research = tracked_research
                        workflow.mazo.analyze_company = tracked_analyze_company
                        workflow.mazo.explain_signal = tracked_explain_signal
                        
                        # Run the actual workflow (this is synchronous)
                        # The workflow will print progress, but we'll track major steps
                        results = workflow.analyze(
                            tickers=request_data.tickers,
                            mode=workflow_mode,
                            research_depth=research_depth
                        )
                        
                        # Restore original methods
                        workflow.mazo.research = original_mazo_research
                        workflow.mazo.analyze_company = original_mazo_analyze
                        workflow.mazo.explain_signal = original_mazo_explain
                        
                        # Mark steps as complete with DETAILED information
                        if workflow_mode != WorkflowMode.RESEARCH_ONLY:
                            # Get step execution time - check both step_details and the update_step call
                            ai_hedge_fund_start = None
                            if "ai_hedge_fund" in progress_tracker.step_details:
                                ai_hedge_fund_start = progress_tracker.step_details["ai_hedge_fund"].get("start_time")
                            ai_hedge_fund_end = time.time()
                            execution_time_seconds = (ai_hedge_fund_end - ai_hedge_fund_start) if ai_hedge_fund_start else None
                            
                            # Capture agent execution details from results
                            agent_executions = []
                            agent_execution_times = []
                            successful_agents = 0
                            failed_agents = 0
                            
                            for result in results:
                                if result.agent_signals:
                                    for agent_signal in result.agent_signals:
                                        exec_time = getattr(agent_signal, 'execution_time_ms', None)
                                        if exec_time:
                                            agent_execution_times.append(exec_time)
                                        
                                        # Check if agent succeeded (has signal and confidence)
                                        if agent_signal.signal and agent_signal.confidence is not None:
                                            successful_agents += 1
                                        else:
                                            failed_agents += 1
                                        
                                        agent_executions.append({
                                            "agent_name": agent_signal.agent_name,
                                            "ticker": result.ticker,
                                            "signal": agent_signal.signal,
                                            "confidence": agent_signal.confidence,
                                            "reasoning": agent_signal.reasoning,  # Full reasoning - no truncation for transparency
                                            "timestamp": datetime.now().isoformat(),
                                            "execution_time_ms": exec_time
                                        })
                            
                            # Calculate summary statistics
                            total_agents = len(agent_executions)
                            signal_counts = {}
                            confidence_scores = []
                            agents_by_ticker = {}
                            
                            for exec in agent_executions:
                                signal = exec.get("signal", "UNKNOWN")
                                signal_counts[signal] = signal_counts.get(signal, 0) + 1
                                
                                if exec.get("confidence") is not None:
                                    confidence_scores.append(exec["confidence"])
                                
                                ticker = exec.get("ticker", "UNKNOWN")
                                if ticker not in agents_by_ticker:
                                    agents_by_ticker[ticker] = 0
                                agents_by_ticker[ticker] += 1
                            
                            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
                            min_confidence = min(confidence_scores) if confidence_scores else 0
                            max_confidence = max(confidence_scores) if confidence_scores else 0
                            
                            # Confidence distribution
                            high_confidence = len([c for c in confidence_scores if c >= 70])
                            medium_confidence = len([c for c in confidence_scores if 40 <= c < 70])
                            low_confidence = len([c for c in confidence_scores if c < 40])
                            
                            # Execution time metrics
                            avg_agent_time = sum(agent_execution_times) / len(agent_execution_times) if agent_execution_times else None
                            min_agent_time = min(agent_execution_times) if agent_execution_times else None
                            max_agent_time = max(agent_execution_times) if agent_execution_times else None
                            
                            # API usage estimation (rough estimates)
                            # Each agent typically uses ~500-2000 tokens (input + output)
                            estimated_tokens_per_agent = 1500  # Average estimate
                            total_estimated_tokens = total_agents * estimated_tokens_per_agent
                            # Rough cost estimate (using GPT-4 pricing as example)
                            input_cost_per_1k = 0.03
                            output_cost_per_1k = 0.06
                            estimated_input_tokens = int(total_estimated_tokens * 0.6)
                            estimated_output_tokens = int(total_estimated_tokens * 0.4)
                            estimated_cost = (estimated_input_tokens / 1000 * input_cost_per_1k) + (estimated_output_tokens / 1000 * output_cost_per_1k)
                            
                            # Data quality indicators (check if we have data for all tickers)
                            data_quality_warnings = []
                            if len(request_data.tickers) > 0:
                                tickers_with_data = len(set([exec.get("ticker") for exec in agent_executions]))
                                if tickers_with_data < len(request_data.tickers):
                                    data_quality_warnings.append(f"Missing data for {len(request_data.tickers) - tickers_with_data} ticker(s)")
                            
                            # Recommendations preview (top 3 from results)
                            top_recommendations = []
                            for result in results[:3]:  # Top 3 tickers
                                if result.recommendations and len(result.recommendations) > 0:
                                    top_recommendations.append({
                                        "ticker": result.ticker,
                                        "signal": result.signal,
                                        "confidence": result.confidence,
                                        "top_recommendation": result.recommendations[0] if result.recommendations else None
                                    })
                            
                            # Create rich summary
                            summary_data = {
                                "message": f"Processed {len(request_data.tickers)} ticker(s) with {total_agents} agent execution(s)",
                                "statistics": {
                                    "total_agents": total_agents,
                                    "tickers_processed": len(request_data.tickers),
                                    "agents_per_ticker": round(total_agents / len(request_data.tickers), 1) if len(request_data.tickers) > 0 else 0,
                                    "average_confidence": round(avg_confidence, 1),
                                    "signal_distribution": signal_counts,
                                    "agents_by_ticker": agents_by_ticker
                                },
                                "execution_time": {
                                    "total_seconds": round(execution_time_seconds, 2) if execution_time_seconds else None,
                                    "total_formatted": f"{execution_time_seconds:.1f}s" if execution_time_seconds else "N/A",
                                    "average_per_agent_ms": round(avg_agent_time, 0) if avg_agent_time else None,
                                    "fastest_agent_ms": round(min_agent_time, 0) if min_agent_time else None,
                                    "slowest_agent_ms": round(max_agent_time, 0) if max_agent_time else None
                                },
                                "confidence_distribution": {
                                    "min": round(min_confidence, 1),
                                    "max": round(max_confidence, 1),
                                    "average": round(avg_confidence, 1),
                                    "high_confidence_count": high_confidence,
                                    "medium_confidence_count": medium_confidence,
                                    "low_confidence_count": low_confidence,
                                    "high_confidence_threshold": 70,
                                    "medium_confidence_threshold": 40
                                },
                                "agent_performance": {
                                    "successful": successful_agents,
                                    "failed": failed_agents,
                                    "success_rate": round((successful_agents / total_agents * 100), 1) if total_agents > 0 else 0
                                },
                                "api_usage": {
                                    "estimated_total_tokens": total_estimated_tokens,
                                    "estimated_input_tokens": estimated_input_tokens,
                                    "estimated_output_tokens": estimated_output_tokens,
                                    "estimated_cost_usd": round(estimated_cost, 4),
                                    "note": "Estimates based on average token usage per agent"
                                },
                                "data_quality": {
                                    "warnings": data_quality_warnings,
                                    "tickers_with_data": len(set([exec.get("ticker") for exec in agent_executions])),
                                    "data_completeness_percent": round((len(set([exec.get("ticker") for exec in agent_executions])) / len(request_data.tickers) * 100), 1) if len(request_data.tickers) > 0 else 100
                                },
                                "recommendations_preview": top_recommendations
                            }
                            
                            progress_tracker.complete_step("ai_hedge_fund", {
                                "status": "complete",
                                "agents_completed": total_agents,
                                "agent_executions": agent_executions,
                                "summary": summary_data
                            })
                            progress_tracker.complete_step("agents", {
                                "status": "complete",
                                "agents_processed": 18,
                                "agent_executions": agent_executions,
                                "breakdown": {
                                    "total_agents": len(agent_executions),
                                    "by_ticker": {
                                        ticker: len([a for a in agent_executions if a["ticker"] == ticker])
                                        for ticker in request_data.tickers
                                    }
                                }
                            })
                            # Check if Mazo research was used by portfolio manager
                            # This is indicated by mazo_research in the state or in decision reasoning
                            mazo_research_used_in_decisions = []
                            mazo_research_provided_to_pm = False
                            
                            # Check if Mazo research was provided to portfolio manager
                            # In FULL and PRE_RESEARCH modes, initial research is provided
                            # In FULL mode, both initial and deep dive are available (but deep dive comes after PM decision)
                            if workflow_mode in [WorkflowMode.FULL, WorkflowMode.PRE_RESEARCH]:
                                mazo_research_provided_to_pm = True
                            
                            for r in results:
                                # Check if any agent signal from portfolio manager mentions Mazo
                                pm_signals = [s for s in (r.agent_signals or []) if s.agent_name == "Portfolio Manager"]
                                mazo_used = False
                                if pm_signals:
                                    pm_reasoning = pm_signals[0].reasoning or ""
                                    mazo_used = "Mazo" in pm_reasoning or "mazo" in pm_reasoning.lower() or "[Mazo research considered]" in pm_reasoning
                                
                                mazo_research_used_in_decisions.append({
                                    "ticker": r.ticker,
                                    "mazo_research_considered": mazo_used,
                                    "has_initial_research": workflow_mode in [WorkflowMode.FULL, WorkflowMode.PRE_RESEARCH],
                                    "has_deep_dive": workflow_mode in [WorkflowMode.FULL, WorkflowMode.POST_RESEARCH],
                                    "portfolio_manager_reasoning": pm_signals[0].reasoning if pm_signals else None
                                })
                            
                            progress_tracker.complete_step("portfolio_manager", {
                                "status": "complete",
                                "decisions": [
                                    {
                                        "ticker": r.ticker,
                                        "signal": r.signal,
                                        "confidence": r.confidence,
                                        "recommendations": r.recommendations[:3] if r.recommendations else [],
                                        "agent_count": len(r.agent_signals) if r.agent_signals else 0
                                    }
                                    for r in results
                                ],
                                "mazo_research_integration": {
                                    "mazo_research_provided": mazo_research_provided_to_pm,
                                    "decisions_with_mazo": mazo_research_used_in_decisions,
                                    "summary": f"Mazo research {'was' if any(d['mazo_research_considered'] for d in mazo_research_used_in_decisions) else 'was not'} explicitly considered in portfolio manager decisions",
                                    "integration_details": {
                                        "initial_research_provided": workflow_mode in [WorkflowMode.FULL, WorkflowMode.PRE_RESEARCH],
                                        "deep_dive_provided": workflow_mode in [WorkflowMode.FULL, WorkflowMode.POST_RESEARCH],
                                        "note": "Initial research is provided to portfolio manager before decision. Deep dive explains the decision after it's made."
                                    }
                                }
                            })
                        
                        # Mazo research steps are already tracked above via wrapped methods
                        # But we need to handle RESEARCH_ONLY mode specifically
                        if workflow_mode == WorkflowMode.RESEARCH_ONLY:
                            # In research-only mode, the research happens in _research_only
                            # which calls mazo.research() - already tracked above
                            if mazo_research_details:
                                progress_tracker.complete_step("mazo_research", {
                                    "status": "complete",
                                    "mazo_research": mazo_research_details[0] if mazo_research_details else None,
                                    "summary": {
                                        "execution_time_ms": mazo_research_details[0].get("execution_time_ms", 0) if mazo_research_details else 0,
                                        "answer_length": mazo_research_details[0].get("answer_length", 0) if mazo_research_details else 0,
                                        "success": mazo_research_details[0].get("success", False) if mazo_research_details else False
                                    }
                                })
                            else:
                                progress_tracker.complete_step("mazo_research", {
                                    "status": "complete",
                                    "note": "Research completed but details not captured"
                                })
                        
                        # Step 3: Trade Execution (if requested)
                        if request_data.execute_trades or request_data.dry_run:
                            progress_tracker.update_step("trade_execution", {
                                "status": "connecting",
                                "mode": "paper"  # Default to paper
                            })
                            
                            if execute_trades is not None:
                                try:
                                    results = execute_trades(results, dry_run=request_data.dry_run)
                                except Exception as e:
                                    progress_tracker.complete_step("trade_execution", {
                                        "status": "error",
                                        "error": str(e)
                                    })
                                    raise
                            else:
                                # Trade execution function not available
                                progress_tracker.complete_step("trade_execution", {
                                    "status": "error",
                                    "note": "Trade execution function not available"
                                })
                            
                            progress_tracker.complete_step("trade_execution", {
                                "status": "complete",
                                "trades_executed": sum(1 for r in results if r.trade and r.trade.executed),
                                "trades_failed": sum(1 for r in results if r.trade and r.trade.error),
                                "trades": [
                                    {
                                        "ticker": r.ticker,
                                        "action": r.trade.action if r.trade else None,
                                        "quantity": r.trade.quantity if r.trade else 0,
                                        "executed": r.trade.executed if r.trade else False,
                                        "order_id": r.trade.order_id if r.trade else None,
                                        "filled_price": r.trade.filled_price if r.trade else None,
                                        "error": r.trade.error if r.trade and r.trade.error else None
                                    }
                                    for r in results if r.trade
                                ],
                                "dry_run": request_data.dry_run
                            })
                        
                        return results
                        
                    except Exception as e:
                        progress_tracker.update_step("error", {
                            "message": str(e),
                            "type": type(e).__name__
                        })
                        raise
                
                # Run in executor to avoid blocking
                loop = asyncio.get_event_loop()
                
                # Start workflow in executor (returns a Future, not a coroutine)
                workflow_future = loop.run_in_executor(None, run_workflow_sync)
                
                # Stream progress updates
                while not workflow_future.done():
                    # Check for disconnect
                    if disconnect_task.done():
                        workflow_future.cancel()
                        try:
                            await workflow_future
                        except (asyncio.CancelledError, Exception):
                            pass
                        return
                    
                    # Get progress updates (non-blocking check)
                    events_sent = False
                    try:
                        # Check queue size first for better performance
                        queue_size = progress_tracker.queue.qsize()
                        for _ in range(queue_size):
                            try:
                                event = progress_tracker.queue.get_nowait()
                                yield event.to_sse()
                                events_sent = True
                            except asyncio.QueueEmpty:
                                break
                    except Exception:
                        # Queue operations can sometimes fail, just continue
                        pass
                    
                    # If we sent events, continue immediately to check for more
                    # Otherwise, wait a bit to avoid busy waiting
                    if not events_sent:
                        await asyncio.sleep(0.05)  # Reduced delay for more responsive updates
                
                # Flush any remaining progress updates before getting results
                # Do this multiple times to ensure all events are sent
                for flush_attempt in range(5):  # Try up to 5 times to flush queue
                    try:
                        queue_size = progress_tracker.queue.qsize()
                        if queue_size == 0:
                            break
                        for _ in range(queue_size):
                            try:
                                event = progress_tracker.queue.get_nowait()
                                yield event.to_sse()
                            except asyncio.QueueEmpty:
                                break
                        if flush_attempt < 4:  # Don't sleep on last attempt
                            await asyncio.sleep(0.02)  # Small delay to allow more events to queue
                    except Exception:
                        break
                
                # Get final results
                try:
                    results = await workflow_future
                except Exception as e:
                    yield ErrorEvent(message=f"Workflow failed: {str(e)}").to_sse()
                    return
                
                # Final flush of any progress updates queued during result processing
                for flush_attempt in range(5):
                    try:
                        queue_size = progress_tracker.queue.qsize()
                        if queue_size == 0:
                            break
                        for _ in range(queue_size):
                            try:
                                event = progress_tracker.queue.get_nowait()
                                yield event.to_sse()
                            except asyncio.QueueEmpty:
                                break
                        if flush_attempt < 4:
                            await asyncio.sleep(0.02)
                    except Exception:
                        break
                
                # Flush any progress updates that were queued during result processing
                try:
                    while not progress_tracker.queue.empty():
                        event = progress_tracker.queue.get_nowait()
                        yield event.to_sse()
                except asyncio.QueueEmpty:
                    pass
                
                # Send complete event with results
                # Safely convert results to dicts, handling edge cases
                results_dicts = []
                for r in results:
                    try:
                        if isinstance(r, list):
                            # If result is a list, take first element
                            if len(r) > 0:
                                r = r[0]
                            else:
                                continue
                        if hasattr(r, 'to_dict'):
                            results_dicts.append(r.to_dict())
                        elif isinstance(r, dict):
                            results_dicts.append(r)
                        else:
                            # Fallback: create basic dict
                            results_dicts.append({
                                "ticker": getattr(r, 'ticker', 'UNKNOWN'),
                                "signal": getattr(r, 'signal', None),
                                "confidence": getattr(r, 'confidence', None),
                                "error": f"Unable to serialize result: {type(r).__name__}"
                            })
                    except Exception as e:
                        print(f"  [Warning] Error serializing result: {e}")
                        results_dicts.append({
                            "ticker": "UNKNOWN",
                            "error": f"Serialization error: {str(e)}"
                        })
                
                complete_data = CompleteEvent(
                    data={
                        "results": results_dicts,
                        "workflow_mode": request_data.mode,
                        "tickers": request_data.tickers
                    }
                )
                yield complete_data.to_sse()
                
            except Exception as e:
                yield ErrorEvent(message=f"Error: {str(e)}").to_sse()
            finally:
                # Cleanup
                if workflow_future and not workflow_future.done():
                    workflow_future.cancel()
                    try:
                        await workflow_future
                    except (asyncio.CancelledError, Exception):
                        pass
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error running unified workflow: {str(e)}"
        )
