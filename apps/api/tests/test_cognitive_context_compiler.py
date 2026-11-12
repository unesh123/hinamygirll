from __future__ import annotations

import pytest
from hinaa_api.agent.compiler import ContextCompiler
from hinaa_api.agent.context_profiles import (
    ModelContextBudget,
    resolve_model_context_budget,
)
from hinaa_api.cognitive.context_compiler import ContextCompiler as CognitiveContextCompiler
from hinaa_api.cognitive.contracts import WorldState


def test_resolve_model_context_budget_matrix():
    # Gemini: 1M token ceiling
    gemini_budget = resolve_model_context_budget("gemini-3.5-flash", "gemini")
    assert gemini_budget.context_limit == 1_000_000
    assert gemini_budget.max_input_budget == 500_000
    assert gemini_budget.output_reserve == 8_192

    # Claude Opus: 200k token ceiling
    claude_budget = resolve_model_context_budget("claude-opus-5.5", "experiential")
    assert claude_budget.context_limit == 200_000
    assert claude_budget.max_input_budget == 150_000
    assert claude_budget.output_reserve == 4_096

    # Codestral: 128k ceiling
    codestral_budget = resolve_model_context_budget("mistralai/codestral-2508", "xkiro")
    assert codestral_budget.context_limit == 128_000
    assert codestral_budget.max_input_budget == 100_000
    assert codestral_budget.output_reserve == 4_096

    # GPT-4o / Respan: 128k ceiling
    respan_budget = resolve_model_context_budget("gpt-4o-mini", "respan")
    assert respan_budget.context_limit == 128_000
    assert respan_budget.max_input_budget == 96_000

    # Local / Mock: 16k ceiling (via provider="ollama")
    local_budget = resolve_model_context_budget("qwen2.5-coder", "ollama")
    assert local_budget.context_limit == 16_384
    assert local_budget.max_input_budget == 12_000


def test_dynamic_budget_in_canonical_context_compiler():
    # Dynamic compiler (max_tokens=None)
    compiler = ContextCompiler(max_tokens=None)

    # Simulate 30 turns of conversation
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}: {'detailed system prompt and context ' * 20}"}
        for i in range(30)
    ]

    # For Claude Opus 5.5, the compiler should allocate up to 150k tokens, preserving rich history
    compiled_claude = compiler.compile(
        system_identity="You are HINA.",
        user_query="Continue execution of singularity plan.",
        history=history,
        model_name="claude-opus-5.5",
        provider="experiential",
    )
    assert compiled_claude.manifest is not None
    assert compiled_claude.manifest.input_budget_tokens >= 100_000
    assert len(compiled_claude.dialogue_messages) > 10

    # For a small local model, the compiler respects tighter bounds
    compiled_local = compiler.compile(
        system_identity="You are HINA.",
        user_query="Continue execution of singularity plan.",
        history=history,
        model_name="llama3.2:1b",
        provider="ollama",
    )
    assert compiled_local.manifest is not None
    assert compiled_local.manifest.input_budget_tokens <= 16_384


def test_explicit_max_tokens_backward_compatibility():
    # Unit tests that explicitly pass max_tokens=300 must be strictly respected
    strict_compiler = ContextCompiler(max_tokens=300)
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}: {'detailed system prompt and context ' * 10}"}
        for i in range(10)
    ]
    compiled = strict_compiler.compile(
        system_identity="You are HINA.",
        user_query="Quick ping.",
        history=history,
        model_name="claude-opus-5.5",
    )
    assert compiled.manifest is not None
    assert compiled.manifest.input_budget_tokens == 300


def test_cognitive_context_compiler_dynamic_budget():
    cog_compiler = CognitiveContextCompiler()
    world = WorldState()

    compiled = cog_compiler.compile(
        query="What is the architecture?",
        world_state=world,
        user_id="user_123",
        model_name="gemini-3.5-flash",
        provider="gemini",
    )
    assert compiled.total_token_estimate >= 0
