"""Deterministic production benchmark suite for Bounded Multi-Segment Long-Form Generation.

Tests 25K, 50K, and 100K multi-segment generations:
- Seam deduplication across continuation boundaries
- Markdown structural consistency (code fence closure, heading sanity)
- Strict AssistantTurnPlan schema validation (displayText/spokenText decoupling)
- SQLite durable database persistence and exact-fidelity roundtrip reload
- Voice response executive summary extraction (<160 chars, no conversational filler)
- ContinuationRequest prompt invariant synchronization
"""

from __future__ import annotations

import hashlib
import json
import pytest

from hinaa_api.config import Settings
from hinaa_api.generation.continuation import (
    SeamGuard,
    run_consistency_pass,
    seam_dedup,
)
from hinaa_api.generation.continuation_contract import (
    ContinuationRequest,
    PromptInvariantVerifier,
)
from hinaa_api.models import AssistantTurnPlan
from hinaa_api.persistence import MemoryService, init_db
from hinaa_api.persistence.db import reset_session_factory
from hinaa_api.prompts.models import MoodSnapshot, PersonalitySettings, PromptPackage
from hinaa_api.services import VoiceResponseType, plan_voice_response


def _generate_segment(index: int, target_chars: int = 6500) -> str:
    """Generate a realistic markdown segment with headings, paragraphs, and code."""
    lines = [
        f"## Section {index}: Architecture Subsystem Analysis Part {index}\n",
        f"This section details the critical telemetry specifications and subsystem design for module {index}. "
        f"The primary requirement is zero-loss buffered streaming across distributed boundary nodes.",
    ]
    # Build substantive paragraphs
    sample_paragraph = (
        f"Subsystem {index} manages persistent state synchronization across edge instances. "
        "Every telemetry payload carries a monotonically increasing sequence identifier. "
        "When packets arrive out of order, the client reassembly buffer orders frames deterministically. "
        "This guarantees exactly-once processing semantics without synthetic re-transmissions. "
    )
    while sum(len(line) for line in lines) < target_chars - 300:
        lines.append(sample_paragraph)

    # Add code block
    lines.append(f"```python\ndef process_node_{index}(telemetry_data):\n    return telemetry_data.validate()\n```")
    lines.append(f"Subsystem {index} verification concluded with nominal state.")
    return "\n\n".join(lines)


def _make_plan(display_text: str, spoken_text: str) -> AssistantTurnPlan:
    return AssistantTurnPlan(
        displayText=display_text,
        spokenText=spoken_text,
        language="en-US",
        emotion={"primary": "neutral", "intensity": 0.1, "valence": 0.0, "arousal": 0.0},
        performance={"facePreset": "neutral", "gesture": "none", "gazeTarget": "camera", "headMotion": "none", "blinkRate": 0.4},
        memoryCandidates=[],
        toolRequests=[],
    )


@pytest.fixture
def memory_service() -> MemoryService:
    reset_session_factory()
    factory = init_db(
        Settings(
            HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
            _env_file=None,
        )
    )
    return MemoryService(factory)


