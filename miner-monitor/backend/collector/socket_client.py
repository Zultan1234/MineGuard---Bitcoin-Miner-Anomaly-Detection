"""
Miner Client
Uses the exact TCP approach that works with Antminer L3+ Hiveon firmware:
- No socket.shutdown() — L3+ closes early if we do
- Larger recv buffer (65536)
- 0.2s sleep before reading
- Regex fix for missing comma between STATS array objects (Hiveon firmware bug)
- String-encoded numbers handled ("GHS 5s": "261.471")

Two modes auto-detected:
  Direct TCP  — connects to cgminer port 4028
  HTTP bridge — connects to bridge.py running on PC near miner
"""
import socket, json, asyncio, re, time
import urllib.request, urllib.error, urllib.parse

DEFAULT_PORT    = 4028
DEFAULT_TIMEOUT = 10


class MinerOfflineError(ConnectionError):
    """Miner reachable but returned no data — it is turned off."""
    pass


def _try_float(v):
    if isinstance(v, bool): return None
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, str):
        try: return float(v.strip())
        except: return None
    return None


def _is_http_bridge(ip, port, timeout=5):
    try:
        with urllib.request.urlopen(
            urllib.request.Request(f"http://{ip}:{port}/",
            headers={"User-Agent": "mm/1"}), timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True
    except:
        return False


def _query_http_bridge(ip, port, command, timeout=DEFAULT_TIMEOUT):
    url = f"http://{ip}:{port}/api?cmd={urllib.parse.quote(command)}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "mm/1"}),
            timeout=timeout) as r:
            body = r.read().decode(errors="replace").strip()
    except urllib.error.URLError as e:
        raise ConnectionError(f"Bridge unreachable {ip}:{port} — {e.reason}")
    except Exception as e:
        raise ConnectionError(f"Bridge error: {e}")

    try:
        outer = json.loads(body)
    except:
        try:
            return json.loads(body.replace("\x00", "").strip())
        except:
            raise ValueError(f"Unparseable bridge response: {body[:200]}")

    raw = outer.get("response", "")
    if isinstance(raw, dict): return raw
    if not raw: raise MinerOfflineError(f"Bridge empty response — miner at {ip} may be off")
    cleaned = raw.replace("\x00", "").strip()
    try:
        return json.loads(cleaned)
    except:
        raise ValueError(f"Bad inner JSON: {cleaned[:200]}")


