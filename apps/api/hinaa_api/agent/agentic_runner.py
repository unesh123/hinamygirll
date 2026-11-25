"""Bounded Server-Side Multi-Step Agentic Loop (`think -> tool -> observe -> adapt -> verify`).

Bridges HINAA's LLM providers with workspace coding tools, local studio MP4
renderers, and approval-gated external connectors inside strict server-side
security, budget, redaction, and cancellation boundaries.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, get_type_hints

from pydantic import BaseModel, Field

from ..config import Settings, get_settings
from ..errors import safe_error_text
from ..tools.policy import (
    IRREVERSIBLE_EXTERNAL_TOOLS,
    LOCAL_EFFECT_TOOLS,
    local_effects_permitted,
)
from ..tools.registry import RiskTier, ToolDefinition, registry
from .runtime import _sanitize_value

logger = logging.getLogger("hinaa.agent.agentic_runner")

StepCallback = Callable[[str, dict[str, Any]], Awaitable[None]]
PlannerCallback = Callable[[list[dict[str, Any]], int], Awaitable[str | dict[str, Any]]]

DEFAULT_AGENTIC_TOOLS: frozenset[str] = frozenset({
    "workspace_list_dir",
    "workspace_read_file",
    "workspace_write_file",
    "workspace_edit_file",
    "workspace_glob",
    "workspace_grep",
    "workspace_run_command",
    "render_code_animation",
    "create_lyric_video",
    "create_motion_video",
    "video_create",
    "mlai_list_routines",
    "mlai_run_routine",
})


class AgenticStepRecord(BaseModel):
    step: int
    action: str
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: str = "completed"
    duration_ms: float = 0.0
    observation: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    rationale: str = ""


class PendingApprovalRecord(BaseModel):
    approval_id: str
    tool: str
    scope: str
    arguments_hash: str
    arguments_preview: dict[str, Any] = Field(default_factory=dict)
    reason: str
    rollback_hint: str


class AgenticRunResult(BaseModel):
    run_id: str
    status: str  # completed | awaiting_approval | cancelled | blocked | budget_exhausted | failed
    summary: str
    steps_executed: int = 0
    steps: list[AgenticStepRecord] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)
    pending_approval: PendingApprovalRecord | None = None
    elapsed_ms: float = 0.0
    blocker: str | None = None


def _hash_args(tool_name: str, args: dict[str, Any]) -> str:
    canonical = json.dumps({"tool": tool_name, "args": args}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


_XML_TOOL_RE = re.compile(
    r"<tool\s+([^>]+)>([\s\S]*?)</tool>",
    re.IGNORECASE,
)
_XML_ATTR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')


def _extract_decision_json(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    txt = str(raw or "").strip()
    if not txt:
        return {"action": "final", "summary": ""}

    # 1. Support raw XML-wrapped tool blocks so multi-line HTML/code never fails JSON string escaping
    xml_m = _XML_TOOL_RE.search(txt)
    if xml_m:
        attr_str, body = xml_m.group(1), xml_m.group(2)
        attrs = {k: (v1 if v1 else v2) for k, v1, v2 in _XML_ATTR_RE.findall(attr_str)}
        tname = attrs.pop("name", "").strip()
        if tname:
            if tname in ("workspace_write_file", "workspace_write") and "path" in attrs and "file_path" not in attrs:
                attrs["file_path"] = attrs.pop("path")
            if tname == "workspace_write_file" and body.strip():
                attrs["content"] = body.lstrip("\r\n")
            elif tname == "render_code_animation" and body.strip() and "html_code" not in attrs and "html_path" not in attrs:
                attrs["html_code"] = body.strip()
            for bool_k in ("overwrite", "preview", "normalize_audio"):
                if bool_k in attrs and isinstance(attrs[bool_k], str):
                    attrs[bool_k] = attrs[bool_k].strip().lower() in ("true", "1", "yes")
            for num_k in ("duration_seconds",):
                if num_k in attrs and isinstance(attrs[num_k], str):
                    try:
                        attrs[num_k] = float(attrs[num_k])
                    except ValueError:
                        pass
            for int_k in ("fps", "width", "height"):
                if int_k in attrs and isinstance(attrs[int_k], str):
                    try:
                        attrs[int_k] = int(attrs[int_k])
                    except ValueError:
                        pass
            return {"action": "call_tool", "tool": tname, "arguments": attrs, "rationale": "XML tool invocation"}

    # Strip markdown JSON fences if present
    if txt.startswith("```"):
        lines = txt.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        txt = "\n".join(lines).strip()

    for candidate in (txt, txt[txt.find("{") : txt.rfind("}") + 1] if "{" in txt and "}" in txt else ""):
        if not candidate:
            continue
        for strict_flag in (True, False):
            try:
                parsed = json.loads(candidate, strict=strict_flag)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

    # Recover cleanly instead of outputting truncated JSON to the user as "final"
    if re.search(r'(?i)(?:"action"\s*:\s*"call_tool"|^\s*\{.*"tool"\s*:|<\s*tool\b)', txt):
        return {
            "action": "_parse_error",
            "error": (
                "Your previous tool call was truncated or invalid JSON/XML. Retry cleanly: "
                "for large HTML/code files use `<tool name=\"workspace_write_file\" path=\"...\">...content...</tool>` "
                "keeping HTML concise (<180 lines), OR send valid compact JSON."
            ),
        }
    return {"action": "final", "summary": txt}


@dataclass
class AgenticLoopRunner:
    """Executes bounded multi-step tool loops with server-side policy gates."""

    max_steps: int = 8
    wall_clock_seconds: float = 210.0
    max_consecutive_failures: int = 2
    per_tool_timeout_seconds: float = 120.0
    workspace_root: str | None = None
    settings: Settings | None = None
    host_header: str | None = "127.0.0.1:8000"
    auto_approve_workspace_edits: bool = True

    def _is_tool_permitted(
        self,
        tdef: ToolDefinition,
        args: dict[str, Any],
        allowed_tools: set[str],
        approved_hashes: set[str],
    ) -> tuple[bool, PendingApprovalRecord | None, str | None]:
        name = tdef.name
        if name not in allowed_tools:
            return False, None, f"Tool '{name}' is outside the allowed scope for this run."

        cfg = self.settings or get_settings()
        if name in LOCAL_EFFECT_TOOLS and not local_effects_permitted(cfg, self.host_header):
            return False, None, f"Tool '{name}' requires local workstation host access."

        # Reversible edits and allowlisted read/test verification commands scoped
        # to a bounded workspace_root do not block autonomous coding loops.
        # Arbitrary shell commands and external connectors still require user approval.
        scoped_edit = bool(
            self.workspace_root
            and self.auto_approve_workspace_edits
            and name in ("workspace_edit_file", "workspace_write_file")
        )
        scoped_verify_cmd = False
        if (
            name == "workspace_run_command"
            and self.workspace_root
            and self.auto_approve_workspace_edits
        ):
            from ..tools.workspace_coding_tools import is_safe_verify_command

            scoped_verify_cmd = is_safe_verify_command(
                str(args.get("command") or ""),
                args.get("args") if isinstance(args.get("args"), list) else None,
            )

        args_hash = _hash_args(name, args)
        needs_approval = bool(
            (tdef.requires_confirmation and not scoped_edit and not scoped_verify_cmd)
            or tdef.risk_tier >= RiskTier.TIER_4_DESTRUCTIVE
            or name in IRREVERSIBLE_EXTERNAL_TOOLS
        )
        if needs_approval and args_hash not in approved_hashes:
            pending = PendingApprovalRecord(
                approval_id=f"appr-{uuid.uuid4().hex[:10]}",
                tool=name,
                scope=str(args.get("file_path") or args.get("routine_id") or args.get("workspace_root") or "workspace"),
                arguments_hash=args_hash,
                arguments_preview=_sanitize_value(args),
                reason=f"Tool '{name}' (tier {tdef.risk_tier}) requires explicit user confirmation.",
                rollback_hint="Cancel or reject before execution; no external state has been modified yet.",
            )
            return False, pending, pending.reason

        return True, None, None

    async def _invoke_tool(self, tdef: ToolDefinition, raw_args: dict[str, Any]) -> dict[str, Any]:
        handler = registry.get_handler(tdef.name)
        if handler is None:
            return {"status": "error", "code": "TOOL_NO_HANDLER", "error": f"No handler registered for {tdef.name}"}

        args = dict(raw_args or {})
        if self.workspace_root and (tdef.name.startswith("workspace_") or tdef.name == "render_code_animation") and not args.get("workspace_root"):
            args["workspace_root"] = self.workspace_root

        # Validate against callable's pydantic parameter model when present
        sig = inspect.signature(handler)
        params_list = list(sig.parameters.values())
        call_arg: Any = args
        if params_list:
            try:
                hints = get_type_hints(handler)
            except Exception:
                hints = {}
            ann = hints.get(params_list[0].name, params_list[0].annotation)
            if inspect.isclass(ann) and hasattr(ann, "model_validate"):
                try:
                    call_arg = ann.model_validate(args)
                except Exception as val_err:
                    return {
                        "status": "error",
                        "code": "TOOL_ARGUMENTS_INVALID",
                        "error": safe_error_text(val_err, []),
                    }

        timeout = min(self.per_tool_timeout_seconds, float(getattr(tdef, "timeout_seconds", 120.0) or 120.0))
        if inspect.iscoroutinefunction(handler):
            res = await asyncio.wait_for(handler(call_arg), timeout=timeout)
        else:
            res = await asyncio.wait_for(asyncio.to_thread(handler, call_arg), timeout=timeout)
        return res if isinstance(res, dict) else {"status": "success", "result": res}

    def _collect_artifacts(
        self,
        tool_name: str,
        args: dict[str, Any],
        obs: dict[str, Any],
        artifacts: list[dict[str, Any]],
        files_changed: list[str],
    ) -> None:
        if obs.get("status") != "success":
            return
        if tool_name in ("workspace_edit_file", "workspace_write_file"):
            fp = str(obs.get("filePath") or args.get("file_path") or "")
            if fp and fp not in files_changed:
                files_changed.append(fp)
            artifacts.append({
                "kind": "diff",
                "tool": tool_name,
                "filePath": fp,
                "newHash": obs.get("newHash"),
                "diff": str(obs.get("diff") or "")[:4000],
            })
            if fp.lower().endswith((".html", ".htm", ".svg")) or obs.get("isHtml"):
                html_src = ""
                if isinstance(args.get("content"), str):
                    html_src = str(args["content"])[:45_000]
                elif self.workspace_root and fp:
                    try:
                        from pathlib import Path
                        p = Path(self.workspace_root) / fp
                        if p.is_file():
                            html_src = p.read_text(encoding="utf-8", errors="replace")[:45_000]
                    except Exception:
                        pass
                if html_src.strip():
                    artifacts.append({
                        "kind": "html",
                        "tool": tool_name,
                        "filePath": fp,
                        "language": "svg" if fp.lower().endswith(".svg") else "html",
                        "content": html_src,
                    })
        elif tool_name == "workspace_run_command":
            artifacts.append({
                "kind": "command",
                "tool": tool_name,
                "command": obs.get("command") or args.get("command"),
                "exitCode": obs.get("exitCode"),
                "durationMs": obs.get("durationMs"),
                "stdout": str(obs.get("stdout") or "")[:2000],
                "stderr": str(obs.get("stderr") or "")[:1200],
            })
        elif obs.get("download_url") or obs.get("asset_id"):
            raw_out = obs.get("output")
            out_dict = raw_out if isinstance(raw_out, dict) else {
                k: obs.get(k) for k in ("width", "height", "duration_seconds", "fps") if obs.get(k) is not None
            }
            artifacts.append({
                "kind": "video" if (obs.get("mime_type") == "video/mp4" or "video" in tool_name or "animation" in tool_name) else "file",
                "tool": tool_name,
                "asset_id": obs.get("asset_id"),
                "filename": obs.get("filename"),
                "download_url": obs.get("download_url"),
                "mime_type": obs.get("mime_type") or ("video/mp4" if "video" in tool_name or "animation" in tool_name else "application/octet-stream"),
                "output": out_dict,
            })

    async def run(
        self,
        *,
        goal: str,
        planner: PlannerCallback,
        allowed_tools: set[str] | None = None,
        approved_hashes: set[str] | None = None,
        cancel_event: asyncio.Event | None = None,
        on_event: StepCallback | None = None,
        run_id: str | None = None,
    ) -> AgenticRunResult:
        rid = run_id or f"run-ag-{uuid.uuid4().hex[:8]}"
        t0 = time.perf_counter()
        deadline = t0 + max(5.0, float(self.wall_clock_seconds))
        permitted = set(allowed_tools if allowed_tools is not None else DEFAULT_AGENTIC_TOOLS)
        approved = set(approved_hashes or ())

        steps: list[AgenticStepRecord] = []
        artifacts: list[dict[str, Any]] = []
        files_changed: list[str] = []
        transcript: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": goal,
                "availableTools": sorted(permitted),
            }
        ]
        last_error_sig: str | None = None
        consecutive_same_errors = 0

        async def _emit(evt_type: str, payload: dict[str, Any]) -> None:
            if on_event is not None:
                try:
                    await on_event(evt_type, {"runId": rid, **payload})
                except Exception:
                    logger.debug("Agentic callback %s failed", evt_type, exc_info=True)

        await _emit("agentic.started", {"goal": goal[:300], "maxSteps": self.max_steps})

        for step_num in range(1, self.max_steps + 1):
            if cancel_event is not None and cancel_event.is_set():
                return AgenticRunResult(
                    run_id=rid,
                    status="cancelled",
                    summary="Task cancelled before next step.",
                    steps_executed=len(steps),
                    steps=steps,
                    artifacts=artifacts,
                    files_changed=files_changed,
                    elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
                )
            if time.perf_counter() >= deadline:
                return AgenticRunResult(
                    run_id=rid,
                    status="budget_exhausted",
                    summary="Stopped: wall-clock budget reached.",
                    steps_executed=len(steps),
                    steps=steps,
                    artifacts=artifacts,
                    files_changed=files_changed,
                    elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
                    blocker="WALL_CLOCK_BUDGET_EXHAUSTED",
                )

            await _emit("agent.step.started", {"step": step_num, "maxSteps": self.max_steps})
            try:
                raw_decision = await planner(transcript, step_num)
                decision = _extract_decision_json(raw_decision)
            except Exception as exc:
                err_msg = safe_error_text(exc, [])
                return AgenticRunResult(
                    run_id=rid,
                    status="failed",
                    summary=f"Planner failed at step {step_num}: {err_msg}",
                    steps_executed=len(steps),
                    steps=steps,
                    artifacts=artifacts,
                    files_changed=files_changed,
                    elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
                    blocker=err_msg,
                )

            action = str(decision.get("action") or "").strip().lower()
            if action == "_parse_error":
                err_txt = str(decision.get("error") or "Invalid tool call format.")
                steps.append(AgenticStepRecord(
                    step=step_num, action="format_retry", status="failed", error=err_txt,
                    observation={"status": "error", "code": "TOOL_FORMAT_ERROR", "error": err_txt},
                ))
                transcript.append({"role": "tool_observation", "trusted": False, "result": {"status": "error", "code": "TOOL_FORMAT_ERROR", "error": err_txt}})
                sig = "FORMAT_ERROR"
                consecutive_same_errors = consecutive_same_errors + 1 if sig == last_error_sig else 1
                last_error_sig = sig
                if consecutive_same_errors >= self.max_consecutive_failures:
                    return AgenticRunResult(
                        run_id=rid, status="blocked",
                        summary=f"Blocked after repeated malformed tool responses: {err_txt}",
                        steps_executed=len(steps), steps=steps, artifacts=artifacts,
                        files_changed=files_changed,
                        elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
                        blocker=err_txt,
                    )
                continue

            if action in ("final", "done", "answer") or (not decision.get("tool") and "summary" in decision):
                summary = str(decision.get("summary") or "Completed.")
                await _emit("agentic.completed", {"steps": len(steps), "artifacts": len(artifacts)})
                return AgenticRunResult(
                    run_id=rid,
                    status="completed",
                    summary=summary,
                    steps_executed=len(steps),
                    steps=steps,
                    artifacts=artifacts,
                    files_changed=files_changed,
                    elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
                )

            tool_name = str(decision.get("tool") or "").strip()
            args = decision.get("arguments")
            if not isinstance(args, dict):
                args = {}
            rationale = str(decision.get("rationale") or "")
            tdef = registry.get(tool_name)
            if tdef is None:
                obs = {"status": "error", "code": "UNKNOWN_TOOL", "error": f"Unknown tool '{tool_name}'."}
                steps.append(AgenticStepRecord(
                    step=step_num, action="call_tool", tool=tool_name,
                    arguments=_sanitize_value(args), status="failed",
                    observation=obs, error=obs["error"], rationale=rationale,
                ))
                transcript.append({"role": "tool_observation", "trusted": False, "tool": tool_name, "result": obs})
                sig = f"UNKNOWN:{tool_name}"
                consecutive_same_errors = consecutive_same_errors + 1 if sig == last_error_sig else 1
                last_error_sig = sig
                if consecutive_same_errors >= self.max_consecutive_failures:
                    return AgenticRunResult(
                        run_id=rid, status="blocked",
                        summary=f"Blocked after repeated unknown tool '{tool_name}'.",
                        steps_executed=len(steps), steps=steps, artifacts=artifacts,
                        files_changed=files_changed,
                        elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
                        blocker=obs["error"],
                    )
                continue

            ok, pending, deny_reason = self._is_tool_permitted(tdef, args, permitted, approved)
            if not ok:
                if pending is not None:
                    await _emit("confirmation.required", pending.model_dump())
                    steps.append(AgenticStepRecord(
                        step=step_num, action="approval_gate", tool=tool_name,
                        arguments=pending.arguments_preview, status="awaiting_approval",
                        error=pending.reason, rationale=rationale,
                    ))
                    return AgenticRunResult(
                        run_id=rid,
                        status="awaiting_approval",
                        summary=pending.reason,
                        steps_executed=len(steps),
                        steps=steps,
                        artifacts=artifacts,
                        files_changed=files_changed,
                        pending_approval=pending,
                        elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
                        blocker=pending.reason,
                    )
                obs = {"status": "error", "code": "TOOL_NOT_PERMITTED", "error": deny_reason or "Tool denied by policy."}
                steps.append(AgenticStepRecord(
                    step=step_num, action="call_tool", tool=tool_name,
                    arguments=_sanitize_value(args), status="failed",
                    observation=obs, error=obs["error"], rationale=rationale,
                ))
                transcript.append({"role": "tool_observation", "trusted": False, "tool": tool_name, "result": obs})
                continue

            step_t0 = time.perf_counter()
            await _emit("tool.started", {"step": step_num, "toolName": tool_name, "arguments": _sanitize_value(args)})
            try:
                raw_obs = await self._invoke_tool(tdef, args)
            except Exception as exec_exc:
                err_msg = safe_error_text(exec_exc, [])
                if not err_msg:
                    err_msg = (
                        f"Tool '{tool_name}' timed out or aborted after {int(self.per_tool_timeout_seconds)}s "
                        "(reduce duration_seconds, resolution/fps, or heavy CSS/SVG filters)."
                    )
                raw_obs = {"status": "error", "code": "TOOL_EXEC_FAILED", "error": err_msg}
            step_ms = round((time.perf_counter() - step_t0) * 1000, 2)
            safe_obs = _sanitize_value(raw_obs)

            is_err = safe_obs.get("status") == "error"
            steps.append(AgenticStepRecord(
                step=step_num,
                action="call_tool",
                tool=tool_name,
                arguments=_sanitize_value(args),
                status="failed" if is_err else "completed",
                duration_ms=step_ms,
                observation=safe_obs,
                error=str(safe_obs.get("error")) if is_err else None,
                rationale=rationale,
            ))
            if not is_err:
                self._collect_artifacts(tool_name, args, safe_obs, artifacts, files_changed)
                last_error_sig = None
                consecutive_same_errors = 0
                await _emit("tool.completed", {"step": step_num, "toolName": tool_name, "durationMs": step_ms, "status": "success"})
                if artifacts:
                    await _emit("artifact.ready", {"step": step_num, "artifact": artifacts[-1]})
            else:
                await _emit("tool.failed", {"step": step_num, "toolName": tool_name, "error": safe_obs.get("error")})
                err_sig = f"{tool_name}:{safe_obs.get('code')}:{str(safe_obs.get('error'))[:80]}"
                consecutive_same_errors = consecutive_same_errors + 1 if err_sig == last_error_sig else 1
                last_error_sig = err_sig
                if consecutive_same_errors >= self.max_consecutive_failures:
                    return AgenticRunResult(
                        run_id=rid,
                        status="blocked",
                        summary=f"Stopped after repeated identical failure on {tool_name}: {safe_obs.get('error')}",
                        steps_executed=len(steps),
                        steps=steps,
                        artifacts=artifacts,
                        files_changed=files_changed,
                        elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
                        blocker=str(safe_obs.get("error")),
                    )

            # Treat repository/tool output explicitly as untrusted data for next planner step
            transcript.append({
                "role": "tool_observation",
                "trusted": False,
                "step": step_num,
                "tool": tool_name,
                "observation": safe_obs,
            })

        return AgenticRunResult(
            run_id=rid,
            status="budget_exhausted",
            summary=f"Reached maximum step budget ({self.max_steps} steps).",
            steps_executed=len(steps),
            steps=steps,
            artifacts=artifacts,
            files_changed=files_changed,
            elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
            blocker="MAX_STEPS_REACHED",
        )
