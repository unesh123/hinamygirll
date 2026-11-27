"""Formal Runtime OS Contract for HINAA (12-state capability model, envelopes, workspace/process/preview/audit/connector tools)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..config import Settings, get_settings
from ..tools.registry import RiskTier, ToolDefinition, ToolEffect, registry
from ..tools.workspace_coding_tools import (
    _PROCESS_POOL,
    _PROCESS_POOL_LOCK,
    WorkspaceEditFileParams,
    WorkspaceGrepParams,
    WorkspaceListDirParams,
    WorkspaceProcessLogsParams,
    WorkspaceReadFileParams,
    WorkspaceRunCommandParams,
    WorkspaceStartProcessParams,
    WorkspaceStopProcessParams,
    WorkspaceWriteFileParams,
    _resolve_inside_workspace,
    _resolve_workspace_root,
    compute_file_hash,
    workspace_edit_file_handler,
    workspace_grep_handler,
    workspace_list_dir_handler,
    workspace_process_logs_handler,
    workspace_read_file_handler,
    workspace_run_command_handler,
    workspace_start_process_handler,
    workspace_stop_process_handler,
    workspace_write_file_handler,
)
from ..voice_fallback import voice_on_cooldown


class CapabilityState(StrEnum):
    UNAVAILABLE = "unavailable"
    CONFIGURED = "configured"
    AUTHORIZED = "authorized"
    CONNECTED = "connected"
    REACHABLE = "reachable"
    EXECUTING = "executing"
    TESTED = "tested"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    REVOKED = "revoked"
    NOT_VERIFIED = "not_verified"


ALLOWED_CAPABILITY_STATES: tuple[str, ...] = tuple(s.value for s in CapabilityState)


class PreviewStage(StrEnum):
    DETECTED = "detected"
    BUILT = "built"
    SERVER_STARTED = "server_started"
    LISTENING = "listening"
    HTTP_200 = "http_200"
    RENDERED_CLEANLY = "rendered_cleanly"
    INTERACTIVE_VERIFIED = "interactive_verified"
    EXPOSED = "exposed"
    DEGRADED = "degraded"
    STOPPED = "stopped"


PREVIEW_STAGES: tuple[str, ...] = tuple(s.value for s in PreviewStage)


class ToolResultEnvelope(BaseModel):
    success: bool
    status: str
    operation_id: str
    timestamp: str
    tool_name: str
    human_summary: str
    structured_result: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    changed_resources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    reversible: bool = True
    verification_state: str = CapabilityState.NOT_VERIFIED.value


class PreviewRecord(BaseModel):
    preview_id: str
    project_path: str
    framework: str
    port: int | None = None
    url: str | None = None
    process_id: str | None = None
    stage: PreviewStage = PreviewStage.DETECTED
    routes: list[str] = Field(default_factory=list)
    last_http_status: int | None = None
    console_error_count: int | None = None
    updated_at: str


_PREVIEW_REGISTRY: dict[str, PreviewRecord] = {}
_PREVIEW_LOCK = threading.Lock()
_OS_TOOLS_REGISTERED = False


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_tool_envelope(
    tool_name: str,
    raw: Any,
    *,
    human_summary: str = "",
    reversible: bool = True,
    verification_state: CapabilityState | str = CapabilityState.NOT_VERIFIED,
    changed_resources: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
) -> ToolResultEnvelope:
    payload = raw if isinstance(raw, dict) else {"result": raw}
    raw_status = str(payload.get("status") or "success")
    ok = raw_status not in {"error", "failed"} and not bool(payload.get("error"))
    err = str(payload.get("error")) if payload.get("error") else None
    changed = list(changed_resources or [])
    for key in ("path", "filePath", "file_path", "exportPath", "zipPath"):
        val = payload.get(key)
        if isinstance(val, str) and val and val not in changed:
            changed.append(val)
    ev = list(evidence or [])
    if payload.get("sha256"):
        ev.append({"type": "sha256", "value": payload["sha256"]})
    if payload.get("screenshotPath"):
        ev.append({"type": "screenshot", "path": payload["screenshotPath"]})
    if payload.get("url"):
        ev.append({"type": "url", "value": payload["url"], "httpStatus": payload.get("httpStatus")})
    v_state = str(verification_state.value if isinstance(verification_state, CapabilityState) else verification_state)
    if not ok and v_state == CapabilityState.NOT_VERIFIED.value:
        v_state = CapabilityState.FAILED.value
    summary = human_summary or (
        f"{tool_name} failed: {err}" if err else f"{tool_name} completed ({raw_status})."
    )
    return ToolResultEnvelope(
        success=ok,
        status=raw_status if ok else "failed",
        operation_id=f"op-{uuid.uuid4().hex[:12]}",
        timestamp=_utc_iso(),
        tool_name=tool_name,
        human_summary=summary,
        structured_result=payload,
        evidence=ev,
        changed_resources=changed,
        warnings=list(warnings or []),
        error=err,
        reversible=reversible,
        verification_state=v_state,
    )


# ---------------------------------------------------------------------------
# Parameter models for missing canonical runtime OS tools
# ---------------------------------------------------------------------------


class _PathParam(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    workspace_root: str | None = None


class _WriteParam(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    content: str
    overwrite: bool = True
    workspace_root: str | None = None


class _PatchParam(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    target: str = Field(..., min_length=1)
    replacement: str
    base_hash: str = ""
    allow_multiple: bool = False
    workspace_root: str | None = None


class _TreeParam(BaseModel):
    subpath: str = "."
    max_depth: int = Field(3, ge=1, le=5)
    max_entries: int = Field(250, ge=1, le=600)
    workspace_root: str | None = None


class _SearchParam(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=500)
    subpath: str = "."
    file_glob: str = "*"
    max_matches: int = Field(100, ge=1, le=300)
    workspace_root: str | None = None


class _ExportParam(BaseModel):
    subpath: str = Field(..., min_length=1, max_length=500)
    output_zip: str = Field(..., min_length=1, max_length=500)
    workspace_root: str | None = None


class _VerifyParam(BaseModel):
    command: str = Field(..., min_length=1, max_length=600)
    subpath: str = "."
    timeout_seconds: int = Field(60, ge=1, le=120)
    workspace_root: str | None = None


class _PortCheckParam(BaseModel):
    port: int = Field(..., ge=1, le=65535)
    host: str = "127.0.0.1"


class _ProcessIdParam(BaseModel):
    process_id: str | None = None
    tail: int = Field(50, ge=1, le=300)


class _ProjectDetectParam(BaseModel):
    subpath: str = "."
    workspace_root: str | None = None


class _PreviewStartParam(BaseModel):
    command: str = Field(..., min_length=1, max_length=600)
    port: int = Field(..., ge=1024, le=65535)
    subpath: str = "."
    preview_id: str | None = None
    workspace_root: str | None = None


class _PreviewHealthParam(BaseModel):
    url: str = Field(..., min_length=8, max_length=500)
    preview_id: str | None = None


class _PreviewIdParam(BaseModel):
    preview_id: str = Field(..., min_length=1, max_length=120)


class _AuditUrlParam(BaseModel):
    url: str = Field(..., min_length=8, max_length=500)
    mobile: bool = False
    screenshot_path: str | None = None


class _ConnectorNameParam(BaseModel):
    name: str | None = None
    live_probe: bool = False


# ---------------------------------------------------------------------------
# Section 4: Workspace handlers delegating to workspace_coding_tools
# ---------------------------------------------------------------------------


async def workspace_read_alias_handler(params: WorkspaceReadFileParams) -> dict[str, Any]:
    return await workspace_read_file_handler(params)


async def workspace_write_alias_handler(params: _WriteParam) -> dict[str, Any]:
    return await workspace_write_file_handler(
        WorkspaceWriteFileParams(
            file_path=params.path,
            content=params.content,
            overwrite=params.overwrite,
            workspace_root=params.workspace_root,
        )
    )


async def workspace_patch_alias_handler(params: _PatchParam) -> dict[str, Any]:
    return await workspace_edit_file_handler(
        WorkspaceEditFileParams(
            file_path=params.path,
            target_content=params.target,
            replacement_content=params.replacement,
            base_hash=params.base_hash,
            allow_multiple=params.allow_multiple,
            workspace_root=params.workspace_root,
        )
    )


async def workspace_tree_handler(params: _TreeParam) -> dict[str, Any]:
    return await workspace_list_dir_handler(
        WorkspaceListDirParams(
            subpath=params.subpath,
            max_depth=params.max_depth,
            max_entries=params.max_entries,
            workspace_root=params.workspace_root,
        )
    )


async def workspace_search_handler(params: _SearchParam) -> dict[str, Any]:
    return await workspace_grep_handler(
        WorkspaceGrepParams(
            pattern=params.pattern,
            subpath=params.subpath,
            file_glob=params.file_glob,
            max_matches=params.max_matches,
            workspace_root=params.workspace_root,
        )
    )


async def workspace_hash_handler(params: _PathParam) -> dict[str, Any]:
    try:
        root = _resolve_workspace_root(params.workspace_root)
        target = _resolve_inside_workspace(root, params.path)
    except ValueError as err:
        return {"status": "error", "error": str(err)}
    if not target.is_file():
        return {"status": "error", "error": f"File not found: {params.path}"}
    return {
        "status": "success",
        "path": params.path,
        "sha256": compute_file_hash(target),
        "bytes": target.stat().st_size,
    }


async def workspace_export_handler(params: _ExportParam) -> dict[str, Any]:
    try:
        root = _resolve_workspace_root(params.workspace_root)
        src = _resolve_inside_workspace(root, params.subpath)
        dst = _resolve_inside_workspace(root, params.output_zip)
    except ValueError as err:
        return {"status": "error", "error": str(err)}
    if not src.exists():
        return {"status": "error", "error": f"Source does not exist: {params.subpath}"}
    dst.parent.mkdir(parents=True, exist_ok=True)
    exported = 0
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if src.is_file():
            zf.write(src, arcname=src.name)
            exported = 1
        else:
            for item in src.rglob("*"):
                if item.is_file() and not any(part in {".git", "node_modules", ".venv", "__pycache__", "dist"} for part in item.parts):
                    zf.write(item, arcname=item.relative_to(src).as_posix())
                    exported += 1
    digest = hashlib.sha256(dst.read_bytes()).hexdigest()
    return {
        "status": "success",
        "exportPath": params.output_zip,
        "filesExported": exported,
        "sha256": digest,
        "bytes": dst.stat().st_size,
    }


async def workspace_verify_handler(params: _VerifyParam) -> dict[str, Any]:
    root = _resolve_workspace_root(params.workspace_root)
    cwd = _resolve_inside_workspace(root, params.subpath)
    return await workspace_run_command_handler(
        WorkspaceRunCommandParams(
            command=params.command,
            timeout_seconds=params.timeout_seconds,
            workspace_root=str(cwd),
        )
    )


# ---------------------------------------------------------------------------
# Section 5: Terminal & Process handlers
# ---------------------------------------------------------------------------


async def terminal_execute_alias_handler(params: WorkspaceRunCommandParams) -> dict[str, Any]:
    return await workspace_run_command_handler(params)


async def process_start_handler(params: WorkspaceStartProcessParams) -> dict[str, Any]:
    return await workspace_start_process_handler(params)


async def process_stop_handler(params: WorkspaceStopProcessParams) -> dict[str, Any]:
    return await workspace_stop_process_handler(params)


async def process_logs_handler(params: WorkspaceProcessLogsParams) -> dict[str, Any]:
    return await workspace_process_logs_handler(params)


async def process_status_handler(params: _ProcessIdParam) -> dict[str, Any]:
    with _PROCESS_POOL_LOCK:
        if params.process_id:
            managed = _PROCESS_POOL.get(params.process_id)
            if managed is None:
                return {"status": "error", "error": f"Unknown process {params.process_id}"}
            items = [managed]
        else:
            items = list(_PROCESS_POOL.values())
        rows = [
            {
                "processId": m.process_id,
                "pid": m.proc.pid,
                "command": m.command,
                "running": m.running(),
                "exitCode": m.proc.poll(),
                "readyPort": m.ready_port,
            }
            for m in items
        ]
    return {"status": "success", "count": len(rows), "processes": rows}


async def port_check_handler(params: _PortCheckParam) -> dict[str, Any]:
    def _probe() -> bool:
        try:
            with socket.create_connection((params.host, params.port), timeout=0.6):
                return True
        except OSError:
            return False

    open_now = await asyncio.to_thread(_probe)
    return {
        "status": "success",
        "host": params.host,
        "port": params.port,
        "listening": open_now,
    }


async def build_project_handler(params: _VerifyParam) -> dict[str, Any]:
    return await workspace_verify_handler(params)


async def test_project_handler(params: _VerifyParam) -> dict[str, Any]:
    return await workspace_verify_handler(params)


# ---------------------------------------------------------------------------
# Section 6: Preview & Hosting Lifecycle handlers
# ---------------------------------------------------------------------------


def list_previews_snapshot() -> list[dict[str, Any]]:
    with _PREVIEW_LOCK:
        return [rec.model_dump() for rec in _PREVIEW_REGISTRY.values()]


async def project_detect_handler(params: _ProjectDetectParam) -> dict[str, Any]:
    try:
        root = _resolve_workspace_root(params.workspace_root)
        target = _resolve_inside_workspace(root, params.subpath)
    except ValueError as err:
        return {"status": "error", "error": str(err)}
    pkg_file = target / "package.json"
    pyproject_file = target / "pyproject.toml"
    framework = "static-html" if (target / "index.html").is_file() else "unknown"
    scripts: dict[str, str] = {}
    if pkg_file.is_file():
        try:
            pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            scripts = dict(pkg.get("scripts") or {})
            deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
            if "vite" in deps:
                framework = "vite-typescript" if "typescript" in deps else "vite"
            elif "next" in deps:
                framework = "nextjs"
            elif "react" in deps:
                framework = "react"
        except Exception:
            framework = "node"
    elif pyproject_file.is_file():
        framework = "python-fastapi"
    return {
        "status": "success",
        "subpath": params.subpath,
        "framework": framework,
        "hasPackageJson": pkg_file.is_file(),
        "hasPyproject": pyproject_file.is_file(),
        "hasIndexHtml": (target / "index.html").is_file(),
        "scripts": scripts,
        "stage": PreviewStage.DETECTED.value,
    }


def _probe_http_local(url: str) -> tuple[bool, int | None, str | None]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            return True, int(resp.status), None
    except urllib.error.HTTPError as he:
        return False, int(he.code), f"HTTP {he.code}"
    except Exception as exc:
        return False, None, str(exc)


async def preview_start_handler(params: _PreviewStartParam) -> dict[str, Any]:
    root = _resolve_workspace_root(params.workspace_root)
    cwd = _resolve_inside_workspace(root, params.subpath)
    res = await workspace_start_process_handler(
        WorkspaceStartProcessParams(
            command=params.command,
            ready_port=params.port,
            ready_wait_ms=4000,
            workspace_root=str(cwd),
        )
    )
    if res.get("status") != "success":
        return res
    url = f"http://127.0.0.1:{params.port}/"
    pid = params.preview_id or f"prev-{params.port}"
    http_ok, http_code, _err = await asyncio.to_thread(_probe_http_local, url)
    stage = PreviewStage.HTTP_200 if http_ok and http_code == 200 else (
        PreviewStage.LISTENING if res.get("listening") else PreviewStage.SERVER_STARTED
    )
    rec = PreviewRecord(
        preview_id=pid,
        project_path=params.subpath,
        framework="web-preview",
        port=params.port,
        url=url,
        process_id=str(res.get("processId")),
        stage=stage,
        routes=["/"],
        last_http_status=http_code,
        updated_at=_utc_iso(),
    )
    with _PREVIEW_LOCK:
        _PREVIEW_REGISTRY[pid] = rec
    return {
        "status": "success",
        "preview": rec.model_dump(),
        "process": res,
    }


async def preview_healthcheck_handler(params: _PreviewHealthParam) -> dict[str, Any]:
    http_ok, code, err = await asyncio.to_thread(_probe_http_local, params.url)
    stage = PreviewStage.HTTP_200 if (http_ok and code == 200) else PreviewStage.DEGRADED
    if params.preview_id:
        with _PREVIEW_LOCK:
            if params.preview_id in _PREVIEW_REGISTRY:
                rec = _PREVIEW_REGISTRY[params.preview_id]
                rec.last_http_status = code
                rec.stage = stage
                rec.updated_at = _utc_iso()
    return {
        "status": "success" if http_ok else "error",
        "url": params.url,
        "reachable": http_ok,
        "httpStatus": code,
        "stage": stage.value,
        "error": err,
    }


async def preview_routes_handler(params: _ProjectDetectParam) -> dict[str, Any]:
    root = _resolve_workspace_root(params.workspace_root)
    base = _resolve_inside_workspace(root, params.subpath)
    routes = ["/"]
    app_tsx = base / "src" / "App.tsx"
    if app_tsx.is_file():
        import re

        text = app_tsx.read_text(encoding="utf-8", errors="ignore")
        for match in re.findall(r'path=["\'](/[^"\']*)["\']', text):
            if match not in routes:
                routes.append(match)
    return {"status": "success", "subpath": params.subpath, "routes": routes}


async def preview_status_handler(params: _PreviewIdParam) -> dict[str, Any]:
    with _PREVIEW_LOCK:
        rec = _PREVIEW_REGISTRY.get(params.preview_id)
    if rec is None:
        return {"status": "error", "error": f"Unknown preview_id '{params.preview_id}'"}
    return {"status": "success", "preview": rec.model_dump()}


async def preview_stop_handler(params: _PreviewIdParam) -> dict[str, Any]:
    with _PREVIEW_LOCK:
        rec = _PREVIEW_REGISTRY.get(params.preview_id)
    if rec is None:
        return {"status": "error", "error": f"Unknown preview_id '{params.preview_id}'"}
    stop_res: dict[str, Any] = {"status": "success"}
    if rec.process_id:
        stop_res = await workspace_stop_process_handler(WorkspaceStopProcessParams(process_id=rec.process_id))
    rec.stage = PreviewStage.STOPPED
    rec.updated_at = _utc_iso()
    return {"status": "success", "preview": rec.model_dump(), "stop": stop_res}


# ---------------------------------------------------------------------------
# Section 7 & 8: Live Playwright Verification & Audit tools (no fabrication)
# ---------------------------------------------------------------------------


async def _run_playwright_audit(url: str, *, mobile: bool = False, screenshot_path: str | None = None) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        return {
            "status": "error",
            "verificationState": CapabilityState.UNAVAILABLE.value,
            "error": f"Playwright unavailable: {exc}",
        }

    viewport = {"width": 390, "height": 844} if mobile else {"width": 1280, "height": 800}
    console_errors: list[str] = []
    page_errors: list[str] = []
    t0 = time.perf_counter()
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(viewport=viewport)
            page = await context.new_page()
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: page_errors.append(str(err)))
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            await page.wait_for_timeout(450)
            metrics = await page.evaluate(
                """() => {
                    const doc = document.documentElement;
                    const imgs = Array.from(document.querySelectorAll('img'));
                    const brokenImgs = imgs.filter(i => !i.complete || i.naturalWidth === 0).length;
                    const buttons = Array.from(document.querySelectorAll('button,a,input,select'));
                    const unlabelled = buttons.filter(el => {
                        const txt = (el.textContent || '').trim();
                        const aria = el.getAttribute('aria-label') || el.getAttribute('title') || '';
                        return !txt && !aria;
                    }).length;
                    return {
                        title: document.title,
                        horizontalOverflowPx: Math.max(0, doc.scrollWidth - window.innerWidth),
                        brokenImages: brokenImgs,
                        interactiveCount: buttons.length,
                        unlabelledControls: unlabelled,
                        canvasCount: document.querySelectorAll('canvas').length,
                    };
                }"""
            )
            saved_shot = None
            if screenshot_path:
                shot_file = Path(screenshot_path)
                shot_file.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(shot_file), full_page=False)
                saved_shot = str(shot_file)
            await browser.close()
    except Exception as exc:
        return {
            "status": "error",
            "url": url,
            "verificationState": CapabilityState.FAILED.value,
            "error": str(exc),
        }

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    http_status = resp.status if resp else None
    all_clean = (
        http_status is not None
        and http_status < 400
        and len(console_errors) == 0
        and len(page_errors) == 0
        and metrics.get("horizontalOverflowPx", 0) <= 2
        and metrics.get("brokenImages", 0) == 0
    )
    return {
        "status": "success" if all_clean else "error",
        "url": url,
        "viewport": viewport,
        "httpStatus": http_status,
        "loadMs": elapsed_ms,
        "consoleErrorCount": len(console_errors),
        "consoleErrors": console_errors[:10],
        "pageErrorCount": len(page_errors),
        "pageErrors": page_errors[:10],
        "screenshotPath": saved_shot,
        "metrics": metrics,
        "verificationState": CapabilityState.HEALTHY.value if all_clean else CapabilityState.DEGRADED.value,
    }


async def visual_snapshot_handler(params: _AuditUrlParam) -> dict[str, Any]:
    return await _run_playwright_audit(params.url, mobile=params.mobile, screenshot_path=params.screenshot_path)


async def layout_audit_handler(params: _AuditUrlParam) -> dict[str, Any]:
    return await _run_playwright_audit(params.url, mobile=params.mobile)


async def responsive_audit_handler(params: _AuditUrlParam) -> dict[str, Any]:
    desktop = await _run_playwright_audit(params.url, mobile=False)
    mobile = await _run_playwright_audit(params.url, mobile=True)
    ok = desktop.get("status") == "success" and mobile.get("status") == "success"
    return {"status": "success" if ok else "error", "desktop": desktop, "mobile": mobile}


async def accessibility_audit_handler(params: _AuditUrlParam) -> dict[str, Any]:
    return await _run_playwright_audit(params.url, mobile=params.mobile)


async def performance_audit_handler(params: _AuditUrlParam) -> dict[str, Any]:
    return await _run_playwright_audit(params.url, mobile=params.mobile)


async def console_error_audit_handler(params: _AuditUrlParam) -> dict[str, Any]:
    return await _run_playwright_audit(params.url, mobile=params.mobile)


# ---------------------------------------------------------------------------
# Section 9: Connector & Auth Readiness Inventory
# ---------------------------------------------------------------------------


def _build_connector_inventory(settings: Settings) -> list[dict[str, Any]]:
    el_cooled = voice_on_cooldown("elevenlabs")
    edge_ok = True
    try:
        import edge_tts  # noqa: F401
    except Exception:
        edge_ok = False

    def _key_state(configured: bool, *, note: str = "", degraded: bool = False) -> tuple[str, str]:
        if not configured:
            return CapabilityState.UNAVAILABLE.value, note or "Credential not configured in environment"
        if degraded:
            return CapabilityState.DEGRADED.value, note or "Configured credential currently throttled/unhealthy"
        return CapabilityState.CONFIGURED.value, note or "Credential configured locally (live probe optional)"

    items: list[dict[str, Any]] = []
    connectors_spec = [
        ("edge_tts", CapabilityState.HEALTHY.value if edge_ok else CapabilityState.UNAVAILABLE.value, "Free unlimited Microsoft Edge Neural TTS", True),
        ("deepgram", *_key_state(settings.deepgram_configured, note="Deepgram Aura-2 TTS + Nova STT"), True),
        ("elevenlabs", *_key_state(settings.elevenlabs_configured, note="Payment/invoice refusal or cooldown" if el_cooled else "ElevenLabs neural voice", degraded=el_cooled), False),
        ("fish_audio", *_key_state(settings.fish_audio_configured, note="Fish Audio TTS key present (check credit balance)"), False),
        ("heygen", *_key_state(settings.heygen_configured, note="HeyGen Video & Avatar API key stored securely"), False),
        ("azure_speech", *_key_state(settings.azure_configured, note="Azure Cognitive Speech TTS"), False),
        ("xkiro", *_key_state(bool(getattr(settings, "xkiro_configured", False)), note="XKiro LLM/Image gateway"), False),
        ("gemini", *_key_state(settings.gemini_configured, note="Google Gemini API"), False),
        ("openai", *_key_state(bool(settings.openai_api_key and settings.openai_api_key.get_secret_value()), note="OpenAI API"), False),
        ("claude", *_key_state(settings.claude_configured, note="Anthropic Claude API"), False),
        ("workspace_fs", CapabilityState.HEALTHY.value, f"Workspace root confined to {_resolve_workspace_root()}", True),
        ("process_supervisor", CapabilityState.HEALTHY.value, "Bounded local process & loopback port verifier", True),
    ]
    for cid, state, summary, *rest in connectors_spec:
        items.append({
            "id": cid,
            "state": state,
            "summary": summary,
            "checkedAt": _utc_iso(),
        })
    return items


async def connector_list_handler(_params: _ConnectorNameParam | None = None) -> dict[str, Any]:
    settings = get_settings()
    rows = _build_connector_inventory(settings)
    return {"status": "success", "count": len(rows), "connectors": rows}


async def connector_status_handler(params: _ConnectorNameParam) -> dict[str, Any]:
    settings = get_settings()
    rows = _build_connector_inventory(settings)
    if params.name:
        for row in rows:
            if row["id"] == params.name:
                return {"status": "success", "connector": row}
        return {"status": "error", "error": f"Unknown connector '{params.name}'"}
    return {"status": "success", "connectors": rows}


async def connector_test_handler(params: _ConnectorNameParam) -> dict[str, Any]:
    settings = get_settings()
    name = (params.name or "").strip().lower()
    if not name:
        return await connector_healthcheck_handler(params)

    if name == "edge_tts":
        try:
            import edge_tts  # noqa: F401
            return {"status": "success", "id": name, "state": CapabilityState.TESTED.value, "detail": "edge_tts module loaded cleanly."}
        except Exception as exc:
            return {"status": "error", "id": name, "state": CapabilityState.FAILED.value, "error": str(exc)}

    if name == "heygen":
        if not settings.heygen_configured:
            return {"status": "error", "id": name, "state": CapabilityState.UNAVAILABLE.value, "error": "HEYGEN_API_KEY missing"}
        assert settings.heygen_api_key
        key_val = settings.heygen_api_key.get_secret_value()
        url = f"{settings.heygen_base_url.rstrip('/')}/v2/voices"

        def _probe() -> tuple[bool, int | None, str]:
            req = urllib.request.Request(url, headers={"X-Api-Key": key_val, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    return True, int(resp.status), "HeyGen /v2/voices reachable & authorized"
            except urllib.error.HTTPError as he:
                return False, int(he.code), f"HeyGen HTTP {he.code}"
            except Exception as exc:
                return False, None, str(exc)

        ok, code, detail = await asyncio.to_thread(_probe)
        state = CapabilityState.HEALTHY if ok else (CapabilityState.REVOKED if code == 401 else CapabilityState.FAILED)
        return {"status": "success" if ok else "error", "id": name, "state": state.value, "httpStatus": code, "detail": detail}

    if name == "deepgram":
        if not settings.deepgram_configured:
            return {"status": "error", "id": name, "state": CapabilityState.UNAVAILABLE.value, "error": "DEEPGRAM_API_KEY missing"}
        return {"status": "success", "id": name, "state": CapabilityState.CONFIGURED.value, "detail": "Deepgram key present; /v1/speak enabled."}

    return await connector_status_handler(_ConnectorNameParam(name=name))


async def connector_healthcheck_handler(params: _ConnectorNameParam | None = None) -> dict[str, Any]:
    settings = get_settings()
    rows = _build_connector_inventory(settings)
    if params and params.live_probe:
        for idx, row in enumerate(list(rows)):
            if row["id"] in {"edge_tts", "heygen"} and row["state"] != CapabilityState.UNAVAILABLE.value:
                tested = await connector_test_handler(_ConnectorNameParam(name=row["id"]))
                rows[idx] = {**row, "state": tested.get("state", row["state"]), "detail": tested.get("detail", row["summary"])}
    healthy_states = {CapabilityState.HEALTHY.value, CapabilityState.TESTED.value, CapabilityState.CONFIGURED.value, CapabilityState.AUTHORIZED.value, CapabilityState.CONNECTED.value, CapabilityState.REACHABLE.value}
    degraded_count = sum(1 for r in rows if r["state"] in {CapabilityState.DEGRADED.value, CapabilityState.FAILED.value, CapabilityState.REVOKED.value})
    active_count = sum(1 for r in rows if r["state"] in healthy_states)
    return {
        "status": "success",
        "allowedStates": list(ALLOWED_CAPABILITY_STATES),
        "previewStages": list(PREVIEW_STAGES),
        "activeCount": active_count,
        "degradedCount": degraded_count,
        "connectors": rows,
    }


def register_runtime_os_tools() -> None:
    """Register formal Section 4-9 runtime tools onto the global ToolRegistry cleanly."""
    global _OS_TOOLS_REGISTERED
    if _OS_TOOLS_REGISTERED:
        return
    _OS_TOOLS_REGISTERED = True

    specs: list[tuple[ToolDefinition, Any]] = [
        # Section 4: Workspace
        (ToolDefinition(name="workspace_read", display_name="OS: Workspace Read", description="Read bounded workspace file slices.", parameters={"file_path": {"type": "string"}}, required_parameters=["file_path"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="file_system"), workspace_read_alias_handler),
        (ToolDefinition(name="workspace_write", display_name="OS: Workspace Write", description="Write a file atomically inside the workspace.", parameters={"path": {"type": "string"}, "content": {"type": "string"}}, required_parameters=["path", "content"], is_read_only=False, is_concurrency_safe=False, requires_confirmation=True, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.MUTATE_WORKSPACE, audit_category="file_system"), workspace_write_alias_handler),
        (ToolDefinition(name="workspace_patch", display_name="OS: Workspace Patch", description="Patch an exact snippet inside a workspace file.", parameters={"path": {"type": "string"}, "target": {"type": "string"}, "replacement": {"type": "string"}}, required_parameters=["path", "target", "replacement"], is_read_only=False, is_concurrency_safe=False, requires_confirmation=True, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.MUTATE_WORKSPACE, audit_category="file_system"), workspace_patch_alias_handler),
        (ToolDefinition(name="workspace_tree", display_name="OS: Workspace Tree", description="List bounded directory tree inside workspace.", parameters={"subpath": {"type": "string"}}, required_parameters=[], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="file_system"), workspace_tree_handler),
        (ToolDefinition(name="workspace_search", display_name="OS: Workspace Search", description="Search regex/text across workspace files.", parameters={"pattern": {"type": "string"}}, required_parameters=["pattern"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="file_system"), workspace_search_handler),
        (ToolDefinition(name="workspace_hash", display_name="OS: Workspace SHA-256", description="Compute SHA-256 digest of a workspace file.", parameters={"path": {"type": "string"}}, required_parameters=["path"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="file_system"), workspace_hash_handler),
        (ToolDefinition(name="workspace_export", display_name="OS: Workspace Zip Export", description="Create a bounded ZIP bundle of a workspace subfolder.", parameters={"subpath": {"type": "string"}, "output_zip": {"type": "string"}}, required_parameters=["subpath", "output_zip"], is_read_only=False, is_concurrency_safe=False, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.MUTATE_WORKSPACE, audit_category="file_system"), workspace_export_handler),
        (ToolDefinition(name="workspace_verify", display_name="OS: Workspace Verify", description="Run bounded verification/lint/build command in workspace subpath.", parameters={"command": {"type": "string"}}, required_parameters=["command"], is_read_only=False, is_concurrency_safe=False, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.EXECUTE_PROCESS, audit_category="terminal"), workspace_verify_handler),
        # Section 5: Terminal & Processes
        (ToolDefinition(name="terminal_execute", display_name="OS: Terminal Execute", description="Execute bounded safe command in workspace.", parameters={"command": {"type": "string"}}, required_parameters=["command"], is_read_only=False, is_concurrency_safe=False, requires_confirmation=True, risk_tier=RiskTier.TIER_3_PROCESS, tool_effect=ToolEffect.EXECUTE_PROCESS, audit_category="terminal"), terminal_execute_alias_handler),
        (ToolDefinition(name="process_start", display_name="OS: Start Process", description="Start bounded background server process.", parameters={"command": {"type": "string"}}, required_parameters=["command"], is_read_only=False, is_concurrency_safe=False, requires_confirmation=True, risk_tier=RiskTier.TIER_3_PROCESS, tool_effect=ToolEffect.EXECUTE_PROCESS, audit_category="terminal"), process_start_handler),
        (ToolDefinition(name="process_stop", display_name="OS: Stop Process", description="Stop a managed background process.", parameters={"process_id": {"type": "string"}}, required_parameters=["process_id"], is_read_only=False, is_concurrency_safe=False, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.EXECUTE_PROCESS, audit_category="terminal"), process_stop_handler),
        (ToolDefinition(name="process_status", display_name="OS: Process Status", description="Inspect managed background processes and ports.", parameters={"process_id": {"type": "string"}}, required_parameters=[], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="terminal"), process_status_handler),
        (ToolDefinition(name="process_logs", display_name="OS: Process Logs", description="Read trailing stdout/stderr of managed process.", parameters={"process_id": {"type": "string"}}, required_parameters=["process_id"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="terminal"), process_logs_handler),
        (ToolDefinition(name="port_check", display_name="OS: Loopback Port Check", description="Check whether a local TCP port is listening.", parameters={"port": {"type": "integer"}}, required_parameters=["port"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="network"), port_check_handler),
        (ToolDefinition(name="build_project", display_name="OS: Build Project", description="Run bounded build command inside project directory.", parameters={"command": {"type": "string"}}, required_parameters=["command"], is_read_only=False, is_concurrency_safe=False, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.EXECUTE_PROCESS, audit_category="code"), build_project_handler),
        (ToolDefinition(name="test_project", display_name="OS: Test Project", description="Run bounded test suite inside project directory.", parameters={"command": {"type": "string"}}, required_parameters=["command"], is_read_only=False, is_concurrency_safe=False, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.EXECUTE_PROCESS, audit_category="code"), test_project_handler),
        # Section 6: Preview & Hosting
        (ToolDefinition(name="project_detect", display_name="OS: Detect Project Stack", description="Detect framework, scripts, and entrypoints for a project directory.", parameters={"subpath": {"type": "string"}}, required_parameters=[], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="code"), project_detect_handler),
        (ToolDefinition(name="preview_start", display_name="OS: Start Live Preview", description="Start local preview server and probe loopback HTTP 200 readiness.", parameters={"command": {"type": "string"}, "port": {"type": "integer"}}, required_parameters=["command", "port"], is_read_only=False, is_concurrency_safe=False, requires_confirmation=True, risk_tier=RiskTier.TIER_3_PROCESS, tool_effect=ToolEffect.EXECUTE_PROCESS, audit_category="browser"), preview_start_handler),
        (ToolDefinition(name="preview_healthcheck", display_name="OS: Preview HTTP Healthcheck", description="Verify a preview URL responds over loopback HTTP.", parameters={"url": {"type": "string"}}, required_parameters=["url"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="browser"), preview_healthcheck_handler),
        (ToolDefinition(name="preview_routes", display_name="OS: Inspect Preview Routes", description="Inspect discovered frontend routes inside a workspace web project.", parameters={"subpath": {"type": "string"}}, required_parameters=[], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="browser"), preview_routes_handler),
        (ToolDefinition(name="preview_status", display_name="OS: Preview Stage Status", description="Inspect 9-stage readiness status of a registered preview.", parameters={"preview_id": {"type": "string"}}, required_parameters=["preview_id"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="browser"), preview_status_handler),
        (ToolDefinition(name="preview_stop", display_name="OS: Stop Preview", description="Stop a managed preview server and mark preview stopped.", parameters={"preview_id": {"type": "string"}}, required_parameters=["preview_id"], is_read_only=False, is_concurrency_safe=False, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.EXECUTE_PROCESS, audit_category="browser"), preview_stop_handler),
        # Section 7 & 8: Browser & Quality Audits
        (ToolDefinition(name="visual_snapshot", display_name="OS: Playwright Snapshot", description="Capture headless Playwright render and DOM telemetry.", parameters={"url": {"type": "string"}}, required_parameters=["url"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.READ, audit_category="browser"), visual_snapshot_handler),
        (ToolDefinition(name="layout_audit", display_name="OS: Layout Overlap & Overflow Audit", description="Audit horizontal overflow, broken images, and controls via headless Playwright.", parameters={"url": {"type": "string"}}, required_parameters=["url"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.READ, audit_category="browser"), layout_audit_handler),
        (ToolDefinition(name="responsive_audit", display_name="OS: Desktop & Mobile Responsive Audit", description="Verify both 1280x800 desktop and 390x844 mobile rendering.", parameters={"url": {"type": "string"}}, required_parameters=["url"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.READ, audit_category="browser"), responsive_audit_handler),
        (ToolDefinition(name="accessibility_audit", display_name="OS: Accessibility Label Audit", description="Inspect unlabelled interactive controls via headless Playwright.", parameters={"url": {"type": "string"}}, required_parameters=["url"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.READ, audit_category="browser"), accessibility_audit_handler),
        (ToolDefinition(name="performance_audit", display_name="OS: Page Load Performance Audit", description="Measure DOM content load timing and console stability.", parameters={"url": {"type": "string"}}, required_parameters=["url"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.READ, audit_category="browser"), performance_audit_handler),
        (ToolDefinition(name="console_error_audit", display_name="OS: Console Error Audit", description="Verify zero uncaught console or page errors in headless Playwright.", parameters={"url": {"type": "string"}}, required_parameters=["url"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_1_REVERSIBLE, tool_effect=ToolEffect.READ, audit_category="browser"), console_error_audit_handler),
        # Section 9: Connectors
        (ToolDefinition(name="connector_list", display_name="OS: List Connectors", description="List all configured providers/connectors and 12-state readiness.", parameters={}, required_parameters=[], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="network"), connector_list_handler),
        (ToolDefinition(name="connector_status", display_name="OS: Connector Status", description="Inspect specific connector 12-state status.", parameters={"name": {"type": "string"}}, required_parameters=[], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.READ, audit_category="network"), connector_status_handler),
        (ToolDefinition(name="connector_test", display_name="OS: Live Test Connector", description="Run live health probe on a named connector (edge_tts, heygen, etc.).", parameters={"name": {"type": "string"}}, required_parameters=["name"], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.EXTERNAL_NETWORK, audit_category="network"), connector_test_handler),
        (ToolDefinition(name="connector_healthcheck", display_name="OS: Aggregate Connector Health", description="Evaluate 12-state health summary across all runtime connectors.", parameters={"live_probe": {"type": "boolean"}}, required_parameters=[], is_read_only=True, is_concurrency_safe=True, requires_confirmation=False, risk_tier=RiskTier.TIER_0_READ_ONLY, tool_effect=ToolEffect.EXTERNAL_NETWORK, audit_category="network"), connector_healthcheck_handler),
    ]

    for tdef, fn in specs:
        if registry.get(tdef.name) is None:
            registry.register(tdef, fn)
