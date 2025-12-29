"""
Mazo Research API Routes

Provides REST endpoints for interacting with the Mazo research agent.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
import json

from app.backend.services.mazo_service import get_mazo_service, ResearchDepth, RESEARCH_TEMPLATES
from app.backend.services.api_key_service import ApiKeyService
from app.backend.database import get_db


router = APIRouter(prefix="/mazo")


def get_api_keys(db: Session) -> Dict[str, str]:
    """Get API keys from the database."""
    api_key_service = ApiKeyService(db)
    return api_key_service.get_api_keys_dict()


# Request/Response Models

class ResearchRequest(BaseModel):
    """Request for a research query."""
    query: str = Field(..., min_length=1, description="The research question to investigate")
    depth: ResearchDepth = Field(default=ResearchDepth.STANDARD, description="Research depth level")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "What are the key growth drivers for NVIDIA in the AI chip market?",
                    "depth": "standard"
                },
                {
                    "query": "Why did Tesla stock drop 10% last week? What were the main catalysts?",
                    "depth": "deep"
                },
                {
                    "query": "What is Apple's current P/E ratio compared to its 5-year average?",
                    "depth": "quick"
                }
            ]
        }
    }


class CompanyAnalysisRequest(BaseModel):
    """Request for company analysis."""
    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker symbol")
    depth: ResearchDepth = Field(default=ResearchDepth.STANDARD, description="Analysis depth level")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticker": "NVDA",
                    "depth": "deep"
                },
                {
                    "ticker": "AAPL",
                    "depth": "standard"
                },
                {
                    "ticker": "TSLA",
                    "depth": "quick"
                }
            ]
        }
    }


class CompareCompaniesRequest(BaseModel):
    """Request to compare multiple companies."""
    tickers: List[str] = Field(..., min_items=2, max_items=5, description="List of ticker symbols to compare")
    depth: ResearchDepth = Field(default=ResearchDepth.STANDARD, description="Analysis depth level")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tickers": ["NVDA", "AMD", "INTC"],
                    "depth": "standard"
                },
                {
                    "tickers": ["AAPL", "MSFT", "GOOGL", "META"],
                    "depth": "deep"
                },
                {
                    "tickers": ["TSLA", "RIVN"],
                    "depth": "quick"
                }
            ]
        }
    }


class ExplainSignalRequest(BaseModel):
    """Request to explain a trading signal."""
    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker symbol")
    signal: str = Field(..., description="Trading signal (BUY, SELL, HOLD)")
    confidence: float = Field(..., ge=0, le=100, description="Signal confidence score")
    reasoning: str = Field(..., description="Brief reasoning from the trading agent")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticker": "NVDA",
                    "signal": "BUY",
                    "confidence": 85.5,
                    "reasoning": "Strong AI demand, dominant market position in data center GPUs, and robust earnings growth trajectory"
                },
                {
                    "ticker": "AAPL",
                    "signal": "HOLD",
                    "confidence": 62.0,
                    "reasoning": "Stable cash flows but limited near-term catalysts, iPhone sales plateauing in key markets"
                },
                {
                    "ticker": "BYND",
                    "signal": "SELL",
                    "confidence": 78.0,
                    "reasoning": "Declining revenue, increasing competition, negative cash flow, and weakening consumer demand"
                }
            ]
        }
    }


class PreResearchRequest(BaseModel):
    """Request for pre-workflow research."""
    tickers: List[str] = Field(..., min_items=1, max_items=10, description="List of ticker symbols")
    depth: ResearchDepth = Field(default=ResearchDepth.STANDARD, description="Research depth level")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tickers": ["AAPL", "MSFT", "GOOGL"],
                    "depth": "standard"
                },
                {
                    "tickers": ["NVDA", "AMD", "INTC", "QCOM", "AVGO"],
                    "depth": "quick"
                }
            ]
        }
    }


class TemplateResearchRequest(BaseModel):
    """Request for template-based research."""
    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker symbol")
    template_id: str = Field(..., description="Template ID to use for research")
    depth: ResearchDepth = Field(default=ResearchDepth.STANDARD, description="Research depth level")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticker": "NVDA",
                    "template_id": "fundamental_analysis",
                    "depth": "deep"
                },
                {
                    "ticker": "TSLA",
                    "template_id": "risk_assessment",
                    "depth": "standard"
                },
                {
                    "ticker": "AAPL",
                    "template_id": "earnings_preview",
                    "depth": "standard"
                },
                {
                    "ticker": "META",
                    "template_id": "growth_catalyst",
                    "depth": "quick"
                }
            ]
        }
    }


class BatchAnalysisRequest(BaseModel):
    """Request for batch analysis of multiple tickers."""
    tickers: List[str] = Field(..., min_items=1, max_items=10, description="List of ticker symbols")
    template_id: str = Field(default="quick_summary", description="Template ID to use")
    depth: ResearchDepth = Field(default=ResearchDepth.QUICK, description="Research depth level")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
                    "template_id": "quick_summary",
                    "depth": "quick"
                },
                {
                    "tickers": ["NVDA", "AMD", "INTC"],
                    "template_id": "competitor_analysis",
                    "depth": "standard"
                },
                {
                    "tickers": ["JPM", "BAC", "WFC", "GS"],
                    "template_id": "fundamental_analysis",
                    "depth": "standard"
                }
            ]
        }
    }


class TemplateInfo(BaseModel):
    """Information about a research template."""
    id: str
    name: str
    description: str


class TemplateResponse(BaseModel):
    """Response containing available templates."""
    templates: List[TemplateInfo]


class ResearchResponse(BaseModel):
    """Response from a research query."""
    success: bool
    answer: Optional[str] = None
    confidence: float = 0
    sources: List[str] = []
    error: Optional[str] = None


# Endpoints

@router.post(
    "/research",
    response_model=ResearchResponse,
    responses={
        200: {"description": "Successful research response"},
        500: {"description": "Internal server error"},
    },
)
async def research(request: ResearchRequest, db: Session = Depends(get_db)):
    """
    Execute a research query using Mazo.

    This endpoint accepts natural language research questions and returns
    detailed analysis with confidence scores and sources.
    """
    try:
        api_keys = get_api_keys(db)
        service = get_mazo_service(api_keys)
        result = await service.research(request.query, request.depth)
        return ResearchResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research query failed: {str(e)}")


@router.post(
    "/analyze",
    response_model=ResearchResponse,
    responses={
        200: {"description": "Successful company analysis"},
        500: {"description": "Internal server error"},
    },
)
async def analyze_company(request: CompanyAnalysisRequest, db: Session = Depends(get_db)):
    """
    Run comprehensive company analysis.

    Provides detailed analysis including business model, competitive position,
    financial health, growth prospects, and key risks.
    """
    try:
        api_keys = get_api_keys(db)
        service = get_mazo_service(api_keys)
        result = await service.analyze_company(request.ticker, request.depth)
        return ResearchResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Company analysis failed: {str(e)}")


@router.post(
    "/compare",
    response_model=ResearchResponse,
    responses={
        200: {"description": "Successful company comparison"},
        500: {"description": "Internal server error"},
    },
)
async def compare_companies(request: CompareCompaniesRequest, db: Session = Depends(get_db)):
    """
    Compare multiple companies.

    Analyzes relative strengths, weaknesses, valuations, and investment merits
    of the specified companies.
    """
    try:
        api_keys = get_api_keys(db)
        service = get_mazo_service(api_keys)
        result = await service.compare_companies(request.tickers, request.depth)
        return ResearchResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Company comparison failed: {str(e)}")


@router.post(
    "/explain-signal",
    response_model=ResearchResponse,
    responses={
        200: {"description": "Successful signal explanation"},
        500: {"description": "Internal server error"},
    },
)
async def explain_signal(request: ExplainSignalRequest, db: Session = Depends(get_db)):
    """
    Explain a trading signal using Mazo research.

    Takes a trading signal generated by the AI Hedge Fund and provides
    detailed context and analysis explaining why the signal was generated.
    """
    try:
        api_keys = get_api_keys(db)
        service = get_mazo_service(api_keys)
        result = await service.explain_signal(
            request.ticker,
            request.signal,
            request.confidence,
            request.reasoning
        )
        return ResearchResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal explanation failed: {str(e)}")


@router.post(
    "/pre-research",
    responses={
        200: {"description": "Successful pre-workflow research"},
        500: {"description": "Internal server error"},
    },
)
async def pre_research(request: PreResearchRequest, db: Session = Depends(get_db)):
    """
    Run pre-workflow research for trading context.

    Gathers relevant context for each ticker before running the trading
    workflow, providing better-informed agent decisions.
    """
    try:
        api_keys = get_api_keys(db)
        service = get_mazo_service(api_keys)
        result = await service.pre_research(request.tickers, request.depth)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pre-research failed: {str(e)}")


@router.get(
    "/health",
    responses={
        200: {"description": "Mazo service health status"},
    },
)
async def health_check(db: Session = Depends(get_db)):
    """
    Check Mazo service health.

    Verifies that the Mazo agent is properly configured and accessible.
    """
    try:
        api_keys = get_api_keys(db)
        service = get_mazo_service(api_keys)
        # Quick test query
        result = await service.research("What is 2+2?", ResearchDepth.QUICK)
        return {
            "status": "healthy" if result.get("success") else "degraded",
            "mazo_path": service.mazo_path,
            "timeout": service.timeout,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@router.get(
    "/templates",
    response_model=TemplateResponse,
    responses={
        200: {"description": "List of available research templates"},
    },
)
async def list_templates():
    """
    Get all available research templates.

    Returns a list of predefined research templates that can be used
    for structured analysis of stocks.
    """
    service = get_mazo_service()
    templates = service.get_templates()
    return TemplateResponse(templates=[TemplateInfo(**t) for t in templates])


@router.post(
    "/research/template",
    response_model=ResearchResponse,
    responses={
        200: {"description": "Successful template-based research"},
        404: {"description": "Template not found"},
        500: {"description": "Internal server error"},
    },
)
async def research_with_template(request: TemplateResearchRequest, db: Session = Depends(get_db)):
    """
    Run research using a predefined template.

    Uses a structured template to perform specific types of analysis
    on a stock ticker.
    """
    if request.template_id not in RESEARCH_TEMPLATES:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{request.template_id}' not found. Use GET /mazo/templates to see available templates."
        )
    try:
        api_keys = get_api_keys(db)
        service = get_mazo_service(api_keys)
        result = await service.research_with_template(
            request.ticker,
            request.template_id,
            request.depth
        )
        return ResearchResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template research failed: {str(e)}")


@router.post(
    "/batch",
    responses={
        200: {"description": "Successful batch analysis"},
        404: {"description": "Template not found"},
        500: {"description": "Internal server error"},
    },
)
async def batch_analyze(request: BatchAnalysisRequest, db: Session = Depends(get_db)):
    """
    Analyze multiple tickers using a template.

    Performs batch analysis on multiple stock tickers using the same
    research template. Useful for screening or comparing companies.
    """
    if request.template_id not in RESEARCH_TEMPLATES:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{request.template_id}' not found. Use GET /mazo/templates to see available templates."
        )
    try:
        api_keys = get_api_keys(db)
        service = get_mazo_service(api_keys)
        result = await service.batch_analyze(
            request.tickers,
            request.template_id,
            request.depth
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")


async def generate_sse_events(query: str, depth: ResearchDepth, api_keys: Dict[str, str]):
    """Generator for SSE events from research stream."""
    service = get_mazo_service(api_keys)
    async for event in service.research_stream(query, depth):
        yield f"data: {json.dumps(event)}\n\n"


@router.post(
    "/research/stream",
    responses={
        200: {"description": "SSE stream of research progress and results"},
        500: {"description": "Internal server error"},
    },
)
async def research_stream(request: ResearchRequest, db: Session = Depends(get_db)):
    """
    Stream research results using Server-Sent Events (SSE).

    Provides real-time progress updates as Mazo processes the research
    query. Events include: start, progress, complete, error.

    Usage:
        const eventSource = new EventSource('/mazo/research/stream', {
            method: 'POST',
            body: JSON.stringify({ query: '...', depth: 'standard' })
        });
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(data.type, data.data);
        };
    """
    api_keys = get_api_keys(db)
    return StreamingResponse(
        generate_sse_events(request.query, request.depth, api_keys),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
