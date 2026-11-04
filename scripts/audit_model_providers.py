"""Phase 01 - Model Provider Audit & Verification Suite."""
import requests
import json
import time
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STREAM_URL = "http://127.0.0.1:8000/api/v1/conversations/turns:stream"

PROVIDERS_TO_AUDIT = [
    {"mode": "xkiro", "name": "XKiro AI", "model": "qwen/qwen3.8-max:free"},
    {"mode": "apmix", "name": "APMIX.AI", "model": "claude-sonnet-4-6-free"},
    {"mode": "oxion", "name": "Oxion AI", "model": "claude-fable-5.1"},
    {"mode": "gemini", "name": "Google Gemini", "model": "gemini-3.5-flash"},
    {"mode": "claude", "name": "Anthropic Claude", "model": "claude-sonnet-4-6"},
    {"mode": "agent-router", "name": "Agent Router", "model": "agnes-2.5-flash"},
    {"mode": "codecraft", "name": "CodeCraft AI", "model": "claude-fable-5"},
    {"mode": "seekai", "name": "SeekAI", "model": "glm-5.3-flash"},
    {"mode": "tokentable", "name": "TokenTable", "model": "auto"},
    {"mode": "cavoti", "name": "Cavoti AI", "model": "claude-fable-5"},
]

def audit_provider(entry: dict) -> dict:
    mode = entry["mode"]
    name = entry["name"]
    model = entry["model"]
    print(f"\n--- Auditing [{name}] (mode: {mode}, model: {model}) ---")

    payload = {
        "sessionId": f"audit-{mode}-{int(time.time()*1000)}",
        "text": "Ping. Reply with one word: 'Pong'.",
        "providerMode": mode,
        "brainModel": model
    }

    t0 = time.time()
    ttfb = None
    deltas = []
    error = None
    status_code = None

    try:
        with requests.post(STREAM_URL, json=payload, stream=True, timeout=25) as r:
            status_code = r.status_code
            if r.status_code != 200:
                error = f"HTTP {r.status_code}: {r.text[:200]}"
                print(f" -> Result: HTTP Error ({r.status_code})")
                return {
                    "mode": mode,
                    "name": name,
                    "model": model,
                    "status": "FAIL",
                    "http_status": status_code,
                    "ttfb_s": None,
                    "total_time_s": round(time.time() - t0, 2),
                    "error": error
                }

            for line in r.iter_lines():
                if line:
                    decoded = line.decode("utf-8", errors="replace")
                    try:
                        data = json.loads(decoded)
                        ev_type = data.get("type")
                        if ev_type == "text.delta":
                            if ttfb is None:
                                ttfb = time.time() - t0
                            deltas.append(data.get("delta", ""))
                        elif ev_type == "error":
                            error = data.get("error") or data.get("message")
                    except Exception:
                        pass
        total_time = time.time() - t0
        full_text = "".join(deltas).strip()

        if error:
            print(f" -> Result: FAILED with error: {error}")
            return {
                "mode": mode,
                "name": name,
                "model": model,
                "status": "FAIL",
                "http_status": status_code,
                "ttfb_s": round(ttfb, 3) if ttfb else None,
                "total_time_s": round(total_time, 2),
                "error": error
            }

        if full_text:
            print(f" -> Result: SUCCESS | TTFB: {ttfb:.2f}s | Total: {total_time:.2f}s")
            print(f" -> Output snippet: {full_text[:80]}")
            return {
                "mode": mode,
                "name": name,
                "model": model,
                "status": "PASS",
                "http_status": status_code,
                "ttfb_s": round(ttfb, 3) if ttfb else None,
                "total_time_s": round(total_time, 2),
                "output_snippet": full_text[:120],
                "error": None
            }
        else:
            print(f" -> Result: EMPTY RESPONSE (Total time: {total_time:.2f}s)")
            return {
                "mode": mode,
                "name": name,
                "model": model,
                "status": "EMPTY",
                "http_status": status_code,
                "ttfb_s": None,
                "total_time_s": round(total_time, 2),
                "error": "No text deltas received"
            }
    except Exception as exc:
        total_time = time.time() - t0
        print(f" -> Result: EXCEPTION: {exc}")
        return {
            "mode": mode,
            "name": name,
            "model": model,
            "status": "ERROR",
            "http_status": status_code,
            "ttfb_s": None,
            "total_time_s": round(total_time, 2),
            "error": str(exc)
        }

if __name__ == "__main__":
    results = []
    for prov in PROVIDERS_TO_AUDIT:
        res = audit_provider(prov)
        results.append(res)
        time.sleep(1)

    out_path = "docs/evolution/model_provider_audit_results.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n==========================================")
    print(f"Audit completed. Results saved to {out_path}")
    print(f"==========================================")
    for r in results:
        stat = r['status']
        ttfb = f"{r['ttfb_s']}s" if r.get('ttfb_s') else "N/A"
        print(f"[{stat:5s}] {r['name']:20s} | TTFB: {ttfb:8s} | Err: {r.get('error') or 'None'}")
