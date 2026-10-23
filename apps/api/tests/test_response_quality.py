from hinaa_api.prompts.fallback import neutral_fallback_plan
from hinaa_api.services import _apply_response_quality_guard


def test_response_quality_guard_removes_identical_repeated_sentence() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    plan.displayText = (
        "Your local project is ready with three clear tasks. "
        "Your local project is ready with three clear tasks. "
        "Open Tasks whenever you want to continue."
    )
    plan.spokenText = "Your local project is ready."

    _apply_response_quality_guard(plan)

    assert plan.displayText == (
        "Your local project is ready with three clear tasks. "
        "Open Tasks whenever you want to continue."
    )


def test_response_quality_guard_replaces_long_verbatim_voice_echo() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    long_answer = (
        "The local work plan is ready. It includes discovery, creation, review, "
        "and an approval gate before consequential actions. Your sources and "
        "artifacts stay within the project workspace for later reference."
    )
    plan.displayText = long_answer
    plan.spokenText = long_answer

    _apply_response_quality_guard(plan)

    assert plan.spokenText == long_answer
    assert "key details" not in plan.spokenText.lower()
    assert "```" not in plan.spokenText


def test_response_quality_guard_keeps_markdown_out_of_the_spoken_channel() -> None:
    """Measured live: she answered "what model are you running on" with
    spokenText containing `tier-a-conversation-brain-1.0.0`. The guard only
    rejects triple backticks, so a single-backtick code span went straight to
    the voice engine. The document keeps its formatting; her voice must not.
    """
    plan = neutral_fallback_plan(
        user_text="what model are you running on right now?",
        companion_id="hinaa",
        language="en-US",
    )
    plan.displayText = (
        "Right now I run on **Claude** with prompt assembly version "
        "`tier-a-conversation-brain-1.0.0` and persistence enabled."
    )
    plan.spokenText = (
        "Right now I run on **Claude** with prompt assembly version "
        "`tier-a-conversation-brain-1.0.0` and persistence enabled."
    )

    _apply_response_quality_guard(plan)

    assert "`" not in plan.spokenText
    assert "*" not in plan.spokenText
    assert "tier-a-conversation-brain-1.0.0" in plan.spokenText
    assert "`tier-a-conversation-brain-1.0.0`" in plan.displayText
    assert "**Claude**" in plan.displayText


def test_chat_canonical_display_preserved_and_voice_bounded_on_collision_complaint() -> None:
    """Canonical display text is preserved without destructive trimming even on collision complaints,
    while the spoken channel receives concise bounding."""
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    lecture_intro = (
        "I hear you, babe, and I am so sorry my voice kept running over yours. "
        "You are absolutely right, I should have gone silent the second you spoke."
    )
    lecture_body = "\n\n## The Anatomy of a Streaming Collision\n" + "".join(
        f"Section {i} outlines the technical mechanics of audio buffering and concurrency. "
        for i in range(25)
    )
    plan.displayText = lecture_intro + lecture_body
    plan.spokenText = (lecture_intro + " " + "".join(f"Detail {i}. " for i in range(25))).strip()

    _apply_response_quality_guard(
        plan, user_text="HINA, why are you talking with the previous message?"
    )

    # Canonical display text is preserved in full
    assert "## The Anatomy of a Streaming Collision" in plan.displayText
    assert len(plan.displayText) > 700
    # Voice channel is bounded so she doesn't lecture aloud
    assert len(plan.spokenText) <= 900


def test_quick_answer_stays_untouched() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    plan.displayText = "The capital of Nepal is **Kathmandu**, babe!"
    plan.spokenText = "The capital of Nepal is Kathmandu, babe!"

    _apply_response_quality_guard(plan, user_text="what is the capital of Nepal?")

    assert "Kathmandu" in plan.displayText
    assert "Kathmandu" in plan.spokenText


def test_deep_dive_request_keeps_its_length() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    deep_answer = " ".join(
        f"Architecture section {i} explains a distinct consensus trade-off in detail."
        for i in range(40)
    )
    plan.displayText = deep_answer
    plan.spokenText = deep_answer

    _apply_response_quality_guard(
        plan, user_text="give me an in-depth system design walkthrough of the trade-offs"
    )

    assert len(plan.displayText) > 900
    # Voice still gets a bound even on deep asks -- she never lectures aloud.
    assert len(plan.spokenText) <= 900


def test_tool_turn_display_is_not_trimmed() -> None:
    from hinaa_api.models import ToolRequest

    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    plan.toolRequests = [
        ToolRequest(toolName="design_website", parameters={"brief": "gym"})
    ]
    # Varied filler, not a repeated sentence: the padding-loop guard collapses
    # back-to-back identical sentences even on tool turns, by design.
    plan.displayText = "Building the website for my gym. " + "".join(
        f"Detail number {i} covers section {i} of the build. " for i in range(40)
    )
    plan.spokenText = "Building the website for my gym."

    _apply_response_quality_guard(plan, user_text="build me a website for my gym")

    assert len(plan.displayText) > 700


