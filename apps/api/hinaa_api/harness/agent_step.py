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
import base64
import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx

from .loop_engine import EvidenceReceipt, LoopTaskSpec
from .loop_events import EVENT_BUS
from .loop_tools import describe_tools, validate_action
from .media_ingest import load_media_insights

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
    '{"type": "build_website", "brief": "<brand + goal>", "confirm": true}, '
    '{"type": "run_dev_server", "command": "<cmd>", "subdir": ".", "port": 3005, "confirm": true}, '
    '{"type": "screenshot_page", "url": "http://127.0.0.1:3005/", "label": "home"}, '
    '{"type": "read_file", "path": "<relative path>", "max_bytes": 16000}, '
    '{"type": "digest_document", "path": "<relative path>", "query": "<focus>", "max_chunks": 6}, '
    '{"type": "list_media"}, '
    '{"type": "describe_media", "media_id": "<med_...>"}, '
    '{"type": "review_diff", "focus": "<area>"}, '
    '{"type": "list_files", "pattern": "**/*"}, '
    '{"type": "search_files", "query": "<literal text>", "glob": "**/*"}, '
    '{"type": "fetch_url", "url": "https://...", "max_chars": 12000}, '
    '{"type": "browser_check", "url": "http://127.0.0.1:3000", "viewport_width": 1280, "viewport_height": 800}'
    "]}\n"
    "Tools:\n" + describe_tools() + "\n"
    "Rules: inspect first with read_file/list_files/search_files/digest_document/list_media (no confirm needed); "
    "every side-effecting action MUST carry \"confirm\": true or it is refused; paths are "
    "relative to the workspace root and must stay inside it; write the complete final "
    "content of any file you touch; keep actions minimal; never invent a verification "
    "result or fabricate assets/metrics."
)

_MAX_ACTIONS_PER_TURN = 8
_MAX_FILE_BYTES = 512_000
_COMMAND_TIMEOUT_SECONDS = 60.0
_OBSERVATION_CHARS = 6_000
_MAX_PROMPT_CHARS = 36_000

