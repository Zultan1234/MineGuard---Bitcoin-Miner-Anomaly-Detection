"""
Preset Registry
CRITICAL: cgminer returns "GHS 5s": "261.471" as a STRING.
_try_float() handles conversion everywhere.
"""
import json, logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger("preset_registry")
PRESETS_DIR = Path(__file__).parent.parent / "presets"

# Antminer L3+ preset includes ALL fields from the real stats response
BUILTIN_PRESETS = {
    "antminer_l3": {
        "name": "Antminer L3/L3+",
        "firmware": "cgminer 4.9.x",
        "description": "Litecoin ASIC ~504 MH/s — includes all stats fields",
        "features": [
            # Summary fields
            {"raw_key":"GHS 5s",          "label":"GHS 5s",           "unit":"GH/s","warn_high":None,"warn_low":0.0},
            {"raw_key":"GHS av",           "label":"GHS av",           "unit":"GH/s","warn_high":None,"warn_low":0.0},
            {"raw_key":"Hardware Errors",  "label":"Hardware Errors",  "unit":"count","warn_high":200,"warn_low":None},
            {"raw_key":"Device Rejected%", "label":"Device Rejected%", "unit":"%","warn_high":30.0,"warn_low":None},
            # Stats — temperatures (PCB inlet)
            {"raw_key":"temp1",  "label":"temp1",  "unit":"C","warn_high":75.0,"warn_low":None},
            {"raw_key":"temp2",  "label":"temp2",  "unit":"C","warn_high":75.0,"warn_low":None},
            {"raw_key":"temp3",  "label":"temp3",  "unit":"C","warn_high":75.0,"warn_low":None},
            {"raw_key":"temp4",  "label":"temp4",  "unit":"C","warn_high":75.0,"warn_low":None},
            # Stats — temperatures (chip exhaust — hotter)
            {"raw_key":"temp2_1","label":"temp2_1","unit":"C","warn_high":85.0,"warn_low":None},
            {"raw_key":"temp2_2","label":"temp2_2","unit":"C","warn_high":85.0,"warn_low":None},
            {"raw_key":"temp2_3","label":"temp2_3","unit":"C","warn_high":85.0,"warn_low":None},
            {"raw_key":"temp2_4","label":"temp2_4","unit":"C","warn_high":85.0,"warn_low":None},
            {"raw_key":"temp_max","label":"temp_max","unit":"C","warn_high":85.0,"warn_low":None},
            # Stats — fans
            {"raw_key":"fan1","label":"fan1","unit":"RPM","warn_high":None,"warn_low":1200},
            {"raw_key":"fan2","label":"fan2","unit":"RPM","warn_high":None,"warn_low":1200},
            # Stats — frequency
            {"raw_key":"frequency", "label":"frequency", "unit":"MHz","warn_high":None,"warn_low":None},
            {"raw_key":"frequency1","label":"frequency1","unit":"MHz","warn_high":None,"warn_low":None},
            {"raw_key":"frequency2","label":"frequency2","unit":"MHz","warn_high":None,"warn_low":None},
            {"raw_key":"frequency3","label":"frequency3","unit":"MHz","warn_high":None,"warn_low":None},
            {"raw_key":"frequency4","label":"frequency4","unit":"MHz","warn_high":None,"warn_low":None},
            # Stats — per-board hashrate
            {"raw_key":"chain_rate1","label":"chain_rate1","unit":"GH/s","warn_high":None,"warn_low":None},
            {"raw_key":"chain_rate2","label":"chain_rate2","unit":"GH/s","warn_high":None,"warn_low":None},
            {"raw_key":"chain_rate3","label":"chain_rate3","unit":"GH/s","warn_high":None,"warn_low":None},
            {"raw_key":"chain_rate4","label":"chain_rate4","unit":"GH/s","warn_high":None,"warn_low":None},
            # Stats — active chips
            {"raw_key":"chain_acn1","label":"chain_acn1","unit":"chips","warn_high":None,"warn_low":60},
            {"raw_key":"chain_acn2","label":"chain_acn2","unit":"chips","warn_high":None,"warn_low":60},
            {"raw_key":"chain_acn3","label":"chain_acn3","unit":"chips","warn_high":None,"warn_low":60},
            {"raw_key":"chain_acn4","label":"chain_acn4","unit":"chips","warn_high":None,"warn_low":60},
            # Stats — HW errors per board
            {"raw_key":"chain_hw1","label":"chain_hw1","unit":"err","warn_high":50,"warn_low":None},
            {"raw_key":"chain_hw2","label":"chain_hw2","unit":"err","warn_high":50,"warn_low":None},
            {"raw_key":"chain_hw3","label":"chain_hw3","unit":"err","warn_high":50,"warn_low":None},
            {"raw_key":"chain_hw4","label":"chain_hw4","unit":"err","warn_high":50,"warn_low":None},
            # Stats — power
            {"raw_key":"chain_power1","label":"chain_power1","unit":"W","warn_high":None,"warn_low":None},
            {"raw_key":"chain_power2","label":"chain_power2","unit":"W","warn_high":None,"warn_low":None},
            {"raw_key":"chain_power3","label":"chain_power3","unit":"W","warn_high":None,"warn_low":None},
            {"raw_key":"chain_power4","label":"chain_power4","unit":"W","warn_high":None,"warn_low":None},
            {"raw_key":"chain_power", "label":"chain_power", "unit":"W","warn_high":None,"warn_low":None},
            # Stats — voltage
            {"raw_key":"voltage1","label":"voltage1","unit":"V","warn_high":10.6,"warn_low":9.5},
            {"raw_key":"voltage2","label":"voltage2","unit":"V","warn_high":10.6,"warn_low":9.5},
            {"raw_key":"voltage3","label":"voltage3","unit":"V","warn_high":10.6,"warn_low":9.5},
            {"raw_key":"voltage4","label":"voltage4","unit":"V","warn_high":10.6,"warn_low":9.5},
            # Stats — misc
            {"raw_key":"Device Hardware%","label":"Device Hardware%","unit":"%","warn_high":5.0,"warn_low":None},
            {"raw_key":"no_matching_work","label":"no_matching_work","unit":"count","warn_high":50,"warn_low":None},
            {"raw_key":"miner_count","label":"miner_count","unit":"boards","warn_high":None,"warn_low":None},
        ]
    },
    "antminer_s9": {
        "name": "Antminer S9",
        "firmware": "bmminer / cgminer",
        "description": "Bitcoin ASIC ~13.5 TH/s",
        "features": [
            {"raw_key":"GHS 5s","label":"GHS 5s","unit":"GH/s","warn_high":None,"warn_low":0.0},
            {"raw_key":"GHS av","label":"GHS av","unit":"GH/s","warn_high":None,"warn_low":0.0},
            {"raw_key":"Hardware Errors","label":"Hardware Errors","unit":"count","warn_high":200,"warn_low":None},
            {"raw_key":"Device Rejected%","label":"Device Rejected%","unit":"%","warn_high":15.0,"warn_low":None},
            {"raw_key":"Temperature","label":"Temperature","unit":"C","warn_high":90.0,"warn_low":None},
            {"raw_key":"fan1","label":"fan1","unit":"RPM","warn_high":None,"warn_low":1500},
            {"raw_key":"fan2","label":"fan2","unit":"RPM","warn_high":None,"warn_low":1500},
        ]
    },
    "antminer_s19": {
        "name": "Antminer S19 / S19 Pro",
        "firmware": "bmminer 2.x",
        "description": "Bitcoin ASIC ~95-110 TH/s",
        "features": [
            {"raw_key":"GHS 5s","label":"GHS 5s","unit":"GH/s","warn_high":None,"warn_low":0.0},
            {"raw_key":"GHS av","label":"GHS av","unit":"GH/s","warn_high":None,"warn_low":0.0},
            {"raw_key":"Hardware Errors","label":"Hardware Errors","unit":"count","warn_high":500,"warn_low":None},
            {"raw_key":"Device Rejected%","label":"Device Rejected%","unit":"%","warn_high":10.0,"warn_low":None},
            {"raw_key":"temp1","label":"temp1","unit":"C","warn_high":95.0,"warn_low":None},
            {"raw_key":"temp2","label":"temp2","unit":"C","warn_high":95.0,"warn_low":None},
            {"raw_key":"temp3","label":"temp3","unit":"C","warn_high":95.0,"warn_low":None},
            {"raw_key":"fan1","label":"fan1","unit":"RPM","warn_high":None,"warn_low":2000},
            {"raw_key":"fan2","label":"fan2","unit":"RPM","warn_high":None,"warn_low":2000},
        ]
    },
    "antminer_s21": {
        "name": "Antminer S21 / S21+",
        "firmware": "bmminer 3.x",
        "description": "Bitcoin ASIC ~200 TH/s",
        "features": [
            {"raw_key":"GHS 5s","label":"GHS 5s","unit":"GH/s","warn_high":None,"warn_low":0.0},
            {"raw_key":"GHS av","label":"GHS av","unit":"GH/s","warn_high":None,"warn_low":0.0},
            {"raw_key":"Hardware Errors","label":"Hardware Errors","unit":"count","warn_high":500,"warn_low":None},
            {"raw_key":"Device Rejected%","label":"Device Rejected%","unit":"%","warn_high":10.0,"warn_low":None},
            {"raw_key":"temp_chip_top","label":"temp_chip_top","unit":"C","warn_high":100.0,"warn_low":None},
            {"raw_key":"temp_chip_bot","label":"temp_chip_bot","unit":"C","warn_high":100.0,"warn_low":None},
            {"raw_key":"fan1","label":"fan1","unit":"RPM","warn_high":None,"warn_low":2500},
            {"raw_key":"fan2","label":"fan2","unit":"RPM","warn_high":None,"warn_low":2500},
        ]
    },
    "whatsminer_m30": {
        "name": "Whatsminer M30S / M30S+",
        "firmware": "bosminer / btminer",
        "description": "MicroBT Bitcoin ASIC ~88-112 TH/s",
        "features": [
            {"raw_key":"GHS 5s","label":"GHS 5s","unit":"GH/s","warn_high":None,"warn_low":0.0},
            {"raw_key":"GHS av","label":"GHS av","unit":"GH/s","warn_high":None,"warn_low":0.0},
            {"raw_key":"Hardware Errors","label":"Hardware Errors","unit":"count","warn_high":500,"warn_low":None},
            {"raw_key":"Temp","label":"Temp","unit":"C","warn_high":95.0,"warn_low":None},
            {"raw_key":"Fan Speed In","label":"Fan Speed In","unit":"RPM","warn_high":None,"warn_low":1500},
            {"raw_key":"Fan Speed Out","label":"Fan Speed Out","unit":"RPM","warn_high":None,"warn_low":1500},
        ]
    },
}

