from __future__ import annotations

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from hinaa_api.main import create_app
from hinaa_api.prompts.assembly import assemble_prompt
from hinaa_api.prompts.models import PromptInput
from hinaa_api.prompts.turn_prompt import build_turn_prompt
from hinaa_api.models import TurnRequest
from hinaa_api.config import Settings
from hinaa_api.rag import RAGKnowledgeService


def test_rag_knowledge_service_lifecycle(tmp_path: Path):
    # Setup mock .hina directory
    hina_dir = tmp_path / ".hina"
    hina_dir.mkdir(parents=True)
    (hina_dir / "architecture.md").write_text(
        "# HINAA Architecture\n\n## Subsystems\n- Harness operating core\n- RAG hybrid retriever\n- Realtime audio barge-in\n",
        encoding="utf-8",
    )
    (hina_dir / "security.md").write_text(
        "# Security Policy\n\n## GHSA Mitigation\nStrict canonical realpath containment prevents path traversal.\n",
        encoding="utf-8",
    )

    svc = RAGKnowledgeService(workspace_root=str(tmp_path))
    indexed = svc.index_repository_memory()
    assert indexed == 2
    assert svc.total_chunks >= 2
    assert svc.total_documents == 2

    # Verify knowledge seeking detection
    assert svc.is_knowledge_seeking("Explain the architecture of HINAA") is True
    assert svc.is_knowledge_seeking("What is the security policy for canonical paths?") is True
    assert svc.is_knowledge_seeking("Hello there, how are you?") is False

    # Test hybrid query
    results = svc.query("Harness operating core RAG", top_k=2)
    assert len(results) > 0
    assert "Harness operating core" in results[0].result.chunk.text
    assert results[0].final_score > 0.0

    # Test context formatting
    block = svc.format_context_block("Harness operating core")
    assert "RETRIEVED REPOSITORY & DOCUMENTATION EVIDENCE" in block
    assert "architecture.md" in block
    assert "RAG MANDATE" in block

    # Ingest custom doc
    chunks = svc.ingest_document(
        text="FastAPI backend runs on port 8000 and is load balanced across multi-cloud regions.",
        document_id="doc_backend_config",
        source="backend_guide.md",
    )
    assert len(chunks) >= 1
    assert svc.total_documents == 3

    # Query new doc
    res_custom = svc.query("FastAPI backend port 8000")
    assert any("port 8000" in r.result.chunk.text for r in res_custom)


def test_prompt_assembly_with_rag_context():
    rag_block = "RETRIEVED REPOSITORY & DOCUMENTATION EVIDENCE:\n[RAG-1] .hina/security.md: Canonical roots enforced."
    inp = PromptInput(
        companion_id="hinaa",
        interaction_mode="rest",
        user_text="What are your security invariants?",
        rag_context_block=rag_block,
    )
    package = assemble_prompt(inp)

    # Verify RAG layer presence
    rag_layer = next((l for l in package.layers if l.name == "rag_knowledge_context"), None)
    assert rag_layer is not None
    assert rag_layer.trusted is False
    assert "Canonical roots enforced" in rag_layer.text

    # Verify user_contents includes note
    assert "GROUNDED REPOSITORY & DOCUMENTATION EVIDENCE IS ATTACHED" in package.user_contents


def test_rag_rest_endpoints():
    app = create_app()
    client = TestClient(app)

    # 1. Status
    res_status = client.get("/v1/rag/status")
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert data_status["status"] == "success"
    assert "total_chunks" in data_status

    # 2. Ingest
    res_ingest = client.post(
        "/v1/rag/ingest",
        json={
            "document_id": "doc_test_api",
            "source": "api_test.md",
            "content": "# Autonomous Core\nHINAA coordinates distributed subagents and verifies outputs.",
        },
    )
    assert res_ingest.status_code == 200
    assert res_ingest.json()["chunks_created"] >= 1

    # 3. Query
    res_query = client.post(
        "/v1/rag/query",
        json={
            "query": "Autonomous Core subagents",
            "top_k": 3,
        },
    )
    assert res_query.status_code == 200
    data_query = res_query.json()
    assert data_query["total_matches"] >= 1
    assert "Autonomous Core" in data_query["results"][0]["text"]
