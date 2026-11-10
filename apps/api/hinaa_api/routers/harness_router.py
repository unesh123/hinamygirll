"""
Router for Frontier Agent Harness & Fleet Endpoints.
Extracted from main.py to maintain modular enterprise architecture.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ..errors import HinaaError

router = APIRouter(tags=["harness"])


# -----------------------------------------------------------------------
# Frontier Agent Harness & Operating Core (Codex ThreadManager Architecture)
# -----------------------------------------------------------------------

@router.post("/v1/harness/threads")
@router.post("/api/v1/harness/threads")
async def harness_create_thread(request: Request) -> dict[str, Any]:
    from hinaa_api.harness import ReasoningEffort, get_thread_manager
    tm = get_thread_manager()
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    thread = tm.create_thread(
        title=body.get("title", "Autonomous HINA Session"),
        model_name=body.get("model", "agnes-2.5-flash"),
        provider_mode=body.get("providerMode", "agent-router"),
        reasoning_effort=ReasoningEffort(body.get("reasoningEffort", "medium")),
    )
    return {"status": "success", "thread": thread.model_dump(mode="json")}


@router.get("/v1/harness/threads")
@router.get("/api/v1/harness/threads")
async def harness_list_threads() -> dict[str, Any]:
    from hinaa_api.harness import get_thread_manager
    tm = get_thread_manager()
    threads = tm.list_threads()
    return {"status": "success", "threads": [t.model_dump(mode="json") for t in threads]}


@router.get("/v1/harness/threads/{thread_id}")
@router.get("/api/v1/harness/threads/{thread_id}")
async def harness_get_thread(thread_id: str) -> dict[str, Any]:
    from hinaa_api.harness import get_thread_manager
    tm = get_thread_manager()
    thread = tm.get_thread(thread_id)
    if not thread:
        raise HinaaError("NOT_FOUND", f"Thread {thread_id} not found", 404, False, False)
    return {"status": "success", "thread": thread.model_dump(mode="json")}


@router.post("/v1/harness/threads/{thread_id}/fork")
@router.post("/api/v1/harness/threads/{thread_id}/fork")
async def harness_fork_thread(thread_id: str, request: Request) -> dict[str, Any]:
    from hinaa_api.harness import get_thread_manager
    tm = get_thread_manager()
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    forked = tm.fork_thread(
        source_thread_id=thread_id,
        from_turn_ordinal=body.get("fromTurnOrdinal"),
        title=body.get("title"),
    )
    return {"status": "success", "forkedThread": forked.model_dump(mode="json")}


@router.get("/v1/harness/threads/{thread_id}/graph")
@router.get("/api/v1/harness/threads/{thread_id}/graph")
async def harness_get_graph(thread_id: str) -> dict[str, Any]:
    from hinaa_api.harness import get_thread_manager
    tm = get_thread_manager()
    thread = tm.get_thread(thread_id)
    if not thread or not thread.active_session or not thread.active_session.graph_node_id:
        raise HinaaError("NOT_FOUND", "Graph not found for thread", 404, False, False)
    tree = tm.scheduler.export_graph_tree(thread.active_session.graph_node_id)
    return {"status": "success", "graph": tree, "allNodes": {k: v.model_dump(mode="json") for k, v in tm.scheduler.nodes.items()}}


@router.get("/v1/harness/threads/{thread_id}/board")
@router.get("/api/v1/harness/threads/{thread_id}/board")
async def harness_get_board(thread_id: str) -> dict[str, Any]:
    from hinaa_api.harness import get_thread_manager
    tm = get_thread_manager()
    messages = tm.scheduler.message_board.get_all_messages()
    return {"status": "success", "messages": [m.model_dump(mode="json") for m in messages]}


@router.post("/v1/harness/threads/{thread_id}/subagents")
@router.post("/api/v1/harness/threads/{thread_id}/subagents")
async def harness_spawn_subagent(thread_id: str, request: Request) -> dict[str, Any]:
    from hinaa_api.harness import AgentRole, get_thread_manager
    tm = get_thread_manager()
    body = await request.json()
    role = AgentRole(body.get("role", "researcher"))
    objective = body.get("objective", "Autonomous subtask")
    child_node = tm.spawn_subagent(thread_id, role, objective, body.get("toolPermissions"))
    return {"status": "success", "subagent": child_node.model_dump(mode="json")}


@router.get("/v1/harness/repository-memory")
@router.get("/api/v1/harness/repository-memory")
async def harness_repo_memory() -> dict[str, Any]:
    from hinaa_api.harness import get_thread_manager
    tm = get_thread_manager()
    return {
        "status": "success",
        "workspaceRoot": tm.workspace_root,
        "memory": tm.repo_memory.load_memory_context(),
        "compiledPromptBlock": tm.repo_memory.compile_prompt_block(),
    }


@router.get("/v1/harness/effective-policy")
@router.get("/api/v1/harness/effective-policy")
async def harness_effective_policy() -> dict[str, Any]:
    from hinaa_api.harness import get_thread_manager
    tm = get_thread_manager()
    default_thread = next(iter(tm._threads.values()), None)
    sess = default_thread.active_session if default_thread else None
    return {
        "status": "success",
        "workspaceRoots": [tm.workspace_root],
        "effectiveFilesystemRoots": sess.environment.canonical_roots() if sess else [tm.workspace_root],
        "shellRuntime": sess.environment.shell_runtime if sess else "kali-linux-wsl",
        "networkPolicy": sess.environment.network_policy.model_dump(mode="json") if sess else {
            "egress_enabled": True,
            "dns_allowlist_only": True,
            "allowed_domains": ["github.com", "api.github.com", "pypi.org", "npmjs.org"]
        },
        "ghsa_w5fx_fh39_j5rw_mitigation": "ACTIVE (canonical root enforcement)",
        "secretStripping": "ACTIVE (child process env & stream output redaction)",
    }


@router.post("/v1/harness/verify")
@router.post("/api/v1/harness/verify")
async def harness_verify_output(request: Request) -> dict[str, Any]:
    from hinaa_api.harness import get_thread_manager
    tm = get_thread_manager()
    body = await request.json()
    rep = tm.verify_output(
        text=body.get("text", ""),
        is_speech=body.get("isSpeech", False),
        file_path=body.get("filePath"),
    )
    return {"status": "success", "report": rep.model_dump(mode="json")}


@router.get("/v1/harness/models")
@router.get("/api/v1/harness/models")
async def harness_list_models() -> dict[str, Any]:
    from hinaa_api.harness import get_model_registry
    reg = get_model_registry()
    models = reg.list_models()
    return {"status": "success", "models": [m.model_dump(mode="json") for m in models]}


@router.get("/v1/harness/telemetry")
@router.get("/api/v1/harness/telemetry")
async def harness_get_telemetry() -> dict[str, Any]:
    from hinaa_api.harness import get_telemetry_probe
    probe = get_telemetry_probe()
    health = probe.get_live_health()
    return {"status": "success", "health": health.model_dump(mode="json")}


@router.post("/v1/harness/verify-release")
@router.post("/api/v1/harness/verify-release")
async def harness_verify_release(request: Request) -> dict[str, Any]:
    from hinaa_api.harness import get_telemetry_probe
    probe = get_telemetry_probe()
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    git_commit = body.get("gitCommit", "ca86cd3")
    record = probe.run_release_verification(git_commit=git_commit)
    return {"status": "success", "verificationRecord": record.model_dump(mode="json")}


@router.post("/v1/harness/browser/evaluate")
@router.post("/api/v1/harness/browser/evaluate")
async def harness_browser_evaluate(request: Request) -> dict[str, Any]:
    from hinaa_api.harness import IsolatedBrowserRuntime
    body = await request.json()
    html = body.get("html", "")
    title = body.get("title", "Web Application")
    auto_repair = body.get("autoRepair", True)
    repaired_code, report = IsolatedBrowserRuntime.evaluate_and_repair(html, title=title, auto_repair=auto_repair)
    return {
        "status": "success",
        "repairedCode": repaired_code,
        "report": report.model_dump(mode="json"),
    }


@router.get("/v1/harness/motion/state")
@router.get("/api/v1/harness/motion/state")
async def harness_get_motion_state() -> dict[str, Any]:
    from hinaa_api.harness import get_motion_director
    director = get_motion_director()
    return {
        "status": "success",
        "semanticState": director.current_state.model_dump(mode="json"),
        "motionProfile": director.current_profile.model_dump(mode="json"),
    }


@router.post("/v1/harness/motion/transition")
@router.post("/api/v1/harness/motion/transition")
async def harness_transition_motion(request: Request) -> dict[str, Any]:
    from hinaa_api.harness import SemanticIntent, get_motion_director
    director = get_motion_director()
    body = await request.json()
    intent_raw = body.get("intent", "thinking")
    try:
        intent = SemanticIntent(intent_raw)
    except ValueError:
        intent = SemanticIntent.WAITING

    profile = director.transition_state(
        intent=intent,
        active_tool=body.get("activeTool"),
        active_agent=body.get("activeAgent"),
        progress=float(body.get("progress", 0.0)),
        energy=float(body["energy"]) if "energy" in body else None,
        focus=float(body["focus"]) if "focus" in body else None,
    )
    return {
        "status": "success",
        "semanticState": director.current_state.model_dump(mode="json"),
        "motionProfile": profile.model_dump(mode="json"),
    }


# -----------------------------------------------------------------------
# Enterprise Device Fleet & Canonical Replay Endpoints
# -----------------------------------------------------------------------

@router.get("/v1/fleet/devices")
@router.get("/api/v1/fleet/devices")
async def fleet_list_devices() -> dict[str, Any]:
    """Lists online companion devices and their hardware/capability inventories."""
    from hinaa_api.fleet.device_fleet import get_fleet_manager
    mgr = get_fleet_manager()
    devices = mgr.list_devices(include_offline=True)
    return {
        "status": "success",
        "devices": [d.model_dump(mode="json") for d in devices],
        "totalOnline": len([d for d in devices if d.status == "online"]),
    }


@router.post("/v1/fleet/devices/heartbeat")
@router.post("/api/v1/fleet/devices/heartbeat")
async def fleet_device_heartbeat(request: Request) -> dict[str, Any]:
    """Records a heartbeat from an edge companion device."""
    from hinaa_api.fleet.device_fleet import get_fleet_manager
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    device_id = body.get("device_id", "dev_local_primary")
    tasks_count = int(body.get("current_tasks_count", 0))
    mgr = get_fleet_manager()
    ok = mgr.record_heartbeat(device_id, tasks_count=tasks_count)
    return {"status": "success" if ok else "not_found", "device_id": device_id}


@router.get("/v1/harness/runs/{run_id}/replay")
@router.get("/api/v1/harness/runs/{run_id}/replay")
async def harness_replay_run(run_id: str) -> dict[str, Any]:
    """Returns the step-by-step audit replay timeline for a specific task run."""
    from hinaa_api.harness.canonical_event_bus import get_canonical_event_bus
    bus = get_canonical_event_bus()
    timeline = bus.replay_run(run_id)
    trace = bus.get_run_trace(run_id)
    return {
        "status": "success",
        "runId": run_id,
        "totalSteps": len(timeline),
        "timeline": timeline,
        "success": trace.success if trace else True,
        "startedAt": trace.started_at if trace else None,
        "completedAt": trace.completed_at if trace else None,
    }


@router.get("/v1/harness/runs/{run_id}/trace")
@router.get("/api/v1/harness/runs/{run_id}/trace")
async def harness_get_trace(run_id: str) -> dict[str, Any]:
    """Returns the complete OpenTelemetry-compatible event trace for a run."""
    from hinaa_api.harness.canonical_event_bus import get_canonical_event_bus
    bus = get_canonical_event_bus()
    trace = bus.get_run_trace(run_id)
    if not trace:
        raise HinaaError("NOT_FOUND", f"Run {run_id} not found in event bus", 404, False, False)
    return {
        "status": "success",
        "trace": trace.model_dump(mode="json"),
    }
