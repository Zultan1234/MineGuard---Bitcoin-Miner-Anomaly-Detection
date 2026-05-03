"""
WebSocket Route — broadcasts unified explanation alongside telemetry.

Output format now includes:
- explanation.narrative:        human-readable string
- explanation.ranked_features:  fused SHAP+LSTM feature ranking
- explanation.confidence:       "high"/"medium"/"low"
- explanation.signature:        failure pattern match (or null)
"""
import asyncio, json, logging
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.collector.poller import poller
from backend.rules.safety_rules import (check_rules, determine_status_from_rules,
                                         compute_deviations_with_status)
from backend.ml.trainer import score_reading, get_baseline
from backend.collector.preset_registry import registry

router  = APIRouter()
logger  = logging.getLogger("ws")
_clients: set[WebSocket] = set()


async def broadcast(msg: dict):
    dead, payload = set(), json.dumps(msg, default=str)
    for ws in _clients:
        try: await ws.send_text(payload)
        except: dead.add(ws)
    _clients.difference_update(dead)


@router.websocket("/live")
async def live_feed(ws: WebSocket):
    await ws.accept(); _clients.add(ws)
    try:
        while True:
            await asyncio.sleep(20)
            await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        _clients.discard(ws)


async def on_new_reading(miner_id: str, timestamp: datetime, values: dict):
    from backend.db.timeseries import AsyncSessionLocal, insert_reading, get_recent_readings
    from backend.db.models import AnomalyEvent, Miner

    # Offline signal
    if "_offline" in values:
        await broadcast({
            "type": "telemetry", "miner_id": miner_id,
            "timestamp": timestamp.isoformat(), "status": "OFFLINE",
            "values": {}, "rule_violations": [], "if_score": None,
            "ml_anomaly": False, "severity": "offline", "offline": True,
            "deviations": [], "explanation": None,
        })
        return

    async with AsyncSessionLocal() as session:
        await insert_reading(session, miner_id, timestamp, values)

        miner = await session.get(Miner, miner_id)
        if miner:
            miner.last_seen = timestamp
            preset = registry.get_preset(miner.preset_id)
            preset_features = preset.get("features", []) if preset else []
        else:
            preset_features = []
        await session.commit()

        baseline = get_baseline(miner_id) or {}

        # Rule check
        violations  = check_rules(values, preset_features, baseline)
        rule_status = determine_status_from_rules(violations)

        # ML scoring + fusion explanation
        recent       = await get_recent_readings(session, miner_id, limit=25)
        recent_window = [r.values for r in reversed(recent)]
        ml_result    = score_reading(miner_id, values, recent_window)
        ml_status    = ml_result.get("ml_status", "GREEN")
        severity     = ml_result.get("severity", "normal")
        explanation  = ml_result.get("explanation")

        # Deviations for dashboard coloring
        deviations = compute_deviations_with_status(values, baseline)

        # Final status fusion
        if   rule_status == "RED":                                 status = "RED"
        elif ml_status   == "RED":                                 status = "RED"
        elif rule_status == "YELLOW" or ml_status == "YELLOW":     status = "YELLOW"
        else:                                                       status = "GREEN"

        # Persist anomaly events
        if status != "GREEN":
            session.add(AnomalyEvent(
                miner_id=miner_id, timestamp=timestamp, status=status,
                if_score=ml_result["isolation_forest"].get("anomaly_score"),
                lstm_error=ml_result["lstm"].get("lstm_error"),
                triggered_rules=[
                    {"rule_name": v.rule_name, "message": v.message, "severity": v.severity}
                    for v in violations
                ],
                affected_features=(
                    explanation.get("ranked_features", []) if explanation else []
                ),
                raw_values=values,
            ))
            await session.commit()

            # Telegram notification (non-blocking, rate-limited)
            try:
                from backend.notifications.telegram import send_alert
                miner_name = miner.name if miner else miner_id
                send_alert(
                    miner_id=miner_id,
                    miner_name=miner_name,
                    status=status,
                    anomaly_score=ml_result["isolation_forest"].get("anomaly_score", 0),
                    narrative=explanation.get("narrative", "") if explanation else "",
                    top_features=explanation.get("ranked_features", []) if explanation else [],
                )
            except Exception as e:
                logger.debug(f"Telegram: {e}")

    await broadcast({
        "type":            "telemetry",
        "miner_id":        miner_id,
        "timestamp":       timestamp.isoformat(),
        "status":          status,
        "values":          values,
        "rule_violations": [
            {"rule_name": v.rule_name, "message": v.message, "severity": v.severity}
            for v in violations
        ],
        "if_score":        ml_result["isolation_forest"].get("anomaly_score"),
        "ml_anomaly":      ml_result["ml_anomaly"],
        "severity":        severity,
        "offline":         False,
        "deviations":      deviations,
        "explanation":     explanation,    # NEW — unified fusion output
    })


poller.on_reading(on_new_reading)
