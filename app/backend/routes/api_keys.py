from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import os
from pathlib import Path

from app.backend.database import get_db
from app.backend.repositories.api_key_repository import ApiKeyRepository
from app.backend.models.schemas import (
    ApiKeyCreateRequest,
    ApiKeyUpdateRequest,
    ApiKeyResponse,
    ApiKeySummaryResponse,
    ApiKeyBulkUpdateRequest,
    ErrorResponse
)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post(
    "/",
    response_model=ApiKeyResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_or_update_api_key(request: ApiKeyCreateRequest, db: Session = Depends(get_db)):
    """Create a new API key or update existing one"""
    try:
        repo = ApiKeyRepository(db)
        api_key = repo.create_or_update_api_key(
            provider=request.provider,
            key_value=request.key_value,
            description=request.description,
            is_active=request.is_active
        )
        return ApiKeyResponse.from_orm(api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create/update API key: {str(e)}")


@router.get(
    "/",
    response_model=List[ApiKeySummaryResponse],
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_api_keys(include_inactive: bool = False, db: Session = Depends(get_db)):
    """Get all API keys (without actual key values for security)"""
    try:
        repo = ApiKeyRepository(db)
        api_keys = repo.get_all_api_keys(include_inactive=include_inactive)
        return [ApiKeySummaryResponse.from_orm(key) for key in api_keys]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve API keys: {str(e)}")


@router.get(
    "/{provider}",
    response_model=ApiKeyResponse,
    responses={
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_api_key(provider: str, db: Session = Depends(get_db)):
    """Get a specific API key by provider"""
    try:
        repo = ApiKeyRepository(db)
        api_key = repo.get_api_key_by_provider(provider)
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        return ApiKeyResponse.from_orm(api_key)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve API key: {str(e)}")


@router.put(
    "/{provider}",
    response_model=ApiKeyResponse,
    responses={
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def update_api_key(provider: str, request: ApiKeyUpdateRequest, db: Session = Depends(get_db)):
    """Update an existing API key"""
    try:
        repo = ApiKeyRepository(db)
        api_key = repo.update_api_key(
            provider=provider,
            key_value=request.key_value,
            description=request.description,
            is_active=request.is_active
        )
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        return ApiKeyResponse.from_orm(api_key)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update API key: {str(e)}")


@router.delete(
    "/{provider}",
    responses={
        204: {"description": "API key deleted successfully"},
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def delete_api_key(provider: str, db: Session = Depends(get_db)):
    """Delete an API key"""
    try:
        repo = ApiKeyRepository(db)
        success = repo.delete_api_key(provider)
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        return {"message": "API key deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete API key: {str(e)}")


@router.patch(
    "/{provider}/deactivate",
    response_model=ApiKeySummaryResponse,
    responses={
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def deactivate_api_key(provider: str, db: Session = Depends(get_db)):
    """Deactivate an API key without deleting it"""
    try:
        repo = ApiKeyRepository(db)
        success = repo.deactivate_api_key(provider)
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Return the updated key
        api_key = repo.get_api_key_by_provider(provider)
        return ApiKeySummaryResponse.from_orm(api_key)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate API key: {str(e)}")


@router.post(
    "/bulk",
    response_model=List[ApiKeyResponse],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def bulk_update_api_keys(request: ApiKeyBulkUpdateRequest, db: Session = Depends(get_db)):
    """Bulk create or update multiple API keys"""
    try:
        repo = ApiKeyRepository(db)
        api_keys_data = [
            {
                'provider': key.provider,
                'key_value': key.key_value,
                'description': key.description,
                'is_active': key.is_active
            }
            for key in request.api_keys
        ]
        api_keys = repo.bulk_create_or_update(api_keys_data)
        return [ApiKeyResponse.from_orm(key) for key in api_keys]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk update API keys: {str(e)}")


@router.patch(
    "/{provider}/last-used",
    responses={
        200: {"description": "Last used timestamp updated"},
        404: {"model": ErrorResponse, "description": "API key not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def update_last_used(provider: str, db: Session = Depends(get_db)):
    """Update the last used timestamp for an API key"""
    try:
        repo = ApiKeyRepository(db)
        success = repo.update_last_used(provider)
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        return {"message": "Last used timestamp updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update last used timestamp: {str(e)}")


@router.post(
    "/sync-to-env",
    responses={
        200: {"description": "Settings synced to .env file"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def sync_to_env_file(db: Session = Depends(get_db)):
    """Sync all API keys from database to .env file"""
    try:
        repo = ApiKeyRepository(db)
        api_keys = repo.get_all_api_keys(include_inactive=False)
        
        # Find .env file (check multiple locations)
        env_paths = [
            Path("/app/.env"),  # Docker container
            Path.cwd() / ".env",  # Current directory
            Path(__file__).parent.parent.parent.parent.parent / ".env",  # Project root
        ]
        
        env_path = None
        for path in env_paths:
            if path.exists():
                env_path = path
                break
        
        if not env_path:
            # Create new .env file in project root
            env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
        
        # Read existing .env content
        existing_content = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        existing_content[key.strip()] = value.strip()
        
        # Update with database values
        updated_keys = []
        for api_key in api_keys:
            if api_key.key_value:
                existing_content[api_key.provider] = api_key.key_value
                updated_keys.append(api_key.provider)
        
        # Write back to .env file
        with open(env_path, 'w') as f:
            f.write("# ===========================================\n")
            f.write("# AI HEDGE FUND ENVIRONMENT CONFIGURATION\n")
            f.write("# Auto-synced from Settings UI\n")
            f.write("# ===========================================\n\n")
            
            # Group by category
            categories = {
                'Financial Data': ['FINANCIAL_DATASETS_API_KEY', 'FMP_API_KEY'],
                'LLM Providers': ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPSEEK_API_KEY', 'GROQ_API_KEY', 'GOOGLE_API_KEY', 'OPENROUTER_API_KEY', 'GIGACHAT_API_KEY', 'XAI_API_KEY'],
                'Custom Endpoints': ['OPENAI_API_BASE', 'ANTHROPIC_API_BASE', 'OPENROUTER_API_BASE', 'XAI_API_BASE'],
                'Azure OpenAI': ['AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_DEPLOYMENT_NAME', 'AZURE_OPENAI_API_VERSION'],
                'Trading': ['ALPACA_API_KEY', 'ALPACA_SECRET_KEY', 'ALPACA_BASE_URL', 'ALPACA_TRADING_MODE'],
                'Search': ['TAVILY_API_KEY'],
                'Mazo Config': ['MAZO_PATH', 'MAZO_TIMEOUT', 'DEFAULT_WORKFLOW_MODE', 'DEFAULT_RESEARCH_DEPTH'],
            }
            
            written_keys = set()
            for category, keys in categories.items():
                category_keys = [(k, existing_content.get(k)) for k in keys if existing_content.get(k)]
                if category_keys:
                    f.write(f"# {category}\n")
                    for key, value in category_keys:
                        f.write(f"{key}={value}\n")
                        written_keys.add(key)
                    f.write("\n")
            
            # Write remaining keys
            remaining = {k: v for k, v in existing_content.items() if k not in written_keys}
            if remaining:
                f.write("# Other Settings\n")
                for key, value in remaining.items():
                    f.write(f"{key}={value}\n")
        
        return {
            "message": f"Synced {len(updated_keys)} keys to {env_path}",
            "updated_keys": updated_keys,
            "env_path": str(env_path)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync to .env file: {str(e)}") 