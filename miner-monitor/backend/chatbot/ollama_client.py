"""
LLM Chatbot — Gemini 2.0 Flash via Google AI Studio
Free tier: ~1500 requests/day, no credit card needed.
Get API key at: https://aistudio.google.com/apikey (free, 2 minutes)

Falls back to a helpful message if no API key is set.
"""
import json
import logging
import urllib.request
import urllib.error
import os
from typing import AsyncIterator
from backend.ml.baseline import summarize_baseline_for_chatbot

logger = logging.getLogger("chatbot")

# Gemini API settings
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_STREAM_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent"

# Read API key from environment variable or config file
def _get_api_key() -> str:
    # Try environment variable first
    key = os.environ.get("GEMINI_API_KEY", "")
    if key: return key
    # Try config file
    config_path = os.path.join(os.path.dirname(__file__), "..", "data", "gemini_key.txt")
    try:
        with open(config_path) as f:
            return f.read().strip()
    except Exception:
        return ""

SYSTEM_PROMPT = """You are an expert ASIC cryptocurrency mining hardware diagnostics assistant.
You monitor mining rigs in real time and help operators understand and fix issues.

You have deep knowledge of:
- Antminer firmware (cgminer, bmminer) API fields and their meaning
- ASIC chip behavior: hashrate degradation, thermal throttling, chain failures
- Fan failure signatures and temperature correlation
- Pool connectivity issues vs hardware issues (rejection rates)
- Normal operating ranges for Antminer L3, S9, S19, S21+, Whatsminer M30

When diagnosing:
1. Cite the specific metric values that triggered the alert
2. Distinguish hardware vs firmware vs connectivity issues
3. Give numbered actionable steps (most likely fix first)
4. Be concise — operators need fast answers
5. If unsure, say so — never fabricate data

Current miner context:
{miner_context}

Respond in plain text. No markdown formatting."""


def build_miner_context(miner_id, miner_name, status, current_values,
                        if_score, lstm_error, triggered_rules,
                        deviations, baseline, recent_events):
    lines = [
        f"Miner: {miner_name} (ID: {miner_id})",
        f"Status: {status}",
        "",
    ]
    if current_values:
        lines.append("Current readings:")
        for feat, val in list(current_values.items())[:15]:
            if not str(feat).startswith("_"):
                lines.append(f"  {feat}: {val}")
        lines.append("")
    if if_score is not None:
        lines.append(f"Isolation Forest anomaly score: {if_score:.4f}")
    if lstm_error is not None:
        lines.append(f"LSTM reconstruction error: {lstm_error:.6f}")
    if triggered_rules:
        lines.append("Active alerts:")
        for r in triggered_rules:
            lines.append(f"  [{r.get('severity','').upper()}] {r.get('message','')}")
        lines.append("")
    if deviations:
        lines.append("Features outside normal range (z > 2.0):")
        for d in deviations:
            lines.append(f"  {d['feature']}: current={d['current']}, baseline={d['baseline_mean']}, z={d['z_score']}")
        lines.append("")
    if baseline:
        lines.append(summarize_baseline_for_chatbot(baseline))
    return "\n".join(lines)


async def _call_gemini(messages: list[dict], miner_context: str) -> str:
    """Call Gemini API synchronously (runs in thread pool for async compat)."""
    api_key = _get_api_key()
    if not api_key:
        return (
            "Gemini API key not configured.\n\n"
            "To enable the chatbot:\n"
            "1. Go to https://aistudio.google.com/apikey\n"
            "2. Click 'Create API Key' (free, no credit card)\n"
            "3. Copy the key\n"
            "4. Either:\n"
            "   a) Set environment variable: set GEMINI_API_KEY=your_key_here\n"
            "   b) Save to file: backend/data/gemini_key.txt\n"
            "5. Restart the backend server"
        )

    system = SYSTEM_PROMPT.format(miner_context=miner_context)

    # Build contents for Gemini format
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1024,
        }
    }

    url = f"{GEMINI_API_URL}?key={api_key}"
    data = json.dumps(payload).encode()

    try:
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
        return body["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if "API_KEY_INVALID" in error_body or "400" in str(e.code):
            return "Invalid Gemini API key. Please check your key at https://aistudio.google.com/apikey"
        if "429" in str(e.code):
            return "Gemini rate limit reached. You have exceeded the free tier limit for today. Try again tomorrow or upgrade at https://aistudio.google.com"
        return f"Gemini API error {e.code}: {error_body[:200]}"
    except Exception as e:
        return f"Error calling Gemini: {e}"


class GeminiClient:
    """Async client for Gemini 2.0 Flash."""

    async def is_available(self) -> bool:
        return bool(_get_api_key())

    async def get_model_info(self) -> dict:
        key = _get_api_key()
        return {
            "available": bool(key),
            "model": "gemini-2.5-flash",
            "provider": "Google AI Studio",
            "api_key_set": bool(key),
            "setup_url": "https://aistudio.google.com/apikey",
        }

    async def chat(self, messages: list[dict], miner_context: str) -> str:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: _call_gemini_sync(messages, miner_context))

    async def stream_chat(self, messages: list[dict], miner_context: str) -> AsyncIterator[str]:
        """Stream tokens from Gemini."""
        # Gemini streaming requires SSE parsing — for simplicity we get the
        # full response and yield it in chunks to simulate streaming
        response = await self.chat(messages, miner_context)
        words = response.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            import asyncio
            await asyncio.sleep(0.02)  # small delay for streaming effect


def _call_gemini_sync(messages, miner_context):
    """Synchronous version for thread pool."""
    import asyncio
    # We need to run without event loop
    api_key = _get_api_key()
    if not api_key:
        return (
            "Gemini API key not configured.\n\n"
            "To enable the chatbot:\n"
            "1. Go to https://aistudio.google.com/apikey\n"
            "2. Sign in with Google (free)\n"
            "3. Click 'Create API Key'\n"
            "4. Set environment variable before starting the server:\n"
            "   Windows:  set GEMINI_API_KEY=your_key_here\n"
            "   Mac/Linux: export GEMINI_API_KEY=your_key_here\n"
            "5. Or save the key to: backend/data/gemini_key.txt\n"
            "6. Restart the server"
        )

    system = SYSTEM_PROMPT.format(miner_context=miner_context)
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024}
    }

    url = f"{GEMINI_API_URL}?key={api_key}"
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
        return body["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        if "API_KEY_INVALID" in err: return "Invalid Gemini API key. Check https://aistudio.google.com/apikey"
        if "429" in str(e.code): return "Rate limit reached. Free tier allows ~1500 requests/day. Try again tomorrow."
        return f"Gemini API error {e.code}: {err[:200]}"
    except Exception as e:
        return f"Error: {e}"


# Singleton — replaces ollama
ollama = GeminiClient()
