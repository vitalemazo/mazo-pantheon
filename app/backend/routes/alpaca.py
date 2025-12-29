"""
Alpaca API Routes

Provides endpoints for:
- Fetching tradeable assets (ticker search)
- Account information
- Portfolio status
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import requests
import logging

from app.backend.database import get_db
from app.backend.repositories.api_key_repository import ApiKeyRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alpaca", tags=["alpaca"])


def get_alpaca_credentials(db: Session) -> tuple[str, str, str]:
    """Get Alpaca credentials from database or environment."""
    repo = ApiKeyRepository(db)
    
    api_key = None
    secret_key = None
    base_url = None
    
    # Try database first
    api_key_record = repo.get_api_key_by_provider("ALPACA_API_KEY")
    if api_key_record:
        api_key = api_key_record.key_value
    
    secret_key_record = repo.get_api_key_by_provider("ALPACA_SECRET_KEY")
    if secret_key_record:
        secret_key = secret_key_record.key_value
    
    base_url_record = repo.get_api_key_by_provider("ALPACA_BASE_URL")
    if base_url_record:
        base_url = base_url_record.key_value
    
    # Fallback to environment
    api_key = api_key or os.environ.get("ALPACA_API_KEY")
    secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")
    base_url = base_url or os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")
    
    return api_key, secret_key, base_url


@router.get("/assets")
async def get_tradeable_assets(
    search: Optional[str] = Query(None, description="Search term to filter assets by symbol or name"),
    asset_class: str = Query("us_equity", description="Asset class: us_equity, crypto"),
    limit: int = Query(50, description="Maximum number of results to return"),
    db: Session = Depends(get_db)
):
    """
    Get a list of tradeable assets from Alpaca.
    
    Filters by tradable=True to only return currently tradeable assets.
    Use the search parameter to filter by symbol or company name.
    """
    api_key, secret_key, base_url = get_alpaca_credentials(db)
    
    if not api_key or not secret_key:
        raise HTTPException(
            status_code=400, 
            detail="Alpaca API credentials not configured. Set ALPACA_API_KEY and ALPACA_SECRET_KEY in Settings."
        )
    
    # Alpaca assets endpoint is on the trading API
    # Remove /v2 from base_url if present for assets endpoint
    assets_base = base_url.replace("/v2", "").replace("paper-api", "paper-api")
    assets_url = f"{assets_base}/v2/assets"
    
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
    }
    
    params = {
        "status": "active",
        "asset_class": asset_class,
    }
    
    try:
        response = requests.get(assets_url, headers=headers, params=params, timeout=30)
        
        if response.status_code != 200:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("message", response.text)
            except:
                pass
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Alpaca API error: {error_msg}"
            )
        
        all_assets = response.json()
        
        # Filter for tradeable assets only
        tradeable_assets = [
            asset for asset in all_assets 
            if asset.get("tradable") == True and asset.get("status") == "active"
        ]
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            tradeable_assets = [
                asset for asset in tradeable_assets
                if search_lower in asset.get("symbol", "").lower() 
                or search_lower in asset.get("name", "").lower()
            ]
        
        # Sort by symbol
        tradeable_assets.sort(key=lambda x: x.get("symbol", ""))
        
        # Limit results
        tradeable_assets = tradeable_assets[:limit]
        
        # Return simplified response
        return {
            "assets": [
                {
                    "symbol": asset.get("symbol"),
                    "name": asset.get("name"),
                    "exchange": asset.get("exchange"),
                    "asset_class": asset.get("class"),
                    "fractionable": asset.get("fractionable", False),
                    "shortable": asset.get("shortable", False),
                    "easy_to_borrow": asset.get("easy_to_borrow", False),
                }
                for asset in tradeable_assets
            ],
            "total": len(tradeable_assets),
            "search": search,
        }
        
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Alpaca API timeout")
    except requests.exceptions.RequestException as e:
        logger.error(f"Alpaca API request failed: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to Alpaca: {str(e)}")


@router.get("/status")
async def get_alpaca_status(db: Session = Depends(get_db)):
    """Check Alpaca connection status and account info."""
    api_key, secret_key, base_url = get_alpaca_credentials(db)
    
    if not api_key or not secret_key:
        return {
            "connected": False,
            "error": "Alpaca API credentials not configured",
            "mode": None,
        }
    
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
    }
    
    try:
        response = requests.get(f"{base_url}/account", headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {
                "connected": False,
                "error": f"API error: {response.status_code}",
                "mode": "paper" if "paper" in base_url else "live",
            }
        
        account = response.json()
        
        return {
            "connected": True,
            "mode": "paper" if "paper" in base_url else "live",
            "account_status": account.get("status"),
            "trading_blocked": account.get("trading_blocked", False),
            "buying_power": float(account.get("buying_power", 0)),
            "cash": float(account.get("cash", 0)),
            "portfolio_value": float(account.get("portfolio_value", 0)),
        }
        
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "mode": "paper" if "paper" in base_url else "live",
        }


@router.get("/popular")
async def get_popular_tickers():
    """
    Get a list of popular/common tickers for quick selection.
    These are hardcoded for fast response without API calls.
    """
    return {
        "tickers": [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "MSFT", "name": "Microsoft Corporation"},
            {"symbol": "GOOGL", "name": "Alphabet Inc."},
            {"symbol": "AMZN", "name": "Amazon.com Inc."},
            {"symbol": "NVDA", "name": "NVIDIA Corporation"},
            {"symbol": "META", "name": "Meta Platforms Inc."},
            {"symbol": "TSLA", "name": "Tesla Inc."},
            {"symbol": "JPM", "name": "JPMorgan Chase & Co."},
            {"symbol": "V", "name": "Visa Inc."},
            {"symbol": "JNJ", "name": "Johnson & Johnson"},
            {"symbol": "WMT", "name": "Walmart Inc."},
            {"symbol": "MA", "name": "Mastercard Inc."},
            {"symbol": "PG", "name": "Procter & Gamble"},
            {"symbol": "UNH", "name": "UnitedHealth Group"},
            {"symbol": "HD", "name": "Home Depot Inc."},
            {"symbol": "BAC", "name": "Bank of America"},
            {"symbol": "DIS", "name": "Walt Disney Co."},
            {"symbol": "NFLX", "name": "Netflix Inc."},
            {"symbol": "ADBE", "name": "Adobe Inc."},
            {"symbol": "CRM", "name": "Salesforce Inc."},
            {"symbol": "AMD", "name": "Advanced Micro Devices"},
            {"symbol": "INTC", "name": "Intel Corporation"},
            {"symbol": "CSCO", "name": "Cisco Systems"},
            {"symbol": "PFE", "name": "Pfizer Inc."},
            {"symbol": "TMO", "name": "Thermo Fisher Scientific"},
        ]
    }