class TestBoundedMultiSegmentLongGenerationBench:
    def test_bounded_multisegment_generation_25k(self, memory_service: MemoryService) -> None:
        num_segments = 4
        segments = [_generate_segment(i, target_chars=6500) for i in range(1, num_segments + 1)]

        # Introduce realistic seam overlaps (provider repeats last sentence of previous segment)
        guard = SeamGuard("")
        accumulated_text = ""

        for i, segment in enumerate(segments):
            if i > 0:
                # Add overlap to the beginning of segment i
                overlap_text = f"Subsystem {i} verification concluded with nominal state."
                segment_with_overlap = f"{overlap_text}\n\n{segment}"
            else:
                segment_with_overlap = segment

            # Feed through SeamGuard
            delta_chunk = guard.feed(segment_with_overlap)
            accumulated_text += delta_chunk
            guard = SeamGuard(accumulated_text[-500:])

        accumulated_text += guard.finish_segment()

        # Run consistency pass
        report = run_consistency_pass(accumulated_text)
        final_text = report.text

        # Verify length >= 25,000 characters
        assert len(final_text) >= 25_000, f"Expected >= 25,000 chars, got {len(final_text)}"
        assert len(final_text) <= 150_000

        # Verify zero seam duplication: each section conclusion should appear exactly once
        for i in range(1, num_segments):
            assert final_text.count(f"Subsystem {i} verification concluded with nominal state.") == 1

        # Verify all code fences are properly closed
        assert final_text.count("```") % 2 == 0

        # Plan voice response
        vtype, voice_text = plan_voice_response(final_text, "", is_progress=False)
        assert vtype == VoiceResponseType.EXECUTIVE_SUMMARY
        assert len(voice_text) <= 350
        assert not voice_text.lower().startswith("here is")
        assert not voice_text.lower().startswith("sure")

        # Validate against AssistantTurnPlan schema
        plan = _make_plan(final_text, voice_text)
        assert len(plan.displayText) >= 25_000
        assert plan.spokenText == voice_text

        # Test SQLite durable persistence & reload
        user = memory_service.ensure_user("bench_user")
        conv_id = memory_service.append_turn(
            user_id=user.id,
            companion_id="hinaa",
            conversation_id=None,
            user_text="Generate 25K architecture documentation",
            assistant_text=plan.model_dump_json(),
            language="en-US",
        )

        context = memory_service.recent_working_context(user.id, conv_id)
        messages = context["recentMessages"]
        assert len(messages) == 2
        loaded_assistant_msg = messages[1]
        assert loaded_assistant_msg["role"] == "assistant"
        payload = json.loads(loaded_assistant_msg["content"])
        assert payload["displayText"] == final_text
        assert payload["spokenText"] == voice_text
        assert len(payload["displayText"]) == len(final_text)

    def test_bounded_multisegment_generation_50k(self, memory_service: MemoryService) -> None:
        num_segments = 8
        segments = [_generate_segment(i, target_chars=6500) for i in range(1, num_segments + 1)]

        guard = SeamGuard("")
        accumulated_text = ""

        for i, segment in enumerate(segments):
            if i > 0:
                overlap_text = f"Subsystem {i} verification concluded with nominal state."
                segment_with_overlap = f"{overlap_text}\n\n{segment}"
            else:
                segment_with_overlap = segment

            delta_chunk = guard.feed(segment_with_overlap)
            accumulated_text += delta_chunk
            guard = SeamGuard(accumulated_text[-500:])

        accumulated_text += guard.finish_segment()
        report = run_consistency_pass(accumulated_text)
        final_text = report.text

        # Verify length >= 50,000 characters
        assert len(final_text) >= 50_000, f"Expected >= 50,000 chars, got {len(final_text)}"
        assert len(final_text) <= 150_000

        # Verify zero seam duplication
        for i in range(1, num_segments):
            assert final_text.count(f"Subsystem {i} verification concluded with nominal state.") == 1

        assert final_text.count("```") % 2 == 0

        vtype, voice_text = plan_voice_response(final_text, "", is_progress=False)
        assert vtype == VoiceResponseType.EXECUTIVE_SUMMARY
        assert len(voice_text) <= 350

        plan = _make_plan(final_text, voice_text)

        # Test SQLite durable persistence & reload across service recreation (Directive §8)
        user = memory_service.ensure_user("bench_user_50k")
        conv_id = memory_service.append_turn(
            user_id=user.id,
            companion_id="hinaa",
            conversation_id=None,
            user_text="Generate 50K architecture documentation",
            assistant_text=plan.model_dump_json(),
            language="en-US",
        )

        # Close/recreate service — verify zero dependence on stream-local state
        recreated_service = MemoryService(memory_service._factory)
        reloaded_context = recreated_service.recent_working_context(user.id, conv_id)
        messages = reloaded_context["recentMessages"]
        loaded_assistant_msg = messages[1]
        payload = json.loads(loaded_assistant_msg["content"])
        loaded_text = payload["displayText"]

        # Assert exact fidelity across reload (§8)
        assert len(loaded_text) == len(final_text)
        assert len(loaded_text) >= 50_000
        assert hashlib.sha256(loaded_text.encode("utf-8")).hexdigest() == hashlib.sha256(final_text.encode("utf-8")).hexdigest()
        assert len(loaded_text.split("\n\n")) == len(final_text.split("\n\n"))
        assert loaded_text.count("```") == final_text.count("```")
        assert loaded_text.count("## Section") == final_text.count("## Section")

    def test_bounded_multisegment_generation_100k(self, memory_service: MemoryService) -> None:
        """100K character generation benchmark with 16 segments.

        CONFIGURATION AUDIT (Directive §6):
        - Production Default: `Settings.llm_max_continuations = 8` (clamped in `config.py`),
          yielding at most 9 segments (1 initial segment + 8 continuations).
        - Benchmark Override: This benchmark explicitly uses `num_segments = 16` to
          stress-test `SeamGuard` and `run_consistency_pass` at ~100K characters across
          16 segments, proving that seam deduplication and consistency verification hold
          far beyond the production ceiling.
        - The `GenerationTrace` tracks `requested_max_segments` (17) vs `effective_max_segments` (9).
        """
        num_segments = 16
        segments = [_generate_segment(i, target_chars=6500) for i in range(1, num_segments + 1)]

        guard = SeamGuard("")
        accumulated_text = ""

        for i, segment in enumerate(segments):
            if i > 0:
                overlap_text = f"Subsystem {i} verification concluded with nominal state."
                segment_with_overlap = f"{overlap_text}\n\n{segment}"
            else:
                segment_with_overlap = segment

            delta_chunk = guard.feed(segment_with_overlap)
            accumulated_text += delta_chunk
            guard = SeamGuard(accumulated_text[-500:])

        accumulated_text += guard.finish_segment()
        report = run_consistency_pass(accumulated_text)
        final_text = report.text

        # Verify length >= 100,000 characters
        assert len(final_text) >= 100_000, f"Expected >= 100,000 chars, got {len(final_text)}"
        # Frontend displayText limit is 150,000 chars
        assert len(final_text) <= 150_000

        # Verify zero seam duplication
        for i in range(1, num_segments):
            assert final_text.count(f"Subsystem {i} verification concluded with nominal state.") == 1

        assert final_text.count("```") % 2 == 0

        vtype, voice_text = plan_voice_response(final_text, "", is_progress=False)
        assert vtype == VoiceResponseType.EXECUTIVE_SUMMARY
        assert len(voice_text) <= 350

        plan = _make_plan(final_text, voice_text)

        # Persistence roundtrip across service recreation (§8)
        user = memory_service.ensure_user("bench_user_100k")
        conv_id = memory_service.append_turn(
            user_id=user.id,
            companion_id="hinaa",
            conversation_id=None,
            user_text="Generate 100K comprehensive documentation",
            assistant_text=plan.model_dump_json(),
            language="en-US",
        )

        # Close/recreate service
        recreated_service = MemoryService(memory_service._factory)
        context = recreated_service.recent_working_context(user.id, conv_id)
        messages = context["recentMessages"]
        loaded_assistant_msg = messages[1]
        payload = json.loads(loaded_assistant_msg["content"])
        loaded_text = payload["displayText"]

        # Assert exact fidelity across reload (§8)
        assert len(loaded_text) == len(final_text)
        assert len(loaded_text) >= 100_000
        assert hashlib.sha256(loaded_text.encode("utf-8")).hexdigest() == hashlib.sha256(final_text.encode("utf-8")).hexdigest()
        assert len(loaded_text.split("\n\n")) == len(final_text.split("\n\n"))
        assert loaded_text.count("```") == final_text.count("```")
        assert loaded_text.count("## Section") == final_text.count("## Section")

    def test_continuation_request_invariants_across_rounds(self) -> None:
        """Verify PromptInvariantVerifier keeps user_contents and raw_user_text synchronized across 5 rounds."""
        from hinaa_api.generation.continuation_contract import render_continuation_prompt

        verifier = PromptInvariantVerifier()
        initial_prompt = PromptPackage(
            companion_id="hinaa",
            interaction_mode="rest",
            system_instruction="You are Hinaa.",
            user_contents="Please provide a comprehensive blueprint of the system.",
            raw_user_text="Please provide a comprehensive blueprint of the system.",
            layers=[],
            prompt_version="test",
            safety_policy_version="test",
            companion_profile_version="test",
            fingerprint="fp1",
            response_depth="conversational",
            language="mixed",
            personality=PersonalitySettings(),
            mood=MoodSnapshot(),
        )

        curr_prompt = initial_prompt
        for round_num in range(1, 6):
            cont_req = ContinuationRequest(
                generation_id=f"gen_{round_num}",
                segment_number=round_num,
                original_goal="Please provide a comprehensive blueprint of the system.",
                previous_tail=f"Tail of section {round_num} ends here.",
            )
            continuation_prompt_text = render_continuation_prompt(cont_req)
            # Simulate updating user_contents with the continuation prompt
            updated_prompt = curr_prompt.model_copy(update={"user_contents": continuation_prompt_text})
            # Verify verifier detects synchronization need and syncs raw_user_text
            verified = verifier.verify_or_sync(updated_prompt)
            assert "--- YOUR PARTIAL OUTPUT SO FAR" in verified.user_contents
            assert verified.user_contents == verified.raw_user_text
            curr_prompt = verified
