"""Acceptance tests for HINAA -> Claude-Code Parity Engineering Specification."""
from __future__ import annotations

import subprocess

import pytest
from hinaa_api.agent.compaction import compact
from hinaa_api.agent.contracts import MOTION_CONTRACT
from hinaa_api.agent.editor import EditError, str_replace
from hinaa_api.agent.fingerprint import fingerprint
from hinaa_api.agent.hooks import apply_guards
from hinaa_api.agent.loop import AgentLoop, StuckError
from hinaa_api.agent.repair import REPAIRS
from hinaa_api.agent.verify import verify_image, verify_pdf, verify_video

# ---------------------------------------------------------------------------
# Section 6: Core Acceptance Gate (all 6 required tests)
# ---------------------------------------------------------------------------

def test_f1_duration_overflow_is_clamped() -> None:
    payload = {"scenes": [{"duration": 3.088} for _ in range(10)]}
    out = apply_guards("render_code_animation", payload)
    total = sum(s["duration"] for s in out["scenes"])
    assert total <= 30.0 + 1e-9


def test_f2_scale_floor_is_clamped() -> None:
    payload = {"scenes": [{"layers": [{"keyframes": [{"scale": 0.02}]}]}]}
    out = apply_guards("render_code_animation", payload)
    assert out["scenes"][0]["layers"][0]["keyframes"][0]["scale"] == 0.05


def test_f3_layer_timing_fits_scene() -> None:
    payload = {
        "scenes": [
            {
                "duration": 3.0,
                "layers": [{"start": 2.8, "duration": 1.5}],
            }
        ]
    }
    err = {
        "type": "value_error",
        "msg": "layer timing must fit inside its scene",
        "loc": ["scenes", 0],
    }
    fix = next(f for m, f in REPAIRS if m(err))
    out = fix(payload, err)
    layer = out["scenes"][0]["layers"][0]
    assert layer["start"] + layer["duration"] <= 3.0 + 1e-9


def test_f4_identical_failure_raises_stuck() -> None:
    class FakeTool:
        def __call__(self, payload):
            class R:
                ok = False

            r = R()
            r.errors = [
                {
                    "type": "value_error",
                    "msg": "at most 30 seconds",
                    "loc": ["scenes"],
                }
            ]
            return r

    class FakeGen:
        def __call__(self, task):
            return {"scenes": [{"duration": 40.0}]}

        def repair(self, p, e):
            return p

    loop = AgentLoop(FakeTool(), FakeGen(), REPAIRS)
    with pytest.raises(StuckError):
        loop.run("test")


def test_fingerprint_is_stable_across_values() -> None:
    a = [
        {
            "type": "greater_than_equal",
            "msg": "must be >= 0.05",
            "loc": ["scenes", 0, "layers", 1, "keyframes", 0, "scale"],
        }
    ]
    b = [
        {
            "type": "greater_than_equal",
            "msg": "must be >= 0.05",
            "loc": ["scenes", 2, "layers", 3, "keyframes", 0, "scale"],
        }
    ]
    assert fingerprint(a) == fingerprint(b)


def test_verify_rejects_short_video(tmp_path) -> None:
    fake = tmp_path / "out.mp4"
    fake.write_bytes(b"\x00" * 200_000)
    with pytest.raises((subprocess.CalledProcessError, AssertionError, OSError)):
        verify_video(str(fake), expected_duration=18.0)


# ---------------------------------------------------------------------------
# Runtime Integration & Supporting Primitive Verification
# ---------------------------------------------------------------------------

