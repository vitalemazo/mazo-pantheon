from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio

from app.backend.routes import api_router
from app.backend.database.connection import engine
from app.backend.database.models import Base
from app.backend.services.ollama_service import ollama_service
from app.backend.services.env_sync_service import sync_env_on_startup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Hedge Fund API", description="Backend API for AI Hedge Fund", version="0.1.0")

# Initialize database tables (this is safe to run multiple times)
Base.metadata.create_all(bind=engine)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routes
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    """Startup event to sync env vars, check Ollama, and start autonomous trading."""
    
    # Sync environment variables to database
    try:
        logger.info("=" * 50)
        logger.info("AI Hedge Fund Backend Starting...")
        logger.info("=" * 50)
        
        # Sync API keys from .env to database
        sync_result = sync_env_on_startup()
        if sync_result.get("synced"):
            logger.info("API keys synced from .env to Settings UI")
        
    except Exception as e:
        logger.warning(f"Could not sync environment variables: {e}")
    
    # Check Ollama availability
    try:
        logger.info("Checking Ollama availability...")
        status = await ollama_service.check_ollama_status()
        
        if status["installed"]:
            if status["running"]:
                logger.info(f"Ollama is installed and running at {status['server_url']}")
                if status["available_models"]:
                    logger.info(f"Available models: {', '.join(status['available_models'])}")
                else:
                    logger.info("No models are currently downloaded")
            else:
                logger.info("Ollama is installed but not running")
        else:
            logger.info("Ollama is not installed. Install it to use local models.")
            logger.info("Visit https://ollama.com to download and install Ollama")
            
    except Exception as e:
        logger.warning(f"Could not check Ollama status: {e}")
    
    logger.info("=" * 50)
    logger.info("Backend ready! Settings UI will show your .env API keys.")
    logger.info("=" * 50)
    
    # ==================== AUTONOMOUS TRADING STARTUP ====================
    try:
        from src.trading.scheduler import get_scheduler
        
        scheduler = get_scheduler()
        
        if scheduler.start():
            logger.info("")
            logger.info("=" * 50)
            logger.info("AUTONOMOUS TRADING MODE ENABLED")
            logger.info("=" * 50)
            
            jobs = scheduler.add_default_schedule()
            
            logger.info(f"Trading scheduler started with {len(jobs)} scheduled tasks")
            logger.info("")
            logger.info("Schedule (Eastern Time):")
            logger.info("  6:30 AM  - Pre-market health check")
            logger.info("  9:35 AM  - Market open momentum scan")
            logger.info("  10:00 AM - Diversification scan")
            logger.info("  12:00 PM - Midday stop-loss review")
            logger.info("  2:00 PM  - Afternoon health check")
            logger.info("  3:30 PM  - Pre-close watchlist monitor")
            logger.info("  4:05 PM  - Daily performance report")
            logger.info("  Every 5m  - Position Monitor (AUTO-EXIT on stop-loss/take-profit)")
            logger.info("  Every 30m - AI Trading Cycle (full pipeline)")
            logger.info("")
            logger.info("System is now fully autonomous!")
            logger.info("=" * 50)
        else:
            logger.warning("Could not start scheduler - running in manual mode")
            
    except Exception as e:
        logger.warning(f"Autonomous trading setup failed: {e}")
        logger.info("System running in manual mode")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event to stop the trading scheduler."""
    try:
        from src.trading.scheduler import get_scheduler
        scheduler = get_scheduler()
        scheduler.stop()
        logger.info("Trading scheduler stopped")
    except Exception as e:
        logger.warning(f"Error stopping scheduler: {e}")
