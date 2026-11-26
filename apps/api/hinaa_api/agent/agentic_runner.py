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
from .tool_labels import describe_tool_call

logger = logging.getLogger("hinaa.agent.agentic_runner")

StepCallback = Callable[[str, dict[str, Any]], Awaitable[None]]
PlannerCallback = Callable[[list[dict[str, Any]], int], Awaitable[str | dict[str, Any]]]

DEFAULT_AGENTIC_TOOLS: frozenset[str] = frozenset({
    "workspace_list_dir",
    "workspace_read_file",
    "workspace_move_file",
    "workspace_git_status_diff",
    "workspace_checkpoint",
    "video_inspect_frames",
    "workspace_write_file",
    "workspace_edit_file",
    "workspace_delete_file",
    "workspace_glob",
    "workspace_grep",
    "workspace_run_command",
    "workspace_verify_html",
    "workspace_verify_url",
    "workspace_start_process",
    "workspace_process_logs",
    "workspace_stop_process",
    "workspace_spawn_subagent",
    "web_search",
    "web_extract",
    "web_answer",
    "image_search",
    "image_generate",
    "browser_cloud_agent",
    "render_code_animation",
    "create_lyric_video",
    "create_motion_video",
    "mlai_list_routines",
    "mlai_run_routine",
})


async def _spawn_subagent_stub_handler(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "error",
        "code": "SUBAGENT_REQUIRES_LOOP",
        "error": "workspace_spawn_subagent must run inside AgenticLoopRunner.",
    }


from ..tools.registry import ToolEffect  # noqa: E402

if registry.get("workspace_spawn_subagent") is None:
    registry.register(
        ToolDefinition(
            name="workspace_spawn_subagent",
            display_name="Agent: Spawn Parallel Subagent",
            description="Launch an isolated read-and-verify subagent with its own context window to inspect modules, search code, or verify HTML pages in parallel.",
            parameters={
                "role": {"type": "string", "description": "Short specialist role (e.g. 'Frontend Auditor', 'API Tracer')."},
                "task": {"type": "string", "description": "Clear inspection/audit/verification task and what exact facts to return."},
            },
            required_parameters=["role", "task"],
            is_read_only=True,
            is_concurrency_safe=True,
            requires_confirmation=False,
            risk_tier=RiskTier.TIER_0_READ_ONLY,
            risk_level="low",
            effect=ToolEffect.READ,
            timeout_seconds=90,
        ),
        _spawn_subagent_stub_handler,
    )


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


def _parse_xml_tool_match(attr_str: str, body: str) -> dict[str, Any] | None:
    attrs = {k: (v1 if v1 else v2) for k, v1, v2 in _XML_ATTR_RE.findall(attr_str)}
    tname = attrs.pop("name", "").strip()
    if not tname:
        return None
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
    for int_k in ("fps", "width", "height", "start_line", "end_line", "ready_port", "wait_ms"):
        if int_k in attrs and isinstance(attrs[int_k], str):
            try:
                attrs[int_k] = int(attrs[int_k])
            except ValueError:
                pass
    return {"tool": tname, "arguments": attrs, "rationale": "XML tool invocation"}


