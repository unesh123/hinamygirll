"""Live voice smoke test: drive a full turn through the realtime WS and confirm
text + audio come back from the HINAA backend."""
from __future__ import annotations

import asyncio
import json
import struct
import sys
import time

import websockets

WS_URL = "ws://127.0.0.1:8000/v1/realtime"


def pcm_speech(duration_seconds: float = 0.6, sample_rate: int = 16000) -> bytes:
    """Generate PCM16 mono 'speech-like' audio: a 220 Hz tone with envelope.

    We use a deterministic tone because the backend rejects pure-zero buffers
    (see _is_dead_silence in realtime.py). A tone is enough to trigger STT.
    """
    import math
    n = int(duration_seconds * sample_rate)
    amplitude = 6000
    freq = 220.0
    samples = bytearray()
    for i in range(n):
        envelope = min(1.0, (i / (sample_rate * 0.1))) * min(
            1.0, ((n - i) / (sample_rate * 0.1))
        )
        value = int(amplitude * envelope * math.sin(2 * math.pi * freq * i / sample_rate))
        samples += struct.pack("<h", value)
    return bytes(samples)


def pcm_frames(pcm: bytes, frame_ms: int = 20, sample_rate: int = 16000) -> list[bytes]:
    frame_size = int(sample_rate * frame_ms / 1000) * 2
    return [pcm[i : i + frame_size] for i in range(0, len(pcm), frame_size)]


async def main() -> int:
    events: list[dict] = []
    async with websockets.connect(WS_URL, max_size=8 * 1024 * 1024) as ws:
        ws.opened_future = asyncio.ensure_future(ws.recv()) if False else None  # placeholder
        await ws.send(json.dumps({
            "type": "session.hello",
            "protocolVersion": "1.0",
            "sessionId": "probe",
            "companionId": "hinaa",
            "providerMode": "mock",
            "language": "en-US",
            "languageMode": "auto",
            "calibration": "natural",
            "generation": 0,
        }))
        # Drain session.ready
        ready = json.loads(await ws.recv())
        events.append(ready)
        print("session.ready:", ready.get("type"))

        # Stream audio frames
        for i, frame in enumerate(pcm_frames(pcm_speech())):
            await ws.send(json.dumps({
                "type": "audio.frame",
                "sequence": i,
                "generation": 0,
                "capturedAtMs": time.time() * 1000,
                "byteLength": len(frame),
            }))
            await ws.send(frame)

        # Commit
        await ws.send(json.dumps({
            "type": "audio.commit",
            "generation": 0,
            "endedAtMs": time.time() * 1000,
            "mockTranscript": "Hello HINAA, please answer briefly.",
        }))

        # Read events for up to 30s
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
            except asyncio.TimeoutError:
                break
            event = json.loads(raw)
            events.append(event)
            t = event.get("type")
            if t == "stt.final":
                print(f"stt.final: {event.get('text')!r}")
            elif t == "assistant.text.delta":
                print(f"text.delta: {event.get('delta')!r}")
            elif t == "assistant.plan":
                print(f"plan.displayText: {event.get('plan', {}).get('displayText', '')[:120]!r}")
            elif t == "tts.audio":
                print(f"tts.audio: {len(event.get('audioBase64', ''))} chars ({event.get('mediaType')}, voice={event.get('actualVoice')})")
            elif t == "turn.complete":
                print(f"turn.complete: ttsStatus={event.get('ttsStatus')}, stt={event.get('sttMs')}ms llm={event.get('llmMs')}ms tts={event.get('ttsMs')}ms total={event.get('totalMs')}ms")
                break
            elif t == "voice.error":
                print(f"voice.error: code={event.get('code')} reason={event.get('reason')!r}")
            elif t == "voice.pipeline":
                print(f"voice.pipeline: stage={event.get('stage')} detail={event.get('detail')!r}")
            elif t == "turn.cancelled":
                print(f"turn.cancelled: reason={event.get('reason')!r}")
            elif t == "error":
                print(f"ERROR: code={event.get('code')} message={event.get('message')!r}")
                break
            else:
                print(f"other event: {t} keys={list(event.keys())[:6]}")

    types = [e.get("type") for e in events]
    print("\n=== Event summary ===")
    for t in types:
        print(" ", t)
    return 0 if "turn.complete" in types else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))