def _query_tcp(ip, port, command, timeout=DEFAULT_TIMEOUT):
    """
    Query cgminer directly via TCP.
    L3+ Hiveon quirks handled:
    1. Do NOT call socket.shutdown() — firmware closes early
    2. Use 65536 byte buffer
    3. Sleep 0.2s before reading
    4. Fix missing comma between STATS array objects (firmware JSON bug)
    """
    raw = b""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, port))
            s.sendall(json.dumps({"command": command}).encode())
            # Do NOT shutdown — L3+ firmware closes early if we do
            time.sleep(0.2)
            while True:
                try:
                    chunk = s.recv(65536)
                    if not chunk: break
                    raw += chunk
                except socket.timeout:
                    break  # no more data
    except socket.timeout:
        raise ConnectionError(f"Miner {ip}:{port} timed out")
    except ConnectionRefusedError:
        raise ConnectionError(f"Refused {ip}:{port}")
    except OSError as e:
        raise ConnectionError(f"Cannot reach {ip}:{port} — {e}")

    text = raw.decode(errors="replace").replace("\x00", "").strip()
    if not text:
        raise MinerOfflineError(f"Miner {ip}:{port} connected but sent no data")

    # Fix Hiveon L3+ firmware bug: missing comma between STATS array objects
    # e.g. }{ -> },{
    text = re.sub(r'}\s*{', '},{', text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Bad JSON: {e} — {text[:300]}")


def poll_miner_sync(ip, port=DEFAULT_PORT, command="summary", use_http=None):
    if use_http is None:
        use_http = _is_http_bridge(ip, port)
    return _query_http_bridge(ip, port, command) if use_http else _query_tcp(ip, port, command)


async def poll_miner_async(ip, port=DEFAULT_PORT, command="summary", use_http=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: poll_miner_sync(ip, port, command, use_http))


def _extract_section_fields(data: dict, section_key: str) -> dict:
    """
    Extract every numeric/string field from a cgminer section list.
    Handles STATS section which has 2 items:
      item[0] = firmware metadata (CGMiner, Miner, Type, etc.) — skip
      item[1] = actual data (temp, fan, chain, etc.) — extract

    Fields to skip:
    - Metadata strings (CGMiner, Type, CompileTime, etc.)
    - Internal counters (id, When, Code, Elapsed)
    - Long chip status strings (chain_acs1-4)
    - The "STATS" integer field inside item[1] (value=0, not useful)
    """
    SKIP = {
        "id", "When", "Code", "Elapsed", "Description", "Msg", "STATUS",
        "CGMiner", "Miner", "CompileTime", "Type", "ID", "STATS",
        "chain_acs1", "chain_acs2", "chain_acs3", "chain_acs4",
        "chain_acs5", "chain_acs6",
        "Min", "Max", "Wait", "Calls", "fan_num", "temp_num",
    }
    result = {}
    section = data.get(section_key, [])
    if not isinstance(section, list):
        return result

    for item in section:
        if not isinstance(item, dict):
            continue
        # Skip firmware info items (they have Type/CGMiner but no temp/fan)
        if "CGMiner" in item or "CompileTime" in item:
            continue
        for k, v in item.items():
            if k in SKIP:
                continue
            if k not in result:
                result[k] = v
    return result


def discover_all_fields(ip, port=DEFAULT_PORT, use_http=None):
    """
    Query summary + stats + devs + pools.
    Returns all numeric fields including string-encoded numbers.
    Temperature, fan, frequency, voltage, chip count all come from stats command.
    """
    if use_http is None:
        use_http = _is_http_bridge(ip, port)

    cmd_results, all_fields, errors = {}, {}, {}

    # summary — required
    r = poll_miner_sync(ip, port, "summary", use_http)
    cmd_results["summary"] = r
    all_fields.update(_extract_section_fields(r, "SUMMARY"))

    # stats — temp, fan, frequency, voltage, chip count, per-board hashrate
    try:
        r = poll_miner_sync(ip, port, "stats", use_http)
        cmd_results["stats"] = r
        for k, v in _extract_section_fields(r, "STATS").items():
            if k not in all_fields:
                all_fields[k] = v
    except Exception as e:
        errors["stats"] = str(e)

    # devs — optional
    try:
        r = poll_miner_sync(ip, port, "devs", use_http)
        cmd_results["devs"] = r
        for k, v in _extract_section_fields(r, "DEVS").items():
            if k not in all_fields:
                all_fields[k] = v
    except Exception as e:
        errors["devs"] = str(e)

    # pools — optional
    try:
        r = poll_miner_sync(ip, port, "pools", use_http)
        cmd_results["pools"] = r
        for k, v in _extract_section_fields(r, "POOLS").items():
            if k not in all_fields:
                all_fields[k] = v
    except Exception as e:
        errors["pools"] = str(e)

    # Convert to numeric — handles string-encoded floats like "65.279"
    SKIP_K = {"id", "When", "Code", "Elapsed", "STATUS", "Description", "Msg", "Min", "Max"}
    numeric = {}
    for k, v in all_fields.items():
        if k in SKIP_K:
            continue
        fv = _try_float(v)
        if fv is not None:
            numeric[k] = fv

    return {
        "command_results": cmd_results,
        "numeric_fields":  numeric,
        "all_fields":      all_fields,
        "errors":          errors,
        "mode":            "http_bridge" if use_http else "tcp_direct",
    }


def extract_key_fields(raw_summary):
    summary = (raw_summary.get("SUMMARY") or [{}])[0]
    s = {}
    for key in ["GHS 5s", "MHS 5s", "GH/S 5s", "TH/S 5s"]:
        if key in summary:
            v = _try_float(summary[key])
            if v is not None:
                if "MHS" in key: v /= 1000
                elif "TH/S" in key: v *= 1000
                s["hashrate_ghs"] = v
                break
    for key in ["GHS av", "MHS av", "GH/S av"]:
        if key in summary:
            v = _try_float(summary[key])
            if v is not None:
                if "MHS" in key: v /= 1000
                s["hashrate_avg_ghs"] = v
                break
    s["accepted"]            = int(summary.get("Accepted", 0) or 0)
    s["rejected"]            = int(summary.get("Rejected", 0) or 0)
    s["hardware_errors"]     = int(summary.get("Hardware Errors", 0) or 0)
    s["device_rejected_pct"] = float(_try_float(summary.get("Device Rejected%", 0)) or 0)
    s["elapsed_seconds"]     = int(summary.get("Elapsed", 0) or 0)
    return s
