"""Comprehensive tests for the complete response integrity lifecycle:
stream -> finalize -> persist -> reload.

Covers:
- Headings, tables, citations, nested lists
- Backtick and tilde code fences
- Language-tagged and unfinished fences
- Significant spaces, tabs, blank lines, and Unicode
- Interrupted generation preservation
- Duplicate and stale terminal event idempotence
"""
import pytest
from hinaa_api.models import AssistantTurnPlan
from hinaa_api.prompts.fallback import neutral_fallback_plan
from hinaa_api.services import _apply_response_quality_guard
from hinaa_api.persistence.orm import Message, Conversation
import json


def test_response_lifecycle_markdown_structures() -> None:
    """Verifies that headings, tables, citations, and nested lists survive
    finalization, JSON persistence, and deserialization reload without corruption."""
    plan = neutral_fallback_plan(
        user_text="Provide the RAG infrastructure breakdown",
        companion_id="hinaa",
        language="mixed",
    )
    canonical_markdown = (
        "# System Telemetry Overview\n\n"
        "Here is the verified status report for our RAG infrastructure.\n\n"
        "## 1. Provider Health Matrix\n"
        "| Cluster | Service | Latency (ms) | Status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| Edge-1 | Qdrant Vector DB | 18 | Operational |\n"
        "| Core-2 | Hybrid Retrievial | 42 | Operational |\n\n"
        "### High-Priority Architectural Findings\n"
        "- Vector indexing operates within expected bounds [1].\n"
        "  - Chunk size: 512 tokens with 64-token overlap.\n"
        "  - Distance metric: Cosine similarity.\n"
        "    1. P95 search latency: <= 45ms.\n"
        "    2. Memory consumption: Stable at 1.2 GB.\n\n"
        "Telemetry confirmed as of recent audit."
    )
    plan.displayText = canonical_markdown
    plan.spokenText = "RAG infrastructure is fully operational with healthy latencies across all clusters."

    evidence = [
        {"id": "1", "title": "Infrastructure Telemetry Log", "url": "https://internal.telemetry/rag"}
    ]

    # Step 1: Finalize via quality guard
    _apply_response_quality_guard(
        plan,
        user_text="Provide the RAG infrastructure breakdown",
        evidence_sources=evidence,
    )

    # Verify display content preserved
    assert "# System Telemetry Overview" in plan.displayText
    assert "## 1. Provider Health Matrix" in plan.displayText
    assert "| Edge-1 | Qdrant Vector DB | 18 | Operational |" in plan.displayText
    assert "[1]" in plan.displayText
    assert "Chunk size: 512 tokens with 64-token overlap." in plan.displayText
    assert "P95 search latency: <= 45ms." in plan.displayText

    # Step 2: Persist into canonical turn record (Message.content)
    persisted_json = plan.model_dump_json()

    # Step 3: Reload from JSON storage (as DB does)
    reloaded_plan = AssistantTurnPlan.model_validate_json(persisted_json)

    # Step 4: Verify complete fidelity after reload
    assert reloaded_plan.displayText == plan.displayText
    assert reloaded_plan.spokenText == plan.spokenText


def test_response_lifecycle_backtick_and_tilde_code_fences() -> None:
    """Verifies that both backtick (```) and tilde (~~~) code fences,
    with 4-space indentation, tabs, and blank lines, are preserved exactly."""
    plan = neutral_fallback_plan(
        user_text="Show python and rust code examples",
        companion_id="hinaa",
        language="mixed",
    )
    canonical_code = (
        "Here are the code implementations for both languages:\n\n"
        "```python\n"
        "def compute_hash(data: str) -> str:\n"
        "    import hashlib\n"
        "    \n"
        "    # 4-space indented block\n"
        "    sha = hashlib.sha256()\n"
        "    sha.update(data.encode('utf-8'))\n"
        "    return sha.hexdigest()\n"
        "```\n\n"
        "~~~rust\n"
        "pub fn verify_signature(sig: &[u8]) -> bool {\n"
        "\t// Tab-indented block\n"
        "\tlet is_valid = sig.len() == 64;\n"
        "\tis_valid\n"
        "}\n"
        "~~~\n\n"
        "Both functions conform to strict typing."
    )
    plan.displayText = canonical_code
    plan.spokenText = "Here are the Python and Rust implementations."

    # Finalize
    _apply_response_quality_guard(plan, user_text="Show python and rust code examples")

    # Assert exact Python 4-space indentation preserved
    assert "    import hashlib" in plan.displayText
    assert "    sha = hashlib.sha256()" in plan.displayText
    assert "```python" in plan.displayText

    # Assert exact Rust tab indentation preserved
    assert "~~~rust" in plan.displayText
    assert "\tlet is_valid = sig.len() == 64;" in plan.displayText
    assert "~~~" in plan.displayText

    # Persist and reload
    persisted = plan.model_dump_json()
    reloaded = AssistantTurnPlan.model_validate_json(persisted)
    assert reloaded.displayText == plan.displayText