def test_render_code_animation_params_clamps_f1_f2_f3_at_serialization() -> None:
    from hinaa_api.motion_studio import MotionComposition
    from hinaa_api.tools.code_animation_tool import RenderCodeAnimationParams

    rp = RenderCodeAnimationParams.model_validate(
        {
            "composition_json": {
                "version": 1,
                "scenes": [
                    {
                        "duration": 16.0,
                        "transition_duration": 0.5,
                        "layers": [
                            {
                                "kind": "text",
                                "text": "Scene One",
                                "start": 12.0,
                                "end": 18.0,
                                "keyframes": [{"time": 0.0, "scale": 0.02}],
                            }
                        ],
                    },
                    {
                        "duration": 14.88,
                        "layers": [
                            {
                                "kind": "text",
                                "text": "Scene Two",
                                "start": 20.0,
                                "end": 22.0,
                                "keyframes": [{"time": 0.0, "scale": 0.01}],
                            }
                        ],
                    },
                ],
                "accents": [0.5, 30.5],
            }
        }
    )
    comp = MotionComposition.model_validate(rp.composition_json)
    assert comp.duration <= 30.0
    assert comp.scenes[0].layers[0].keyframes[0].scale == 0.05
    assert comp.scenes[1].layers[0].keyframes[0].scale == 0.05
    assert all(t < comp.duration for t in comp.accents)


def test_motion_video_params_clamps_30s_overflow() -> None:
    from hinaa_api.tools.motion_video_tool import MotionVideoParams

    mv = MotionVideoParams.model_validate(
        {
            "title": "Audio Synced Edit",
            "scenes": [{"title": f"Cut {i}", "duration": 4.0} for i in range(8)],
        }
    )
    assert sum(s.duration for s in mv.scenes) <= 30.0 + 1e-6


def test_editor_str_replace_and_verifiers(tmp_path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("alpha = 1\nbeta = 2\n", encoding="utf-8")

    with pytest.raises(EditError, match="anchor not found"):
        str_replace(target, "missing", "x")

    target_dup = tmp_path / "dup.py"
    target_dup.write_text("x = 1\nx = 1\n", encoding="utf-8")
    with pytest.raises(EditError, match="ambiguous"):
        str_replace(target_dup, "x = 1", "x = 2", count=1)

    res = str_replace(target, "beta = 2", "beta = 42")
    assert res["replaced"] == 1
    assert "beta = 42" in target.read_text(encoding="utf-8")

    # Image + PDF modality verifiers
    from PIL import Image

    img_path = tmp_path / "frame.png"
    Image.new("RGB", (512, 512), "cyan").save(img_path)
    assert verify_image(str(img_path))["ok"] is True

    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + (b"0" * 6000))
    assert verify_pdf(str(pdf_path))["ok"] is True


def test_compaction_preserves_tool_results_verbatim() -> None:
    messages = [
        {"role": "user", "content": "Build the animation " + ("A" * 1200)},
        {"role": "assistant", "content": "Checking files " + ("B" * 1200)},
        {"role": "tool", "content": '{"duration": 18.0, "ok": true}'},
        *[
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}"}
            for i in range(8)
        ],
    ]
    out = compact(messages, keep_recent=4, budget=500)
    assert out[0]["role"] == "system"
    assert any(m.get("role") == "tool" and '"duration": 18.0' in m.get("content", "") for m in out)


def test_motion_contract_injected_in_prompts() -> None:
    from hinaa_api.agent.live_agentic_service import (
        build_agentic_messages,
        build_compact_tool_prompt,
    )

    msgs = build_agentic_messages(
        {"render_code_animation"},
        [{"role": "user", "content": "Create a reel"}],
        1,
        8,
    )
    assert "MOTION COMPOSITION CONTRACT" in msgs[0]["content"]
    assert "MOTION COMPOSITION CONTRACT" in MOTION_CONTRACT

    compact_prompt = build_compact_tool_prompt(
        {"render_code_animation"},
        [{"role": "user", "content": "Create a reel"}],
        1,
        8,
    )
    assert "MOTION COMPOSITION CONTRACT" in compact_prompt


