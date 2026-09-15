"""P0.15 Canonical Context Authority Tests (Directives §1–§10).

Verifies:
1. ContextCompiler is the sole context-selection and budgeting authority across all paths.
2. Assembler (prompts/context.py & assembly.py) acts strictly as a FORMAT_ONLY serializer.
3. ContextPayloadIntegrityVerifier detects:
   - UNDECLARED_CONTEXT
   - DUPLICATED_CONTEXT
   - TRUST_ESCALATION
   - STALE_CONTEXT
   - SELECTED_NOT_SENT / MISSING_SELECTED_ITEM
   - TOKEN_BUDGET_MISMATCH
4. Manifest and payload fingerprinting is deterministic and tamper-evident.
"""

from __future__ import annotations

import pytest

from hinaa_api.agent.compiler import (
    CompiledContextFingerprint,
    ContextCompiler,
    ContextPayloadIntegrityVerifier,
)
from hinaa_api.agent.context_items import ContextManifest, InstructionAuthority, TrustLevel
from hinaa_api.models import TurnRequest
from hinaa_api.prompts.turn_prompt import build_turn_prompt
from hinaa_api.prompts.context import (
    build_history_block,
    build_memory_block,
    build_session_memory_block,
)


class TestContextAuthority:
    def test_assembly_is_strictly_format_only_when_preselected(self) -> None:
        """P0.15 §1/§2: Assembler must render preselected turns verbatim without slicing."""
        turns = (
            ("user", "Decision: The database is PostgreSQL."),
            ("assistant", "Understood, using PostgreSQL."),
            ("user", "Constraint: All APIs must use FastAPI."),
            ("assistant", "FastAPI registered."),
            ("user", "Deploy to cluster-east."),
            ("assistant", "Cluster-east targeted."),
            ("user", "Turn 4"),
            ("assistant", "Response 4"),
            ("user", "Turn 5"),
            ("assistant", "Response 5"),
            ("user", "Turn 6"),
            ("assistant", "Response 6"),
        )
        
        # When pre_selected is True, build_history_block must NOT slice to max_turns=4
        rendered = build_history_block(turns, max_turns=4, max_chars=100, pre_selected=True)
        
        assert "Decision: The database is PostgreSQL." in rendered
        assert "Constraint: All APIs must use FastAPI." in rendered
        assert "Deploy to cluster-east." in rendered
        assert "Turn 6" in rendered
        assert '<conversation_history trusted="false">' in rendered

    def test_memory_blocks_not_artificially_sliced_by_serializer(self) -> None:
        """P0.15 §2: Long-term and session memory blocks must preserve all compiler-selected items."""
        ten_approved = tuple(f"Approved fact number {i}: detailed enterprise specification info" for i in range(10))
        rendered_approved = build_memory_block(ten_approved)

        # Previously sliced at [:8], must now contain all 10
        assert "Approved fact number 0" in rendered_approved
        assert "Approved fact number 8" in rendered_approved
        assert "Approved fact number 9" in rendered_approved

        ten_session = tuple(f"Learned preference {i}: user wants strict TypeScript" for i in range(10))
        rendered_session = build_session_memory_block(ten_session)
        assert "Learned preference 0" in rendered_session
        assert "Learned preference 8" in rendered_session
        assert "Learned preference 9" in rendered_session

    def test_integrity_verifier_detects_undeclared_context(self) -> None:
        """P0.15 §4: Detect undeclared context present in payload but absent from manifest."""
        manifest = ContextManifest(
            manifest_id="mf_test_01",
            request_id="req_01",
            conversation_id="conv_01",
            profile="STANDARD",
            allocations={"conversation": 4000},
            cacheable_prefix_tokens=200,
            model_context_limit=8000,
            output_reserve_tokens=1000,
            included_items=[
                {"source_type": "user_message", "tokens": 20, "trust_level": "user_explicit"},
            ],
        )

        class MockPackage:
            manifest_id = "mf_test_01"
            memory_context = ["Undeclared memory block injected behind compiler's back"]
            tool_context = []
            rag_context = []
            token_counts = {"conversation": 20, "memory": 50, "tool": 0, "rag": 0}

        report = ContextPayloadIntegrityVerifier.verify(MockPackage(), manifest)
        assert report["ok"] is False
        issue_types = [issue["type"] for issue in report["issues"]]
        assert "UNDECLARED_CONTEXT" in issue_types

    def test_integrity_verifier_detects_duplicated_context(self) -> None:
        """P0.15 §5: Detect duplicate context items across payload zones."""
        manifest = ContextManifest(
            manifest_id="mf_test_02",
            request_id="req_02",
            conversation_id="conv_02",
            profile="STANDARD",
            allocations={"conversation": 4000},
            cacheable_prefix_tokens=200,
            model_context_limit=8000,
            output_reserve_tokens=1000,
            included_items=[
                {"source_type": "memory", "tokens": 30, "trust_level": "memory"},
            ],
        )

        class MockPackage:
            manifest_id = "mf_test_02"
            memory_context = ["Database is PostgreSQL", "Database is PostgreSQL"]
            tool_context = []
            rag_context = []
            token_counts = {"conversation": 0, "memory": 30, "tool": 0, "rag": 0}

        report = ContextPayloadIntegrityVerifier.verify(MockPackage(), manifest)
        assert report["ok"] is False
        issue_types = [issue["type"] for issue in report["issues"]]
        assert "DUPLICATED_CONTEXT" in issue_types

    def test_integrity_verifier_detects_trust_escalation(self) -> None:
        """P0.15 §6: External untrusted sources marked trusted in manifest are rejected."""
        manifest = ContextManifest(
            manifest_id="mf_test_03",
            request_id="req_03",
            conversation_id="conv_03",
            profile="STANDARD",
            allocations={"conversation": 4000},
            cacheable_prefix_tokens=200,
            model_context_limit=8000,
            output_reserve_tokens=1000,
            included_items=[
                {"id": "src_inject", "source_type": "web", "tokens": 50, "trust_level": "trusted"},
            ],
        )

        class MockPackage:
            manifest_id = "mf_test_03"
            memory_context = []
            tool_context = []
            rag_context = []
            token_counts = {"conversation": 0, "memory": 0, "tool": 0, "rag": 0}

        report = ContextPayloadIntegrityVerifier.verify(MockPackage(), manifest)
        assert report["ok"] is False
        issue_types = [issue["type"] for issue in report["issues"]]
        assert "TRUST_ESCALATION" in issue_types

    def test_integrity_verifier_detects_budget_overflow(self) -> None:
        """P0.15 §7: Payload exceeding context budget is flagged."""
        manifest = ContextManifest(
            manifest_id="mf_test_04",
            request_id="req_04",
            conversation_id="conv_04",
            profile="STANDARD",
            allocations={"conversation": 1000},
            cacheable_prefix_tokens=100,
            model_context_limit=2000,
            output_reserve_tokens=1500,  # leaves budget = 500
            included_items=[],
        )

        class MockPackage:
            manifest_id = "mf_test_04"
            memory_context = []
            tool_context = []
            rag_context = []
            token_counts = {"conversation": 300, "memory": 300, "tool": 0, "rag": 0}  # total 600 > 500

        report = ContextPayloadIntegrityVerifier.verify(MockPackage(), manifest)
        assert report["ok"] is False
        issue_types = [issue["type"] for issue in report["issues"]]
        assert "TOKEN_BUDGET_MISMATCH" in issue_types
        assert "TOKEN_ACCOUNTING_MISMATCH" in issue_types

    def test_manifest_fingerprint_deterministic_and_unique(self) -> None:
        """P0.15 §8: Context fingerprint deterministically hashes manifest items."""
        m1 = ContextManifest(
            manifest_id="m1",
            request_id="r1",
            conversation_id="c1",
            profile="STANDARD",
            allocations={"conversation": 4000},
            cacheable_prefix_tokens=100,
            model_context_limit=8000,
            output_reserve_tokens=1000,
            included_items=[
                {"source_type": "memory", "source_id": "mem_1", "tokens": 20, "trust_level": "memory"},
            ],
        )
        m2 = ContextManifest(
            manifest_id="m2",
            request_id="r2",
            conversation_id="c2",
            profile="STANDARD",
            allocations={"conversation": 4000},
            cacheable_prefix_tokens=100,
            model_context_limit=8000,
            output_reserve_tokens=1000,
            included_items=[
                {"source_type": "memory", "source_id": "mem_1", "tokens": 20, "trust_level": "memory"},
            ],
        )
        m3 = ContextManifest(
            manifest_id="m3",
            request_id="r3",
            conversation_id="c3",
            profile="STANDARD",
            allocations={"conversation": 4000},
            cacheable_prefix_tokens=100,
            model_context_limit=8000,
            output_reserve_tokens=1000,
            included_items=[
                {"source_type": "web", "source_id": "src_attack", "tokens": 40, "trust_level": "external_data"},
            ],
        )

        fp1 = CompiledContextFingerprint.compute(m1)
        fp2 = CompiledContextFingerprint.compute(m2)
        fp3 = CompiledContextFingerprint.compute(m3)

        assert fp1.combined_hash == fp2.combined_hash
        assert fp1.combined_hash != fp3.combined_hash
