from __future__ import annotations

import json
import math
import struct
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hinaa_api.live.asr import StreamingASR
from hinaa_api.live.orchestrator import LiveOrchestrator, summarize_for_voice
from hinaa_api.live.pc_control import (
    ConfirmationRequiredError,
    execute_pc_action,
    locate_target,
    register_pc_control_tools,
)
from hinaa_api.live.transport import create_live_router
from hinaa_api.live.tts import SentenceStreamer
from hinaa_api.live.vad import VoiceActivityDetector
from hinaa_api.live.wake import LiveSessionLifecycle, NoiseSuppressor, WakeWordDetector


def _sine_pcm16(amplitude: int = 12000, n_samples: int = 480) -> bytes:
    buf = bytearray(n_samples * 2)
    for i in range(n_samples):
        val = int(amplitude * math.sin(2.0 * math.pi * 240.0 * (i / 16000.0)))
        struct.pack_into("<h", buf, i * 2, val)
    return bytes(buf)


def test_ws_live_echo_and_latency() -> None:
    app = FastAPI()
    app.include_router(create_live_router())
    client = TestClient(app)

    status = client.get("/v1/live/status")
    assert status.status_code == 200
    assert status.json()["pcConfirmationRequiredForWrites"] is True

    with client.websocket_connect("/ws/live") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "state"

        t0 = time.perf_counter()
        ws.send_json({"type": "echo", "payload": "jarvis-ping"})
        echo = ws.receive_json()
        assert echo == {"type": "echo", "payload": "jarvis-ping"}

        ws.send_json({"type": "text", "text": "Hello Hinaa"})
        state_msg = ws.receive_json()
        assert state_msg == {"type": "state", "state": "thinking"}
        speaking_msg = ws.receive_json()
        assert speaking_msg == {"type": "state", "state": "speaking"}
        spoken = ws.receive_json()
        assert spoken["type"] == "assistant.spoken"
        pcm_total = 0
        lat = None
        for _ in range(40):
            frame = ws.receive()
            if frame.get("bytes") is not None:
                pcm_total += len(frame["bytes"])
                continue
            if frame.get("text") is not None:
                parsed = json.loads(frame["text"])
                if parsed.get("type") == "latency":
                    lat = parsed
                    break
        assert pcm_total > 0
        assert lat is not None and lat["type"] == "latency"
        assert (time.perf_counter() - t0) < 6.0


def test_vad_onset_hangover_and_fast_barge_in() -> None:
    vad = VoiceActivityDetector(onset_frames=3, hangover_frames=5)
    silence = b"\x00" * 960
    speech = _sine_pcm16(amplitude=14000)

    # Normal speech onset
    events = [vad.process_frame(speech).event for _ in range(3)]
    assert events[-1] == "speech_start"

    # Hangover holds until 5 silent frames
    silent_events = [vad.process_frame(silence).event for _ in range(5)]
    assert silent_events[-1] == "speech_end"

    # Barge-in triggers in <= 2 frames (60ms < 300ms target)
    vad.reset()
    barge = [vad.process_frame(speech, is_tts_speaking=True).event for _ in range(2)]
    assert "barge_in" in barge


@pytest.mark.asyncio
async def test_streaming_asr_and_sentence_tts_cancel() -> None:
    asr = StreamingASR(transcribe_fn=lambda b, final: "check server logs" if final else "check")
    asr.push_audio(_sine_pcm16())
    partial = await asr.flush(is_final=False)
    assert partial.text == "check"
    assert partial.is_final is False
    final = await asr.flush(is_final=True)
    assert final.text == "check server logs"
    assert final.latency_ms < 500.0

    tts = SentenceStreamer()
    s1 = await tts.push_token("First sentence complete. Second ")
    assert s1 == ["First sentence complete."]
    s2 = await tts.finish()
    assert s2 == ["Second"]
    chunks = [c async for c in tts.stream_chunks()]
    assert len(chunks) == 2

    tts.reset()
    tts.cancel()
    after_cancel = await tts.push_token("Should not speak.")
    assert after_cancel == []


@pytest.mark.asyncio
async def test_live_orchestrator_runs_tools_concurrently_and_summarizes_for_voice() -> None:
    summarized = summarize_for_voice("## Title\nClick [docs](https://example.com) ```python\nx=1\n``` Done.")
    assert "```" not in summarized
    assert "https://" not in summarized
    assert "Done." in summarized

    done_event = False

    async def slow_tool(_utt, _route):
        nonlocal done_event
        done_event = True
        return "Tests finished cleanly with zero failures."

    orch = LiveOrchestrator(tool_fn=slow_tool)
    spoken_later: list[str] = []

    async def on_res(txt: str) -> None:
        spoken_later.append(txt)

    out = await orch.handle_utterance("Refactor the React button component and run unit tests", on_tool_result=on_res)
    assert "On it" in out.spoken_intro
    assert out.background_task is not None
    await out.background_task
    assert done_event is True
    assert spoken_later == ["Tests finished cleanly with zero failures."]


