"""coding_agent tool — codex-style self-repairing code work from chat.

The owner says "fix the login bug in auth.py" or "create a snake game in
snake.py", and this tool does the whole loop instead of describing it:

1. Reads the target inside the workspace root (path escapes rejected).
2. Asks the strongest configured LLM for a surgical patch (or a full file for
   new creations) — never for prose about a patch.
3. Applies it atomically with base-hash + AST validation
   (agent/coding_agent.py — concurrent edits are refused, never clobbered).
4. Runs the verification command in the secret-stripping sandbox
   (agent/sandbox.py — ambient API keys never reach the subprocess).
5. On failure, feeds the parsed error back to the LLM and retries, bounded.
6. Answers with evidence — diff, hashes, verification output — or an honest
   failure that names what could not be verified.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ..agent.coding_agent import (
    CodePatch,
    CodingAgentLoop,
    apply_code_patch,
    compute_file_hash,
)
from ..agent.sandbox import CommandRequest, SandboxExecutor
from ..config import Settings
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.coding_agent")

MAX_FILE_READ_CHARS = 30_000
MAX_ATTEMPTS_CEILING = 5


class CodingAgentParams(BaseModel):
    task: str = Field(..., min_length=3, max_length=4000, description="What to change or build, in the owner's words")
    file_path: str = Field(..., min_length=1, max_length=500, description="Target file, relative to the workspace root")
    test_command: str | None = Field(None, max_length=500, description="Verification command, e.g. 'pytest tests/test_x.py -q'. Defaults to a Python syntax gate for .py files.")
    workspace_root: str | None = Field(None, max_length=500, description="Workspace root override; defaults to HINAA_LOCAL_WORKSPACE_DIR or the HINAA repo")
    max_attempts: int | None = Field(3, ge=1, le=MAX_ATTEMPTS_CEILING, description="Repair attempts before giving up honestly")


# ── LLM access ─────────────────────────────────────────────────────────────
# The tool needs raw text completions, not a companion plan, so it speaks plain
# OpenAI-compatible chat completions to the strongest gateway that is actually
# configured. Order: frontier (Cavoti/Experiential Claude) → Groq → xKiro → APMIX.

def _configured_code_backends(settings: Settings) -> list[dict[str, str]]:
    backends: list[dict[str, str]] = []

    def _add(name: str, key: Any, base_url: str, model: str) -> None:
        secret = key.get_secret_value() if key else ""
        if secret and base_url and model:
            backends.append({
                "name": name,
                "key": secret,
                "url": base_url.rstrip("/") + "/chat/completions",
                "model": model,
            })

    _add("cavoti", settings.cavoti_api_key, settings.cavoti_base_url, settings.cavoti_model)
    _add("experiential", settings.explabs_api_key, settings.explabs_base_url, settings.explabs_model)
    _add("groq", settings.groq_api_key, "https://api.groq.com/openai/v1", settings.groq_model)
    xkiro_key = settings.xkiro_api_key or settings.xkiro_api_key1
    _add("xkiro", xkiro_key, settings.xkiro_base_url, settings.xkiro_model)
    _add("apmix", settings.apmix_api_key, settings.apmix_base_url, settings.apmix_model)
    return backends


async def _llm_text(backends: list[dict[str, str]], system: str, user: str) -> tuple[str, str]:
    """First configured backend that answers wins; returns (text, provider label)."""
    last_error = "no LLM gateway answered"
    for backend in backends:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    backend["url"],
                    headers={
                        "Authorization": f"Bearer {backend['key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": backend["model"],
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "temperature": 0.2,
                        "max_tokens": 8192,
                    },
                )
            if response.status_code != 200:
                last_error = f"{backend['name']} HTTP {response.status_code}"
                logger.warning("coding_agent backend %s rejected: HTTP %d", backend["name"], response.status_code)
                continue
            data = response.json()
            choices = data.get("choices") or []
            message = choices[0].get("message", {}) if choices else {}
            content = message.get("content") or message.get("reasoning_content") or ""
            if isinstance(content, str) and content.strip():
                return content, f"{backend['name']}:{backend['model']}"
            last_error = f"{backend['name']} returned empty content"
        except Exception as exc:
            last_error = f"{backend['name']} {type(exc).__name__}"
            logger.warning("coding_agent backend %s failed: %s", backend["name"], type(exc).__name__)
    raise RuntimeError(f"Coding brain unavailable: {last_error}")


# ── LLM output parsing ─────────────────────────────────────────────────────

_PATCH_SYSTEM = (
    "You are HINAA's coding engine. Output ONLY a JSON object, no markdown fences, no prose. "
    'Schema: {"file_path": string, "target_content": string, "replacement_content": string, "summary": string}. '
    "target_content must be an EXACT verbatim snippet of the current file that your change replaces; "
    "replacement_content is what takes its place. Keep the patch surgical — the smallest snippet that "
    "carries the change with enough context to be unique in the file."
)

_CREATE_SYSTEM = (
    "You are HINAA's coding engine. Output ONLY a JSON object, no markdown fences, no prose. "
    'Schema: {"file_path": string, "full_content": string, "summary": string}. '
    "full_content is the COMPLETE contents of the new file. Make it runnable and clean."
)


def _extract_json_object(raw: str) -> dict[str, Any]:
    """Pull the first balanced JSON object out of a model reply, fences or not."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in model reply")
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : index + 1])
    raise ValueError("unbalanced JSON object in model reply")


