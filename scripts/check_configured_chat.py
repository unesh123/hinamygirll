"""Explicit synthetic upstream check: one short streaming request per configured lane.

No fallback, retries, environment changes, private prompts, or credential output.
Run from the repository root with the API virtualenv. Not a quality benchmark.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
import httpx
from hinaa_api.config import get_settings
from hinaa_api.services import ProviderRouter
from hinaa_api.brain_ledger import fingerprint_for, record_call, row_for_brain

MODES = ["gmi", "openai", "custom", "real", "groq", "claude", "qwen", "agent-router",
         "cx-gateway", "codecraft", "ollama", "pgsgrove", "seekai", "tokentable",
         "xkiro", "cavoti", "apmix", "oxion", "respan", "experiential"]


def text_delta(data: dict) -> str:
    choices = data.get("choices") or []
    if choices:
        content = (choices[0].get("delta") or choices[0].get("message") or {}).get("content")
        if isinstance(content, str):
            return content
    if data.get("type") == "content_block_delta":
        return data.get("delta", {}).get("text", "")
    candidates = data.get("candidates") or []
    if candidates:
        return "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if not p.get("thought"))
    return ""


async def check(mode, router, client, semaphore, record=False):
    row = {"mode": mode, "status": "unverified"}
    try:
        provider = router.llm(mode)
    except Exception as error:
        return {**row, "status": "not_configured", "code": getattr(error, "code", type(error).__name__)}
    row["model"] = provider.model
    key = provider._key
    base = getattr(provider, "_base_url", "")
    headers = {"Authorization": f"Bearer {key}"}
    payload_model = provider._model_for_payload() if hasattr(provider, "_model_for_payload") else provider.model
    row["payloadModel"] = payload_model
    body = {"model": payload_model, "messages": [{"role": "user", "content": "Reply with exactly the word Pong."}], "max_tokens": 24, "stream": True}
    url = f"{base}/chat/completions"
    if mode == "real":
        headers = {"x-goog-api-key": key}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{provider.model}:streamGenerateContent?alt=sse"
        body = {"contents": [{"role": "user", "parts": [{"text": "Reply with exactly the word Pong."}]}], "generationConfig": {"maxOutputTokens": 512}}
    elif mode == "claude":
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        headers.update(getattr(provider, "gateway_auth_headers", {}))
        url = base.rstrip("/") + ("/messages" if base.endswith("/v1") else "/v1/messages")
    elif mode == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
    async with semaphore:
        start = time.perf_counter()
        try:
            async with asyncio.timeout(15):
                async with client.stream("POST", url, headers=headers, json=body, follow_redirects=False) as response:
                    row["httpStatus"] = response.status_code
                    if response.status_code != 200:
                        row["status"] = "rejected"
                    else:
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            try:
                                data = json.loads(line[5:].strip())
                            except ValueError:
                                continue
                            if not isinstance(data, dict):
                                continue
                            if data.get("error"):
                                row["status"] = "stream_error"
                                break
                            text = text_delta(data)
                            if text.strip():
                                row["status"] = "responding"
                                row["firstTextMs"] = round((time.perf_counter() - start) * 1000)
                                row["nonemptyText"] = True
                                break
                        else:
                            row["status"] = "no_text"
        except Exception as error:
            row.update(status="failed", code=type(error).__name__)
        row["elapsedMs"] = round((time.perf_counter() - start) * 1000)
    if record and row["status"] != "no_text":
        status = row.get("httpStatus")
        code = ("PROVIDER_TIMEOUT" if row.get("code") in {"ReadTimeout", "ConnectTimeout", "TimeoutError"}
                else "PROVIDER_RATE_LIMIT" if status == 429
                else "PROVIDER_AUTH_REJECTED" if status in {401, 403}
                else "PROVIDER_PAYMENT_REQUIRED" if status == 402
                else "PROVIDER_ENDPOINT_OR_MODEL_MISSING" if status == 404
                else "PROVIDER_CHECK_FAILED")
        record_call(provider.id, ok=row["status"] == "responding", code="" if row["status"] == "responding" else code,
                    model=provider.model, fingerprint=fingerprint_for(router.settings, row_for_brain(provider.id)),
                    detail=f"Synthetic first-text check: {row['status']}; HTTP {status}; {row['elapsedMs']} ms. Not a quality benchmark.")
    print(json.dumps(row), flush=True)
    return row


async def main():
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=MODES)
    parser.add_argument("--output", default=".runtime/configured-chat-check.json")
    parser.add_argument("--record", action="store_true", help="Record this live check in Hina's existing health ledger")
    args = parser.parse_args()
    router = ProviderRouter(get_settings())
    async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=4), limits=httpx.Limits(max_connections=3)) as client:
        semaphore = asyncio.Semaphore(3)
        rows = await asyncio.gather(*(check(mode, router, client, semaphore, args.record) for mode in args.modes))
    report = {"checkedAt": datetime.now(timezone.utc).isoformat(), "scope": "one synthetic first-text probe per default model; no fallback", "results": rows}
    path = ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