def _try_float(v):
    """Convert value to float including string-encoded numbers like '261.471'."""
    if isinstance(v, bool): return None
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, str):
        try: return float(v.strip())
        except: return None
    return None

def _flatten_response(raw_api_data: dict) -> dict:
    """Flatten cgminer response into {field_name: value}, skipping STATUS section."""
    flat = {}
    SKIP = {"STATUS","status","CGMiner","Miner","CompileTime","Type",
            "chain_acs1","chain_acs2","chain_acs3","chain_acs4"}
    def walk(obj, skip=False):
        if isinstance(obj, dict):
            for k, v in obj.items():
                s = skip or k in SKIP
                if not s:
                    if isinstance(v, (int,float,str,bool)):
                        if k not in flat: flat[k] = v
                    elif isinstance(v, (dict,list)): walk(v, s)
        elif isinstance(obj, list):
            for item in obj: walk(item, skip)
    walk(raw_api_data)
    return flat

class PresetRegistry:
    def __init__(self):
        self._presets = dict(BUILTIN_PRESETS)
        self._load_user_presets()

    def _load_user_presets(self):
        if not PRESETS_DIR.exists(): return
        for f in PRESETS_DIR.glob("*.json"):
            try:
                with open(f) as fp: data = json.load(fp)
                if f.stem not in self._presets: self._presets[f.stem] = data
            except Exception as e: logger.warning(f"Could not load preset {f}: {e}")

    def list_presets(self):
        return [{"id":k,"name":v["name"],"description":v.get("description","")} for k,v in self._presets.items()]

    def get_preset(self, preset_id): return self._presets.get(preset_id)

    def save_user_preset(self, preset_id: str, preset_data: dict):
        PRESETS_DIR.mkdir(exist_ok=True)
        with open(PRESETS_DIR / f"{preset_id}.json", "w") as f:
            json.dump(preset_data, f, indent=2)
        self._presets[preset_id] = preset_data

    def extract_values(self, preset_id: str, raw_api_data: dict) -> dict:
        """Extract {label: float} for every preset feature. Handles string-encoded numbers."""
        preset = self.get_preset(preset_id)
        if not preset: return {}
        flat = _flatten_response(raw_api_data)
        result = {}
        for feat in preset.get("features", []):
            raw_key = feat.get("raw_key","")
            label   = feat.get("label", raw_key)
            if not raw_key: continue
            if raw_key in flat:
                v = _try_float(flat[raw_key])
                if v is not None: result[label] = v
        return result

registry = PresetRegistry()
