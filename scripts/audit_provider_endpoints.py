"""Phase 01 - Direct Upstream Provider Endpoint Audit."""
import httpx
import json
import time
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("apps/api"))
from hinaa_api.config import get_settings

settings = get_settings()

PROVIDERS = [
    {
        "id": "xkiro",
        "name": "XKiro AI",
        "url": f"{settings.active_xkiro_base_url}/chat/completions",
        "key": settings.active_xkiro_keys[0] if settings.active_xkiro_keys else "",
        "model": settings.active_xkiro_model,
        "payload": {
            "model": settings.active_xkiro_model,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 10
        }
    },
    {
        "id": "oxion",
        "name": "Oxion AI",
        "url": f"{settings.active_oxion_base_url}/chat/completions",
        "key": settings.active_oxion_key.get_secret_value() if settings.active_oxion_key else "",
        "model": settings.active_oxion_model,
        "payload": {
            "model": settings.active_oxion_model,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 10
        }
    },
    {
        "id": "apmix",
        "name": "APMIX.AI",
        "url": f"{settings.active_apmix_base_url}/chat/completions",
        "key": settings.active_apmix_key.get_secret_value() if settings.active_apmix_key else "",
        "model": settings.active_apmix_model,
        "payload": {
            "model": settings.active_apmix_model,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 10
        }
    },
    {
        "id": "claude",
        "name": "Anthropic Claude (mwapi)",
        "url": f"{settings.claude_base_url}/v1/messages",
        "key": settings.claude_api_key.get_secret_value() if settings.claude_api_key else "",
        "model": settings.claude_model,
        "payload": {
            "model": settings.claude_model,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 10
        }
    },
    {
        "id": "agent-router",
        "name": "Agent Router",
        "url": f"{settings.active_agent_router_base_url}/chat/completions",
        "key": settings.active_agent_router_key.get_secret_value() if settings.active_agent_router_key else "",
        "model": settings.active_agent_router_model,
        "payload": {
            "model": settings.active_agent_router_model,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 10
        }
    },
    {
        "id": "codecraft",
        "name": "CodeCraft AI",
        "url": f"{settings.active_codecraft_base_url}/chat/completions",
        "key": settings.active_codecraft_key.get_secret_value() if settings.active_codecraft_key else "",
        "model": settings.active_codecraft_model,
        "payload": {
            "model": settings.active_codecraft_model,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 10
        }
    },
    {
        "id": "seekai",
        "name": "SeekAI",
        "url": f"{settings.active_seekai_base_url}/chat/completions",
        "key": settings.active_seekai_key.get_secret_value() if settings.active_seekai_key else "",
        "model": settings.active_seekai_model,
        "payload": {
            "model": settings.active_seekai_model,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 10
        }
    },
    {
        "id": "tokentable",
        "name": "TokenTable",
        "url": f"{settings.active_tokentable_base_url}/chat/completions",
        "key": settings.active_tokentable_key.get_secret_value() if settings.active_tokentable_key else "",
        "model": settings.active_tokentable_model,
        "payload": {
            "model": settings.active_tokentable_model,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 10
        }
    },
    {
        "id": "cavoti",
        "name": "Cavoti AI",
        "url": f"{settings.active_cavoti_base_url}/chat/completions",
        "key": settings.active_cavoti_key.get_secret_value() if settings.active_cavoti_key else "",
        "model": settings.active_cavoti_model,
        "payload": {
            "model": settings.active_cavoti_model,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 10
        }
    }
]

def probe_direct(p: dict) -> dict:
    url = p["url"]
    key = p["key"]
    name = p["name"]
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    }
    t0 = time.time()
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.post(url, json=p["payload"], headers=headers)
            elapsed = time.time() - t0
            snippet = resp.text[:160].replace("\n", " ")
            return {
                "id": p["id"],
                "name": name,
                "url": url,
                "model": p["model"],
                "status_code": resp.status_code,
                "latency_s": round(elapsed, 3),
                "response_snippet": snippet,
                "status": "PASS" if resp.status_code == 200 else "FAIL"
            }
    except Exception as exc:
        return {
            "id": p["id"],
            "name": name,
            "url": url,
            "model": p["model"],
            "status_code": None,
            "latency_s": round(time.time() - t0, 3),
            "response_snippet": str(exc),
            "status": "ERROR"
        }

if __name__ == "__main__":
    results = []
    print("=" * 70)
    print("DIRECT UPSTREAM ENDPOINT AUDIT")
    print("=" * 70)
    for p in PROVIDERS:
        res = probe_direct(p)
        results.append(res)
        sc = res["status_code"] or "ERR"
        lat = f"{res['latency_s']}s"
        print(f"[{res['status']:5s}] {res['name']:25s} | HTTP {str(sc):4s} | {lat:8s} | {res['response_snippet'][:60]}")

    out_path = "docs/evolution/direct_provider_audit_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved direct provider audit to {out_path}")
