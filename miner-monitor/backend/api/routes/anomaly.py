"""
Anomaly API Routes
Query anomaly events, scores, and status history.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.db.timeseries import get_session, get_recent_events
from backend.db.models import AnomalyEvent, Miner

router = APIRouter()


@router.get("/{miner_id}/events")
async def list_events(
    miner_id: str,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    events = await get_recent_events(session, miner_id, limit=limit)
    return [_event_to_dict(e) for e in events]


@router.get("/{miner_id}/latest")
async def latest_event(miner_id: str, session: AsyncSession = Depends(get_session)):
    events = await get_recent_events(session, miner_id, limit=1)
    if not events:
        raise HTTPException(404, "No anomaly events recorded yet")
    return _event_to_dict(events[0])


@router.get("/summary/all")
async def all_miners_summary(session: AsyncSession = Depends(get_session)):
    """Return the latest status for every registered miner — used by the dashboard overview."""
    result = await session.execute(select(Miner).where(Miner.enabled == True))
    miners = result.scalars().all()

    summaries = []
    for m in miners:
        events = await get_recent_events(session, m.id, limit=1)
        latest = _event_to_dict(events[0]) if events else None
        summaries.append({
            "miner_id": m.id,
            "miner_name": m.name,
            "ip": m.ip,
            "last_seen": m.last_seen.isoformat() if m.last_seen else None,
            "latest_event": latest,
        })
    return summaries


def _event_to_dict(e: AnomalyEvent) -> dict:
    return {
        "id": e.id,
        "miner_id": e.miner_id,
        "timestamp": e.timestamp.isoformat(),
        "status": e.status,
        "if_score": e.if_score,
        "lstm_error": e.lstm_error,
        "triggered_rules": e.triggered_rules or [],
        "affected_features": e.affected_features or [],
        "raw_values": e.raw_values or {},
        "chatbot_diagnosis": e.chatbot_diagnosis,
    }
