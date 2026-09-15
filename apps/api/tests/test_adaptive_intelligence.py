from __future__ import annotations

import pytest
from hinaa_api.intelligence.answer_depth import AnswerDepth, AnswerDepthController
from hinaa_api.intelligence.research_detector import ResearchNeedDetector


def test_answer_depth_inference():
    # Quick queries
    assert AnswerDepthController.infer_depth("hi") == AnswerDepth.QUICK
    assert AnswerDepthController.infer_depth("hi hina") == AnswerDepth.QUICK
    assert AnswerDepthController.infer_depth("what is 4+4?") == AnswerDepth.QUICK
    assert AnswerDepthController.infer_depth("capital of France") == AnswerDepth.QUICK
    assert AnswerDepthController.infer_depth("give me a quick answer on Python GIL") == AnswerDepth.QUICK

    # Standard query
    assert AnswerDepthController.infer_depth("what is Next.js?") == AnswerDepth.STANDARD
    assert AnswerDepthController.infer_depth("What are some good anime to watch this weekend?") == AnswerDepth.STANDARD

    # Detailed query
    assert AnswerDepthController.infer_depth("how does Next.js routing work?") == AnswerDepth.DETAILED
    assert AnswerDepthController.infer_depth("Explain how vector embeddings work in RAG") == AnswerDepth.DETAILED
    assert AnswerDepthController.infer_depth("What are the pros and cons of SQLite vs Postgres?") == AnswerDepth.DETAILED

    # Deep query
    assert AnswerDepthController.infer_depth("design the ideal Next.js architecture for my Hina app") == AnswerDepth.DEEP
    assert AnswerDepthController.infer_depth("research the best production design and compare options") == AnswerDepth.DEEP
    assert AnswerDepthController.infer_depth("Deep dive into the architecture of distributed consensus algorithms") == AnswerDepth.DEEP
    assert AnswerDepthController.infer_depth("System design for high-throughput WebSocket message broker with trade-offs") == AnswerDepth.DEEP

    # Exhaustive / Artifact query
    assert AnswerDepthController.infer_depth("give me the complete implementation specification") == AnswerDepth.EXHAUSTIVE
    assert AnswerDepthController.infer_depth("make it 10,000 lines") == AnswerDepth.EXHAUSTIVE
    assert AnswerDepthController.infer_depth("Provide a complete specification covering all edge cases and failure modes") == AnswerDepth.EXHAUSTIVE



def test_research_need_detection():
    # Temporal & current event queries need research
    needs_res, q = ResearchNeedDetector.needs_research("What happened in Nepal today?")
    assert needs_res is True
    assert "nepal today" in q.lower()

    needs_res, q = ResearchNeedDetector.needs_research("latest news on quantum computing breakthrough")
    assert needs_res is True

    # General static queries do not need live research
    needs_res, q = ResearchNeedDetector.needs_research("how to reverse a linked list in Python")
    assert needs_res is False