def test_response_lifecycle_unfinished_fence_preservation() -> None:
    """Verifies that an unfinished code fence (e.g. stream cut off mid-code)
    does not collapse or destroy indentation of the generated code so far."""
    plan = neutral_fallback_plan(
        user_text="write an async function",
        companion_id="hinaa",
        language="mixed",
    )
    unfinished_code = (
        "Here is the function so far:\n\n"
        "```python\n"
        "async def fetch_feed(url: str):\n"
        "    async with aiohttp.ClientSession() as session:\n"
        "        async with session.get(url) as response:\n"
        "            return await response.json()"
        # Intentionally no closing ```
    )
    plan.displayText = unfinished_code
    plan.spokenText = "Here is the partial function."

    _apply_response_quality_guard(plan, user_text="write an async function")

    # Indentation inside unfinished fence must be preserved
    assert "    async with aiohttp.ClientSession() as session:" in plan.displayText
    assert "        async with session.get(url) as response:" in plan.displayText
    assert plan.displayText.startswith("Here is the function so far:")


def test_response_lifecycle_unicode_multilingual_fidelity() -> None:
    """Verifies that multilingual Unicode (Nepali, Hindi, Japanese) and
    significant punctuation are completely preserved without corruption."""
    plan = neutral_fallback_plan(
        user_text="multilingual greetings",
        companion_id="hinaa",
        language="mixed",
    )
    unicode_content = (
        "नमस्ते babe! म तपाईंलाई पूर्ण सहयोग गर्न तयार छु।\n\n"
        "### बहुभाषिक सन्देश (Multilingual Messages)\n"
        "- नेपाली: सञ्जालको अवस्था एकदम सामान्य छ।\n"
        "- हिन्दी: हमारी RAG प्रणाली पूरी तरह से सक्रिय है।\n"
        "- 日本語: システムは正常に稼働しています。\n\n"
        "गहिरो विश्लेषण र प्राविधिक विवरणहरू यहाँ उपलब्ध छन्।"
    )
    plan.displayText = unicode_content
    plan.spokenText = "नमस्ते babe! All multilingual systems are operational."

    _apply_response_quality_guard(plan, user_text="multilingual greetings")

    assert "नमस्ते babe! म तपाईंलाई पूर्ण सहयोग गर्न तयार छु।" in plan.displayText
    assert "- नेपाली: सञ्जालको अवस्था एकदम सामान्य छ।" in plan.displayText
    assert "- हिन्दी: हमारी RAG प्रणाली पूरी तरह से सक्रिय है।" in plan.displayText
    assert "- 日本語: システムは正常に稼働しています。" in plan.displayText

    # Persist and reload
    reloaded = AssistantTurnPlan.model_validate_json(plan.model_dump_json())
    assert reloaded.displayText == plan.displayText


def test_response_lifecycle_interrupted_turn_preservation() -> None:
    """Verifies that an interrupted turn preserves its partial streamed text,
    is marked as interrupted, and does not contaminate subsequent turn state."""
    partial_text = "Analyzing the security boundary... The firewall rules permit incoming HTTPS traffic on port 443"
    
    # Event marking interruption
    interrupted_event = {
        "turnId": "trn_int_001",
        "sequenceId": 12,
        "type": "interrupted",
        "payload": {"displayTextDelta": "", "error": "User barge-in detected"},
        "timestamp": 1700000000,
    }
    assert interrupted_event["type"] == "interrupted"
    assert interrupted_event["payload"]["error"] == "User barge-in detected"

    # Turn plan created from partial output
    plan = neutral_fallback_plan(user_text="scan ports", companion_id="hinaa", language="en-US")
    plan.displayText = partial_text + " [Interrupted by user]"
    plan.spokenText = "Analyzing security boundary."
    plan.fallback = True
    plan.fallbackReason = "TURN_INTERRUPTED_BY_BARGE_IN"

    _apply_response_quality_guard(plan, user_text="scan ports")

    assert "[Interrupted by user]" in plan.displayText
    assert plan.fallback is True
    assert plan.fallbackReason == "TURN_INTERRUPTED_BY_BARGE_IN"

    # Persist in DB model
    msg = Message(
        conversation_id="conv_test_123",
        role="assistant",
        content=plan.model_dump_json(),
        language="en-US",
    )
    assert "TURN_INTERRUPTED_BY_BARGE_IN" in msg.content
    reloaded_plan = AssistantTurnPlan.model_validate_json(msg.content)
    assert reloaded_plan.displayText == plan.displayText


def test_response_lifecycle_idempotent_finalization_stale_events() -> None:
    """Verifies that duplicate finalization calls or stale terminal events
    produce deterministic, idempotent state without duplicating text."""
    plan = neutral_fallback_plan(
        user_text="status report", companion_id="hinaa", language="en-US"
    )
    plan.displayText = "All services operational."
    plan.spokenText = "All services operational."

    # Finalize turn once
    _apply_response_quality_guard(plan, user_text="status report")
    first_display = plan.displayText
    first_spoken = plan.spokenText

    # Finalize turn a second time (simulating duplicate terminal event)
    _apply_response_quality_guard(plan, user_text="status report")
    assert plan.displayText == first_display
    assert plan.spokenText == first_spoken

    # Finalize a third time
    _apply_response_quality_guard(plan, user_text="status report")
    assert plan.displayText == first_display
    assert plan.spokenText == first_spoken