_SECRET_PATTERNS = (
    re.compile(r"\bsk-(?:ant-[A-Za-z0-9_-]{8,}|proj-[A-Za-z0-9_-]{10,}|live-[A-Za-z0-9_-]{10,}|[A-Za-z0-9_-]{20,})"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bgh[po]_[0-9A-Za-z]{20,}\b"),
    re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{16,}"),
)

_BLOCKED_FETCH_HOSTS = frozenset({"localhost", "localhost.localdomain", "metadata.google.internal"})


def scrub_secrets(value: Any) -> Any:
    """Recursively mask API tokens and bearer secrets before writing traces or SSE payloads."""
    if isinstance(value, str):
        out = value
        for pat in _SECRET_PATTERNS:
            out = pat.sub("[REDACTED]", out)
        return out
    if isinstance(value, dict):
        return {k: scrub_secrets(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_secrets(item) for item in value]
    return value


def _is_blocked_ip(ip_text: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    )


def _check_fetch_url_safety(url: str) -> Optional[str]:
    """Validate scheme, optional egress allowlist, and block private/SSRF targets."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or not parsed.hostname:
        return "only absolute http(s) URLs are allowed"
    host = parsed.hostname.lower().strip(".")
    allowlist_raw = os.environ.get("HINAA_LOOP_EGRESS_ALLOWLIST", "").strip()
    if allowlist_raw:
        allowed = [item.strip().lower() for item in allowlist_raw.split(",") if item.strip()]
        if allowed and not any(host == dom or host.endswith("." + dom) for dom in allowed):
            return f"egress blocked: host {host!r} not in HINAA_LOOP_EGRESS_ALLOWLIST"
    if os.environ.get("HINAA_LOOP_ALLOW_PRIVATE_FETCH") == "1":
        return None
    if host in _BLOCKED_FETCH_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        return f"ssrf blocked: host {host!r} is restricted"
    if _is_blocked_ip(host):
        return f"ssrf blocked: address {host!r} is private or link-local"
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return None
    for info in infos:
        resolved_ip = info[4][0]
        if _is_blocked_ip(resolved_ip):
            return f"ssrf blocked: {host!r} resolves to private/link-local address {resolved_ip}"
    return None


def _is_screenshot_url_allowed(url: str) -> Optional[str]:
    """Allow local loopback dev servers and non-metadata http(s) URLs for visual screenshots."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "only absolute http(s) URLs can be screenshotted"
    host = parsed.hostname.lower().strip(".")
    if host in {"127.0.0.1", "localhost", "::1"}:
        return None
    return _check_fetch_url_safety(url)


_APPROVAL_WAITERS: Dict[tuple[str, str], asyncio.Future] = {}


def compute_approval_id(task_id: str, turn: int, action: Dict[str, Any]) -> str:
    """Derive a server-bound canonical hash ID for an approval request (never model-controlled)."""
    canonical = json.dumps({"task_id": task_id, "turn": turn, "action": action}, sort_keys=True, default=str)
    return "appr_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def resolve_approval(task_id: str, approval_id: str, approved: bool) -> bool:
    """Resolve a live pending approval future matching (task_id, approval_id)."""
    fut = _APPROVAL_WAITERS.get((task_id, approval_id))
    if fut is None or fut.done():
        return False
    fut.set_result(bool(approved))
    return True


def list_pending_approvals(task_id: str) -> List[str]:
    """Return active approval_ids currently waiting on human confirmation for a task."""
    return [aid for (tid, aid), fut in _APPROVAL_WAITERS.items() if tid == task_id and not fut.done()]
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


def resolve_loop_providers(settings: Any = None) -> List[LoopProvider]:
    """Return all configured providers ordered by verified reliability and latency."""
    if settings is None:
        from ..config import get_settings

        settings = get_settings()

    providers: List[LoopProvider] = []

    gemini_key = getattr(settings, "gemini_api_key", None)
    if gemini_key is not None and _secret(gemini_key).strip():
        providers.append(
            LoopProvider(
                name="gemini",
                protocol="openai",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key=_secret(gemini_key).strip(),
                model=str(getattr(settings, "gemini_model", None) or "gemini-2.5-flash"),
            )
        )

    xkiro_key = getattr(settings, "active_xkiro_key", None) or getattr(settings, "xkiro_api_key", None)
    xkiro_base = getattr(settings, "active_xkiro_base_url", None) or getattr(settings, "xkiro_base_url", None)
    if xkiro_key is not None and _secret(xkiro_key).strip() and xkiro_base:
        providers.append(
            LoopProvider(
                name="xkiro",
                protocol="openai",
                base_url=str(xkiro_base).strip().rstrip("/"),
                api_key=_secret(xkiro_key).strip(),
                model=str(getattr(settings, "active_xkiro_model", "openai/gpt-6.2-sol")),
            )
        )

    openai_key = getattr(settings, "openai_api_key", None)
    if openai_key is not None and _secret(openai_key).strip():
        providers.append(
            LoopProvider(
                name="openai",
                protocol="openai",
                base_url="https://api.openai.com/v1",
                api_key=_secret(openai_key).strip(),
                model=str(getattr(settings, "openai_model", "gpt-5-mini")),
            )
        )

    groq_key = getattr(settings, "groq_api_key", None)
    if groq_key is not None and _secret(groq_key).strip():
        providers.append(
            LoopProvider(
                name="groq",
                protocol="openai",
                base_url="https://api.groq.com/openai/v1",
                api_key=_secret(groq_key).strip(),
                model=str(getattr(settings, "groq_model", "llama-3.1-8b-instant")),
            )
        )

    claude_key = getattr(settings, "claude_api_key", None)
    if claude_key is not None and _secret(claude_key).strip():
        base_url = getattr(settings, "claude_base_url", "https://api.anthropic.com").strip().rstrip("/")
        model = getattr(settings, "active_claude_model", None) or "claude-sonnet-4-5"
        providers.append(
            LoopProvider(
                name="claude",
                protocol="anthropic",
                base_url=base_url,
                api_key=_secret(claude_key).strip(),
                model=str(model),
            )
        )

    agent_router_key = getattr(settings, "agent_router_api_key", None)
    if agent_router_key is not None and _secret(agent_router_key).strip():
        base_url = getattr(settings, "active_agent_router_base_url", None) or "https://api.agentrouter.dev/v1"
        model = getattr(settings, "active_agent_router_model", None) or "gpt-6-astra"
        if str(base_url).strip():
            providers.append(
                LoopProvider(
                    name="agent-router",
                    protocol="openai",
                    base_url=str(base_url).strip().rstrip("/"),
                    api_key=_secret(agent_router_key).strip(),
                    model=str(model),
                )
            )

    return providers


def resolve_loop_provider(settings: Any = None) -> Optional[LoopProvider]:
    """Pick the highest-priority configured provider, falling back smoothly."""
    providers = resolve_loop_providers(settings)
    return providers[0] if providers else None


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
        fallback_providers: Optional[List[LoopProvider]] = None,
        state_dir: Optional[Path] = None,
        require_human_approval: bool = False,
        approval_timeout_seconds: float = 300.0,
    ) -> None:
        self.provider = provider
        self._fallback_providers = list(fallback_providers or [])
        self.workspace = Path(workspace_dir)
        self.trace_path = Path(trace_path)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_dir = Path(state_dir) if state_dir is not None else self.trace_path.parent
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        self._client = client
        self._owns_client = client is None
        self._require_human_approval = require_human_approval
        self._approval_timeout_seconds = approval_timeout_seconds
        self._observations: List[str] = []
        self._pending_vision_images: List[Path] = []
        self._spawned_servers: List[subprocess.Popen] = []
        self._current_task_id: str = ""
        self._current_turn: int = 0

    async def aclose(self) -> None:
        for proc in self._spawned_servers:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except OSError:
                pass
        self._spawned_servers.clear()
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    # -- model call ---------------------------------------------------------

    @staticmethod
    def _budget_prompt(parts: List[str], max_chars: int = _MAX_PROMPT_CHARS) -> str:
        """Assemble prompt parts with middle-out compaction so long runs stay inside context budget."""
        joined = "\n\n".join(parts)
        if len(joined) <= max_chars or len(parts) <= 2:
            return joined if len(joined) <= max_chars else (
                joined[: max_chars // 2]
                + f"\n...[truncated middle {len(joined) - max_chars} chars]...\n"
                + joined[-(max_chars // 2 - 80):]
            )
        head = "\n\n".join(parts[:2])
        tail = "\n\n".join(parts[-2:]) if len(parts) >= 4 else parts[-1]
        middle = "\n\n".join(parts[2:-2]) if len(parts) >= 4 else ""
        fixed_len = len(head) + len(tail) + 64
        if fixed_len >= max_chars:
            head_budget = max(400, int(max_chars * 0.35))
            tail_budget = max(400, max_chars - head_budget - 80)
            return (
                head[:head_budget]
                + f"\n...[truncated middle {max(0, len(joined) - head_budget - tail_budget)} chars]...\n"
                + tail[-tail_budget:]
            )
        avail_mid = max_chars - fixed_len
        if len(middle) <= avail_mid:
            return f"{head}\n\n{middle}\n\n{tail}" if middle else f"{head}\n\n{tail}"
        keep_half = max(0, (avail_mid - 64) // 2)
        trimmed = (
            (middle[:keep_half] if keep_half else "")
            + f"\n...[truncated middle {len(middle) - 2 * keep_half} chars]...\n"
            + (middle[-keep_half:] if keep_half else "")
        )
        return f"{head}\n\n{trimmed}\n\n{tail}"

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
        media_items = load_media_insights(self._state_dir, spec.task_id) if spec.task_id else []
        if media_items:
            brief_media = "; ".join(f"{m.media_id} ({m.kind}: {m.summary[:100]})" for m in media_items[:8])
            parts.append(f"Attached media insights ({len(media_items)} total): {brief_media}")
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
        return self._budget_prompt(parts)

    @staticmethod
    def _encode_vision_parts(vision_paths: List[Path], protocol: str) -> List[Dict[str, Any]]:
        parts: List[Dict[str, Any]] = []
        for path in vision_paths[:2]:
            if not path.is_file() or path.stat().st_size > 4_000_000:
                continue
            ext = path.suffix.lower()
            mime = "image/jpeg" if ext in {".jpg", ".jpeg"} else "image/webp" if ext == ".webp" else "image/png"
            b64 = base64.b64encode(path.read_bytes()).decode("ascii")
            if protocol == "anthropic":
                parts.append(
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}}
                )
            else:
                parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        return parts

    async def _call_single_provider(
        self,
        prov: LoopProvider,
        user_prompt: str,
        *,
        vision_paths: Optional[List[Path]] = None,
        system_prompt: str = _SYSTEM_PROMPT,
    ) -> tuple[str, int, int, float]:
        if self._client is None:
            self._client = httpx.AsyncClient()
            self._owns_client = True
        started = time.perf_counter()
        v_parts = self._encode_vision_parts(vision_paths or [], prov.protocol)
        if prov.protocol == "anthropic":
            url = f"{prov.base_url}/v1/messages"
            headers = {"x-api-key": prov.api_key, "anthropic-version": "2023-06-01"}
            msg_content: Any = (
                [{"type": "text", "text": user_prompt}, *v_parts] if v_parts else user_prompt
            )
            payload: Dict[str, Any] = {
                "model": prov.model,
                "max_tokens": self._max_output_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": msg_content}],
            }
        else:
            url = f"{prov.base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {prov.api_key}"}
            msg_content = (
                [{"type": "text", "text": user_prompt}, *v_parts] if v_parts else user_prompt
            )
            payload = {
                "model": prov.model,
                "max_tokens": self._max_output_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": msg_content},
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
                if prov.protocol == "anthropic":
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
                await asyncio.sleep(1.0)
        raise RuntimeError(f"LLM call failed for {prov.name} ({prov.model}): {last_error}")

    async def _call_model(
        self,
        user_prompt: str,
        *,
        vision_paths: Optional[List[Path]] = None,
        system_prompt: str = _SYSTEM_PROMPT,
    ) -> tuple[str, int, int, float]:
        candidates = [self.provider, *self._fallback_providers]
        errors: List[str] = []
        for idx, cand in enumerate(candidates):
            try:
                res = await self._call_single_provider(
                    cand,
                    user_prompt,
                    vision_paths=vision_paths,
                    system_prompt=system_prompt,
                )
                if idx > 0:
                    self.provider = cand
                return res
            except RuntimeError as err:
                errors.append(str(err))
        raise RuntimeError(" ; ".join(errors))

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

    async def _await_human_approval(self, tool_name: str, action: Dict[str, Any]) -> Optional[str]:
        """Suspend execution on a side-effecting tool until POST /approve resolves its server hash ID."""
        task_id = self._current_task_id or "loop"
        approval_id = compute_approval_id(task_id, self._current_turn, action)
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        _APPROVAL_WAITERS[(task_id, approval_id)] = fut
        try:
            await EVENT_BUS.publish(
                task_id,
                "approval_required",
                {
                    "approval_id": approval_id,
                    "turn": self._current_turn,
                    "tool": tool_name,
                    "action": scrub_secrets(action),
                },
            )
            approved = await asyncio.wait_for(fut, timeout=self._approval_timeout_seconds)
            return None if approved else "blocked: human approval denied"
        except asyncio.TimeoutError:
            return "blocked: human approval timed out"
        finally:
            _APPROVAL_WAITERS.pop((task_id, approval_id), None)

    async def _apply_action(self, action: Dict[str, Any]) -> ActionOutcome:
        spec, args, error = validate_action(action)
        if error is not None or spec is None:
            return ActionOutcome(
                action=action if isinstance(action, dict) else {},
                status="blocked" if isinstance(error, str) and error.startswith("blocked:") else "error",
                detail=error or "invalid action",
            )

        if self._require_human_approval and spec.side_effect:
            gate_err = await self._await_human_approval(spec.name, action)
            if gate_err is not None:
                return ActionOutcome(action=action, status="blocked", detail=gate_err)

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
            cur_url = args.url  # type: ignore[attr-defined]
            ssrf_err = _check_fetch_url_safety(cur_url)
            if ssrf_err is not None:
                return ActionOutcome(action=action, status="blocked", detail=ssrf_err)
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as fetch_client:
                    response = None
                    for _ in range(4):
                        response = await fetch_client.get(cur_url)
                        if response.status_code in (301, 302, 303, 307, 308):
                            loc = response.headers.get("location", "").strip()
                            if not loc:
                                break
                            cur_url = urljoin(cur_url, loc)
                            hop_err = _check_fetch_url_safety(cur_url)
                            if hop_err is not None:
                                return ActionOutcome(action=action, status="blocked", detail=hop_err)
                            continue
                        break
                assert response is not None
                response.raise_for_status()
            except httpx.HTTPError as exc:
                return ActionOutcome(action=action, status="error", detail=f"fetch failed: {exc}")
            body = response.text[: args.max_chars]  # type: ignore[attr-defined]
            return ActionOutcome(action=action, status="applied", detail=f"HTTP {response.status_code}\n{body}")

        if spec.name == "browser_check":
            return await self._browser_check(action, args)

        if spec.name == "build_website":
            return await self._build_website(action, args)

        if spec.name == "run_dev_server":
            return await self._run_dev_server(action, args)

        if spec.name == "screenshot_page":
            return await self._screenshot_page(action, args)

        if spec.name == "list_media":
            items = load_media_insights(self._state_dir, self._current_task_id or "loop")
            kind_filter = (args.kind or "").strip().lower()  # type: ignore[attr-defined]
            if kind_filter:
                items = [m for m in items if m.kind.lower() == kind_filter]
            brief = [
                {
                    "media_id": m.media_id,
                    "filename": m.filename,
                    "kind": m.kind,
                    "size_bytes": m.size_bytes,
                    "summary": m.summary,
                }
                for m in items[:50]
            ]
            return ActionOutcome(action=action, status="applied", detail=json.dumps(brief))

        if spec.name == "describe_media":
            media_id = args.media_id.strip()  # type: ignore[attr-defined]
            items = load_media_insights(self._state_dir, self._current_task_id or "loop")
            found = next((m for m in items if m.media_id == media_id), None)
            if found is None:
                return ActionOutcome(action=action, status="skipped", detail=f"media_id {media_id!r} not found")
            return ActionOutcome(
                action=action,
                status="applied",
                detail=json.dumps(found.model_dump(exclude={"stored_path"})),
            )

        if spec.name == "digest_document":
            return self._digest_document(action, args)

        if spec.name == "review_diff":
            diff_text = self._collect_workspace_diff(args.focus)  # type: ignore[attr-defined]
            return ActionOutcome(action=action, status="applied", detail=diff_text)

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

    async def _build_website(self, action: Dict[str, Any], args: Any) -> ActionOutcome:
        try:
            from ..foundry.service import get_foundry_service

            rec = get_foundry_service().create_site(
                args.brief,
                palette=args.palette,
                logos=list(args.logos or []),
            )
        except Exception as exc:
            return ActionOutcome(action=action, status="error", detail=f"build_website failed: {exc}")
        preview_url = f"/api/v1/foundry/sites/{rec.site_id}/preview"
        if self._current_task_id:
            await EVENT_BUS.publish(
                self._current_task_id,
                "preview_ready",
                {
                    "site_id": rec.site_id,
                    "url": preview_url,
                    "brand": rec.brand,
                    "size_kb": rec.size_kb,
                    "archetype": rec.archetype,
                    "turn": self._current_turn,
                },
            )
        return ActionOutcome(
            action=action,
            status="applied",
            detail=json.dumps(
                {
                    "site_id": rec.site_id,
                    "preview_url": preview_url,
                    "brand": rec.brand,
                    "size_kb": rec.size_kb,
                    "archetype": rec.archetype,
                }
            ),
        )

    async def _run_dev_server(self, action: Dict[str, Any], args: Any) -> ActionOutcome:
        if os.environ.get("HINAA_LOOP_ALLOW_COMMANDS") != "1":
            return ActionOutcome(
                action=action,
                status="blocked",
                detail="shell disabled; set HINAA_LOOP_ALLOW_COMMANDS=1 to enable run_dev_server",
            )
        subdir = _confined_path(self.workspace, args.subdir)
        if subdir is None or not subdir.is_dir():
            return ActionOutcome(action=action, status="blocked", detail="subdir outside workspace or missing")
        port = int(args.port)
        url = f"http://127.0.0.1:{port}/"
        try:
            proc = subprocess.Popen(
                args.command,
                cwd=str(subdir),
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            return ActionOutcome(action=action, status="error", detail=f"failed to start dev server: {exc}")
        self._spawned_servers.append(proc)
        reachable = False
        async with httpx.AsyncClient(timeout=1.0) as probe:
            for _ in range(10):
                if proc.poll() is not None:
                    break
                try:
                    resp = await probe.get(url)
                    if resp.status_code < 500:
                        reachable = True
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.35)
        if self._current_task_id:
            await EVENT_BUS.publish(
                self._current_task_id,
                "preview_ready",
                {"url": url, "port": port, "pid": proc.pid, "reachable": reachable, "turn": self._current_turn},
            )
        return ActionOutcome(
            action=action,
            status="applied",
            detail=json.dumps({"preview_url": url, "port": port, "pid": proc.pid, "reachable": reachable}),
        )

    async def _screenshot_page(self, action: Dict[str, Any], args: Any) -> ActionOutcome:
        url_err = _is_screenshot_url_allowed(args.url)
        if url_err is not None:
            return ActionOutcome(action=action, status="blocked", detail=url_err)
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return ActionOutcome(action=action, status="error", detail="playwright not installed")
        safe_task = re.sub(r"[^A-Za-z0-9._-]+", "_", self._current_task_id or "loop")
        safe_label = re.sub(r"[^A-Za-z0-9._-]+", "_", args.label or "page")[:40]
        evidence_dir = self.workspace / "docs" / "evidence" / safe_task
        evidence_dir.mkdir(parents=True, exist_ok=True)
        desktop_path = evidence_dir / f"{safe_label}_desktop.png"
        mobile_path = evidence_dir / f"{safe_label}_mobile.png"
        console_errors: List[str] = []
        overflow: Dict[str, bool] = {}
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    for key, w, h, target_path in (
                        ("desktop", 1280, 800, desktop_path),
                        ("mobile", 390, 844, mobile_path),
                    ):
                        page = await browser.new_page(viewport={"width": w, "height": h})
                        page.on(
                            "console",
                            lambda msg: console_errors.append(msg.text[:200]) if msg.type == "error" else None,
                        )
                        await page.goto(args.url, timeout=30_000, wait_until="domcontentloaded")
                        overflow[key] = bool(
                            await page.evaluate(
                                "document.documentElement.scrollWidth > document.documentElement.clientWidth"
                            )
                        )
                        await page.screenshot(path=str(target_path), full_page=False)
                        await page.close()
                finally:
                    await browser.close()
        except Exception as exc:
            return ActionOutcome(action=action, status="error", detail=f"screenshot_page failed: {exc}")

        self._pending_vision_images.extend([desktop_path, mobile_path])
        rel_desktop = desktop_path.relative_to(self.workspace).as_posix()
        rel_mobile = mobile_path.relative_to(self.workspace).as_posix()
        if self._current_task_id:
            await EVENT_BUS.publish(
                self._current_task_id,
                "evidence_captured",
                {
                    "turn": self._current_turn,
                    "url": args.url,
                    "screenshots": [rel_desktop, rel_mobile],
                    "overflow": overflow,
                    "console_errors": console_errors[:10],
                },
            )
        return ActionOutcome(
            action=action,
            status="applied",
            detail=json.dumps(
                {
                    "screenshots": [rel_desktop, rel_mobile],
                    "overflow": overflow,
                    "console_errors": console_errors[:10],
                }
            ),
        )

    def _digest_document(self, action: Dict[str, Any], args: Any) -> ActionOutcome:
        path = _confined_path(self.workspace, args.path)
        if path is None:
            return ActionOutcome(action=action, status="blocked", detail="path outside workspace")
        if not path.is_file():
            return ActionOutcome(action=action, status="skipped", detail="file not found")
        headings: List[str] = []
        matching: List[str] = []
        samples: List[str] = []
        query = (args.query or "").strip().lower()
        max_chunks = int(args.max_chunks)
        line_count = 0
        word_count = 0
        buf: List[str] = []
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line_count += 1
                word_count += len(line.split())
                s = line.strip()
                if s.startswith("#") and len(headings) < 40:
                    headings.append(s[:120])
                buf.append(line.rstrip())
                if len(buf) >= 20:
                    chunk = "\n".join(buf)[:650]
                    buf.clear()
                    if query and query in chunk.lower() and len(matching) < max_chunks:
                        matching.append(f"[lines {line_count - 19}-{line_count}]\n{chunk}")
                    elif not query and len(samples) < max_chunks and (line_count // 20) % 5 == 1:
                        samples.append(f"[lines {line_count - 19}-{line_count}]\n{chunk}")
                if line_count >= 50_000:
                    break
        if buf:
            chunk = "\n".join(buf)[:650]
            if query and query in chunk.lower() and len(matching) < max_chunks:
                matching.append(f"[tail]\n{chunk}")
            elif not query and len(samples) < max_chunks:
                samples.append(f"[tail]\n{chunk}")
        excerpts = matching if matching else samples
        payload = {
            "path": args.path,
            "lines_scanned": line_count,
            "words_scanned": word_count,
            "headings": headings,
            "excerpts": excerpts[:max_chunks],
        }
        return ActionOutcome(action=action, status="applied", detail=json.dumps(payload)[:5500])

    def _collect_workspace_diff(self, focus: str = "") -> str:
        try:
            st = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=15,
            )
            df = subprocess.run(
                ["git", "diff", "--unified=2"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=15,
            )
            raw = f"STATUS:\n{st.stdout[:1200]}\n\nDIFF:\n{df.stdout[:4200]}"
            if focus:
                raw = f"FOCUS: {focus}\n" + raw
            return scrub_secrets(raw)
        except Exception as exc:
            return f"diff inspection unavailable: {exc}"

    # -- trace --------------------------------------------------------------

    def _append_trace(self, record: Dict[str, Any]) -> None:
        sanitized = scrub_secrets({k: record.get(k) for k in _TRACE_LINE_KEYS})
        line = json.dumps(sanitized, ensure_ascii=False, default=str)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    # -- public entry -------------------------------------------------------

    async def run(self, spec: LoopTaskSpec, turn: int, last_receipt: Optional[EvidenceReceipt]) -> AgentStepResult:
        self._current_task_id = spec.task_id
        self._current_turn = turn
        user_prompt = self._build_user_prompt(spec, turn, last_receipt)
        vision_imgs = list(self._pending_vision_images[:2])
        self._pending_vision_images.clear()
        try:
            text, input_tokens, output_tokens, latency_ms = await self._call_model(
                user_prompt,
                vision_paths=vision_imgs,
            )
        except Exception as exc:
            err_msg = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
            result = AgentStepResult(
                thought="",
                summary=f"LLM call failed: {err_msg}",
                actions_applied=0,
                status="error",
                provider=self.provider.name,
                model=self.provider.model,
                error=err_msg,
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
                    "error": err_msg[:500],
                }
            )
            result.trace_path = str(self.trace_path)
            await EVENT_BUS.publish(
                spec.task_id,
                "turn_failed",
                {"turn": turn, "error": scrub_secrets(err_msg[:500])},
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
            scrub_secrets(
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
                        {"status": o.status, "detail": o.detail[:600], "tool": o.action.get("type")}
                        for o in outcomes
                    ],
                }
            ),
        )
        return result

    async def run_diff_review(self, spec: LoopTaskSpec, focus: str = "") -> Dict[str, Any]:
        """Fresh-context post-gate self-review examining only workspace diff and goal."""
        diff_bundle = self._collect_workspace_diff(focus)
        reviewer_system = (
            "You are a strict senior code reviewer in a fresh context window. "
            "Review ONLY the workspace diff against the goal. Return ONLY JSON: "
            '{"approved": true|false, "severity": "none"|"minor"|"critical", "findings": ["..."], "summary": "..."}'
        )
        prompt = f"Goal: {spec.goal_title}\n\n{diff_bundle}"
        try:
            raw, _, _, _ = await self._call_model(prompt, system_prompt=reviewer_system)
            parsed = _extract_json_object(raw) or {}
            verdict = {
                "approved": bool(parsed.get("approved", True)),
                "severity": str(parsed.get("severity", "none")),
                "findings": list(parsed.get("findings") or [])[:10],
                "summary": str(parsed.get("summary") or raw[:300]),
            }
        except Exception as exc:
            verdict = {
                "approved": True,
                "severity": "none",
                "findings": [],
                "summary": f"Reviewer skipped: {exc}",
            }
        if spec.task_id:
            await EVENT_BUS.publish(spec.task_id, "turn_reviewed", scrub_secrets(verdict))
        return verdict

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
    *,
    state_dir: Optional[Path] = None,
    require_human_approval: bool = False,
) -> Optional[LLMAgentStep]:
    """Build a real agent step for a task, or None when no provider is configured."""
    providers = resolve_loop_providers(settings)
    if not providers:
        return None
    if trace_dir is None:
        from ..runtime_paths import project_root

        trace_dir = project_root() / ".runtime" / "loop_state"
    workspace = Path(workspace_dir) if workspace_dir else Path(spec.workspace_dir) if spec.workspace_dir else None
    if workspace is None:
        from ..runtime_paths import project_root

        workspace = project_root()
    return LLMAgentStep(
        provider=providers[0],
        fallback_providers=providers[1:],
        workspace_dir=workspace,
        trace_path=trace_dir / f"{spec.task_id}_trace.jsonl",
        state_dir=state_dir or trace_dir,
        client=client,
        require_human_approval=require_human_approval,
    )
