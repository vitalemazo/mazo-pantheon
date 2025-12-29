"""
Environment Variable Sync Service

Syncs API keys from environment variables (.env file) to the database
so they're visible and editable in the Settings UI.
"""

import os
import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.backend.database.connection import SessionLocal
from app.backend.repositories.api_key_repository import ApiKeyRepository

logger = logging.getLogger(__name__)


# List of environment variables that should be synced to the database
ENV_KEYS_TO_SYNC = [
    # Financial Data
    {
        "env_key": "FINANCIAL_DATASETS_API_KEY",
        "provider": "FINANCIAL_DATASETS_API_KEY",
        "description": "For getting financial data to power the hedge fund"
    },
    
    # LLM Providers
    {
        "env_key": "OPENAI_API_KEY",
        "provider": "OPENAI_API_KEY",
        "description": "For OpenAI models (GPT-4o, etc.)"
    },
    {
        "env_key": "OPENAI_API_BASE",
        "provider": "OPENAI_API_BASE",
        "description": "Custom base URL for OpenAI-compatible APIs"
    },
    {
        "env_key": "ANTHROPIC_API_KEY",
        "provider": "ANTHROPIC_API_KEY",
        "description": "For Claude models (claude-4-sonnet, etc.)"
    },
    {
        "env_key": "DEEPSEEK_API_KEY",
        "provider": "DEEPSEEK_API_KEY",
        "description": "For DeepSeek models"
    },
    {
        "env_key": "GROQ_API_KEY",
        "provider": "GROQ_API_KEY",
        "description": "For Groq-hosted models"
    },
    {
        "env_key": "GOOGLE_API_KEY",
        "provider": "GOOGLE_API_KEY",
        "description": "For Gemini models"
    },
    {
        "env_key": "XAI_API_KEY",
        "provider": "XAI_API_KEY",
        "description": "For xAI models (Grok)"
    },
    {
        "env_key": "GIGACHAT_API_KEY",
        "provider": "GIGACHAT_API_KEY",
        "description": "For GigaChat models"
    },
    {
        "env_key": "OPENROUTER_API_KEY",
        "provider": "OPENROUTER_API_KEY",
        "description": "For OpenRouter models"
    },
    
    # Azure OpenAI
    {
        "env_key": "AZURE_OPENAI_API_KEY",
        "provider": "AZURE_OPENAI_API_KEY",
        "description": "Azure OpenAI API key"
    },
    {
        "env_key": "AZURE_OPENAI_ENDPOINT",
        "provider": "AZURE_OPENAI_ENDPOINT",
        "description": "Azure OpenAI endpoint URL"
    },
    {
        "env_key": "AZURE_OPENAI_DEPLOYMENT_NAME",
        "provider": "AZURE_OPENAI_DEPLOYMENT_NAME",
        "description": "Azure OpenAI deployment name"
    },
    
    # Search & Research
    {
        "env_key": "TAVILY_API_KEY",
        "provider": "TAVILY_API_KEY",
        "description": "For web search in research"
    },
    
    # Trading
    {
        "env_key": "ALPACA_API_KEY",
        "provider": "ALPACA_API_KEY",
        "description": "Alpaca trading API key"
    },
    {
        "env_key": "ALPACA_SECRET_KEY",
        "provider": "ALPACA_SECRET_KEY",
        "description": "Alpaca trading secret key"
    },
    {
        "env_key": "ALPACA_BASE_URL",
        "provider": "ALPACA_BASE_URL",
        "description": "Alpaca API base URL (paper or live)"
    },
    {
        "env_key": "ALPACA_TRADING_MODE",
        "provider": "ALPACA_TRADING_MODE",
        "description": "Alpaca trading mode (paper or live)"
    },
    
    # Mazo Configuration
    {
        "env_key": "MAZO_PATH",
        "provider": "MAZO_PATH",
        "description": "Path to Mazo directory"
    },
    {
        "env_key": "MAZO_TIMEOUT",
        "provider": "MAZO_TIMEOUT",
        "description": "Timeout for Mazo queries in seconds"
    },
    {
        "env_key": "DEFAULT_WORKFLOW_MODE",
        "provider": "DEFAULT_WORKFLOW_MODE",
        "description": "Default workflow mode (signal, research, pre-research, post-research, full)"
    },
    {
        "env_key": "DEFAULT_RESEARCH_DEPTH",
        "provider": "DEFAULT_RESEARCH_DEPTH",
        "description": "Default research depth (quick, standard, deep)"
    },
    
    # Workflow Optimization
    {
        "env_key": "AGGREGATE_DATA",
        "provider": "AGGREGATE_DATA",
        "description": "Pre-fetch all financial data before agents run. Reduces API calls but adds initial delay. (true/false)"
    },
    
    # Data Source Fallbacks
    {
        "env_key": "USE_YAHOO_FINANCE_FALLBACK",
        "provider": "USE_YAHOO_FINANCE_FALLBACK",
        "description": "Use Yahoo Finance as fallback when Financial Datasets API fails (true/false)"
    },
    {
        "env_key": "YAHOO_FINANCE_FOR_PRICES",
        "provider": "YAHOO_FINANCE_FOR_PRICES",
        "description": "Enable Yahoo Finance fallback for price data (true/false)"
    },
    {
        "env_key": "YAHOO_FINANCE_FOR_METRICS",
        "provider": "YAHOO_FINANCE_FOR_METRICS",
        "description": "Enable Yahoo Finance fallback for financial metrics (true/false)"
    },
    {
        "env_key": "YAHOO_FINANCE_FOR_NEWS",
        "provider": "YAHOO_FINANCE_FOR_NEWS",
        "description": "Enable Yahoo Finance fallback for news (true/false)"
    },
    {
        "env_key": "PRIMARY_DATA_SOURCE",
        "provider": "PRIMARY_DATA_SOURCE",
        "description": "Primary financial data source (financial_datasets, yahoo_finance, fmp)"
    },
    
    # FMP (Financial Modeling Prep) API
    {
        "env_key": "FMP_API_KEY",
        "provider": "FMP_API_KEY",
        "description": "Financial Modeling Prep API key for stock data, financials, and news"
    },
    {
        "env_key": "USE_FMP_FALLBACK",
        "provider": "USE_FMP_FALLBACK",
        "description": "Use FMP as fallback when primary API fails (true/false)"
    },
    {
        "env_key": "FMP_FOR_PRICES",
        "provider": "FMP_FOR_PRICES",
        "description": "Enable FMP fallback for price data (true/false)"
    },
    {
        "env_key": "FMP_FOR_METRICS",
        "provider": "FMP_FOR_METRICS",
        "description": "Enable FMP fallback for financial metrics (true/false)"
    },
    {
        "env_key": "FMP_FOR_NEWS",
        "provider": "FMP_FOR_NEWS",
        "description": "Enable FMP fallback for news (true/false)"
    },
    {
        "env_key": "FMP_FOR_FINANCIALS",
        "provider": "FMP_FOR_FINANCIALS",
        "description": "Enable FMP fallback for income statements, balance sheets, cash flows (true/false)"
    },
]


