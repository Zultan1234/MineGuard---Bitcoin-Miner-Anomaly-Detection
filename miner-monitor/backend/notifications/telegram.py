"""
Telegram Notifications — sends alerts to your phone.

Setup (2 minutes):
  1. Open Telegram, search @BotFather, send /newbot, get BOT TOKEN
  2. Search @userinfobot, send /start, get your CHAT ID
  3. Either set env vars:
       set TELEGRAM_BOT_TOKEN=your_token
       set TELEGRAM_CHAT_ID=your_chat_id
     Or save to files:
       backend/data/telegram_token.txt
       backend/data/telegram_chat_id.txt
  4. Restart the backend

Only sends on YELLOW/RED. Rate-limited: 1 per miner per 5 minutes.
"""
import os, time, logging, json
import urllib.request
from pathlib import Path

logger = logging.getLogger("notifications.telegram")
DATA_DIR = Path(__file__).parent.parent / "data"
_last_alert: dict = {}
COOLDOWN = 300  # 5 minutes

def _load(filename):
    p = DATA_DIR / filename
    return p.read_text().strip() if p.exists() else ""

def _config():
    token = os.environ.get("TELEGRAM_BOT_TOKEN","") or _load("telegram_token.txt")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID","") or _load("telegram_chat_id.txt")
    return token, chat_id

def is_configured():
    t, c = _config()
    return bool(t and c)

def send_alert(miner_id, miner_name, status, anomaly_score=0, narrative="", top_features=None):
    if status not in ("YELLOW","RED"): return False
    token, chat_id = _config()
    if not token or not chat_id: return False

    now = time.time()
    if now - _last_alert.get(miner_id, 0) < COOLDOWN: return False

    icon = "🔴" if status == "RED" else "🟡"
    lines = [f"{icon} *{miner_name}* — {status}", f"Score: {anomaly_score:.1%}"]
    if narrative: lines.append(f"\n{narrative}")
    if top_features:
        for f in top_features[:3]:
            pct = f.get("pct_deviation",0)
            sign = "+" if pct > 0 else ""
            lines.append(f"  • {f.get('feature','')}: {sign}{pct:.1f}%")

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id":chat_id,"text":"\n".join(lines),"parse_mode":"Markdown"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read())
            if res.get("ok"):
                _last_alert[miner_id] = now
                logger.info(f"Telegram sent for {miner_id}: {status}")
                return True
    except Exception as e:
        logger.warning(f"Telegram failed: {e}")
    return False

def get_status():
    t, c = _config()
    return {"configured": bool(t and c), "bot_token_set": bool(t), "chat_id_set": bool(c)}