@pytest.mark.asyncio
async def test_agentic_runner_blocks_identical_failing_payloads(tmp_path) -> None:
    from hinaa_api.agent.agentic_runner import AgenticLoopRunner

    calls = 0

    async def bad_planner(_transcript, _step):
        nonlocal calls
        calls += 1
        return {
            "action": "call_tool",
            "tool": "workspace_read_file",
            "arguments": {"file_path": "does_not_exist_999.py"},
        }

    runner = AgenticLoopRunner(
        max_steps=8,
        max_consecutive_failures=4,
        workspace_root=str(tmp_path),
    )
    res = await runner.run(
        goal="Read missing file",
        planner=bad_planner,
        allowed_tools={"workspace_read_file"},
    )
    assert res.status == "blocked"
    assert res.steps_executed == 3
    assert any("IDENTICAL_RETRY_BLOCKED" in str(s.observation) for s in res.steps)


@pytest.mark.asyncio
async def test_agentic_runner_rejects_midtext_planning_and_zero_tool_completion(
    tmp_path,
) -> None:
    from hinaa_api.agent.agentic_runner import AgenticLoopRunner

    async def talk_only_planner(_transcript, _step):
        return (
            "Honest answer first: Yes I can do this. "
            "Let me pull the exact composition schema now."
        )

    runner = AgenticLoopRunner(max_steps=3, workspace_root=str(tmp_path))
    res = await runner.run(
        goal="Create a viral TikTok typography MP4 right now",
        planner=talk_only_planner,
        allowed_tools={"render_code_animation", "workspace_read_file"},
    )
    assert res.status == "failed"
    assert res.blocker == "NO_TOOL_EXECUTED"
    assert res.steps_executed == 0

    calls = 0

    async def recover_after_nudge(_transcript, step_num: int):
        nonlocal calls
        calls += 1
        if step_num == 1:
            return (
                "You're right to be annoyed — let me stop talking and render it. "
                "Checking the workspace now."
            )
        if step_num == 2:
            return {
                "action": "call_tool",
                "tool": "workspace_write_file",
                "arguments": {
                    "file_path": "ok.txt",
                    "content": "rendered",
                },
            }
        return {"action": "final", "summary": "Wrote ok.txt."}

    runner2 = AgenticLoopRunner(max_steps=4, workspace_root=str(tmp_path))
    res2 = await runner2.run(
        goal="Create a viral TikTok typography MP4",
        planner=recover_after_nudge,
        allowed_tools={"workspace_write_file"},
    )
    assert res2.status == "completed"
    assert calls == 3
    assert (tmp_path / "ok.txt").read_text(encoding="utf-8") == "rendered"


@pytest.mark.asyncio
async def test_viral_tiktok_followup_triggers_agentic_route(settings) -> None:
    from hinaa_api.models import TurnRequest
    from hinaa_api.prompts.assembly import assemble_prompt
    from hinaa_api.prompts.models import MoodSnapshot, PersonalitySettings, PromptInput
    from hinaa_api.services import ConversationService

    prompt_pkg = assemble_prompt(
        PromptInput(
            user_text="What are your current capacities?",
            companion_id="hinaa",
            interaction_mode="realtime",
            personality=PersonalitySettings(),
            mood=MoodSnapshot(label="calm", intensity=0.4),
        )
    )
    assert "no interactive tool runner" not in prompt_pkg.system_instruction.lower()

    svc = ConversationService(settings)
    tiktok_events = [
        ev.decode("utf-8", "replace") if isinstance(ev, bytes) else str(ev)
        async for ev in svc.stream_turn(
            TurnRequest(
                sessionId="tiktok-parity-route",
                text=(
                    "Okay, bro, can you make one for me? "
                    "It should get 100% viral on TikTok, okay?"
                ),
                providerMode="mock",
            ),
            "cid-tiktok",
        )
    ]
    assert any("agentic.started" in ev for ev in tiktok_events)

    cap_events = [
        ev.decode("utf-8", "replace") if isinstance(ev, bytes) else str(ev)
        async for ev in svc.stream_turn(
            TurnRequest(
                sessionId="cap-parity-route",
                text="What are your current capacities?",
                providerMode="mock",
            ),
            "cid-cap",
        )
    ]
    assert not any("agentic.started" in ev for ev in cap_events)