class EnvSyncService:
    """Service to sync environment variables to the database."""
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize with optional database session."""
        self._db = db
    
    def _get_db(self) -> Session:
        """Get or create database session."""
        if self._db:
            return self._db
        return SessionLocal()
    
    def sync_env_to_database(self, overwrite: bool = False) -> Dict[str, any]:
        """
        Sync environment variables to the database.
        
        Args:
            overwrite: If True, overwrite existing keys in database.
                      If False, only add keys that don't exist in database.
        
        Returns:
            Summary of sync operation.
        """
        db = self._get_db()
        close_db = self._db is None  # Only close if we created the session
        
        try:
            repo = ApiKeyRepository(db)
            
            synced = []
            skipped = []
            errors = []
            
            for key_config in ENV_KEYS_TO_SYNC:
                env_key = key_config["env_key"]
                provider = key_config["provider"]
                description = key_config["description"]
                
                # Get value from environment
                env_value = os.environ.get(env_key)
                
                if not env_value:
                    # No value in environment
                    continue
                
                try:
                    # Check if key already exists in database
                    existing = repo.get_api_key_by_provider(provider)
                    
                    if existing and not overwrite:
                        # Key exists and we're not overwriting
                        skipped.append(provider)
                        continue
                    
                    # Create or update the key
                    repo.create_or_update_api_key(
                        provider=provider,
                        key_value=env_value,
                        description=description,
                        is_active=True
                    )
                    synced.append(provider)
                    logger.info(f"✓ Synced {provider} from environment to database")
                    
                except Exception as e:
                    errors.append({"provider": provider, "error": str(e)})
                    logger.error(f"✗ Failed to sync {provider}: {e}")
            
            return {
                "synced": synced,
                "skipped": skipped,
                "errors": errors,
                "total_env_keys": len([k for k in ENV_KEYS_TO_SYNC if os.environ.get(k["env_key"])]),
                "success": len(errors) == 0
            }
            
        finally:
            if close_db:
                db.close()
    
    def get_env_keys_status(self) -> List[Dict[str, any]]:
        """Get status of all environment keys (present in env vs database)."""
        db = self._get_db()
        close_db = self._db is None
        
        try:
            repo = ApiKeyRepository(db)
            
            status = []
            for key_config in ENV_KEYS_TO_SYNC:
                env_key = key_config["env_key"]
                provider = key_config["provider"]
                
                env_value = os.environ.get(env_key)
                db_key = repo.get_api_key_by_provider(provider)
                
                status.append({
                    "provider": provider,
                    "env_key": env_key,
                    "description": key_config["description"],
                    "in_env": bool(env_value),
                    "in_database": bool(db_key),
                    "is_active": db_key.is_active if db_key else None,
                    "synced": bool(env_value) and bool(db_key)
                })
            
            return status
            
        finally:
            if close_db:
                db.close()


# Singleton instance
env_sync_service = EnvSyncService()


def sync_env_on_startup():
    """Called on application startup to sync env vars to database."""
    logger.info("Syncing environment variables to database...")
    
    try:
        result = env_sync_service.sync_env_to_database(overwrite=False)
        
        if result["synced"]:
            logger.info(f"✓ Synced {len(result['synced'])} API keys from .env to database")
            for key in result["synced"]:
                logger.info(f"  - {key}")
        
        if result["skipped"]:
            logger.info(f"ℹ Skipped {len(result['skipped'])} keys (already in database)")
        
        if result["errors"]:
            logger.warning(f"✗ Failed to sync {len(result['errors'])} keys")
            for err in result["errors"]:
                logger.warning(f"  - {err['provider']}: {err['error']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to sync environment variables: {e}")
        return {"synced": [], "skipped": [], "errors": [{"error": str(e)}], "success": False}
