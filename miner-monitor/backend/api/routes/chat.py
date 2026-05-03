"""Chat API Routes — now uses Gemini 2.0 Flash instead of Ollama."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.timeseries import get_session, get_recent_readings, get_recent_events
from backend.db.models import Miner, ChatMessage
from backend.chatbot.ollama_client import ollama, build_miner_context
from backend.ml.trainer import get_baseline, score_reading
from backend.rules.safety_rules import check_rules, determine_status_from_rules
from backend.collector.preset_registry import registry

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    miner_id: str | None = None
    history: list[dict] = []

@router.post("/message")
async def send_message(body: ChatRequest, session: AsyncSession = Depends(get_session)):
    context = await _build_context(body.miner_id, session)
    messages = body.history + [{"role": "user", "content": body.message}]
    reply = await ollama.chat(messages, context)
    if body.miner_id:
        session.add(ChatMessage(miner_id=body.miner_id, role="user", content=body.message))
        session.add(ChatMessage(miner_id=body.miner_id, role="assistant", content=reply))
        await session.commit()
    return {"reply": reply}

@router.post("/stream")
async def stream_message(body: ChatRequest, session: AsyncSession = Depends(get_session)):
    context = await _build_context(body.miner_id, session)
    messages = body.history + [{"role": "user", "content": body.message}]

    async def generate():
        full = []
        async for token in ollama.stream_chat(messages, context):
            full.append(token)
            yield f"data: {token}\n\n"
        if body.miner_id and full:
            from backend.db.timeseries import AsyncSessionLocal
            async with AsyncSessionLocal() as s:
                s.add(ChatMessage(miner_id=body.miner_id, role="user", content=body.message))
                s.add(ChatMessage(miner_id=body.miner_id, role="assistant", content="".join(full)))
                await s.commit()
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@router.get("/history/{miner_id}")
async def get_history(miner_id: str, limit: int = 50, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(ChatMessage).where(ChatMessage.miner_id == miner_id)
        .order_by(ChatMessage.timestamp).limit(limit)
    )
    msgs = result.scalars().all()
    return [{"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()} for m in msgs]

@router.get("/status")
async def chatbot_status():
    info = await ollama.get_model_info()
    return {
        "available": info["available"],
        "model": info["model"],
        "provider": info["provider"],
        "api_key_set": info["api_key_set"],
        "setup_url": info["setup_url"],
        "setup_instructions": None if info["api_key_set"] else {
            "step1": "Go to https://aistudio.google.com/apikey",
            "step2": "Sign in with Google (free, no credit card)",
            "step3": "Click 'Create API Key'",
            "step4": "Set env var: set GEMINI_API_KEY=your_key",
            "step5": "Or save to file: backend/data/gemini_key.txt",
            "step6": "Restart the backend server",
        }
    }

async def _build_context(miner_id: str | None, session: AsyncSession) -> str:
    if not miner_id:
        return "No specific miner selected. Answer general mining hardware questions."
    miner = await session.get(Miner, miner_id)
    if not miner:
        return f"Miner {miner_id} not found."
    readings = await get_recent_readings(session, miner_id, limit=25)
    events = await get_recent_events(session, miner_id, limit=5)
    current_values = readings[0].values if readings else {}
    preset = registry.get_preset(miner.preset_id)
    violations = check_rules(current_values, preset.get("features", []) if preset else [])
    rule_status = determine_status_from_rules(violations)
    recent_window = [r.values for r in reversed(readings)]
    ml_result = score_reading(miner_id, current_values, recent_window)
    if rule_status == "RED": status = "RED"
    elif ml_result["ml_anomaly"] or rule_status == "YELLOW": status = "YELLOW"
    else: status = "GREEN"
    return build_miner_context(
        miner_id=miner_id, miner_name=miner.name, status=status,
        current_values=current_values,
        if_score=ml_result["isolation_forest"].get("anomaly_score"),
        lstm_error=ml_result["lstm"].get("lstm_error"),
        triggered_rules=[{"severity": v.severity, "message": v.message} for v in violations],
        deviations=ml_result.get("deviations", []),
        baseline=get_baseline(miner_id),
        recent_events=[{"timestamp": e.timestamp.isoformat(), "status": e.status} for e in events],
    )
