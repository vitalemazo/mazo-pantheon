"""
System Configuration Routes

Exposes trading configuration, data source status, and system settings.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any

router = APIRouter(prefix="/system", tags=["System Configuration"])


@router.get("/config")
async def get_system_config() -> Dict[str, Any]:
    """
    Get current system configuration.
    
    Returns all trading parameters, model settings, and data source config.
    """
    try:
        from src.trading.config import get_trading_config
        config = get_trading_config()
        return {
            "success": True,
            "config": config.to_dict(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "config": None,
        }


@router.get("/config/risk")
async def get_risk_config() -> Dict[str, Any]:
    """Get risk management configuration."""
    try:
        from src.trading.config import get_risk_config
        config = get_risk_config()
        return {
            "success": True,
            "stop_loss_pct": config.default_stop_loss_pct,
            "take_profit_pct": config.default_take_profit_pct,
            "position_size_pct": config.default_position_size_pct,
            "max_position_pct": config.max_position_pct,
            "max_sector_pct": config.max_sector_pct,
            "max_total_positions": config.max_total_positions,
            "max_hold_hours": config.max_hold_hours,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/data-sources")
async def get_data_sources() -> Dict[str, Any]:
    """
    Get status of all configured market data sources.
    
    Shows which data APIs are available, their rate limits, and priority.
    """
    try:
        from src.tools.data_providers import get_available_data_sources
        sources = get_available_data_sources()
        
        # Add summary
        available_count = sum(1 for s in sources.values() if s["available"])
        
        return {
            "success": True,
            "summary": {
                "total_sources": len(sources),
                "available_sources": available_count,
                "has_free_unlimited": sources.get("Yahoo Finance", {}).get("available", False),
            },
            "sources": sources,
        }
    except ImportError:
        return {
            "success": False,
            "error": "Multi-source data provider not installed",
            "sources": {},
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "sources": {},
        }


@router.get("/models")
async def get_model_config() -> Dict[str, Any]:
    """Get AI model configuration."""
    try:
        from src.trading.config import get_model_config
        from src.utils.llm import THINKING_MODEL_AGENTS
        
        config = get_model_config()
        
        return {
            "success": True,
            "default_model": config.default_model,
            "thinking_model": config.thinking_model,
            "fast_model": config.fast_model,
            "provider": config.provider,
            "thinking_agents": list(THINKING_MODEL_AGENTS),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/scanner")
async def get_scanner_config() -> Dict[str, Any]:
    """Get stock scanner configuration."""
    try:
        from src.trading.config import get_scanner_config
        config = get_scanner_config()
        
        return {
            "success": True,
            "scan_sp500": config.scan_sp500,
            "scan_nasdaq100": config.scan_nasdaq100,
            "additional_tickers": config.additional_tickers,
            "sector_rotation": config.sector_rotation,
            "min_volume": config.min_volume,
            "min_price": config.min_price,
            "max_price": config.max_price,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/config/reload")
async def reload_config() -> Dict[str, Any]:
    """
    Reload configuration from environment variables.
    
    Use this after updating environment variables to apply changes.
    """
    try:
        from src.trading.config import reload_config
        config = reload_config()
        
        return {
            "success": True,
            "message": "Configuration reloaded",
            "config": config.to_dict(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/agents")
async def get_agents_info() -> Dict[str, Any]:
    """Get information about available AI agents."""
    agents = [
        {"id": "warren_buffett", "name": "Warren Buffett", "style": "Value Investing", "uses_thinking": True},
        {"id": "ben_graham", "name": "Ben Graham", "style": "Deep Value / Margin of Safety", "uses_thinking": True},
        {"id": "charlie_munger", "name": "Charlie Munger", "style": "Quality Business / Moats"},
        {"id": "peter_lynch", "name": "Peter Lynch", "style": "Growth at Reasonable Price"},
        {"id": "cathie_wood", "name": "Cathie Wood", "style": "Disruptive Innovation"},
        {"id": "michael_burry", "name": "Michael Burry", "style": "Contrarian / Short", "uses_thinking": True},
        {"id": "bill_ackman", "name": "Bill Ackman", "style": "Activist Value"},
        {"id": "stanley_druckenmiller", "name": "Stanley Druckenmiller", "style": "Macro / Momentum"},
        {"id": "aswath_damodaran", "name": "Aswath Damodaran", "style": "Valuation Expert"},
        {"id": "mohnish_pabrai", "name": "Mohnish Pabrai", "style": "Dhandho Value"},
        {"id": "phil_fisher", "name": "Phil Fisher", "style": "Scuttlebutt / Growth"},
        {"id": "rakesh_jhunjhunwala", "name": "Rakesh Jhunjhunwala", "style": "Bull Market Momentum"},
        {"id": "fundamentals", "name": "Fundamentals Analyst", "style": "Financial Statement Analysis"},
        {"id": "technicals", "name": "Technical Analyst", "style": "Chart Patterns / Indicators"},
        {"id": "valuation", "name": "Valuation Analyst", "style": "DCF / Relative Valuation"},
        {"id": "growth", "name": "Growth Analyst", "style": "Revenue / Earnings Growth"},
        {"id": "sentiment", "name": "Sentiment Analyst", "style": "Market Sentiment"},
        {"id": "news_sentiment", "name": "News Analyst", "style": "News & Headlines"},
        {"id": "risk_manager", "name": "Risk Manager", "style": "Portfolio Risk", "uses_thinking": True},
        {"id": "portfolio_manager", "name": "Portfolio Manager", "style": "Final Decisions", "uses_thinking": True},
    ]
    
    return {
        "success": True,
        "total_agents": len(agents),
        "thinking_model_agents": sum(1 for a in agents if a.get("uses_thinking")),
        "agents": agents,
    }
