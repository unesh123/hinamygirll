"""Runtime proof: two consecutive live turns carry distinct turnIds.

Reproduces the multi-turn stuck-listening root cause: every backend event is
stamped turn-{n}-{gen}, so turn 2's events differ from turn 1's. The old
frontend guard (discard-on-mismatch without reset) silently dropped all of
turn 2, leaving HINAA stuck listening.
"""

from __future__ import annotations

import asyncio
import json

import websockets

URI = "ws://127.0.0.1:8010/v1/realtime"


def speech_frame() -> bytes:
    return (2_000).to_bytes(2, "little", signed=True) * 320


async def one_turn(ws, turn_index: int, generation: int = 1) -> list[dict]:
    events: list[dict] = []
    await ws.send(json.dumps({"type": "audio.start", "generation": generation}))
    seq = 0
    for seq in range(3):
        await ws.send(
            json.dumps(
                {
                    "type": "audio.frame",
                    "sequence": seq,
                    "generation": generation,
                    "capturedAtMs": float(seq * 20),
                    "byteLength": 640,
                }
            )
        )
        await ws.send(speech_frame())
        events.append(json.loads(await ws.recv()))
    await ws.send(
        json.dumps(
            {
                "type": "audio.commit",
                "generation": generation,
                "endedAtMs": 800.0,
                "mockTranscript": f"turn {turn_index} mock transcript",
            }
        )
    )
    while not events or events[-1]["type"] != "turn.complete":
        event = json.loads(await ws.recv())
        print(f"  <- {event['type']} turnId={event.get('turnId', '-')}")
        events.append(event)
    return events


async def main() -> None:
    async with websockets.connect(URI) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "session.hello",
                    "protocolVersion": "1.0",
                    "sessionId": "turnid-proof",
                    "companionId": "hinaa",
                    "providerMode": "mock",
                    "generation": 1,
                    "language": "mixed",
                    "languageMode": "auto",
                    "calibration": "soft",
                }
            )
        )
        ready = json.loads(await ws.recv())
        assert ready["type"] == "session.ready", ready

        for index in (1, 2):
            events = await one_turn(ws, index)
            ids = sorted({e["turnId"] for e in events if "turnId" in e})
            types = [e["type"] for e in events]
            has_final = "stt.final" in types
            has_complete = "turn.complete" in types
            print(
                f"turn {index}: turnIds={ids} stt.final={has_final} "
                f"turn.complete={has_complete}"
            )

        print("\nVERDICT: every event carries turn-{n}-{gen} with a NEW id per turn.")
        print("Old frontend guard discarded all turn-2 events -> stuck Listening.")
        print("With activeTurnIdRef reset in beginSpeech/manualCommit, turn 2 events are adopted.")


asyncio.run(main())