def test_pc_control_confirmation_gate_20_cases_and_ocr_target() -> None:
    tools = register_pc_control_tools()
    assert len(tools) == 6

    # 20 write action cases must ALL refuse without confirmed=True
    write_cases = [
        ("click", {"x": 10, "y": 20}),
        ("pc.click", {"label": "Send", "ocr_tokens": [{"text": "Send", "x": 10, "y": 10, "width": 40, "height": 20}]}),
        ("type", {"text": "hello"}),
        ("pc.type", {"text": "rm -rf"}),
        ("hotkey", {"keys": ["ctrl", "c"]}),
        ("pc.hotkey", {"keys": ["alt", "f4"]}),
        ("open_app", {"app": "notepad"}),
        ("pc.open_app", {"app": "powershell"}),
    ] * 2 + [("unknown_write", {}), ("click", {}), ("type", {"text": ""}), ("open_app", {"app": "calc"})]
    assert len(write_cases) == 20
    for act, params in write_cases:
        with pytest.raises(ConfirmationRequiredError):
            execute_pc_action(act, params, confirmed=False)

    # Read actions succeed without confirmation
    assert execute_pc_action("pc.screenshot")["status"] in {"ok", "unavailable"}
    pt = locate_target("Submit", ocr_tokens=[{"text": "Submit", "x": 100, "y": 200, "width": 60, "height": 30}])
    assert pt is not None and pt.x == 130 and pt.y == 215


def test_wake_idle_clock_and_40_command_voice_routing_accuracy() -> None:
    wake = WakeWordDetector("hey hina")
    assert wake.matches_transcript("Hey Hina what is the weather?") is True
    assert wake.matches_transcript("random background tv") is False

    sup = NoiseSuppressor()
    assert sup.process(b"\x01\x00" * 480) == b"\x00" * 960

    clock = LiveSessionLifecycle(idle_timeout_seconds=30.0)
    assert clock.wake(now=100.0) == "listening"
    assert clock.tick(now=120.0) == "listening"
    assert clock.tick(now=131.0) == "idle"

    # L9: 40-command golden voice suite accuracy >= 90%
    from hinaa_api.intent_router import route_intent

    golden = [
        ("How are you today?", "chat"),
        ("Explain what quantum entanglement means", "chat"),
        ("Why does React use keys?", "chat"),
        ("Tell me a joke", "chat"),
        ("What is the capital of Japan?", "chat"),
        ("Search the web for latest Vite 6 notes", "research"),
        ("Look up today's Tokyo weather", "research"),
        ("Compare FastAPI vs Litestar benchmarks", "research"),
        ("Deep research quantum computing trends", "research"),
        ("Find out latest Python 3.14 features", "research"),
        ("Fix the bug in ChatPanel component", "coding"),
        ("Refactor the database query function", "coding"),
        ("Implement unit tests for the API endpoint", "coding"),
        ("Check the Python traceback in runner", "coding"),
        ("Run typecheck on the repository", "coding"),
        ("Generate an anime wallpaper of Tokyo", "creative_media"),
        ("Create a motion graphics clip", "creative_media"),
        ("Make a minimal logo design", "creative_media"),
        ("Build a presentation slide deck", "creative_media"),
        ("Render cinematic typography video", "creative_media"),
        ("Summarize this PDF contract", "documents"),
        ("Parse the quarterly csv spreadsheet", "documents"),
        ("Extract action items from this docx file", "documents"),
        ("Generate an invoice PDF report", "documents"),
        ("Analyze the attached whitepaper document", "documents"),
        ("Open YouTube in browser", "browser"),
        ("Navigate to github repo page", "browser"),
        ("Play lofi music on Spotify", "browser"),
        ("Take a screenshot of Google homepage", "browser"),
        ("Browse Hacker News top posts", "browser"),
        ("Start a 25 minute Pomodoro timer", "automation"),
        ("Remind me at 6 PM to call Alex", "automation"),
        ("Split 4500 between 3 people", "automation"),
        ("Roll 2d6", "automation"),
        ("Flip a coin", "automation"),
        ("Plan a step-by-step migration and then deploy", "plan"),
        ("First research competitors and after that build a deck", "plan"),
        ("Orchestrate a full repo audit workflow", "plan"),
        ("Build the app step-by-step then run tests", "plan"),
        ("Create a pipeline to test and deploy", "plan"),
    ]
    assert len(golden) == 40
    correct = sum(1 for text, expected in golden if route_intent(text).route == expected)
    accuracy = correct / len(golden)
    assert accuracy >= 0.90, f"Voice routing accuracy {accuracy:.2%} < 90%"