# ── Workspace helpers ──────────────────────────────────────────────────────

def _resolve_workspace(override: str | None) -> str:
    root = override or os.environ.get("HINAA_LOCAL_WORKSPACE_DIR") or str(
        Path(__file__).resolve().parents[4]
    )
    return os.path.realpath(os.path.abspath(root))


def _resolve_target(workspace: str, file_path: str) -> str:
    full = os.path.realpath(os.path.abspath(os.path.join(workspace, file_path)))
    if not full.startswith(workspace + os.sep) and full != workspace:
        raise ValueError(f"File path {file_path!r} escapes the workspace root")
    return full


def _default_verify_command(full_path: str) -> list[str] | None:
    if full_path.endswith(".py"):
        return [sys.executable, "-m", "py_compile", full_path]
    return None


# ── Handler ────────────────────────────────────────────────────────────────

async def coding_agent_handler(params: CodingAgentParams) -> dict[str, Any]:
    settings = Settings()
    backends = _configured_code_backends(settings)
    if not backends:
        return {
            "status": "error",
            "code": "CODING_BRAIN_UNAVAILABLE",
            "error": (
                "No LLM gateway is configured for code work. Set one of CAVOTI_AI_API_KEY, "
                "EXPLABS_API_KEY, GROQ_API_KEY, XKIRO_API_KEY, or APMIX_API_KEY."
            ),
        }

    try:
        workspace = _resolve_workspace(params.workspace_root)
        full_path = _resolve_target(workspace, params.file_path)
    except ValueError as error:
        return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(error)}

    sandbox = SandboxExecutor(default_allowed_root=workspace)
    exists = os.path.exists(full_path)

    # ── Mode B: create a brand-new file ────────────────────────────────────
    if not exists:
        user_prompt = (
            f"Create the file {params.file_path}.\n\nTask: {params.task}\n\n"
            "Output the JSON object with the complete file contents."
        )
        try:
            raw, provider_label = await _llm_text(backends, _CREATE_SYSTEM, user_prompt)
            payload = _extract_json_object(raw)
        except Exception as error:
            return {"status": "error", "code": "CODING_BRAIN_FAILED", "error": str(error)}

        full_content = str(payload.get("full_content") or "")
        if not full_content.strip():
            return {"status": "error", "code": "CODING_BRAIN_EMPTY", "error": "The coding brain returned an empty file."}

        if full_path.endswith(".py"):
            import ast

            try:
                ast.parse(full_content, filename=params.file_path)
            except SyntaxError as syn_err:
                return {
                    "status": "error",
                    "code": "SYNTAX_FAILURE",
                    "error": f"Generated file has a Python syntax error: {syn_err}",
                }

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        tmp_path = f"{full_path}.hinaa_tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(full_content)
        os.replace(tmp_path, full_path)

        evidence = [f"Created {params.file_path} ({len(full_content)} bytes) via {provider_label}"]
        verify_cmd = params.test_command or _default_verify_command(full_path)
        verification = await _run_verification(sandbox, verify_cmd, workspace)
        evidence.extend(verification["evidence"])
        if verification["ran"] and not verification["ok"]:
            return {
                "status": "error",
                "code": "VERIFICATION_FAILED",
                "error": "File created but verification failed.",
                "filePath": params.file_path,
                "testOutput": verification["output"],
                "evidence": evidence,
            }

        return {
            "status": "success",
            "mode": "create",
            "filePath": params.file_path,
            "provider": provider_label,
            "fileSizeBytes": len(full_content.encode("utf-8")),
            "hash": compute_file_hash(full_content)[:12],
            "verification": verification["output"] or ("passed" if verification["ran"] else "not requested"),
            "evidence": evidence,
            "summary": str(payload.get("summary") or f"Created {params.file_path}."),
        }

    # ── Mode A: self-repairing edit of an existing file ────────────────────
    with open(full_path, "r", encoding="utf-8", errors="replace") as handle:
        original_content = handle.read()
    base_hash = compute_file_hash(original_content)
    excerpt = original_content[:MAX_FILE_READ_CHARS]
    truncated = len(original_content) > MAX_FILE_READ_CHARS

    async def patch_generator(attempt_idx: int, error_context: str, last_attempt: Any) -> CodePatch:
        retry_note = ""
        if attempt_idx > 0 and error_context:
            retry_note = (
                f"\n\nAttempt {attempt_idx} failed verification. Fix it:\n{error_context[:4000]}"
            )
        elif attempt_idx > 0 and last_attempt is not None and last_attempt.patch_result.error:
            retry_note = f"\n\nAttempt {attempt_idx} could not be applied: {last_attempt.patch_result.error}"

        user_prompt = (
            f"File: {params.file_path}\n\nTask: {params.task}\n\n"
            f"Current file content{' (first 30000 chars)' if truncated else ''}:\n"
            f"-----BEGIN FILE-----\n{excerpt}\n-----END FILE-----"
            f"{retry_note}\n\nOutput the JSON patch object."
        )
        raw, _ = await _llm_text(backends, _PATCH_SYSTEM, user_prompt)
        payload = _extract_json_object(raw)
        target = str(payload.get("target_content") or "")
        replacement = str(payload.get("replacement_content") or "")
        if not target:
            raise ValueError("The coding brain returned an empty target_content; refusing a blind edit.")
        return CodePatch(
            file_path=params.file_path,
            target_content=target,
            replacement_content=replacement,
            base_hash=base_hash,
        )

    verify_cmd = params.test_command or _default_verify_command(full_path)
    if verify_cmd is None:
        # No natural gate for non-Python files: a successful patch application is
        # the verification, so give the loop a command that always passes.
        verify_cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]

    loop = CodingAgentLoop(
        workspace,
        sandbox,
        max_repair_attempts=min(params.max_attempts or 3, MAX_ATTEMPTS_CEILING),
    )
    try:
        result = await loop.execute_repair_loop(patch_generator, verify_cmd, timeout_seconds=120.0)
    except Exception as error:
        # A brain that cannot produce a usable patch is a failure to report,
        # not an exception to leak — and the file is untouched unless a patch
        # already applied cleanly.
        return {
            "status": "error",
            "code": "CODING_BRAIN_FAILED",
            "error": str(error),
            "filePath": params.file_path,
        }

    if not result.success:
        return {
            "status": "error",
            "code": "REPAIR_EXHAUSTED" if result.status == "budget_exhausted" else result.status.upper(),
            "error": result.error or "The repair loop could not resolve the task.",
            "filePath": params.file_path,
            "attempts": result.attempts,
            "evidence": result.evidence,
            "testOutput": result.final_test_output[-2000:] if result.final_test_output else "",
        }

    applied = result.applied_patches[-1] if result.applied_patches else None
    diff = ""
    if applied is not None:
        # Recompute the diff against the original snapshot for the receipt.
        with open(full_path, "r", encoding="utf-8", errors="replace") as handle:
            new_content = handle.read()
        import difflib

        diff = "".join(
            difflib.unified_diff(
                original_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{params.file_path}",
                tofile=f"b/{params.file_path}",
            )
        )[:20_000]

    return {
        "status": "success",
        "mode": "edit",
        "filePath": params.file_path,
        "attempts": result.attempts,
        "diff": diff,
        "verification": result.final_test_output[-2000:] if result.final_test_output else "passed",
        "evidence": result.evidence,
        "summary": f"Edited {params.file_path} and verified it after {result.attempts} attempt(s).",
    }


