"""Measure real per-provider chat latency with a tiny completion.

Read-only diagnostic: one short request per configured brain, timed, with a
hard per-provider cap so a hung gateway cannot stall the probe itself.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

import httpx  # noqa: E402

from hinaa_api.config import get_settings  # noqa: E402


async def probe(name: str, base_url: str, key: str, model: str, cap: float = 35.0) -> dict:
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say hi in one word."}],
        "max_tokens": 8,
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(cap, connect=5.0)) as client:
            resp = await client.post(url, json=payload, headers=headers)
        dt = time.perf_counter() - t0
        body = resp.text[:160].replace("\n", " ")
        ok = resp.status_code == 200
        snippet = ""
        if ok:
            try:
                snippet = resp.json()["choices"][0]["message"]["content"][:60]
            except Exception:
                snippet = body[:60]
        return {"provider": name, "model": model, "ms": round(dt * 1000), "status": resp.status_code, "ok": ok, "snippet": snippet or body}
    except Exception as exc:  # noqa: BLE001
        dt = time.perf_counter() - t0
        return {"provider": name, "model": model, "ms": round(dt * 1000), "status": None, "ok": False, "snippet": f"{type(exc).__name__}: {exc}"[:160]}


async def main() -> None:
    s = get_settings()
    targets: list[tuple[str, str, str, str]] = []

    def secret(v) -> str:
        return v.get_secret_value() if v else ""

    if s.agent_router_configured:
        targets.append(("agent-router", s.active_agent_router_base_url, secret(s.active_agent_router_key), s.active_agent_router_model))
    if s.cavoti_configured:
        targets.append(("cavoti", s.active_cavoti_base_url, secret(s.active_cavoti_key), s.active_cavoti_model))
    if s.explabs_configured:
        targets.append(("experiential", s.explabs_base_url, secret(s.explabs_api_key), s.active_explabs_model))
    if s.xkiro_configured:
        targets.append(("xkiro", s.active_xkiro_base_url, secret(s.active_xkiro_key), s.active_xkiro_model))
    if s.gemini_configured:
        # Gemini native endpoint differs; probe via its configured OpenAI-compatible shim if any.
        targets.append(("gemini(native-check-skip)", "(native api)", "n/a", s.gemini_model))

    print(f"Probing {len(targets)} providers, 35s cap each...\n")
    results = []
    for name, base, key, model in targets:
        if "(native api)" in base:
            continue
        r = await probe(name, base, key, model)
        results.append(r)
        print(json.dumps(r, ensure_ascii=False))

    ok = [r for r in results if r["ok"]]
    if ok:
        fastest = min(ok, key=lambda r: r["ms"])
        print(f"\nFastest healthy brain: {fastest['provider']} at {fastest['ms']}ms")


if __name__ == "__main__":
    asyncio.run(main())
