"""
Database Layer
Async SQLAlchemy session factory and time-series query helpers.
"""
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, desc, and_
from backend.db.models import Base, TelemetryReading, AnomalyEvent, Miner, TrainingRun

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "miner_monitor.db"))
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    """Create all tables on startup."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields a database session."""
    async with AsyncSessionLocal() as session:
        yield session


# ── Telemetry helpers ──────────────────────────────────────────────────────────

async def insert_reading(
    session: AsyncSession,
    miner_id: str,
    timestamp: datetime,
    values: dict,
    poll_ok: bool = True,
):
    reading = TelemetryReading(
        miner_id=miner_id,
        timestamp=timestamp,
        values=values,
        poll_ok=poll_ok,
    )
    session.add(reading)
    await session.commit()
    return reading


async def get_recent_readings(
    session: AsyncSession,
    miner_id: str,
    limit: int = 100,
    since: Optional[datetime] = None,
) -> list[TelemetryReading]:
    q = select(TelemetryReading).where(
        TelemetryReading.miner_id == miner_id,
        TelemetryReading.poll_ok == True,
    )
    if since:
        q = q.where(TelemetryReading.timestamp >= since)
    q = q.order_by(desc(TelemetryReading.timestamp)).limit(limit)
    result = await session.execute(q)
    return result.scalars().all()


async def get_readings_for_training(
    session: AsyncSession,
    miner_id: str,
    max_samples: int = 5000,
) -> list[dict]:
    """Return telemetry values as a list of dicts for ML training."""
    q = (
        select(TelemetryReading.timestamp, TelemetryReading.values)
        .where(
            TelemetryReading.miner_id == miner_id,
            TelemetryReading.poll_ok == True,
        )
        .order_by(TelemetryReading.timestamp)
        .limit(max_samples)
    )
    result = await session.execute(q)
    return [{"timestamp": ts, **vals} for ts, vals in result.all()]


# ── Anomaly event helpers ──────────────────────────────────────────────────────

async def insert_anomaly_event(session: AsyncSession, event: AnomalyEvent):
    session.add(event)
    await session.commit()
    return event


async def get_recent_events(
    session: AsyncSession,
    miner_id: str,
    limit: int = 20,
) -> list[AnomalyEvent]:
    q = (
        select(AnomalyEvent)
        .where(AnomalyEvent.miner_id == miner_id)
        .order_by(desc(AnomalyEvent.timestamp))
        .limit(limit)
    )
    result = await session.execute(q)
    return result.scalars().all()


# ── Training run helpers ───────────────────────────────────────────────────────

async def get_active_training(
    session: AsyncSession, miner_id: str
) -> Optional[TrainingRun]:
    q = select(TrainingRun).where(
        TrainingRun.miner_id == miner_id,
        TrainingRun.is_active == True,
    )
    result = await session.execute(q)
    return result.scalar_one_or_none()


async def get_completed_training(
    session: AsyncSession, miner_id: str
) -> Optional[TrainingRun]:
    q = (
        select(TrainingRun)
        .where(
            TrainingRun.miner_id == miner_id,
            TrainingRun.status == "complete",
        )
        .order_by(desc(TrainingRun.finished_at))
        .limit(1)
    )
    result = await session.execute(q)
    return result.scalar_one_or_none()
