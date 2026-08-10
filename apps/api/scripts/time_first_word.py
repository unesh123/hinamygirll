"""Time HINAA's first-word latency on the live turns:stream endpoint.

Measures, per turn:
  - time to first event (thinking)
  - time to first text.delta (her first word)
  - time to full stream completion
  - provider/model info from the plan event (if present)
"""
from __future__ import annotations

import asyncio
import json
import time

import httpx

URL = "http://127.0.0.1:8000/v1/conversations/turns:stream"


def payload(text: str, sid: str) -> dict:
    return {
        "text": text,
        "companionId": "hinaa",
        "language": "mixed",
        "sessionId": sid,
        "providerMode": "cx-gateway",
    }


async def time_turn(label: str, text: str, sid: str) -> None:
    t0 = time.perf_counter()
    first_event: float | None = None
    first_text: float | None = None
    first_text_sample = ""
    usage_ms: float | None = None
    event_counts: dict[str, int] = {}
    plan_provider = ""
    plan_model = ""

    buf = b""
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", URL, json=payload(text, sid)) as resp:
            async for chunk in resp.aiter_bytes():
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    raw = line.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    now = time.perf_counter() - t0
                    typ = obj.get("type", "?")
                    event_counts[typ] = event_counts.get(typ, 0) + 1
                    if first_event is None:
                        first_event = now
                    if typ == "text.delta" and first_text is None:
                        first_text = now
                        first_text_sample = str(obj.get("delta", ""))[:40]
                    if typ == "usage":
                        usage_ms = obj.get("latencyMs")
                    if typ == "plan":
                        p = obj.get("plan", {}) or {}
                        plan_provider = str(p.get("provider", ""))
                        plan_model = str(p.get("model", ""))
    total = time.perf_counter() - t0

    def safe(s: str) -> str:
        return s.encode("ascii", "replace").decode("ascii")

    def fmt(v: float | None) -> str:
        return f"{v:.2f}s" if v is not None else "n/a"

    print(f"\n=== {label} ===")
    print(f"  first event (thinking):   {fmt(first_event)}")
    print(f"  FIRST WORD (text.delta):  {fmt(first_text)}   sample: {safe(first_text_sample)!r}")
    print(f"  stream total:             {fmt(total)}")
    print(f"  provider/model:           {plan_provider or '?'} / {plan_model or '?'}")
    if usage_ms is not None:
        print(f"  backend latencyMs:        {usage_ms:.0f} ms")
    print(f"  event types:              {json.dumps(event_counts)}")


async def main() -> None:
    # Cold casual turn first (after restart, the dead OpenAI key ping happens once).
    await time_turn("CASUAL 'hi bro' #1 (cold after restart)", "hey bro hi how are you doing today", "lat-casual-1")
    # Warm casual turn (negative cache should route to Gemini flash fast path).
    await time_turn("CASUAL 'hi bro' #2 (warm, fast path)", "miss you bro what are you up to", "lat-casual-2")
    # Coding question -> CX reasoning brain.
    await time_turn("CODING question (CX brain)", "write a python function that reverses a string and explain it briefly", "lat-code-1")


if __name__ == "__main__":
    asyncio.run(main())
