"""Liveness semantics for one live brain attempt.

Guards the fix for a measured production bug: a wall-clock timeout killed
Claude 31k characters into a real report, and a fallback brain answered in the
client's place. A long answer must survive; only a silent one may be abandoned.
"""

from __future__ import annotations

import asyncio

import pytest

from hinaa_api.config import Settings
from hinaa_api.prompts.performance import build_plan_from_text
from hinaa_api.services import live_generation_window


async def _drain(
    *,
    tokens: int,
    gap_s: float,
    ceiling_s: float,
    idle_s: float,
) -> tuple[str, list[str], bool, list[str]]:
    forwarded: list[str] = []
    sink: list[str] = []

    async def forward(delta: str) -> None:
        forwarded.append(delta)

    expired_idle = False
    try:
        async with live_generation_window(
            ceiling_s=ceiling_s, idle_s=idle_s, forward=forward, sink=sink
        ) as (emit, idle_expired):
            for index in range(tokens):
                await asyncio.sleep(gap_s)
                await emit(f"t{index}")
            expired_idle = idle_expired()
            outcome = "completed"
    except TimeoutError:
        outcome = "timeout"
        expired_idle = idle_expired()
    return outcome, forwarded, expired_idle, sink


@pytest.mark.asyncio
async def test_steady_tokens_survive_a_tight_idle_window() -> None:
    # 1.2s of work inside a 0.15s idle window: length alone must not kill it.
    outcome, forwarded, idle_expired, sink = await _drain(
        tokens=60, gap_s=0.02, ceiling_s=10.0, idle_s=0.15
    )
    assert outcome == "completed"
    assert len(forwarded) == 60
    assert sink == forwarded
    assert idle_expired is False


@pytest.mark.asyncio
async def test_silent_stream_is_abandoned_at_the_idle_limit() -> None:
    outcome, forwarded, idle_expired, _ = await _drain(
        tokens=2, gap_s=0.6, ceiling_s=10.0, idle_s=0.15
    )
    assert outcome == "timeout"
    assert idle_expired is True
    assert len(forwarded) < 2


@pytest.mark.asyncio
async def test_absolute_ceiling_still_bounds_a_never_ending_stream() -> None:
    # Tokens keep flowing, so only the hung-connection backstop can end this.
    outcome, _, idle_expired, _ = await _drain(
        tokens=200, gap_s=0.02, ceiling_s=0.5, idle_s=5.0
    )
    assert outcome == "timeout"
    assert idle_expired is False


@pytest.mark.asyncio
async def test_sink_is_optional_for_callers_that_only_need_liveness() -> None:
    async def forward(_delta: str) -> None:
        return None

    async with live_generation_window(
        ceiling_s=5.0, idle_s=0.2, forward=forward
    ) as (emit, _expired):
        await emit("a")
        await asyncio.sleep(0.1)
        await emit("b")
        await asyncio.sleep(0.1)
        await emit("c")


def test_salvaged_spoken_summary_scales_with_depth() -> None:
    body = "\n\n".join(
        f"### Section {index}\n\n" + " ".join(
            f"Sentence {index}.{sentence} explains a subsystem in detail."
            for sentence in range(12)
        )
        for index in range(14)
    )
    report = build_plan_from_text(
        text=body, companion_id="hinaa", language="en-US", depth="report"
    )
    minimal = build_plan_from_text(
        text=body, companion_id="hinaa", language="en-US", depth="minimal"
    )
    assert report.displayText == body
    assert len(report.spokenText) > len(minimal.spokenText)
    assert len(minimal.spokenText) <= 220


def test_report_spoken_summary_is_not_cut_short_by_one_long_sentence() -> None:
    """Measured: a 38,783-char report got a 470-character spoken summary.

    The walk stopped at the first sentence that no longer fit, so she described
    a 5,900-word document in one breath and then asked to walk through it.
    """
    monster = "Each subsystem records provider, model, tool, latency, token and failure metadata " * 22 + "."
    tail = " ".join(
        f"Section {index} explains how one part of her runtime actually behaves."
        for index in range(12)
    )
    body = (
        "HINAA is a multi-modal companion system built on a layered architecture.\n\n"
        + monster
        + "\n\n"
        + tail
    )
    plan = build_plan_from_text(
        text=body, companion_id="hinaa", language="en-US", depth="report"
    )
    assert len(plan.spokenText) > 700
    assert "failure metadata" not in plan.spokenText
    assert not plan.spokenText.endswith("…")
    assert plan.spokenText.rstrip().endswith((".", "!", "?"))


def test_live_ceiling_ignores_a_low_ops_request_timeout() -> None:
    """This deployment sets HINAA_LLM_TIMEOUT_SECONDS=90; that must not end a live turn.

    Measured production failure: Claude streamed 30,988 characters of a real
    report and was cut at 90s, then gemini-3.5-flash-lite answered in its place
    and the client labelled the whole reply as coming from the fallback brain.
    """
    settings = Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        HINAA_LLM_TIMEOUT_SECONDS=90,
    )
    assert settings.llm_timeout_seconds == 90.0
    assert settings.llm_stream_ceiling_seconds > settings.llm_timeout_seconds


def test_live_ceiling_never_drops_below_the_idle_timeout() -> None:
    """Otherwise silence never gets to decide and length kills the answer again."""
    settings = Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        HINAA_LLM_STREAM_IDLE_TIMEOUT_SECONDS=120,
        HINAA_LLM_STREAM_CEILING_SECONDS=30,
    )
    assert settings.llm_stream_ceiling_seconds > settings.llm_stream_idle_timeout_seconds
    assert any("idle timeout" in c for c in settings.generation_config_corrections)