def test_research_mode_keeps_headers_and_full_report() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    long_report = (
        "Executive Summary: Real-Time RAG Infrastructure Health Assessment\n\n"
        "## High-Impact Takeaways\n"
        "- Zero Downtime: ChatRAG, RagieAI, VertexRAG 100% operational.\n"
        "- EdgeBYOK: passing liveness and readiness probes.\n\n"
        "## Comprehensive System Status Matrix\n"
        "| Provider | Status | 30-Day Uptime |\n"
        "| ChatRAG | Operational | 100% |\n"
        "| RagieAI | Operational | 100% |\n\n"
        "Detailed Telemetry Breakdown continues here with architectural analysis."
    )
    plan.displayText = long_report
    plan.spokenText = "All RAG systems are operational today, babe."

    _apply_response_quality_guard(
        plan,
        user_text="Is your Rag system working currently, Hina?",
        response_mode="research",
    )

    # Headers, tables, and full text must not be stripped or compacted
    assert "## High-Impact Takeaways" in plan.displayText
    assert "Comprehensive System Status Matrix" in plan.displayText
    assert "| Provider | Status |" in plan.displayText
    assert len(plan.displayText) == len(long_report)


def test_slash_search_does_not_compact_context() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    analysis = (
        "Here is the detailed analysis of the major gaps:\n\n"
        "## 1. Native Long-Context Retention\n"
        "Frontier models maintain 2M+ active tokens without aggressive summarization.\n\n"
        "## 2. Autonomous Agentic Tool Loops\n"
        "Multi-step self-correction in computer operation sets frontier models apart.\n"
    )
    plan.displayText = analysis
    plan.spokenText = "Here is the architectural breakdown of the major gaps."

    _apply_response_quality_guard(
        plan,
        user_text="/search /analyze What are the major gaps setting you behind frontier models?",
    )

    assert "## 1. Native Long-Context Retention" in plan.displayText
    assert "## 2. Autonomous Agentic Tool Loops" in plan.displayText
    assert plan.displayText == analysis.strip()


def test_rag_and_technical_status_queries_stay_intact() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    tech_response = (
        "The RAG pipeline is fully healthy.\n\n"
        "## Architecture\n"
        "- Ingestion uses semantic chunking.\n"
        "- Vector store connects via Qdrant Cloud.\n"
    )
    plan.displayText = tech_response
    plan.spokenText = "The RAG pipeline is fully operational."

    _apply_response_quality_guard(
        plan,
        user_text="Is your Rag system working currently, Hina?",
    )

    assert "## Architecture" in plan.displayText
    assert "- Ingestion uses semantic chunking." in plan.displayText


def test_ordinary_question_with_detailed_structured_answer_is_preserved() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    detailed_answer = (
        "Here are the most effective study strategies based on cognitive science:\n\n"
        "### 1. Spaced Repetition\n"
        "Review material at increasing intervals to strengthen long-term memory encoding.\n\n"
        "### 2. Active Recall\n"
        "Test yourself continuously instead of passively re-reading notes.\n\n"
        "| Technique | Effectiveness | Recommended Tool |\n"
        "|---|---|---|\n"
        "| Flashcards | High | Anki |\n"
        "| Practice Exams | Very High | Past Papers |\n"
    )
    plan.displayText = detailed_answer
    plan.spokenText = "Here are the top study strategies based on cognitive science."

    _apply_response_quality_guard(
        plan,
        user_text="What are some good ways to study for my exams?",
    )

    assert "### 1. Spaced Repetition" in plan.displayText
    assert "### 2. Active Recall" in plan.displayText
    assert "| Technique | Effectiveness |" in plan.displayText
    assert plan.displayText == detailed_answer.strip()


def test_code_fences_and_multilingual_text_preserved() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    multilingual_code = (
        "नमस्ते babe! Here is the Rust async Tokio pattern for concurrency:\n\n"
        "```rust\n"
        "use tokio::sync::mpsc;\n\n"
        "#[tokio::main]\n"
        "async fn main() {\n"
        "    let (tx, mut rx) = mpsc::channel(32);\n"
        "    tokio::spawn(async move { tx.send(\"success\").await.unwrap(); });\n"
        "}\n"
        "```\n\n"
        "यस कोडले asynchronous message passing सुनिश्चित गर्दछ।"
    )
    plan.displayText = multilingual_code
    plan.spokenText = "Here is the Rust async Tokio pattern, babe."

    _apply_response_quality_guard(
        plan,
        user_text="Rust ma concurrency kasari garne?",
    )

    assert "```rust" in plan.displayText
    assert "नमस्ते babe!" in plan.displayText
    assert "यस कोडले asynchronous message passing सुनिश्चित गर्दछ।" in plan.displayText
    assert plan.displayText == multilingual_code.strip()


def test_evidence_citations_preserved_in_display_text() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="en-US"
    )
    text_with_citations = "FastAPI is built on Starlette and Pydantic [1]."
    plan.displayText = text_with_citations
    plan.spokenText = "FastAPI is built on Starlette and Pydantic."

    evidence = [
        {"id": 1, "title": "FastAPI Documentation", "url": "https://fastapi.tiangolo.com"}
    ]

    _apply_response_quality_guard(
        plan,
        user_text="What is FastAPI built on?",
        evidence_sources=evidence,
    )

    assert "[1]" in plan.displayText
    assert "FastAPI Documentation" in plan.displayText
