"""
Environment Sync Routes

API routes for syncing environment variables to the database.
"""

from fastapi import APIRouter
from typing import Dict, List, Any

from app.backend.services.env_sync_service import env_sync_service

router = APIRouter(prefix="/env-sync", tags=["env-sync"])


@router.get("/status")
async def get_env_sync_status() -> List[Dict[str, Any]]:
    """
    Get the sync status of all environment variables.
    Shows which keys are in .env vs database.
    """
    return env_sync_service.get_env_keys_status()


@router.post("/sync")
async def sync_env_to_database(overwrite: bool = False) -> Dict[str, Any]:
    """
    Manually sync environment variables to the database.
    
    Args:
        overwrite: If True, overwrite existing keys. If False, only add missing keys.
    """
    return env_sync_service.sync_env_to_database(overwrite=overwrite)
