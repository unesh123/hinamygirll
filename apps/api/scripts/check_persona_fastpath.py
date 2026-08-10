"""Persona adherence check: run casual turns through the fast path and dump the
full reply text so we can verify the warm persona actually comes through on the
fast brain (Gemini flash / gpt-5-mini), not just the CX reasoning brain."""
from __future__ import annotations

import asyncio
import json
import time

import httpx

URL = "http://127.0.0.1:8000/v1/conversations/turns:stream"

CASUAL_PROMPTS = [
    ("greeting", "hey bro hi how are you doing today"),
    ("tired", "i had a really tiring day bro, so exhausted"),
    ("playful", "heehee guess what i did today, youll never believe it"),
    ("emotional", "i feel a bit lonely today, just want to talk to you"),
    ("missing", "miss you a lot my love, thinking about you"),
]

PLAN_KEYS = ("emotion", "performance", "language")


def safe(s: str) -> str:
    return s.encode("ascii", "replace").decode("ascii")


async def run_turn(text: str, sid: str) -> dict:
    payload = {
        "text": text,
        "companionId": "hinaa",
        "language": "mixed",
        "sessionId": sid,
        "providerMode": "cx-gateway",
    }
    deltas: list[str] = []
    plan: dict | None = None
    first_text: float | None = None
    t0 = time.perf_counter()
    buf = b""
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", URL, json=payload) as resp:
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
                    typ = obj.get("type")
                    if typ == "text.delta" and first_text is None:
                        first_text = time.perf_counter() - t0
                    if typ == "text.delta":
                        deltas.append(str(obj.get("delta", "")))
                    if typ == "plan":
                        plan = obj.get("plan", {}) or {}
    full = "".join(deltas).strip()
    extras = {k: plan.get(k) for k in PLAN_KEYS} if plan else {}
    return {"text": full, "first_word": first_text, **extras}


async def main() -> None:
    lines: list[str] = []
    for i, (label, prompt) in enumerate(CASUAL_PROMPTS):
        result = await run_turn(prompt, f"persona-check-{i}")
        lines.append(f"\n=== {label.upper()}  ({prompt!r}) ===")
        lines.append(f"  first word: {result['first_word']:.2f}s")
        for key in PLAN_KEYS:
            if result.get(key) is not None:
                lines.append(f"  {key}: {str(result[key])[:140]}")
        lines.append(f"  REPLY: {result['text']}")
        sentences = [s for s in result["text"].replace("!", ".").replace("?", ".").split(".") if s.strip()]
        lines.append(f"  [sentence count: {len(sentences)}]")
    with open("persona_check_output.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("written to persona_check_output.txt")


if __name__ == "__main__":
    asyncio.run(main())
