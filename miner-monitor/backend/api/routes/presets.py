"""
Presets API Routes
List built-in presets, save custom user presets.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.collector.preset_registry import registry

router = APIRouter()


class SavePresetRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    firmware: str = "custom"
    features: list[dict]


@router.get("/")
async def list_presets():
    return registry.list_presets()


@router.get("/{preset_id}")
async def get_preset(preset_id: str):
    preset = registry.get_preset(preset_id)
    if not preset:
        raise HTTPException(404, f"Preset '{preset_id}' not found")
    return preset


@router.post("/")
async def save_preset(body: SavePresetRequest):
    registry.save_user_preset(body.id, {
        "name": body.name,
        "description": body.description,
        "firmware": body.firmware,
        "features": body.features,
    })
    return {"saved": body.id}
