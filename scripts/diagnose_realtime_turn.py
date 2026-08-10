"""End-to-end realtime turn diagnostic.

Simulates exactly what the browser does over ws://localhost:8000/v1/realtime:
  session.hello (providerMode=real) -> audio.start -> PCM frames -> audio.commit
and prints every server event (audio payloads summarized, never dumped).

Speech input: a short phrase synthesized once via ElevenLabs TTS as raw
pcm_16000 so it can be fed directly as microphone frames. Small paid call.
"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from hinaa_api.config import Settings  # noqa: E402

PHRASE = "Hello Hinaa, how are you today?"


def fetch_speech_pcm(settings: Settings) -> bytes:
    key = settings.elevenlabs_api_key.get_secret_value()  # type: ignore[union-attr]
    base = settings.elevenlabs_base_url.rstrip("/")
    url = f"{base}/v1/text-to-speech/{settings.elevenlabs_hinaa_voice_id}"
    r = httpx.post(
        url,
        headers={"xi-api-key": key},
        params={"output_format": "pcm_16000"},
        json={"text": PHRASE, "model_id": settings.elevenlabs_model_id},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.content


async def run_turn(pcm: bytes) -> None:
    uri = "ws://127.0.0.1:8000/v1/realtime"
    async with websockets.connect(uri, max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({
            "type": "session.hello",
            "protocolVersion": "1.0",
            "sessionId": "diagnostic-live",
            "companionId": "hinaa",
            "providerMode": "real",
            "generation": 0,
            "language": "mixed",
            "languageMode": "auto",
            "calibration": "natural",
        }))
        print("<<", json.loads(await ws.recv())["type"])

        await ws.send(json.dumps({"type": "audio.start", "generation": 0}))
        print("<<", json.loads(await ws.recv())["type"])

        frame_bytes = 640  # 20 ms @ 16 kHz s16le
        total = min(len(pcm) - (len(pcm) % frame_bytes), frame_bytes * 400)  # cap ~8s
        seq = 0
        for off in range(0, total, frame_bytes):
            frame = pcm[off:off + frame_bytes]
            await ws.send(json.dumps({
                "type": "audio.frame",
                "sequence": seq,
                "generation": 0,
                "capturedAtMs": float(seq * 20),
                "byteLength": len(frame),
            }))
            await ws.send(frame)
            seq += 1
        print(f">> sent {seq} frames ({seq * 20} ms of audio)")

        await ws.send(json.dumps({
            "type": "audio.commit",
            "generation": 0,
            "endedAtMs": float(seq * 20),
        }))

        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=60.0)
            except asyncio.TimeoutError:
                print("!! timed out waiting for server events")
                return
            event = json.loads(raw)
            etype = event.get("type")
            if etype == "tts.audio":
                blob = base64.b64decode(event.get("audioBase64", ""))
                print(f"<< tts.audio segment={event.get('segment')}/{event.get('segments')} "
                      f"bytes={len(blob)} mediaType={event.get('mediaType')} provider={event.get('provider')}")
            elif etype in {"stt.final", "stt.partial"}:
                print(f"<< {etype} text={event.get('text')!r} provider={event.get('provider')}")
            elif etype == "assistant.text.delta":
                print(f"<< delta {event.get('delta')!r}")
            elif etype == "error":
                print(f"<< ERROR code={event.get('code')} retryable={event.get('retryable')} msg={event.get('message')}")
                return
            elif etype == "turn.cancelled":
                print(f"<< turn.cancelled reason={event.get('reason')}")
                return
            else:
                print("<<", etype, {k: v for k, v in event.items() if k in {"sttMs", "llmMs", "ttsMs", "totalMs", "provider"}})
            if etype == "turn.complete":
                return


def main() -> int:
    env_local = ROOT / "apps" / "api" / ".env.local"
    settings = Settings(_env_file=str(env_local) if env_local.exists() else None)
    print(f"[1] Synthesizing test phrase as pcm_16000: {PHRASE!r}")
    pcm = fetch_speech_pcm(settings)
    print(f"[1] Got {len(pcm)} bytes of PCM speech")
    print("[2] Running realtime turn with providerMode=real ...")
    asyncio.run(run_turn(pcm))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
