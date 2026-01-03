"""
Alpaca API Routes

Provides endpoints for:
- Fetching tradeable assets (ticker search)
- Account information
- Portfolio status

Uses Redis caching to dramatically speed up asset searches.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import requests
import logging

from app.backend.database import get_db
from app.backend.repositories.api_key_repository import ApiKeyRepository
from app.backend.services.cache_service import (
    get_cached_alpaca_assets, 
    cache_alpaca_assets,
    CacheTTL,
    get_cached,
    set_cached,
)

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
    
    Uses Redis caching (1 hour TTL) to avoid repeated API calls.
    The full asset list is cached, then filtered client-side for searches.
    """
    # Try to get cached assets first
    cache_key = f"alpaca:assets:{asset_class}"
    cached_assets = get_cached(cache_key)
    
    if cached_assets is None:
        # Cache miss - fetch from Alpaca
        logger.info(f"[Cache] Fetching Alpaca assets from API...")
        
        api_key, secret_key, base_url = get_alpaca_credentials(db)
        
        if not api_key or not secret_key:
            raise HTTPException(
                status_code=400, 
                detail="Alpaca API credentials not configured. Set ALPACA_API_KEY and ALPACA_SECRET_KEY in Settings."
            )
        
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
            
            # Filter for tradeable assets and simplify
            cached_assets = [
                {
                    "symbol": asset.get("symbol"),
                    "name": asset.get("name"),
                    "exchange": asset.get("exchange"),
                    "asset_class": asset.get("class"),
                    "fractionable": asset.get("fractionable", False),
                    "shortable": asset.get("shortable", False),
                    "easy_to_borrow": asset.get("easy_to_borrow", False),
                }
                for asset in all_assets 
                if asset.get("tradable") == True and asset.get("status") == "active"
            ]
            
            # Cache for 1 hour (assets rarely change)
            set_cached(cache_key, cached_assets, CacheTTL.ALPACA_ASSETS)
            logger.info(f"[Cache] Cached {len(cached_assets)} Alpaca assets")
            
        except requests.exceptions.Timeout:
            raise HTTPException(status_code=504, detail="Alpaca API timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"Alpaca API request failed: {e}")
            raise HTTPException(status_code=502, detail=f"Failed to connect to Alpaca: {str(e)}")
    else:
        logger.debug(f"[Cache] Using cached Alpaca assets ({len(cached_assets)} items)")
    
    # Now filter cached assets
    tradeable_assets = cached_assets
    
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
    
    return {
        "assets": tradeable_assets,
        "total": len(tradeable_assets),
        "search": search,
        "cached": cached_assets is not None,
    }


@router.get("/status")
async def get_alpaca_status(db: Session = Depends(get_db)):
    """Check Alpaca connection status and account info (cached for 30 seconds)."""
    # Check cache first
    cache_key = "alpaca:status"
    cached_status = get_cached(cache_key)
    if cached_status:
        cached_status["cached"] = True
        return cached_status
    
    api_key, secret_key, base_url = get_alpaca_credentials(db)
    
    if not api_key or not secret_key:
        return {
            "connected": False,
            "error": "Alpaca API credentials not configured",
            "mode": None,
            "cached": False,
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
                "cached": False,
            }
        
        account = response.json()
        
        result = {
            "connected": True,
            "mode": "paper" if "paper" in base_url else "live",
            "account_status": account.get("status"),
            "trading_blocked": account.get("trading_blocked", False),
            "buying_power": float(account.get("buying_power", 0)),
            "cash": float(account.get("cash", 0)),
            "portfolio_value": float(account.get("portfolio_value", 0)),
            "cached": False,
        }
        
        # Cache for 30 seconds
        set_cached(cache_key, result, CacheTTL.ALPACA_ACCOUNT)
        return result
        
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "mode": "paper" if "paper" in base_url else "live",
            "cached": False,
        }


@router.post("/refresh")
async def refresh_alpaca_connection(db: Session = Depends(get_db)):
    """
    Force refresh Alpaca connection with latest credentials from database.
    Clears all Alpaca caches and fetches fresh account data.
    
    Call this after updating Alpaca API keys in Settings.
    """
    from app.backend.services.cache_service import delete_cached
    
    # Clear all Alpaca caches
    cache_keys_to_clear = [
        "alpaca:status",
        "alpaca:assets:us_equity",
        "alpaca:assets:crypto",
        "alpaca:account",
        "alpaca:positions",
    ]
    
    cleared = 0
    for key in cache_keys_to_clear:
        try:
            delete_cached(key)
            cleared += 1
        except Exception:
            pass
    
    logger.info(f"[Alpaca] Cleared {cleared} cache keys for credential refresh")
    
    # Now fetch fresh account data with new credentials
    api_key, secret_key, base_url = get_alpaca_credentials(db)
    
    if not api_key or not secret_key:
        return {
            "success": False,
            "error": "Alpaca API credentials not configured",
            "account": None,
        }
    
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
    }
    
    try:
        # Fetch account
        response = requests.get(f"{base_url}/account", headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"API error: {response.status_code} - {response.text}",
                "account": None,
            }
        
        account = response.json()
        
        # Fetch positions
        positions_response = requests.get(f"{base_url}/positions", headers=headers, timeout=10)
        positions = positions_response.json() if positions_response.status_code == 200 else []
        
        account_data = {
            "connected": True,
            "mode": "paper" if "paper" in base_url else "live",
            "account_status": account.get("status"),
            "buying_power": float(account.get("buying_power", 0)),
            "cash": float(account.get("cash", 0)),
            "portfolio_value": float(account.get("portfolio_value", 0)),
            "equity": float(account.get("equity", 0)),
            "positions_count": len(positions),
        }
        
        # Cache the fresh data
        set_cached("alpaca:status", account_data, CacheTTL.ALPACA_ACCOUNT)
        
        logger.info(f"[Alpaca] Refreshed connection - Equity: ${account_data['equity']:,.2f}, Positions: {account_data['positions_count']}")
        
        return {
            "success": True,
            "message": "Alpaca connection refreshed with new credentials",
            "account": account_data,
        }
        
    except Exception as e:
        logger.error(f"[Alpaca] Refresh failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "account": None,
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
