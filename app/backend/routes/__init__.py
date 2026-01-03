from fastapi import APIRouter

from app.backend.routes.hedge_fund import router as hedge_fund_router
from app.backend.routes.health import router as health_router
from app.backend.routes.storage import router as storage_router
from app.backend.routes.flows import router as flows_router
from app.backend.routes.flow_runs import router as flow_runs_router
from app.backend.routes.ollama import router as ollama_router
from app.backend.routes.language_models import router as language_models_router
from app.backend.routes.api_keys import router as api_keys_router
from app.backend.routes.mazo import router as mazo_router
from app.backend.routes.unified_workflow import router as unified_workflow_router
from app.backend.routes.env_sync import router as env_sync_router
from app.backend.routes.alpaca import router as alpaca_router
from app.backend.routes.diversification import router as diversification_router
from app.backend.routes.trading import router as trading_router
from app.backend.routes.history import router as history_router
from app.backend.routes.monitoring import router as monitoring_router
from app.backend.routes.system_config import router as system_config_router
from app.backend.routes.transparency import router as transparency_router
from app.backend.routes.sync import router as sync_router
from app.backend.routes.charts import router as charts_router
from app.backend.routes.danelfin import router as danelfin_router

# Main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router, tags=["health"])
api_router.include_router(hedge_fund_router, tags=["hedge-fund"])
api_router.include_router(mazo_router, tags=["mazo"])
api_router.include_router(storage_router, tags=["storage"])
api_router.include_router(flows_router, tags=["flows"])
api_router.include_router(flow_runs_router, tags=["flow-runs"])
api_router.include_router(ollama_router, tags=["ollama"])
api_router.include_router(language_models_router, tags=["language-models"])
api_router.include_router(api_keys_router, tags=["api-keys"])
api_router.include_router(unified_workflow_router, tags=["unified-workflow"])
api_router.include_router(env_sync_router, tags=["env-sync"])
api_router.include_router(alpaca_router, tags=["alpaca"])
api_router.include_router(diversification_router, tags=["diversification"])
api_router.include_router(trading_router, tags=["trading"])
api_router.include_router(history_router, tags=["history"])
api_router.include_router(monitoring_router, tags=["monitoring"])
api_router.include_router(system_config_router, tags=["system-config"])
api_router.include_router(transparency_router, tags=["transparency"])
api_router.include_router(sync_router, tags=["sync"])
api_router.include_router(charts_router, tags=["charts"])
api_router.include_router(danelfin_router, tags=["danelfin"])