"""
Miners API Routes
Add/remove/update miners, discover fields, get live status.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.timeseries import get_session, insert_reading
from backend.db.models import Miner, TelemetryReading
from backend.collector.socket_client import discover_all_fields, poll_miner_async
from backend.collector.preset_registry import registry
from backend.collector.poller import poller
from backend.rules.safety_rules import check_rules, determine_status_from_rules
from backend.ml.trainer import score_reading, get_baseline
from backend.db.timeseries import get_recent_readings, AsyncSessionLocal

router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class AddMinerRequest(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9\-_]+$", description="Unique slug e.g. l3-01")
    name: str
    ip: str
    port: int = 4028
    preset_id: str = "antminer_l3"
    poll_interval: int = Field(30, ge=10, le=300)


class UpdateMinerRequest(BaseModel):
    name: Optional[str] = None
    poll_interval: Optional[int] = None
    enabled: Optional[bool] = None
    preset_id: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_miners(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Miner))
    miners = result.scalars().all()
    return [_miner_to_dict(m) for m in miners]


@router.post("/")
async def add_miner(body: AddMinerRequest, session: AsyncSession = Depends(get_session)):
    existing = await session.get(Miner, body.id)
    if existing:
        raise HTTPException(400, f"Miner '{body.id}' already exists")

    miner = Miner(
        id=body.id,
        name=body.name,
        ip=body.ip,
        port=body.port,
        preset_id=body.preset_id,
        poll_interval=body.poll_interval,
    )
    session.add(miner)
    await session.commit()
    poller.add_miner(body.id, body.ip, body.port, body.preset_id, body.poll_interval)
    return _miner_to_dict(miner)


@router.get("/{miner_id}")
async def get_miner(miner_id: str, session: AsyncSession = Depends(get_session)):
    miner = await session.get(Miner, miner_id)
    if not miner:
        raise HTTPException(404, f"Miner '{miner_id}' not found")
    return _miner_to_dict(miner)


@router.patch("/{miner_id}")
async def update_miner(
    miner_id: str,
    body: UpdateMinerRequest,
    session: AsyncSession = Depends(get_session),
):
    miner = await session.get(Miner, miner_id)
    if not miner:
        raise HTTPException(404, f"Miner '{miner_id}' not found")

    if body.name is not None:
        miner.name = body.name
    if body.poll_interval is not None:
        miner.poll_interval = body.poll_interval
        poller.update_interval(miner_id, body.poll_interval)
    if body.enabled is not None:
        miner.enabled = body.enabled
        if not body.enabled:
            poller.remove_miner(miner_id)
        else:
            poller.add_miner(miner_id, miner.ip, miner.port, miner.preset_id, miner.poll_interval)
    if body.preset_id is not None:
        miner.preset_id = body.preset_id

    await session.commit()
    return _miner_to_dict(miner)


@router.delete("/{miner_id}")
async def delete_miner(miner_id: str, session: AsyncSession = Depends(get_session)):
    miner = await session.get(Miner, miner_id)
    if not miner:
        raise HTTPException(404)
    poller.remove_miner(miner_id)
    await session.delete(miner)
    await session.commit()
    return {"deleted": miner_id}


@router.post("/{miner_id}/poll")
async def poll_once(miner_id: str, session: AsyncSession = Depends(get_session)):
    miner = await session.get(Miner, miner_id)
    if not miner:
        raise HTTPException(404)
    try:
        raw = await poll_miner_async(miner.ip, miner.port, "summary")
        values = registry.extract_values(miner.preset_id, raw)
        ts = datetime.now(timezone.utc)
        await insert_reading(session, miner_id, ts, values)
        miner.last_seen = ts
        miner.last_raw_response = raw
        await session.commit()
        return {"ok": True, "values": values, "raw": raw}
    except Exception as e:
        raise HTTPException(502, str(e))


@router.get("/{miner_id}/status")
async def get_status(miner_id: str, session: AsyncSession = Depends(get_session)):
    miner = await session.get(Miner, miner_id)
    if not miner:
        raise HTTPException(404)

    readings = await get_recent_readings(session, miner_id, limit=25)
    if not readings:
        return {"status": "UNKNOWN", "message": "No telemetry data yet", "miner_id": miner_id}

    latest = readings[0]
    current_values = latest.values

    preset = registry.get_preset(miner.preset_id)
    preset_features = preset.get("features", []) if preset else []
    violations = check_rules(current_values, preset_features)
    rule_status = determine_status_from_rules(violations)

    recent_window = [r.values for r in reversed(readings)]
    baseline = get_baseline(miner_id)
    ml_result = score_reading(miner_id, current_values, recent_window)

    ml_status = ml_result.get("ml_status", "GREEN")
    if rule_status == "RED":
        final_status = "RED"
    elif ml_status == "RED":
        final_status = "RED"
    elif rule_status == "YELLOW" or ml_status == "YELLOW":
        final_status = "YELLOW"
    else:
        final_status = "GREEN"

    return {
        "miner_id": miner_id,
        "miner_name": miner.name,
        "status": final_status,
        "timestamp": latest.timestamp.isoformat(),
        "current_values": current_values,
        "rule_violations": [
            {"rule_name": v.rule_name, "message": v.message, "severity": v.severity}
            for v in violations
        ],
        "ml": ml_result,
        "last_seen": miner.last_seen.isoformat() if miner.last_seen else None,
    }


@router.post("/discover")
async def discover_fields(body: dict):
    """
    Connect to a miner and return all available numeric fields.
    Returns a real error message if miner connects but returns no data,
    instead of silently showing 0/0 features.
    """
    ip = body.get("ip")
    port = int(body.get("port", 4028))
    if not ip:
        raise HTTPException(400, "ip required")
    try:
        result = discover_all_fields(ip, port)
        numeric = result["numeric_fields"]

        # Miner connected but returned zero numeric fields
        if len(numeric) == 0:
            raw_preview = ""
            for cmd_result in result["command_results"].values():
                import json
                raw_preview = json.dumps(cmd_result)[:400]
                break
            raise HTTPException(
                422,
                f"Miner connected but returned 0 numeric fields. "
                f"This usually means cgminer api-allow is set to W:127.0.0.1 "
                f"(localhost only) and is blocking your remote connection. "
                f"Fix: ask your friend to change api-allow to W:0/0 in cgminer.conf "
                f"and restart cgminer. Raw response was: {raw_preview}"
            )

        return {
            "numeric_fields": numeric,
            "all_fields": result["all_fields"],
            "commands_available": list(result["command_results"].keys()),
            "field_count": len(numeric),
            "errors": result.get("errors", {}),
            "raw_sample": {
                k: v for k, v in list(result["command_results"].items())[:1]
            },
        }
    except HTTPException:
        raise
    except ConnectionError as e:
        raise HTTPException(502, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/{miner_id}/telemetry")
async def get_telemetry(
    miner_id: str,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    readings = await get_recent_readings(session, miner_id, limit=limit)
    return [
        {"timestamp": r.timestamp.isoformat(), "values": r.values, "poll_ok": r.poll_ok}
        for r in reversed(readings)
    ]


def _miner_to_dict(m: Miner) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "ip": m.ip,
        "port": m.port,
        "preset_id": m.preset_id,
        "poll_interval": m.poll_interval,
        "enabled": m.enabled,
        "last_seen": m.last_seen.isoformat() if m.last_seen else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
