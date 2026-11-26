"""HINAA OS — Real LLM-backed agent step for the Loop Engineering Harness.

Replaces the simulated agent step (``await asyncio.sleep(...); return
"Executed repair step."``) with a genuine model call:

1. Resolve the first configured provider from ``hinaa_api.config.Settings``
   (agent-router, claude/anthropic, openai, groq, gemini).
2. Build a goal + failure-evidence prompt and ask the model for a JSON action
   plan: ``{"thought": str, "actions": [{"type": "write_file"|"delete_file"|
   "run_command"|"read_file"|"list_files", ...}]}``.
3. Validate each action against the typed tool registry (pydantic schemas in
   ``loop_tools.py``): read-only tools run auto-approved; side-effecting tools
   require ``confirm: true`` on the action. Execution stays inside the loop
   workspace (no escapes via ``..`` or absolute paths outside it); shell
   commands are opt-in via ``HINAA_LOOP_ALLOW_COMMANDS=1``.
4. Append a JSONL trace line per turn under the loop state dir: prompt size,
   model, latency, token usage, thought, actions and their outcomes.

The hard verification gate in ``loop_engine.LoopEngine`` stays the single
source of truth for success; the agent step only proposes changes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from .loop_engine import EvidenceReceipt, LoopTaskSpec
from .loop_events import EVENT_BUS
from .loop_tools import describe_tools, validate_action

logger = logging.getLogger("hinaa.harness.agent_step")

_SYSTEM_PROMPT = (
    "You are Hina, an autonomous coding agent executing an unattended repair loop. "
    "Each turn you receive the goal, the constraints, and the evidence from the last "
    "failed verification (exit code and output). You must change the workspace so the "
    "verification command passes. Reply with ONLY a JSON object, no markdown fences:\n"
    '{"thought": "<short diagnosis>", "actions": ['
    '{"type": "write_file", "path": "<relative path>", "content": "<full file content>", "confirm": true}, '
    '{"type": "delete_file", "path": "<relative path>", "confirm": true}, '
    '{"type": "run_command", "command": "<shell command>", "confirm": true}, '
    '{"type": "read_file", "path": "<relative path>", "max_bytes": 16000}, '
    '{"type": "list_files", "pattern": "**/*"}, '
    '{"type": "search_files", "query": "<literal text>", "glob": "**/*"}, '
    '{"type": "fetch_url", "url": "https://...", "max_chars": 12000}, '
    '{"type": "browser_check", "url": "http://127.0.0.1:3000", "viewport_width": 1280, "viewport_height": 800}'
    "]}\n"
    "Tools:\n" + describe_tools() + "\n"
    "Rules: inspect first with read_file/list_files/search_files (no confirm needed); every "
    "side-effecting action MUST carry \"confirm\": true or it is refused; paths are "
    "relative to the workspace root and must stay inside it; write the complete final "
    "content of any file you touch; keep actions minimal; never invent a verification "
    "result."
)

_MAX_ACTIONS_PER_TURN = 8
_MAX_FILE_BYTES = 512_000
_COMMAND_TIMEOUT_SECONDS = 60.0
_OBSERVATION_CHARS = 6_000
_TRACE_LINE_KEYS = (
    "ts",
    "task_id",
    "turn",
    "provider",
    "model",
    "latency_ms",
    "prompt_chars",
    "input_tokens",
    "output_tokens",
    "thought",
    "actions",
    "outcomes",
    "status",
    "error",
)


@dataclass
class LoopProvider:
    """A concrete LLM endpoint the loop step can call."""

    name: str
    protocol: str  # "openai" | "anthropic"
    base_url: str
    api_key: str
    model: str


@dataclass
class ActionOutcome:
    action: Dict[str, Any]
    status: str  # "applied" | "blocked" | "error" | "skipped"
    detail: str = ""


@dataclass
class AgentStepResult:
    thought: str
    summary: str
    actions_applied: int
    status: str  # "acted" | "no_actions" | "blocked_no_llm" | "error"
    provider: Optional[str] = None
    model: Optional[str] = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    outcomes: List[ActionOutcome] = field(default_factory=list)
    trace_path: Optional[str] = None
    error: Optional[str] = None

    def as_engine_summary(self) -> str:
        return self.summary


def _secret(value: Any) -> str:
    """Read a pydantic SecretStr or plain str without leaking it."""
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    return getter() if callable(getter) else str(value)


def resolve_loop_provider(settings: Any = None) -> Optional[LoopProvider]:
    """Pick the first configured provider, mirroring the registry fallback chain."""
    if settings is None:
        from ..config import get_settings

        settings = get_settings()

    def configured(key: Any, base_url: Any, model: Any) -> bool:
        return bool(_secret(key).strip() and str(base_url or "").strip() and str(model or "").strip())

    agent_router_key = getattr(settings, "agent_router_api_key", None)
    if agent_router_key is not None and _secret(agent_router_key).strip():
        base_url = getattr(settings, "active_agent_router_base_url", None) or "https://api.agentrouter.dev/v1"
        model = getattr(settings, "active_agent_router_model", None) or "gpt-6-astra"
        if _secret(agent_router_key).strip() and str(base_url).strip():
            return LoopProvider(
                name="agent-router",
                protocol="openai",
                base_url=str(base_url).strip().rstrip("/"),
                api_key=_secret(agent_router_key).strip(),
                model=str(model),
            )

    claude_key = getattr(settings, "claude_api_key", None)
    if claude_key is not None and _secret(claude_key).strip():
        base_url = getattr(settings, "claude_base_url", "https://api.anthropic.com").strip().rstrip("/")
        model = getattr(settings, "active_claude_model", None) or "claude-sonnet-4-5"
        return LoopProvider(
            name="claude",
            protocol="anthropic",
            base_url=base_url,
            api_key=_secret(claude_key).strip(),
            model=str(model),
        )

    openai_key = getattr(settings, "openai_api_key", None)
    if openai_key is not None and _secret(openai_key).strip():
        return LoopProvider(
            name="openai",
            protocol="openai",
            base_url="https://api.openai.com/v1",
            api_key=_secret(openai_key).strip(),
            model=str(getattr(settings, "openai_model", "gpt-5-mini")),
        )

    groq_key = getattr(settings, "groq_api_key", None)
    if groq_key is not None and _secret(groq_key).strip():
        return LoopProvider(
            name="groq",
            protocol="openai",
            base_url="https://api.groq.com/openai/v1",
            api_key=_secret(groq_key).strip(),
            model=str(getattr(settings, "groq_model", "llama-3.1-8b-instant")),
        )

    gemini_key = getattr(settings, "gemini_api_key", None)
    if gemini_key is not None and _secret(gemini_key).strip():
        return LoopProvider(
            name="gemini",
            protocol="openai",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key=_secret(gemini_key).strip(),
            model="gemini-2.5-flash",
        )

    return None


def _confined_path(workspace: Path, raw: str) -> Optional[Path]:
    """Resolve a model-supplied path inside the workspace, or None on escape."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = Path(raw.strip())
    if candidate.is_absolute():
        return None
    resolved = (workspace / candidate).resolve()
    workspace_resolved = workspace.resolve()
    if resolved != workspace_resolved and workspace_resolved not in resolved.parents:
        return None
    return resolved


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Tolerant extraction of the first JSON object in a model reply."""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    decoder = json.JSONDecoder()
    for match in re.finditer(r"[{]", cleaned):
        try:
            value, _ = decoder.raw_decode(cleaned[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


class LLMAgentStep:
    """Calls a real model and applies its guarded file actions in the workspace."""

    def __init__(
        self,
        provider: LoopProvider,
        workspace_dir: Path,
        trace_path: Path,
        *,
        max_output_tokens: int = 8_192,
        timeout_seconds: float = 120.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.provider = provider
        self.workspace = Path(workspace_dir)
        self.trace_path = Path(trace_path)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        self._client = client
        self._owns_client = client is None
        self._observations: List[str] = []

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    # -- model call ---------------------------------------------------------

    def _build_user_prompt(self, spec: LoopTaskSpec, turn: int, last_receipt: Optional[EvidenceReceipt]) -> str:
        parts = [
            f"Goal: {spec.goal_title}",
            f"Turn: {turn}/{spec.max_turns}",
            f"Workspace root: {self.workspace}",
        ]
        if spec.description:
            parts.append(f"Description: {spec.description}")
        if spec.target_files:
            parts.append("Target files: " + ", ".join(spec.target_files))
        if spec.constraints:
            parts.append("Constraints:\n" + "\n".join(f"- {c}" for c in spec.constraints))
        parts.append("Verification command: " + " ".join(spec.verification_command))
        if last_receipt is not None and not last_receipt.passed:
            err = last_receipt.stderr_snippet or last_receipt.stdout_snippet or "Non-zero exit code"
            parts.append(
                f"Last verification FAILED with exit code {last_receipt.exit_code}:\n"
                f"```\n{err[:8000]}\n```"
            )
        elif last_receipt is not None:
            parts.append("Last verification passed on baseline; no work needed.")
        if self._observations:
            parts.append("Tool results from your previous turn:\n" + "\n\n".join(self._observations))
        return "\n\n".join(parts)

    async def _call_model(self, user_prompt: str) -> tuple[str, int, int, float]:
        assert self._client is not None
        started = time.perf_counter()
        if self.provider.protocol == "anthropic":
            url = f"{self.provider.base_url}/v1/messages"
            headers = {"x-api-key": self.provider.api_key, "anthropic-version": "2023-06-01"}
            payload: Dict[str, Any] = {
                "model": self.provider.model,
                "max_tokens": self._max_output_tokens,
                "system": _SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            }
        else:
            url = f"{self.provider.base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {self.provider.api_key}"}
            payload = {
                "model": self.provider.model,
                "max_tokens": self._max_output_tokens,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            }

        last_error: Optional[str] = None
        for attempt in range(2):
            try:
                response = await self._client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
                latency_ms = (time.perf_counter() - started) * 1000.0
                usage = data.get("usage") or {}
                if self.provider.protocol == "anthropic":
                    blocks = data.get("content") or []
                    text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
                else:
                    choices = data.get("choices") or []
                    text = (choices[0].get("message") or {}).get("content", "") if choices else ""
                return (
                    text,
                    int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
                    int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
                    latency_ms,
                )
            except httpx.HTTPStatusError as exc:
                last_error = f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
                if exc.response.status_code not in (429, 500, 502, 503):
                    break
            except (httpx.TimeoutException, httpx.HTTPError, ValueError, KeyError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            if attempt == 0:
                await asyncio.sleep(1.5)
        raise RuntimeError(f"LLM call failed after retries: {last_error}")

    # -- action execution ---------------------------------------------------

    async def _browser_check(self, action: Dict[str, Any], args: Any) -> ActionOutcome:
        """Render a URL headless via Playwright and report what the page shows."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return ActionOutcome(action=action, status="error", detail="playwright not installed")
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(
                        viewport={"width": args.viewport_width, "height": args.viewport_height}
                    )
                    console_errors: List[str] = []
                    page.on(
                        "console",
                        lambda msg: console_errors.append(msg.text[:200])
                        if msg.type == "error"
                        else None,
                    )
                    response = await page.goto(args.url, timeout=30_000, wait_until="domcontentloaded")
                    title = await page.title()
                    body_text = (await page.inner_text("body"))[:2000]
                    overflow = await page.evaluate(
                        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                    )
                finally:
                    await browser.close()
        except Exception as exc:  # playwright raises many types
            return ActionOutcome(action=action, status="error", detail=f"browser_check failed: {exc}")
        status = response.status if response else 0
        detail = (
            f"HTTP {status}; title={title!r}; overflow-x={overflow}; "
            f"console_errors={json.dumps(console_errors[:10])}\n{body_text}"
        )
        return ActionOutcome(action=action, status="applied", detail=detail)

    async def _apply_action(self, action: Dict[str, Any]) -> ActionOutcome:
        spec, args, error = validate_action(action)
        if error is not None or spec is None:
            return ActionOutcome(action=action if isinstance(action, dict) else {}, status="blocked" if isinstance(error, str) and error.startswith("blocked:") else "error", detail=error or "invalid action")

        if spec.name == "read_file":
            path = _confined_path(self.workspace, args.path)  # type: ignore[attr-defined]
            if path is None:
                return ActionOutcome(action=action, status="blocked", detail="path outside workspace")
            if not path.is_file():
                return ActionOutcome(action=action, status="skipped", detail="file not found")
            content = path.read_text(encoding="utf-8", errors="replace")[: args.max_bytes]  # type: ignore[attr-defined]
            return ActionOutcome(action=action, status="applied", detail=f"read {len(content)} chars\n{content}")

        if spec.name == "list_files":
            pattern = args.pattern  # type: ignore[attr-defined]
            matches = sorted(str(p.relative_to(self.workspace)) for p in self.workspace.glob(pattern) if p.is_file())[:200]
            return ActionOutcome(action=action, status="applied", detail=json.dumps(matches))

        if spec.name == "search_files":
            query = args.query  # type: ignore[attr-defined]
            glob = args.glob  # type: ignore[attr-defined]
            matches: List[str] = []
            for candidate in sorted(self.workspace.glob(glob)):
                if not candidate.is_file() or len(matches) >= args.max_results:  # type: ignore[attr-defined]
                    if len(matches) >= args.max_results:  # type: ignore[attr-defined]
                        break
                    continue
                try:
                    text = candidate.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for lineno, line in enumerate(text.splitlines(), start=1):
                    if query in line:
                        matches.append(f"{candidate.relative_to(self.workspace)}:{lineno}: {line.strip()[:200]}")
                        if len(matches) >= args.max_results:  # type: ignore[attr-defined]
                            break
            return ActionOutcome(action=action, status="applied", detail="\n".join(matches) or "no matches")

        if spec.name == "fetch_url":
            parsed = urlparse(args.url)  # type: ignore[attr-defined]
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                return ActionOutcome(action=action, status="blocked", detail="only absolute http(s) URLs are allowed")
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as fetch_client:
                    response = await fetch_client.get(args.url)  # type: ignore[attr-defined]
                response.raise_for_status()
            except httpx.HTTPError as exc:
                return ActionOutcome(action=action, status="error", detail=f"fetch failed: {exc}")
            body = response.text[: args.max_chars]  # type: ignore[attr-defined]
            return ActionOutcome(action=action, status="applied", detail=f"HTTP {response.status_code}\n{body}")

        if spec.name == "browser_check":
            return await self._browser_check(action, args)

        if spec.name == "write_file":
            path = _confined_path(self.workspace, args.path)  # type: ignore[attr-defined]
            if path is None:
                return ActionOutcome(action=action, status="blocked", detail="path outside workspace")
            content = args.content  # type: ignore[attr-defined]
            if len(content.encode("utf-8")) > _MAX_FILE_BYTES:
                return ActionOutcome(action=action, status="blocked", detail="content exceeds size cap")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ActionOutcome(action=action, status="applied", detail=f"wrote {len(content)} chars")

        if spec.name == "delete_file":
            path = _confined_path(self.workspace, args.path)  # type: ignore[attr-defined]
            if path is None:
                return ActionOutcome(action=action, status="blocked", detail="path outside workspace")
            if path.is_file():
                path.unlink()
                return ActionOutcome(action=action, status="applied", detail=f"deleted {path.name}")
            return ActionOutcome(action=action, status="skipped", detail="file not found")

        if spec.name == "run_command":
            if os.environ.get("HINAA_LOOP_ALLOW_COMMANDS") != "1":
                return ActionOutcome(
                    action=action,
                    status="blocked",
                    detail="shell disabled; set HINAA_LOOP_ALLOW_COMMANDS=1 to enable",
                )
            command = args.command  # type: ignore[attr-defined]
            try:
                proc = subprocess.run(
                    command,
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=_COMMAND_TIMEOUT_SECONDS,
                    shell=True,
                )
                detail = f"exit {proc.returncode}; stdout={proc.stdout[:400]!r} stderr={proc.stderr[:400]!r}"
                return ActionOutcome(action=action, status="applied", detail=detail)
            except subprocess.TimeoutExpired:
                return ActionOutcome(action=action, status="error", detail="command timeout")
            except OSError as exc:
                return ActionOutcome(action=action, status="error", detail=str(exc))

        return ActionOutcome(action=action, status="error", detail=f"unhandled tool: {spec.name!r}")

    # -- trace --------------------------------------------------------------

    def _append_trace(self, record: Dict[str, Any]) -> None:
        line = json.dumps({k: record.get(k) for k in _TRACE_LINE_KEYS}, ensure_ascii=False, default=str)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    # -- public entry -------------------------------------------------------

    async def run(self, spec: LoopTaskSpec, turn: int, last_receipt: Optional[EvidenceReceipt]) -> AgentStepResult:
        user_prompt = self._build_user_prompt(spec, turn, last_receipt)
        try:
            text, input_tokens, output_tokens, latency_ms = await self._call_model(user_prompt)
        except Exception as exc:
            result = AgentStepResult(
                thought="",
                summary=f"LLM call failed: {exc}",
                actions_applied=0,
                status="error",
                provider=self.provider.name,
                model=self.provider.model,
                error=str(exc),
            )
            self._append_trace(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "task_id": spec.task_id,
                    "turn": turn,
                    "provider": self.provider.name,
                    "model": self.provider.model,
                    "latency_ms": 0.0,
                    "prompt_chars": len(user_prompt),
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "thought": "",
                    "actions": [],
                    "outcomes": [],
                    "status": "error",
                    "error": str(exc)[:500],
                }
            )
            result.trace_path = str(self.trace_path)
            await EVENT_BUS.publish(
                spec.task_id,
                "turn_failed",
                {"turn": turn, "error": str(exc)[:500]},
            )
            return result

        parsed = _extract_json_object(text)
        outcomes: List[ActionOutcome] = []
        if parsed is None:
            thought, actions = text.strip()[:2000], []
        else:
            thought = str(parsed.get("thought", ""))
            raw_actions = parsed.get("actions")
            actions = raw_actions if isinstance(raw_actions, list) else []
        for action in actions[:_MAX_ACTIONS_PER_TURN]:
            outcomes.append(await self._apply_action(action))
        self._observations = [
            f"[{o.action.get('type', '?')}] {o.status}: {o.detail[:_OBSERVATION_CHARS]}" for o in outcomes
        ]

        applied = sum(1 for o in outcomes if o.status == "applied")
        blocked = sum(1 for o in outcomes if o.status == "blocked")
        if parsed is None:
            summary = "Model reply was not a JSON action plan; no changes applied."
            status = "error"
        elif applied == 0 and not actions:
            summary = f"Model proposed no actions. Thought: {thought[:300]}"
            status = "no_actions"
        else:
            summary = (
                f"Thought: {thought[:300]} | actions: {len(actions)} proposed, "
                f"{applied} applied, {blocked} blocked."
            )
            status = "acted"

        result = AgentStepResult(
            thought=thought[:2000],
            summary=summary,
            actions_applied=applied,
            status=status,
            provider=self.provider.name,
            model=self.provider.model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            outcomes=outcomes,
            trace_path=str(self.trace_path),
        )
        self._append_trace(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "task_id": spec.task_id,
                "turn": turn,
                "provider": self.provider.name,
                "model": self.provider.model,
                "latency_ms": round(latency_ms, 2),
                "prompt_chars": len(user_prompt),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "thought": result.thought,
                "actions": actions[:_MAX_ACTIONS_PER_TURN],
                "outcomes": [
                    {"status": o.status, "detail": o.detail[:300], "action": o.action}
                    for o in outcomes
                ],
                "status": status,
                "error": None,
            }
        )
        await EVENT_BUS.publish(
            spec.task_id,
            "turn_completed",
            {
                "turn": turn,
                "thought": result.thought,
                "provider": self.provider.name,
                "model": self.provider.model,
                "latency_ms": round(latency_ms, 2),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "actions_applied": applied,
                "actions_blocked": blocked,
                "outcomes": [
                    {"status": o.status, "detail": o.detail[:300]} for o in outcomes
                ],
            },
        )
        return result

    def as_engine_step(
        self, spec: LoopTaskSpec
    ) -> Callable[[int, Optional[EvidenceReceipt]], Awaitable[str]]:
        """Adapter matching the LoopEngine.run_loop agent_step signature."""

        async def step(turn: int, last_receipt: Optional[EvidenceReceipt]) -> str:
            result = await self.run(spec, turn, last_receipt)
            return result.as_engine_summary()

        return step


def build_llm_agent_step(
    spec: LoopTaskSpec,
    workspace_dir: Optional[Path] = None,
    trace_dir: Optional[Path] = None,
    settings: Any = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Optional[LLMAgentStep]:
    """Build a real agent step for a task, or None when no provider is configured."""
    provider = resolve_loop_provider(settings)
    if provider is None:
        return None
    if trace_dir is None:
        from ..runtime_paths import project_root

        trace_dir = project_root() / ".runtime" / "loop_state"
    workspace = Path(workspace_dir) if workspace_dir else Path(spec.workspace_dir) if spec.workspace_dir else None
    if workspace is None:
        from ..runtime_paths import project_root

        workspace = project_root()
    return LLMAgentStep(
        provider=provider,
        workspace_dir=workspace,
        trace_path=trace_dir / f"{spec.task_id}_trace.jsonl",
        client=client,
    )
