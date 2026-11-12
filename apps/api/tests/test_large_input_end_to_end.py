"""
Tests for HINAA OS Large-Input End-to-End Handling and 8K Cap Elimination.
Verifies payloads from 8,000 up to 200,000 characters across request validation,
schema compliance, and beginning/middle/end content preservation without silent truncation.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from hinaa_api.models import TurnRequest, SpeechRequest
from hinaa_api.main import ProjectTaskBody, CreateTaskBody, ResolveTaskBody, SteerTaskBody, ProjectAgentRunBody


def generate_payload_with_markers(char_count: int) -> str:
    """Generate exact-length string with markers at start, middle, and end."""
    start_marker = "[[START_MARKER_V6]]"
    mid_marker = "[[MIDDLE_MARKER_V6]]"
    end_marker = "[[END_MARKER_V6]]"

    overhead = len(start_marker) + len(mid_marker) + len(end_marker)
    fill_needed = max(0, char_count - overhead)
    half_fill = fill_needed // 2
    rem_fill = fill_needed - half_fill

    payload = f"{start_marker}{'A' * half_fill}{mid_marker}{'B' * rem_fill}{end_marker}"
    assert len(payload) == char_count
    return payload


@pytest.mark.parametrize("size", [8_000, 25_000, 50_000, 100_000, 150_000, 200_000])
def test_large_input_turn_request_model(size: int):
    """Verify TurnRequest accepts payloads up to 200,000 chars without 8000 cap error."""
    payload = generate_payload_with_markers(size)
    req = TurnRequest(sessionId="sess-test", text=payload)

    assert len(req.text) == size
    assert req.text.startswith("[[START_MARKER_V6]]")
    assert "[[MIDDLE_MARKER_V6]]" in req.text
    assert req.text.endswith("[[END_MARKER_V6]]")


@pytest.mark.parametrize("size", [8_000, 25_000, 50_000, 100_000, 150_000, 200_000])
def test_large_input_fastapi_task_models(size: int):
    """Verify ProjectTaskBody, CreateTaskBody, etc. accept large goals up to 200K."""
    payload = generate_payload_with_markers(size)

    ptb = ProjectTaskBody(title="Large task", detail=payload)
    assert len(ptb.detail) == size

    ctb = CreateTaskBody(goal=payload)
    assert len(ctb.goal) == size

    rtb = ResolveTaskBody(text=payload)
    assert len(rtb.text) == size

    stb = SteerTaskBody(instruction=payload)
    assert len(stb.instruction) == size

    prb = ProjectAgentRunBody(goal=payload)
    assert len(prb.goal) == size


def test_schema_json_definitions_allow_200k():
    """Verify contracts/schemas JSON definitions specify 200K caps."""
    schema_dir = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "schemas"

    realtime_path = schema_dir / "realtime-event.schema.json"
    if realtime_path.exists():
        raw_text = realtime_path.read_text(encoding="utf-8")
        assert '"maxLength":200000' in raw_text or '"maxLength": 200000' in raw_text

    turn_plan_path = schema_dir / "assistant-turn-plan.schema.json"
    if turn_plan_path.exists():
        raw_text = turn_plan_path.read_text(encoding="utf-8")
        assert '"maxLength":150000' in raw_text or '"maxLength": 150000' in raw_text
