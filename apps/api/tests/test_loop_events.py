"""Tests for the loop event bus and SSE streaming (harness/loop_events.py)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hinaa_api.harness.loop_events import EVENT_BUS, LoopEventBus, sse_format, sse_stream  # noqa: E402


def test_publish_history_and_sequence():
    bus = LoopEventBus()
    tid = "t1"

    async def run():
        await bus.publish(tid, "loop_started", {"goal": "g"})
        await bus.publish(tid, "turn_completed", {"turn": 1})
        await bus.publish(tid, "turn_completed", {"turn": 2})

    asyncio.run(run())
    history = bus.history(tid)
    assert [e["sequence"] for e in history] == [1, 2, 3]
    assert bus.history(tid, since_sequence=2)[0]["data"]["turn"] == 2


def test_subscriber_receives_replay_and_live_events():
    bus = LoopEventBus()
    tid = "t2"

    async def run():
        await bus.publish(tid, "loop_started", {})
        queue = await bus.subscribe(tid)
        await bus.publish(tid, "turn_completed", {"turn": 1})
        replay = await asyncio.wait_for(queue.get(), timeout=1)
        live = await asyncio.wait_for(queue.get(), timeout=1)
        return replay, live

    replay, live = asyncio.run(run())
    assert replay["event_type"] == "loop_started"
    assert live["data"]["turn"] == 1


def test_sse_format_and_stream_terminates():
    frame = sse_format({"sequence": 4, "ts": "ts", "event_type": "turn_completed", "data": {"turn": 1}})
    assert frame.startswith("id: 4\nevent: turn_completed\ndata: ")
    assert frame.endswith("\n\n")
    payload = json.loads(frame.split("data: ", 1)[1].strip("\n"))
    assert payload["data"]["turn"] == 1

    bus = LoopEventBus()
    EVENT_BUS_patched = bus
    tid = "t3"

    async def produce():
        await asyncio.sleep(0.05)
        await EVENT_BUS_patched.publish(tid, "loop_finished", {"status": "COMPLETED"})

    async def collect():
        queue_task = asyncio.create_task(produce())
        frames = []
        async for frame in sse_stream(task_id=tid):
            frames.append(frame)
            if "[DONE]" in frame:
                break
        await queue_task
        return frames

    # patch the module-level bus used by sse_stream
    import hinaa_api.harness.loop_events as le

    original = le.EVENT_BUS
    le.EVENT_BUS = bus
    try:
        frames = asyncio.run(collect())
    finally:
        le.EVENT_BUS = original
    assert any("loop_finished" in f for f in frames)
    assert frames[-1].endswith("data: [DONE]\n\n")