def _extract_decision_json(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    txt = str(raw or "").strip()
    if not txt:
        return {"action": "final", "summary": ""}

    # 1. Support one or multiple XML-wrapped tool blocks (enabling parallel batch reads/searches)
    xml_matches = list(_XML_TOOL_RE.finditer(txt))
    if xml_matches:
        parsed_calls = []
        for xm in xml_matches[:6]:
            call = _parse_xml_tool_match(xm.group(1), xm.group(2))
            if call is not None:
                parsed_calls.append(call)
        if len(parsed_calls) == 1:
            return {"action": "call_tool", **parsed_calls[0]}
        if len(parsed_calls) > 1:
            return {
                "action": "call_tools",
                "calls": parsed_calls,
                "rationale": f"Parallel batch ({len(parsed_calls)} tools)",
            }

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


def _extract_vision_bytes(raw_obs: dict[str, Any]) -> tuple[str, bytes] | None:
    p_str = raw_obs.pop("_vision_preview_path", None)
    if not isinstance(p_str, str) or not p_str:
        return None
    from pathlib import Path

    p = Path(p_str)
    try:
        if p.is_file() and p.stat().st_size <= 1_500_000:
            data = p.read_bytes()
            mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            return mime, data
    except Exception:
        pass
    finally:
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass
    return None


@dataclass
class AgenticLoopRunner:
    """Executes bounded multi-step tool loops with server-side policy gates."""

    max_steps: int = 16
    wall_clock_seconds: float = 360.0
    max_consecutive_failures: int = 2
    per_tool_timeout_seconds: float = 120.0
    workspace_root: str | None = None
    settings: Settings | None = None
    host_header: str | None = "127.0.0.1:8000"
    auto_approve_workspace_edits: bool = True
    subagent_depth: int = 0

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

        # Reversible edits and allowlisted read/test/server commands scoped
        # to a bounded workspace_root do not block autonomous coding loops.
        # Arbitrary shell commands and external connectors still require user approval.
        scoped_edit = bool(
            self.workspace_root
            and self.auto_approve_workspace_edits
            and name in (
                "workspace_edit_file",
                "workspace_write_file",
                "workspace_delete_file",
                "workspace_move_file",
                "workspace_checkpoint",
            )
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
        scoped_server_cmd = False
        if (
            name == "workspace_start_process"
            and self.workspace_root
            and self.auto_approve_workspace_edits
        ):
            from ..tools.workspace_coding_tools import is_safe_server_command

            scoped_server_cmd = is_safe_server_command(
                str(args.get("command") or ""),
                args.get("args") if isinstance(args.get("args"), list) else None,
            )

        full_auto = bool(getattr(cfg, "full_autonomy", False) and getattr(cfg, "auto_approve", False))
        auto_web_or_local = full_auto and (
            name in ("web_search", "web_extract", "web_answer", "image_search")
            or (bool(self.workspace_root) and name == "workspace_stop_process")
        )
        args_hash = _hash_args(name, args)
        needs_approval = bool(
            (
                tdef.requires_confirmation
                and not scoped_edit
                and not scoped_verify_cmd
                and not scoped_server_cmd
                and not auto_web_or_local
            )
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
        if (
            self.workspace_root
            and (tdef.name.startswith("workspace_") or tdef.name in ("render_code_animation", "video_inspect_frames"))
            and not args.get("workspace_root")
        ):
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

    def _verify_artifacts_on_disk(self, artifacts: list[dict[str, Any]]) -> None:
        """Annotate workspace file artifacts with real on-disk verification."""
        if not self.workspace_root:
            return
        from pathlib import Path

        root = Path(self.workspace_root).resolve()
        for art in artifacts:
            if not isinstance(art, dict):
                continue
            fp = str(art.get("filePath") or "").strip()
            if not fp or art.get("tool") == "workspace_delete_file":
                continue
            try:
                resolved = (root / fp).resolve()
                inside = resolved.is_relative_to(root)
                art["verifiedOnDisk"] = bool(inside and resolved.is_file())
            except Exception:
                art["verifiedOnDisk"] = False

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
        if tool_name in ("workspace_edit_file", "workspace_write_file", "workspace_delete_file", "workspace_move_file"):
            fp = str(obs.get("destPath") or obs.get("filePath") or args.get("dest_path") or args.get("file_path") or "")
            if fp and fp not in files_changed:
                files_changed.append(fp)
            if tool_name == "workspace_move_file":
                sp = str(obs.get("sourcePath") or args.get("source_path") or "")
                artifacts.append({
                    "kind": "diff",
                    "tool": tool_name,
                    "filePath": fp,
                    "diff": f"Moved {sp} -> {fp}",
                })
                return
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
                    html_src = str(args["content"])[:120_000]
                elif self.workspace_root and fp:
                    try:
                        from pathlib import Path
                        p = Path(self.workspace_root) / fp
                        if p.is_file():
                            html_src = p.read_text(encoding="utf-8", errors="replace")[:120_000]
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
        steer_queue: asyncio.Queue[str] | None = None,
        initial_images: list[tuple[str, bytes]] | None = None,
        steer_images_queue: asyncio.Queue[list[tuple[str, bytes]]] | None = None,
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

        pending_vision_images: list[tuple[str, bytes]] = list(initial_images or [])[:8]
        await _emit("agentic.started", {"goal": goal[:300], "maxSteps": self.max_steps})

        async def _call_planner(cur_step: int) -> str | dict[str, Any]:
            if pending_vision_images:
                try:
                    sig_p = inspect.signature(planner)
                    if "images" in sig_p.parameters or any(
                        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig_p.parameters.values()
                    ):
                        return await planner(transcript, cur_step, images=list(pending_vision_images))
                except (ValueError, TypeError):
                    pass
            return await planner(transcript, cur_step)

        async def _run_subagent(args: dict[str, Any]) -> dict[str, Any]:
            if self.subagent_depth >= 1:
                return {"status": "error", "code": "SUBAGENT_DEPTH_EXCEEDED", "error": "Nested subagents beyond depth 1 are disallowed."}
            role = str(args.get("role") or "Specialist Researcher")[:80]
            task = str(args.get("task") or "").strip()
            if not task:
                return {"status": "error", "code": "INVALID_TASK", "error": "Subagent task must be non-empty."}
            sub_tools = {
                t for t in (
                    "workspace_list_dir",
                    "workspace_glob",
                    "workspace_grep",
                    "workspace_read_file",
                    "workspace_git_status_diff",
                    "video_inspect_frames",
                    "workspace_verify_html",
                    "workspace_verify_url",
                )
                if t in permitted
            }
            sub_runner = AgenticLoopRunner(
                max_steps=6,
                wall_clock_seconds=75.0,
                max_consecutive_failures=2,
                per_tool_timeout_seconds=45.0,
                workspace_root=self.workspace_root,
                settings=self.settings,
                host_header=self.host_header,
                auto_approve_workspace_edits=False,
                subagent_depth=self.subagent_depth + 1,
            )
            sub_res = await sub_runner.run(
                goal=f"[Subagent Role: {role}]\n{task}\nReturn concise verified facts with file paths, line numbers, or URL checks.",
                planner=planner,
                allowed_tools=sub_tools,
                cancel_event=cancel_event,
            )
            return {
                "status": "success" if sub_res.status == "completed" else "error",
                "role": role,
                "subRunId": sub_res.run_id,
                "stepsExecuted": sub_res.steps_executed,
                "summary": sub_res.summary,
            }

        async def _exec_tool_item(tdef: ToolDefinition, args: dict[str, Any]) -> tuple[dict[str, Any], float]:
            step_t0 = time.perf_counter()
            try:
                if tdef.name == "workspace_spawn_subagent":
                    raw_obs = await _run_subagent(args)
                else:
                    raw_obs = await self._invoke_tool(tdef, args)
            except Exception as exec_exc:
                err_msg = safe_error_text(exec_exc, [])
                if not err_msg:
                    err_msg = (
                        f"Tool '{tdef.name}' timed out or aborted after {int(self.per_tool_timeout_seconds)}s "
                        "(reduce duration_seconds, resolution/fps, or heavy CSS/SVG filters)."
                    )
                raw_obs = {"status": "error", "code": "TOOL_EXEC_FAILED", "error": err_msg}
            return raw_obs, round((time.perf_counter() - step_t0) * 1000, 2)

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

            if steer_queue is not None:
                steered_msgs: list[str] = []
                while not steer_queue.empty():
                    try:
                        s_msg = str(steer_queue.get_nowait() or "").strip()
                        if s_msg:
                            steered_msgs.append(s_msg)
                    except asyncio.QueueEmpty:
                        break
                for s_msg in steered_msgs:
                    transcript.append({
                        "role": "user",
                        "content": (
                            "[LIVE USER DIRECTION WHILE BUILDING — incorporate these preferences into your current/next build]: "
                            + s_msg
                        ),
                    })
                    await _emit("agent.steered", {"message": s_msg, "step": step_num})
            if steer_images_queue is not None:
                while not steer_images_queue.empty():
                    try:
                        img_batch = steer_images_queue.get_nowait() or []
                        for mime_t, raw_b in img_batch:
                            if raw_b:
                                pending_vision_images.append((mime_t, raw_b))
                    except asyncio.QueueEmpty:
                        break
                if len(pending_vision_images) > 8:
                    pending_vision_images = pending_vision_images[-8:]

            await _emit("agent.step.started", {"step": step_num, "maxSteps": self.max_steps})
            try:
                raw_decision = await _call_planner(step_num)
                pending_vision_images.clear()
                decision = _extract_decision_json(raw_decision)
            except Exception as exc:
                pending_vision_images.clear()
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
            raw_thought = str(
                decision.get("thought")
                or decision.get("reasoning")
                or (
                    decision.get("rationale")
                    if decision.get("rationale") not in (None, "", "XML tool invocation")
                    else ""
                )
            ).strip()
            if raw_thought and action != "_parse_error":
                await _emit("thought.delta", {"step": step_num, "text": raw_thought})
                await _emit("thought.done", {"step": step_num, "summary": raw_thought[:200]})
            if action == "_parse_error":
                err_txt = str(decision.get("error") or "Invalid tool call format.")
                steps.append(AgenticStepRecord(
                    step=step_num, action="format_retry", status="failed", error=err_txt,
                    observation={"status": "error", "code": "TOOL_FORMAT_ERROR", "error": err_txt},
                ))
                err_obs = {"status": "error", "code": "TOOL_FORMAT_ERROR", "error": err_txt}
                transcript.append({
                    "role": "tool_observation",
                    "trusted": False,
                    "observation": err_obs,
                    "result": err_obs,
                })
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

            if action in ("final", "done", "answer") or (
                not decision.get("tool") and not decision.get("calls") and "summary" in decision
            ):
                summary = str(decision.get("summary") or "Completed.").strip()
                looks_like_planning_or_truncated_code = (
                    len(steps) == 0
                    and any(
                        t in permitted
                        for t in ("render_code_animation", "workspace_write_file", "workspace_edit_file", "workspace_read_file", "workspace_run_command")
                    )
                    and (
                        not summary
                        or summary.count("```") % 2 == 1
                        or re.match(
                            r"(?i)^\s*(?:the\s+user\s+wants|let\s+me\s+(?:first|check|plan|write|build|create)|let'?s\s+(?:first|check|plan|write|build|create)|i\s+(?:will|need\s+to|should)\s+(?:first|write|create|check|render)|reasoning\s+ran\s+out)",
                            summary,
                        )
                        or ("<script>" in summary and "window.setAnimationTime" in summary)
                        or "```html" in summary.lower()
                        or "```javascript" in summary.lower()
                    )
                )
                if looks_like_planning_or_truncated_code and step_num < self.max_steps:
                    err_txt = (
                        "Do not answer with planning prose or unexecuted HTML/JS snippets at step 1. "
                        "Call the real tool immediately (e.g. render_code_animation or workspace_write_file / workspace_read_file)."
                    )
                    retry_obs = {"status": "error", "code": "TOOL_REQUIRED", "error": err_txt}
                    steps.append(AgenticStepRecord(
                        step=step_num, action="format_retry", status="failed", error=err_txt, observation=retry_obs,
                    ))
                    transcript.append({"role": "tool_observation", "trusted": False, "observation": retry_obs, "result": retry_obs})
                    continue
                self._verify_artifacts_on_disk(artifacts)
                await _emit("agentic.completed", {"steps": len(steps), "artifacts": len(artifacts)})
                return AgenticRunResult(
                    run_id=rid,
                    status="completed",
                    summary=summary or "Completed.",
                    steps_executed=len(steps),
                    steps=steps,
                    artifacts=artifacts,
                    files_changed=files_changed,
                    elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
                )

            if action == "call_tools" and isinstance(decision.get("calls"), list):
                raw_calls = [c for c in decision["calls"][:6] if isinstance(c, dict)]
            else:
                raw_calls = [{
                    "tool": decision.get("tool"),
                    "arguments": decision.get("arguments"),
                    "rationale": decision.get("rationale"),
                }]

            validated_calls: list[tuple[str, dict[str, Any], str, ToolDefinition]] = []
            for call_item in raw_calls:
                tool_name = str(call_item.get("tool") or "").strip()
                args = call_item.get("arguments")
                if not isinstance(args, dict):
                    args = {}
                rationale = str(call_item.get("rationale") or decision.get("rationale") or "")
                tdef = registry.get(tool_name)
                if tdef is None:
                    obs = {"status": "error", "code": "UNKNOWN_TOOL", "error": f"Unknown tool '{tool_name}'."}
                    steps.append(AgenticStepRecord(
                        step=step_num, action="call_tool", tool=tool_name,
                        arguments=_sanitize_value(args), status="failed",
                        observation=obs, error=obs["error"], rationale=rationale,
                    ))
                    transcript.append({
                        "role": "tool_observation",
                        "trusted": False,
                        "step": step_num,
                        "call_id": f"call_{step_num}_err",
                        "tool": tool_name,
                        "arguments": _sanitize_value(args),
                        "observation": obs,
                        "result": obs,
                    })
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
                        meta = describe_tool_call(tool_name, args)
                        await _emit("confirmation.required", {**pending.model_dump(), **meta})
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
                    transcript.append({
                        "role": "tool_observation",
                        "trusted": False,
                        "step": step_num,
                        "call_id": f"call_{step_num}_err",
                        "tool": tool_name,
                        "arguments": _sanitize_value(args),
                        "observation": obs,
                        "result": obs,
                    })
                    continue

                validated_calls.append((tool_name, args, rationale, tdef))

            if not validated_calls:
                continue

            can_parallel = len(validated_calls) > 1 and all(
                td.is_read_only and td.is_concurrency_safe for _, _, _, td in validated_calls
            )
            parallel_group = f"batch-{step_num}" if can_parallel else None

            for tool_name, args, _rat, _tdef in validated_calls:
                meta = describe_tool_call(tool_name, args)
                started_payload: dict[str, Any] = {
                    "step": step_num,
                    "toolName": tool_name,
                    "arguments": _sanitize_value(args),
                    "label": meta["label"],
                    "target": meta["target"],
                    "lane": meta["lane"],
                }
                if parallel_group:
                    started_payload["parallelGroup"] = parallel_group
                await _emit("tool.started", started_payload)
            if can_parallel:
                batch_results = await asyncio.gather(
                    *(_exec_tool_item(td, a) for _, a, _, td in validated_calls)
                )
            else:
                batch_results = []
                for _, a, _, td in validated_calls:
                    batch_results.append(await _exec_tool_item(td, a))

            for idx_c, ((tool_name, args, rationale, _tdef), (raw_obs, step_ms)) in enumerate(zip(validated_calls, batch_results)):
                vis = _extract_vision_bytes(raw_obs) if isinstance(raw_obs, dict) else None
                if vis is not None:
                    pending_vision_images.append(vis)
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
                    meta = describe_tool_call(tool_name, args)
                    await _emit(
                        "tool.completed",
                        {
                            "step": step_num,
                            "toolName": tool_name,
                            "durationMs": step_ms,
                            "status": "success",
                            "label": meta["label"],
                            "target": meta["target"],
                            "lane": meta["lane"],
                        },
                    )
                    if artifacts:
                        await _emit("artifact.ready", {"step": step_num, "artifact": artifacts[-1]})
                else:
                    meta = describe_tool_call(tool_name, args)
                    await _emit(
                        "tool.failed",
                        {
                            "step": step_num,
                            "toolName": tool_name,
                            "error": safe_obs.get("error"),
                            "label": meta["label"],
                            "target": meta["target"],
                            "lane": meta["lane"],
                        },
                    )
                    err_sig = f"{tool_name}:{safe_obs.get('code')}:{str(safe_obs.get('error'))[:80]}"
                    consecutive_same_errors = consecutive_same_errors + 1 if err_sig == last_error_sig else 1
                    last_error_sig = err_sig
                    if consecutive_same_errors >= self.max_consecutive_failures:
                        await _emit("agent.step.completed", {"step": step_num, "maxSteps": self.max_steps})
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
                    "call_id": f"call_{step_num}_{idx_c}",
                    "tool": tool_name,
                    "arguments": _sanitize_value(args),
                    "observation": safe_obs,
                })
            await _emit("agent.step.completed", {"step": step_num, "maxSteps": self.max_steps})

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
