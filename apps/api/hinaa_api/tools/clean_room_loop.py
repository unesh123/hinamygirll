"""clean_room_loop tool — autonomous reverse-engineering, specification, and clean-room rebuild.

Inspired by morluto/rea and the 6-stage Clean-Room loop:
[TARGET / EVIDENCE] -> [ANALYZE] -> [SPEC.md] -> [REBUILD] -> [ORACLE] -> [RETRY / 100% PASS]

1. Analyzes target evidence (decompiled logic, network traces, API payload shapes, or feature behaviors).
2. Generates a formal, unpolluted behavioral specification (SPEC.md) with data contracts and invariants.
3. Synthesizes an independent automated test oracle suite (pytest) covering happy paths and edge cases.
4. Generates a clean-room production implementation satisfying the specification.
5. Executes the oracle in the secret-stripping sandbox.
6. Automatically self-repairs code discrepancies against the oracle until all assertions pass with 0 behavioral diffs.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..agent.coding_agent import (
    CodePatch,
    apply_code_patch,
    compute_file_hash,
)
from ..agent.sandbox import CommandRequest, SandboxExecutor
from ..config import Settings
from .coding_agent_tool import (
    _configured_code_backends,
    _extract_json_object,
    _llm_text,
    _resolve_target,
    _resolve_workspace,
)
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.clean_room_loop")

MAX_ATTEMPTS_CEILING = 5


class CleanRoomRebuildParams(BaseModel):
    task: str = Field(
        ...,
        min_length=3,
        max_length=4000,
        description="High-level description of the feature or capability to clean-room rebuild",
    )
    target_evidence: str = Field(
        ...,
        min_length=5,
        max_length=20000,
        description="Concrete evidence: decompiled routines, API shapes, network traces, or observed behavior",
    )
    destination_file: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Target destination file for the rebuilt implementation, relative to workspace root",
    )
    oracle_test_file: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Path for the generated automated oracle test suite, relative to workspace root",
    )
    spec_file: str | None = Field(
        None,
        max_length=500,
        description="Optional path to write the formal clean-room specification (SPEC.md)",
    )
    test_command: str | None = Field(
        None,
        max_length=500,
        description="Optional custom test command (defaults to 'pytest <oracle_test_file> -q')",
    )
    workspace_root: str | None = Field(
        None,
        max_length=500,
        description="Workspace root override",
    )
    max_attempts: int | None = Field(
        3,
        ge=1,
        le=MAX_ATTEMPTS_CEILING,
        description="Maximum self-repair iterations against the oracle (1-5)",
    )


# ── Prompts ─────────────────────────────────────────────────────────────────

_SPEC_SYSTEM = (
    "You are HINAA's Clean-Room Reverse Engineering Architect. Output ONLY a JSON object, no markdown prose. "
    'Schema: {"spec_markdown": string, "summary": string, "interfaces": list[string], "invariants": list[string]}. '
    "spec_markdown must define the formal functional specification: components, input/output data contracts, "
    "preconditions, postconditions, and error codes without copying proprietary code."
)

_ORACLE_SYSTEM = (
    "You are HINAA's Verification Oracle Engineer. Output ONLY a JSON object, no markdown prose. "
    'Schema: {"file_path": string, "full_content": string, "summary": string}. '
    "full_content is the COMPLETE pytest test suite that rigorously tests the specified interfaces, "
    "boundary values, invariants, and failure modes. Make all tests independent, self-contained, and deterministic."
)

_REBUILD_SYSTEM = (
    "You are HINAA's Clean-Room Code Synthesis Engine. Output ONLY a JSON object, no markdown prose. "
    'Schema: {"file_path": string, "full_content": string, "summary": string}. '
    "full_content is the COMPLETE, runnable clean-room implementation satisfying the specification and oracles. "
    "Write production-grade, typed Python code with comprehensive error handling."
)

_REPAIR_SYSTEM = (
    "You are HINAA's Self-Repairing Code Engine. Output ONLY a JSON object, no markdown prose. "
    'Schema: {"file_path": string, "target_content": string, "replacement_content": string, "summary": string}. '
    "target_content must be an EXACT verbatim snippet of the current implementation that needs fixing; "
    "replacement_content is what takes its place to satisfy the failing oracle test. Keep it surgical."
)


# ── Core Execution Logic ───────────────────────────────────────────────────

async def clean_room_loop_handler(params: CleanRoomRebuildParams) -> dict[str, Any]:
    """Execute the 6-stage clean-room reverse engineering and oracle rebuild loop."""
    settings = Settings()
    backends = _configured_code_backends(settings)
    if not backends:
        return {
            "status": "error",
            "code": "CODING_BRAIN_UNAVAILABLE",
            "error": "No LLM coding gateway configured (Cavoti, Groq, xKiro, APMIX).",
            "evidence": ["Checked configured backends: 0 available"],
        }

    workspace = _resolve_workspace(params.workspace_root)
    try:
        dest_path = Path(_resolve_target(workspace, params.destination_file))
        oracle_path = Path(_resolve_target(workspace, params.oracle_test_file))
        spec_path = Path(_resolve_target(workspace, params.spec_file)) if params.spec_file else None
    except ValueError as exc:
        return {
            "status": "error",
            "code": "WORKSPACE_ESCAPE",
            "error": str(exc),
            "evidence": [f"workspace={workspace}"],
        }

    evidence: list[str] = [
        f"Target feature: {params.task}",
        f"Destination file: {params.destination_file}",
        f"Oracle test file: {params.oracle_test_file}",
    ]

    # Stage 1: Generate Formal Behavioral Specification (SPEC.md)
    spec_user_prompt = (
        f"TASK: {params.task}\n\n"
        f"OBSERVED TARGET EVIDENCE:\n{params.target_evidence}\n\n"
        f"TARGET FILE: {params.destination_file}\n"
        "Synthesize an unpolluted clean-room functional specification with formal contracts and testable invariants."
    )
    raw_spec, spec_backend = await _llm_text(backends, _SPEC_SYSTEM, spec_user_prompt)
    parsed_spec = _extract_json_object(raw_spec)
    spec_md = parsed_spec.get("spec_markdown", f"# Spec for {params.task}\n\n{params.target_evidence}")
    evidence.append(f"Stage 1 [ANALYZE]: Spec generated via {spec_backend} ({len(spec_md)} chars)")

    if spec_path:
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(spec_md, encoding="utf-8")
        evidence.append(f"Written formal specification to {params.spec_file}")

    # Stage 2: Synthesize Automated Test Oracle Suite
    oracle_user_prompt = (
        f"FEATURE SPECIFICATION:\n{spec_md}\n\n"
        f"TARGET MODULE TO TEST: {params.destination_file}\n"
        f"ORACLE FILE PATH: {params.oracle_test_file}\n"
        "Generate a complete, self-contained pytest oracle suite verifying the specification. "
        "Import the implementation module assuming it will be located at the destination path."
    )
    raw_oracle, oracle_backend = await _llm_text(backends, _ORACLE_SYSTEM, oracle_user_prompt)
    parsed_oracle = _extract_json_object(raw_oracle)
    oracle_content = parsed_oracle.get("full_content", "")
    if not oracle_content.strip():
        return {
            "status": "error",
            "code": "ORACLE_SYNTHESIS_FAILED",
            "error": "Model returned empty test oracle content.",
            "evidence": evidence,
        }

    # Validate oracle Python syntax
    try:
        ast.parse(oracle_content, filename=str(oracle_path))
    except SyntaxError as exc:
        return {
            "status": "error",
            "code": "ORACLE_SYNTAX_ERROR",
            "error": f"Generated oracle test has syntax error: {exc}",
            "evidence": evidence,
        }

    oracle_path.parent.mkdir(parents=True, exist_ok=True)
    oracle_path.write_text(oracle_content, encoding="utf-8")
    oracle_hash = compute_file_hash(oracle_content)
    evidence.append(f"Stage 2 [ORACLE]: Synthesized {params.oracle_test_file} (SHA256 {oracle_hash[:12]})")

    # Stage 3: Clean-Room Implementation Rebuild
    rebuild_user_prompt = (
        f"FEATURE SPECIFICATION:\n{spec_md}\n\n"
        f"TEST ORACLES TO SATISFY:\n{oracle_content}\n\n"
        f"DESTINATION PATH: {params.destination_file}\n"
        "Synthesize the complete clean-room implementation satisfying all test cases."
    )
    raw_impl, impl_backend = await _llm_text(backends, _REBUILD_SYSTEM, rebuild_user_prompt)
    parsed_impl = _extract_json_object(raw_impl)
    impl_content = parsed_impl.get("full_content", "")
    if not impl_content.strip():
        return {
            "status": "error",
            "code": "REBUILD_SYNTHESIS_FAILED",
            "error": "Model returned empty implementation content.",
            "evidence": evidence,
        }

    try:
        ast.parse(impl_content, filename=str(dest_path))
    except SyntaxError as exc:
        return {
            "status": "error",
            "code": "REBUILD_SYNTAX_ERROR",
            "error": f"Initial implementation has syntax error: {exc}",
            "evidence": evidence,
        }

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(impl_content, encoding="utf-8")
    impl_hash = compute_file_hash(impl_content)
    evidence.append(f"Stage 3 [REBUILD]: Synthesized {params.destination_file} (SHA256 {impl_hash[:12]})")

    # Stage 4 & 5: Oracle Execution & Self-Repair Loop
    sandbox = SandboxExecutor()
    cmd = params.test_command or f"{sys.executable} -m pytest {oracle_path} -q"
    max_attempts = params.max_attempts or 3
    current_content = impl_content
    attempt = 0
    passed = False
    last_output = ""

    while attempt < max_attempts and not passed:
        attempt += 1
        outcome = await sandbox.run_command(
            CommandRequest(
                command=cmd,
                cwd=workspace,
                allowed_root=workspace,
                timeout_seconds=60.0,
                env_overrides={"PYTHONPATH": str(workspace)},
            )
        )
        last_output = (outcome.stdout + "\n" + outcome.stderr).strip()[-2000:]
        if outcome.success:
            passed = True
            evidence.append(f"Stage 5 [ORACLE PASS]: Verification passed on attempt {attempt}/{max_attempts} (exit 0)")
            break

        evidence.append(f"Attempt {attempt}/{max_attempts}: Oracle failed (exit {outcome.exit_code})")
        if attempt >= max_attempts:
            break

        # Stage 6: Self-Repair
        repair_user_prompt = (
            f"TARGET FILE: {params.destination_file}\n"
            f"CURRENT CODE:\n{current_content}\n\n"
            f"TEST ORACLE:\n{oracle_content}\n\n"
            f"FAILING ORACLE OUTPUT:\n{last_output}\n\n"
            "Propose a surgical patch to fix the failing test."
        )
        try:
            raw_patch, repair_backend = await _llm_text(backends, _REPAIR_SYSTEM, repair_user_prompt)
            parsed_patch = _extract_json_object(raw_patch)
            patch = CodePatch(
                file_path=params.destination_file,
                target_content=parsed_patch.get("target_content", ""),
                replacement_content=parsed_patch.get("replacement_content", ""),
                base_hash=compute_file_hash(current_content),
            )
            patch_result = apply_code_patch(workspace, patch)
            if not patch_result.success:
                evidence.append(f"Repair patch rejected on attempt {attempt}: {patch_result.error}")
                continue
            current_content = dest_path.read_text(encoding="utf-8")
            evidence.append(f"Applied surgical patch via {repair_backend} on attempt {attempt}")
        except Exception as exc:
            evidence.append(f"Self-repair step raised: {exc}")

    return {
        "status": "success" if passed else "incomplete",
        "task": params.task,
        "destination_file": params.destination_file,
        "oracle_test_file": params.oracle_test_file,
        "spec_file": params.spec_file,
        "verified": passed,
        "attempts": attempt,
        "oracle_output": last_output,
        "spec": parsed_spec.get("summary", ""),
        "evidence": evidence,
    }


# ── Tool Registration ───────────────────────────────────────────────────────

clean_room_tool_def = ToolDefinition(
    name="clean_room_loop",
    display_name="Clean-Room Reverse Engineering & Rebuild",
    description=(
        "Autonomous clean-room reverse engineering and rebuild loop (morluto/rea architecture). "
        "Analyzes target evidence, generates a formal behavioral specification (SPEC.md), synthesizes "
        "an independent automated test oracle suite (pytest), generates a clean-room implementation, "
        "and self-repairs in the sandbox until the oracle tests pass with 0 behavioral diffs."
    ),
    parameters={
        "task": {"type": "string", "description": "Description of the feature to reverse-engineer and rebuild"},
        "target_evidence": {"type": "string", "description": "Concrete observed evidence, API traces, or decompiled snippets"},
        "destination_file": {"type": "string", "description": "Target destination file for the clean-room rebuild"},
        "oracle_test_file": {"type": "string", "description": "Path for the generated automated oracle test suite"},
        "spec_file": {"type": "string", "description": "Optional path to save the formal SPEC.md file"},
        "test_command": {"type": "string", "description": "Optional custom verification command"},
        "workspace_root": {"type": "string", "description": "Workspace root override"},
        "max_attempts": {"type": "integer", "description": "Max self-repair attempts (1-5)"},
    },
    required_parameters=["task", "target_evidence", "destination_file", "oracle_test_file"],
    requires_confirmation=False,
    risk_level="high",
)

registry.register(clean_room_tool_def, clean_room_loop_handler)
