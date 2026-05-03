"""
FastAPI Application Entry Point
Miner Monitor Backend — REST API + WebSocket
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.timeseries import init_db
from backend.collector.poller import poller
from backend.api.routes import miners, training, anomaly, chat, presets, ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB and background scheduler. Shutdown: stop scheduler."""
    logger.info("Initializing database...")
    await init_db()

    logger.info("Starting background poller...")
    poller.start()

    # Restore any previously registered miners from DB
    from backend.db.timeseries import AsyncSessionLocal
    from backend.db.models import Miner
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Miner).where(Miner.enabled == True))
        saved_miners = result.scalars().all()
        for m in saved_miners:
            poller.add_miner(m.id, m.ip, m.port, m.preset_id, m.poll_interval)
            logger.info(f"Restored polling for miner {m.id} ({m.ip})")

        # Restore trained models
        from backend.db.models import TrainingRun
        from backend.ml.trainer import load_saved_models
        runs_result = await session.execute(
            select(TrainingRun).where(TrainingRun.status == "complete")
        )
        for run in runs_result.scalars().all():
            if run.model_path:
                load_saved_models(run.miner_id, run.model_path)

    logger.info("Miner Monitor API is ready")
    yield

    logger.info("Shutting down poller...")
    poller.stop()


app = FastAPI(
    title="Miner Monitor API",
    description="ASIC miner telemetry, anomaly detection, and LLM diagnostics",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all route modules
app.include_router(miners.router,   prefix="/api/miners",   tags=["miners"])
app.include_router(training.router, prefix="/api/training", tags=["training"])
app.include_router(anomaly.router,  prefix="/api/anomaly",  tags=["anomaly"])
app.include_router(chat.router,     prefix="/api/chat",     tags=["chat"])
app.include_router(presets.router,  prefix="/api/presets",  tags=["presets"])
app.include_router(ws.router,       prefix="/ws",           tags=["websocket"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