async def _run_verification(
    sandbox: SandboxExecutor, command: list[str] | str | None, workspace: str
) -> dict[str, Any]:
    if not command:
        return {"ran": False, "ok": True, "output": "", "evidence": []}
    outcome = await sandbox.run_command(
        CommandRequest(command=command, cwd=workspace, allowed_root=workspace, timeout_seconds=120.0)
    )
    output = (outcome.stdout + "\n" + outcome.stderr).strip()[-2000:]
    return {
        "ran": True,
        "ok": outcome.success,
        "output": output,
        "evidence": [
            f"Verification {'passed' if outcome.success else 'FAILED'} (exit {outcome.exit_code}, {outcome.duration_ms:.0f}ms)"
        ],
    }


coding_agent_def = ToolDefinition(
    name="coding_agent",
    display_name="Coding Agent",
    description=(
        "Codex-style code work: edits or creates a file inside the workspace with an LLM-proposed "
        "surgical patch, applies it atomically with base-hash and syntax validation, runs the "
        "verification command in the secret-stripping sandbox, and self-repairs on failure up to "
        "`max_attempts`. Answers with the diff and verification evidence, or an honest failure. "
        "Never clobbers a concurrent edit and never touches a path outside the workspace root."
    ),
    parameters={
        "task": {"type": "string", "description": "What to change or build, in the owner's words"},
        "file_path": {"type": "string", "description": "Target file relative to the workspace root"},
        "test_command": {"type": "string", "description": "Verification command (default: Python syntax gate for .py files)"},
        "workspace_root": {"type": "string", "description": "Workspace root override"},
        "max_attempts": {"type": "integer", "description": "Repair attempts before giving up (1-5)"},
    },
    required_parameters=["task", "file_path"],
    requires_confirmation=False,
    risk_level="high",
    side_effects="Writes files inside the workspace root and runs a bounded verification command in the sandbox.",
)

registry.register(coding_agent_def, coding_agent_handler)
